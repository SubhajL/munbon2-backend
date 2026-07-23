from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from typing import Any, cast

import pytest

import algorithms.hydraulic_schedule_optimizer as optimizer_module
from algorithms.hydraulic_schedule_optimizer import (
    DeliveryObligation,
    GateEventKind,
    GatePlanEvent,
    GatePulseDuty,
    HydraulicScheduleError,
    LimitedAdjustmentProblem,
    ModelOperatingEnvelope,
    PlanStatus,
    QuantizedFlowCandidate,
    ReachCapacity,
    TimeWindow,
    optimize_limited_adjustment_plan,
    verify_adjustment_budget,
)

UTC = timezone.utc
MODEL_SNAPSHOT_ID = "a" * 64
STEP_SECONDS = 3_600
HORIZON_START = datetime(2026, 7, 16, tzinfo=UTC)
HORIZON_END = HORIZON_START + timedelta(days=3)
PATH_REACH = "C_S_M(0,0)"


def test_cbc_solver_prefers_the_native_system_binary(monkeypatch) -> None:
    calls = []

    def coin_cmd(**kwargs):
        calls.append(kwargs)
        return "native-cbc"

    monkeypatch.setattr(optimizer_module.shutil, "which", lambda name: "/usr/bin/cbc")
    monkeypatch.setattr(optimizer_module.pulp, "COIN_CMD", coin_cmd)

    solver = optimizer_module._cbc_solver(
        remaining_seconds=15.0,
        warm_start=True,
    )

    assert solver == "native-cbc"
    assert calls == [
        {
            "path": "/usr/bin/cbc",
            "msg": False,
            "threads": 1,
            "timeLimit": 15.0,
            "warmStart": True,
        }
    ]


def test_cbc_solver_falls_back_to_the_bundled_binary(monkeypatch) -> None:
    calls = []

    def pulp_cbc_cmd(**kwargs):
        calls.append(kwargs)
        return "bundled-cbc"

    monkeypatch.setattr(optimizer_module.shutil, "which", lambda name: None)
    monkeypatch.setattr(optimizer_module.pulp, "PULP_CBC_CMD", pulp_cbc_cmd)

    solver = optimizer_module._cbc_solver(
        remaining_seconds=15.0,
        warm_start=False,
    )

    assert solver == "bundled-cbc"
    assert calls == [
        {
            "msg": False,
            "threads": 1,
            "timeLimit": 15.0,
            "warmStart": False,
        }
    ]


def _window(start_hour: int, duration_hours: int) -> TimeWindow:
    starts_at = HORIZON_START + timedelta(hours=start_hour)
    return TimeWindow(starts_at, starts_at + timedelta(hours=duration_hours))


def _obligation(
    requirement_id: str,
    *,
    gate_id: str = "GATE-1",
    required_volume_m3: float,
    window: TimeWindow,
    path_reach_ids: tuple[str, ...] = (PATH_REACH,),
    travel_delay_seconds: int = 0,
    minimum_delivery_fraction: float = 1.0,
    maximum_delivery_fraction: float = 1.0,
    maximum_excess_volume_m3: float = 0.0,
) -> DeliveryObligation:
    return DeliveryObligation(
        requirement_id=requirement_id,
        service_date=date(2026, 7, 16),
        section_id=f"SECTION-{requirement_id}",
        gate_id=gate_id,
        required_volume_m3=required_volume_m3,
        maximum_excess_volume_m3=maximum_excess_volume_m3,
        delivery_window=window,
        rotation_windows=(window,),
        path_reach_ids=path_reach_ids,
        travel_delay_seconds=travel_delay_seconds,
        minimum_delivery_fraction=minimum_delivery_fraction,
        maximum_delivery_fraction=maximum_delivery_fraction,
    )


