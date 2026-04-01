"""
Redis-backed sliding window rate limiter for API endpoints.
Prevents abuse and ensures fair resource allocation.
"""
from datetime import datetime, timezone

import structlog
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.dependencies import redis_client

logger = structlog.get_logger()

# Default rate limits per endpoint pattern
DEFAULT_LIMITS = {
    "/api/v1/whatsapp/webhook": {"requests": 200, "window": 60},
    "/api/v1/schemes/search": {"requests": 30, "window": 60},
    "/api/v1/schemes/eligibility-check": {"requests": 30, "window": 60},
    "/api/v1/grievances/": {"requests": 20, "window": 60},
    "/api/v1/tasks/": {"requests": 30, "window": 60},
    "/api/v1/forms/auto-fill": {"requests": 15, "window": 60},
    "/api/v1/voice/transcribe": {"requests": 10, "window": 60},
    "/api/v1/grievances/export": {"requests": 5, "window": 3600},
    "/api/v1/tasks/export": {"requests": 5, "window": 3600},
    "/api/v1/analytics/export": {"requests": 5, "window": 3600},
}

# Exempt paths
EXEMPT_PATHS = {"/health", "/api/v1/health", "/", "/docs", "/openapi.json"}

# Global fallback
GLOBAL_LIMIT = {"requests": 100, "window": 60}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window counter rate limiter using Redis."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip exempt paths
        if path in EXEMPT_PATHS:
            return await call_next(request)

        # Get identifier (employee_id from query, or client IP)
        identifier = self._get_identifier(request)

        # Find matching rate limit
        limit_config = self._get_limit_for_path(path)
        max_requests = limit_config["requests"]
        window_seconds = limit_config["window"]

        try:
            # Check rate limit
            current_count, ttl = await self._check_rate_limit(
                identifier, path, max_requests, window_seconds
            )

            if current_count > max_requests:
                logger.warning(
                    "Rate limit exceeded",
                    identifier=identifier,
                    path=path,
                    count=current_count,
                    limit=max_requests,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded. Please try again later.",
                        "detail_te": "అభ్యర్థన పరిమితి దాటింది. దయచేసి కొద్దిసేపట్లో మళ్ళీ ప్రయత్నించండి.",
                        "retry_after": ttl,
                    },
                    headers={
                        "Retry-After": str(ttl),
                        "X-RateLimit-Limit": str(max_requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(ttl),
                    },
                )

            # Process request
            response = await call_next(request)

            # Add rate limit headers
            remaining = max(0, max_requests - current_count)
            response.headers["X-RateLimit-Limit"] = str(max_requests)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(ttl)

            return response

        except Exception as e:
            # On Redis failure, allow the request (fail-open)
            logger.debug("Rate limiter error, allowing request", error=str(e))
            return await call_next(request)

    def _get_identifier(self, request: Request) -> str:
        """Extract rate limit identifier from request."""
        # Try employee_id from query params
        employee_id = request.query_params.get("employee_id")
        if employee_id:
            return f"emp:{employee_id}"

        # Fall back to client IP
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        return f"ip:{client_ip}"

    def _get_limit_for_path(self, path: str) -> dict:
        """Find the matching rate limit config for a path."""
        for pattern, config in DEFAULT_LIMITS.items():
            if path.startswith(pattern):
                return config
        return GLOBAL_LIMIT

    async def _check_rate_limit(
        self, identifier: str, path: str, max_requests: int, window_seconds: int
    ) -> tuple[int, int]:
        """Check and increment rate limit counter. Returns (current_count, ttl)."""
        # Normalize path for key
        path_key = path.replace("/", "_").strip("_")
        now = int(datetime.now(timezone.utc).timestamp())
        window_start = now - window_seconds
        key = f"ratelimit:{identifier}:{path_key}"

        pipe = redis_client.pipeline()
        # Remove old entries outside window
        pipe.zremrangebyscore(key, 0, window_start)
        # Add current request
        pipe.zadd(key, {str(now): now})
        # Count requests in window
        pipe.zcard(key)
        # Set TTL
        pipe.expire(key, window_seconds)

        results = await pipe.execute()
        current_count = results[2]
        ttl = window_seconds

        return current_count, ttl
