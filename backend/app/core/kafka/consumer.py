import asyncio
import json
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional
 
from aiokafka import AIOKafkaConsumer, ConsumerRecord
from aiokafka.errors import KafkaConnectionError, KafkaError
 
from app.core.config import settings
from app.core.kafka.topics import (
    TOPIC_PLAY_EVENTS,
    TOPIC_PLAY_EVENTS_DLQ,
    TOPIC_USER_LIKES,
)
from app.logging_config import get_logger

logger = get_logger("app.core.kafka.consumer", service="KafkaConsumerService")


@dataclass
class ConsumerMessage:
    """Normalised view of an AIOKafka ConsumerRecord passed to handlers."""
    topic: str
    partition: int
    offset: int
    key: Optional[bytes]
    value: bytes
    timestamp_ms: int
    headers: list[tuple[str, bytes]]
 
    @classmethod
    def from_record(cls, record: ConsumerRecord) -> "ConsumerMessage":
        return cls(
            topic=record.topic,
            partition=record.partition,
            offset=record.offset,
            key=record.key,
            value=record.value,
            timestamp_ms=record.timestamp,
            headers=list(record.headers or []),
        )
 
 
HandlerFn = Callable[[ConsumerMessage], Awaitable[None]]
 
# Tuning
CONSUMER_GROUP_ID = "muse-backend"
RECONNECT_DELAY_SECONDS = 5.0
MAX_RECONNECT_ATTEMPTS = 10
SESSION_TIMEOUT_MS = 30_000
HEARTBEAT_INTERVAL_MS = 3_000
 
 
class KafkaConsumerService:
    """
    Manages an AIOKafkaConsumer and dispatches messages to registered handlers.
    """
 
    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        group_id: str = CONSUMER_GROUP_ID,
    ) -> None:
        self._servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self._group_id = group_id
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._handlers: dict[str, HandlerFn] = {}
        self._running = False
 
    def register_handler(self, topic: str, handler: HandlerFn) -> None:
        """Register an async handler for messages from a specific topic."""
        self._handlers[topic] = handler
        logger.info(
            "kafka_handler_registered",
            extra={"topic": topic, "handler": handler.__qualname__},
        )
 
    @property
    def subscribed_topics(self) -> list[str]:
        return list(self._handlers.keys())
 
    async def start(self) -> None:
        """Create and start the AIOKafkaConsumer."""
        if not self._handlers:
            logger.warning("kafka_consumer_no_handlers — not starting consumer")
            return
 
        try:
            self._consumer = AIOKafkaConsumer(
                *self.subscribed_topics,
                bootstrap_servers=self._servers,
                # group_id=self._group_id,
                enable_auto_commit=False,
                auto_offset_reset="earliest",
                session_timeout_ms=SESSION_TIMEOUT_MS,
                heartbeat_interval_ms=HEARTBEAT_INTERVAL_MS,
                fetch_max_bytes=1_048_576,   # 1 MB
                max_poll_records=100,
            )
            await self._consumer.start()
            self._running = True
            logger.info(
                "kafka_consumer_started",
                extra={
                    "group_id": self._group_id,
                    "topics": self.subscribed_topics,
                    "bootstrap_servers": self._servers,
                },
            )
        except Exception as exc:
            logger.error(
                "kafka_consumer_start_failed",
                extra={"error": str(exc)},
                exc_info=True,
            )
            self._consumer = None
 
    async def stop(self) -> None:
        """Stop the consumer and release resources."""
        self._running = False
        if self._consumer is not None:
            try:
                await self._consumer.stop()
                logger.info("kafka_consumer_stopped")
            except Exception as exc:
                logger.warning(
                    "kafka_consumer_stop_error",
                    extra={"error": str(exc)},
                )
            finally:
                self._consumer = None
 
    async def consume_loop(self) -> None:
        """
        Main consumption loop.  Run as an asyncio.Task.
 
        Polls messages, dispatches to handlers, commits offsets.
        On KafkaConnectionError it sleeps and retries up to MAX_RECONNECT_ATTEMPTS
        before giving up (the application will restart from supervisor/k8s).
        """
        reconnect_attempts = 0
 
        while self._running:
            if self._consumer is None:
                if reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                    logger.critical(
                        "kafka_consumer_gave_up",
                        extra={"max_attempts": MAX_RECONNECT_ATTEMPTS},
                    )
                    return
                reconnect_attempts += 1
                logger.warning(
                    "kafka_consumer_reconnecting",
                    extra={
                        "attempt": reconnect_attempts,
                        "delay_s": RECONNECT_DELAY_SECONDS,
                    },
                )
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)
                await self.start()
                continue
 
            try:
                async for record in self._consumer:
                    if not self._running:
                        break
                    await self._dispatch(record)
                    reconnect_attempts = 0  # reset on successful poll
 
            except asyncio.CancelledError:
                logger.info("kafka_consumer_loop_cancelled")
                break
 
            except KafkaConnectionError as exc:
                logger.error(
                    "kafka_consumer_connection_lost",
                    extra={"error": str(exc), "reconnect_attempt": reconnect_attempts},
                )
                await self.stop()
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)
 
            except KafkaError as exc:
                logger.error(
                    "kafka_consumer_kafka_error",
                    extra={"error_type": type(exc).__name__, "error": str(exc)},
                    exc_info=True,
                )
                await asyncio.sleep(1.0)
 
            except Exception as exc:
                logger.critical(
                    "kafka_consumer_unexpected_error",
                    extra={"error_type": type(exc).__name__, "error": str(exc)},
                    exc_info=True,
                )
                await asyncio.sleep(1.0)
 
    # Internal dispatch
    async def _dispatch(self, record: ConsumerRecord) -> None:
        """
        Dispatch a single ConsumerRecord to its registered handler.
 
        Commit offset only after the handler succeeds.
        On handler failure, forward to DLQ then commit (so we don't redeliver).
        """
        msg = ConsumerMessage.from_record(record)
        handler = self._handlers.get(msg.topic)
 
        if handler is None:
            logger.warning(
                "kafka_no_handler_for_topic",
                extra={"topic": msg.topic, "partition": msg.partition, "offset": msg.offset},
            )
            await self._commit(record)
            return
 
        t0 = time.monotonic()
        try:
            await handler(msg)
            latency_ms = (time.monotonic() - t0) * 1000
            logger.info(
                "kafka_message_handled",
                extra={
                    "topic": msg.topic,
                    "partition": msg.partition,
                    "offset": msg.offset,
                    "latency_ms": round(latency_ms, 2),
                    "handler": handler.__qualname__,
                },
            )
        except Exception as exc:
            latency_ms = (time.monotonic() - t0) * 1000
            logger.error(
                "kafka_handler_failed",
                extra={
                    "topic": msg.topic,
                    "partition": msg.partition,
                    "offset": msg.offset,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "latency_ms": round(latency_ms, 2),
                    "handler": handler.__qualname__,
                },
                exc_info=True,
            )
            await self._forward_to_dlq(msg, exc)
 
        finally:
            await self._commit(record)
 
    async def _commit(self, record: ConsumerRecord) -> None:
        """Commit offset for a single record."""
        if self._consumer is None:
            return
        try:
            from aiokafka import TopicPartition
            tp = TopicPartition(record.topic, record.partition)
            await self._consumer.commit({tp: record.offset + 1})
        except Exception as exc:
            logger.warning(
                "kafka_commit_failed",
                extra={
                    "topic": record.topic,
                    "partition": record.partition,
                    "offset": record.offset,
                    "error": str(exc),
                },
            )
 
    async def _forward_to_dlq(self, msg: ConsumerMessage, error: Exception) -> None:
        """Send a failed message to the dead-letter queue."""
        # Import here to avoid circular: consumer → producer
        from app.core.kafka.producer import kafka_producer
 
        dlq_topic_map = {
            TOPIC_PLAY_EVENTS: TOPIC_PLAY_EVENTS_DLQ,
            TOPIC_USER_LIKES: f"{TOPIC_USER_LIKES}.dlq",
        }
        dlq_topic = dlq_topic_map.get(msg.topic)
        if dlq_topic is None or kafka_producer is None:
            logger.warning(
                "kafka_dlq_skip",
                extra={"topic": msg.topic, "has_producer": kafka_producer is not None},
            )
            return
 
        dlq_payload = json.dumps({
            "original_topic": msg.topic,
            "original_partition": msg.partition,
            "original_offset": msg.offset,
            "original_key": msg.key.decode() if msg.key else None,
            "raw_value": msg.value.hex(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "failed_at": time.time(),
        }).encode()
 
        await kafka_producer.send(
            topic=dlq_topic,
            value=dlq_payload,
            key=msg.key,
        )
        logger.info(
            "kafka_message_dlq_forwarded",
            extra={
                "original_topic": msg.topic,
                "dlq_topic": dlq_topic,
                "partition": msg.partition,
                "offset": msg.offset,
            },
        )
 
    # Health
    @property
    def is_healthy(self) -> bool:
        return self._consumer is not None and self._running
 
 
#Module-level singleton
kafka_consumer_service: Optional[KafkaConsumerService] = None
 