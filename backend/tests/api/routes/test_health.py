"""
Tests for GET /health.

Uses AsyncMock to control what each dependency check returns so we can test
every combination of healthy / degraded / unhealthy without real services.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio



# Helpers 

async def _get(async_client, path: str = "/health"):
    return await async_client.get(path)


# All healthy 

async def test_health_all_healthy(async_client):
    """When all checks pass → 200 + status=healthy."""
    with (
        patch(
            "app.api.routes.private.health._check_postgres",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 1.0},
        ),
        patch(
            "app.api.routes.private.health._check_redis",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 0.5},
        ),
        patch(
            "app.api.routes.private.health._check_kafka",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 2.0, "topics": [], "missing_topics": []},
        ),
        # patch("app.api.routes.private.health.kafka_producer", MagicMock(is_healthy=True)),
        # patch(
        #     "app.api.routes.private.health.kafka_consumer_service",
        #     MagicMock(is_healthy=True, subscribed_topics=["play-events"]),
        # ),
    ):
        resp = await _get(async_client)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert "checks" in body
    assert "uptime_seconds" in body


# Response shape 

async def test_health_response_has_all_sections(async_client):
    """Response always contains postgres, redis, kafka, kafka_producer, kafka_consumer."""
    with (
        patch(
            "app.api.routes.private.health._check_postgres",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 1.0},
        ),
        patch(
            "app.api.routes.private.health._check_redis",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 0.5},
        ),
        patch(
            "app.api.routes.private.health._check_kafka",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 1.0, "topics": [], "missing_topics": []},
        ),
        # patch("app.api.routes.private.health.kafka_producer", MagicMock(is_healthy=True)),
        # patch(
        #     "app.api.routes.private.health.kafka_consumer_service",
        #     MagicMock(is_healthy=True, subscribed_topics=[]),
        # ),
    ):
        resp = await _get(async_client)

    checks = resp.json()["checks"]
    assert "postgres" in checks
    assert "redis" in checks
    assert "kafka" in checks
    assert "kafka_producer" in checks
    assert "kafka_consumer" in checks


#  Postgres failure → unhealthy 

async def test_health_postgres_down_returns_503(async_client):
    """Postgres failure is critical → 503 + status=unhealthy."""
    with (
        patch(
            "app.api.routes.private.health._check_postgres",
            new_callable=AsyncMock,
            return_value={"status": "error", "latency_ms": 5000.0, "error": "connection refused"},
        ),
        patch(
            "app.api.routes.private.health._check_redis",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 0.5},
        ),
        patch(
            "app.api.routes.private.health._check_kafka",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 1.0, "topics": [], "missing_topics": []},
        ),
        # patch("app.api.routes.private.health.kafka_producer", MagicMock(is_healthy=True)),
        # patch(
        #     "app.api.routes.private.health.kafka_consumer_service",
        #     MagicMock(is_healthy=True, subscribed_topics=[]),
        # ),
    ):
        resp = await _get(async_client)

    assert resp.status_code == 503
    assert resp.json()["status"] == "unhealthy"


#Redis failure → unhealthy

async def test_health_redis_down_returns_503(async_client):
    with (
        patch(
            "app.api.routes.private.health._check_postgres",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 1.0},
        ),
        patch(
            "app.api.routes.private.health._check_redis",
            new_callable=AsyncMock,
            return_value={"status": "error", "latency_ms": 100.0, "error": "ECONNREFUSED"},
        ),
        patch(
            "app.api.routes.private.health._check_kafka",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 1.0, "topics": [], "missing_topics": []},
        ),
        # patch("app.api.routes.private.health.kafka_producer", MagicMock(is_healthy=True)),
        # patch(
        #     "app.api.routes.private.health.kafka_consumer_service",
        #     MagicMock(is_healthy=True, subscribed_topics=[]),
        # ),
    ):
        resp = await _get(async_client)

    assert resp.status_code == 503
    assert resp.json()["status"] == "unhealthy"


#Kafka failure → degraded 

async def test_health_kafka_down_returns_200_degraded(async_client):
    """Kafka failure is non-critical → 200 + status=degraded."""
    with (
        patch(
            "app.api.routes.private.health._check_postgres",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 1.0},
        ),
        patch(
            "app.api.routes.private.health._check_redis",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 0.5},
        ),
        patch(
            "app.api.routes.private.health._check_kafka",
            new_callable=AsyncMock,
            return_value={"status": "error", "latency_ms": 5000.0, "error": "broker unavailable"},
        ),
        # patch("app.api.routes.private.health.kafka_producer", MagicMock(is_healthy=False)),
        # patch(
        #     "app.api.routes.private.health.kafka_consumer_service",
        #     MagicMock(is_healthy=False, subscribed_topics=[]),
        # ),
    ):
        resp = await _get(async_client)

    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"


# Kafka missing topics

async def test_health_kafka_missing_topics_is_degraded(async_client):
    """Some topics missing → kafka check is degraded, overall may be degraded."""
    with (
        patch(
            "app.api.routes.private.health._check_postgres",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 1.0},
        ),
        patch(
            "app.api.routes.private.health._check_redis",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 0.5},
        ),
        patch(
            "app.api.routes.private.health._check_kafka",
            new_callable=AsyncMock,
            return_value={
                "status": "degraded",
                "latency_ms": 2.0,
                "topics": ["play-events"],
                "missing_topics": ["chart-updates"],
            },
        ),
        # patch("app.api.routes.private.health.kafka_producer", MagicMock(is_healthy=True)),
        # patch(
        #     "app.api.routes.private.health.kafka_consumer_service",
        #     MagicMock(is_healthy=True, subscribed_topics=["play-events"]),
        # ),
    ):
        resp = await _get(async_client)

    assert resp.status_code == 200
    kafka_check = resp.json()["checks"]["kafka"]
    assert "chart-updates" in kafka_check["missing_topics"]


#Uptime

async def test_health_uptime_is_positive(async_client):
    """uptime_seconds is always a positive number."""
    with (
        patch(
            "app.api.routes.private.health._check_postgres",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 1.0},
        ),
        patch(
            "app.api.routes.private.health._check_redis",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 0.5},
        ),
        patch(
            "app.api.routes.private.health._check_kafka",
            new_callable=AsyncMock,
            return_value={"status": "ok", "latency_ms": 1.0, "topics": [], "missing_topics": []},
        ),
        # patch("app.api.routes.private.health.kafka_producer", MagicMock(is_healthy=True)),
        # patch(
        #     "app.api.routes.private.health.kafka_consumer_service",
        #     MagicMock(is_healthy=True, subscribed_topics=[]),
        # ),
    ):
        resp = await _get(async_client)

    assert resp.json()["uptime_seconds"] > 0


#_check_postgres unit 

async def test_check_postgres_ok(async_session):
    from app.api.routes.private.health import _check_postgres

    result = await _check_postgres(async_session)

    assert result["status"] == "ok"
    assert result["latency_ms"] >= 0


async def test_check_postgres_error_returns_dict():
    from app.api.routes.private.health import _check_postgres

    bad_session = AsyncMock()
    bad_session.execute = AsyncMock(side_effect=Exception("pg down"))

    result = await _check_postgres(bad_session)

    assert result["status"] == "error"
    assert "error" in result


# _check_redis unit

async def test_check_redis_ok():
    from app.api.routes.private.health import _check_redis

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)

    result = await _check_redis(mock_redis)

    assert result["status"] == "ok"
    assert result["latency_ms"] >= 0


async def test_check_redis_error_returns_dict():
    from app.api.routes.private.health import _check_redis

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(side_effect=Exception("connection refused"))

    result = await _check_redis(mock_redis)

    assert result["status"] == "error"
    assert "error" in result


# _check_kafka unit 

async def test_check_kafka_ok():
    from app.api.routes.private.health import _check_kafka
    from app.core.kafka.topics import TOPIC_SPECS

    all_topic_names = [s.name for s in TOPIC_SPECS]

    with patch(
        "app.api.routes.private.health.list_topics",
        new_callable=AsyncMock,
        return_value=all_topic_names,
    ):
        result = await _check_kafka()

    assert result["status"] == "ok"
    assert result["missing_topics"] == []


async def test_check_kafka_missing_topics():
    from app.api.routes.private.health import _check_kafka

    with patch(
        "app.api.routes.private.health.list_topics",
        new_callable=AsyncMock,
        return_value=[],   # no topics at all
    ):
        result = await _check_kafka()

    assert result["status"] == "degraded"
    assert len(result["missing_topics"]) > 0


async def test_check_kafka_connection_error():
    from app.api.routes.private.health import _check_kafka

    with patch(
        "app.api.routes.private.health.list_topics",
        new_callable=AsyncMock,
        side_effect=Exception("broker unreachable"),
    ):
        result = await _check_kafka()

    assert result["status"] == "error"
    assert "error" in result