def _problem(
    obligations: tuple[DeliveryObligation, ...],
    candidates: tuple[QuantizedFlowCandidate, ...],
    *,
    capacities: tuple[ReachCapacity, ...] = (ReachCapacity(PATH_REACH, 10.0),),
    duties: tuple[GatePulseDuty, ...] = (
        GatePulseDuty("GATE-1", STEP_SECONDS, 36 * STEP_SECONDS),
    ),
) -> LimitedAdjustmentProblem:
    return LimitedAdjustmentProblem(
        model_snapshot_id=MODEL_SNAPSHOT_ID,
        operating_envelope=ModelOperatingEnvelope(
            minimum_flow_m3s=0.0,
            maximum_flow_m3s=10.0,
            minimum_timestep_seconds=300.0,
            maximum_timestep_seconds=STEP_SECONDS,
            maximum_horizon_seconds=10 * 24 * STEP_SECONDS,
        ),
        horizon_start=HORIZON_START,
        horizon_end=HORIZON_END,
        obligations=obligations,
        flow_candidates=candidates,
        reach_capacities=capacities,
        pulse_duties=duties,
    )


def test_same_opening_across_midnight_has_zero_trims() -> None:
    arrival_window = _window(1, 40)
    problem = _problem(
        (
            _obligation(
                "REQ-30H",
                required_volume_m3=30 * STEP_SECONDS,
                window=arrival_window,
                travel_delay_seconds=STEP_SECONDS,
            ),
        ),
        (QuantizedFlowCandidate("GATE-1", 0.5, 1.0),),
    )

    result = optimize_limited_adjustment_plan(
        problem,
        model_step_seconds=STEP_SECONDS,
    )

    assert result.status is PlanStatus.FEASIBLE
    assert result.objective is not None
    assert result.objective.intermediate_trims == 0
    assert result.events == (
        GatePlanEvent("GATE-1", GateEventKind.OPEN, HORIZON_START, 0.5),
        GatePlanEvent(
            "GATE-1",
            GateEventKind.CLOSE,
            HORIZON_START + timedelta(hours=30),
            0.0,
        ),
    )


def test_optimizer_runs_at_the_configured_five_minute_model_step() -> None:
    window = _window(0, 1)
    problem = _problem(
        (
            _obligation(
                "REQ-FIVE-MINUTE",
                required_volume_m3=STEP_SECONDS,
                window=window,
            ),
        ),
        (QuantizedFlowCandidate("GATE-1", 0.5, 1.0),),
    )

    result = optimize_limited_adjustment_plan(problem)

    assert result.status is PlanStatus.FEASIBLE
    assert result.model_step_seconds == 300
    assert result.events[-1].planned_at == HORIZON_START + timedelta(hours=1)


def test_optimizer_builds_one_planned_trim_from_quantized_candidates() -> None:
    window = _window(0, 2)
    problem = _problem(
        (
            _obligation(
                "REQ-TRIM",
                required_volume_m3=3 * STEP_SECONDS,
                window=window,
            ),
        ),
        (
            QuantizedFlowCandidate("GATE-1", 0.5, 1.0),
            QuantizedFlowCandidate("GATE-1", 1.0, 2.0),
        ),
    )

    result = optimize_limited_adjustment_plan(
        problem,
        model_step_seconds=STEP_SECONDS,
    )

    assert result.status is PlanStatus.FEASIBLE
    assert result.objective is not None
    assert result.objective.intermediate_trims == 1
    assert tuple(event.kind for event in result.events) == (
        GateEventKind.OPEN,
        GateEventKind.TRIM,
        GateEventKind.CLOSE,
    )


def test_optimizer_prefers_zero_trims_when_feasible() -> None:
    window = _window(0, 2)
    problem = _problem(
        (
            _obligation(
                "REQ-ZERO-TRIM",
                required_volume_m3=2 * STEP_SECONDS,
                window=window,
            ),
        ),
        (
            QuantizedFlowCandidate("GATE-1", 0.25, 0.5),
            QuantizedFlowCandidate("GATE-1", 0.5, 1.0),
            QuantizedFlowCandidate("GATE-1", 0.75, 1.5),
        ),
    )

    result = optimize_limited_adjustment_plan(
        problem,
        model_step_seconds=STEP_SECONDS,
    )

    assert result.status is PlanStatus.FEASIBLE
    assert result.objective is not None
    assert result.objective.intermediate_trims == 0
    assert result.events == (
        GatePlanEvent("GATE-1", GateEventKind.OPEN, HORIZON_START, 0.5),
        GatePlanEvent(
            "GATE-1",
            GateEventKind.CLOSE,
            HORIZON_START + timedelta(hours=2),
            0.0,
        ),
    )


