from datetime import datetime
 
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
 
from app.logging_config import get_logger
from app.core.kafka.consumer import ConsumerMessage
from app.core.kafka.schemas import PlayEventMessage
from app.core.db import async_engine
from app.models.tracks import PlayEvent
 
logger = get_logger("app.core.kafka.handlers")
 
_async_session_factory = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
 
 
async def handle_play_event(msg: ConsumerMessage) -> None:
    """
    Consume a message from the play-events topic.
 
    What this handler does:
    1. Deserialise and validate the message against PlayEventMessage schema.
       On ValidationError → raises immediately → consumer DLQs the message.
    2. Persist the PlayEvent to Postgres inside its own session+transaction.
    3. Log success with structured context.
 
    Note: counter increments (daily_plays etc.) are done inline in the HTTP
    handler in play_event.py for low latency. This handler is the durable
    write path — it ensures every play is recorded even if the HTTP layer
    crashed after committing the counter UPDATE but before the Kafka ACK.
    In practice the DB will reject the duplicate because of the PlayEvent PK;
    we catch IntegrityError and treat it as a no-op.
    """
    try:
        event_msg = PlayEventMessage.from_bytes(msg.value)
    except (ValidationError, Exception) as exc:
        logger.error(
            "play_event_deserialise_failed",
            extra={
                "topic": msg.topic,
                "partition": msg.partition,
                "offset": msg.offset,
                "error": str(exc),
                "raw_length": len(msg.value),
            },
        )
        raise  
 
    logger.info(
        "play_event_consumed",
        extra={
            "event_id": event_msg.event_id,
            "track_id": event_msg.track_id,
            "user_id": event_msg.user_id,
            "partition": msg.partition,
            "offset": msg.offset,
        },
    )
 
    async with _async_session_factory() as session:
        try:
            import uuid
            play_event = PlayEvent(
                id=uuid.UUID(event_msg.event_id),
                track_id=uuid.UUID(event_msg.track_id),
                user_id=uuid.UUID(event_msg.user_id),
                duration_listened=event_msg.duration_listened,
                completed=event_msg.completed,
                played_at=datetime.fromisoformat(event_msg.played_at),
            )
            session.add(play_event)
            await session.commit()
 
            logger.info(
                "play_event_persisted",
                extra={
                    "event_id": event_msg.event_id,
                    "track_id": event_msg.track_id,
                },
            )
 
        except Exception as exc:
            await session.rollback()
 
            if "duplicate key" in str(exc).lower() or "unique" in str(exc).lower():
                logger.info(
                    "play_event_duplicate_skipped",
                    extra={"event_id": event_msg.event_id},
                )
                return
 
            logger.error(
                "play_event_persist_failed",
                extra={
                    "event_id": event_msg.event_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                exc_info=True,
            )
            raise 
 