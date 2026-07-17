"""Deterministic engineering-prior model-release generation (PR 2.1c).

Turns the approved V1 hydraulic policy plus the canonical V3 artifacts
into a schema-v1 model release: 41 surveyed transport elements receive
Muskingum-Cunge-derived delay/dispersion surrogates, seepage-derived loss
fractions, and conservatively derated capacities; the 170 m outlet flume
stays explicitly unavailable. Every constant comes from the policy JSON —
a missing key raises instead of defaulting — and every member of every
distribution is produced by a named, physically consistent perturbation
bundle. Missing evidence is never invented.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from .config_loader import ConfigError
from .conveyance_loss import (
    OPERATING_DEPTH_FRAC,
    SEEPAGE_RATE_BY_LINING,
    _segment_seepage_m3s,
    parse_chainage_m,
    sections_by_edge_from_geometry,
    seepage_rate_for_lining,
)
from .model_release import (
    EvidenceClass,
    HydraulicModelRelease,
    ModelLineage,
    OperatingEnvelope,
    ParameterDistribution,
    ReachResponseParameters,
    SourceArtifact,
    UnavailableReach,
    model_release_content_hash,
    validate_model_release,
)
from .muskingum_cunge import (
    CascadeSection,
    MuskingumCungeError,
    TrapezoidSection,
    fit_t10_t90,
    flood_wave_celerity_m_s,
    route_cascade,
)
from .node_id import normalize_gate_id
from .routing_topology import RoutingGeometryStatus, RoutingRole, RoutingTopology

__all__ = [
    "EngineeringResponseError",
    "generate_engineering_model_release",
    "load_engineering_policy",
    "model_release_artifact_payload",
]

_MEMBER_NAMES = ("lower", "nominal", "upper")
_EVIDENCE_REFS = (
    "canal_geometry",
    "engineering_prior_policy",
    "gate_calibrations",
    "routing_topology",
)


class EngineeringResponseError(ValueError):
    """The policy and canonical evidence cannot yield a reviewed release."""


class ConveyanceExceededError(EngineeringResponseError):
    """Derived conveyance loss consumes the reference flow for one reach —
    that reach becomes explicitly unavailable, never a non-physical response."""


class HydraulicEvidenceError(EngineeringResponseError):
    """The approved policy cannot derive an admissible hydraulic state or a
    stable response for one reach — that reach becomes explicitly
    unavailable, never a fabricated response and never a whole-release
    abort."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EngineeringResponseError(message)


def _policy_get(data: dict, *path: str):
    cursor = data
    for key in path:
        if not isinstance(cursor, dict) or key not in cursor:
            raise EngineeringResponseError(
                f"engineering policy is missing required key {'.'.join(path)!r}"
            )
        cursor = cursor[key]
    return cursor


@dataclass(frozen=True)
class EngineeringPolicy:
    raw: dict

    def get(self, *path: str):
        return _policy_get(self.raw, *path)


def load_engineering_policy(data: dict) -> EngineeringPolicy:
    _require(isinstance(data, dict), "engineering policy must be a JSON object")
    _require(
        _policy_get(data, "schema_version") == 1,
        "engineering policy schema_version must be 1",
    )
    _require(
        _policy_get(data, "evidence_class") == "engineering_prior",
        "engineering policy evidence_class must be engineering_prior",
    )
    _require(
        _policy_get(data, "commandable") is False,
        "engineering policy must declare commandable false",
    )
    for member in _MEMBER_NAMES:
        _policy_get(data, "member_bundles", member)
    for perturbation in (
        "manning_n",
        "seepage_rate",
        "flow_to_state",
        "geometry_tolerance",
    ):
        spec = _policy_get(data, "perturbations", perturbation)
        _require(
            isinstance(spec, dict)
            and spec.get("kind") in ("relative", "multiplier"),
            f"perturbation {perturbation!r} must declare kind "
            "relative|multiplier",
        )
        for direction in ("lower", "upper"):
            magnitude = spec.get(direction)
            _require(
                isinstance(magnitude, (int, float))
                and not isinstance(magnitude, bool)
                and math.isfinite(magnitude),
                f"perturbation {perturbation!r} must declare finite numeric "
                f"{direction} magnitude",
            )
    return EngineeringPolicy(raw=data)