def test_optimizer_reports_infeasible_when_gate_needs_three_trims() -> None:
    obligations = tuple(
        _obligation(
            f"REQ-{index}",
            required_volume_m3=flow_m3s * STEP_SECONDS,
            window=_window(index, 1),
        )
        for index, flow_m3s in enumerate((1.0, 2.0, 1.0, 2.0))
    )
    problem = _problem(
        obligations,
        (
            QuantizedFlowCandidate("GATE-1", 0.5, 1.0),
            QuantizedFlowCandidate("GATE-1", 1.0, 2.0),
        ),
        duties=(GatePulseDuty("GATE-1", 4 * STEP_SECONDS, 4 * STEP_SECONDS),),
    )

    result = optimize_limited_adjustment_plan(
        problem,
        model_step_seconds=STEP_SECONDS,
        max_intermediate_trims=2,
    )

    assert result.status is PlanStatus.INFEASIBLE
    assert result.events == ()
    assert result.infeasible_reasons == (
        "no gate timeline satisfies volume, timing, capacity, pulse-duty, and adjustment constraints",
    )


def test_optimizer_allows_two_trims_only_when_policy_explicitly_allows_two() -> None:
    obligations = tuple(
        _obligation(
            f"REQ-TWO-{index}",
            required_volume_m3=flow_m3s * STEP_SECONDS,
            window=_window(index, 1),
        )
        for index, flow_m3s in enumerate((1.0, 2.0, 1.0))
    )
    problem = _problem(
        obligations,
        (
            QuantizedFlowCandidate("GATE-1", 0.5, 1.0),
            QuantizedFlowCandidate("GATE-1", 1.0, 2.0),
        ),
        duties=(GatePulseDuty("GATE-1", 3 * STEP_SECONDS, 3 * STEP_SECONDS),),
    )

    result = optimize_limited_adjustment_plan(
        problem,
        model_step_seconds=STEP_SECONDS,
        max_intermediate_trims=2,
    )

    assert result.status is PlanStatus.FEASIBLE
    assert result.objective is not None
    assert result.objective.intermediate_trims == 2


def test_optimizer_reports_shared_upstream_capacity_conflict() -> None:
    shared_reach = "C_SHARED"
    window = _window(0, 1)
    obligations = (
        _obligation(
            "REQ-A",
            gate_id="GATE-A",
            required_volume_m3=STEP_SECONDS,
            window=window,
            path_reach_ids=(shared_reach, "C_A"),
        ),
        _obligation(
            "REQ-B",
            gate_id="GATE-B",
            required_volume_m3=STEP_SECONDS,
            window=window,
            path_reach_ids=(shared_reach, "C_B"),
        ),
    )
    problem = _problem(
        obligations,
        (
            QuantizedFlowCandidate("GATE-A", 0.5, 1.0),
            QuantizedFlowCandidate("GATE-B", 0.5, 1.0),
        ),
        capacities=(
            ReachCapacity(shared_reach, 1.5),
            ReachCapacity("C_A", 1.0),
            ReachCapacity("C_B", 1.0),
        ),
        duties=(
            GatePulseDuty("GATE-A", STEP_SECONDS, STEP_SECONDS),
            GatePulseDuty("GATE-B", STEP_SECONDS, STEP_SECONDS),
        ),
    )

    result = optimize_limited_adjustment_plan(
        problem,
        model_step_seconds=STEP_SECONDS,
    )

    assert result.status is PlanStatus.INFEASIBLE
    assert result.events == ()


def test_optimizer_uses_lower_delivery_fraction_for_required_volume() -> None:
    window = _window(0, 2)
    problem = _problem(
        (
            _obligation(
                "REQ-LOSS",
                required_volume_m3=STEP_SECONDS,
                maximum_excess_volume_m3=STEP_SECONDS,
                window=window,
                minimum_delivery_fraction=0.5,
                maximum_delivery_fraction=1.0,
            ),
        ),
        (QuantizedFlowCandidate("GATE-1", 0.5, 1.0),),
    )

    result = optimize_limited_adjustment_plan(
        problem,
        model_step_seconds=STEP_SECONDS,
    )

    assert result.status is PlanStatus.FEASIBLE
    assert sum(item.lower_volume_m3 for item in result.allocations) == STEP_SECONDS
    assert sum(item.upper_volume_m3 for item in result.allocations) == 2 * STEP_SECONDS


