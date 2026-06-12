"""
Tests for PlayEventService._maybe_publish ( real Kafka integration).

All use AsyncMock producers so no real Kafka broker is needed.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from app.core.services.play_event import PlayEventService
from app.models.play import PlayRequest

pytestmark = pytest.mark.asyncio


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def mock_redis():
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    return redis


def _make_mock_producer(delivered: bool = True):
    """Return a mock KafkaProducerService."""
    producer = AsyncMock()
    
    producer.is_healthy = True
    return producer


@pytest_asyncio.fixture
async def service_with_kafka(async_session, mock_redis):
    producer = _make_mock_producer()
    return PlayEventService(
        session=async_session,
        redis=mock_redis,
        kafka_producer=producer,
    ), producer


# ── _maybe_publish ────────────────────────────────────────────────────────────

async def test_maybe_publish_sends_to_correct_topic(service_with_kafka, sample_tracks):
    """_maybe_publish sends to TOPIC_PLAY_EVENTS with correct key."""
    from app.core.kafka.topics import TOPIC_PLAY_EVENTS

    service, producer = service_with_kafka
    user_id = uuid.uuid4()
    payload = PlayRequest(
        track_id=sample_tracks[0].id,
        duration_listened=120,
        completed=False,
    )

    response = await service.record(user_id=user_id, payload=payload)
    assert response.deduplicated is False

    producer.send.assert_awaited_once()
    call_kwargs = producer.send.await_args.kwargs
    print(call_kwargs)
    assert call_kwargs["topic"] == TOPIC_PLAY_EVENTS
    assert call_kwargs["key"] == str(sample_tracks[0].id).encode()


async def test_maybe_publish_message_contains_required_fields(service_with_kafka, sample_tracks):
    """The published value is a valid PlayEventMessage JSON."""
    import json
    service, producer = service_with_kafka
    user_id = uuid.uuid4()
    payload = PlayRequest(
        track_id=sample_tracks[0].id,
        duration_listened=60,
        completed=True,
    )

    await service.record(user_id=user_id, payload=payload)

    raw_value = producer.send.await_args.kwargs["value"]
    decoded = json.loads(raw_value.decode())
    assert "event_id" in decoded
    assert "track_id" in decoded
    assert decoded["track_id"] == str(sample_tracks[0].id)
    assert decoded["completed"] is True
    assert decoded["duration_listened"] == 60


async def test_maybe_publish_noop_when_no_producer(async_session, mock_redis, sample_tracks):
    """Without a producer no exception is raised and the play is still recorded."""
    service = PlayEventService(session=async_session, redis=mock_redis, kafka_producer=None)
    user_id = uuid.uuid4()
    payload = PlayRequest(
        track_id=sample_tracks[0].id,
        duration_listened=90,
        completed=False,
    )

    response = await service.record(user_id=user_id, payload=payload)
    assert response.deduplicated is False


async def test_maybe_publish_kafka_failure_does_not_break_record(service_with_kafka, sample_tracks):
    """If send() returns False the play event is still returned as recorded."""
    service, producer = service_with_kafka
    producer.send = AsyncMock(return_value=False)   # simulated delivery failure

    user_id = uuid.uuid4()
    payload = PlayRequest(
        track_id=sample_tracks[0].id,
        duration_listened=100,
        completed=False,
    )

    response = await service.record(user_id=user_id, payload=payload)
    assert response.deduplicated is False


async def test_maybe_publish_exception_does_not_propagate(service_with_kafka, sample_tracks):
    """If send() raises, the exception is swallowed and the play is still returned."""
    service, producer = service_with_kafka
    producer.send = AsyncMock(side_effect=RuntimeError("kafka down"))

    user_id = uuid.uuid4()
    payload = PlayRequest(
        track_id=sample_tracks[0].id,
        duration_listened=200,
        completed=True,
    )

    # Must not raise
    response = await service.record(user_id=user_id, payload=payload)
    assert response.event_id is not None