@dataclass(frozen=True)
class _SectionEvidence:
    from_km: str
    length_m: float
    bottom_width_m: float
    depth_m: float
    side_slope: float
    manning_n: float
    bed_slope: float
    lining_type: str | None
    q_max_m3s: float
    q_rotation_plan_m3s: float | None


def _sections_for_edge(
    canonical_edge: tuple[str, str], canal_geometry: dict
) -> list[_SectionEvidence]:
    sections = []
    normalized_edge = tuple(normalize_gate_id(node) for node in canonical_edge)
    for section in canal_geometry.get("canal_sections", ()):
        row_edge = (
            normalize_gate_id(section.get("from_node")),
            normalize_gate_id(section.get("to_node")),
        )
        if row_edge != normalized_edge:
            continue
        geometry = section.get("geometry", {})
        cross_section = geometry.get("cross_section", {})
        hydraulic = geometry.get("hydraulic_params", {})
        evidence = _SectionEvidence(
            from_km=section.get("from_km"),
            length_m=geometry.get("length_m"),
            bottom_width_m=cross_section.get("bottom_width_m"),
            depth_m=cross_section.get("depth_m"),
            side_slope=cross_section.get("side_slope"),
            manning_n=hydraulic.get("manning_n"),
            bed_slope=hydraulic.get("bed_slope"),
            lining_type=hydraulic.get("lining_type"),
            q_max_m3s=hydraulic.get("q_max"),
            q_rotation_plan_m3s=hydraulic.get("q_rotation_plan"),
        )
        for field_name in (
            "length_m",
            "bottom_width_m",
            "depth_m",
            "manning_n",
            "bed_slope",
            "q_max_m3s",
        ):
            value = getattr(evidence, field_name)
            _require(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                and value > 0.0,
                f"section {canonical_edge!r}@{evidence.from_km} field "
                f"{field_name} must be positive finite",
            )
        sections.append(evidence)
    sections.sort(key=lambda section: parse_chainage_m(section.from_km) or 0.0)
    return sections


def _section_reference_flow(section: _SectionEvidence, policy: EngineeringPolicy) -> float:
    rule = policy.get("reference_flow", "section_rule")
    _require(
        rule == "q_rotation_plan_else_fraction_of_q_max",
        f"unreviewed reference flow section rule {rule!r}",
    )
    if section.q_rotation_plan_m3s is not None:
        _require(
            isinstance(section.q_rotation_plan_m3s, (int, float))
            and not isinstance(section.q_rotation_plan_m3s, bool)
            and math.isfinite(section.q_rotation_plan_m3s)
            and section.q_rotation_plan_m3s > 0.0,
            "q_rotation_plan must be positive finite when present",
        )
        return float(section.q_rotation_plan_m3s)
    fraction = policy.get("reference_flow", "fallback_fraction_of_q_max")
    return float(fraction) * section.q_max_m3s


def _perturbed(value: float, spec: dict, direction: str | None) -> float:
    if direction is None:
        return value
    kind = spec.get("kind")
    magnitude = spec.get(direction)
    _require(
        kind in ("relative", "multiplier")
        and isinstance(magnitude, (int, float))
        and not isinstance(magnitude, bool),
        "perturbation spec must declare kind and lower/upper magnitudes",
    )
    if kind == "relative":
        return value * (1.0 + magnitude)
    return value * magnitude


