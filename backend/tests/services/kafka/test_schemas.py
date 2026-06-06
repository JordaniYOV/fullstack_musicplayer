"""
Tests for app/core/kafka/schemas.py

Validates that every schema round-trips correctly through to_bytes/from_bytes
and that required fields are enforced.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest

from app.core.kafka.schemas import (
    KafkaMessage,
    PlayEventMessage,
    PlayEventDLQMessage,
    UserLikeMessage,
    ChartUpdateMessage,
)


# KafkaMessage base 

def test_kafka_message_has_auto_event_id():
    msg = PlayEventMessage(
        track_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        duration_listened=120,
        completed=False,
        played_at=datetime.now(),
    )
    assert msg.event_id is not None
    assert type(msg.event_id) == uuid.UUID  # must be a valid UUID


def test_kafka_message_has_auto_produced_at():
    msg = PlayEventMessage(
        track_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        duration_listened=0,
        completed=False,
        played_at=datetime.now(),
    )
    assert type(msg.produced_at) == datetime 


def test_kafka_message_schema_version_default():
    msg = PlayEventMessage(
        track_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        duration_listened=0,
        completed=False,
        played_at=datetime.now()
    )
    assert msg.schema_version == 1


#PlayEventMessage round-trip 

def test_play_event_to_bytes_produces_valid_json():
    msg = PlayEventMessage(
        track_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        duration_listened=180,
        completed=True,
        played_at=datetime.now(),
    )
    raw = msg.to_bytes()
    assert isinstance(raw, bytes)
    parsed = json.loads(raw.decode())
    assert parsed["duration_listened"] == 180
    assert parsed["completed"] is True


def test_play_event_from_bytes_round_trips():
    original = PlayEventMessage(
        track_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        duration_listened=300,
        completed=False,
        played_at=datetime.now(),
    )
    raw = original.to_bytes()
    restored = PlayEventMessage.from_bytes(raw)

    assert restored.event_id == original.event_id
    assert restored.track_id == original.track_id
    assert restored.user_id == original.user_id
    assert restored.duration_listened == 300
    assert restored.completed is False


def test_play_event_from_bytes_invalid_json_raises():
    with pytest.raises(Exception):
        PlayEventMessage.from_bytes(b"not json at all")


def test_play_event_from_bytes_missing_field_raises():
    """Missing required field (track_id) → ValidationError."""
    partial = json.dumps({
        "event_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "duration_listened": 10,
        "completed": False,
        # track_id and played_at intentionally omitted
    }).encode()
    with pytest.raises(Exception):
        PlayEventMessage.from_bytes(partial)


# PlayEventDLQMessage

def test_dlq_message_round_trips():
    msg = PlayEventDLQMessage(
        original_topic="play-events",
        original_partition=2,
        original_offset=999,
        raw_value="deadbeef",
        error_type="ValueError",
        error_message="bad data",
    )
    raw = msg.to_bytes()
    restored = PlayEventDLQMessage.from_bytes(raw)

    assert restored.original_topic == "play-events"
    assert restored.original_offset == 999
    assert restored.error_type == "ValueError"


def test_dlq_message_has_failed_at_timestamp():
    msg = PlayEventDLQMessage(
        original_topic="play-events",
        original_partition=0,
        original_offset=1,
        raw_value="ff",
        error_type="TypeError",
        error_message="oops",
    )
    assert type(msg.failed_at) == datetime


# UserLikeMessage

def test_user_like_message_round_trips():
    msg = UserLikeMessage(
        user_id=uuid.uuid4(),
        entity_id=uuid.uuid4(),
        entity_type="track",
        action="like",
    )
    raw = msg.to_bytes()
    restored = UserLikeMessage.from_bytes(raw)

    assert restored.action == "like"
    assert restored.entity_type == "track"


def test_user_like_message_unlike():
    msg = UserLikeMessage(
        user_id=uuid.uuid4(),
        entity_id=uuid.uuid4(),
        entity_type="album",
        action="unlike",
    )
    assert msg.action == "unlike"
    assert msg.entity_type == "album"


# ChartUpdateMessage 

def test_chart_update_message_round_trips():
    msg = ChartUpdateMessage(
        chart_type="daily",
        period="2026-05-05",
        tracks_count=100,
    )
    raw = msg.to_bytes()
    restored = ChartUpdateMessage.from_bytes(raw)

    assert restored.chart_type == "daily"
    assert restored.period == "2026-05-05"
    assert restored.tracks_count == 100


def test_chart_update_has_aggregated_at():
    msg = ChartUpdateMessage(
        chart_type="weekly",
        period="2026-W18",
        tracks_count=50,
    )
    assert type(msg.aggregated_at) == datetime


# ── Event ID uniqueness ───────────────────────────────────────────────────────

def test_two_messages_have_different_event_ids():
    m1 = PlayEventMessage(
        track_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        duration_listened=60,
        completed=False,
        played_at=datetime.now(),
    )
    m2 = PlayEventMessage(
        track_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        duration_listened=60,
        completed=False,
        played_at=datetime.now(),
    )
    assert m1.event_id != m2.event_id