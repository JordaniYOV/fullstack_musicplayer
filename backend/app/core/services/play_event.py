from datetime import datetime
from turtle import up
from typing import Any, Optional
import uuid
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from redis import asyncio as aioredis
from sqlmodel import select

from app.logging_config import get_logger
from app.models.play import PlayRequest, PlayResponse
from app.models.tracks import PlayEvent, Track


logger = get_logger("app.service.play_event" service="PlayEventService" engine="psycopg3")

DEDUP_WINDOW_SECONDS: int = 30

RECOUNT_THRESHOLD: int = 50

class PlayEventService:
    def __init__(
            self,
            session: AsyncSession, 
            redis: aioredis.Redis,
            kafka_producer: Optional[Any] = None,
    ) -> None:
        self.session = session,
        self.redis = redis, 
        self.kafka_producer = kafka_producer
        self.logger = logger.bind(instance_id=id(self))

    async def record(
            self,
            user_id: uuid.UUID,
            payload: PlayRequest,
    ) -> PlayResponse:
        """
        Main entry point called by route
        Always return a PlayResponse
        """
        track = await self.get_track(payload.track_id)

        if track is None:
            self.logger.warning(
                "play_event_track_not_found", 
                extra={"user_id": str(user_id), "track_id": str(payload.track_id)}, 
            )
            raise ValueError(f"Track {payload.track_id} not found")
        
        if await self.is_duplicate(user_id, payload.track_id):
            self.logger.info(
                "play_event_deduplicated", 
                extra={"user_id": str(user_id), "track_id": str(payload.track_id)}, 
            )
            return PlayResponse(
                event_id=uuid.uuid4(),
                track_id=payload.track_id,
                recorded_at=datetime.utcnow(),
                deduplicated=True,
                message="Duplicate play event - not recorded again."
            )
        try:
            event = await self.persist_event(user_id, payload)

            await self.increment_counters(payload.track_id)

            await self.maybe_publish(user_id, payload, event)

            await self.maybe_trigger_recount(payload.track_id)

            self.logger.info(
                "play_event_recorded", 
                extra={
                    "event_id": str(event.id),
                    "user_id": str(user_id), 
                    "track_id": str(payload.track_id), 
                    "duration_listened": payload.duration_listened,
                    "completed": payload.completed,
                }
            )

            return PlayResponse(
                event_id=event.id,
                track_id=event.track_id,
                recorded_at=event.played_at,
                deduplicated=False,
                message="Play event recorded"
            )
        except Exception as e:
            self.logger.error(
                "play_event_recording_failed", 
                extra={
                    "user_id": str(user_id), 
                    "track_id": str(payload.track_id), 
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True
            )
            raise

    async def get_user_history(
            self, 
            user_id: uuid.UUID, 
            limit: int = 20, 
            offset: int = 0
    ) -> list[PlayEvent]:
        """
        Return a pagination list of PlayEvents for a user, most recent first
        """

        query = (
            select(PlayEvent)
            .where(PlayEvent.user_id == user_id)
            .order_by(PlayEvent.played_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(query)
        events = list(result.scalars().all())

    # private helpers

    async def get_track(self, track_id: uuid.UUID) -> Optional[Any]:
        result = await self.session.execute(select(Track).where(Track.id == track_id))

        return result.scalar_onre_or_none()
    
    async def is_duplicate(self, user_id: uuid.UUID, track_id: uuid.UUID) -> bool:
        """
        Check Redis for a short-lived dedup key.
        key format: "dedup:play:{user_id}:{track_id}"
        TTL = DEDUP_WINDOW_SECONDS
        Uses SET with NX and expiration to ensure atomicity
        """

        key = f"dedup:play:{user_id}:{track_id}"
        try:
            was_set = await self.redis.set(key, 1, ex=DEDUP_WINDOW_SECONDS, nx=True)
            return was_set is None
        except Exception as e:
            self.logger.warning(
                "dedup_redis_error",
                extra={"error": str(e)}
            )
            return False
    
    async def persist_event(self, user_id: uuid.UUID, payload: PlayRequest) -> PlayEvent:
        event = PlayEvent(
            track_id=payload.track_id,
            user_id=user_id,
            duration_listened=payload.duration_listened,
            completed=payload.completed,
        )
        self.session.add(event)
        await self.session.flush()  # to get the event.id populated
        return event
    
    async def increment_counters(self, track_id: uuid.UUID) -> None:
        """ 
        Increment all four play counter in a single UPDATE query
        """
        stmt = (
            update(Track)
            .where(Track.id == track_id)
            .values(
                daily_plays=Track.daily_plays + 1,
                weekly_plays=Track.weekly_plays + 1,
                monthly_plays=Track.monthly_plays + 1,
                all_time_plays=Track.all_time_plays + 1,
            )
        )

        await self.session.execute(stmt)
        await self.session.commit()

    async def maybe_publish(self, user_id: uuid.UUID, payload: PlayRequest, event: PlayEvent) -> None:
        """Puplish play event to Kafka for async processing (e.g. updating charts)"""
        if self.kafka_producer is None:
            return
 
        import json
        message = {
            "event_id": str(event.id),
            "track_id": str(payload.track_id),
            "user_id": str(user_id),
            "duration_listened": payload.duration_listened,
            "completed": payload.completed,
            "played_at": event.played_at.isoformat(),
        }
        try:
            await self.kafka_producer.send_and_wait(
                "play-events",
                value=json.dumps(message).encode(),
                key=str(payload.track_id).encode(),
            )
        except Exception as exc:
            logger.error(
                "kafka_publish_failed",
                extra={"error": str(exc), "track_id": str(payload.track_id)},
                exc_info=True
            )
    async def maybe_trigger_recount(self, track_id: uuid.UUID) -> None:
        """
        Count today's play events for this track
        If we have crossed RECOUNT_THRESHOLD, fire a Celery task that re-runs the daily aggregation so the chart reflects spike.
        """
        today = datetime.today().isoformat()
        counter_key = f"play_counter:{track_id}:{today}"

        try:
            count = await self.redis.incr(counter_key)
            if count == 1:
                await self.redis.expire(counter_key, 90_000) 
            
            if count % RECOUNT_THRESHOLD == 0:
                # Fire Celery task to recount daily chart for this track
                from app.tasks.update_popular_tracks import aggregate_daily_task

                await aggregate_daily_task.apply_async(
                    kwargs={"target_date_str": today},
                    queue="aggregation",
                    countdown=5,  
                )

                self.logger.info(
                    "recount_triggered",
                    extra={"track_id": str(track_id), "count": count, "treshold": RECOUNT_THRESHOLD}
                )
        except Exception as e:
            self.logger.warning(
                "recount_trigger_failed",
                extra={"track_id": str(track_id), "error": str(e)},
                exc_info=True
            )