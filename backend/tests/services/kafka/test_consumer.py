"""
Unit tests for KafkaConsumerService.

Tests use AsyncMock to simulate ConsumerRecord delivery without a real broker.
"""
from __future__ import annotations

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from aiokafka.errors import KafkaConnectionError

from app.core.kafka.consumer import (
    ConsumerMessage,
    KafkaConsumerService,
)


# Helpers 

def _make_record(
    topic: str = "play-events",
    partition: int = 0,
    offset: int = 10,
    key: bytes = b"track-1",
    value: bytes = b'{"event_id":"abc"}',
):
    record = MagicMock()
    record.topic = topic
    record.partition = partition
    record.offset = offset
    record.key = key
    record.value = value
    record.timestamp = 1_700_000_000_000
    record.headers = []
    return record


# Fixtures 

@pytest_asyncio.fixture
async def consumer_service() -> KafkaConsumerService:
    svc = KafkaConsumerService(bootstrap_servers="localhost:9092")
    mock_consumer = AsyncMock()
    mock_consumer.stop = AsyncMock()
    svc._consumer = mock_consumer
    svc._running = True
    return svc

# ConsumerMessage

def test_consumer_message_from_record():
    record = _make_record()
    msg = ConsumerMessage.from_record(record)
    assert msg.topic == "play-events"
    assert msg.partition == 0
    assert msg.offset == 10
    assert msg.key == b"track-1"
    assert msg.value == b'{"event_id":"abc"}'


# register_handler

async def test_register_handler_stores_correctly(consumer_service):
    async def my_handler(msg): pass
    consumer_service.register_handler("play-events", my_handler)
    assert consumer_service._handlers["play-events"] is my_handler


async def test_subscribed_topics_lists_registered(consumer_service):
    async def h1(msg): pass
    async def h2(msg): pass
    consumer_service.register_handler("play-events", h1)
    consumer_service.register_handler("user-likes", h2)
    assert set(consumer_service.subscribed_topics) == {"play-events", "user-likes"}


# start 

async def test_start_skips_if_no_handlers():
    svc = KafkaConsumerService()
    # No handlers registered
    with patch("app.core.kafka.consumer.AIOKafkaConsumer") as MockConsumer:
        await svc.start()
    MockConsumer.assert_not_called()
    assert svc._consumer is None


async def test_start_creates_consumer_with_correct_topics():
    svc = KafkaConsumerService(bootstrap_servers="localhost:9094")
    async def h(msg): pass
    svc.register_handler("play-events", h)

    with patch("app.core.kafka.consumer.AIOKafkaConsumer") as MockConsumer:
        mock_instance = AsyncMock()
        MockConsumer.return_value = mock_instance
        await svc.start()

    MockConsumer.assert_called_once()
    call_args = MockConsumer.call_args
    assert "play-events" in call_args.args


async def test_start_failure_leaves_consumer_none():
    svc = KafkaConsumerService()
    async def h(msg): pass
    svc.register_handler("play-events", h)

    with patch("app.core.kafka.consumer.AIOKafkaConsumer") as MockConsumer:
        mock_instance = AsyncMock()
        mock_instance.start.side_effect = KafkaConnectionError("refused")
        MockConsumer.return_value = mock_instance
        await svc.start()

    assert svc._consumer is None


# stop 

async def test_stop_calls_underlying_stop(consumer_service):
    mok = consumer_service._consumer
    await consumer_service.stop()
    mok.stop.assert_awaited_once()
    assert consumer_service._consumer is None
    assert consumer_service._running is False


async def test_stop_noop_when_already_stopped():
    svc = KafkaConsumerService()
    svc._consumer = None
    await svc.stop()   # must not raise


# _dispatch 

async def test_dispatch_calls_registered_handler(consumer_service):
    handler = AsyncMock()
    consumer_service.register_handler("play-events", handler)

    record = _make_record(topic="play-events")
    with patch.object(consumer_service, "_commit", new_callable=AsyncMock):
        await consumer_service._dispatch(record)

    print(f"handler type: {type(handler)}")
    print(f"handler.await_args: {handler.await_args}")
    print(f"handler.await_count: {handler.await_count}")
    print(f"handler.called: {handler.called}")
    handler.assert_awaited_once_with(ANY) 
    msg_arg = handler.await_args.args[0]
    assert isinstance(msg_arg, ConsumerMessage)
    assert msg_arg.topic == "play-events"


async def test_dispatch_commits_after_success(consumer_service):
    async def handler(msg): pass
    consumer_service.register_handler("play-events", handler)

    record = _make_record()
    with patch.object(consumer_service, "_commit", new_callable=AsyncMock) as mock_commit:
        await consumer_service._dispatch(record)

    mock_commit.assert_awaited_once_with(record)


async def test_dispatch_commits_even_after_handler_failure(consumer_service):
    """Commit must happen even when the handler raises — otherwise partition stalls."""
    async def bad_handler(msg):
        raise RuntimeError("handler exploded")

    consumer_service.register_handler("play-events", bad_handler)

    record = _make_record()
    with patch.object(consumer_service, "_commit", new_callable=AsyncMock) as mock_commit:
        with patch.object(consumer_service, "_forward_to_dlq", new_callable=AsyncMock):
            await consumer_service._dispatch(record)

    mock_commit.assert_awaited_once_with(record)


async def test_dispatch_forwards_to_dlq_on_handler_failure(consumer_service):
    """A failing handler triggers DLQ forwarding."""
    async def bad_handler(msg):
        raise ValueError("bad message")

    consumer_service.register_handler("play-events", bad_handler)

    record = _make_record()
    with patch.object(consumer_service, "_commit", new_callable=AsyncMock):
        with patch.object(
            consumer_service, "_forward_to_dlq", new_callable=AsyncMock
        ) as mock_dlq:
            await consumer_service._dispatch(record)

    mock_dlq.assert_awaited_once()
    dlq_call = mock_dlq.await_args.args
    assert isinstance(dlq_call[0], ConsumerMessage)
    assert isinstance(dlq_call[1], ValueError)


async def test_dispatch_no_handler_still_commits(consumer_service):
    """Unknown topic: commit so we don't re-deliver, but don't call any handler."""
    record = _make_record(topic="unknown-topic")
    with patch.object(consumer_service, "_commit", new_callable=AsyncMock) as mock_commit:
        await consumer_service._dispatch(record)

    mock_commit.assert_awaited_once_with(record)


# _commit 

async def test_commit_calls_consumer_commit(consumer_service):
    record = _make_record(partition=1, offset=42)
    from aiokafka import TopicPartition
    expected_tp = TopicPartition("play-events", 1)

    consumer_service._consumer.commit = AsyncMock()
    await consumer_service._commit(record)

    consumer_service._consumer.commit.assert_awaited_once_with(
        {expected_tp: 43}   # offset + 1
    )


async def test_commit_noop_when_consumer_none(consumer_service):
    consumer_service._consumer = None
    record = _make_record()
    await consumer_service._commit(record)   # must not raise


async def test_commit_swallows_exception(consumer_service):
    """A commit failure must not propagate — we log and move on."""
    consumer_service._consumer.commit = AsyncMock(side_effect=Exception("commit failed"))
    record = _make_record()
    await consumer_service._commit(record)   # must not raise


# is_healthy 

def test_is_healthy_true_when_running(consumer_service):
    assert consumer_service.is_healthy is True


def test_is_healthy_false_when_not_running(consumer_service):
    consumer_service._running = False
    assert consumer_service.is_healthy is False


def test_is_healthy_false_when_no_consumer():
    svc = KafkaConsumerService()
    assert svc.is_healthy is False