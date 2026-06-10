"""
HTTP request middleware.

LoggingMiddleware
-----------------
Runs for every request. Adds:
  - A unique X-Trace-ID header (UUID) so every log line in a request shares an id.
  - Structured log at the end of each request: method, path, status_code, latency_ms,
    user_agent, ip, trace_id.
  - The trace_id is bound to structlog's context for the lifetime of the request
    so any log emitted from a service layer also carries it.

Usage in main.py:
    app.add_middleware(LoggingMiddleware)
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import get_logger

logger = get_logger("app.core.middleware")

# Headers we add / read
TRACE_ID_HEADER = "X-Trace-ID"
# If the client already sends a trace id (from a gateway) we reuse it
REQUEST_ID_HEADER = "X-Request-ID"


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Structured request logging middleware.

    Emits one log line per request with:
        trace_id, method, path, status_code, latency_ms,
        client_ip, user_agent, response_content_length
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # ── Generate / propagate trace id ─────────────────────────────────
        trace_id: str = (
            request.headers.get(REQUEST_ID_HEADER)
            or request.headers.get(TRACE_ID_HEADER)
            or str(uuid.uuid4())
        )

        # Store on request.state so route handlers can access it if needed
        request.state.trace_id = trace_id

        # ── Timing ────────────────────────────────────────────────────────
        t0 = time.monotonic()

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            latency_ms = (time.monotonic() - t0) * 1000
            logger.error(
                "request_unhandled_exception",
                extra={
                    "trace_id": trace_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "latency_ms": round(latency_ms, 2),
                },
                exc_info=True,
            )
            raise

        latency_ms = (time.monotonic() - t0) * 1000

        # ── Propagate trace id in response headers ────────────────────────
        response.headers[TRACE_ID_HEADER] = trace_id

        # ── Structured log ────────────────────────────────────────────────
        # Skip health-check noise at INFO level
        log_fn = logger.debug if request.url.path in ("/health", "/metrics") else logger.info

        log_fn(
            "http_request",
            extra={
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query) or None,
                "status_code": response.status_code,
                "latency_ms": round(latency_ms, 2),
                "client_ip": _get_client_ip(request),
                "user_agent": request.headers.get("user-agent"),
                "content_length": response.headers.get("content-length"),
            },
        )

        return response


def _get_client_ip(request: Request) -> str:
    """
    Extract real client IP.
    Prefers X-Forwarded-For (set by nginx / load-balancer) over request.client.host.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # X-Forwarded-For can be a comma-separated list; take the first (leftmost) IP
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"