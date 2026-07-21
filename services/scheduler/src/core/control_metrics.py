"""Pure builders for the scheduler control-plane Prometheus metrics (PR 6.4).

Metrics are DERIVED FROM THE DURABLE APPEND-ONLY TABLES at scrape time, never from
in-process counters: the shadow-dispatch/reconcile tick is a separate short-lived process
(``jobs.shadow_dispatch_once``), so a counter it incremented would never be scraped. Counting
over append-only tables is monotonic (COUNT only grows), so counter semantics are honest, and
every uvicorn worker reads the same DB — no ``prometheus_client`` multiprocess mode needed.

This module is PURE (no I/O): it takes a snapshot of pre-aggregated counts and emits
``prometheus_client`` metric families with the FULL bounded-enum cross-product pre-set to 0.
That zero-fill is the cardinality guarantee — a GROUP BY only emits series for values that
occurred, which would leave ``== 0`` alerts comparing against an absent series on a fresh
deploy. Only closed enum vocabularies are used as labels; never a raw id, free-text quality,
or free-text reason (those would be unbounded).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence, get_args

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, Metric

from core.authority_grant import EVENT_TYPES as AUTHORITY_GRANT_EVENT_TYPES
from core.worker_heartbeat import DISPATCH_WORKER_NAME
from schemas.machine_boundary import ValidationRejectionReason, ValidationStatus
from schemas.machine_execution import ExecutionStatus

METRICS_CONTENT_TYPE = CONTENT_TYPE_LATEST

# --- Bounded label vocabularies (single source of truth; locked by tests) -------------------
# optimizer/prediction statuses mirror schemas/control_plan.py's persisted Literal columns.
OPTIMIZER_STATUSES: tuple[str, ...] = ("feasible", "infeasible")
PREDICTION_STATUSES: tuple[str, ...] = ("not_requested", "completed", "infeasible")
# validation status + rejection reasons come straight from the machine-boundary Literals, so
# they can never drift from the receipt contract the 0010 CHECK also mirrors.
VALIDATION_STATUSES: tuple[str, ...] = tuple(get_args(ValidationStatus))
REJECTION_REASONS: tuple[str, ...] = tuple(get_args(ValidationRejectionReason))
EXECUTION_STATUSES: tuple[str, ...] = tuple(get_args(ExecutionStatus))

# Single source of truth for the worker label (shared with the heartbeat producer/reader).
DISPATCH_WORKER_LABEL = DISPATCH_WORKER_NAME


@dataclass(frozen=True)
class WorkerHeartbeat:
    """Heartbeat view for the metrics gauge. ``age_seconds`` is None when the key is absent."""

    present: bool
    age_seconds: float | None


@dataclass(frozen=True)
class ControlPlaneMetricSnapshot:
    """Pre-aggregated counts + gauges read from the durable tables at scrape time."""

    plan_runs_by_optimizer_status: Mapping[str, int] = field(default_factory=dict)
    prediction_runs_by_status: Mapping[str, int] = field(default_factory=dict)
    validations_by_status: Mapping[str, int] = field(default_factory=dict)
    rejections_by_reason: Mapping[str, int] = field(default_factory=dict)
    readback_mismatch_by_gate: Mapping[str, int] = field(default_factory=dict)
    authority_grant_events_by_type: Mapping[str, int] = field(default_factory=dict)
    execution_receipts_by_status: Mapping[str, int] = field(default_factory=dict)
    dispatch_pending_count: int = 0
    dispatch_lag_seconds: float = 0.0
    worker_heartbeat: WorkerHeartbeat = WorkerHeartbeat(present=False, age_seconds=None)


def _counter_over_vocab(
    name: str,
    help_text: str,
    label: str,
    vocab: Sequence[str],
    counts: Mapping[str, int],
) -> CounterMetricFamily:
    """A counter with one series PER vocab value, zero-filled — the cardinality guarantee."""
    family = CounterMetricFamily(name, help_text, labels=[label])
    for value in vocab:
        family.add_metric([value], float(counts.get(value, 0)))
    return family


def build_control_plane_metric_families(
    snapshot: ControlPlaneMetricSnapshot,
) -> list[Metric]:
    """Emit the scheduler control-plane metric families from a scrape snapshot. PURE."""
    families: list[Metric] = [
        _counter_over_vocab(
            "control_plan_runs_total",
            "Control plan drafts created, by optimizer feasibility status.",
            "status",
            OPTIMIZER_STATUSES,
            snapshot.plan_runs_by_optimizer_status,
        ),
        _counter_over_vocab(
            "control_prediction_runs_total",
            "Control plan prediction runs, by prediction status.",
            "status",
            PREDICTION_STATUSES,
            snapshot.prediction_runs_by_status,
        ),
        _counter_over_vocab(
            "control_intent_validations_total",
            "Command-intent validation receipts (the rejection-rate denominator), by status.",
            "status",
            VALIDATION_STATUSES,
            snapshot.validations_by_status,
        ),
        _counter_over_vocab(
            "command_intent_rejections_total",
            "Command-intent validation rejections observed via durable receipts, by reason. "
            "schema_invalid is 0 here (it mints no receipt) — SCADA counts that one.",
            "reason",
            REJECTION_REASONS,
            snapshot.rejections_by_reason,
        ),
        _counter_over_vocab(
            "control_authority_grant_events_total",
            "Execution-authority grant lifecycle events (PR 7.1a), by event type. "
            "OBSERVATIONAL ONLY — authority status comes solely from the pure "
            "ledger fold, never from these counters.",
            "event_type",
            AUTHORITY_GRANT_EVENT_TYPES,
            snapshot.authority_grant_events_by_type,
        ),
        _counter_over_vocab(
            "control_command_executions_total",
            "Durable operator-approved machine execution receipts, by terminal status.",
            "status",
            EXECUTION_STATUSES,
            snapshot.execution_receipts_by_status,
        ),
    ]

    # gate_readback_mismatch_total{gate}: the ONLY data-driven label. Cardinality is bounded by
    # the write path — observations exist only for approved-registry (D6-gated) baseline gates,
    # never arbitrary payloads — so no cross-product is possible or needed.
    mismatch = CounterMetricFamily(
        "gate_readback_mismatch_total",
        "Readback observations whose verdict is mismatch (drift vs the plan baseline), by gate.",
        labels=["gate"],
    )
    for gate, count in sorted(snapshot.readback_mismatch_by_gate.items()):
        mismatch.add_metric([gate], float(count))
    families.append(mismatch)

    # Dispatch lag/pending: a gauge, not a histogram — a histogram is unfillable across the
    # tick-process boundary. pending_count separates "idle" (0 pending) from "backed up".
    families.append(
        GaugeMetricFamily(
            "command_intent_lag_seconds",
            "Age of the oldest claimed-but-unreceipted command intent; 0 when none pending.",
            value=float(snapshot.dispatch_lag_seconds),
        )
    )
    families.append(
        GaugeMetricFamily(
            "command_intent_dispatch_pending",
            "Claimed-but-unreceipted command intents on active plans (0 = nothing to dispatch).",
            value=float(snapshot.dispatch_pending_count),
        )
    )

    # Worker liveness: present separates "idle" (present=1, no pending) from "dead" (present=0).
    present = GaugeMetricFamily(
        "scheduler_dispatch_worker_heartbeat_present",
        "1 if a fresh shadow-dispatch worker heartbeat exists in Redis, else 0.",
        labels=["worker"],
    )
    present.add_metric(
        [DISPATCH_WORKER_LABEL], 1.0 if snapshot.worker_heartbeat.present else 0.0
    )
    families.append(present)

    if snapshot.worker_heartbeat.age_seconds is not None:
        age = GaugeMetricFamily(
            "scheduler_dispatch_worker_heartbeat_age_seconds",
            "Seconds since the last shadow-dispatch worker heartbeat (absent when no heartbeat).",
            labels=["worker"],
        )
        age.add_metric(
            [DISPATCH_WORKER_LABEL], float(snapshot.worker_heartbeat.age_seconds)
        )
        families.append(age)

    return families


def scrape_error_family(errored: bool) -> Metric:
    """A 0/1 gauge so a failed scrape is visible to Prometheus without dropping the target."""
    return GaugeMetricFamily(
        "scheduler_metrics_scrape_error",
        "1 if the last /metrics scrape failed to read the database, else 0.",
        value=1.0 if errored else 0.0,
    )


class _FamilyCollector:
    """A one-shot collector yielding pre-built families — a fresh registry per scrape means no
    cross-scrape state and no multiprocess coordination."""

    def __init__(self, families: Sequence[Metric]) -> None:
        self._families = families

    def collect(self):
        return iter(self._families)


def render_metric_families(families: Sequence[Metric]) -> bytes:
    """Render metric families to the Prometheus text exposition format."""
    registry = CollectorRegistry()
    registry.register(_FamilyCollector(families))
    return generate_latest(registry)
