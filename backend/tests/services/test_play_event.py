# from __future__ import annotations
"""
Tests for PlayEventService (without Kafka integration).
"""
import uuid
import pytest
import pytest_asyncio

from unittest.mock import AsyncMock, MagicMock, patch

from sqlmodel import select

from app.schemas.play import PlayRequest
from app.models.tracks import PlayEvent, Track
from app.core.services.play_event import DEDUP_WINDOW_SECONDS, RECOUNT_THRESHOLD



@pytest_asyncio.fixture
async def mock_redis(): 
    """Async Mock Redis"""
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    return redis

@pytest_asyncio.fixture
async def service(mock_redis, async_session): 
    """PlayEventService with mocked Redis and DB session"""
    from app.core.services.play_event import PlayEventService
    return PlayEventService(session=async_session, redis=mock_redis, kafka_producer=None)

@pytest_asyncio.fixture
async def play_request(sample_track): 
    """A valid PlayRequest for the first sample track."""
    return PlayRequest(
        track_id= sample_track[0].id, 
        duration_listened=120,
        completed=False,
    )
    



async def test_record_play_persists_event(service, sample_tracks, async_session, mock_redis):
    """A normal play creates a PlayEvent row"""
    user_id = uuid.uuid4()
    payload = PlayRequest(
        track_id=sample_tracks[0].id, 
        duration_listened=354,
        completed=True,
    )

    response = await service.record(user_id=user_id, payload=payload)

    assert response.deduplicated is False
    assert response.track_id == sample_tracks[0].id
    assert response.event_id is not None

    result = await async_session.execute(
        select(PlayEvent).where(PlayEvent.id == response.event_id)
    )

    event = result.scalar_one_or_none()

    assert event is not None 
    assert event.user_id == user_id
    assert event.duration_listened == 354
    assert event.completed is True

async def test_record_play_increments_counters(service, async_session, sample_tracks, mock_redis):
    """Counter columns on Track are incremented after a play."""
    track = sample_tracks[1]
    user_id = uuid.uuid4()
 
    # Capture baseline counts
    result = await async_session.execute(select(Track).where(Track.id == track.id))
    before = result.scalar_one()
    before_daily = before.daily_plays
    before_all_time = before.all_time_plays
 
    payload = PlayRequest(track_id=track.id, duration_listened=120, completed=False)
    await service.record(user_id=user_id, payload=payload)
 
    # Refresh from DB
    await async_session.refresh(before)
    assert before.daily_plays == before_daily + 1
    assert before.all_time_plays == before_all_time + 1
    assert before.weekly_plays >= 1
    assert before.monthly_plays >= 1
 
 
async def test_record_play_returns_response_shape(service, sample_tracks, mock_redis):
    """PlayResponse has the expected fields."""
    user_id = uuid.uuid4()
    payload = PlayRequest(track_id=sample_tracks[2].id, duration_listened=0, completed=False)
 
    response = await service.record(user_id=user_id, payload=payload)
 
    assert hasattr(response, "event_id")
    assert hasattr(response, "track_id")
    assert hasattr(response, "recorded_at")
    assert hasattr(response, "deduplicated")
    assert hasattr(response, "message")
 
 
# ------------------------------------------------------------------
# Deduplication
# ------------------------------------------------------------------
 
async def test_dedup_returns_deduplicated_true(service, sample_tracks, mock_redis):
    """When Redis SET NX returns None the play is treated as a duplicate."""
    mock_redis.set.return_value = None  # None = key already existed = duplicate
 
    user_id = uuid.uuid4()
    payload = PlayRequest(track_id=sample_tracks[0].id, duration_listened=30, completed=False)
 
    response = await service.record(user_id=user_id, payload=payload)
 
    assert response.deduplicated is True
 
 
async def test_dedup_does_not_persist_event(service, async_session, sample_tracks, mock_redis):
    """Deduplicated plays must NOT create a PlayEvent row."""
    mock_redis.set.return_value = None
 
    user_id = uuid.uuid4()
    payload = PlayRequest(track_id=sample_tracks[0].id, duration_listened=15, completed=False)
    response = await service.record(user_id=user_id, payload=payload)
 
    result = await async_session.execute(
        select(PlayEvent).where(PlayEvent.id == response.event_id)
    )
    assert result.scalar_one_or_none() is None
 
 
async def test_dedup_uses_correct_redis_key(service, sample_tracks, mock_redis):
    """Redis SET NX is called with the right key pattern and TTL."""
    user_id = uuid.uuid4()
    payload = PlayRequest(track_id=sample_tracks[0].id, duration_listened=10, completed=False)
 
    await service.record(user_id=user_id, payload=payload)
 
    expected_key = f"dedup:play:{user_id}:{sample_tracks[0].id}"
    mock_redis.set.assert_called_once_with(
        expected_key, 1, ex=DEDUP_WINDOW_SECONDS, nx=True
    )
 
 
async def test_dedup_redis_error_fails_open(service, sample_tracks, async_session, mock_redis):
    """If Redis is unavailable the play should still be recorded (fail open)."""
    mock_redis.set.side_effect = Exception("connection refused")
 
    user_id = uuid.uuid4()
    payload = PlayRequest(track_id=sample_tracks[0].id, duration_listened=60, completed=False)
 
    response = await service.record(user_id=user_id, payload=payload)
 
    # Should not be marked as deduplicated
    assert response.deduplicated is False
 
 
