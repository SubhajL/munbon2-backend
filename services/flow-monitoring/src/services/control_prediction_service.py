"""Runtime orchestration seam for pure sensorless control predictions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import math

from core.fulfillment import (
    ClosureProjection,
    ClosureRequirement,
    earliest_safe_closure,
)
from core.network_transient import (
    BranchAllocation,
    GateFlowEvent,
    NetworkReachCapacityExceededError,
    NetworkTimeline,
    NetworkTransientError,
    OperatorWithdrawalEvent,
    SectionRequirement,
    WithdrawalCapacityCheckStatus,
    simulate_network_timeline,
)
from core.model_release import HydraulicModelRelease
from core.model_snapshot import ModelSnapshotError, build_model_snapshot
from core.prediction_engine import (
    PredictionEngineError,
    validate_prediction_engine_descriptor,
)
from core.prediction_repository import PREDICTION_ENGINE_REQUEST_KEY
from core.reach_response import ReachResponse, ReachState, ResponseMember
from core.routing_topology import RoutingRole, RoutingTopology

_VOLUME_TOLERANCE_M3 = 1e-9
_FLOW_TOLERANCE_M3S = 1e-9

_ENGINE_DESCRIPTOR_EMBED_FIELDS = (
    "schema_version",
    "engine_id",
    "semantic_contract_version",
    "build_digest",
    "content_hash",
)


class PredictionModelUnavailableError(ValueError):
    """No hydraulic model release is configured for this runtime."""


class PredictionLineageConflictError(ValueError):
    """The request pins a snapshot/release the runtime does not serve."""


class PredictionEngineIdentityError(ValueError):
    """The identity rollout cannot proceed: the current engine descriptor is
    missing or the request does not carry it (fail closed)."""


def normalize_prediction_request_identity_v2(
    normalized_request: dict, engine_descriptor: dict | None
) -> dict:
    """The identity-v2 payload: the normalized request augmented with the
    CURRENT engine descriptor. The engine thus enters the v2 run id and can be
    re-checked on load. Fail closed when the descriptor is absent/invalid."""
    if engine_descriptor is None:
        raise PredictionEngineIdentityError(
            "prediction engine descriptor is not loaded; identity-v2 "
            "predictions are unavailable"
        )
    try:
        validate_prediction_engine_descriptor(engine_descriptor)
    except PredictionEngineError as exc:
        raise PredictionEngineIdentityError(str(exc)) from exc
    if PREDICTION_ENGINE_REQUEST_KEY in normalized_request:
        raise PredictionEngineIdentityError(
            f"request must not pre-carry the {PREDICTION_ENGINE_REQUEST_KEY!r} "
            "identity block"
        )
    return {
        **normalized_request,
        PREDICTION_ENGINE_REQUEST_KEY: {
            field: engine_descriptor[field]
            for field in _ENGINE_DESCRIPTOR_EMBED_FIELDS
        },
    }


@dataclass(frozen=True)
class RequirementShortfallViolation:
    requirement_id: str
    required_volume_m3: float
    predicted_delivered_m3: float
    shortfall_m3: float
    kind: str = "requirement_shortfall"


@dataclass(frozen=True)
class WithdrawalShortfallViolation:
    structure_id: str
    first_at: datetime
    steps: int
    planned_total_m3: float
    predicted_total_m3: float
    shortfall_total_m3: float
    kind: str = "withdrawal_shortfall"


@dataclass(frozen=True)
class WithdrawalCapacityExceededViolation:
    structure_id: str
    first_at: datetime
    steps: int
    maximum_planned_flow_m3s: float
    structure_max_flow_m3s: float
    kind: str = "withdrawal_capacity_exceeded"


@dataclass(frozen=True)
class WithdrawalCapacityUnavailableViolation:
    structure_id: str
    first_at: datetime
    steps: int
    maximum_planned_flow_m3s: float
    kind: str = "withdrawal_capacity_unavailable"


PredictionViolation = (
    RequirementShortfallViolation
    | WithdrawalShortfallViolation
    | WithdrawalCapacityExceededViolation
    | WithdrawalCapacityUnavailableViolation
)


@dataclass(frozen=True)
class MemberInfeasibility:
    """Plain value copy of a capacity abort — never the live exception, so
    outcomes stay serializable and hold no traceback-pinned engine state."""

    reach_id: str
    kind: str
    attempted_flow_m3s: float
    capacity_m3s: float
    interval_start: datetime
    interval_end: datetime


@dataclass(frozen=True)
class MemberPrediction:
    member: ResponseMember
    timeline: NetworkTimeline | None
    infeasibility: MemberInfeasibility | None
    violations: tuple[PredictionViolation, ...]
    predicted_delivered_total_m3: float | None


@dataclass(frozen=True)
class ControlPredictionOutcome:
    snapshot_id: str
    covered_transport_reach_ids: tuple[str, ...]
    excluded_transport_reaches: tuple[tuple[str, str], ...]
    members: tuple[MemberPrediction, ...]


def build_withdrawal_structure_max_flow_map(
    routing_topology: RoutingTopology,
    gate_calibrations_config: Mapping[str, object],
) -> tuple[tuple[str, float | None], ...]:
    """Authoritative structure maxima for the withdrawal structures.

    The ONLY accepted source is gate_calibrations
    ``gates[structure_id].structure_max_flow_m3s`` — never rated q_max,
    dimensions, or donor inference. Absent metadata stays None so capacity
    checks report unavailable instead of fabricating a ceiling.
    """
    gates = gate_calibrations_config.get("gates")
    if not isinstance(gates, Mapping):
        raise NetworkTransientError(
            "gate calibrations config must carry a gates mapping"
        )
    capacity: dict[str, float | None] = {}
    for element in routing_topology.elements:
        if element.role is not RoutingRole.WITHDRAWAL_STRUCTURE:
            continue
        structure_id = element.downstream_node_id
        gate = gates.get(structure_id)
        if not isinstance(gate, Mapping):
            raise NetworkTransientError(
                f"withdrawal structure {structure_id!r} is absent from the "
                "gate calibrations artifact"
            )
        q_max = gate.get("structure_max_flow_m3s")
        if q_max is not None and (
            isinstance(q_max, bool)
            or not isinstance(q_max, (int, float))
            or not math.isfinite(q_max)
            or q_max <= 0.0
        ):
            raise NetworkTransientError(
                f"structure_max_flow_m3s for {structure_id!r} must be None "
                "or a positive finite flow"
            )
        capacity[structure_id] = q_max
    return tuple(sorted(capacity.items()))


@dataclass(frozen=True)
class ControlPredictionService:
    routing_topology: RoutingTopology
    reach_responses: tuple[ReachResponse, ...]
    maximum_horizon_seconds: float | None
    structure_max_flow_m3s_by_id: tuple[tuple[str, float | None], ...] = ()
    prediction_engine_descriptor: dict | None = None

    def __post_init__(self) -> None:
        if self.prediction_engine_descriptor is not None:
            try:
                validate_prediction_engine_descriptor(
                    self.prediction_engine_descriptor
                )
            except PredictionEngineError as exc:
                raise NetworkTransientError(
                    f"prediction_engine_descriptor is invalid: {exc}"
                ) from exc
        if not isinstance(self.routing_topology, RoutingTopology):
            raise NetworkTransientError(
                "routing_topology must be a typed RoutingTopology"
            )
        if not isinstance(self.structure_max_flow_m3s_by_id, tuple):
            raise NetworkTransientError(
                "structure_max_flow_m3s_by_id must be an immutable tuple of "
                "(structure_id, q_max) pairs"
            )
        expected = {
            element.downstream_node_id
            for element in self.routing_topology.elements
            if element.role is RoutingRole.WITHDRAWAL_STRUCTURE
        }
        provided = [pair[0] for pair in self.structure_max_flow_m3s_by_id]
        if len(provided) != len(set(provided)) or set(provided) != expected:
            raise NetworkTransientError(
                "structure_max_flow_m3s_by_id must cover exactly the "
                f"withdrawal structures {sorted(expected)!r}"
            )
        if not isinstance(self.reach_responses, tuple):
            raise NetworkTransientError("reach_responses must be an immutable tuple")
        if self.reach_responses and self.maximum_horizon_seconds is None:
            raise NetworkTransientError(
                "maximum_horizon_seconds is required with a model release"
            )
        if self.maximum_horizon_seconds is not None and (
            isinstance(self.maximum_horizon_seconds, bool)
            or not isinstance(self.maximum_horizon_seconds, (int, float))
            or not math.isfinite(self.maximum_horizon_seconds)
            or self.maximum_horizon_seconds <= 0.0
        ):
            raise NetworkTransientError(
                "maximum_horizon_seconds must be a finite number > 0"
            )
        # Non-field cache: the snapshot id is constant per (release, config,
        # actuation) for this frozen service, so hot-path requests must not
        # re-serialize and re-hash the whole model every POST.
        object.__setattr__(self, "_snapshot_id_cache", {})

    def member_responses(
        self, member: ResponseMember
    ) -> tuple[ReachResponse, ...]:
        """THE single member-selection rule; orchestration and the engine
        seam must never encode it twice."""
        return tuple(
            response
            for response in self.reach_responses
            if response.member is member
        )

    def predict_member(
        self,
        member: ResponseMember,
        initial_states: tuple[ReachState, ...],
        gate_events: tuple[GateFlowEvent, ...],
        withdrawal_events: tuple[OperatorWithdrawalEvent, ...],
        requirements: tuple[SectionRequirement, ...],
        branch_allocations: tuple[BranchAllocation, ...],
        starts_at: datetime,
        ends_at: datetime,
        timestep_seconds: float,
        unavailable_transport_reach_ids: frozenset[str] = frozenset(),
    ) -> NetworkTimeline:
        if not isinstance(member, ResponseMember):
            raise NetworkTransientError("member must be a ResponseMember")
        horizon_seconds = (ends_at - starts_at).total_seconds()
        if (
            self.maximum_horizon_seconds is not None
            and horizon_seconds > self.maximum_horizon_seconds
        ):
            raise NetworkTransientError(
                f"prediction horizon {horizon_seconds} exceeds model release envelope "
                f"{self.maximum_horizon_seconds}"
            )
        member_responses = self.member_responses(member)
        return simulate_network_timeline(
            self.routing_topology,
            member_responses,
            initial_states,
            gate_events,
            withdrawal_events,
            dict(self.structure_max_flow_m3s_by_id),
            requirements,
            branch_allocations,
            starts_at,
            ends_at,
            timestep_seconds,
            unavailable_transport_reach_ids=unavailable_transport_reach_ids,
        )

    def validate_prediction_request(
        self,
        release: HydraulicModelRelease | None,
        config_sha256: Mapping[str, str],
        actuation_approved: bool,
        model_snapshot_id: str,
        model_release_id: str,
        model_release_content_hash: str,
        gate_events: tuple[GateFlowEvent, ...],
        requirements: tuple[SectionRequirement, ...],
        starts_at: datetime,
        ends_at: datetime,
        timestep_seconds: float,
    ) -> str:
        """Fail closed before any member runs; returns the runtime snapshot id."""
        if release is None:
            raise PredictionModelUnavailableError(
                "hydraulic model release is not configured; predictions are "
                "unavailable"
            )
        cache_key = (
            release.content_hash,
            tuple(sorted(config_sha256.items())),
            actuation_approved,
        )
        snapshot_id = self._snapshot_id_cache.get(cache_key)
        if snapshot_id is None:
            snapshot = self.model_snapshot(
                release, config_sha256, actuation_approved
            )
            snapshot_id = snapshot["snapshot_id"]
            self._snapshot_id_cache[cache_key] = snapshot_id
        pinned = (
            model_snapshot_id,
            model_release_id,
            model_release_content_hash,
        )
        served = (snapshot_id, release.release_id, release.content_hash)
        if pinned != served:
            raise PredictionLineageConflictError(
                "request pins do not match the served model: "
                f"snapshot {model_snapshot_id!r} vs {snapshot_id!r}, "
                f"release {model_release_id!r} vs {release.release_id!r}, "
                f"hash {model_release_content_hash!r} vs "
                f"{release.content_hash!r}"
            )
        envelope = release.operating_envelope
        if not (
            envelope.minimum_timestep_seconds
            <= timestep_seconds
            <= envelope.maximum_timestep_seconds
        ):
            raise NetworkTransientError(
                f"timestep {timestep_seconds} is outside the release envelope "
                f"[{envelope.minimum_timestep_seconds}, "
                f"{envelope.maximum_timestep_seconds}]"
            )
        horizon_seconds = (ends_at - starts_at).total_seconds()
        if horizon_seconds > envelope.maximum_horizon_seconds:
            raise NetworkTransientError(
                f"prediction horizon {horizon_seconds} exceeds model release "
                f"envelope {envelope.maximum_horizon_seconds}"
            )
        if not any(event.effective_at == starts_at for event in gate_events):
            raise NetworkTransientError(
                "source_flow_events must include an explicit event at "
                "starts_at; pass flow_m3s 0.0 to state a dry source"
            )
        for requirement in requirements:
            # A window reaching outside the horizon would present a
            # partial-window simulation as a complete verdict — fail closed.
            if not (
                starts_at
                <= requirement.window_start
                < requirement.window_end
                <= ends_at
            ):
                raise NetworkTransientError(
                    f"requirement {requirement.requirement_id!r} window "
                    "must lie entirely within the prediction horizon"
                )
        for event in gate_events:
            if event.flow_m3s == 0.0:
                continue
            if not (
                envelope.minimum_flow_m3s
                <= event.flow_m3s
                <= envelope.maximum_flow_m3s
            ):
                raise NetworkTransientError(
                    f"source flow {event.flow_m3s} m3/s is outside the model "
                    f"validity envelope [{envelope.minimum_flow_m3s}, "
                    f"{envelope.maximum_flow_m3s}]"
                )
        return snapshot_id

    def predict_control_timeline(
        self,
        release: HydraulicModelRelease | None,
        config_sha256: Mapping[str, str],
        actuation_approved: bool,
        model_snapshot_id: str,
        model_release_id: str,
        model_release_content_hash: str,
        gate_events: tuple[GateFlowEvent, ...],
        withdrawal_events: tuple[OperatorWithdrawalEvent, ...],
        requirements: tuple[SectionRequirement, ...],
        branch_allocations: tuple[BranchAllocation, ...],
        starts_at: datetime,
        ends_at: datetime,
        timestep_seconds: float,
    ) -> ControlPredictionOutcome:
        snapshot_id = self.validate_prediction_request(
            release,
            config_sha256,
            actuation_approved,
            model_snapshot_id,
            model_release_id,
            model_release_content_hash,
            gate_events,
            requirements,
            starts_at,
            ends_at,
            timestep_seconds,
        )
        transports = set(self.routing_topology.transport_reach_ids())
        reason_by_reach = {
            reach.reach_id: reach.reason
            for reach in release.unavailable_reaches
        }
        members = []
        covered_order: tuple[str, ...] = ()
        for member in (
            ResponseMember.LOWER,
            ResponseMember.NOMINAL,
            ResponseMember.UPPER,
        ):
            member_responses = self.member_responses(member)
            covered = {response.reach_id for response in member_responses}
            unavailable = transports - covered
            if unavailable != set(reason_by_reach):
                raise ModelSnapshotError(
                    "runtime response coverage does not match the model "
                    f"release for member {member.value!r}"
                )
            initial_states = tuple(
                ReachState(release.release_id, response.reach_id, member)
                for response in member_responses
            )
            try:
                timeline = self.predict_member(
                    member,
                    initial_states,
                    gate_events,
                    withdrawal_events,
                    requirements,
                    branch_allocations,
                    starts_at,
                    ends_at,
                    timestep_seconds,
                    unavailable_transport_reach_ids=frozenset(unavailable),
                )
            except NetworkReachCapacityExceededError as exc:
                members.append(
                    MemberPrediction(
                        member=member,
                        timeline=None,
                        infeasibility=MemberInfeasibility(
                            reach_id=exc.reach_id,
                            kind=exc.kind,
                            attempted_flow_m3s=exc.attempted_flow_m3s,
                            capacity_m3s=exc.capacity_m3s,
                            interval_start=exc.interval_start,
                            interval_end=exc.interval_end,
                        ),
                        violations=(),
                        predicted_delivered_total_m3=None,
                    )
                )
                continue
            covered_order = tuple(
                state.reach_id for state in timeline.final_reach_states
            )
            members.append(
                MemberPrediction(
                    member=member,
                    timeline=timeline,
                    infeasibility=None,
                    violations=collect_prediction_violations(
                        timeline,
                        requirements,
                        dict(self.structure_max_flow_m3s_by_id),
                    ),
                    predicted_delivered_total_m3=sum(
                        state.predicted_delivered_m3
                        for state in timeline.final_fulfillment
                    ),
                )
            )
        if not covered_order:
            covered_order = tuple(
                reach_id
                for reach_id in self.routing_topology.transport_reach_ids()
                if reach_id not in reason_by_reach
            )
        return ControlPredictionOutcome(
            snapshot_id=snapshot_id,
            covered_transport_reach_ids=covered_order,
            excluded_transport_reaches=tuple(
                sorted(reason_by_reach.items())
            ),
            members=tuple(members),
        )

    def earliest_safe_closure(
        self,
        closing_gate_id: str,
        requirements: tuple[ClosureRequirement, ...],
        projections: tuple[ClosureProjection, ...],
    ) -> datetime | None:
        if closing_gate_id not in self.routing_topology.canonical_gate_node_ids():
            raise NetworkTransientError(
                f"closing_gate_id {closing_gate_id!r} must be a canal gate, "
                "not a virtual routing node"
            )
        routing_edges = self.routing_topology.routing_edges()
        return earliest_safe_closure(
            closing_gate_id,
            routing_edges,
            requirements,
            projections,
        )

    def model_snapshot(
        self,
        release: HydraulicModelRelease | None,
        config_sha256: Mapping[str, str],
        actuation_approved: bool,
    ) -> dict:
        expected_horizon = (
            None
            if release is None
            else release.operating_envelope.maximum_horizon_seconds
        )
        if self.maximum_horizon_seconds != expected_horizon:
            raise ModelSnapshotError(
                "runtime prediction horizon does not match the model release"
            )
        if self.prediction_engine_descriptor is None:
            raise ModelSnapshotError(
                "prediction engine descriptor is not loaded; model snapshots "
                "are unavailable"
            )
        return build_model_snapshot(
            self.routing_topology,
            self.reach_responses,
            release,
            config_sha256,
            actuation_approved,
            self.prediction_engine_descriptor,
        )


def collect_prediction_violations(
    timeline: NetworkTimeline,
    requirements: tuple[SectionRequirement, ...],
    structure_max_flow_m3s: Mapping[str, float | None],
) -> tuple[PredictionViolation, ...]:
    """Deterministic, step-aggregated violations from one COMPLETED timeline.

    An unknown structure maximum with a positive planned withdrawal is ALWAYS
    surfaced — capacity that cannot be checked must never read as approved."""
    violations: list[PredictionViolation] = []
    requirement_by_id = {
        requirement.requirement_id: requirement for requirement in requirements
    }
    for state in timeline.final_fulfillment:
        requirement = requirement_by_id[state.requirement_id]
        if (
            state.predicted_delivered_m3 + _VOLUME_TOLERANCE_M3
            < requirement.required_volume_m3
        ):
            violations.append(
                RequirementShortfallViolation(
                    requirement_id=state.requirement_id,
                    required_volume_m3=requirement.required_volume_m3,
                    predicted_delivered_m3=state.predicted_delivered_m3,
                    shortfall_m3=(
                        requirement.required_volume_m3
                        - state.predicted_delivered_m3
                    ),
                )
            )
        # No predicted-excess channel here: _route_network_step clamps
        # delivery at required_volume_m3 with zero attributed in-transit, so
        # the network simulation can never produce PREDICTED_EXCESS —
        # advertising the violation would be false assurance. Excess
        # accounting arrives with the ledger projection (roadmap PR 5.1).
    shortfall_steps: dict[str, list] = {}
    exceeded_steps: dict[str, list] = {}
    unavailable_steps: dict[str, list] = {}
    planned_m3: dict[str, float] = {}
    predicted_m3: dict[str, float] = {}
    for step in timeline.steps:
        for point in step.withdrawals:
            structure_id = point.structure_id
            planned_m3[structure_id] = planned_m3.get(structure_id, 0.0) + (
                point.planned_flow_m3s * timeline.timestep_seconds
            )
            predicted_m3[structure_id] = predicted_m3.get(
                structure_id, 0.0
            ) + (point.predicted_withdrawal_m3s * timeline.timestep_seconds)
            if point.shortfall_m3s > _FLOW_TOLERANCE_M3S:
                shortfall_steps.setdefault(structure_id, []).append(step)
            if (
                point.capacity_check_status
                is WithdrawalCapacityCheckStatus.EXCEEDS_CAPACITY
            ):
                exceeded_steps.setdefault(structure_id, []).append(
                    (step, point.planned_flow_m3s)
                )
            if (
                point.capacity_check_status
                is WithdrawalCapacityCheckStatus.UNAVAILABLE
                and point.planned_flow_m3s > 0.0
            ):
                unavailable_steps.setdefault(structure_id, []).append(
                    (step, point.planned_flow_m3s)
                )
    for structure_id, steps in sorted(shortfall_steps.items()):
        violations.append(
            WithdrawalShortfallViolation(
                structure_id=structure_id,
                first_at=steps[0].starts_at,
                steps=len(steps),
                planned_total_m3=planned_m3[structure_id],
                predicted_total_m3=predicted_m3[structure_id],
                shortfall_total_m3=(
                    planned_m3[structure_id] - predicted_m3[structure_id]
                ),
            )
        )
    for structure_id, offending in sorted(exceeded_steps.items()):
        violations.append(
            WithdrawalCapacityExceededViolation(
                structure_id=structure_id,
                first_at=offending[0][0].starts_at,
                steps=len(offending),
                maximum_planned_flow_m3s=max(
                    planned for _, planned in offending
                ),
                structure_max_flow_m3s=structure_max_flow_m3s[structure_id],
            )
        )
    for structure_id, offending in sorted(unavailable_steps.items()):
        violations.append(
            WithdrawalCapacityUnavailableViolation(
                structure_id=structure_id,
                first_at=offending[0][0].starts_at,
                steps=len(offending),
                maximum_planned_flow_m3s=max(
                    planned for _, planned in offending
                ),
            )
        )
    return tuple(
        sorted(
            violations,
            key=lambda violation: (
                violation.kind,
                getattr(violation, "requirement_id", "")
                or getattr(violation, "structure_id", ""),
            ),
        )
    )
