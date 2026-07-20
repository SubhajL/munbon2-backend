"""Shared contract for the shadow-dispatch worker heartbeat (PR 6.4).

The dispatch tick (``jobs.shadow_dispatch_once``) writes a fresh ISO-8601 instant to a Redis
key at the end of every run; readiness (armed mode only) and the ``/metrics`` collector read it
to tell a running-but-idle worker from a dead one. A DEDICATED per-tick heartbeat is required
because a healthy idle worker (empty/all-receipted outbox) writes no control rows — liveness
cannot be derived from the append-only tables. Redis (not a new table) because the scheduler
already depends on it and ``/ready`` already pings it; a Redis restart transiently loses the
beat and readiness fails closed until the next tick, which is the conservative direction.
"""

from __future__ import annotations

from datetime import datetime

from core.logger import get_logger

logger = get_logger(__name__)

DISPATCH_WORKER_NAME = "shadow_dispatch"
DISPATCH_HEARTBEAT_KEY = "scheduler:shadow_dispatch:heartbeat"
# The key outlives many staleness windows so age stays computable; once it expires the worker
# is definitively dead and both readiness and /metrics report it absent.
HEARTBEAT_TTL_SECONDS = 3600


async def record_dispatch_heartbeat(
    redis,
    *,
    now: datetime,
    key: str = DISPATCH_HEARTBEAT_KEY,
    ttl_seconds: int = HEARTBEAT_TTL_SECONDS,
) -> bool:
    """Write a fresh ISO heartbeat; return True on success. BEST-EFFORT: a Redis failure is
    logged and swallowed so it can never fail the already-committed dispatch tick (a missing
    beat simply reads as stale/absent downstream)."""
    try:
        await redis.set(key, now.isoformat(), expire=ttl_seconds)
        return True
    except Exception as error:  # noqa: BLE001 - the heartbeat must never fail the tick
        logger.error("dispatch heartbeat write failed (non-fatal): {}", str(error))
        return False


async def read_dispatch_heartbeat(redis, *, key: str = DISPATCH_HEARTBEAT_KEY) -> str | None:
    """Read the raw ISO heartbeat string, or None if absent/unreadable. Never raises — a
    metrics or readiness read must not become an HTTP 500."""
    try:
        return await redis.get(key)
    except Exception:  # noqa: BLE001 - swallow driver errors (can carry host/creds)
        return None


def heartbeat_age_seconds(heartbeat_iso: str | None, now: datetime) -> float | None:
    """Age of the heartbeat in seconds, or None when absent/unparseable/naive. A future beat
    (clock skew) is clamped to 0.0 rather than reported negative."""
    if not heartbeat_iso:
        return None
    try:
        beat = datetime.fromisoformat(heartbeat_iso)
    except (ValueError, TypeError):
        return None
    # Both operands must be tz-aware; a naive `beat` OR a naive `now` yields None rather than a
    # TypeError from the subtraction (honors the docstring for both operands).
    if beat.tzinfo is None or now.tzinfo is None:
        return None
    age = (now - beat).total_seconds()
    return age if age > 0 else 0.0
