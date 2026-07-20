"""Unit tests for the pure control-plane metric builders (PR 6.4-sched)."""

from __future__ import annotations

from core.control_metrics import (
    OPTIMIZER_STATUSES,
    PREDICTION_STATUSES,
    REJECTION_REASONS,
    VALIDATION_STATUSES,
    ControlPlaneMetricSnapshot,
    WorkerHeartbeat,
    build_control_plane_metric_families,
    render_metric_families,
    scrape_error_family,
)


def _render(snapshot: ControlPlaneMetricSnapshot) -> str:
    return render_metric_families(build_control_plane_metric_families(snapshot)).decode()


def _series_value(body: str, series: str) -> float | None:
    for line in body.splitlines():
        if line.startswith(series + " "):
            return float(line[len(series) + 1 :])
    return None


def test_empty_snapshot_pre_registers_every_enum_series_at_zero():
    body = _render(ControlPlaneMetricSnapshot())
    for status in OPTIMIZER_STATUSES:
        assert _series_value(body, f'control_plan_runs_total{{status="{status}"}}') == 0.0
    for status in PREDICTION_STATUSES:
        assert _series_value(body, f'control_prediction_runs_total{{status="{status}"}}') == 0.0
    for status in VALIDATION_STATUSES:
        assert _series_value(body, f'control_intent_validations_total{{status="{status}"}}') == 0.0
    for reason in REJECTION_REASONS:
        assert (
            _series_value(body, f'command_intent_rejections_total{{reason="{reason}"}}') == 0.0
        )


def test_counts_are_reflected_per_bounded_label():
    snapshot = ControlPlaneMetricSnapshot(
        plan_runs_by_optimizer_status={"feasible": 7, "infeasible": 2},
        prediction_runs_by_status={"completed": 5, "infeasible": 1, "not_requested": 3},
        validations_by_status={"validation_accepted": 4, "validation_rejected": 6},
        rejections_by_reason={"freshness_failed": 4, "deadline_expired": 2},
    )
    body = _render(snapshot)
    assert _series_value(body, 'control_plan_runs_total{status="feasible"}') == 7.0
    assert _series_value(body, 'control_plan_runs_total{status="infeasible"}') == 2.0
    assert _series_value(body, 'control_prediction_runs_total{status="not_requested"}') == 3.0
    assert _series_value(body, 'control_intent_validations_total{status="validation_rejected"}') == 6.0
    assert _series_value(body, 'command_intent_rejections_total{reason="freshness_failed"}') == 4.0
    assert _series_value(body, 'command_intent_rejections_total{reason="deadline_expired"}') == 2.0
    # a reason that did not occur is still present, at 0 (present, not absent).
    assert _series_value(body, 'command_intent_rejections_total{reason="lineage_mismatch"}') == 0.0


def test_enum_labels_are_bounded_to_the_known_vocab():
    # Feed a value OUTSIDE the vocab; it must NOT appear as a series (cardinality guard).
    snapshot = ControlPlaneMetricSnapshot(
        rejections_by_reason={"totally_unknown_reason": 99, "freshness_failed": 1},
    )
    body = _render(snapshot)
    assert "totally_unknown_reason" not in body
    rejection_series = [
        line for line in body.splitlines() if line.startswith("command_intent_rejections_total{")
    ]
    # Exactly one series per known reason, no more.
    assert len(rejection_series) == len(REJECTION_REASONS)


def test_readback_mismatch_is_emitted_per_gate_only_when_present():
    empty = _render(ControlPlaneMetricSnapshot())
    assert "gate_readback_mismatch_total{" not in empty
    body = _render(
        ControlPlaneMetricSnapshot(readback_mismatch_by_gate={"M(0,0;1,0)": 3})
    )
    assert _series_value(body, 'gate_readback_mismatch_total{gate="M(0,0;1,0)"}') == 3.0


def test_dispatch_lag_and_pending_gauges():
    body = _render(
        ControlPlaneMetricSnapshot(dispatch_pending_count=2, dispatch_lag_seconds=45.5)
    )
    assert _series_value(body, "command_intent_lag_seconds") == 45.5
    assert _series_value(body, "command_intent_dispatch_pending") == 2.0


def test_worker_heartbeat_present_and_age():
    dead = _render(
        ControlPlaneMetricSnapshot(worker_heartbeat=WorkerHeartbeat(present=False, age_seconds=None))
    )
    assert (
        _series_value(dead, 'scheduler_dispatch_worker_heartbeat_present{worker="shadow_dispatch"}')
        == 0.0
    )
    # No age series when there is no heartbeat.
    assert "scheduler_dispatch_worker_heartbeat_age_seconds{" not in dead

    alive = _render(
        ControlPlaneMetricSnapshot(worker_heartbeat=WorkerHeartbeat(present=True, age_seconds=12.0))
    )
    assert (
        _series_value(alive, 'scheduler_dispatch_worker_heartbeat_present{worker="shadow_dispatch"}')
        == 1.0
    )
    assert (
        _series_value(
            alive, 'scheduler_dispatch_worker_heartbeat_age_seconds{worker="shadow_dispatch"}'
        )
        == 12.0
    )


def test_scrape_error_family_renders_zero_or_one():
    ok = render_metric_families([scrape_error_family(False)]).decode()
    err = render_metric_families([scrape_error_family(True)]).decode()
    assert _series_value(ok, "scheduler_metrics_scrape_error") == 0.0
    assert _series_value(err, "scheduler_metrics_scrape_error") == 1.0
