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
from typing import Mapping

from sqlalchemy import text

# The control-plane tables are migration-owned (ControlBase, never create_all).
# Readiness proves all six exist before claiming the plane is serviceable.
# ``control_plan_campaign_versions`` (0006) is the source of truth for campaign
# identity: without it every draft read fails closed on a missing mapping, so a
# deployment that lost the mapping table must not report ready.
EXPECTED_CONTROL_TABLES: tuple[str, ...] = (
    "control_plan_runs",
    "control_plan_requirements",
    "gate_plan_events",
    "control_state_transitions",
    "section_delivery_ledger",
    "control_plan_campaign_versions",
)

CONTROL_SCHEMA = "scheduler"

# The tracked migration manifest MUST contain at least these baseline pairs. An
# empty or partial migration package (SQL files omitted from a deployment) would
# otherwise let readiness compare empty==empty and pass — so a missing baseline id
# fails closed, never "ok".
REQUIRED_BASELINE_MIGRATION_IDS: frozenset[str] = frozenset(
    {
        "0001_control_plan_drafts",
        "0002_predicted_delivery_ledger",
        "0003_control_plan_review_lifecycle",
        "0006_control_plan_campaign_identity",
    }
)


@dataclass(frozen=True)
class ReadinessResult:
    """A fail-closed readiness verdict plus per-dependency safe status strings."""

    ready: bool
    checks: dict[str, str]


def evaluate_migrations(
    tracked: Mapping[str, str], applied: Mapping[str, str]
) -> str:
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
        + [f"to_regclass('{CONTROL_SCHEMA}.{table}')" for table in EXPECTED_CONTROL_TABLES]
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


async def _ping_redis(redis) -> bool:
    client = getattr(redis, "client", None)
    if client is None:
        return False
    try:
        return bool(await client.ping())
    except Exception:
        # A raw redis exception can carry host/port — swallow it, report a bool.
        return False


async def check_scheduler_readiness(engine, redis) -> ReadinessResult:
    """Fail-closed dependency truth for the scheduler `/ready` endpoint."""
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
    return ReadinessResult(ready, checks)