# ------------------------------------------------------------------
# Track not found
# ------------------------------------------------------------------
 
async def test_record_play_unknown_track_raises(service, mock_redis):
    """Recording a play for a non-existent track raises ValueError."""
    user_id = uuid.uuid4()
    payload = PlayRequest(
        track_id=uuid.uuid4(),   # random UUID — not in DB
        duration_listened=100,
        completed=False,
    )
 
    with pytest.raises(ValueError, match="not found"):
        await service.record(user_id=user_id, payload=payload)
 
 
# ------------------------------------------------------------------
# Recount threshold
# ------------------------------------------------------------------
 
async def test_recount_triggered_at_threshold(service, sample_tracks, mock_redis):
    """Celery task is dispatched when the Redis counter hits RECOUNT_THRESHOLD."""
    
    mock_redis.incr.return_value = RECOUNT_THRESHOLD
 
    user_id = uuid.uuid4()
    payload = PlayRequest(track_id=sample_tracks[0].id, duration_listened=200, completed=True)
 
    with patch(
        "app.tasks.update_popular_tracks.aggregate_daily_task"
    ) as mock_task:
        mock_task.apply_async = MagicMock()
        await service.record(user_id=user_id, payload=payload)
        mock_task.apply_async.assert_called_once()
 
 
async def test_recount_not_triggered_below_threshold(service, sample_tracks, mock_redis):
    """Celery task is NOT dispatched when the counter is below RECOUNT_THRESHOLD."""
    mock_redis.incr.return_value = RECOUNT_THRESHOLD - 1
 
    user_id = uuid.uuid4()
    payload = PlayRequest(track_id=sample_tracks[0].id, duration_listened=200, completed=True)
 
    with patch(
        "app.core.services.aggregation.AggregationService.aggregate_daily"
    ) as mock_task:
        mock_task.apply_async = MagicMock()
        await service.record(user_id=user_id, payload=payload)
        mock_task.apply_async.assert_not_called()
 
 
async def test_recount_redis_error_does_not_crash(service, sample_tracks, mock_redis):
    """A Redis error in the recount step should not surface to the caller."""
    mock_redis.incr.side_effect = Exception("redis down")
 
    user_id = uuid.uuid4()
    payload = PlayRequest(track_id=sample_tracks[0].id, duration_listened=100, completed=False)
 
    # Should complete without raising
    response = await service.record(user_id=user_id, payload=payload)
    assert response.deduplicated is False
 
 
# ------------------------------------------------------------------
# User history
# ------------------------------------------------------------------
 
async def test_get_user_history_returns_events(service, async_session, sample_tracks, mock_redis):
    """get_user_history returns PlayEvent rows for the correct user."""
    user_id = uuid.uuid4()
 
    # Add 3 events for this user
    for i in range(3):
        payload = PlayRequest(track_id=sample_tracks[i].id, duration_listened=100 + i, completed=False)
        # Bypass dedup by calling _persist_event directly
        await service.persist_event(user_id, payload)
    await async_session.commit()
 
    history = await service.get_user_history(user_id=user_id, limit=10)
 
    assert len(history) == 3
    for event in history:
        assert event.user_id == user_id
 
 
async def test_get_user_history_pagination(service, async_session, sample_tracks, mock_redis):
    """Limit and offset work correctly."""
    user_id = uuid.uuid4()
    for _ in range(5):
        payload = PlayRequest(track_id=sample_tracks[0].id, duration_listened=60, completed=False)
        await service.persist_event(user_id, payload)
    await async_session.commit()
 
    page1 = await service.get_user_history(user_id=user_id, limit=3, offset=0)
    page2 = await service.get_user_history(user_id=user_id, limit=3, offset=3)
 
    assert len(page1) == 3
    assert len(page2) == 2
    # No overlap
    page1_ids = {e.id for e in page1}
    page2_ids = {e.id for e in page2}
    assert page1_ids.isdisjoint(page2_ids)
 
 
async def test_get_user_history_empty_for_unknown_user(service, mock_redis):
    """Unknown user returns an empty list, not an error."""
    history = await service.get_user_history(user_id=uuid.uuid4(), limit=20)
    assert history == []
 
 
# ------------------------------------------------------------------
# Validation — PlayRequest schema
# ------------------------------------------------------------------

def test_play_request_rejects_negative_duration():
    """duration_listened < 0 fails Pydantic validation."""
    with pytest.raises(Exception):
        PlayRequest(track_id=uuid.uuid4(), duration_listened=-1, completed=False)
 
def test_play_request_rejects_excessive_duration():
    """duration_listened > 14 400 s (4 h) fails the custom validator."""
    with pytest.raises(Exception):
        PlayRequest(track_id=uuid.uuid4(), duration_listened=99_999, completed=False)
 
def test_play_request_allows_zero_duration():
    """Zero duration is valid (counts as a skip)."""
    req = PlayRequest(track_id=uuid.uuid4(), duration_listened=0, completed=False)
    assert req.duration_listened == 0 