def test_optimizer_places_release_inside_rotation_window() -> None:
    delivery_window = _window(0, 4)
    obligation = _obligation(
        "REQ-ROTATION",
        required_volume_m3=STEP_SECONDS,
        window=delivery_window,
    )
    obligation = replace(obligation, rotation_windows=(_window(2, 1),))
    problem = _problem(
        (obligation,),
        (QuantizedFlowCandidate("GATE-1", 0.5, 1.0),),
    )

    result = optimize_limited_adjustment_plan(
        problem,
        model_step_seconds=STEP_SECONDS,
    )

    assert result.status is PlanStatus.FEASIBLE
    assert result.events[0].planned_at == HORIZON_START + timedelta(hours=2)


def test_optimizer_does_not_truncate_delayed_arrival_after_plan_end() -> None:
    delivery_window = _window(1, 1)
    obligation = _obligation(
        "REQ-TAIL",
        required_volume_m3=STEP_SECONDS,
        window=delivery_window,
        travel_delay_seconds=STEP_SECONDS,
    )
    problem = replace(
        _problem(
            (obligation,),
            (QuantizedFlowCandidate("GATE-1", 0.5, 1.0),),
        ),
        horizon_end=HORIZON_START + timedelta(hours=1),
    )

    result = optimize_limited_adjustment_plan(
        problem,
        model_step_seconds=STEP_SECONDS,
    )

    assert result.status is PlanStatus.INFEASIBLE


def test_optimizer_rejects_horizon_beyond_model_envelope() -> None:
    window = _window(0, 1)
    problem = _problem(
        (
            _obligation(
                "REQ-HORIZON",
                required_volume_m3=STEP_SECONDS,
                window=window,
            ),
        ),
        (QuantizedFlowCandidate("GATE-1", 0.5, 1.0),),
    )
    problem = replace(
        problem,
        operating_envelope=replace(
            problem.operating_envelope,
            maximum_horizon_seconds=2 * 24 * STEP_SECONDS,
        ),
    )

    with pytest.raises(
        HydraulicScheduleError,
        match="planning horizon exceeds the model operating envelope",
    ):
        optimize_limited_adjustment_plan(
            problem,
            model_step_seconds=STEP_SECONDS,
        )


def test_optimizer_rejects_model_step_outside_snapshot_envelope() -> None:
    window = _window(0, 1)
    problem = replace(
        _problem(
            (
                _obligation(
                    "REQ-STEP-ENVELOPE",
                    required_volume_m3=STEP_SECONDS,
                    window=window,
                ),
            ),
            (QuantizedFlowCandidate("GATE-1", 0.5, 1.0),),
        ),
        operating_envelope=ModelOperatingEnvelope(
            minimum_flow_m3s=0.0,
            maximum_flow_m3s=10.0,
            minimum_timestep_seconds=60.0,
            maximum_timestep_seconds=300.0,
            maximum_horizon_seconds=10 * 24 * STEP_SECONDS,
        ),
    )

    with pytest.raises(
        HydraulicScheduleError,
        match="model_step_seconds is outside the model operating envelope",
    ):
        optimize_limited_adjustment_plan(
            problem,
            model_step_seconds=STEP_SECONDS,
        )


def test_optimizer_enforces_snapshot_source_flow_ceiling() -> None:
    window = _window(0, 1)
    obligations = (
        _obligation(
            "REQ-SOURCE-A",
            gate_id="GATE-A",
            required_volume_m3=STEP_SECONDS,
            window=window,
            path_reach_ids=("C_A",),
        ),
        _obligation(
            "REQ-SOURCE-B",
            gate_id="GATE-B",
            required_volume_m3=STEP_SECONDS,
            window=window,
            path_reach_ids=("C_B",),
        ),
    )
    problem = replace(
        _problem(
            obligations,
            (
                QuantizedFlowCandidate("GATE-A", 0.5, 1.0),
                QuantizedFlowCandidate("GATE-B", 0.5, 1.0),
            ),
            capacities=(
                ReachCapacity("C_A", 1.0),
                ReachCapacity("C_B", 1.0),
            ),
            duties=(
                GatePulseDuty("GATE-A", STEP_SECONDS, STEP_SECONDS),
                GatePulseDuty("GATE-B", STEP_SECONDS, STEP_SECONDS),
            ),
        ),
        operating_envelope=ModelOperatingEnvelope(
            minimum_flow_m3s=0.0,
            maximum_flow_m3s=1.5,
            minimum_timestep_seconds=300.0,
            maximum_timestep_seconds=STEP_SECONDS,
            maximum_horizon_seconds=10 * 24 * STEP_SECONDS,
        ),
    )

    result = optimize_limited_adjustment_plan(
        problem,
        model_step_seconds=STEP_SECONDS,
    )

    assert result.status is PlanStatus.INFEASIBLE


