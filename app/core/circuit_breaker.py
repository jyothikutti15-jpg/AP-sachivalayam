"""
Circuit breaker for the Claude API.

States:
  CLOSED   — normal operation, requests pass through.
  OPEN     — API is down; requests fail fast without hitting the API.
  HALF_OPEN — recovery probe; one request is allowed through after the
               cooldown expires. Success → CLOSED, failure → OPEN.

Usage:
    result = await _claude_circuit.call(client.messages.create(...))

The module exposes a single process-level singleton `claude_circuit` so all
LLMRouter instances in the same worker share state.
"""
import asyncio
import time
from enum import Enum

import anthropic
import structlog

logger = structlog.get_logger()

# Exceptions that count as transient API failures and should trip the breaker.
# 4xx client errors (bad request, auth) are NOT included — those are our bugs.
_TRIP_ON = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
    anthropic.RateLimitError,
)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the circuit is open."""


class CircuitBreaker:
    """Async-safe circuit breaker with CLOSED / OPEN / HALF_OPEN states."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        """Current logical state (accounts for recovery timeout)."""
        return self._logical_state()

    async def call(self, coro):
        """Execute *coro* guarded by the circuit breaker.

        Raises CircuitOpenError immediately if the circuit is open.
        Re-raises the original exception on failure (after recording it).
        """
        current = self._logical_state()

        if current == CircuitState.OPEN:
            raise CircuitOpenError(
                f"Claude API circuit is open — retry in "
                f"{self._seconds_until_recovery():.0f}s"
            )

        try:
            result = await coro
        except _TRIP_ON as exc:
            await self._record_failure(was_half_open=(current == CircuitState.HALF_OPEN))
            raise
        except Exception:
            # Non-transient errors (e.g. bad request) — don't trip the breaker.
            raise
        else:
            await self._record_success(was_half_open=(current == CircuitState.HALF_OPEN))
            return result

    def status(self) -> dict:
        """Return a snapshot for health-check / metrics endpoints."""
        return {
            "state": self._logical_state().value,
            "failure_count": self._failure_count,
            "recovery_in_seconds": max(0.0, self._seconds_until_recovery()),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _logical_state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self._recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    def _seconds_until_recovery(self) -> float:
        if self._state != CircuitState.OPEN:
            return 0.0
        elapsed = time.monotonic() - self._last_failure_time
        return max(0.0, self._recovery_timeout - elapsed)

    async def _record_success(self, *, was_half_open: bool) -> None:
        async with self._lock:
            self._failure_count = 0
            if self._state != CircuitState.CLOSED:
                self._state = CircuitState.CLOSED
                logger.info(
                    "Circuit breaker CLOSED — Claude API recovered",
                    was_half_open=was_half_open,
                )

    async def _record_failure(self, *, was_half_open: bool) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            should_open = (
                self._failure_count >= self._failure_threshold or was_half_open
            )
            if should_open and self._state != CircuitState.OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker OPEN — Claude API failing",
                    consecutive_failures=self._failure_count,
                    recovery_in_seconds=self._recovery_timeout,
                )


# ---------------------------------------------------------------------------
# Process-level singleton — shared across all LLMRouter instances in a worker.
# Initialised lazily on first use so settings are fully loaded beforehand.
# ---------------------------------------------------------------------------
_circuit: CircuitBreaker | None = None


def get_circuit_breaker() -> CircuitBreaker:
    global _circuit
    if _circuit is None:
        from app.config import get_settings
        s = get_settings()
        _circuit = CircuitBreaker(
            failure_threshold=s.claude_circuit_failure_threshold,
            recovery_timeout=s.claude_circuit_recovery_timeout,
        )
    return _circuit
