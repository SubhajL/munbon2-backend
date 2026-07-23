"""Pure limited-adjustment planning for sensorless canal campaigns."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
import math
import re
import shutil
from time import monotonic

import pulp


class HydraulicScheduleError(ValueError):
    """The requested hydraulic planning problem is invalid."""


class GateEventKind(str, Enum):
    OPEN = "open"
    TRIM = "trim"
    CLOSE = "close"


class PlanStatus(str, Enum):
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"


@dataclass(frozen=True)
class TimeWindow:
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class DeliveryObligation:
    requirement_id: str
    service_date: date
    section_id: str
    gate_id: str
    required_volume_m3: float
    maximum_excess_volume_m3: float
    delivery_window: TimeWindow
    rotation_windows: tuple[TimeWindow, ...]
    path_reach_ids: tuple[str, ...]
    travel_delay_seconds: int
    minimum_delivery_fraction: float
    maximum_delivery_fraction: float


@dataclass(frozen=True)
class QuantizedFlowCandidate:
    gate_id: str
    target_position_m: float
    source_flow_m3s: float


@dataclass(frozen=True)
class ReachCapacity:
    reach_id: str
    maximum_flow_m3s: float


@dataclass(frozen=True)
class GatePulseDuty:
    gate_id: str
    minimum_open_seconds: int
    maximum_open_seconds: int


@dataclass(frozen=True)
class ModelOperatingEnvelope:
    minimum_flow_m3s: float
    maximum_flow_m3s: float
    minimum_timestep_seconds: float
    maximum_timestep_seconds: float
    maximum_horizon_seconds: float


@dataclass(frozen=True)
class LimitedAdjustmentProblem:
    model_snapshot_id: str
    operating_envelope: ModelOperatingEnvelope
    horizon_start: datetime
    horizon_end: datetime
    obligations: tuple[DeliveryObligation, ...]
    flow_candidates: tuple[QuantizedFlowCandidate, ...]
    reach_capacities: tuple[ReachCapacity, ...]
    pulse_duties: tuple[GatePulseDuty, ...]


@dataclass(frozen=True)
class GatePlanEvent:
    gate_id: str
    kind: GateEventKind
    planned_at: datetime
    target_position_m: float


@dataclass(frozen=True)
class DeliveryAllocation:
    requirement_id: str
    gate_id: str
    release_start: datetime
    release_end: datetime
    predicted_arrival_start: datetime
    predicted_arrival_end: datetime
    target_position_m: float
    lower_volume_m3: float
    upper_volume_m3: float


@dataclass(frozen=True)
class PlanObjective:
    intermediate_trims: int
    excess_volume_m3: float
    physical_moves: int
    source_variation_m3s: float
    open_seconds: int


@dataclass(frozen=True)
class LimitedAdjustmentPlan:
    status: PlanStatus
    model_snapshot_id: str
    model_step_seconds: int
    events: tuple[GatePlanEvent, ...]
    allocations: tuple[DeliveryAllocation, ...]
    objective: PlanObjective | None
    infeasible_reasons: tuple[str, ...]


@dataclass(frozen=True)
class GateAdjustmentBudget:
    gate_id: str
    intermediate_trims: int


@dataclass(frozen=True)
class _OptimizationModel:
    problem: pulp.LpProblem
    allocations: dict[tuple[int, int, int], pulp.LpVariable]
    trims: dict[tuple[str, int], pulp.LpVariable]
    variations: dict[tuple[str, int], pulp.LpVariable]
    gate_candidates: dict[str, tuple[int, ...]]
    gate_steps: dict[tuple[str, int], pulp.LpAffineExpression]
    timestep_count: int


_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_INFEASIBLE_REASON = (
    "no gate timeline satisfies volume, timing, capacity, pulse-duty, "
    "and adjustment constraints"
)
_EVENT_ORDER = {
    GateEventKind.CLOSE: 0,
    GateEventKind.OPEN: 1,
    GateEventKind.TRIM: 2,
}


def verify_adjustment_budget(
    events: tuple[GatePlanEvent, ...],
    max_intermediate_trims: int = 1,
) -> tuple[GateAdjustmentBudget, ...]:
    _validate_trim_policy(max_intermediate_trims)
    if not isinstance(events, tuple):
        raise HydraulicScheduleError("events must be an immutable tuple")
    events_by_gate: dict[str, list[GatePlanEvent]] = defaultdict(list)
    for event in events:
        if not isinstance(event, GatePlanEvent):
            raise HydraulicScheduleError("events must contain GatePlanEvent values")
        _validate_identifier(event.gate_id, "event gate_id")
        _validate_aware_datetime(event.planned_at, "event planned_at")
        _validate_finite(event.target_position_m, "event target_position_m")
        events_by_gate[event.gate_id].append(event)

    budgets = []
    for gate_id, gate_events in sorted(events_by_gate.items()):
        trims = _validate_gate_events(gate_id, gate_events)
        if trims > 2:
            raise HydraulicScheduleError(
                f"{gate_id} has {trims} intermediate trims; the absolute ceiling is 2"
            )
        if trims > max_intermediate_trims:
            raise HydraulicScheduleError(
                f"{gate_id} has {trims} intermediate trims; policy allows "
                f"{max_intermediate_trims}"
            )
        budgets.append(GateAdjustmentBudget(gate_id, trims))
    return tuple(budgets)


def optimize_limited_adjustment_plan(
    problem: LimitedAdjustmentProblem,
    *,
    model_step_seconds: int = 300,
    max_intermediate_trims: int = 1,
    solver_timeout_seconds: int = 60,
) -> LimitedAdjustmentPlan:
    _validate_problem(
        problem,
        model_step_seconds,
        max_intermediate_trims,
        solver_timeout_seconds,
    )
    optimization = _build_optimization_model(
        problem,
        model_step_seconds,
        max_intermediate_trims,
    )
    if not _solve_lexicographic(optimization, problem, solver_timeout_seconds):
        return LimitedAdjustmentPlan(
            status=PlanStatus.INFEASIBLE,
            model_snapshot_id=problem.model_snapshot_id,
            model_step_seconds=model_step_seconds,
            events=(),
            allocations=(),
            objective=None,
            infeasible_reasons=(_INFEASIBLE_REASON,),
        )
    selected = _selected_allocations(optimization)
    events = _gate_events(problem, optimization, selected, model_step_seconds)
    budgets = verify_adjustment_budget(events, max_intermediate_trims)
    allocations = _delivery_allocations(
        problem,
        selected,
        model_step_seconds,
    )
    return LimitedAdjustmentPlan(
        status=PlanStatus.FEASIBLE,
        model_snapshot_id=problem.model_snapshot_id,
        model_step_seconds=model_step_seconds,
        events=events,
        allocations=allocations,
        objective=_plan_objective(
            problem,
            selected,
            events,
            budgets,
            model_step_seconds,
        ),
        infeasible_reasons=(),
    )


def _validate_gate_events(gate_id: str, events: list[GatePlanEvent]) -> int:
    ordered = sorted(events, key=lambda event: event.planned_at)
    if len({event.planned_at for event in ordered}) != len(ordered):
        raise HydraulicScheduleError(f"{gate_id} has simultaneous gate events")
    is_open = False
    opened_once = False
    target = 0.0
    trims = 0
    for event in ordered:
        if event.kind is GateEventKind.OPEN:
            if is_open or opened_once or event.target_position_m <= 0:
                raise HydraulicScheduleError(f"{gate_id} has an invalid open event")
            is_open = True
            opened_once = True
        elif event.kind is GateEventKind.TRIM:
            if (
                not is_open
                or event.target_position_m <= 0
                or event.target_position_m == target
            ):
                raise HydraulicScheduleError(f"{gate_id} has an invalid trim event")
            trims += 1
        elif event.kind is GateEventKind.CLOSE:
            if not is_open or event.target_position_m != 0:
                raise HydraulicScheduleError(f"{gate_id} has an invalid close event")
            is_open = False
        else:
            raise HydraulicScheduleError(f"{gate_id} has an unknown event kind")
        target = event.target_position_m
    if is_open or not opened_once or ordered[-1].kind is not GateEventKind.CLOSE:
        raise HydraulicScheduleError(f"{gate_id} event sequence must end closed")
    return trims


def _validate_problem(
    problem: LimitedAdjustmentProblem,
    model_step_seconds: int,
    max_intermediate_trims: int,
    solver_timeout_seconds: int,
) -> None:
    if not isinstance(problem, LimitedAdjustmentProblem):
        raise HydraulicScheduleError("problem must be a LimitedAdjustmentProblem")
    _validate_positive_integer(model_step_seconds, "model_step_seconds")
    _validate_positive_integer(solver_timeout_seconds, "solver_timeout_seconds")
    _validate_trim_policy(max_intermediate_trims)
    if (
        not isinstance(problem.model_snapshot_id, str)
        or _SHA256_HEX.fullmatch(problem.model_snapshot_id) is None
    ):
        raise HydraulicScheduleError(
            "model_snapshot_id must be a lowercase SHA-256 digest"
        )
    _validate_aware_datetime(problem.horizon_start, "horizon_start")
    _validate_aware_datetime(problem.horizon_end, "horizon_end")
    _validate_operating_envelope(problem.operating_envelope)
    horizon_seconds = (problem.horizon_end - problem.horizon_start).total_seconds()
    if horizon_seconds <= 0 or horizon_seconds % model_step_seconds != 0:
        raise HydraulicScheduleError(
            "planning horizon must be positive and align to model_step_seconds"
        )
    if horizon_seconds > problem.operating_envelope.maximum_horizon_seconds:
        raise HydraulicScheduleError(
            "planning horizon exceeds the model operating envelope"
        )
    if not (
        problem.operating_envelope.minimum_timestep_seconds
        <= model_step_seconds
        <= problem.operating_envelope.maximum_timestep_seconds
    ):
        raise HydraulicScheduleError(
            "model_step_seconds is outside the model operating envelope"
        )
    _validate_tuple_collection(
        problem.obligations,
        "obligations",
        DeliveryObligation,
    )
    _validate_tuple_collection(
        problem.flow_candidates,
        "flow_candidates",
        QuantizedFlowCandidate,
    )
    _validate_tuple_collection(
        problem.reach_capacities,
        "reach_capacities",
        ReachCapacity,
    )
    _validate_tuple_collection(
        problem.pulse_duties,
        "pulse_duties",
        GatePulseDuty,
    )
    if not problem.obligations:
        raise HydraulicScheduleError("obligations must not be empty")
    _validate_obligations(problem, model_step_seconds)
    obligation_gates = {item.gate_id for item in problem.obligations}
    _validate_candidates(problem.flow_candidates, obligation_gates)
    _validate_capacities(problem)
    _validate_pulse_duties(
        problem.pulse_duties,
        obligation_gates,
        model_step_seconds,
    )


def _validate_obligations(
    problem: LimitedAdjustmentProblem,
    model_step_seconds: int,
) -> None:
    requirement_ids = [item.requirement_id for item in problem.obligations]
    if len(set(requirement_ids)) != len(requirement_ids):
        raise HydraulicScheduleError("requirement_id values must be unique")
    first_service_date = problem.horizon_start.date()
    last_service_date = first_service_date + timedelta(days=6)
    for item in problem.obligations:
        _validate_identifier(item.requirement_id, "requirement_id")
        _validate_identifier(item.section_id, "section_id")
        _validate_identifier(item.gate_id, "obligation gate_id")
        if not isinstance(item.service_date, date) or isinstance(
            item.service_date, datetime
        ):
            raise HydraulicScheduleError("service_date must be a date")
        if not first_service_date <= item.service_date <= last_service_date:
            raise HydraulicScheduleError(
                f"{item.requirement_id} service_date must be within D through D+6"
            )
        _validate_positive(item.required_volume_m3, "required_volume_m3")
        _validate_nonnegative(
            item.maximum_excess_volume_m3,
            "maximum_excess_volume_m3",
        )
        _validate_window(item.delivery_window, "delivery_window")
        _validate_tuple_collection(
            item.rotation_windows,
            "rotation_windows",
            TimeWindow,
        )
        if not item.rotation_windows:
            raise HydraulicScheduleError("rotation_windows must not be empty")
        for window in item.rotation_windows:
            _validate_window(window, "rotation_window")
        if not isinstance(item.path_reach_ids, tuple):
            raise HydraulicScheduleError("path_reach_ids must be an immutable tuple")
        if not item.path_reach_ids or any(
            not isinstance(reach_id, str) for reach_id in item.path_reach_ids
        ):
            raise HydraulicScheduleError("path_reach_ids must contain reach IDs")
        for reach_id in item.path_reach_ids:
            _validate_identifier(reach_id, "path reach_id")
        if len(set(item.path_reach_ids)) != len(item.path_reach_ids):
            raise HydraulicScheduleError("path_reach_ids must not contain duplicates")
        if (
            isinstance(item.travel_delay_seconds, bool)
            or not isinstance(item.travel_delay_seconds, int)
            or item.travel_delay_seconds < 0
            or item.travel_delay_seconds % model_step_seconds != 0
        ):
            raise HydraulicScheduleError(
                "travel_delay_seconds must be a non-negative model-step multiple"
            )
        _validate_delivery_fractions(item)


def _validate_operating_envelope(envelope: ModelOperatingEnvelope) -> None:
    if not isinstance(envelope, ModelOperatingEnvelope):
        raise HydraulicScheduleError(
            "operating_envelope must be a ModelOperatingEnvelope"
        )
    values = (
        envelope.minimum_flow_m3s,
        envelope.maximum_flow_m3s,
        envelope.minimum_timestep_seconds,
        envelope.maximum_timestep_seconds,
        envelope.maximum_horizon_seconds,
    )
    for value in values:
        _validate_finite(value, "operating envelope value")
    if envelope.minimum_flow_m3s != 0:
        raise HydraulicScheduleError(
            "minimum model flow must be zero to represent closure"
        )
    if envelope.maximum_flow_m3s <= envelope.minimum_flow_m3s:
        raise HydraulicScheduleError(
            "maximum model flow must exceed minimum model flow"
        )
    if envelope.minimum_timestep_seconds <= 0 or (
        envelope.maximum_timestep_seconds < envelope.minimum_timestep_seconds
    ):
        raise HydraulicScheduleError("model timestep envelope is invalid")
    if envelope.maximum_horizon_seconds < envelope.maximum_timestep_seconds:
        raise HydraulicScheduleError("model horizon envelope is invalid")


def _validate_candidates(
    candidates: tuple[QuantizedFlowCandidate, ...],
    obligation_gates: set[str],
) -> None:
    if not isinstance(candidates, tuple) or not candidates:
        raise HydraulicScheduleError("flow_candidates must be a non-empty tuple")
    candidate_keys = []
    candidate_gates = set()
    for candidate in candidates:
        _validate_identifier(candidate.gate_id, "candidate gate_id")
        _validate_positive(candidate.target_position_m, "target_position_m")
        _validate_positive(candidate.source_flow_m3s, "source_flow_m3s")
        candidate_keys.append((candidate.gate_id, candidate.target_position_m))
        candidate_gates.add(candidate.gate_id)
    if len(set(candidate_keys)) != len(candidate_keys):
        raise HydraulicScheduleError(
            "quantized target positions must be unique within each gate"
        )
    if candidate_gates != obligation_gates:
        raise HydraulicScheduleError(
            "flow candidate gates must exactly cover obligation gates"
        )


def _validate_capacities(problem: LimitedAdjustmentProblem) -> None:
    if not isinstance(problem.reach_capacities, tuple):
        raise HydraulicScheduleError("reach_capacities must be an immutable tuple")
    capacity_ids = []
    for capacity in problem.reach_capacities:
        _validate_identifier(capacity.reach_id, "capacity reach_id")
        _validate_positive(capacity.maximum_flow_m3s, "maximum_flow_m3s")
        capacity_ids.append(capacity.reach_id)
    if len(set(capacity_ids)) != len(capacity_ids):
        raise HydraulicScheduleError("reach capacities must be unique")
    required_reaches = {
        reach_id
        for obligation in problem.obligations
        for reach_id in obligation.path_reach_ids
    }
    missing = sorted(required_reaches - set(capacity_ids))
    if missing:
        raise HydraulicScheduleError(f"missing reach capacities: {missing}")


def _validate_pulse_duties(
    duties: tuple[GatePulseDuty, ...],
    obligation_gates: set[str],
    model_step_seconds: int,
) -> None:
    if not isinstance(duties, tuple):
        raise HydraulicScheduleError("pulse_duties must be an immutable tuple")
    duty_gates = [duty.gate_id for duty in duties]
    if len(set(duty_gates)) != len(duty_gates):
        raise HydraulicScheduleError("pulse duties must be unique by gate")
    if set(duty_gates) != obligation_gates:
        raise HydraulicScheduleError("pulse duties must exactly cover obligation gates")
    for duty in duties:
        _validate_identifier(duty.gate_id, "pulse duty gate_id")
        _validate_positive_integer(duty.minimum_open_seconds, "minimum_open_seconds")
        _validate_positive_integer(duty.maximum_open_seconds, "maximum_open_seconds")
        if (
            duty.minimum_open_seconds > duty.maximum_open_seconds
            or duty.minimum_open_seconds % model_step_seconds != 0
            or duty.maximum_open_seconds % model_step_seconds != 0
        ):
            raise HydraulicScheduleError(
                "pulse duty bounds must be ordered model-step multiples"
            )


def _validate_delivery_fractions(obligation: DeliveryObligation) -> None:
    _validate_positive(
        obligation.minimum_delivery_fraction,
        "minimum_delivery_fraction",
    )
    _validate_positive(
        obligation.maximum_delivery_fraction,
        "maximum_delivery_fraction",
    )
    if (
        obligation.minimum_delivery_fraction > obligation.maximum_delivery_fraction
        or obligation.maximum_delivery_fraction > 1
    ):
        raise HydraulicScheduleError(
            "delivery fractions must satisfy 0 < minimum <= maximum <= 1"
        )


def _validate_window(window: TimeWindow, name: str) -> None:
    if not isinstance(window, TimeWindow):
        raise HydraulicScheduleError(f"{name} must be a TimeWindow")
    _validate_aware_datetime(window.starts_at, f"{name} starts_at")
    _validate_aware_datetime(window.ends_at, f"{name} ends_at")
    if window.starts_at >= window.ends_at:
        raise HydraulicScheduleError(f"{name} must have positive duration")


def _build_optimization_model(
    problem: LimitedAdjustmentProblem,
    model_step_seconds: int,
    max_intermediate_trims: int,
) -> _OptimizationModel:
    timestep_count = int(
        (problem.horizon_end - problem.horizon_start).total_seconds()
        // model_step_seconds
    )
    model = pulp.LpProblem("LimitedAdjustmentCanalPlan", pulp.LpMinimize)
    gate_candidates = _gate_candidate_indices(problem)
    allocations = _allocation_variables(
        model,
        problem,
        timestep_count,
        model_step_seconds,
        gate_candidates,
    )
    candidate_steps, gate_steps = _state_expressions(
        problem,
        gate_candidates,
        allocations,
    )
    trims = _add_gate_timeline_constraints(
        model,
        problem,
        model_step_seconds,
        max_intermediate_trims,
        gate_candidates,
        candidate_steps,
        gate_steps,
    )
    _add_volume_constraints(model, problem, model_step_seconds, allocations)
    _add_capacity_constraints(
        model,
        problem,
        allocations,
    )
    _add_source_flow_constraints(model, problem, allocations)
    variations = _add_variation_constraints(
        model,
        problem,
        allocations,
    )
    return _OptimizationModel(
        model,
        allocations,
        trims,
        variations,
        gate_candidates,
        gate_steps,
        timestep_count,
    )


def _gate_candidate_indices(
    problem: LimitedAdjustmentProblem,
) -> dict[str, tuple[int, ...]]:
    indices: dict[str, list[int]] = defaultdict(list)
    for candidate_index, candidate in enumerate(problem.flow_candidates):
        indices[candidate.gate_id].append(candidate_index)
    return {
        gate_id: tuple(
            sorted(
                gate_indices,
                key=lambda index: (
                    problem.flow_candidates[index].target_position_m,
                    problem.flow_candidates[index].source_flow_m3s,
                ),
            )
        )
        for gate_id, gate_indices in indices.items()
    }


def _allocation_variables(
    model: pulp.LpProblem,
    problem: LimitedAdjustmentProblem,
    timestep_count: int,
    model_step_seconds: int,
    gate_candidates: dict[str, tuple[int, ...]],
) -> dict[tuple[int, int, int], pulp.LpVariable]:
    variables = {}
    for obligation_index, obligation in enumerate(problem.obligations):
        for timestep in range(timestep_count):
            if not _can_allocate_at(
                problem,
                obligation,
                timestep,
                model_step_seconds,
            ):
                continue
            for candidate_index in gate_candidates[obligation.gate_id]:
                key = (obligation_index, candidate_index, timestep)
                variables[key] = pulp.LpVariable(
                    f"allocation_{obligation_index}_{candidate_index}_{timestep}",
                    cat=pulp.LpBinary,
                )
    for gate_id, candidate_indices in gate_candidates.items():
        obligation_indices = [
            index
            for index, obligation in enumerate(problem.obligations)
            if obligation.gate_id == gate_id
        ]
        eligible_timesteps = sorted(
            {
                timestep
                for obligation_index, _, timestep in variables
                if obligation_index in obligation_indices
            }
        )
        for timestep in eligible_timesteps:
            model += (
                pulp.lpSum(
                    variables[key]
                    for obligation_index in obligation_indices
                    for candidate_index in candidate_indices
                    if (key := (obligation_index, candidate_index, timestep))
                    in variables
                )
                <= 1,
                f"single_allocation_{gate_id}_{timestep}",
            )
    return variables


def _can_allocate_at(
    problem: LimitedAdjustmentProblem,
    obligation: DeliveryObligation,
    timestep: int,
    model_step_seconds: int,
) -> bool:
    release_start = problem.horizon_start + timedelta(
        seconds=timestep * model_step_seconds
    )
    release_end = release_start + timedelta(seconds=model_step_seconds)
    delay = timedelta(seconds=obligation.travel_delay_seconds)
    arrival_start = release_start + delay
    arrival_end = release_end + delay
    return (
        arrival_end <= problem.horizon_end
        and obligation.delivery_window.starts_at <= arrival_start
        and arrival_end <= obligation.delivery_window.ends_at
        and any(
            rotation.starts_at <= arrival_start and arrival_end <= rotation.ends_at
            for rotation in obligation.rotation_windows
        )
    )


def _state_expressions(
    problem: LimitedAdjustmentProblem,
    gate_candidates: dict[str, tuple[int, ...]],
    allocations: dict[tuple[int, int, int], pulp.LpVariable],
) -> tuple[
    dict[tuple[str, int, int], pulp.LpAffineExpression],
    dict[tuple[str, int], pulp.LpAffineExpression],
]:
    candidate_steps = {}
    gate_steps = {}
    for gate_id, candidate_indices in gate_candidates.items():
        obligation_indices = [
            index
            for index, obligation in enumerate(problem.obligations)
            if obligation.gate_id == gate_id
        ]
        eligible_timesteps = [
            timestep
            for obligation_index, _, timestep in allocations
            if obligation_index in obligation_indices
        ]
        if not eligible_timesteps:
            continue
        for timestep in range(min(eligible_timesteps), max(eligible_timesteps) + 1):
            states = []
            for candidate_index in candidate_indices:
                state = pulp.lpSum(
                    allocations[key]
                    for obligation_index in obligation_indices
                    if (key := (obligation_index, candidate_index, timestep))
                    in allocations
                )
                candidate_steps[(gate_id, candidate_index, timestep)] = state
                states.append(state)
            gate_steps[(gate_id, timestep)] = pulp.lpSum(states)
    return candidate_steps, gate_steps


def _add_gate_timeline_constraints(
    model: pulp.LpProblem,
    problem: LimitedAdjustmentProblem,
    model_step_seconds: int,
    max_intermediate_trims: int,
    gate_candidates: dict[str, tuple[int, ...]],
    candidate_steps: dict[tuple[str, int, int], pulp.LpAffineExpression],
    gate_steps: dict[tuple[str, int], pulp.LpAffineExpression],
) -> dict[tuple[str, int], pulp.LpVariable]:
    duties = {duty.gate_id: duty for duty in problem.pulse_duties}
    starts = {}
    trims = {}
    for gate_id, candidate_indices in gate_candidates.items():
        gate_timesteps = sorted(
            timestep
            for state_gate_id, timestep in gate_steps
            if state_gate_id == gate_id
        )
        if not gate_timesteps:
            continue
        first_timestep = gate_timesteps[0]
        for timestep in gate_timesteps:
            current = gate_steps[(gate_id, timestep)]
            previous = (
                0 if timestep == first_timestep else gate_steps[(gate_id, timestep - 1)]
            )
            start = pulp.LpVariable(f"start_{gate_id}_{timestep}", cat=pulp.LpBinary)
            starts[(gate_id, timestep)] = start
            model += start >= current - previous
            model += start <= current
            model += start <= 1 - previous
            if timestep == first_timestep:
                continue
            trim = pulp.LpVariable(f"trim_{gate_id}_{timestep}", cat=pulp.LpBinary)
            trims[(gate_id, timestep)] = trim
            model += trim <= current
            model += trim <= previous
            for candidate_index in candidate_indices:
                model += trim >= (
                    candidate_steps[(gate_id, candidate_index, timestep)]
                    - candidate_steps[(gate_id, candidate_index, timestep - 1)]
                    - start
                )
        used = pulp.lpSum(starts[(gate_id, timestep)] for timestep in gate_timesteps)
        model += used == 1, f"one_continuous_opening_{gate_id}"
        duty = duties[gate_id]
        open_steps = pulp.lpSum(
            gate_steps[(gate_id, timestep)] for timestep in gate_timesteps
        )
        model += open_steps >= duty.minimum_open_seconds // model_step_seconds
        model += open_steps <= duty.maximum_open_seconds // model_step_seconds
        model += (
            pulp.lpSum(trims[(gate_id, timestep)] for timestep in gate_timesteps[1:])
            <= max_intermediate_trims,
            f"adjustment_budget_{gate_id}",
        )
    return trims


def _add_volume_constraints(
    model: pulp.LpProblem,
    problem: LimitedAdjustmentProblem,
    model_step_seconds: int,
    allocations: dict[tuple[int, int, int], pulp.LpVariable],
) -> None:
    for obligation_index, obligation in enumerate(problem.obligations):
        lower_terms = []
        upper_terms = []
        for (index, candidate_index, _), variable in allocations.items():
            if index != obligation_index:
                continue
            flow = problem.flow_candidates[candidate_index].source_flow_m3s
            lower_terms.append(
                variable
                * flow
                * obligation.minimum_delivery_fraction
                * model_step_seconds
            )
            upper_terms.append(
                variable
                * flow
                * obligation.maximum_delivery_fraction
                * model_step_seconds
            )
        model += (
            pulp.lpSum(lower_terms) >= obligation.required_volume_m3,
            f"required_volume_{obligation_index}",
        )
        model += (
            pulp.lpSum(upper_terms)
            <= obligation.required_volume_m3 + obligation.maximum_excess_volume_m3,
            f"excess_volume_{obligation_index}",
        )


def _add_capacity_constraints(
    model: pulp.LpProblem,
    problem: LimitedAdjustmentProblem,
    allocations: dict[tuple[int, int, int], pulp.LpVariable],
) -> None:
    capacities = {
        capacity.reach_id: capacity.maximum_flow_m3s
        for capacity in problem.reach_capacities
    }
    for reach_id in sorted(capacities):
        obligation_indices = {
            index
            for index, obligation in enumerate(problem.obligations)
            if reach_id in obligation.path_reach_ids
        }
        active_timesteps = sorted(
            {
                allocation_timestep
                for (
                    obligation_index,
                    _,
                    allocation_timestep,
                ) in allocations
                if obligation_index in obligation_indices
            }
        )
        for timestep in active_timesteps:
            model += (
                pulp.lpSum(
                    variable * problem.flow_candidates[candidate_index].source_flow_m3s
                    for (
                        obligation_index,
                        candidate_index,
                        allocation_timestep,
                    ), variable in allocations.items()
                    if obligation_index in obligation_indices
                    and allocation_timestep == timestep
                )
                <= capacities[reach_id],
                f"capacity_{reach_id}_{timestep}",
            )


def _add_source_flow_constraints(
    model: pulp.LpProblem,
    problem: LimitedAdjustmentProblem,
    allocations: dict[tuple[int, int, int], pulp.LpVariable],
) -> None:
    for timestep in sorted({key[2] for key in allocations}):
        model += (
            pulp.lpSum(
                variable * problem.flow_candidates[candidate_index].source_flow_m3s
                for (
                    _,
                    candidate_index,
                    allocation_timestep,
                ), variable in allocations.items()
                if allocation_timestep == timestep
            )
            <= problem.operating_envelope.maximum_flow_m3s,
            f"source_flow_envelope_{timestep}",
        )


def _add_variation_constraints(
    model: pulp.LpProblem,
    problem: LimitedAdjustmentProblem,
    allocations: dict[tuple[int, int, int], pulp.LpVariable],
) -> dict[tuple[str, int], pulp.LpVariable]:
    variations: dict[tuple[str, int], pulp.LpVariable] = {}
    active_timesteps = sorted({key[2] for key in allocations})
    if not active_timesteps:
        return variations
    first_timestep = active_timesteps[0]
    last_timestep = active_timesteps[-1]
    flows = {
        timestep: pulp.lpSum(
            variable * problem.flow_candidates[candidate_index].source_flow_m3s
            for (
                _,
                candidate_index,
                allocation_timestep,
            ), variable in allocations.items()
            if allocation_timestep == timestep
        )
        for timestep in range(first_timestep, last_timestep + 1)
    }
    for boundary in range(first_timestep, last_timestep + 2):
        previous = 0 if boundary == first_timestep else flows[boundary - 1]
        current = 0 if boundary > last_timestep else flows[boundary]
        variation = pulp.LpVariable(f"source_variation_{boundary}", lowBound=0)
        variations[("source", boundary)] = variation
        model += variation >= current - previous
        model += variation >= previous - current
    return variations


def _solve_lexicographic(
    optimization: _OptimizationModel,
    problem: LimitedAdjustmentProblem,
    solver_timeout_seconds: int,
) -> bool:
    model = optimization.problem
    deadline = monotonic() + solver_timeout_seconds
    trim_objective = pulp.lpSum(optimization.trims.values())
    if not _solve_before_deadline(
        model,
        trim_objective,
        deadline,
        allow_infeasible=True,
        warm_start=False,
    ):
        return False
    model += trim_objective == round(_expression_value(trim_objective))

    fixed_volume = _has_fixed_single_candidate_volume(
        optimization,
        problem,
    )
    if not fixed_volume:
        upper_volume = _upper_volume_expression(
            problem,
            optimization.allocations,
        )
        _solve_before_deadline(model, upper_volume, deadline)
        model += upper_volume <= _expression_value(upper_volume) + 1e-6

    if not fixed_volume or len(optimization.gate_candidates) > 1:
        variation = pulp.lpSum(optimization.variations.values())
        _solve_before_deadline(model, variation, deadline)
        model += variation <= _expression_value(variation) + 1e-8

    if not fixed_volume:
        open_steps = pulp.lpSum(optimization.gate_steps.values())
        _solve_before_deadline(model, open_steps, deadline)
        model += open_steps == round(_expression_value(open_steps))

    _solve_before_deadline(
        model,
        _deterministic_tiebreak_expression(optimization, problem),
        deadline,
    )
    return True


def _solve_before_deadline(
    model: pulp.LpProblem,
    objective: pulp.LpAffineExpression,
    deadline: float,
    allow_infeasible: bool = False,
    warm_start: bool = True,
) -> bool:
    remaining_seconds = deadline - monotonic()
    if remaining_seconds <= 0:
        raise HydraulicScheduleError("optimizer exceeded its end-to-end solver timeout")
    solver = _cbc_solver(
        remaining_seconds=remaining_seconds,
        warm_start=warm_start,
    )
    model.setObjective(objective)
    status = pulp.LpStatus[model.solve(solver)]
    if status == "Optimal":
        return True
    if allow_infeasible and status == "Infeasible":
        return False
    raise HydraulicScheduleError(f"optimizer did not prove an optimal result: {status}")


def _cbc_solver(*, remaining_seconds: float, warm_start: bool):
    system_cbc = shutil.which("cbc")
    options = {
        "msg": False,
        "threads": 1,
        "timeLimit": remaining_seconds,
        "warmStart": warm_start,
    }
    if system_cbc is not None:
        return pulp.COIN_CMD(path=system_cbc, **options)
    return pulp.PULP_CBC_CMD(**options)


def _expression_value(expression: pulp.LpAffineExpression) -> float:
    value = pulp.value(expression)
    return 0.0 if value is None else float(value)


def _has_fixed_single_candidate_volume(
    optimization: _OptimizationModel,
    problem: LimitedAdjustmentProblem,
) -> bool:
    return all(
        len(candidate_indices) == 1
        for candidate_indices in optimization.gate_candidates.values()
    ) and all(
        obligation.maximum_excess_volume_m3 == 0
        and obligation.minimum_delivery_fraction == obligation.maximum_delivery_fraction
        for obligation in problem.obligations
    )


def _upper_volume_expression(
    problem: LimitedAdjustmentProblem,
    allocations: dict[tuple[int, int, int], pulp.LpVariable],
) -> pulp.LpAffineExpression:
    return pulp.lpSum(
        variable
        * problem.flow_candidates[candidate_index].source_flow_m3s
        * problem.obligations[obligation_index].maximum_delivery_fraction
        for (obligation_index, candidate_index, _), variable in allocations.items()
    )


def _deterministic_tiebreak_expression(
    optimization: _OptimizationModel,
    problem: LimitedAdjustmentProblem,
) -> pulp.LpAffineExpression:
    candidate_ranks = {
        candidate_index: rank
        for candidate_indices in optimization.gate_candidates.values()
        for rank, candidate_index in enumerate(candidate_indices)
    }
    rank_bound = max(len(indices) for indices in optimization.gate_candidates.values())
    time_weight = rank_bound * optimization.timestep_count**2 + 1
    return pulp.lpSum(
        variable
        * (
            time_weight * (timestep + 1)
            + candidate_ranks[candidate_index]
            * (optimization.timestep_count - timestep)
            + obligation_index
        )
        for (
            obligation_index,
            candidate_index,
            timestep,
        ), variable in optimization.allocations.items()
    )


def _selected_allocations(
    optimization: _OptimizationModel,
) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        sorted(
            key
            for key, variable in optimization.allocations.items()
            if variable.value() is not None and variable.value() > 0.5
        )
    )


def _gate_events(
    problem: LimitedAdjustmentProblem,
    optimization: _OptimizationModel,
    selected: tuple[tuple[int, int, int], ...],
    model_step_seconds: int,
) -> tuple[GatePlanEvent, ...]:
    states: dict[tuple[str, int], int] = {}
    for obligation_index, candidate_index, timestep in selected:
        gate_id = problem.obligations[obligation_index].gate_id
        states[(gate_id, timestep)] = candidate_index
    events = []
    for gate_id in sorted(optimization.gate_candidates):
        active_steps = sorted(
            timestep for state_gate_id, timestep in states if state_gate_id == gate_id
        )
        first_step = active_steps[0]
        previous_candidate = states[(gate_id, first_step)]
        events.append(
            GatePlanEvent(
                gate_id,
                GateEventKind.OPEN,
                problem.horizon_start
                + timedelta(seconds=first_step * model_step_seconds),
                problem.flow_candidates[previous_candidate].target_position_m,
            )
        )
        for timestep in active_steps[1:]:
            candidate_index = states[(gate_id, timestep)]
            if candidate_index == previous_candidate:
                continue
            events.append(
                GatePlanEvent(
                    gate_id,
                    GateEventKind.TRIM,
                    problem.horizon_start
                    + timedelta(seconds=timestep * model_step_seconds),
                    problem.flow_candidates[candidate_index].target_position_m,
                )
            )
            previous_candidate = candidate_index
        events.append(
            GatePlanEvent(
                gate_id,
                GateEventKind.CLOSE,
                problem.horizon_start
                + timedelta(seconds=(active_steps[-1] + 1) * model_step_seconds),
                0.0,
            )
        )
    return tuple(
        sorted(
            events,
            key=lambda event: (
                event.planned_at,
                event.gate_id,
                _EVENT_ORDER[event.kind],
            ),
        )
    )


def _delivery_allocations(
    problem: LimitedAdjustmentProblem,
    selected: tuple[tuple[int, int, int], ...],
    model_step_seconds: int,
) -> tuple[DeliveryAllocation, ...]:
    allocations = []
    selected_by_obligation: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for obligation_index, candidate_index, timestep in selected:
        selected_by_obligation[obligation_index].append((timestep, candidate_index))
    for obligation_index, steps in sorted(selected_by_obligation.items()):
        for start, end, candidate_index in _allocation_segments(steps):
            obligation = problem.obligations[obligation_index]
            candidate = problem.flow_candidates[candidate_index]
            release_start = problem.horizon_start + timedelta(
                seconds=start * model_step_seconds
            )
            release_end = problem.horizon_start + timedelta(
                seconds=(end + 1) * model_step_seconds
            )
            duration = (end - start + 1) * model_step_seconds
            delay = timedelta(seconds=obligation.travel_delay_seconds)
            allocations.append(
                DeliveryAllocation(
                    obligation.requirement_id,
                    obligation.gate_id,
                    release_start,
                    release_end,
                    release_start + delay,
                    release_end + delay,
                    candidate.target_position_m,
                    candidate.source_flow_m3s
                    * obligation.minimum_delivery_fraction
                    * duration,
                    candidate.source_flow_m3s
                    * obligation.maximum_delivery_fraction
                    * duration,
                )
            )
    return tuple(
        sorted(
            allocations,
            key=lambda item: (
                item.release_start,
                item.gate_id,
                item.requirement_id,
                item.target_position_m,
            ),
        )
    )


def _allocation_segments(
    steps: list[tuple[int, int]],
) -> tuple[tuple[int, int, int], ...]:
    ordered = sorted(steps)
    segments = []
    start, previous = ordered[0][0], ordered[0][0]
    candidate_index = ordered[0][1]
    for timestep, current_candidate in ordered[1:]:
        if timestep == previous + 1 and current_candidate == candidate_index:
            previous = timestep
            continue
        segments.append((start, previous, candidate_index))
        start = previous = timestep
        candidate_index = current_candidate
    segments.append((start, previous, candidate_index))
    return tuple(segments)


def _plan_objective(
    problem: LimitedAdjustmentProblem,
    selected: tuple[tuple[int, int, int], ...],
    events: tuple[GatePlanEvent, ...],
    budgets: tuple[GateAdjustmentBudget, ...],
    model_step_seconds: int,
) -> PlanObjective:
    upper_volume = sum(
        problem.flow_candidates[candidate_index].source_flow_m3s
        * problem.obligations[obligation_index].maximum_delivery_fraction
        * model_step_seconds
        for obligation_index, candidate_index, _ in selected
    )
    required_volume = sum(
        obligation.required_volume_m3 for obligation in problem.obligations
    )
    return PlanObjective(
        intermediate_trims=sum(item.intermediate_trims for item in budgets),
        excess_volume_m3=max(0.0, upper_volume - required_volume),
        physical_moves=len(events),
        source_variation_m3s=_source_variation(problem, selected),
        open_seconds=len(selected) * model_step_seconds,
    )


def _source_variation(
    problem: LimitedAdjustmentProblem,
    selected: tuple[tuple[int, int, int], ...],
) -> float:
    flows: dict[int, float] = defaultdict(float)
    for _, candidate_index, timestep in selected:
        flows[timestep] += problem.flow_candidates[candidate_index].source_flow_m3s
    variation = 0.0
    first = min(flows)
    last = max(flows)
    previous = 0.0
    for timestep in range(first, last + 1):
        current = flows[timestep]
        variation += abs(current - previous)
        previous = current
    variation += abs(previous)
    return variation


def _validate_trim_policy(max_intermediate_trims: int) -> None:
    if (
        isinstance(max_intermediate_trims, bool)
        or not isinstance(max_intermediate_trims, int)
        or not 0 <= max_intermediate_trims <= 2
    ):
        raise HydraulicScheduleError("max_intermediate_trims must be between 0 and 2")


def _validate_aware_datetime(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise HydraulicScheduleError(f"{name} must be timezone-aware")


def _validate_finite(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HydraulicScheduleError(f"{name} must be a finite number")
    if not math.isfinite(value):
        raise HydraulicScheduleError(f"{name} must be a finite number")


def _validate_positive(value: float, name: str) -> None:
    _validate_finite(value, name)
    if value <= 0:
        raise HydraulicScheduleError(f"{name} must be positive")


def _validate_nonnegative(value: float, name: str) -> None:
    _validate_finite(value, name)
    if value < 0:
        raise HydraulicScheduleError(f"{name} must be non-negative")


def _validate_positive_integer(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise HydraulicScheduleError(f"{name} must be a positive integer")


def _validate_identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise HydraulicScheduleError(f"{name} must not be blank")
    if value != value.strip():
        raise HydraulicScheduleError(f"{name} must not contain boundary whitespace")


def _validate_tuple_collection(
    value: object,
    name: str,
    item_type: type,
) -> None:
    if not isinstance(value, tuple):
        raise HydraulicScheduleError(f"{name} must be an immutable tuple")
    if any(not isinstance(item, item_type) for item in value):
        raise HydraulicScheduleError(
            f"{name} contains an invalid {item_type.__name__} value"
        )