def test_optimizer_measures_variation_on_aggregate_source_flow() -> None:
    obligations = (
        _obligation(
            "REQ-A-0",
            gate_id="GATE-A",
            required_volume_m3=2 * STEP_SECONDS,
            window=_window(0, 1),
            path_reach_ids=("C_A",),
        ),
        _obligation(
            "REQ-A-1",
            gate_id="GATE-A",
            required_volume_m3=STEP_SECONDS,
            window=_window(1, 1),
            path_reach_ids=("C_A",),
        ),
        _obligation(
            "REQ-B-0",
            gate_id="GATE-B",
            required_volume_m3=STEP_SECONDS,
            window=_window(0, 1),
            path_reach_ids=("C_B",),
        ),
        _obligation(
            "REQ-B-1",
            gate_id="GATE-B",
            required_volume_m3=2 * STEP_SECONDS,
            window=_window(1, 1),
            path_reach_ids=("C_B",),
        ),
    )
    problem = _problem(
        obligations,
        (
            QuantizedFlowCandidate("GATE-A", 0.5, 1.0),
            QuantizedFlowCandidate("GATE-A", 1.0, 2.0),
            QuantizedFlowCandidate("GATE-B", 0.5, 1.0),
            QuantizedFlowCandidate("GATE-B", 1.0, 2.0),
        ),
        capacities=(
            ReachCapacity("C_A", 2.0),
            ReachCapacity("C_B", 2.0),
        ),
        duties=(
            GatePulseDuty("GATE-A", 2 * STEP_SECONDS, 2 * STEP_SECONDS),
            GatePulseDuty("GATE-B", 2 * STEP_SECONDS, 2 * STEP_SECONDS),
        ),
    )

    result = optimize_limited_adjustment_plan(
        problem,
        model_step_seconds=STEP_SECONDS,
    )

    assert result.status is PlanStatus.FEASIBLE
    assert result.objective is not None
    assert result.objective.source_variation_m3s == 6.0


def test_optimizer_staggers_single_candidate_gates_to_reduce_source_variation() -> None:
    window = _window(0, 2)
    obligations = (
        _obligation(
            "REQ-STAGGER-A",
            gate_id="GATE-A",
            required_volume_m3=STEP_SECONDS,
            window=window,
            path_reach_ids=("C_A",),
        ),
        _obligation(
            "REQ-STAGGER-B",
            gate_id="GATE-B",
            required_volume_m3=STEP_SECONDS,
            window=window,
            path_reach_ids=("C_B",),
        ),
    )
    problem = _problem(
        obligations,
        (
            QuantizedFlowCandidate("GATE-A", 0.5, 1.0),
            QuantizedFlowCandidate("GATE-B", 0.5, 1.0),
        ),
        capacities=(
            ReachCapacity("C_A", 1.0),
            ReachCapacity("C_B", 1.0),
        ),
        duties=(
            GatePulseDuty("GATE-A", STEP_SECONDS, STEP_SECONDS),
            GatePulseDuty("GATE-B", STEP_SECONDS, STEP_SECONDS),
        ),
    )

    result = optimize_limited_adjustment_plan(
        problem,
        model_step_seconds=STEP_SECONDS,
    )

    assert result.status is PlanStatus.FEASIBLE
    assert result.objective is not None
    assert result.objective.source_variation_m3s == 2.0