def _seepage_m3s(
    section: _SectionEvidence,
    policy: EngineeringPolicy,
    geometry_scale: float,
    seepage_multiplier: float,
) -> float:
    lining = section.lining_type
    _require(
        lining is None or lining in SEEPAGE_RATE_BY_LINING,
        f"section lining_type {lining!r} is not a reviewed seepage class "
        f"{sorted(SEEPAGE_RATE_BY_LINING)}; refusing a silent fallback",
    )
    _require(
        policy.get("loss", "operating_depth_fraction") == OPERATING_DEPTH_FRAC,
        "policy operating_depth_fraction disagrees with the canonical "
        "conveyance-loss constant",
    )
    # Single B5 seepage law: delegate to the canonical segment flux.
    segment = {
        "cross_section": {
            "bottom_width_m": section.bottom_width_m * geometry_scale,
            "depth_m": section.depth_m * geometry_scale,
            "side_slope": section.side_slope,
        },
        "seepage_rate_m_s": seepage_rate_for_lining(lining) * seepage_multiplier,
        "length_m": section.length_m,
    }
    return _segment_seepage_m3s(segment)


def _member_directions(policy: EngineeringPolicy, member: str) -> dict:
    return policy.get("member_bundles", member)


def _derive_member(
    sections: list[_SectionEvidence],
    policy: EngineeringPolicy,
    member: str,
    nominal_reference_flow: float,
) -> dict:
    directions = _member_directions(policy, member)
    manning_direction = directions.get("manning_n")
    seepage_direction = directions.get("seepage_rate")
    flow_direction = directions.get("flow_to_state")
    geometry_direction = directions.get("geometry_tolerance")

    perturbations = policy.get("perturbations")
    geometry_scale = _perturbed(
        1.0, perturbations["geometry_tolerance"], geometry_direction
    )
    seepage_multiplier = _perturbed(
        1.0, perturbations["seepage_rate"], seepage_direction
    )

    state_flow = _perturbed(
        nominal_reference_flow, perturbations["flow_to_state"], flow_direction
    )

    timestep = policy.get("muskingum_cunge", "timestep_seconds")
    _require(
        policy.get("reference_flow", "state_evaluation")
        == "midpoint_of_zero_to_reference_transition",
        "unreviewed reference-state evaluation rule",
    )
    _require(
        policy.get("muskingum_cunge", "coefficient_evaluation")
        == "constant_at_reference_state",
        "unreviewed Muskingum-Cunge coefficient evaluation method",
    )
    _require(
        policy.get("surrogate_fit", "delay") == "t10"
        and policy.get("surrogate_fit", "dispersion") == "t90_minus_t10"
        and policy.get("surrogate_fit", "interpolation") == "linear",
        "unreviewed surrogate fit definition",
    )
    _require(
        policy.get("loss", "model") == "wetted_perimeter_seepage"
        and policy.get("loss", "composition") == "sum_of_section_seepage_flux"
        and policy.get("loss", "fraction_denominator")
        == "nominal_element_reference_flow",
        "unreviewed loss model definition",
    )
    residual_floor = state_flow * policy.get(
        "reference_flow", "minimum_residual_flow_fraction"
    )
    cascade = []
    total_travel_seconds = 0.0
    total_seepage_m3s = 0.0
    remaining_flow = state_flow
    for section in sections:
        if remaining_flow < residual_floor:
            raise ConveyanceExceededError(
                "seepage exhausts the reference flow before the reach outlet"
            )
        trapezoid = TrapezoidSection(
            bottom_width_m=section.bottom_width_m * geometry_scale,
            depth_m=section.depth_m * geometry_scale,
            side_slope=section.side_slope,
            manning_n=_perturbed(
                section.manning_n, perturbations["manning_n"], manning_direction
            ),
            bed_slope=section.bed_slope,
        )
        # Policy section 3: for a transition Q0 -> Q1 the hydraulic state is
        # evaluated at (Q0 + Q1) / 2 — the dry-start transition midpoint.
        midpoint_state_flow = 0.5 * remaining_flow
        cascade.append(
            CascadeSection(
                trapezoid, float(section.length_m), midpoint_state_flow
            )
        )
        try:
            celerity = flood_wave_celerity_m_s(trapezoid, midpoint_state_flow)
        except MuskingumCungeError as exc:
            raise HydraulicEvidenceError(str(exc)) from exc
        total_travel_seconds += section.length_m / celerity
        # Loss band uses the member's seepage multiplier; in-cascade state
        # threading always uses the nominal seepage estimate (policy
        # correlation note) so a widened loss band cannot exhaust the
        # evaluation flow.
        total_seepage_m3s += _seepage_m3s(
            section, policy, geometry_scale, seepage_multiplier
        )
        remaining_flow -= _seepage_m3s(section, policy, geometry_scale, 1.0)

    horizon_steps = int(
        policy.get("muskingum_cunge", "horizon_travel_factor")
        * total_travel_seconds
        / timestep
    ) + int(policy.get("muskingum_cunge", "horizon_floor_steps"))
    try:
        outflows = route_cascade(
            tuple(cascade),
            step_flow_m3s=state_flow,
            timestep_seconds=timestep,
            horizon_steps=horizon_steps,
        )
        t10, t90 = fit_t10_t90(
            outflows,
            state_flow,
            timestep,
            lower_threshold=policy.get("surrogate_fit", "lower_threshold"),
            upper_threshold=policy.get("surrogate_fit", "upper_threshold"),
        )
    except MuskingumCungeError as exc:
        raise HydraulicEvidenceError(str(exc)) from exc

    loss_fraction = total_seepage_m3s / nominal_reference_flow
    if loss_fraction >= 1.0:
        raise ConveyanceExceededError(
            "derived loss fraction reaches or exceeds the reference flow"
        )
    return {
        "member": member,
        "delay_seconds": t10,
        "dispersion_seconds": t90 - t10,
        "loss_fraction": loss_fraction,
        "state_flow_m3s": state_flow,
        "travel_seconds": total_travel_seconds,
    }


