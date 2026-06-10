"""
Tests for app/core/kafka/topics.py

auto_create_topics and list_topics are tested by mocking AIOKafkaAdminClient.
No real broker required.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiokafka.errors import KafkaConnectionError, TopicAlreadyExistsError

from app.core.kafka.topics import (
    TOPIC_PLAY_EVENTS,
    TOPIC_PLAY_EVENTS_DLQ,
    TOPIC_USER_LIKES,
    TOPIC_CHART_UPDATES,
    TOPIC_SPECS,
    auto_create_topics,
    list_topics,
)


#auto_create_topics 

def _mock_admin(create_result: dict | None = None, start_raises=None):
    """Return a context-managed AsyncMock AIOKafkaAdminClient."""
    admin = AsyncMock()

    if start_raises:
        admin.start = AsyncMock(side_effect=start_raises)
    else:
        admin.start = AsyncMock()

    admin.stop = AsyncMock()
    admin.close = AsyncMock()

    if create_result is None:
        # All topics created successfully (error=None per topic)
        create_result = {spec.name: None for spec in TOPIC_SPECS}

    admin.create_topics = AsyncMock(return_value=create_result)
    return admin


async def test_auto_create_topics_calls_create_topics():
    mock_admin = _mock_admin()
    with patch("app.core.kafka.topics.AIOKafkaAdminClient", return_value=mock_admin):
        await auto_create_topics(bootstrap_servers="localhost:9094", max_retries=1)

    mock_admin.create_topics.assert_awaited_once()


async def test_auto_create_topics_passes_all_specs():
    """create_topics receives a NewTopic for each spec in TOPIC_SPECS."""
    mock_admin = _mock_admin()
    with patch("app.core.kafka.topics.AIOKafkaAdminClient", return_value=mock_admin):
        await auto_create_topics(bootstrap_servers="localhost:9094", max_retries=1)

    call_args = mock_admin.create_topics.await_args
    new_topics = call_args.args[0]
    created_names = {t.name for t in new_topics}
    expected_names = {spec.name for spec in TOPIC_SPECS}
    assert created_names == expected_names


async def test_auto_create_topics_handles_already_exists():
    """TopicAlreadyExistsError per topic is treated as success (idempotent)."""
    create_result = {spec.name: TopicAlreadyExistsError() for spec in TOPIC_SPECS}
    mock_admin = _mock_admin(create_result=create_result)

    with patch("app.core.kafka.topics.AIOKafkaAdminClient", return_value=mock_admin):
        # Should not raise
        await auto_create_topics(bootstrap_servers="localhost:9094", max_retries=1)


async def test_auto_create_topics_retries_on_connection_error():
    """KafkaConnectionError triggers a retry (up to max_retries times)."""
    mock_admin_fail = AsyncMock()
    mock_admin_fail.start = AsyncMock(side_effect=KafkaConnectionError("refused"))
    mock_admin_fail.close = AsyncMock()

    with patch("app.core.kafka.topics.AIOKafkaAdminClient", return_value=mock_admin_fail):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            # max_retries=2 → should try twice then give up without raising
            await auto_create_topics(
                bootstrap_servers="localhost:9094",
                max_retries=2,
                retry_delay=0.0,
            )

    assert mock_admin_fail.start.await_count == 2


async def test_auto_create_topics_does_not_raise_on_unexpected_error():
    """Non-KafkaConnectionError is caught and logged, never propagated."""
    mock_admin = AsyncMock()
    mock_admin.start = AsyncMock()
    mock_admin.create_topics = AsyncMock(side_effect=RuntimeError("unexpected"))
    mock_admin.close = AsyncMock()

    with patch("app.core.kafka.topics.AIOKafkaAdminClient", return_value=mock_admin):
        await auto_create_topics(bootstrap_servers="localhost:9094", max_retries=1)
    # Must reach here without raising


async def test_auto_create_topics_closes_admin_on_success():
    """Admin client is always closed even on success."""
    mock_admin = _mock_admin()
    with patch("app.core.kafka.topics.AIOKafkaAdminClient", return_value=mock_admin):
        await auto_create_topics(bootstrap_servers="localhost:9094", max_retries=1)

    mock_admin.close.assert_awaited()


async def test_auto_create_topics_closes_admin_on_error():
    """Admin client is closed even when start() raises."""
    mock_admin = AsyncMock()
    mock_admin.start = AsyncMock(side_effect=KafkaConnectionError("refused"))
    mock_admin.close = AsyncMock()

    with patch("app.core.kafka.topics.AIOKafkaAdminClient", return_value=mock_admin):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await auto_create_topics(
                bootstrap_servers="localhost:9094",
                max_retries=1,
                retry_delay=0.0,
            )

    mock_admin.close.assert_awaited()


# list_topics 

async def test_list_topics_returns_topic_names():
    topic_names = [spec.name for spec in TOPIC_SPECS]
    mock_admin = AsyncMock()
    mock_admin.start = AsyncMock()
    mock_admin.close = AsyncMock()
    # describe_topics returns list of dicts with "topic" key
    mock_admin.describe_topics = AsyncMock(
        return_value=[{"topic": name} for name in topic_names]
    )

    with patch("app.core.kafka.topics.AIOKafkaAdminClient", return_value=mock_admin):
        result = await list_topics(bootstrap_servers="localhost:9094")

    assert set(result) == set(topic_names)


async def test_list_topics_returns_empty_on_error():
    mock_admin = AsyncMock()
    mock_admin.start = AsyncMock(side_effect=KafkaConnectionError("broker down"))
    mock_admin.close = AsyncMock()

    with patch("app.core.kafka.topics.AIOKafkaAdminClient", return_value=mock_admin):
        result = await list_topics(bootstrap_servers="localhost:9094")

    assert result == []


async def test_list_topics_closes_admin_on_success():
    mock_admin = AsyncMock()
    mock_admin.start = AsyncMock()
    mock_admin.close = AsyncMock()
    mock_admin.describe_topics = AsyncMock(return_value=[])

    with patch("app.core.kafka.topics.AIOKafkaAdminClient", return_value=mock_admin):
        await list_topics(bootstrap_servers="localhost:9094")

    mock_admin.close.assert_awaited()


# Topic constants 
def test_all_topic_constants_defined():
    """Every constant referenced elsewhere is defined."""
    assert TOPIC_PLAY_EVENTS == "play-events"
    assert TOPIC_PLAY_EVENTS_DLQ == "play-events.dlq"
    assert TOPIC_USER_LIKES == "user-likes"
    assert TOPIC_CHART_UPDATES == "chart-updates"


def test_topic_specs_non_empty():
    assert len(TOPIC_SPECS) >= 4


def test_every_spec_has_name_and_partitions():
    for spec in TOPIC_SPECS:
        assert spec.name
        assert spec.partitions >= 1
        assert spec.replication_factor >= 1