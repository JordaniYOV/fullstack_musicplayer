import asyncio

from typing import Optional
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import KafkaConnectionError, TopicAlreadyExistsError
from dataclasses import dataclass, field

from app.core.config import settings
from app.logging_config import get_logger

TOPIC_PLAY_EVENTS = "play-events"
TOPIC_PLAY_EVENTS_DLQ = "play-events.dlq"

TOPIC_USER_LIKES = "user-events"
TOPIC_USER_LIKES_DLQ = "user-events.dlq"

TOPIC_CHART_UPDATES = "chart-updates"

logger = get_logger("app.core.kafka.topics")

@dataclass
class TopicSpec:
    name: str
    partitions: int = 3
    replication_factor: int = 1
    config: dict = field(default_factory=dict)

TOPIC_SPECS: list[TopicSpec] = [
    TopicSpec(
        name=TOPIC_PLAY_EVENTS,
        partitions=6, 
        config={
            "retention.ms": str(7 * 24 * 3600 * 1000), # 7 days
            "cleanup.policy": "delete",
        }
    ), 
     TopicSpec(
        name=TOPIC_PLAY_EVENTS_DLQ,
        partitions=1,
        config={"retention.ms": str(30 * 24 * 3600 * 1000)},  # 30 days
    ),
    TopicSpec(
        name=TOPIC_USER_LIKES,
        partitions=3,
        config={"retention.ms": str(7 * 24 * 3600 * 1000)},
    ),
    TopicSpec(
        name=TOPIC_USER_LIKES_DLQ,
        partitions=1,
        config={"retention.ms": str(30 * 24 * 3600 * 1000)},
    ),
    TopicSpec(
        name=TOPIC_CHART_UPDATES,
        partitions=1,
        config={"retention.ms": str(24 * 3600 * 1000)},        # 1 day
    ),
]


async def auto_create_topics(
        bootstrap_servers: Optional[str] = None,
        max_retries: int = 5,
        retry_delay: float = 3.0
) -> None:
    """
    Indepedantly create all topics defined in TOPIC_SPECS.
    Called at app start with lifspan creation.
    Errors are logged but never raised.A missing topic will surface as a produce/consume error later
    """
    servers = bootstrap_servers or settings.kafka_bootstrap_servers

    for attempt in range(1, max_retries + 1):
        admin: Optional[AIOKafkaAdminClient] = None
        try:
            admin = AIOKafkaAdminClient(bootstrap_servers=servers)
            await admin.start()
 
            new_topics = [
                NewTopic(
                    name=spec.name,
                    num_partitions=spec.partitions,
                    replication_factor=spec.replication_factor,
                    topic_configs=spec.config,
                )
                for spec in TOPIC_SPECS
            ]
 
            results = await admin.create_topics(new_topics, validate_only=False)
 
            for topic, error_code, error_message in results.topic_errors:
                if error_code == 0 or error_code == 36: # 36 = TopicAlreadyExists
                    logger.info(
                        "kafka_topic_ready",
                        extra={"topic": topic, "already_existed": error_message == 36},
                    )
                else:
                    logger.error(
                        "kafka_topic_create_failed",
                        extra={"topic": topic, "error": str(error_message)},
                    )
 
            logger.info(
                "kafka_topics_initialised",
                extra={"count": len(TOPIC_SPECS), "attempt": attempt},
            )
            return 
        
        except KafkaConnectionError as exc:
            logger.warning(
                "kafka_admin_connect_failed",
                extra={
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "error": str(exc),
                },
            )
            if attempt < max_retries:
                await asyncio.sleep(retry_delay * attempt)  
        except Exception as exc:
            logger.error(
                "kafka_admin_unexpected_error",
                extra={"attempt": attempt, "error": str(exc)},
                exc_info=True,
            )
            return 
 
        finally:
            if admin is not None:
                try:
                    await admin.close()
                except Exception:
                    pass
 
    logger.error(
        "kafka_topic_init_gave_up",
        extra={"max_retries": max_retries, "servers": servers},
    )

async def list_topics(bootstrap_servers: Optional[str] = None) -> list[str]:
    """Return all topic names currenty on the broker. Used by the health check."""
    servers = bootstrap_servers or settings.kafka_bootstrap_servers
    admin: Optional[AIOKafkaAdminClient] = None
    try:
        admin = AIOKafkaAdminClient(bootstrap_servers=servers)
        await admin.start()
        metadata = await admin.describe_topics(
            [spec.name for spec in TOPIC_SPECS]
        )
        return [t["topic"] for t in metadata]
    except Exception as exc:
        logger.warning(
            "kafka_list_topics_failed",
            extra={"error": str(exc)},
        )
        return []
    finally:
        if admin is not None:
            try:
                await admin.close()
            except Exception:
                pass