def test_optimizer_rejects_requirement_after_d_plus_six() -> None:
    window = _window(0, 1)
    obligation = _obligation(
        "REQ-D7",
        required_volume_m3=STEP_SECONDS,
        window=window,
    )
    obligation = replace(obligation, service_date=date(2026, 7, 23))
    problem = _problem(
        (obligation,),
        (QuantizedFlowCandidate("GATE-1", 0.5, 1.0),),
    )

    with pytest.raises(
        HydraulicScheduleError,
        match="service_date must be within D through D\\+6",
    ):
        optimize_limited_adjustment_plan(
            problem,
            model_step_seconds=STEP_SECONDS,
        )


def test_optimizer_extends_past_d_plus_six_to_clear_valid_obligation() -> None:
    delivery_window = _window(7 * 24, 1)
    obligation = replace(
        _obligation(
            "REQ-D6-TAIL",
            required_volume_m3=STEP_SECONDS,
            window=delivery_window,
        ),
        service_date=date(2026, 7, 22),
    )
    problem = replace(
        _problem(
            (obligation,),
            (QuantizedFlowCandidate("GATE-1", 0.5, 1.0),),
            duties=(GatePulseDuty("GATE-1", STEP_SECONDS, STEP_SECONDS),),
        ),
        horizon_end=HORIZON_START + timedelta(days=8),
    )

    result = optimize_limited_adjustment_plan(
        problem,
        model_step_seconds=STEP_SECONDS,
    )

    assert result.status is PlanStatus.FEASIBLE
    assert result.events == (
        GatePlanEvent(
            "GATE-1",
            GateEventKind.OPEN,
            HORIZON_START + timedelta(days=7),
            0.5,
        ),
        GatePlanEvent(
            "GATE-1",
            GateEventKind.CLOSE,
            HORIZON_START + timedelta(days=7, hours=1),
            0.0,
        ),
    )


def test_optimizer_requires_immutable_problem_collections() -> None:
    window = _window(0, 1)
    problem = _problem(
        (
            _obligation(
                "REQ-MUTABLE",
                required_volume_m3=STEP_SECONDS,
                window=window,
            ),
        ),
        (QuantizedFlowCandidate("GATE-1", 0.5, 1.0),),
    )
    problem = replace(
        problem,
        obligations=cast(Any, list(problem.obligations)),
    )

    with pytest.raises(
        HydraulicScheduleError,
        match="obligations must be an immutable tuple",
    ):
        optimize_limited_adjustment_plan(
            problem,
            model_step_seconds=STEP_SECONDS,
        )


def test_optimizer_rejects_requirement_ids_with_boundary_whitespace() -> None:
    window = _window(0, 1)
    problem = _problem(
        (
            _obligation(
                " REQ-WHITESPACE ",
                required_volume_m3=STEP_SECONDS,
                window=window,
            ),
        ),
        (QuantizedFlowCandidate("GATE-1", 0.5, 1.0),),
    )

    with pytest.raises(
        HydraulicScheduleError,
        match="requirement_id must not contain boundary whitespace",
    ):
        optimize_limited_adjustment_plan(
            problem,
            model_step_seconds=STEP_SECONDS,
        )


def test_verify_adjustment_budget_rejects_more_than_two_trims() -> None:
    events = (
        GatePlanEvent("GATE-1", GateEventKind.OPEN, HORIZON_START, 0.25),
        GatePlanEvent(
            "GATE-1", GateEventKind.TRIM, HORIZON_START + timedelta(hours=1), 0.5
        ),
        GatePlanEvent(
            "GATE-1", GateEventKind.TRIM, HORIZON_START + timedelta(hours=2), 0.75
        ),
        GatePlanEvent(
            "GATE-1", GateEventKind.TRIM, HORIZON_START + timedelta(hours=3), 1.0
        ),
        GatePlanEvent(
            "GATE-1", GateEventKind.CLOSE, HORIZON_START + timedelta(hours=4), 0.0
        ),
    )

    with pytest.raises(
        HydraulicScheduleError,
        match="GATE-1 has 3 intermediate trims; the absolute ceiling is 2",
    ):
        verify_adjustment_budget(events, max_intermediate_trims=2)


def test_verify_adjustment_budget_rejects_policy_above_absolute_ceiling() -> None:
    with pytest.raises(
        HydraulicScheduleError,
        match="max_intermediate_trims must be between 0 and 2",
    ):
        verify_adjustment_budget((), max_intermediate_trims=3)