def _distribution(
    members: dict[str, dict], field: str, decimals: int
) -> ParameterDistribution:
    values = {name: round(members[name][field], decimals) for name in _MEMBER_NAMES}
    ordered = (values["lower"], values["nominal"], values["upper"])
    _require(
        ordered[0] <= ordered[1] <= ordered[2],
        f"perturbation bundles produced an unordered {field} distribution "
        f"{values!r}; revise the policy rather than sorting silently",
    )
    return ParameterDistribution(*ordered)


def _terminating_gate_id(element) -> str:
    return element.canonical_edges[-1][1]


def _capacity_planning_limit(
    element,
    sections: list[_SectionEvidence],
    gate_calibrations: dict,
    policy: EngineeringPolicy,
) -> tuple[float, str, float, str]:
    gate_id = _terminating_gate_id(element)
    gate = gate_calibrations.get("gates", {}).get(gate_id)
    _require(
        isinstance(gate, dict),
        f"terminating gate {gate_id!r} is absent from gate calibrations",
    )
    candidates = {
        "section_q_max_min": min(section.q_max_m3s for section in sections)
    }
    for field in ("q_max_m3s", "structure_max_flow_m3s"):
        value = gate.get(field)
        if value is not None:
            _require(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                and value > 0.0,
                f"gate {gate_id!r} {field} must be positive finite when present",
            )
            candidates[f"terminating_gate_{field}"] = float(value)
    ceiling_source, hard_ceiling = min(
        candidates.items(), key=lambda item: (item[1], item[0])
    )
    method = gate.get("calibration_method")
    derating = policy.get("capacity", "derating_by_calibration_method")
    _require(
        method in derating,
        f"gate {gate_id!r} calibration_method {method!r} has no reviewed "
        "capacity derating",
    )
    return hard_ceiling * derating[method], method, hard_ceiling, ceiling_source


