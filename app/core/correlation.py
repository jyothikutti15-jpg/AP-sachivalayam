"""
Request correlation ID middleware.

Attaches a unique X-Correlation-ID to every request, binding it into the
structlog context so every log line emitted during that request carries the
same ID — making it trivial to trace a single request across all services.

Priority:
  1. Use X-Correlation-ID header sent by the caller (e.g. WhatsApp gateway).
  2. Fall back to a new UUID4 if the header is absent or empty.

The resolved ID is:
  - Bound into structlog contextvars → auto-injected into all log lines.
  - Returned in the X-Correlation-ID response header so callers can log it.
"""
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Resolve correlation ID
        correlation_id = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())

        # Bind to structlog context for this async task — cleared automatically
        # after the request because structlog.contextvars uses contextvars.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
        )

        response: Response = await call_next(request)

        # Echo the ID back so clients/gateways can correlate their own logs.
        response.headers[CORRELATION_HEADER] = correlation_id
        return response
