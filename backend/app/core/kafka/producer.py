import __future__
import asyncio
import json
import time

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError, KafkaTimeoutError

from app.core.config import settings
from app.logging_config import get_logger
from app.core.kafka.topics import TOPIC_PLAY_EVENTS_DLQ, TOPIC_USER_LIKES_DLQ

logger = get_logger("app.core.kafka.producer", service="KafkaProducerService")

MAX_RETRIES: int = 3
BASE_RETRY_DELAY: float = 0.2
CIRCUIT_OPEN_THRESHOLD: int = 10
CIRCUIT_RESET_SECONDS: float = 30.0

_DLQ_MAP: dict[str, str] =  {
    "play-events": TOPIC_PLAY_EVENTS_DLQ,
    "user-likes": TOPIC_USER_LIKES_DLQ,
}

class KafkaProducerService:
    """
    Async Kafka producer with retry, circuit breaker, and DLQ support.
     Usage (in lifespan):
        producer = KafkaProducerService()
        await producer.start()
        app.state.kafka_producer = producer
        yield
        await producer.stop()
 
    Usage (in a service):
        await producer.send(topic="play-events", value=msg.to_bytes(), key=b"track-id")
    """

    def __init__(
            self,
            bootstrap_servers: str | None = None,
    ):
        self._servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self._producer: AIOKafkaProducer | None = None

        self._consecutive_failures: int = 0
        self._circuit_opened_at: float | None = None

    async def start(self) -> None:
        try:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self._servers,
                acks="all",
                enable_idempotence=True,
                linger_ms=5,
                request_timeout_ms=10_000,
                max_batch_size=32768,
                compression_type="gzip",
                value_serializer=None,
                key_serializer=None,
            )
            await self._producer.start()
            logger.info("Kafka producer started", extra={"bootstrap_servers": self._servers})
        
        except Exception as e:
            logger.error("Failed to start Kafka producer", exc_info=True, extrs={"error": str(e)})
            self._producer = None
    
    async def stop(self) -> None:
        """Flush pending messages and close the producer."""
        if self._producer is None:
            return
        try:
            await self._producer.stop()
            logger.info("kafka_producer_stopped")
        except Exception as exc:
            logger.warning(
                "kafka_producer_stop_error",
                extra={"error": str(exc)},
            )
        finally:
            self._producer = None
 
    # Public send API
    async def send(
        self,
        topic: str,
        value: bytes,
        key: bytes | None = None,
        headers: list[tuple[str, bytes]] | None = None,
    ) -> bool:
        """
        Send a message to a Kafka topic.
 
        Returns True if the message was delivered, False if it was dropped
        (circuit open) or all retries were exhausted (message forwarded to DLQ).
        Never raises.
        """
        if self._producer is None:
            logger.warning(
                "kafka_send_skipped_no_producer",
                extra={"topic": topic},
            )
            return False
 
        #Circuit breaker: open? 
        if self.is_circuit_open():
            logger.warning(
                "kafka_circuit_open_drop",
                extra={"topic": topic},
            )
            return False
 
        #Retry loop
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            t0 = time.monotonic()
            try:
                record_metadata = await self._producer.send_and_wait(
                    topic,
                    value=value,
                    key=key,
                    headers=headers or [],
                )
                latency_ms = (time.monotonic() - t0) * 1000
                self.reset_circuit()
                logger.info(
                    "kafka_message_produced",
                    extra={
                        "topic": topic,
                        "partition": record_metadata.partition,
                        "offset": record_metadata.offset,
                        "latency_ms": round(latency_ms, 2),
                        "attempt": attempt,
                        "key": key.decode() if key else None,
                    },
                )
                return True
 
            except (KafkaConnectionError, KafkaTimeoutError) as exc:
                last_exc = exc
                latency_ms = (time.monotonic() - t0) * 1000
                logger.warning(
                    "kafka_send_retryable_error",
                    extra={
                        "topic": topic,
                        "attempt": attempt,
                        "max_retries": MAX_RETRIES,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "latency_ms": round(latency_ms, 2),
                    },
                )
                if attempt < MAX_RETRIES:
                    delay = BASE_RETRY_DELAY * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
 
            except Exception as exc:
               
                last_exc = exc
                logger.error(
                    "kafka_send_fatal_error",
                    extra={
                        "topic": topic,
                        "attempt": attempt,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                    exc_info=True,
                )
                break   
 
        # All retries exhausted
        self.record_failure()
        logger.error(
            "kafka_send_failed_all_retries",
            extra={
                "topic": topic,
                "max_retries": MAX_RETRIES,
                "error": str(last_exc),
                "circuit_failures": self._consecutive_failures,
            },
        )
        await self.send_to_dlq(topic=topic, value=value, key=key, error=last_exc)
        return False
 
    # Circuit breaker helpers
    def is_circuit_open(self) -> bool:
        if self._circuit_opened_at is None:
            return False
        elapsed = time.monotonic() - self._circuit_opened_at
        if elapsed >= CIRCUIT_RESET_SECONDS:
            logger.info("kafka_circuit_half_open")
            self._circuit_opened_at = None
            return False
        return True
 
    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if (
            self._consecutive_failures >= CIRCUIT_OPEN_THRESHOLD
            and self._circuit_opened_at is None
        ):
            self._circuit_opened_at = time.monotonic()
            logger.error(
                "kafka_circuit_opened",
                extra={
                    "consecutive_failures": self._consecutive_failures,
                    "reset_in_seconds": CIRCUIT_RESET_SECONDS,
                },
            )
 
    def reset_circuit(self) -> None:
        if self._consecutive_failures > 0:
            logger.info(
                "kafka_circuit_reset",
                extra={"previous_failures": self._consecutive_failures},
            )
        self._consecutive_failures = 0
        self._circuit_opened_at = None

    # Dead-letter queue
    async def send_to_dlq(
        self,
        topic: str,
        value: bytes,
        key: bytes | None,
        error: Exception | None,
    ) -> None:
        """
        Forward a failed message to the dead-letter queue topic.
        Best-effort only — if this also fails we just log it.
        """
        dlq_topic = _DLQ_MAP.get(topic)
        if dlq_topic is None:
            logger.warning(
                "kafka_no_dlq_for_topic",
                extra={"topic": topic},
            )
            return
 
        if self._producer is None:
            return
 
        dlq_payload = json.dumps({
            "original_topic": topic,
            "original_key": key.decode() if key else None,
            "original_value": value.hex(),
            "error_type": type(error).__name__ if error else "Unknown",
            "error_message": str(error) if error else "",
            "failed_at": time.time(),
        }).encode()
 
        try:
            await self._producer.send_and_wait(dlq_topic, value=dlq_payload, key=key)
            logger.info(
                "kafka_dlq_forwarded",
                extra={"original_topic": topic, "dlq_topic": dlq_topic},
            )
        except Exception as dlq_exc:
            logger.critical(
                "kafka_dlq_forward_failed",
                extra={
                    "dlq_topic": dlq_topic,
                    "error": str(dlq_exc),
                },
            )
 
    # Health
    @property
    def is_healthy(self) -> bool:
        """True if the producer is running and the circuit is closed."""
        return self._producer is not None and not self.is_circuit_open()
 
kafka_producer: KafkaProducerService | None = None
 