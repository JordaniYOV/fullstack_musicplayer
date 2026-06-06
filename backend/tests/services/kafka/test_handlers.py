"""
Tests for app/core/kafka/handlers.py

handle_play_event is tested in isolation:
- valid message → PlayEvent persisted
- invalid JSON → raises (consumer will DLQ)
- duplicate event_id → skipped (idempotent)
- DB error → raises (consumer will DLQ)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.kafka.consumer import ConsumerMessage
from app.core.kafka.schemas import PlayEventMessage

pytestmark = pytest.mark.asyncio


# Helpers

def _make_valid_message(
    event_id: uuid.UUID | None = None,
    track_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> ConsumerMessage:
    msg = PlayEventMessage(
        event_id=event_id or uuid.uuid4(),
        track_id=track_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        duration_listened=180,
        completed=True,
        played_at=datetime.now(),
    )
    return ConsumerMessage(
        topic="play-events",
        partition=0,
        offset=1,
        key=msg.track_id.bytes,
        value=msg.to_bytes(),
        timestamp_ms=1_700_000_000_000,
        headers=[],
    )


def _make_invalid_message() -> ConsumerMessage:
    return ConsumerMessage(
        topic="play-events",
        partition=0,
        offset=2,
        key=b"key",
        value=b"THIS IS NOT JSON {{{",
        timestamp_ms=1_700_000_000_000,
        headers=[],
    )


# Tests 

async def test_handle_play_event_persists_to_db(async_session, sample_tracks):
    """A valid message results in a PlayEvent row in the database."""
    from sqlalchemy import select
    from app.models.tracks import PlayEvent
    from app.core.kafka import handlers

    track = sample_tracks[0]
    event_id = uuid.uuid4()
    msg = _make_valid_message(event_id=event_id, track_id=track.id)

    # Patch the session factory to use our test session
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=async_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch.object(handlers, "_async_session_factory", mock_factory):
        await handlers.handle_play_event(msg)

    result = await async_session.execute(
        select(PlayEvent).where(PlayEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    assert event is not None
    assert event.track_id == track.id
    assert event.duration_listened == 180
    assert event.completed is True


async def test_handle_play_event_invalid_json_raises():
    """Invalid JSON raises an exception so the consumer DLQs the message."""
    from app.core.kafka import handlers

    msg = _make_invalid_message()

    with pytest.raises(Exception):
        await handlers.handle_play_event(msg)


async def test_handle_play_event_duplicate_is_skipped(async_session, sample_tracks):
    """Consuming the same event_id twice is idempotent — second call skips silently."""
    from app.core.kafka import handlers

    track = sample_tracks[0]
    event_id = uuid.uuid4()
    msg = _make_valid_message(event_id=event_id, track_id=track.id)

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=async_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch.object(handlers, "_async_session_factory", mock_factory):
        # First consume
        await handlers.handle_play_event(msg)
        # Second consume — should not raise
        await handlers.handle_play_event(msg)


async def test_handle_play_event_db_error_propagates(sample_tracks):
    """A non-duplicate DB error re-raises so the consumer can DLQ."""
    from app.core.kafka import handlers

    msg = _make_valid_message(track_id=sample_tracks[0].id)

    # Session raises an unexpected error on add
    mock_session = AsyncMock()
    mock_session.add = MagicMock(side_effect=RuntimeError("db crashed"))
    mock_session.rollback = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch.object(handlers, "_async_session_factory", mock_factory):
        with pytest.raises(RuntimeError, match="db crashed"):
            await handlers.handle_play_event(msg)


async def test_handle_play_event_rollback_on_error(sample_tracks):
    """Session is rolled back when a non-duplicate error occurs."""
    from app.core.kafka import handlers

    msg = _make_valid_message(track_id=sample_tracks[0].id)

    mock_session = AsyncMock()
    mock_session.add = MagicMock(side_effect=RuntimeError("unexpected"))
    mock_session.rollback = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch.object(handlers, "_async_session_factory", mock_factory):
        with pytest.raises(RuntimeError):
            await handlers.handle_play_event(msg)

    mock_session.rollback.assert_awaited_once()