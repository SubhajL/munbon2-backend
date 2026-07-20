"""Async Prometheus scrape handler for the scheduler control plane (PR 6.4).

Derives bounded aggregates from the durable append-only tables + the worker heartbeat from
Redis, builds the metric families, and renders Prometheus text. FAIL-SAFE: any DB error yields a
``scheduler_metrics_scrape_error=1`` gauge (HTTP 200) so Prometheus records the failure without
dropping the target. On that error path the ``control_*`` COUNTER families are intentionally
OMITTED (not zero-filled): zero-filling a counter mid-history reads as a counter RESET and would
corrupt ``rate()``/``increase()`` far worse than a one-scrape gap — Prometheus rides a transient
gap out via ``for:``/staleness, and ``scheduler_metrics_scrape_error`` says why. Read-only; a
per-scrape ``statement_timeout`` bounds a slow scan so ``/metrics`` can never starve the operator
read pool. Four small grouped queries (control_plan_runs, receipts, observations, pending/lag).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from core.control_metrics import (
    ControlPlaneMetricSnapshot,
    WorkerHeartbeat,
    build_control_plane_metric_families,
    render_metric_families,
    scrape_error_family,
)
from core.logger import get_logger
from core.worker_heartbeat import heartbeat_age_seconds, read_dispatch_heartbeat

logger = get_logger(__name__)

SCHEMA = "scheduler"
_STATEMENT_TIMEOUT_MS = 2000


async def _group_counts(conn, sql: str, params: dict | None = None) -> dict[str, int]:
    rows = (await conn.execute(text(sql), params or {})).fetchall()
    return {row[0]: int(row[1]) for row in rows if row[0] is not None}


async def collect_metric_snapshot(conn, redis, now: datetime) -> ControlPlaneMetricSnapshot:
    """Read the durable tables + the Redis heartbeat into a scrape snapshot. Read-only."""
    # One scan of control_plan_runs feeds BOTH the optimizer-status and prediction-status series.
    plan_runs: dict[str, int] = {}
    prediction_runs: dict[str, int] = {}
    for opt_status, pred_status, count in (
        await conn.execute(
            text(
                f"SELECT optimizer_status, prediction_status, count(*) "
                f"FROM {SCHEMA}.control_plan_runs GROUP BY optimizer_status, prediction_status"
            )
        )
    ).fetchall():
        plan_runs[opt_status] = plan_runs.get(opt_status, 0) + int(count)
        prediction_runs[pred_status] = prediction_runs.get(pred_status, 0) + int(count)

    # One scan of the receipts feeds BOTH the validation-status totals (the rejection-rate
    # denominator) and the per-reason rejection counts.
    validations: dict[str, int] = {}
    rejections: dict[str, int] = {}
    for status, reason_code, count in (
        await conn.execute(
            text(
                f"SELECT status, reason_code, count(*) "
                f"FROM {SCHEMA}.control_command_validation_receipts GROUP BY status, reason_code"
            )
        )
    ).fetchall():
        validations[status] = validations.get(status, 0) + int(count)
        if status == "validation_rejected" and reason_code is not None:
            rejections[reason_code] = rejections.get(reason_code, 0) + int(count)

    readback_mismatch = await _group_counts(
        conn,
        f"SELECT canonical_gate_id, count(*) FROM {SCHEMA}.control_gate_readback_observations "
        "WHERE verdict = 'mismatch' GROUP BY canonical_gate_id",
    )
    # Dispatch pending + lag: outbox intents with a 'claimed' event (0009) and NO receipt (0010),
    # SCOPED to plans that STILL HOLD AUTHORITY (control_active_gate_authority — the dispatcher's
    # own active set via load_active_shadow_plan_keys). A superseded/invalidated plan releases
    # its mutex, so its stuck intents drop out — otherwise a single orphaned intent of a dead
    # plan pins the lag gauge at an ever-growing age forever, permanently firing the lag alert.
    # lag = age of the OLDEST such intent (0 when none).
    pending = (
        await conn.execute(
            text(
                f"""
                SELECT
                    count(*) AS pending,
                    COALESCE(EXTRACT(EPOCH FROM (:now - min(e.occurred_at))), 0) AS lag_seconds
                FROM {SCHEMA}.control_command_outbox o
                JOIN {SCHEMA}.control_command_execution_events e
                    ON e.intent_id = o.intent_id AND e.event_type = 'claimed'
                JOIN {SCHEMA}.control_active_gate_authority a
                    ON a.plan_id = o.plan_id AND a.plan_version = o.plan_version
                WHERE NOT EXISTS (
                    SELECT 1 FROM {SCHEMA}.control_command_validation_receipts r
                    WHERE r.intent_id = o.intent_id
                )
                """
            ),
            {"now": now},
        )
    ).first()
    pending_count = int(pending.pending) if pending else 0
    lag_seconds = max(0.0, float(pending.lag_seconds)) if pending else 0.0

    heartbeat_iso = await read_dispatch_heartbeat(redis)
    heartbeat = WorkerHeartbeat(
        present=heartbeat_iso is not None,
        age_seconds=heartbeat_age_seconds(heartbeat_iso, now),
    )

    return ControlPlaneMetricSnapshot(
        plan_runs_by_optimizer_status=plan_runs,
        prediction_runs_by_status=prediction_runs,
        validations_by_status=validations,
        rejections_by_reason=rejections,
        readback_mismatch_by_gate=readback_mismatch,
        dispatch_pending_count=pending_count,
        dispatch_lag_seconds=lag_seconds,
        worker_heartbeat=heartbeat,
    )


async def render_metrics(engine, redis, *, now: datetime | None = None) -> bytes:
    """Render the scheduler control-plane metrics; fail-safe on any DB error."""
    now = now or datetime.now(timezone.utc)
    try:
        # A transaction so SET LOCAL statement_timeout is scoped to this scrape and reset on
        # commit (never leaked back to the pooled connection). Read-only queries only.
        async with engine.begin() as conn:
            await conn.execute(text(f"SET LOCAL statement_timeout = {_STATEMENT_TIMEOUT_MS}"))
            snapshot = await collect_metric_snapshot(conn, redis, now)
    except Exception as error:  # noqa: BLE001 - a scrape must never 500; report scrape_error
        # Log the exception CLASS (never the message — it can carry host/creds) so the one place
        # a scrape can fail is diagnosable. Counters are omitted (not zero-filled) — see module
        # docstring: zero-filling a counter reads as a reset and corrupts rate().
        logger.error("metrics scrape failed to read the database: {}", type(error).__name__)
        return render_metric_families([scrape_error_family(True)])

    families = build_control_plane_metric_families(snapshot)
    families.append(scrape_error_family(False))
    return render_metric_families(families)
