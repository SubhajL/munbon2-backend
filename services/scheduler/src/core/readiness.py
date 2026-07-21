"""Dependency-truth readiness for the scheduler control plane (PR 4.4a-2).

`/health` is process liveness only; `/ready` calls `check_scheduler_readiness`,
which is ready ONLY when:
  * every tracked migration id + checksum matches `scheduler.schema_migrations`,
  * all six control tables exist (`to_regclass`), and
  * the Redis revocation store answers a ping.

Everything fails closed: a missing/extra/drifted migration, an empty/partial
migration manifest, an unreadable migration file, a missing table, an unreachable
database, or an unreachable Redis all make the service NOT ready. The returned
``checks`` only ever hold safe status strings ("ok" / "missing" / "incomplete" /
"drift" / "error" / "unreachable") — never a hostname, credential, or raw
exception text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

from sqlalchemy import text

from core.worker_heartbeat import heartbeat_age_seconds, read_dispatch_heartbeat

# The control-plane tables are migration-owned (ControlBase, never create_all).
# Readiness proves EVERY migration-owned table exists before claiming the plane
# is serviceable — including the 0007-0012 execution/receipt/readback/authority
# ledgers (PR 7.1a closes the gap where a dropped execution table could leave
# /ready green while dispatch, metrics, readback, or authority reads fail).
EXPECTED_CONTROL_TABLES: tuple[str, ...] = (
    "control_plan_runs",
    "control_plan_requirements",
    "gate_plan_events",
    "control_state_transitions",
    "section_delivery_ledger",
    "control_plan_campaign_versions",
    "control_command_outbox",
    "control_active_gate_authority",
    "control_command_execution_events",
    "control_command_validation_receipts",
    "control_gate_readback_observations",
    "control_authority_grants",
    "control_authority_grant_events",
)

CONTROL_SCHEMA = "scheduler"

# The tracked migration manifest MUST contain EVERY applied pair. An empty or
# partial migration package (SQL files omitted from a deployment) would
# otherwise let readiness compare empty==empty and pass — so a missing id fails
# closed, never "ok". A partially packaged execution ledger must not be ready.
REQUIRED_BASELINE_MIGRATION_IDS: frozenset[str] = frozenset(
    {
        "0001_control_plan_drafts",
        "0002_predicted_delivery_ledger",
        "0003_control_plan_review_lifecycle",
        "0004_control_plan_list_indexes",
        "0005_control_plan_provenance_v2",
        "0006_control_plan_campaign_identity",
        "0007_control_plan_shadow_activation",
        "0008_control_plan_active_supersede",
        "0009_open_loop_execution",
        "0010_shadow_dispatch_receipts",
        "0011_gate_readback_observations",
        "0012_authority_grants",
    }
)


@dataclass(frozen=True)
class ReadinessResult:
    """A fail-closed readiness verdict plus per-dependency safe status strings."""

    ready: bool
    checks: dict[str, str]


def evaluate_migrations(tracked: Mapping[str, str], applied: Mapping[str, str]) -> str:
    """Compare tracked (code-owned) migration checksums against what the DB has.

    "drift" also covers an APPLIED migration the code no longer tracks — an
    unknown migration in the registry is as dangerous as an edited one."""
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


def evaluate_control_tables(present: Mapping[str, bool]) -> str:
    if all(present.get(table) for table in EXPECTED_CONTROL_TABLES):
        return "ok"
    return "missing"


def _tracked_scheduler_migrations() -> dict[str, str]:
    # Imported lazily so importing this module never depends on the migrations
    # package being importable (it is at service-root, not under src/).
    import migrations.migrate as migrate

    return {
        migration_id: migrate.migration_checksum(migration_id)
        for migration_id in migrate.discover_migration_ids()
    }


def _evaluate_tracked_migrations_status(
    registry_present: bool, applied: Mapping[str, str]
) -> str:
    """Fail-closed verdict for the migration dependency, computed inside a guard.

    Reading the tracked SQL files can raise (a missing/unreadable file, an
    incomplete pair): that must become a safe not-ready "error" — never an HTTP
    500 that leaks a file path. A tracked manifest missing a baseline id is
    "incomplete" (an empty/partial deployment package). Only a present registry
    with a matching, complete manifest can be "ok"."""
    try:
        tracked = _tracked_scheduler_migrations()
    except Exception:
        return "error"
    if not REQUIRED_BASELINE_MIGRATION_IDS.issubset(tracked):
        return "incomplete"
    if not registry_present:
        return "missing"
    return evaluate_migrations(tracked, applied)


async def _read_scheduler_db_state(engine):
    """One connection, two reads: the regclass of the registry + six control
    tables, then the applied migration id/checksum rows (only if the registry
    exists). Returns (registry_present, present_by_table, applied_by_id)."""
    regclass_columns = ", ".join(
        [f"to_regclass('{CONTROL_SCHEMA}.schema_migrations')"]
        + [
            f"to_regclass('{CONTROL_SCHEMA}.{table}')"
            for table in EXPECTED_CONTROL_TABLES
        ]
    )
    async with engine.connect() as conn:
        row = (await conn.execute(text(f"SELECT {regclass_columns}"))).first()
        registry_present = row[0] is not None
        present = {
            table: row[index + 1] is not None
            for index, table in enumerate(EXPECTED_CONTROL_TABLES)
        }
        applied: dict[str, str] = {}
        if registry_present:
            rows = (
                await conn.execute(
                    text(
                        "SELECT migration_id, checksum "
                        f"FROM {CONTROL_SCHEMA}.schema_migrations"
                    )
                )
            ).fetchall()
            applied = {r[0]: r[1] for r in rows}
    return registry_present, present, applied


def evaluate_worker_health(
    armed: bool, heartbeat_iso: str | None, now: datetime, threshold_seconds: int
) -> str:
    """Fail-closed verdict for the shadow-dispatch worker's liveness (PR 6.4).

    DARK-by-default: when not armed the worker is not a readiness dependency at all (returns
    "disabled" and never blocks). When armed (execution mode shadow + a SCADA base URL, i.e. the
    tick is EXPECTED to run), a missing/unparseable/stale heartbeat fails closed — but note the
    caller only lets this block `/ready` when armed, so a dead worker in dark deployments can
    never black out the read-only dashboard that operators need to SEE that dispatch is stuck.
    """
    if not armed:
        return "disabled"
    if heartbeat_iso is None:
        return "missing"
    age = heartbeat_age_seconds(heartbeat_iso, now)
    if age is None:
        return "error"  # present but unparseable/naive → do not trust it
    return "ok" if age <= threshold_seconds else "stale"


async def _ping_redis(redis) -> bool:
    client = getattr(redis, "client", None)
    if client is None:
        return False
    try:
        return bool(await client.ping())
    except Exception:
        # A raw redis exception can carry host/port — swallow it, report a bool.
        return False


async def check_scheduler_readiness(
    engine,
    redis,
    *,
    worker_armed: bool | None = None,
    heartbeat_stale_seconds: int | None = None,
    worker_health_gates_readiness: bool | None = None,
    now: datetime | None = None,
) -> ReadinessResult:
    """Fail-closed dependency truth for the scheduler `/ready` endpoint.

    `/ready` answers "can this replica serve reads" — migrations match + control tables exist +
    Redis pings. Worker-health is DARK-by-default and BLAST-RADIUS-ISOLATED: read ONLY when armed
    (the dispatcher's real dark-gate — shadow mode + SCADA base URL + service secret), REPORTED in
    `checks` for visibility/alerting, but it flips the LB-facing `ready` bool ONLY when
    `worker_health_gates_readiness` is explicitly enabled. By default a dead out-of-process
    dispatch tick can never make a healthy read-serving replica not-ready — otherwise it would
    black out the very read-only dashboard operators need to SEE that dispatch is stuck. The
    primary worker-health signal is the Prometheus heartbeat gauge, not `/ready`."""
    try:
        registry_present, present, applied = await _read_scheduler_db_state(engine)
    except Exception:
        # Never surface the driver's exception (it can contain host/credentials).
        return ReadinessResult(False, {"database": "unreachable"})

    migrations_status = _evaluate_tracked_migrations_status(registry_present, applied)
    tables_status = evaluate_control_tables(present)
    redis_ok = await _ping_redis(redis)

    checks = {
        "migrations": migrations_status,
        "control_tables": tables_status,
        "redis": "ok" if redis_ok else "unreachable",
    }
    ready = migrations_status == "ok" and tables_status == "ok" and redis_ok

    if (
        worker_armed is None
        or heartbeat_stale_seconds is None
        or worker_health_gates_readiness is None
    ):
        from core.config import settings

        if worker_armed is None:
            # Mirror the dispatcher's dark-gate EXACTLY (build_scada_validation_client): base URL
            # alone is not "armed" — without the service secret nothing can be dispatched.
            worker_armed = (
                settings.control_execution_mode == "shadow"
                and bool(settings.scheduler_scada_base_url)
                and bool(settings.scheduler_service_jwt_secret)
            )
        if heartbeat_stale_seconds is None:
            heartbeat_stale_seconds = settings.control_worker_heartbeat_stale_seconds
        if worker_health_gates_readiness is None:
            worker_health_gates_readiness = (
                settings.control_worker_health_gates_readiness
            )

    if worker_armed:
        heartbeat_iso = await read_dispatch_heartbeat(redis)
        worker_status = evaluate_worker_health(
            True,
            heartbeat_iso,
            now or datetime.now(timezone.utc),
            heartbeat_stale_seconds,
        )
        checks["dispatch_worker"] = worker_status
        if worker_health_gates_readiness:
            ready = ready and worker_status == "ok"

    return ReadinessResult(ready, checks)