def generate_engineering_model_release(
    routing_topology: RoutingTopology,
    canal_geometry: dict,
    gate_calibrations: dict,
    policy: EngineeringPolicy,
    sources: tuple[SourceArtifact, ...],
) -> tuple[HydraulicModelRelease, dict]:
    _require(
        policy.get("reference_flow", "element_rule") == "min_over_sections",
        "unreviewed element reference-flow rule",
    )
    _require(
        policy.get("loss", "missing_lining_type") == "unknown_class",
        "unreviewed missing-lining handling",
    )
    _require(
        policy.get("capacity", "hard_ceiling_bounds")
        == [
            "section_q_max_min",
            "terminating_gate_q_max_m3s",
            "terminating_gate_structure_max_flow_m3s",
        ],
        "unreviewed capacity hard-ceiling bounds",
    )
    _require(
        policy.get("capacity", "derating_selector")
        == "terminating_gate_calibration_method",
        "unreviewed capacity derating selector",
    )
    _require(
        policy.get("capacity", "distribution") == "degenerate_planning_limit",
        "unreviewed capacity distribution rule",
    )
    _require(
        policy.get("initialization_assumption") == "dry",
        "unreviewed initialization assumption",
    )
    try:
        # Canonical Wave-2.1a section guards: multi-row edges need parseable
        # forward-running, non-overlapping chainage — reuse, never relax.
        sections_by_edge_from_geometry(canal_geometry)
    except ConfigError as exc:
        raise EngineeringResponseError(
            f"canal geometry fails the canonical section guards: {exc}"
        ) from exc
    transports = [
        element
        for element in routing_topology.elements
        if element.role is RoutingRole.TRANSPORT
    ]
    decimals = policy.get("emitted_precision_decimals")
    generated_at = datetime.fromisoformat(
        policy.get("release_generated_at").replace("Z", "+00:00")
    )
    _require(
        generated_at.tzinfo is not None
        and generated_at.utcoffset() is not None,
        "release_generated_at must carry an explicit timezone; a naive "
        "timestamp would make the artifact bytes machine-dependent",
    )
    generated_at = generated_at.astimezone(timezone.utc)

    reach_parameters = []
    unavailable = []
    diagnostics: dict[str, dict] = {}
    for element in transports:
        if element.geometry_status is RoutingGeometryStatus.UNAVAILABLE:
            unavailable.append(
                UnavailableReach(
                    reach_id=element.element_id,
                    reason=policy.get("unavailable_reasons", "geometry_unavailable"),
                )
            )
            diagnostics[element.element_id] = {"status": "unavailable"}
            continue
        sections = _sections_for_edge(element.canonical_edges[0], canal_geometry)
        if element.element_id.startswith("C_J(LMC,0+170)_"):
            sections = [
                section
                for section in sections
                if (parse_chainage_m(section.from_km) or 0.0) >= 170.0
            ]
        _require(
            bool(sections),
            f"transport element {element.element_id!r} has no surveyed "
            "sections; refusing to invent geometry",
        )
        nominal_reference_flow = min(
            _section_reference_flow(section, policy) for section in sections
        )
        try:
            members = {
                member: _derive_member(
                    sections, policy, member, nominal_reference_flow
                )
                for member in _MEMBER_NAMES
            }
        except ConveyanceExceededError:
            unavailable.append(
                UnavailableReach(
                    reach_id=element.element_id,
                    reason=policy.get(
                        "unavailable_reasons", "conveyance_loss_exceeds_reference"
                    ),
                )
            )
            diagnostics[element.element_id] = {
                "status": "unavailable",
                "reason_key": "conveyance_loss_exceeds_reference",
            }
            continue
        except HydraulicEvidenceError:
            unavailable.append(
                UnavailableReach(
                    reach_id=element.element_id,
                    reason=policy.get(
                        "unavailable_reasons", "hydraulic_state_unavailable"
                    ),
                )
            )
            diagnostics[element.element_id] = {
                "status": "unavailable",
                "reason_key": "hydraulic_state_unavailable",
            }
            continue
        planning_limit, method, hard_ceiling, ceiling_source = (
            _capacity_planning_limit(element, sections, gate_calibrations, policy)
        )
        capacity_value = round(planning_limit, decimals["capacity_m3s"])
        reach_parameters.append(
            ReachResponseParameters(
                reach_id=element.element_id,
                delay_seconds=_distribution(
                    members, "delay_seconds", decimals["delay_seconds"]
                ),
                loss_fraction=_distribution(
                    members, "loss_fraction", decimals["loss_fraction"]
                ),
                dispersion_seconds=_distribution(
                    members, "dispersion_seconds", decimals["dispersion_seconds"]
                ),
                capacity_m3s=ParameterDistribution(
                    capacity_value, capacity_value, capacity_value
                ),
                evidence_refs=_EVIDENCE_REFS,
            )
        )
        diagnostics[element.element_id] = {
            "status": "parameterized",
            "sections": [section.from_km for section in sections],
            "nominal_reference_flow_m3s": nominal_reference_flow,
            "members": members,
            "capacity": {
                "hard_ceiling_m3s": hard_ceiling,
                "planning_limit_m3s": planning_limit,
                "derating_selector": method,
                "ceiling_source": ceiling_source,
            },
            "missing_lining_sections": [
                section.from_km
                for section in sections
                if section.lining_type is None
            ],
        }

    envelope = policy.get("operating_envelope")
    release = HydraulicModelRelease(
        schema_version=1,
        release_id=policy.get("release_id"),
        generated_at=generated_at,
        evidence_class=EvidenceClass.ENGINEERING_PRIOR,
        commandable=False,
        lineage=ModelLineage(
            generator="scripts/build_hydraulic_model_release.py",
            generator_version=policy.get("policy_version"),
            sources=sources,
        ),
        operating_envelope=OperatingEnvelope(
            envelope["minimum_flow_m3s"],
            envelope["maximum_flow_m3s"],
            envelope["minimum_timestep_seconds"],
            envelope["maximum_timestep_seconds"],
            envelope["maximum_horizon_seconds"],
        ),
        reach_parameters=tuple(reach_parameters),
        unavailable_reaches=tuple(unavailable),
        content_hash="0" * 64,
    )
    release = HydraulicModelRelease(
        **{
            **release.__dict__,
            "content_hash": model_release_content_hash(release),
        }
    )
    validate_model_release(release, routing_topology.transport_reach_ids())
    return release, diagnostics


