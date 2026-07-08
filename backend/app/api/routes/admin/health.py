"""
Health check endpoint.

GET /health
-----------
Returns a JSON response describing the health of every dependency.
Used by Docker health checks, Kubernetes liveness/readiness probes,
and the Kafka UI's status page.

Response shape:
{
  "status": "healthy" | "degraded" | "unhealthy",
  "uptime_seconds": 123.4,
  "checks": {
    "postgres": {"status": "ok", "latency_ms": 1.2},
    "redis":    {"status": "ok", "latency_ms": 0.4},
    "kafka":    {"status": "ok", "topics": ["play-events", ...]},
  }
}

- "healthy"   → all checks passed
- "degraded"  → at least one non-critical check failed (Kafka)
- "unhealthy" → a critical check failed (Postgres or Redis)

The HTTP status code mirrors the overall status:
  healthy   → 200
  degraded  → 200   (app is still serving traffic)
  unhealthy → 503
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RedisDep, SessionDep
from app.core.kafka.topics import TOPIC_SPECS, list_topics
from app.logging_config import get_logger

logger = get_logger("app.api.routes.health", engine="psycopg3")

router = APIRouter(tags=["health_private"])


_PROCESS_START = time.monotonic()


@router.get(
    "/health",
    summary="Health check",
    description="Returns the status of all backend dependencies.",
    response_description="Health status object",
)
async def health_check(
    session: SessionDep,
    redis: RedisDep,
) -> JSONResponse:

    checks: dict[str, Any] = {}
    overall = "healthy"

    # Postgres 
    postgres_status = await _check_postgres(session)
    checks["postgres"] = postgres_status
    if postgres_status["status"] != "ok":
        overall = "unhealthy"   # critical

    # Redis 
    redis_status = await _check_redis(redis)
    checks["redis"] = redis_status
    if redis_status["status"] != "ok":
        overall = "unhealthy"   # critical

    # Kafka 
    kafka_status = await _check_kafka()
    checks["kafka"] = kafka_status
    if kafka_status["status"] != "ok" and overall == "healthy":
        overall = "degraded"    # non-critical — charts still work from DB

    # Producer circuit breaker 
    from app.core.kafka.producer import kafka_producer
    checks["kafka_producer"] = {
        "status": "ok" if (kafka_producer and kafka_producer.is_healthy) else "degraded",
        "circuit_open": kafka_producer is not None and not kafka_producer.is_healthy,
    }

    # Consumer
    from app.core.kafka.consumer import kafka_consumer_service
    checks["kafka_consumer"] = {
        "status": "ok" if (kafka_consumer_service and kafka_consumer_service.is_healthy) else "degraded",
        "subscribed_topics": (
            kafka_consumer_service.subscribed_topics if kafka_consumer_service else []
        ),
    }

    uptime_seconds = round(time.monotonic() - _PROCESS_START, 1)

    body = {
        "status": overall,
        "uptime_seconds": uptime_seconds,
        "checks": checks,
    }

    http_status = 503 if overall == "unhealthy" else 200

    logger.debug(
        "health_check",
        extra={"status": overall, "uptime_seconds": uptime_seconds},
    )

    return JSONResponse(content=body, status_code=http_status)


# Individual check helpers

async def _check_postgres(session: AsyncSession) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        await session.execute(text("SELECT 1"))
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        return {"status": "ok", "latency_ms": latency_ms}
    except Exception as exc:
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.error(
            "health_postgres_failed",
            extra={"error": str(exc), "latency_ms": latency_ms},
        )
        return {
            "status": "error",
            "latency_ms": latency_ms,
            "error": str(exc),
        }


async def _check_redis(redis) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        pong = await redis.ping()
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        return {"status": "ok" if pong else "error", "latency_ms": latency_ms}
    except Exception as exc:
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.error(
            "health_redis_failed",
            extra={"error": str(exc), "latency_ms": latency_ms},
        )
        return {
            "status": "error",
            "latency_ms": latency_ms,
            "error": str(exc),
        }


async def _check_kafka() -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        live_topics = await list_topics()
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        expected = {spec.name for spec in TOPIC_SPECS}
        missing = expected - set(live_topics)
        return {
            "status": "ok" if not missing else "degraded",
            "latency_ms": latency_ms,
            "topics": live_topics,
            "missing_topics": list(missing),
        }
    except Exception as exc:
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.error(
            "health_kafka_failed",
            extra={"error": str(exc), "latency_ms": latency_ms},
        )
        return {
            "status": "error",
            "latency_ms": latency_ms,
            "error": str(exc),
        }