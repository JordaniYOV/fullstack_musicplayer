"""
Tests for LoggingMiddleware.

Uses a minimal Starlette/FastAPI test app so we don't need the full Muse
application stack. Every test inspects the response headers and captured
log records to verify middleware behaviour.
"""
from __future__ import annotations

# import logging
from structlog.testing import capture_logs
import uuid
from typing import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.middlewares.logging import LoggingMiddleware, TRACE_ID_HEADER, REQUEST_ID_HEADER


# ── Minimal test app ──────────────────────────────────────────────────────────

def _make_app(handler: Callable | None = None) -> FastAPI:
    """Return a tiny FastAPI app with LoggingMiddleware and one route."""
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.get("/ok")
    async def ok_route():
        return {"status": "ok"}

    @app.get("/trace-echo")
    async def trace_echo(request: Request):
        return {"trace_id": request.state.trace_id}

    @app.get("/error")
    async def error_route():
        raise RuntimeError("intentional crash")

    @app.get("/health")
    async def health_route():
        return {"status": "healthy"}

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_make_app(), raise_server_exceptions=False)


# ── Trace ID ──────────────────────────────────────────────────────────────────

def test_trace_id_header_added_to_response(client):
    """Middleware injects X-Trace-ID into every response."""
    resp = client.get("/ok")
    assert TRACE_ID_HEADER in resp.headers
    # Value must be a valid UUID
    trace_id = resp.headers[TRACE_ID_HEADER]
    uuid.UUID(trace_id)   # raises if invalid


def test_trace_id_is_unique_per_request(client):
    """Each request gets a different trace ID."""
    r1 = client.get("/ok")
    r2 = client.get("/ok")
    assert r1.headers[TRACE_ID_HEADER] != r2.headers[TRACE_ID_HEADER]


def test_trace_id_propagated_from_request_id_header(client):
    """If the client sends X-Request-ID the middleware reuses it."""
    client_trace = str(uuid.uuid4())
    resp = client.get("/ok", headers={REQUEST_ID_HEADER: client_trace})
    assert resp.headers[TRACE_ID_HEADER] == client_trace


def test_trace_id_propagated_from_x_trace_id_header(client):
    """If the client sends X-Trace-ID the middleware reuses it."""
    client_trace = str(uuid.uuid4())
    resp = client.get("/ok", headers={TRACE_ID_HEADER: client_trace})
    assert resp.headers[TRACE_ID_HEADER] == client_trace


def test_trace_id_stored_on_request_state(client):
    """request.state.trace_id is accessible inside route handlers."""
    resp = client.get("/trace-echo")
    assert resp.status_code == 200
    body = resp.json()
    assert "trace_id" in body
    uuid.UUID(body["trace_id"])   # must be a valid UUID


# ── Structured logging ────────────────────────────────────────────────────────

def test_request_log_emitted():
    """Middleware emits one INFO log per non-health request."""
    app = _make_app()
    client = TestClient(app, raise_server_exceptions=False)

    with capture_logs() as cap_logs:
        client.get("/ok")

    log_messages = [log for log in cap_logs if log["log_level"] == "info"]
    assert any("http_request" in m["event"] for m in log_messages)


def test_request_log_contains_required_fields():
    """The log record extra dict has method, path, status_code, latency_ms."""
    app = _make_app()
    client = TestClient(app, raise_server_exceptions=False)

    with capture_logs() as cap_logs:
        response = client.get("/ok")
    
    http_records = [r for r in cap_logs if r.get("event") == "http_request"]
    assert len(http_records) >= 1

    record = http_records[0]
    extra = record["extra"]
    
    assert extra["method"] == "GET"
    assert extra["path"] == "/ok"
    assert extra["status_code"] == 200
    assert "latency_ms" in extra
    assert isinstance(extra["latency_ms"], (int, float))
    assert extra["latency_ms"] >= 0
    
    assert record.get("log_level", "").lower() == "info"


def test_health_endpoint_logged_at_debug(caplog):
    """Requests to /health are logged at DEBUG not INFO (to reduce noise)."""
    app = _make_app()
    client = TestClient(app, raise_server_exceptions=False)

    with capture_logs() as cap_logs:
        client.get("/health")

    health_logs = [
        r for r in cap_logs
        if r.get("event") == "http_request"
    ]
    assert len(health_logs) >= 1
    record = health_logs[0]
    assert record.get("log_level", "").lower() == "debug"

def test_error_route_logs_at_error_level(caplog):
    """Unhandled exceptions are logged at ERROR level before re-raising."""
    app = _make_app()
    client = TestClient(app, raise_server_exceptions=False)

    with capture_logs() as cap_logs:
        client.get("/error")

    error_logs = [r for r in cap_logs if r.get("log_level").lower() == 'error']
    # Middleware should have emitted at least one error log
    assert len(error_logs) >= 1


# # ── Latency ───────────────────────────────────────────────────────────────────

def test_latency_is_positive(caplog):
    """Logged latency_ms must be a positive number."""
    app = _make_app()
    client = TestClient(app, raise_server_exceptions=False)

    with capture_logs() as cap_logs:
        client.get("/ok")

    http_records = [r for r in cap_logs if r.get("event") == "http_request"]
    assert len(http_records) >= 1
    # latency_ms is stored in the LogRecord extra attributes
    record_dict = http_records[0].get("extra")
    latency = record_dict.get("latency_ms")
    if latency is not None:
        assert latency >= 0


# ── Client IP ─────────────────────────────────────────────────────────────────

def test_x_forwarded_for_used_for_client_ip():
    """If X-Forwarded-For is present it is used as client_ip."""
    from app.core.middleware import _get_client_ip

    mock_request = MagicMock()
    mock_request.headers = {"x-forwarded-for": "203.0.113.5, 10.0.0.1"}
    mock_request.client = MagicMock()
    mock_request.client.host = "10.0.0.2"

    ip = _get_client_ip(mock_request)
    assert ip == "203.0.113.5"


def test_client_host_used_when_no_forwarded_for():
    """Falls back to request.client.host when X-Forwarded-For is absent."""
    from app.core.middleware import _get_client_ip

    mock_request = MagicMock()
    mock_request.headers = {}
    mock_request.client = MagicMock()
    mock_request.client.host = "192.168.1.1"

    ip = _get_client_ip(mock_request)
    assert ip == "192.168.1.1"


def test_unknown_when_no_client():
    """Returns 'unknown' when there is no client information at all."""
    from app.core.middleware import _get_client_ip

    mock_request = MagicMock()
    mock_request.headers = {}
    mock_request.client = None

    ip = _get_client_ip(mock_request)
    assert ip == "unknown"