def model_release_artifact_payload(release: HydraulicModelRelease) -> dict:
    generated_at = release.generated_at.astimezone(timezone.utc)
    return {
        "schema_version": release.schema_version,
        "release_id": release.release_id,
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "evidence_class": release.evidence_class.value,
        "commandable": release.commandable,
        "lineage": {
            "generator": release.lineage.generator,
            "generator_version": release.lineage.generator_version,
            "sources": [
                {
                    "source_id": source.source_id,
                    "version": source.version,
                    "sha256": source.sha256,
                }
                for source in release.lineage.sources
            ],
        },
        "operating_envelope": {
            "minimum_flow_m3s": release.operating_envelope.minimum_flow_m3s,
            "maximum_flow_m3s": release.operating_envelope.maximum_flow_m3s,
            "minimum_timestep_seconds": (
                release.operating_envelope.minimum_timestep_seconds
            ),
            "maximum_timestep_seconds": (
                release.operating_envelope.maximum_timestep_seconds
            ),
            "maximum_horizon_seconds": (
                release.operating_envelope.maximum_horizon_seconds
            ),
        },
        "reach_parameters": [
            {
                "reach_id": parameters.reach_id,
                "delay_seconds": _distribution_payload(parameters.delay_seconds),
                "loss_fraction": _distribution_payload(parameters.loss_fraction),
                "dispersion_seconds": _distribution_payload(
                    parameters.dispersion_seconds
                ),
                "capacity_m3s": _distribution_payload(parameters.capacity_m3s),
                "evidence_refs": list(parameters.evidence_refs),
            }
            for parameters in release.reach_parameters
        ],
        "unavailable_reaches": [
            {"reach_id": entry.reach_id, "reason": entry.reason}
            for entry in release.unavailable_reaches
        ],
        "content_hash": release.content_hash,
    }


def _distribution_payload(distribution: ParameterDistribution) -> dict:
    return {
        "lower": distribution.lower,
        "nominal": distribution.nominal,
        "upper": distribution.upper,
    }
