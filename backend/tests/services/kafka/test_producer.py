"""
Unit tests for KafkaProducerService.

All tests use AsyncMock to avoid needing a real Kafka broker.
The AIOKafkaProducer is patched at the class level so we never open a socket.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from aiokafka.errors import KafkaConnectionError, KafkaTimeoutError

from app.core.kafka.producer import (
    KafkaProducerService,
    MAX_RETRIES,
    CIRCUIT_OPEN_THRESHOLD,
    CIRCUIT_RESET_SECONDS,
)


# Fixtures 

def _make_record_metadata(partition: int = 0, offset: int = 1):
    meta = MagicMock()
    meta.partition = partition
    meta.offset = offset
    return meta


@pytest_asyncio.fixture
async def producer() -> KafkaProducerService:
    """Producer with a mocked underlying AIOKafkaProducer."""
    svc = KafkaProducerService(bootstrap_servers="localhost:9094")
    mock_inner = AsyncMock()
    mock_inner.send_and_wait = AsyncMock(return_value=_make_record_metadata())
    svc._producer = mock_inner
    return svc


# start / stop 

async def test_start_success():
    """start() initialises _producer and logs success."""
    svc = KafkaProducerService(bootstrap_servers="localhost:9094")
    with patch("app.core.kafka.producer.AIOKafkaProducer") as MockProducer:
        mock_instance = AsyncMock()
        MockProducer.return_value = mock_instance
        await svc.start()

    assert svc._producer is mock_instance
    mock_instance.start.assert_awaited_once()


async def test_start_failure_sets_producer_none():
    """If the broker is unreachable start() sets _producer=None (no crash)."""
    svc = KafkaProducerService(bootstrap_servers="localhost:9094")
    with patch("app.core.kafka.producer.AIOKafkaProducer") as MockProducer:
        mock_instance = AsyncMock()
        mock_instance.start.side_effect = KafkaConnectionError("refused")
        MockProducer.return_value = mock_instance
        await svc.start()

    assert svc._producer is None


async def test_stop_calls_underlying_stop(producer):
    mok = producer._producer
    await producer.stop()
    mok.stop.assert_awaited_once()
    assert producer._producer is None


async def test_stop_noop_when_no_producer():
    svc = KafkaProducerService()
    svc._producer = None
    await svc.stop()   # must not raise


# send — happy path 

async def test_send_returns_true_on_success(producer):
    result = await producer.send("play-events", b"payload", key=b"track-1")
    assert result is True


async def test_send_calls_send_and_wait_with_correct_args(producer):
    await producer.send("play-events", b"hello", key=b"k")
    producer._producer.send_and_wait.assert_awaited_once_with(
        "play-events", value=b"hello", key=b"k", headers=[]
    )


async def test_send_resets_circuit_on_success(producer):
    producer._consecutive_failures = 3
    await producer.send("play-events", b"x")
    assert producer._consecutive_failures == 0


# send — no producer

async def test_send_returns_false_when_no_producer():
    svc = KafkaProducerService()
    svc._producer = None
    result = await svc.send("play-events", b"x")
    assert result is False


# send — retries 

async def test_send_retries_on_connection_error(producer):
    """Transient KafkaConnectionError is retried up to MAX_RETRIES times."""
    producer._producer.send_and_wait = AsyncMock(
        side_effect=[
            KafkaConnectionError("timeout"),
            KafkaConnectionError("timeout"),
            _make_record_metadata(),   # success on 3rd attempt
        ]
    )
    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await producer.send("play-events", b"x")

    assert result is True
    assert producer._producer.send_and_wait.await_count == 3


async def test_send_fails_after_max_retries(producer):
    """After MAX_RETRIES all failed → returns False and records failure."""
    producer._producer.send_and_wait = AsyncMock(
        side_effect=KafkaConnectionError("down")
    )
    # Patch DLQ send so we don't need a real producer for it
    with patch.object(producer, "send_to_dlq", new_callable=AsyncMock):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await producer.send("play-events", b"x")

    assert result is False
    assert producer._consecutive_failures == 1


async def test_send_no_retry_on_non_retriable_error(producer):
    """Non-KafkaConnectionError errors are not retried."""
    producer._producer.send_and_wait = AsyncMock(
        side_effect=ValueError("bad serialisation")
    )
    with patch.object(producer, "send_to_dlq", new_callable=AsyncMock):
        result = await producer.send("play-events", b"x")

    # Should have only tried once
    assert producer._producer.send_and_wait.await_count == 1
    assert result is False


# Circuit breaker 

async def test_circuit_opens_after_threshold(producer):
    """After CIRCUIT_OPEN_THRESHOLD consecutive failures the circuit opens."""
    producer._producer.send_and_wait = AsyncMock(
        side_effect=KafkaConnectionError("down")
    )
    with patch.object(producer, "send_to_dlq", new_callable=AsyncMock):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            for _ in range(CIRCUIT_OPEN_THRESHOLD):
                await producer.send("play-events", b"x")

    assert producer.is_circuit_open() is True


async def test_circuit_open_drops_messages_immediately(producer):
    """When circuit is open send() returns False without calling send_and_wait."""
    producer._circuit_opened_at = time.monotonic()  # force open
    producer._consecutive_failures = CIRCUIT_OPEN_THRESHOLD

    result = await producer.send("play-events", b"x")

    assert result is False
    producer._producer.send_and_wait.assert_not_awaited()


async def test_circuit_resets_after_timeout(producer):
    """After CIRCUIT_RESET_SECONDS the circuit half-opens and allows a request."""
    # Simulate circuit opened long ago
    producer._circuit_opened_at = time.monotonic() - CIRCUIT_RESET_SECONDS - 1
    producer._consecutive_failures = CIRCUIT_OPEN_THRESHOLD

    assert producer.is_circuit_open() is False   # should be half-open now
    # A successful send resets fully
    result = await producer.send("play-events", b"x")
    assert result is True
    assert producer._circuit_opened_at is None


# DLQ forwarding 
async def test_dlq_forwarded_on_all_retries_exhausted(producer):
    """After all retries fail, _send_to_dlq is called."""
    producer._producer.send_and_wait = AsyncMock(
        side_effect=KafkaConnectionError("down")
    )
    with patch.object(producer, "send_to_dlq", new_callable=AsyncMock) as mock_dlq:
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await producer.send("play-events", b"payload", key=b"k")

    mock_dlq.assert_awaited_once()
    call_kwargs = mock_dlq.await_args.kwargs
    assert call_kwargs["topic"] == "play-events"
    assert call_kwargs["value"] == b"payload"
    assert call_kwargs["key"] == b"k"


async def test_dlq_sends_to_correct_topic(producer):
    """_send_to_dlq sends to play-events.dlq for play-events failures."""
    from app.core.kafka.topics import TOPIC_PLAY_EVENTS_DLQ

    producer._producer.send_and_wait = AsyncMock(return_value=_make_record_metadata())
    error = RuntimeError("handler failed")

    await producer.send_to_dlq("play-events", b"payload", b"key", error)

    producer._producer.send_and_wait.assert_awaited_once()
    call_args = producer._producer.send_and_wait.await_args
    assert call_args.args[0] == TOPIC_PLAY_EVENTS_DLQ


async def test_dlq_no_crash_when_dlq_send_fails(producer):
    """If even the DLQ send fails, we log and do not raise."""
    producer._producer.send_and_wait = AsyncMock(
        side_effect=KafkaConnectionError("totally down")
    )
    # Should not raise
    await producer.send_to_dlq("play-events", b"x", None, RuntimeError("orig"))


# is_healthy 

async def test_is_healthy_true_when_producer_up_circuit_closed(producer):
    assert producer.is_healthy is True


async def test_is_healthy_false_when_no_producer():
    svc = KafkaProducerService()
    svc._producer = None
    assert svc.is_healthy is False


async def test_is_healthy_false_when_circuit_open(producer):
    producer._circuit_opened_at = time.monotonic()
    producer._consecutive_failures = CIRCUIT_OPEN_THRESHOLD
    assert producer.is_healthy is False