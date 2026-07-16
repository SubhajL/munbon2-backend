"""
core.network_flow_controller — canonical demand→flow controller (spec §10 consolidation).

This module is the single home the remediation spec designates for flow-per-gate
computation (C9/C10), replacing the divergent duplicate implementations. It is being
built incrementally, item-by-item; this increment adds only the A1–A3 aggregation entry
point (`required_flow_per_reach`). Later P1 items attach the demand producer/contract
(C12), conveyance loss (B5), the branch-split inverse (B8), and the SCADA bridge, and
wire it into the running service (F-03/C9).

The controller loads and connectivity-guards the canonical network once at construction
(`core.network_topology.load_validated_network`) and delegates the pure aggregation to
`core.demand_aggregation`.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from .branch_split import ReachOpening, ReachTarget, branch_split_openings
from .canal_capacity import min_segment_q_max
from .config_loader import file_sha256, load_canal_geometry_config
from .conveyance_loss import (
    make_reach_loss,
    normalize_edge,
    reach_chainage_gap_m,
    reach_has_geometry,
    reach_spans_from_geometry,
    sections_by_edge_from_geometry,
)
from .demand_aggregation import required_flow_per_reach
from .demand_contract import DemandContractError, ensure_aware_utc
from .network_topology import (
    NetworkTopologyError,
    is_spanning_tree,
    load_validated_network,
    nodes_of,
)
from .node_id import normalize_node_id

# Calibration bundles must explicitly opt in to gate actuation; the SCADA generator emits
# (and the strict loader ENFORCES) `intended_use == "planning_only"` — inferred, not
# field-validated, coefficients on defaulted sills — so no current bundle is actuation-grade.
ACTUATION_APPROVED_USE = "actuation"

# Why a reach carrying demand could not be commanded, so the wiring returns "opening
# unavailable" rather than an assumed command (plan HIGH #11).
REASON_LEVEL_MISSING = "level_missing"  # no level reading for a boundary node
REASON_LEVEL_STALE = "level_stale"  # a boundary level is older than the freshness SLA
REASON_LEVEL_FUTURE = "level_future"  # a boundary level is timestamped ahead of now
REASON_LEVEL_INVALID = "level_invalid"  # naive timestamp / non-finite level (bad datum)
REASON_CAPACITY_UNSURVEYED = (
    "capacity_unsurveyed"  # partial survey: canal limit not known
)
# The reach's inputs are trustworthy, but the calibration bundle is not approved for
# actuation (planning-only: inferred coefficients on defaulted sills) — so the opening it
# would compute is a planning estimate, never a command.
REASON_NOT_ACTUATION_APPROVED = "calibration_not_actuation_approved"
# This reach could be commanded, but another reach in the SAME plan could not, so
# commanding it would open an upstream gate toward an uncommandable downstream reach —
# partial actuation is unsafe, so the whole plan fails closed.
REASON_PLAN_INCOMPLETE = "blocked_by_uncommandable_reach"


@dataclass(frozen=True)
class ReachCoverage:
    """Wave 2.8a observability for one reach: how trustworthy its model is.

    `calibration_method`/`confidence` come from the reach's terminating (downstream)
    gate — a `measured` field-rated gate is worth more than an `inferred` similar-gate
    estimate or a `default`. `has_geometry` says whether the reach has a surveyed cross
    section (else its conveyance loss and capacity bound are not modelled). These are the
    generic feasibility fields; data-lineage coverage (demand version, workbook version,
    section→gate mapping) is 2.8b, gated on later waves.
    """

    calibration_method: str
    confidence: float
    has_geometry: bool


@dataclass(frozen=True)
class LevelReading:
    """A freshness-stamped real water-surface elevation (m MSL) at one node.

    `observed_at` is when the level was actually measured — the wiring only commands a
    gate whose boundary readings are recent enough (plan HIGH #11), so the timestamp is
    part of the datum, not metadata.
    """

    water_level_m: float
    observed_at: datetime


@dataclass(frozen=True)
class UnavailableReach:
    """A reach that carries demand but cannot be commanded: its boundary levels were not
    a fresh real measurement. It is surfaced (never a fabricated opening) so the operator
    supplies levels or leaves the gate as-is."""

    reach: tuple[str, str]
    requested_m3s: float
    reason: str
    unavailable_nodes: tuple[str, ...]
    detail: str


@dataclass(frozen=True)
class OpeningsResult:
    """Outcome of the demand→opening wiring: the reaches that were commanded (each with
    the honest branch-split infeasibility surface), the reaches that could not be
    commanded on fresh levels, and how many reaches carry no demand this plan."""

    openings: list[ReachOpening]
    unavailable: list[UnavailableReach]
    idle_reaches: int


class NetworkFlowController:
    """Loads the canonical network once (connectivity-guarded) and computes required
    per-reach flow from a per-node demand. This is the A1–A3 + B5 slice of the spec-§10
    consolidation module; later items attach the demand contract and the SCADA bridge.

    When a `geometry_path` is given, per-reach conveyance loss (B5) can be applied; reaches
    without a surveyed section are surfaced in `reaches_missing_geometry` (they take zero
    loss — never a fabricated seepage).
    """

    def __init__(
        self,
        network_path: str,
        geometry_path: str | None = None,
        calibration_path: str | None = None,
    ):
        self.edges = load_validated_network(network_path)
        # load_validated_network only guards connectivity; the subtree-per-reach aggregation
        # also needs a proper spanning tree (no node with two parents) — enforce it here so a
        # malformed network fails at startup, not on every /plan request.
        if not is_spanning_tree(self.edges):
            raise NetworkTopologyError(
                f"{network_path}: network is connected but not a spanning tree "
                "(a node has multiple parents); aggregation would double-count it"
            )
        self.sections: dict = {}
        reach_spans: dict = {}
        if geometry_path is not None:
            # Strict schema/drift validation (Wave 1.1) before the geometry is indexed.
            geometry = load_canal_geometry_config(geometry_path)
            self.sections = sections_by_edge_from_geometry(geometry)
            reach_spans = reach_spans_from_geometry(geometry)
            if not self.sections:
                # geometry supplied but unusable -> losses would silently be zero; fail closed.
                raise ValueError(
                    f"{geometry_path}: geometry file has no usable canal_sections"
                )
        # Wave 2.1a/2.1b: partial surveys are legal but never silent — unsurveyed
        # chainage (loss/capacity understate there) is surfaced per reach. The
        # geometry's `reaches` spans make HEAD/TAIL gaps measurable too; all five
        # real partial reaches gap at a boundary, not between segments.
        self.reaches_missing_geometry = {
            edge
            for edge in self.edges
            if not reach_has_geometry(self.sections, edge[0], edge[1])
        }
        self.reaches_with_chainage_gaps = {
            edge: gap
            for edge, segments in self.sections.items()
            if (gap := reach_chainage_gap_m(segments, span=reach_spans.get(edge)))
            is not None
            and gap > 0.0
        }
        self._normalized_edges = {normalize_edge(u, v) for u, v in self.edges}
        # Any-spacing id resolution (Wave 1.2): canonical compact form -> the exact
        # network key. Uniqueness is guaranteed by load_network_config's grammar +
        # normalized-collision validation.
        self._exact_by_normalized = {
            normalize_node_id(node): node for node in nodes_of(self.edges)
        }
        orphans = sorted(set(self.sections) - self._normalized_edges)
        if orphans:
            # Geometry describing reaches the network does not have means the two
            # files drifted apart (e.g. a half-regenerated survey) — fail closed
            # rather than silently losing loss coverage on the real reaches.
            raise ValueError(
                f"{geometry_path}: geometry sections are not network reaches: "
                f"{[list(edge) for edge in orphans[:5]]}"
                f"{'...' if len(orphans) > 5 else ''}"
            )

        # Wave 2.8a: per-reach coverage/confidence, computed once (a static network
        # property). The calibration loader is strict (a missing/drifted file raises at
        # construction, Wave 1.1) so a mis-built release fails closed at startup, not on
        # a request. Every reach terminates at a real gate — the source S is only ever
        # upstream — so get_calibration is always called with a valid gate id.
        from utils.gate_calibration_loader import GateCalibrationLoader

        self._calibration = GateCalibrationLoader(calibration_path)
        self.config_sha256 = {
            "network": file_sha256(network_path),
            "gate_calibrations": file_sha256(self._calibration.calibration_file),
        }
        if geometry_path is not None:
            self.config_sha256["canal_geometry"] = file_sha256(geometry_path)
        # Cross-file gate-set consistency: a downstream gate ABSENT from the calibration
        # file would silently get a fabricated generic default (confidence 0.6) — the
        # loader's per-gate fallback is fail-OPEN, and its internal count guard does not
        # see the network. That is exactly the "hardcode where real data exists" the
        # confidence field is meant to prevent, so refuse it here: the two artifacts
        # drifted (a network regen without a matching calibration regen). get_gate_data
        # returns {} only when the gate is not in the file.
        uncalibrated = sorted(
            edge[1]
            for edge in self.edges
            if not self._calibration.get_gate_data(edge[1])
        )
        if uncalibrated:
            raise ValueError(
                "network gates absent from the calibration file (network/calibration "
                f"drift; coverage would be fabricated): {uncalibrated[:5]}"
                f"{'...' if len(uncalibrated) > 5 else ''}"
            )
        # Per-edge coverage (2.8a) and the reach's canal-capacity bound, computed ONCE.
        # `self.sections`/`reaches_with_chainage_gaps` are keyed by NORMALIZED edges, so the
        # capacity lookup MUST normalize the raw network edge so formatting drift cannot
        # silently drop a surveyed limit. The terminating
        # gate's GateFlowCalibration is NOT precomputed here: it is assembled per commanded
        # reach in `_reach_targets`, so a single bad gate calibration cannot abort
        # construction and take down /plan (which needs no flow calibration).
        self.reach_coverage: dict = {}
        self._reach_capacity: dict = {}
        self._reach_capacity_uncertain: set = set()
        for edge in self.edges:
            u, v = edge
            cal = self._calibration.get_calibration(v)
            self.reach_coverage[edge] = ReachCoverage(
                calibration_method=cal.calibration_method,
                confidence=cal.confidence,
                has_geometry=edge not in self.reaches_missing_geometry,
            )
            norm = normalize_edge(u, v)
            capacity = (
                min_segment_q_max(self.sections[norm])
                if norm in self.sections
                else None
            )
            if norm in self.reaches_with_chainage_gaps or (
                norm in self.sections and capacity is None
            ):
                # Capacity is not trustworthy: either a partial survey (min_segment_q_max
                # bounds only the KNOWN segments, the gap may be weaker) OR a surveyed reach
                # whose segments carry NO valid rating. Either way the canal bound is unknown
                # → the reach fails closed under actuation rather than trusting the gate q_max.
                self._reach_capacity[edge] = None
                self._reach_capacity_uncertain.add(edge)
            else:
                # A fully surveyed reach uses its weakest segment; an unsurveyed reach has no
                # canal bound, so the gate's rated q_max (inside branch_split) is the only,
                # honest, ceiling.
                self._reach_capacity[edge] = capacity

    def coverage_summary(self) -> dict:
        """Network-level roll-up of the per-reach coverage (Wave 2.8a): how much of the
        model rests on surveyed geometry vs measured/inferred calibration. A request-
        independent snapshot an operator can read before trusting a plan. Derived wholly
        from `reach_coverage` so the roll-up and the per-reach values cannot drift apart.
        """
        surveyed = sum(1 for cov in self.reach_coverage.values() if cov.has_geometry)
        method_counts = Counter(
            cov.calibration_method for cov in self.reach_coverage.values()
        )
        return {
            "total_reaches": len(self.edges),
            "geometry_surveyed": surveyed,
            "geometry_missing": len(self.edges) - surveyed,
            "chainage_gaps": len(self.reaches_with_chainage_gaps),
            "calibration_method_counts": dict(method_counts),
        }

    @property
    def actuation_approved(self) -> bool:
        """Whether this controller may drive gate actuation. HARD-CODED False: the strict
        loader accepts ONLY `intended_use == "planning_only"` (inferred coefficients on
        defaulted sills), so no loadable bundle is actuation-grade, and there is deliberately
        no runtime input — no per-call argument, no settable flag, and NOT a derivation from
        the mutable `_calibration.intended_use` — that could turn actuation on for a
        planning-only bundle (plan HIGH #11 / Codex). A real, immutable, validated
        actuation-capability mechanism (with field-validated calibrations + approved sills)
        is a future wave; until then /openings commands nothing (every reach is
        opening-unavailable). See ACTUATION_APPROVED_USE for the intended bundle marker.
        """
        return False

    def openings_for_demand(
        self,
        node_demand: dict,
        node_levels: dict,
        now: datetime,
        max_level_age_seconds: float,
        apply_losses: bool = False,
        charge_dry_reaches: bool = False,
        always_wet=(),
    ) -> OpeningsResult:
        """Demand → per-reach flow → per-gate opening (Wave 2.7 /control wiring).

        Each reach that carries flow is solved by the branch-split inverse
        (`core.branch_split`) on its terminating gate's calibration, its canal capacity,
        and the REAL freshness-stamped boundary levels the caller supplies. Openings are
        emitted ONLY when the whole plan is safely commandable; otherwise every reach is
        returned opening-unavailable, NEVER an assumed command (plan HIGH #11):
          - a boundary level that is missing / stale (> the SLA) / future / malformed is
            not a usable datum (`_reach_targets`);
          - a reach whose canal capacity is not fully surveyed has no trustworthy bound;
          - `self.actuation_approved` is False — the calibration bundle is planning-only
            (inferred coefficients on defaulted sills; the strict loader ENFORCES this), so
            an opening would be a planning estimate, not a command;
          - ANY reach in the plan is uncommandable → NONE are commanded: opening an upstream
            gate toward an uncommandable downstream reach is unsafe partial actuation.
        Approval is a property of the loaded bundle (`self.actuation_approved`), not a
        caller argument — no caller can force a command on a planning-only bundle. Idle
        reaches (no demand this plan) need no levels and are only counted.
        """
        now_utc = ensure_aware_utc(now, "now")
        if (
            isinstance(max_level_age_seconds, bool)
            or not isinstance(max_level_age_seconds, (int, float))
            or not math.isfinite(max_level_age_seconds)
            or max_level_age_seconds <= 0
        ):
            raise ValueError(
                "max_level_age_seconds must be a finite positive number, got "
                f"{max_level_age_seconds!r}"
            )
        reach_flow = self.required_flow_per_reach(
            node_demand,
            apply_losses=apply_losses,
            charge_dry_reaches=charge_dry_reaches,
            always_wet=always_wet,
        )
        levels = self._resolve_levels(node_levels, now_utc, max_level_age_seconds)
        targets, unavailable, idle = self._reach_targets(reach_flow, levels)

        if not self.actuation_approved:
            # Planning-only bundle: computing a command would command on assumed (defaulted
            # sill) geometry — surface every otherwise-commandable reach, never emit it.
            unavailable = unavailable + [
                self._blocked(
                    t,
                    REASON_NOT_ACTUATION_APPROVED,
                    "calibration bundle is not approved for actuation "
                    "(planning-only: inferred coefficients on defaulted sills)",
                )
                for t in targets
            ]
            return OpeningsResult(
                openings=[], unavailable=unavailable, idle_reaches=idle
            )
        if unavailable:
            # Partial actuation is unsafe: releasing water through a commandable reach toward
            # a reach that could NOT be commanded risks flooding it. Fail the whole plan.
            unavailable = unavailable + [
                self._blocked(
                    t,
                    REASON_PLAN_INCOMPLETE,
                    "another reach in this plan is uncommandable; partial "
                    "actuation is unsafe, so the whole plan fails closed",
                )
                for t in targets
            ]
            return OpeningsResult(
                openings=[], unavailable=unavailable, idle_reaches=idle
            )
        openings = branch_split_openings(targets)
        if not all(o.feasible for o in openings):
            # A reach that looked commandable turned infeasible at solve time (e.g. no
            # driving head, over-capacity): the same partial-actuation hazard, discovered by
            # the inverse rather than up front — so still block the WHOLE plan.
            blocked = [
                UnavailableReach(
                    reach=o.reach,
                    requested_m3s=o.requested_m3s,
                    reason=REASON_PLAN_INCOMPLETE,
                    unavailable_nodes=(),
                    detail=f"plan not fully commandable (a reach solved as {o.reason}); "
                    "partial actuation is unsafe",
                )
                for o in openings
            ]
            return OpeningsResult(
                openings=[], unavailable=unavailable + blocked, idle_reaches=idle
            )
        return OpeningsResult(
            openings=openings, unavailable=unavailable, idle_reaches=idle
        )

    def _reach_targets(self, reach_flow: dict, levels: dict) -> tuple:
        """Split the demand-carrying reaches into commandable ReachTargets and
        opening-unavailable reaches (missing/stale/future/invalid level, or unsurveyed
        capacity), plus the idle count. Approval is NOT considered here — that is the
        caller's decision — so this pure split is testable without a (non-existent)
        actuation-approved bundle."""
        targets: list[ReachTarget] = []
        unavailable: list[UnavailableReach] = []
        idle = 0
        for edge in self.edges:
            target = reach_flow[edge]
            if target <= 0.0:
                idle += 1
                continue
            upstream, downstream = edge
            readings: dict = {}
            problems: list[tuple[str, str]] = []
            for node in (upstream, downstream):
                level, reason = levels.get(
                    normalize_node_id(node), (None, REASON_LEVEL_MISSING)
                )
                if reason is None:
                    readings[node] = level
                else:
                    problems.append((node, reason))
            if problems:
                unavailable.append(
                    UnavailableReach(
                        reach=edge,
                        requested_m3s=target,
                        reason=problems[0][1],
                        unavailable_nodes=tuple(node for node, _ in problems),
                        detail="; ".join(
                            f"{node}: {reason}" for node, reason in problems
                        ),
                    )
                )
                continue
            if edge in self._reach_capacity_uncertain:
                unavailable.append(
                    UnavailableReach(
                        reach=edge,
                        requested_m3s=target,
                        reason=REASON_CAPACITY_UNSURVEYED,
                        unavailable_nodes=(),
                        detail="reach capacity is not fully surveyed; a safe opening "
                        "cannot be bounded",
                    )
                )
                continue
            targets.append(
                ReachTarget(
                    reach=edge,
                    calibration=self._calibration.build_flow_calibration(downstream),
                    upstream_level_m=readings[upstream],
                    downstream_level_m=readings[downstream],
                    target_flow_m3s=target,
                    capacity_m3s=self._reach_capacity[edge],
                )
            )
        return targets, unavailable, idle

    @staticmethod
    def _blocked(target: ReachTarget, reason: str, detail: str) -> UnavailableReach:
        """A would-be-commandable reach turned opening-unavailable by a plan-level block
        (planning-only bundle, or an uncommandable peer reach)."""
        return UnavailableReach(
            reach=target.reach,
            requested_m3s=target.target_flow_m3s,
            reason=reason,
            unavailable_nodes=(),
            detail=detail,
        )

    def _resolve_levels(
        self, node_levels: dict, now_utc: datetime, max_level_age_seconds: float
    ) -> dict:
        """Freshness-classify each supplied level, re-keyed to the normalized node id
        (any spacing, Wave 1.2). Returns {normalized_id: (level_m, None)} for a usable
        reading or {normalized_id: (None, reason)} for an unusable one (stale/future/
        invalid). A colliding key OR a key that names no network node fails the whole
        request closed (400) — a level for an unknown/mistyped node is a request-structure
        error, never silently dropped (which would leave the real reach uncommanded while
        the operator believed a level was supplied). A malformed READING (naive timestamp /
        non-finite level) is classified per-reach (level_invalid), NOT a global abort — one
        bad sensor must not deny actuation to reaches with their own fresh levels."""
        resolved: dict = {}
        alias_of: dict = {}
        for node_id, reading in node_levels.items():
            if not isinstance(node_id, str):
                raise ValueError(f"level key is not a node id string: {node_id!r}")
            # normalize_node_id is lenient (it passes non-gate strings through unchanged),
            # so validate against the real network node set explicitly.
            key = normalize_node_id(node_id)
            if key not in self._exact_by_normalized:
                raise ValueError(
                    f"level for unknown node {node_id!r} (not in the network)"
                )
            if key in resolved:
                raise ValueError(
                    "level keys collide after normalization:"
                    f" {alias_of[key]!r} and {node_id!r} both name {key!r}"
                )
            alias_of[key] = node_id
            resolved[key] = self._classify_level(
                reading, now_utc, max_level_age_seconds
            )
        return resolved

    @staticmethod
    def _classify_level(
        reading, now_utc: datetime, max_level_age_seconds: float
    ) -> tuple:
        """(level_m, None) if the reading is a fresh real datum; (None, reason) otherwise.
        A naive timestamp or non-finite level is a malformed datum for THAT node
        (level_invalid) — surfaced per-reach, not raised — so one bad sensor does not deny
        the whole network."""
        try:
            observed = ensure_aware_utc(reading.observed_at, "observed_at")
        except DemandContractError:
            return (None, REASON_LEVEL_INVALID)  # naive / non-datetime timestamp
        level = reading.water_level_m
        if (
            isinstance(level, bool)
            or not isinstance(level, (int, float))
            or not math.isfinite(level)
        ):
            return (None, REASON_LEVEL_INVALID)
        age = (now_utc - observed).total_seconds()
        # A timestamp ahead of `now` is not a current measurement — a fast/unsynchronised
        # sensor clock could otherwise make a genuinely old reading look fresh. Never
        # command on a future-stamped level; surface it so the clock issue is fixed.
        if age < 0:
            return (None, REASON_LEVEL_FUTURE)
        if age > max_level_age_seconds:
            return (None, REASON_LEVEL_STALE)
        return (float(level), None)

    def required_flow_per_reach(
        self,
        node_demand: dict,
        apply_losses: bool = False,
        charge_dry_reaches: bool = False,
        always_wet=(),
    ) -> dict:
        """Flow each reach must carry to serve `node_demand`, keyed by (upstream, downstream).

        With `apply_losses=True` and geometry loaded, each reach also carries its conveyance
        (seepage + operational) loss (B5); otherwise the result is the lossless A1–A3 sum.
        Dry-reach semantics (D1): reaches with no flow in this plan take no loss unless
        listed in `always_wet` ([upstream, downstream] pairs, any id spacing — must be real
        network reaches, fail-closed) or `charge_dry_reaches=True` (legacy whole-network
        steady mode). Both knobs require `apply_losses=True`.
        """
        if not apply_losses and (charge_dry_reaches or always_wet):
            raise ValueError(
                "charge_dry_reaches/always_wet only make sense with apply_losses=True"
            )
        node_demand = self._resolve_demands(node_demand)
        reach_loss = None
        if apply_losses:
            wet = set()
            unknown = []
            no_geometry = []
            for pair in always_wet:
                upstream, downstream = pair
                key = normalize_edge(upstream, downstream)
                if key not in self._normalized_edges:
                    unknown.append([upstream, downstream])
                elif key not in self.sections:
                    # "keep this reach charged" is unfulfillable without surveyed geometry
                    # (loss would silently be 0) -> fail closed, don't feign coverage.
                    no_geometry.append([upstream, downstream])
                else:
                    wet.add(key)
            if unknown:
                raise ValueError(f"always_wet contains unknown reaches: {unknown}")
            if no_geometry:
                raise ValueError(
                    "always_wet reaches have no surveyed geometry (their seepage cannot "
                    f"be charged): {no_geometry}"
                )
            reach_loss = make_reach_loss(
                self.sections,
                charge_dry_reaches=charge_dry_reaches,
                always_wet=frozenset(wet),
            )
        return required_flow_per_reach(self.edges, node_demand, reach_loss=reach_loss)

    def _resolve_demands(self, node_demand: dict) -> dict:
        """Demand keys accepted in ANY spacing (compact canonical or survey-spaced),
        re-keyed to the network-exact ids (Wave 1.2). Unknown ids and two keys naming
        the same physical node fail closed; values are validated downstream."""
        resolved: dict = {}
        alias_of: dict = {}
        for node_id, value in node_demand.items():
            if not isinstance(node_id, str):
                raise ValueError(f"demand key is not a node id string: {node_id!r}")
            exact = self._exact_by_normalized.get(normalize_node_id(node_id))
            if exact is None:
                raise ValueError(
                    f"demand for unknown node {node_id!r} (not in the network)"
                )
            if exact in resolved:
                raise ValueError(
                    "demand keys collide after normalization:"
                    f" {alias_of[exact]!r} and {node_id!r} both name {exact!r}"
                )
            resolved[exact] = value
            alias_of[exact] = node_id
        return resolved
