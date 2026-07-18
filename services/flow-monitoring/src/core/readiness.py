"""Dependency-truth readiness for flow-monitoring's control plane (PR 4.4a-2).

`/health` is process liveness only; `/ready` calls `check_flow_readiness`, which
is ready ONLY when:
  * Postgres is healthy,
  * a valid commandable=false engineering-prior release is loaded,
  * the non-commanding prediction service is initialized,
  * BOTH prediction tables exist, and
  * the prediction migration checksum matches `flow_monitoring.schema_migrations`.

Only PostgreSQL gates readiness, so it is pinged DIRECTLY under a bounded
wall-clock — never the full multi-store health check, whose hung InfluxDB/
Timescale/Redis would otherwise stall a healthy-PG readiness.

Everything fails closed. The returned ``checks`` hold only safe status strings
("ok" / "missing" / "incomplete" / "unhealthy" / "not_migrated" / "drift" /
"error" / "unreachable") — never a hostname, credential, or raw exception text.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Mapping

from core.model_release import EvidenceClass

PREDICTION_TABLES: tuple[str, ...] = (
    "prediction_runs",
    "prediction_artifacts",
)

SCHEMA = "flow_monitoring"

# The tracked migration manifest MUST contain at least this baseline pair. An
# empty/partial package (SQL files omitted) would otherwise compare empty==empty
# and pass — so a missing baseline id fails closed.
REQUIRED_BASELINE_MIGRATION_IDS: frozenset[str] = frozenset(
    {"0001_prediction_persistence"}
)

# Bounded wall-clock for the direct Postgres readiness probe: only PostgreSQL
# gates flow readiness, so we ping IT under a hard timeout rather than the full
# multi-store health check (a hung InfluxDB/Timescale/Redis must never stall it).
DEFAULT_POSTGRES_PROBE_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class ReadinessResult:
    ready: bool
    checks: dict[str, str]


def evaluate_migrations(
    tracked: Mapping[str, str], applied: Mapping[str, str]
) -> str:
    """Compare code-owned migration checksums against the DB registry.

    An applied migration the code no longer tracks is "drift" (as dangerous as an
    edited pair); a tracked pair the DB has not applied is "missing"."""
    tracked_ids = set(tracked)
    applied_ids = set(applied)
    if applied_ids - tracked_ids:
        return "drift"
    if tracked_ids - applied_ids:
        return "missing"
    for migration_id in tracked_ids:
        if applied[migration_id] != tracked[migration_id]:
            return "drift"
    return "ok"


def evaluate_release(release) -> str:
    """A shadow-served release must be present, non-commandable, and an
    engineering prior — never a commandable one."""
    if release is None:
        return "missing"
    if getattr(release, "commandable", None) is not False:
        return "commandable"
    if getattr(release, "evidence_class", None) is not EvidenceClass.ENGINEERING_PRIOR:
        return "wrong_evidence"
    return "ok"


def _tracked_flow_migrations() -> dict[str, str]:
    import migrations.migrate as migrate

    return {
        migration_id: migrate.migration_checksum(migration_id)
        for migration_id in migrate.discover_migration_ids()
    }


async def _check_prediction_persistence(pool) -> str:
    """Probe both prediction tables + the migration checksum through the asyncpg
    pool. Never raises: any driver error collapses to "unreachable"."""
    if pool is None:
        return "unreachable"
    try:
        async with pool.acquire() as conn:
            runs = await conn.fetchval(
                f"SELECT to_regclass('{SCHEMA}.prediction_runs')"
            )
            artifacts = await conn.fetchval(
                f"SELECT to_regclass('{SCHEMA}.prediction_artifacts')"
            )
            registry = await conn.fetchval(
                f"SELECT to_regclass('{SCHEMA}.schema_migrations')"
            )
            applied: dict[str, str] = {}
            if registry is not None:
                rows = await conn.fetch(
                    "SELECT migration_id, checksum "
                    f"FROM {SCHEMA}.schema_migrations"
                )
                applied = {r["migration_id"]: r["checksum"] for r in rows}
    except Exception:
        return "unreachable"

    if runs is None or artifacts is None:
        return "not_migrated"
    # Reading the tracked SQL files can raise (missing/unreadable file, incomplete
    # pair): that must fail closed as a safe "error", never a 500 leaking a path.
    try:
        tracked = _tracked_flow_migrations()
    except Exception:
        return "error"
    if not REQUIRED_BASELINE_MIGRATION_IDS.issubset(tracked):
        return "incomplete"
    return evaluate_migrations(tracked, applied)


async def _probe_postgres(db_manager, timeout_seconds: float) -> bool:
    """Ping ONLY PostgreSQL (the sole store that gates flow readiness) under a
    hard wall-clock. A hung InfluxDB/Timescale/Redis is irrelevant here and must
    never block a healthy-PG readiness. Fails closed on timeout/error/missing
    client."""
    postgres = getattr(db_manager, "postgres", None)
    ping = getattr(postgres, "ping", None)
    if ping is None:
        return False
    try:
        async with asyncio.timeout(timeout_seconds):
            return bool(await ping())
    except Exception:
        return False


async def check_flow_readiness(
    app,
    db_manager,
    postgres_probe_timeout_seconds: float = DEFAULT_POSTGRES_PROBE_TIMEOUT_SECONDS,
) -> ReadinessResult:
    """Fail-closed dependency truth for flow-monitoring's `/ready` endpoint."""
    postgres_ok = await _probe_postgres(db_manager, postgres_probe_timeout_seconds)

    release_status = evaluate_release(getattr(app.state, "hydraulic_model_release", None))
    service = getattr(app.state, "control_prediction_service", None)
    service_status = "ok" if service is not None else "uninitialized"

    if postgres_ok:
        pool = getattr(getattr(db_manager, "postgres", None), "pool", None)
        persistence_status = await _check_prediction_persistence(pool)
    else:
        persistence_status = "unreachable"

    checks = {
        "database": "ok" if postgres_ok else "unhealthy",
        "model_release": release_status,
        "prediction_service": service_status,
        "prediction_persistence": persistence_status,
    }
    ready = (
        postgres_ok
        and release_status == "ok"
        and service_status == "ok"
        and persistence_status == "ok"
    )
    return ReadinessResult(ready, checks)
