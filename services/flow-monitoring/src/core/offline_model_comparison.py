"""Offline hydraulic-simulator interchange and golden comparison contract."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
import math
from pathlib import Path
import re
from typing import cast

from .config_loader import ConfigError, load_strict_json_object
from .demand_contract import canonical_json, content_hash
from .network_topology import ROOT
from .network_transient import (
    BranchAllocation,
    GateFlowEvent,
    NetworkTimeline,
    NetworkTransientError,
    OperatorWithdrawalEvent,
    SectionRequirement,
    route_gate_events,
    route_operator_withdrawal_events,
)
from .reach_response import ResponseMember
from .routing_topology import (
    RoutingElement,
    RoutingGeometryStatus,
    RoutingRole,
    RoutingTopology,
    build_routing_topology,
    routing_topology_payload,
)

__all__ = [
    "ComparisonStatus",
    "ComparisonTolerance",
    "GoldenComparisonReport",
    "OfflineModelComparisonError",
    "OFFLINE_SAMPLE_SEMANTICS",
    "OfflineReferenceResult",
    "OfflineReferenceSample",
    "OfflineSimulationCase",
    "ReachComparison",
    "build_golden_comparison_report",
    "build_offline_simulation_case",
    "golden_comparison_report_payload",
    "load_offline_reference_result",
    "load_offline_simulation_case",
    "offline_simulation_case_payload",
    "write_golden_comparison_report",
    "write_offline_simulation_case",
]


class OfflineModelComparisonError(ValueError):
    """An offline interchange artifact violates its comparison contract."""


class ComparisonStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"


_CASE_KEYS = {
    "schema_version",
    "case_id",
    "model_snapshot_id",
    "model_release_id",
    "model_release_content_hash",
    "member",
    "sample_semantics",
    "config_sha256",
    "routing_topology",
    "withdrawal_events",
    "withdrawal_structure_max_flow_m3s",
    "initial_state_kind",
    "starts_at",
    "ends_at",
    "timestep_seconds",
    "gate_events",
    "requirements",
    "branch_allocations",
    "content_hash",
}
_REFERENCE_KEYS = {
    "schema_version",
    "case_id",
    "case_content_hash",
    "evidence_class",
    "sample_semantics",
    "simulator",
    "validates_real_canal_behavior",
    "samples",
    "content_hash",
}
_CONFIG_KEYS = {
    "network",
    "canal_geometry",
    "gate_calibrations",
    "geometry_coverage",
    "routing_topology",
}
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_INITIAL_STATE_KIND = "dry"
_REFERENCE_EVIDENCE_CLASS = "offline_high_fidelity_simulation"
_REPORT_KIND = "offline_golden_comparison"
OFFLINE_SAMPLE_SEMANTICS = "mean_outflow_m3s_for_interval_ending_at_sampled_at"


@dataclass(frozen=True)
class OfflineSimulationCase:
    schema_version: int
    case_id: str
    model_snapshot_id: str
    model_release_id: str
    model_release_content_hash: str
    member: ResponseMember
    config_sha256: tuple[tuple[str, str], ...]
    routing_topology: RoutingTopology
    withdrawal_events: tuple[OperatorWithdrawalEvent, ...]
    withdrawal_structure_max_flow_m3s: tuple[tuple[str, float | None], ...]
    initial_state_kind: str
    starts_at: datetime
    ends_at: datetime
    timestep_seconds: float
    gate_events: tuple[GateFlowEvent, ...]
    requirements: tuple[SectionRequirement, ...]
    branch_allocations: tuple[BranchAllocation, ...]
    content_hash: str


@dataclass(frozen=True)
class OfflineReferenceSample:
    sampled_at: datetime
    reach_id: str
    outflow_m3s: float


@dataclass(frozen=True)
class OfflineReferenceResult:
    schema_version: int
    case_id: str
    case_content_hash: str
    evidence_class: str
    simulator_id: str
    simulator_version: str
    source_sha256: str
    validates_real_canal_behavior: bool
    samples: tuple[OfflineReferenceSample, ...]
    content_hash: str


@dataclass(frozen=True)
class ComparisonTolerance:
    maximum_flow_error_m3s: float
    maximum_volume_error_m3: float
    maximum_arrival_time_error_seconds: float
    arrival_flow_threshold_m3s: float


@dataclass(frozen=True)
class ReachComparison:
    reach_id: str
    sample_count: int
    maximum_absolute_flow_error_m3s: float
    root_mean_square_flow_error_m3s: float
    candidate_volume_m3: float
    reference_volume_m3: float
    absolute_volume_error_m3: float
    candidate_arrival_at: datetime | None
    reference_arrival_at: datetime | None
    arrival_time_error_seconds: float | None
    passed: bool


@dataclass(frozen=True)
class GoldenComparisonReport:
    schema_version: int
    report_kind: str
    status: ComparisonStatus
    software_verification_only: bool
    validates_real_canal_behavior: bool
    case_id: str
    case_content_hash: str
    model_snapshot_id: str
    model_release_id: str
    model_release_content_hash: str
    member: ResponseMember
    candidate_source_sha256: str
    candidate_result_hash: str
    reference_result_hash: str
    reference_simulator_id: str
    reference_simulator_version: str
    reference_source_sha256: str
    tolerance: ComparisonTolerance
    compared_reaches: int
    compared_samples: int
    failing_reaches: tuple[str, ...]
    reach_comparisons: tuple[ReachComparison, ...]
    content_hash: str


def build_offline_simulation_case(
    case_id: str,
    model_snapshot_id: str,
    model_release_id: str,
    model_release_content_hash: str,
    member: ResponseMember,
    config_sha256: dict[str, str],
    routing_topology: RoutingTopology,
    starts_at: datetime,
    ends_at: datetime,
    timestep_seconds: float,
    gate_events: tuple[GateFlowEvent, ...],
    withdrawal_events: tuple[OperatorWithdrawalEvent, ...],
    withdrawal_structure_max_flow_m3s: dict[str, float | None],
    requirements: tuple[SectionRequirement, ...],
    branch_allocations: tuple[BranchAllocation, ...],
) -> OfflineSimulationCase:
    _validate_non_blank(case_id, "case_id")
    _validate_sha256(model_snapshot_id, "model_snapshot_id")
    _validate_non_blank(model_release_id, "model_release_id")
    _validate_sha256(model_release_content_hash, "model_release_content_hash")
    if not isinstance(member, ResponseMember):
        raise OfflineModelComparisonError("member must be a ResponseMember")
    normalized_config = _normalize_config_sha256(config_sha256)
    if not isinstance(routing_topology, RoutingTopology):
        raise OfflineModelComparisonError(
            "routing_topology must be a typed RoutingTopology"
        )
    allocation_edges = routing_topology.allocation_edges()
    _validate_timeline_bounds(starts_at, ends_at, timestep_seconds)
    normalized_events = _normalize_gate_events(
        gate_events, starts_at, ends_at, timestep_seconds
    )
    normalized_withdrawal_events = _normalize_withdrawal_events(
        withdrawal_events,
        routing_topology,
        starts_at,
        ends_at,
        timestep_seconds,
    )
    normalized_capacity = _normalize_withdrawal_capacity(
        withdrawal_structure_max_flow_m3s, routing_topology
    )
    normalized_requirements = _normalize_requirements(
        requirements,
        routing_topology.canonical_gate_node_ids()
        - set(routing_topology.withdrawal_structure_node_ids()),
        starts_at,
        ends_at,
        timestep_seconds,
    )
    normalized_allocations = _normalize_branch_allocations(
        branch_allocations, allocation_edges
    )
    case = OfflineSimulationCase(
        schema_version=3,
        case_id=case_id.strip(),
        model_snapshot_id=model_snapshot_id,
        model_release_id=model_release_id.strip(),
        model_release_content_hash=model_release_content_hash,
        member=member,
        config_sha256=normalized_config,
        routing_topology=routing_topology,
        withdrawal_events=normalized_withdrawal_events,
        withdrawal_structure_max_flow_m3s=normalized_capacity,
        initial_state_kind=_INITIAL_STATE_KIND,
        starts_at=starts_at.astimezone(timezone.utc),
        ends_at=ends_at.astimezone(timezone.utc),
        timestep_seconds=float(timestep_seconds),
        gate_events=normalized_events,
        requirements=normalized_requirements,
        branch_allocations=normalized_allocations,
        content_hash="0" * 64,
    )
    return replace(case, content_hash=content_hash(_case_payload(case, False)))


def offline_simulation_case_payload(case: OfflineSimulationCase) -> dict:
    _validate_case(case)
    return _case_payload(case, True)


def load_offline_simulation_case(path: str | Path) -> OfflineSimulationCase:
    data = _load_json(path)
    if _require_integer(data, "schema_version", "offline_case") != 3:
        raise OfflineModelComparisonError("offline_case.schema_version must be 3")
    _require_exact_keys(data, _CASE_KEYS, "offline_case")
    initial_state_kind = _require_string(data, "initial_state_kind", "offline_case")
    if initial_state_kind != _INITIAL_STATE_KIND:
        raise OfflineModelComparisonError("offline_case.initial_state_kind must be dry")
    member_value = _require_string(data, "member", "offline_case")
    _require_literal(
        data,
        "sample_semantics",
        OFFLINE_SAMPLE_SEMANTICS,
        "offline_case",
    )
    try:
        member = ResponseMember(member_value)
    except ValueError as exc:
        raise OfflineModelComparisonError(
            f"offline_case.member is unknown: {member_value!r}"
        ) from exc
    case = build_offline_simulation_case(
        case_id=_require_string(data, "case_id", "offline_case"),
        model_snapshot_id=_require_string(data, "model_snapshot_id", "offline_case"),
        model_release_id=_require_string(data, "model_release_id", "offline_case"),
        model_release_content_hash=_require_string(
            data, "model_release_content_hash", "offline_case"
        ),
        member=member,
        config_sha256=_require_object(data, "config_sha256", "offline_case"),
        routing_topology=_parse_routing_topology(
            _require_object(data, "routing_topology", "offline_case")
        ),
        withdrawal_events=tuple(
            _parse_withdrawal_event(value, index)
            for index, value in enumerate(
                _require_array(data, "withdrawal_events", "offline_case")
            )
        ),
        withdrawal_structure_max_flow_m3s=_require_object(
            data, "withdrawal_structure_max_flow_m3s", "offline_case"
        ),
        starts_at=_parse_datetime(
            _require_string(data, "starts_at", "offline_case"),
            "offline_case.starts_at",
        ),
        ends_at=_parse_datetime(
            _require_string(data, "ends_at", "offline_case"),
            "offline_case.ends_at",
        ),
        timestep_seconds=_require_number(data, "timestep_seconds", "offline_case"),
        gate_events=tuple(
            _parse_gate_event(value, index)
            for index, value in enumerate(
                _require_array(data, "gate_events", "offline_case")
            )
        ),
        requirements=tuple(
            _parse_requirement(value, index)
            for index, value in enumerate(
                _require_array(data, "requirements", "offline_case")
            )
        ),
        branch_allocations=tuple(
            _parse_branch_allocation(value, index)
            for index, value in enumerate(
                _require_array(data, "branch_allocations", "offline_case")
            )
        ),
    )
    declared_hash = _require_string(data, "content_hash", "offline_case")
    _validate_sha256(declared_hash, "offline_case.content_hash")
    if declared_hash != case.content_hash:
        raise OfflineModelComparisonError(
            f"offline_case content_hash drift: declared {declared_hash!r}, "
            f"expected {case.content_hash!r}"
        )
    return case


def write_offline_simulation_case(
    path: str | Path, case: OfflineSimulationCase
) -> None:
    _write_json(path, offline_simulation_case_payload(case))


def load_offline_reference_result(
    path: str | Path, case: OfflineSimulationCase
) -> OfflineReferenceResult:
    _validate_case(case)
    data = _load_json(path)
    _require_exact_keys(data, _REFERENCE_KEYS, "offline_reference")
    simulator = _require_object(data, "simulator", "offline_reference")
    _require_literal(
        data,
        "sample_semantics",
        OFFLINE_SAMPLE_SEMANTICS,
        "offline_reference",
    )
    _require_exact_keys(
        simulator,
        {"simulator_id", "simulator_version", "source_sha256"},
        "offline_reference.simulator",
    )
    result = OfflineReferenceResult(
        schema_version=_require_integer(data, "schema_version", "offline_reference"),
        case_id=_require_string(data, "case_id", "offline_reference"),
        case_content_hash=_require_string(
            data, "case_content_hash", "offline_reference"
        ),
        evidence_class=_require_string(data, "evidence_class", "offline_reference"),
        simulator_id=_require_string(
            simulator, "simulator_id", "offline_reference.simulator"
        ),
        simulator_version=_require_string(
            simulator, "simulator_version", "offline_reference.simulator"
        ),
        source_sha256=_require_string(
            simulator, "source_sha256", "offline_reference.simulator"
        ),
        validates_real_canal_behavior=_require_boolean(
            data, "validates_real_canal_behavior", "offline_reference"
        ),
        samples=tuple(
            sorted(
                (
                    _parse_reference_sample(value, index)
                    for index, value in enumerate(
                        _require_array(data, "samples", "offline_reference")
                    )
                ),
                key=lambda sample: (sample.reach_id, sample.sampled_at),
            )
        ),
        content_hash=_require_string(data, "content_hash", "offline_reference"),
    )
    _validate_reference_result(result, case)
    return result


def build_golden_comparison_report(
    case: OfflineSimulationCase,
    candidate: NetworkTimeline,
    reference: OfflineReferenceResult,
    tolerance: ComparisonTolerance,
    candidate_source_sha256: str,
) -> GoldenComparisonReport:
    _validate_case(case)
    _validate_reference_result(reference, case)
    _validate_tolerance(tolerance)
    _validate_sha256(candidate_source_sha256, "candidate_source_sha256")
    if candidate_source_sha256 == reference.source_sha256:
        raise OfflineModelComparisonError(
            "offline reference must be independent from the candidate source"
        )
    candidate_samples = _candidate_samples(case, candidate)
    candidate_hash = content_hash(
        {
            "case_id": case.case_id,
            "case_content_hash": case.content_hash,
            "model_release_id": candidate.model_release_id,
            "member": candidate.member.value,
            "source_sha256": candidate_source_sha256,
            "samples": [_sample_payload(sample) for sample in candidate_samples],
        }
    )
    candidate_by_reach = _samples_by_reach(candidate_samples)
    reference_by_reach = _samples_by_reach(reference.samples)
    comparisons = tuple(
        _compare_reach(
            reach_id,
            candidate_by_reach[reach_id],
            reference_by_reach[reach_id],
            case.timestep_seconds,
            tolerance,
        )
        for reach_id in sorted(candidate_by_reach)
    )
    failing_reaches = tuple(
        comparison.reach_id for comparison in comparisons if not comparison.passed
    )
    report = GoldenComparisonReport(
        schema_version=2,
        report_kind=_REPORT_KIND,
        status=(
            ComparisonStatus.PASSED if not failing_reaches else ComparisonStatus.FAILED
        ),
        software_verification_only=True,
        validates_real_canal_behavior=False,
        case_id=case.case_id,
        case_content_hash=case.content_hash,
        model_snapshot_id=case.model_snapshot_id,
        model_release_id=case.model_release_id,
        model_release_content_hash=case.model_release_content_hash,
        member=case.member,
        candidate_source_sha256=candidate_source_sha256,
        candidate_result_hash=candidate_hash,
        reference_result_hash=reference.content_hash,
        reference_simulator_id=reference.simulator_id,
        reference_simulator_version=reference.simulator_version,
        reference_source_sha256=reference.source_sha256,
        tolerance=tolerance,
        compared_reaches=len(comparisons),
        compared_samples=len(candidate_samples),
        failing_reaches=failing_reaches,
        reach_comparisons=comparisons,
        content_hash="0" * 64,
    )
    return replace(
        report,
        content_hash=content_hash(_report_payload(report, False)),
    )


def golden_comparison_report_payload(report: GoldenComparisonReport) -> dict:
    _validate_report(report)
    return _report_payload(report, True)


def write_golden_comparison_report(
    path: str | Path, report: GoldenComparisonReport
) -> None:
    _write_json(path, golden_comparison_report_payload(report))


def _case_payload(case: OfflineSimulationCase, include_hash: bool) -> dict:
    payload = {
        "schema_version": case.schema_version,
        "case_id": case.case_id,
        "model_snapshot_id": case.model_snapshot_id,
        "model_release_id": case.model_release_id,
        "model_release_content_hash": case.model_release_content_hash,
        "member": case.member.value,
        "sample_semantics": OFFLINE_SAMPLE_SEMANTICS,
        "config_sha256": dict(case.config_sha256),
        "routing_topology": {
            "schema_version": case.routing_topology.schema_version,
            "source_sha256": case.routing_topology.source_sha256,
            "content_hash": case.routing_topology.content_hash,
            "elements": routing_topology_payload(case.routing_topology)[
                "elements"
            ],
        },
        "withdrawal_events": [
            {
                "structure_id": event.structure_id,
                "effective_at": _format_datetime(event.effective_at),
                "planned_flow_m3s": event.planned_flow_m3s,
                "purpose": event.purpose,
                "operator_reference": event.operator_reference,
            }
            for event in case.withdrawal_events
        ],
        "withdrawal_structure_max_flow_m3s": dict(
            case.withdrawal_structure_max_flow_m3s
        ),
        "initial_state_kind": case.initial_state_kind,
        "starts_at": _format_datetime(case.starts_at),
        "ends_at": _format_datetime(case.ends_at),
        "timestep_seconds": case.timestep_seconds,
        "gate_events": [
            {
                "node_id": event.node_id,
                "effective_at": _format_datetime(event.effective_at),
                "flow_m3s": event.flow_m3s,
            }
            for event in case.gate_events
        ],
        "requirements": [
            {
                "requirement_id": requirement.requirement_id,
                "section_id": requirement.section_id,
                "delivery_node_id": requirement.delivery_node_id,
                "window_start": _format_datetime(requirement.window_start),
                "window_end": _format_datetime(requirement.window_end),
                "required_volume_m3": requirement.required_volume_m3,
                "maximum_delivery_m3s": requirement.maximum_delivery_m3s,
                "approved_excess_m3": requirement.approved_excess_m3,
            }
            for requirement in case.requirements
        ],
        "branch_allocations": [
            {
                "upstream_node_id": allocation.upstream_node_id,
                "downstream_node_id": allocation.downstream_node_id,
                "fraction": allocation.fraction,
            }
            for allocation in case.branch_allocations
        ],
    }
    if include_hash:
        payload["content_hash"] = case.content_hash
    return payload


def _reference_payload(result: OfflineReferenceResult, include_hash: bool) -> dict:
    payload = {
        "schema_version": result.schema_version,
        "case_id": result.case_id,
        "case_content_hash": result.case_content_hash,
        "evidence_class": result.evidence_class,
        "sample_semantics": OFFLINE_SAMPLE_SEMANTICS,
        "simulator": {
            "simulator_id": result.simulator_id,
            "simulator_version": result.simulator_version,
            "source_sha256": result.source_sha256,
        },
        "validates_real_canal_behavior": result.validates_real_canal_behavior,
        "samples": [_sample_payload(sample) for sample in result.samples],
    }
    if include_hash:
        payload["content_hash"] = result.content_hash
    return payload


def _report_payload(report: GoldenComparisonReport, include_hash: bool) -> dict:
    payload = {
        "schema_version": report.schema_version,
        "report_kind": report.report_kind,
        "status": report.status.value,
        "software_verification_only": report.software_verification_only,
        "validates_real_canal_behavior": report.validates_real_canal_behavior,
        "sample_semantics": OFFLINE_SAMPLE_SEMANTICS,
        "case": {
            "case_id": report.case_id,
            "content_hash": report.case_content_hash,
            "model_snapshot_id": report.model_snapshot_id,
            "model_release_id": report.model_release_id,
            "model_release_content_hash": report.model_release_content_hash,
            "member": report.member.value,
        },
        "candidate": {
            "source_sha256": report.candidate_source_sha256,
            "result_hash": report.candidate_result_hash,
        },
        "reference": {
            "result_hash": report.reference_result_hash,
            "simulator_id": report.reference_simulator_id,
            "simulator_version": report.reference_simulator_version,
            "source_sha256": report.reference_source_sha256,
        },
        "tolerance": {
            "maximum_flow_error_m3s": report.tolerance.maximum_flow_error_m3s,
            "maximum_volume_error_m3": report.tolerance.maximum_volume_error_m3,
            "maximum_arrival_time_error_seconds": (
                report.tolerance.maximum_arrival_time_error_seconds
            ),
            "arrival_flow_threshold_m3s": (report.tolerance.arrival_flow_threshold_m3s),
        },
        "summary": {
            "compared_reaches": report.compared_reaches,
            "compared_samples": report.compared_samples,
            "failing_reaches": list(report.failing_reaches),
        },
        "reach_comparisons": [
            {
                "reach_id": comparison.reach_id,
                "sample_count": comparison.sample_count,
                "maximum_absolute_flow_error_m3s": (
                    comparison.maximum_absolute_flow_error_m3s
                ),
                "root_mean_square_flow_error_m3s": (
                    comparison.root_mean_square_flow_error_m3s
                ),
                "candidate_volume_m3": comparison.candidate_volume_m3,
                "reference_volume_m3": comparison.reference_volume_m3,
                "absolute_volume_error_m3": comparison.absolute_volume_error_m3,
                "candidate_arrival_at": _format_optional_datetime(
                    comparison.candidate_arrival_at
                ),
                "reference_arrival_at": _format_optional_datetime(
                    comparison.reference_arrival_at
                ),
                "arrival_time_error_seconds": (comparison.arrival_time_error_seconds),
                "passed": comparison.passed,
            }
            for comparison in report.reach_comparisons
        ],
    }
    if include_hash:
        payload["content_hash"] = report.content_hash
    return payload


def _sample_payload(sample: OfflineReferenceSample) -> dict:
    return {
        "sampled_at": _format_datetime(sample.sampled_at),
        "reach_id": sample.reach_id,
        "outflow_m3s": sample.outflow_m3s,
    }


def _validate_case(case: OfflineSimulationCase) -> None:
    rebuilt = build_offline_simulation_case(
        case.case_id,
        case.model_snapshot_id,
        case.model_release_id,
        case.model_release_content_hash,
        case.member,
        dict(case.config_sha256),
        case.routing_topology,
        case.starts_at,
        case.ends_at,
        case.timestep_seconds,
        case.gate_events,
        case.withdrawal_events,
        dict(case.withdrawal_structure_max_flow_m3s),
        case.requirements,
        case.branch_allocations,
    )
    if case.schema_version != 3:
        raise OfflineModelComparisonError("offline case schema_version must be 3")
    if case.initial_state_kind != _INITIAL_STATE_KIND:
        raise OfflineModelComparisonError("offline case initial_state_kind must be dry")
    _validate_sha256(case.content_hash, "offline case content_hash")
    if case != rebuilt:
        raise OfflineModelComparisonError("offline case content_hash or ordering drift")


def _normalize_withdrawal_events(
    withdrawal_events: tuple[OperatorWithdrawalEvent, ...],
    routing_topology: RoutingTopology,
    starts_at: datetime,
    ends_at: datetime,
    timestep_seconds: float,
) -> tuple[OperatorWithdrawalEvent, ...]:
    if not isinstance(withdrawal_events, tuple):
        raise OfflineModelComparisonError(
            "withdrawal_events must be an immutable tuple"
        )
    try:
        route_operator_withdrawal_events(
            withdrawal_events,
            frozenset(routing_topology.withdrawal_structure_node_ids()),
            starts_at,
            ends_at,
            timestep_seconds,
        )
    except NetworkTransientError as exc:
        raise OfflineModelComparisonError(str(exc)) from exc
    normalized = [
        OperatorWithdrawalEvent(
            structure_id=event.structure_id,
            effective_at=event.effective_at.astimezone(timezone.utc),
            planned_flow_m3s=float(event.planned_flow_m3s),
            purpose=event.purpose.strip(),
            operator_reference=(
                None
                if event.operator_reference is None
                else event.operator_reference.strip()
            ),
        )
        for event in withdrawal_events
    ]
    normalized.sort(key=lambda event: (event.effective_at, event.structure_id))
    return tuple(normalized)


def _normalize_withdrawal_capacity(
    withdrawal_structure_max_flow_m3s: dict[str, float | None],
    routing_topology: RoutingTopology,
) -> tuple[tuple[str, float | None], ...]:
    if not isinstance(withdrawal_structure_max_flow_m3s, dict):
        raise OfflineModelComparisonError(
            "withdrawal_structure_max_flow_m3s must be a dict"
        )
    expected = set(routing_topology.withdrawal_structure_node_ids())
    if set(withdrawal_structure_max_flow_m3s) != expected:
        raise OfflineModelComparisonError(
            "withdrawal_structure_max_flow_m3s coverage must exactly equal "
            f"the case withdrawal structures {sorted(expected)!r}"
        )
    for structure_id, q_max in withdrawal_structure_max_flow_m3s.items():
        if q_max is None:
            continue
        if (
            isinstance(q_max, bool)
            or not isinstance(q_max, (int, float))
            or not math.isfinite(q_max)
            or q_max <= 0.0
        ):
            raise OfflineModelComparisonError(
                f"withdrawal capacity for {structure_id!r} must be null or a "
                "positive finite flow"
            )
    return tuple(
        sorted(
            (structure_id, None if q_max is None else float(q_max))
            for structure_id, q_max in withdrawal_structure_max_flow_m3s.items()
        )
    )


def _parse_withdrawal_event(value: object, index: int) -> OperatorWithdrawalEvent:
    path = f"offline_case.withdrawal_events[{index}]"
    data = _as_object(value, path)
    _require_exact_keys(
        data,
        {
            "structure_id",
            "effective_at",
            "planned_flow_m3s",
            "purpose",
            "operator_reference",
        },
        path,
    )
    operator_reference = data.get("operator_reference")
    if operator_reference is not None and not isinstance(operator_reference, str):
        raise OfflineModelComparisonError(
            f"{path}.operator_reference must be a string or null"
        )
    return OperatorWithdrawalEvent(
        structure_id=_require_string(data, "structure_id", path),
        effective_at=_parse_datetime(
            _require_string(data, "effective_at", path), f"{path}.effective_at"
        ),
        planned_flow_m3s=_require_number(data, "planned_flow_m3s", path),
        purpose=_require_string(data, "purpose", path),
        operator_reference=operator_reference,
    )


def _normalize_config_sha256(
    config_sha256: dict[str, str],
) -> tuple[tuple[str, str], ...]:
    if not isinstance(config_sha256, dict) or set(config_sha256) != _CONFIG_KEYS:
        raise OfflineModelComparisonError(
            f"config_sha256 must contain exactly {sorted(_CONFIG_KEYS)}"
        )
    for key, value in config_sha256.items():
        _validate_sha256(value, f"config_sha256.{key}")
    return tuple(sorted(config_sha256.items()))


def _validate_timeline_bounds(
    starts_at: datetime, ends_at: datetime, timestep_seconds: float
) -> None:
    _validate_aware(starts_at, "starts_at")
    _validate_aware(ends_at, "ends_at")
    _validate_positive(timestep_seconds, "timestep_seconds")
    duration_seconds = (ends_at - starts_at).total_seconds()
    if duration_seconds <= 0.0:
        raise OfflineModelComparisonError("ends_at must be after starts_at")
    step_count = duration_seconds / timestep_seconds
    if not math.isclose(step_count, round(step_count), rel_tol=0.0, abs_tol=1e-9):
        raise OfflineModelComparisonError(
            "simulation horizon must be aligned to timestep_seconds"
        )


def _normalize_gate_events(
    gate_events: tuple[GateFlowEvent, ...],
    starts_at: datetime,
    ends_at: datetime,
    timestep_seconds: float,
) -> tuple[GateFlowEvent, ...]:
    if not isinstance(gate_events, tuple):
        raise OfflineModelComparisonError("gate_events must be an immutable tuple")
    try:
        route_gate_events(gate_events, starts_at, ends_at, timestep_seconds)
    except NetworkTransientError as exc:
        raise OfflineModelComparisonError(str(exc)) from exc
    normalized = tuple(
        GateFlowEvent(
            node_id=event.node_id.strip(),
            effective_at=event.effective_at.astimezone(timezone.utc),
            flow_m3s=float(event.flow_m3s),
        )
        for event in gate_events
    )
    non_root_nodes = sorted(
        {event.node_id for event in normalized if event.node_id != ROOT}
    )
    if non_root_nodes:
        raise OfflineModelComparisonError(
            "gate events may inject water only at the network root; "
            f"got {non_root_nodes!r}"
        )
    return tuple(
        sorted(
            normalized,
            key=lambda event: (event.effective_at, event.node_id),
        )
    )


def _normalize_requirements(
    requirements: tuple[SectionRequirement, ...],
    gate_node_ids: frozenset[str] | set[str],
    starts_at: datetime,
    ends_at: datetime,
    timestep_seconds: float,
) -> tuple[SectionRequirement, ...]:
    if not isinstance(requirements, tuple):
        raise OfflineModelComparisonError("requirements must be an immutable tuple")
    network_nodes = gate_node_ids
    seen = set()
    normalized = []
    for requirement in requirements:
        _validate_non_blank(requirement.requirement_id, "requirement_id")
        _validate_non_blank(requirement.section_id, "section_id")
        _validate_non_blank(requirement.delivery_node_id, "delivery_node_id")
        requirement_id = requirement.requirement_id.strip()
        section_id = requirement.section_id.strip()
        delivery_node_id = requirement.delivery_node_id.strip()
        if requirement_id in seen:
            raise OfflineModelComparisonError("duplicate requirement_id")
        seen.add(requirement_id)
        if delivery_node_id not in network_nodes:
            raise OfflineModelComparisonError(
                f"requirement delivery node {delivery_node_id!r} is not a "
                "deliverable canal gate; withdrawal structure releases are "
                "operator withdrawal events, not section deliveries"
            )
        _validate_aware(requirement.window_start, "requirement.window_start")
        _validate_aware(requirement.window_end, "requirement.window_end")
        if (
            not starts_at
            <= requirement.window_start
            < requirement.window_end
            <= ends_at
        ):
            raise OfflineModelComparisonError(
                "requirement window must be within the simulation horizon"
            )
        _validate_aligned(
            requirement.window_start,
            starts_at,
            timestep_seconds,
            "requirement.window_start",
        )
        _validate_aligned(
            requirement.window_end,
            starts_at,
            timestep_seconds,
            "requirement.window_end",
        )
        _validate_non_negative(
            requirement.required_volume_m3, "requirement.required_volume_m3"
        )
        _validate_positive(
            requirement.maximum_delivery_m3s,
            "requirement.maximum_delivery_m3s",
        )
        _validate_non_negative(
            requirement.approved_excess_m3, "requirement.approved_excess_m3"
        )
        normalized.append(
            SectionRequirement(
                requirement_id=requirement_id,
                section_id=section_id,
                delivery_node_id=delivery_node_id,
                window_start=requirement.window_start.astimezone(timezone.utc),
                window_end=requirement.window_end.astimezone(timezone.utc),
                required_volume_m3=float(requirement.required_volume_m3),
                maximum_delivery_m3s=float(requirement.maximum_delivery_m3s),
                approved_excess_m3=float(requirement.approved_excess_m3),
            )
        )
    return tuple(sorted(normalized, key=lambda item: item.requirement_id))


def _normalize_branch_allocations(
    branch_allocations: tuple[BranchAllocation, ...],
    network_edges: tuple[tuple[str, str], ...],
) -> tuple[BranchAllocation, ...]:
    if not isinstance(branch_allocations, tuple):
        raise OfflineModelComparisonError(
            "branch_allocations must be an immutable tuple"
        )
    children: dict[str, list[str]] = defaultdict(list)
    for upstream, downstream in network_edges:
        children[upstream].append(downstream)
    expected = {
        (upstream, downstream)
        for upstream, downstream_nodes in children.items()
        if len(downstream_nodes) > 1
        for downstream in downstream_nodes
    }
    actual = set()
    fractions: dict[str, float] = defaultdict(float)
    normalized = []
    for allocation in branch_allocations:
        _validate_non_blank(
            allocation.upstream_node_id, "branch allocation upstream_node_id"
        )
        _validate_non_blank(
            allocation.downstream_node_id, "branch allocation downstream_node_id"
        )
        upstream = allocation.upstream_node_id.strip()
        downstream = allocation.downstream_node_id.strip()
        key = (upstream, downstream)
        if key in actual:
            raise OfflineModelComparisonError("duplicate branch allocation")
        actual.add(key)
        _validate_non_negative(allocation.fraction, "branch allocation fraction")
        if allocation.fraction > 1.0:
            raise OfflineModelComparisonError("branch allocation fraction must be <= 1")
        fractions[upstream] += allocation.fraction
        normalized.append(
            BranchAllocation(upstream, downstream, float(allocation.fraction))
        )
    if actual != expected:
        raise OfflineModelComparisonError(
            "branch allocation coverage must exactly match every branched edge"
        )
    for upstream in fractions:
        if not math.isclose(fractions[upstream], 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise OfflineModelComparisonError(
                f"branch allocations for {upstream!r} must sum to 1"
            )
    return tuple(
        sorted(
            normalized,
            key=lambda item: (item.upstream_node_id, item.downstream_node_id),
        )
    )


def _validate_reference_result(
    result: OfflineReferenceResult, case: OfflineSimulationCase
) -> None:
    if result.schema_version != 2:
        raise OfflineModelComparisonError("offline reference schema_version must be 2")
    if (result.case_id, result.case_content_hash) != (case.case_id, case.content_hash):
        raise OfflineModelComparisonError(
            "offline reference case lineage does not match the exported case"
        )
    if result.evidence_class != _REFERENCE_EVIDENCE_CLASS:
        raise OfflineModelComparisonError(
            "offline reference evidence_class must be " f"{_REFERENCE_EVIDENCE_CLASS}"
        )
    _validate_non_blank(result.simulator_id, "simulator_id")
    _validate_non_blank(result.simulator_version, "simulator_version")
    _validate_sha256(result.source_sha256, "source_sha256")
    if not isinstance(result.validates_real_canal_behavior, bool):
        raise OfflineModelComparisonError(
            "validates_real_canal_behavior must be a boolean"
        )
    if result.validates_real_canal_behavior:
        raise OfflineModelComparisonError(
            "validates_real_canal_behavior must be false for offline comparison"
        )
    expected_keys = _expected_sample_keys(case)
    actual_keys = [(sample.reach_id, sample.sampled_at) for sample in result.samples]
    if len(set(actual_keys)) != len(actual_keys):
        raise OfflineModelComparisonError(
            "offline reference contains duplicate samples"
        )
    if set(actual_keys) != expected_keys:
        raise OfflineModelComparisonError(
            "offline reference sample coverage must exactly match every reach and timestep"
        )
    for sample in result.samples:
        _validate_non_negative(sample.outflow_m3s, "sample.outflow_m3s")
    _validate_sha256(result.content_hash, "offline reference content_hash")
    expected_hash = content_hash(_reference_payload(result, False))
    if result.content_hash != expected_hash:
        raise OfflineModelComparisonError(
            f"offline reference content_hash drift: declared {result.content_hash!r}, "
            f"expected {expected_hash!r}"
        )


def _candidate_samples(
    case: OfflineSimulationCase, candidate: NetworkTimeline
) -> tuple[OfflineReferenceSample, ...]:
    if candidate.model_release_id != case.model_release_id:
        raise OfflineModelComparisonError(
            "candidate model release does not match the offline case"
        )
    if candidate.member is not case.member:
        raise OfflineModelComparisonError(
            "candidate response member does not match the offline case member"
        )
    if (candidate.starts_at, candidate.ends_at) != (case.starts_at, case.ends_at):
        raise OfflineModelComparisonError(
            "candidate horizon does not match the offline case"
        )
    if candidate.timestep_seconds != case.timestep_seconds:
        raise OfflineModelComparisonError(
            "candidate timestep does not match the offline case"
        )
    step_count = round(
        (case.ends_at - case.starts_at).total_seconds() / case.timestep_seconds
    )
    expected_intervals = tuple(
        (
            case.starts_at + timedelta(seconds=index * case.timestep_seconds),
            case.starts_at + timedelta(seconds=(index + 1) * case.timestep_seconds),
        )
        for index in range(step_count)
    )
    if tuple((step.starts_at, step.ends_at) for step in candidate.steps) != (
        expected_intervals
    ):
        raise OfflineModelComparisonError(
            "candidate step intervals do not match the offline case"
        )
    samples = tuple(
        sorted(
            (
                OfflineReferenceSample(
                    sampled_at=step.ends_at,
                    reach_id=point.reach_id,
                    outflow_m3s=point.outflow_m3s,
                )
                for step in candidate.steps
                for point in step.reaches
            ),
            key=lambda sample: (sample.reach_id, sample.sampled_at),
        )
    )
    for sample in samples:
        _validate_non_negative(sample.outflow_m3s, "candidate outflow_m3s")
    actual_keys = {(sample.reach_id, sample.sampled_at) for sample in samples}
    if len(samples) != len(actual_keys) or actual_keys != _expected_sample_keys(case):
        raise OfflineModelComparisonError(
            "candidate sample coverage must exactly match every reach and timestep"
        )
    return samples


def _samples_by_reach(
    samples: tuple[OfflineReferenceSample, ...],
) -> dict[str, tuple[OfflineReferenceSample, ...]]:
    grouped: dict[str, list[OfflineReferenceSample]] = defaultdict(list)
    for sample in samples:
        grouped[sample.reach_id].append(sample)
    return {
        reach_id: tuple(sorted(values, key=lambda sample: sample.sampled_at))
        for reach_id, values in grouped.items()
    }


def _compare_reach(
    reach_id: str,
    candidate: tuple[OfflineReferenceSample, ...],
    reference: tuple[OfflineReferenceSample, ...],
    timestep_seconds: float,
    tolerance: ComparisonTolerance,
) -> ReachComparison:
    if tuple(sample.sampled_at for sample in candidate) != tuple(
        sample.sampled_at for sample in reference
    ):
        raise OfflineModelComparisonError(
            f"sample instants do not align for reach {reach_id!r}"
        )
    errors = tuple(
        candidate_sample.outflow_m3s - reference_sample.outflow_m3s
        for candidate_sample, reference_sample in zip(candidate, reference)
    )
    maximum_error = max(abs(error) for error in errors)
    root_mean_square_error = math.sqrt(
        sum(error * error for error in errors) / len(errors)
    )
    candidate_volume = sum(
        sample.outflow_m3s * timestep_seconds for sample in candidate
    )
    reference_volume = sum(
        sample.outflow_m3s * timestep_seconds for sample in reference
    )
    volume_error = abs(candidate_volume - reference_volume)
    candidate_arrival = _arrival_at(candidate, tolerance.arrival_flow_threshold_m3s)
    reference_arrival = _arrival_at(reference, tolerance.arrival_flow_threshold_m3s)
    arrival_error = _arrival_error_seconds(candidate_arrival, reference_arrival)
    arrival_passed = (candidate_arrival is None and reference_arrival is None) or (
        arrival_error is not None
        and arrival_error <= tolerance.maximum_arrival_time_error_seconds
    )
    passed = (
        maximum_error <= tolerance.maximum_flow_error_m3s
        and volume_error <= tolerance.maximum_volume_error_m3
        and arrival_passed
    )
    return ReachComparison(
        reach_id=reach_id,
        sample_count=len(candidate),
        maximum_absolute_flow_error_m3s=maximum_error,
        root_mean_square_flow_error_m3s=root_mean_square_error,
        candidate_volume_m3=candidate_volume,
        reference_volume_m3=reference_volume,
        absolute_volume_error_m3=volume_error,
        candidate_arrival_at=candidate_arrival,
        reference_arrival_at=reference_arrival,
        arrival_time_error_seconds=arrival_error,
        passed=passed,
    )


def _arrival_at(
    samples: tuple[OfflineReferenceSample, ...], threshold_m3s: float
) -> datetime | None:
    return next(
        (
            sample.sampled_at
            for sample in samples
            if sample.outflow_m3s >= threshold_m3s
        ),
        None,
    )


def _arrival_error_seconds(
    candidate: datetime | None, reference: datetime | None
) -> float | None:
    if candidate is None or reference is None:
        return None
    return abs((candidate - reference).total_seconds())


def _validate_tolerance(tolerance: ComparisonTolerance) -> None:
    if not isinstance(tolerance, ComparisonTolerance):
        raise OfflineModelComparisonError("tolerance must be a ComparisonTolerance")
    _validate_non_negative(tolerance.maximum_flow_error_m3s, "maximum_flow_error_m3s")
    _validate_non_negative(tolerance.maximum_volume_error_m3, "maximum_volume_error_m3")
    _validate_non_negative(
        tolerance.maximum_arrival_time_error_seconds,
        "maximum_arrival_time_error_seconds",
    )
    _validate_positive(
        tolerance.arrival_flow_threshold_m3s, "arrival_flow_threshold_m3s"
    )


def _validate_report(report: GoldenComparisonReport) -> None:
    if report.schema_version != 2 or report.report_kind != _REPORT_KIND:
        raise OfflineModelComparisonError("golden report schema or kind is invalid")
    if not isinstance(report.status, ComparisonStatus):
        raise OfflineModelComparisonError("golden report status is invalid")
    if report.software_verification_only is not True:
        raise OfflineModelComparisonError(
            "golden report software_verification_only must be true"
        )
    if report.validates_real_canal_behavior is not False:
        raise OfflineModelComparisonError(
            "golden report validates_real_canal_behavior must be false"
        )
    _validate_sha256(
        report.candidate_source_sha256, "golden report candidate_source_sha256"
    )
    if report.candidate_source_sha256 == report.reference_source_sha256:
        raise OfflineModelComparisonError(
            "golden report reference must be independent from the candidate source"
        )
    _validate_sha256(report.content_hash, "golden report content_hash")
    expected_hash = content_hash(_report_payload(report, False))
    if report.content_hash != expected_hash:
        raise OfflineModelComparisonError(
            f"golden report content_hash drift: declared {report.content_hash!r}, "
            f"expected {expected_hash!r}"
        )


def _expected_sample_keys(
    case: OfflineSimulationCase,
) -> set[tuple[str, datetime]]:
    step_count = round(
        (case.ends_at - case.starts_at).total_seconds() / case.timestep_seconds
    )
    sampled_at = tuple(
        case.starts_at + timedelta(seconds=(index + 1) * case.timestep_seconds)
        for index in range(step_count)
    )
    return {
        (reach_id, instant)
        for reach_id in case.routing_topology.transport_reach_ids()
        for instant in sampled_at
    }


def _parse_routing_topology(data: dict) -> RoutingTopology:
    path = "offline_case.routing_topology"
    _require_exact_keys(
        data,
        {"schema_version", "source_sha256", "content_hash", "elements"},
        path,
    )
    elements = tuple(
        _parse_routing_element(value, index)
        for index, value in enumerate(_require_array(data, "elements", path))
    )
    try:
        topology = build_routing_topology(
            elements, _require_string(data, "source_sha256", path)
        )
    except ValueError as exc:
        raise OfflineModelComparisonError(f"{path}: {exc}") from exc
    if data.get("schema_version") != topology.schema_version:
        raise OfflineModelComparisonError(
            f"{path}.schema_version must be {topology.schema_version}"
        )
    if data.get("content_hash") != topology.content_hash:
        raise OfflineModelComparisonError(
            f"{path}.content_hash drift: declared {data.get('content_hash')!r}, "
            f"expected {topology.content_hash!r}"
        )
    return topology


def _parse_routing_element(value: object, index: int) -> RoutingElement:
    path = f"offline_case.routing_topology.elements[{index}]"
    data = _as_object(value, path)
    _require_exact_keys(
        data,
        {
            "element_id",
            "upstream_node_id",
            "downstream_node_id",
            "role",
            "canonical_edges",
            "canal",
            "span_m",
            "geometry_status",
            "located_at_km",
        },
        path,
    )
    try:
        role = RoutingRole(_require_string(data, "role", path))
        geometry_status = RoutingGeometryStatus(
            _require_string(data, "geometry_status", path)
        )
    except ValueError as exc:
        raise OfflineModelComparisonError(f"{path}: {exc}") from exc
    canonical_edges = _require_array(data, "canonical_edges", path)
    if not canonical_edges or any(
        not isinstance(edge, list)
        or len(edge) != 2
        or any(not isinstance(node, str) or not node for node in edge)
        for edge in canonical_edges
    ):
        raise OfflineModelComparisonError(
            f"{path}.canonical_edges must be a non-empty list of node-id pairs"
        )
    canal = data.get("canal")
    if canal is not None and not isinstance(canal, str):
        raise OfflineModelComparisonError(f"{path}.canal must be a string or null")
    span_m = data.get("span_m")
    if span_m is not None and (
        isinstance(span_m, bool)
        or not isinstance(span_m, (int, float))
        or not math.isfinite(span_m)
    ):
        raise OfflineModelComparisonError(
            f"{path}.span_m must be a finite number or null"
        )
    located_at_km = data.get("located_at_km")
    if located_at_km is not None and not isinstance(located_at_km, str):
        raise OfflineModelComparisonError(
            f"{path}.located_at_km must be a string or null"
        )
    return RoutingElement(
        element_id=_require_string(data, "element_id", path),
        upstream_node_id=_require_string(data, "upstream_node_id", path),
        downstream_node_id=_require_string(data, "downstream_node_id", path),
        role=role,
        canonical_edges=tuple((edge[0], edge[1]) for edge in canonical_edges),
        canal=canal,
        span_m=None if span_m is None else float(span_m),
        geometry_status=geometry_status,
        located_at_km=located_at_km,
    )


def _parse_gate_event(value: object, index: int) -> GateFlowEvent:
    path = f"offline_case.gate_events[{index}]"
    data = _as_object(value, path)
    _require_exact_keys(data, {"node_id", "effective_at", "flow_m3s"}, path)
    return GateFlowEvent(
        node_id=_require_string(data, "node_id", path),
        effective_at=_parse_datetime(
            _require_string(data, "effective_at", path), f"{path}.effective_at"
        ),
        flow_m3s=_require_number(data, "flow_m3s", path),
    )


def _parse_requirement(value: object, index: int) -> SectionRequirement:
    path = f"offline_case.requirements[{index}]"
    data = _as_object(value, path)
    _require_exact_keys(
        data,
        {
            "requirement_id",
            "section_id",
            "delivery_node_id",
            "window_start",
            "window_end",
            "required_volume_m3",
            "maximum_delivery_m3s",
            "approved_excess_m3",
        },
        path,
    )
    return SectionRequirement(
        requirement_id=_require_string(data, "requirement_id", path),
        section_id=_require_string(data, "section_id", path),
        delivery_node_id=_require_string(data, "delivery_node_id", path),
        window_start=_parse_datetime(
            _require_string(data, "window_start", path), f"{path}.window_start"
        ),
        window_end=_parse_datetime(
            _require_string(data, "window_end", path), f"{path}.window_end"
        ),
        required_volume_m3=_require_number(data, "required_volume_m3", path),
        maximum_delivery_m3s=_require_number(data, "maximum_delivery_m3s", path),
        approved_excess_m3=_require_number(data, "approved_excess_m3", path),
    )


def _parse_branch_allocation(value: object, index: int) -> BranchAllocation:
    path = f"offline_case.branch_allocations[{index}]"
    data = _as_object(value, path)
    _require_exact_keys(
        data,
        {"upstream_node_id", "downstream_node_id", "fraction"},
        path,
    )
    return BranchAllocation(
        upstream_node_id=_require_string(data, "upstream_node_id", path),
        downstream_node_id=_require_string(data, "downstream_node_id", path),
        fraction=_require_number(data, "fraction", path),
    )


def _parse_reference_sample(value: object, index: int) -> OfflineReferenceSample:
    path = f"offline_reference.samples[{index}]"
    data = _as_object(value, path)
    _require_exact_keys(data, {"sampled_at", "reach_id", "outflow_m3s"}, path)
    return OfflineReferenceSample(
        sampled_at=_parse_datetime(
            _require_string(data, "sampled_at", path), f"{path}.sampled_at"
        ),
        reach_id=_require_string(data, "reach_id", path),
        outflow_m3s=_require_number(data, "outflow_m3s", path),
    )


def _load_json(path: str | Path) -> dict:
    try:
        return load_strict_json_object(str(path))
    except ConfigError as exc:
        raise OfflineModelComparisonError(str(exc)) from exc


def _write_json(path: str | Path, payload: dict) -> None:
    try:
        Path(path).write_text(canonical_json(payload) + "\n", encoding="utf-8")
    except OSError as exc:
        raise OfflineModelComparisonError(
            f"{path}: cannot write artifact: {exc}"
        ) from exc


def _require_exact_keys(data: dict, expected: set[str], path: str) -> None:
    actual = set(data)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise OfflineModelComparisonError(
            f"{path} keys differ; missing={missing}, unexpected={unexpected}"
        )


def _as_object(value: object, path: str) -> dict:
    if not isinstance(value, dict):
        raise OfflineModelComparisonError(f"{path} must be an object")
    return value


def _require_object(data: dict, key: str, path: str) -> dict:
    return _as_object(data.get(key), f"{path}.{key}")


def _require_array(data: dict, key: str, path: str) -> list:
    value = data.get(key)
    if not isinstance(value, list):
        raise OfflineModelComparisonError(f"{path}.{key} must be an array")
    return value


def _require_string(data: dict, key: str, path: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OfflineModelComparisonError(f"{path}.{key} must be a non-empty string")
    return value


def _require_literal(data: dict, key: str, expected: str, path: str) -> None:
    value = _require_string(data, key, path)
    if value != expected:
        raise OfflineModelComparisonError(
            f"{path}.{key} must be {expected!r}, got {value!r}"
        )


def _require_boolean(data: dict, key: str, path: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise OfflineModelComparisonError(f"{path}.{key} must be a boolean")
    return value


def _require_integer(data: dict, key: str, path: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise OfflineModelComparisonError(f"{path}.{key} must be an integer")
    return value


def _require_number(data: dict, key: str, path: str) -> float:
    value = cast(float, data.get(key))
    _validate_finite(value, f"{path}.{key}")
    return float(value)


def _parse_datetime(value: str, path: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OfflineModelComparisonError(
            f"{path} must be an ISO-8601 datetime"
        ) from exc
    _validate_aware(parsed, path)
    return parsed.astimezone(timezone.utc)


def _format_datetime(value: datetime) -> str:
    _validate_aware(value, "datetime")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _format_optional_datetime(value: datetime | None) -> str | None:
    return None if value is None else _format_datetime(value)


def _validate_aligned(
    value: datetime, starts_at: datetime, timestep_seconds: float, label: str
) -> None:
    offset = (value - starts_at).total_seconds() / timestep_seconds
    if not math.isclose(offset, round(offset), rel_tol=0.0, abs_tol=1e-9):
        raise OfflineModelComparisonError(
            f"{label} must be aligned to timestep_seconds"
        )


def _validate_non_blank(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise OfflineModelComparisonError(f"{label} must be a non-empty string")


def _validate_aware(value: datetime, label: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise OfflineModelComparisonError(f"{label} must be timezone-aware")


def _validate_finite(value: float, label: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise OfflineModelComparisonError(f"{label} must be a finite number")


def _validate_non_negative(value: float, label: str) -> None:
    _validate_finite(value, label)
    if value < 0.0:
        raise OfflineModelComparisonError(f"{label} must be >= 0")


def _validate_positive(value: float, label: str) -> None:
    _validate_finite(value, label)
    if value <= 0.0:
        raise OfflineModelComparisonError(f"{label} must be > 0")


def _validate_sha256(value: str, label: str) -> None:
    if not isinstance(value, str) or _SHA256_HEX.fullmatch(value) is None:
        raise OfflineModelComparisonError(
            f"{label} must be a lowercase SHA-256 hex digest"
        )


def _reach_id(upstream: str, downstream: str) -> str:
    return f"C_{upstream}_{downstream}"
