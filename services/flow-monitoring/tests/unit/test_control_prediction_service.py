from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.prediction_engine import build_prediction_engine_descriptor

from core.fulfillment import (
    ClosureProjection,
    ClosureRequirement,
    VolumeBounds,
)
from core.model_release import (
    EvidenceClass,
    HydraulicModelRelease,
    ModelLineage,
    OperatingEnvelope,
    ParameterDistribution,
    ReachResponseParameters,
    SourceArtifact,
    model_release_content_hash,
)
from core.model_snapshot import ModelSnapshotError
from core.network_transient import (
    GateFlowEvent,
    NetworkTransientError,
    SectionRequirement,
)
from core.reach_response import (
    ReachResponse,
    ReachState,
    ResponseMember,
    reach_responses_from_model_release,
)
from core.routing_topology import (
    RoutingElement,
    RoutingGeometryStatus,
    RoutingRole,
    build_routing_topology,
)
from services.control_prediction_service import (
    ControlPredictionService,
    PredictionLineageConflictError,
    PredictionModelUnavailableError,
)

START = datetime(2026, 7, 16, tzinfo=timezone.utc)
SERVICE_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DESCRIPTOR = build_prediction_engine_descriptor(SERVICE_ROOT)


def _topology(edges):
    return build_routing_topology(
        tuple(
            RoutingElement(
                element_id=f"C_{upstream}_{downstream}",
                upstream_node_id=upstream,
                downstream_node_id=downstream,
                role=RoutingRole.TRANSPORT,
                canonical_edges=((upstream, downstream),),
                canal=None,
                span_m=100.0,
                geometry_status=RoutingGeometryStatus.SURVEYED,
                located_at_km=None,
            )
            for upstream, downstream in edges
        )
    )


RESPONSE = ReachResponse(
    model_release_id="engineering-prior-2569-v1",
    reach_id="C_S_A",
    member=ResponseMember.NOMINAL,
    delay_seconds=0.0,
    loss_fraction=0.0,
    dispersion_seconds=0.0,
    capacity_m3s=2.0,
    minimum_timestep_seconds=60.0,
    maximum_timestep_seconds=300.0,
)
CONFIG_SHA256 = {
    "network": "a" * 64,
    "canal_geometry": "b" * 64,
    "gate_calibrations": "c" * 64,
    "geometry_coverage": "1" * 64,
    "routing_topology": "2" * 64,
}


def _model_release() -> HydraulicModelRelease:
    release = HydraulicModelRelease(
        schema_version=1,
        release_id="engineering-prior-2569-v1",
        generated_at=START,
        evidence_class=EvidenceClass.ENGINEERING_PRIOR,
        commandable=False,
        lineage=ModelLineage(
            "release-builder",
            "1.0.0",
            (SourceArtifact("network", "v1", "d" * 64),),
        ),
        operating_envelope=OperatingEnvelope(
            0.0,
            2.0,
            60.0,
            300.0,
            3600.0,
        ),
        reach_parameters=(
            ReachResponseParameters(
                "C_S_A",
                ParameterDistribution(0.0, 0.0, 0.0),
                ParameterDistribution(0.0, 0.0, 0.0),
                ParameterDistribution(0.0, 0.0, 0.0),
                ParameterDistribution(1.0, 1.5, 2.0),
                ("network",),
            ),
        ),
        unavailable_reaches=(),
        content_hash="0" * 64,
    )
    return replace(release, content_hash=model_release_content_hash(release))


def test_prediction_service_invokes_pure_network_timeline():
    service = ControlPredictionService(_topology((("S", "A"),)), (RESPONSE,), 3600.0)
    timeline = service.predict_member(
        ResponseMember.NOMINAL,
        (ReachState(RESPONSE.model_release_id, RESPONSE.reach_id, RESPONSE.member),),
        (GateFlowEvent("S", START, 1.0),),
        (),
        (),
        (),
        START,
        START + timedelta(minutes=1),
        60.0,
    )

    assert (timeline.member, timeline.mass_balance.terminal_outflow_m3) == (
        ResponseMember.NOMINAL,
        60.0,
    )


def test_prediction_service_rejects_horizon_above_model_release_envelope():
    service = ControlPredictionService(_topology((("S", "A"),)), (RESPONSE,), 60.0)

    with pytest.raises(NetworkTransientError, match="horizon"):
        service.predict_member(
            ResponseMember.NOMINAL,
            (
                ReachState(
                    RESPONSE.model_release_id, RESPONSE.reach_id, RESPONSE.member
                ),
            ),
            (GateFlowEvent("S", START, 1.0),),
            (),
            (),
            (),
            START,
            START + timedelta(minutes=2),
            60.0,
        )


def test_prediction_service_derives_closure_descendants_from_its_runtime_topology():
    service = ControlPredictionService(
        _topology((("S", "A"), ("A", "B"), ("A", "C"))), (), None
    )
    requirements = (
        ClosureRequirement("requirement-1", "B", 100.0, 0.0, START),
        ClosureRequirement("requirement-2", "C", 100.0, 0.0, START),
    )
    projection = ClosureProjection(
        START,
        "requirement-1",
        VolumeBounds(100.0, 100.0, 100.0),
    )

    assert service.earliest_safe_closure("B", requirements, (projection,)) == START


def test_closure_at_a_non_gate_routing_node_fails_closed():
    from core.routing_topology import (
        RoutingElement,
        RoutingGeometryStatus,
        RoutingRole,
    )

    elements = (
        RoutingElement(
            element_id="C_S_A",
            upstream_node_id="S",
            downstream_node_id="A",
            role=RoutingRole.TRANSPORT,
            canonical_edges=(("S", "A"),),
            canal=None,
            span_m=100.0,
            geometry_status=RoutingGeometryStatus.SURVEYED,
            located_at_km=None,
        ),
        RoutingElement(
            element_id="C_A_J(TEST,0+100)",
            upstream_node_id="A",
            downstream_node_id="J(TEST,0+100)",
            role=RoutingRole.TRANSPORT,
            canonical_edges=(("A", "B"),),
            canal=None,
            span_m=100.0,
            geometry_status=RoutingGeometryStatus.SURVEYED,
            located_at_km=None,
        ),
        RoutingElement(
            element_id="C_J(TEST,0+100)_B",
            upstream_node_id="J(TEST,0+100)",
            downstream_node_id="B",
            role=RoutingRole.TRANSPORT,
            canonical_edges=(("A", "B"),),
            canal=None,
            span_m=100.0,
            geometry_status=RoutingGeometryStatus.SURVEYED,
            located_at_km=None,
        ),
    )
    service = ControlPredictionService(
        build_routing_topology(elements), (), None
    )

    with pytest.raises(NetworkTransientError, match="canal gate"):
        service.earliest_safe_closure("J(TEST,0+100)", (), ())


def test_prediction_service_routes_operator_withdrawal_events():
    from core.network_transient import OperatorWithdrawalEvent

    elements = (
        RoutingElement(
            element_id="C_S_A",
            upstream_node_id="S",
            downstream_node_id="A",
            role=RoutingRole.TRANSPORT,
            canonical_edges=(("S", "A"),),
            canal=None,
            span_m=100.0,
            geometry_status=RoutingGeometryStatus.SURVEYED,
            located_at_km=None,
        ),
        RoutingElement(
            element_id="WD_A_W",
            upstream_node_id="A",
            downstream_node_id="W",
            role=RoutingRole.WITHDRAWAL_STRUCTURE,
            canonical_edges=(("A", "W"),),
            canal=None,
            span_m=None,
            geometry_status=RoutingGeometryStatus.NOT_APPLICABLE,
            located_at_km="0+100",
        ),
    )
    service = ControlPredictionService(
        build_routing_topology(elements),
        (RESPONSE,),
        3600.0,
        (("W", None),),
    )

    timeline = service.predict_member(
        ResponseMember.NOMINAL,
        (ReachState(RESPONSE.model_release_id, RESPONSE.reach_id, RESPONSE.member),),
        (GateFlowEvent("S", START, 1.0),),
        (
            OperatorWithdrawalEvent(
                structure_id="W",
                effective_at=START,
                planned_flow_m3s=0.5,
                purpose="industrial_supply",
            ),
        ),
        (),
        (),
        START,
        START + timedelta(minutes=1),
        60.0,
    )

    assert timeline.mass_balance.withdrawn_m3 == 30.0
    assert timeline.steps[0].withdrawals[0].structure_id == "W"


def test_prediction_service_rejects_incomplete_withdrawal_capacity_mapping():
    elements = (
        RoutingElement(
            element_id="C_S_A",
            upstream_node_id="S",
            downstream_node_id="A",
            role=RoutingRole.TRANSPORT,
            canonical_edges=(("S", "A"),),
            canal=None,
            span_m=100.0,
            geometry_status=RoutingGeometryStatus.SURVEYED,
            located_at_km=None,
        ),
        RoutingElement(
            element_id="WD_A_W",
            upstream_node_id="A",
            downstream_node_id="W",
            role=RoutingRole.WITHDRAWAL_STRUCTURE,
            canonical_edges=(("A", "W"),),
            canal=None,
            span_m=None,
            geometry_status=RoutingGeometryStatus.NOT_APPLICABLE,
            located_at_km="0+100",
        ),
    )

    with pytest.raises(NetworkTransientError, match="withdrawal structures"):
        ControlPredictionService(
            build_routing_topology(elements), (), None
        )


def test_prediction_service_returns_snapshot_bound_to_its_release_horizon():
    release = _model_release()
    service = ControlPredictionService(
        _topology((("S", "A"),)),
        reach_responses_from_model_release(release),
        release.operating_envelope.maximum_horizon_seconds,
        prediction_engine_descriptor=ENGINE_DESCRIPTOR,
    )

    snapshot = service.model_snapshot(release, CONFIG_SHA256, False)

    assert (
        snapshot["data_status"],
        snapshot["response_model"]["release_id"],
        snapshot["action_model"]["operating_envelope"]["maximum_horizon_seconds"],
    ) == ("complete", release.release_id, 3600.0)


def test_prediction_service_rejects_snapshot_release_horizon_drift():
    release = _model_release()
    service = ControlPredictionService(
        _topology((("S", "A"),)),
        reach_responses_from_model_release(release),
        1800.0,
    )

    with pytest.raises(ModelSnapshotError, match="horizon"):
        service.model_snapshot(release, CONFIG_SHA256, False)


@pytest.mark.parametrize(
    "routing_topology,reach_responses,maximum_horizon_seconds",
    [
        ((("S", "A"),), (RESPONSE,), 60.0),
        ("not-a-topology", (RESPONSE,), 60.0),
        (None, [RESPONSE], 60.0),
        (None, (RESPONSE,), None),
        (None, (RESPONSE,), float("nan")),
    ],
)
def test_prediction_service_rejects_untyped_or_missing_release_contract(
    routing_topology, reach_responses, maximum_horizon_seconds
):
    if routing_topology is None:
        routing_topology = _topology((("S", "A"),))
    with pytest.raises(NetworkTransientError):
        ControlPredictionService(
            routing_topology, reach_responses, maximum_horizon_seconds
        )


def _dual_reach_release() -> HydraulicModelRelease:
    release = HydraulicModelRelease(
        schema_version=1,
        release_id="engineering-prior-2569-v1",
        generated_at=START,
        evidence_class=EvidenceClass.ENGINEERING_PRIOR,
        commandable=False,
        lineage=ModelLineage(
            "release-builder",
            "1.0.0",
            (SourceArtifact("network", "v1", "d" * 64),),
        ),
        operating_envelope=OperatingEnvelope(0.0, 5.0, 60.0, 300.0, 3600.0),
        reach_parameters=(
            ReachResponseParameters(
                "C_S_A",
                ParameterDistribution(0.0, 0.0, 0.0),
                ParameterDistribution(0.0, 0.0, 0.0),
                ParameterDistribution(0.0, 0.0, 0.0),
                ParameterDistribution(1.0, 1.5, 2.0),
                ("network",),
            ),
        ),
        unavailable_reaches=(),
        content_hash="0" * 64,
    )
    return replace(release, content_hash=model_release_content_hash(release))


def _timeline_service(release: HydraulicModelRelease) -> ControlPredictionService:
    return ControlPredictionService(
        _topology((("S", "A"),)),
        reach_responses_from_model_release(release),
        release.operating_envelope.maximum_horizon_seconds,
        prediction_engine_descriptor=ENGINE_DESCRIPTOR,
    )


def _predict(service, release, **overrides):
    kwargs = dict(
        release=release,
        config_sha256=CONFIG_SHA256,
        actuation_approved=False,
        model_snapshot_id=service.model_snapshot(
            release, CONFIG_SHA256, False
        )["snapshot_id"],
        model_release_id=release.release_id,
        model_release_content_hash=release.content_hash,
        gate_events=(GateFlowEvent("S", START, 1.2),),
        withdrawal_events=(),
        requirements=(),
        branch_allocations=(),
        starts_at=START,
        ends_at=START + timedelta(minutes=10),
        timestep_seconds=60.0,
    )
    kwargs.update(overrides)
    return service.predict_control_timeline(**kwargs)


class TestPredictControlTimeline:
    def test_runs_members_in_lower_nominal_upper_order(self):
        release = _dual_reach_release()
        outcome = _predict(_timeline_service(release), release, gate_events=(
            GateFlowEvent("S", START, 0.5),
        ))

        assert [entry.member for entry in outcome.members] == [
            ResponseMember.LOWER,
            ResponseMember.NOMINAL,
            ResponseMember.UPPER,
        ]
        assert all(entry.timeline is not None for entry in outcome.members)
        assert outcome.covered_transport_reach_ids == ("C_S_A",)
        assert outcome.excluded_transport_reaches == ()

    def test_capacity_exceedance_is_member_infeasibility_not_error(self):
        release = _dual_reach_release()
        outcome = _predict(_timeline_service(release), release)

        lower, nominal, upper = outcome.members
        assert lower.timeline is None
        assert lower.predicted_delivered_total_m3 is None
        assert lower.infeasibility.reach_id == "C_S_A"
        assert nominal.timeline is not None
        assert upper.timeline is not None

    def test_lineage_pin_mismatch_raises_conflict(self):
        release = _dual_reach_release()
        service = _timeline_service(release)

        with pytest.raises(PredictionLineageConflictError):
            _predict(service, release, model_snapshot_id="0" * 64)
        with pytest.raises(PredictionLineageConflictError):
            _predict(service, release, model_release_id="other-release")
        with pytest.raises(PredictionLineageConflictError):
            _predict(service, release, model_release_content_hash="f" * 64)

    def test_missing_release_is_model_unavailable(self):
        service = ControlPredictionService(_topology((("S", "A"),)), (), None)

        with pytest.raises(PredictionModelUnavailableError):
            service.predict_control_timeline(
                release=None,
                config_sha256=CONFIG_SHA256,
                actuation_approved=False,
                model_snapshot_id="0" * 64,
                model_release_id="engineering-prior-2569-v1",
                model_release_content_hash="0" * 64,
                gate_events=(GateFlowEvent("S", START, 0.5),),
                withdrawal_events=(),
                requirements=(),
                branch_allocations=(),
                starts_at=START,
                ends_at=START + timedelta(minutes=10),
                timestep_seconds=60.0,
            )

    def test_source_event_required_exactly_at_start(self):
        release = _dual_reach_release()
        service = _timeline_service(release)

        with pytest.raises(NetworkTransientError, match="starts_at"):
            _predict(
                service,
                release,
                gate_events=(
                    GateFlowEvent("S", START + timedelta(minutes=1), 0.5),
                ),
            )

    def test_source_flow_outside_envelope_rejected_zero_allowed(self):
        release = _dual_reach_release()
        service = _timeline_service(release)

        with pytest.raises(NetworkTransientError, match="validity envelope"):
            _predict(
                service,
                release,
                gate_events=(GateFlowEvent("S", START, 6.0),),
            )
        outcome = _predict(
            service, release, gate_events=(GateFlowEvent("S", START, 0.0),)
        )
        assert all(entry.timeline is not None for entry in outcome.members)


class TestCollectPredictionViolations:
    def _completed_timeline(self, requirements, withdrawal_events=(),
                            flow_m3s=0.5):
        release = _dual_reach_release()
        service = _timeline_service(release)
        outcome = _predict(
            service,
            release,
            gate_events=(GateFlowEvent("S", START, flow_m3s),),
            requirements=requirements,
            withdrawal_events=withdrawal_events,
        )
        return outcome.members[1]

    def test_requirement_shortfall_reports_exact_deficit(self):
        requirement = SectionRequirement(
            requirement_id="REQ-1",
            section_id="SEC-1",
            delivery_node_id="A",
            window_start=START,
            window_end=START + timedelta(minutes=10),
            required_volume_m3=1000.0,
            maximum_delivery_m3s=2.0,
        )
        member = self._completed_timeline((requirement,))

        shortfalls = [
            violation
            for violation in member.violations
            if violation.kind == "requirement_shortfall"
        ]
        assert len(shortfalls) == 1
        violation = shortfalls[0]
        # Independent oracle: zero delay/loss/dispersion, 0.5 m3/s inflow for
        # a 10-minute horizon, under the 2.0 m3/s delivery cap -> 300 m3.
        assert violation.requirement_id == "REQ-1"
        assert violation.predicted_delivered_m3 == pytest.approx(300.0)
        assert violation.shortfall_m3 == pytest.approx(700.0)
        assert member.predicted_delivered_total_m3 == pytest.approx(300.0)

    def test_fulfilled_requirement_emits_no_shortfall(self):
        requirement = SectionRequirement(
            requirement_id="REQ-2",
            section_id="SEC-1",
            delivery_node_id="A",
            window_start=START,
            window_end=START + timedelta(minutes=10),
            required_volume_m3=60.0,
            maximum_delivery_m3s=2.0,
            approved_excess_m3=1000.0,
        )
        member = self._completed_timeline((requirement,))

        assert [
            violation.kind for violation in member.violations
        ] == []

    def test_zero_planned_withdrawal_emits_no_capacity_violation(self):
        member = self._completed_timeline(())
        assert member.violations == ()


class TestRequirementWindowContainment:
    def test_window_outside_horizon_fails_closed(self):
        release = _dual_reach_release()
        service = _timeline_service(release)
        early_start = SectionRequirement(
            requirement_id="REQ-EARLY",
            section_id="SEC-1",
            delivery_node_id="A",
            window_start=START - timedelta(minutes=5),
            window_end=START + timedelta(minutes=5),
            required_volume_m3=10.0,
            maximum_delivery_m3s=1.0,
        )
        late_end = SectionRequirement(
            requirement_id="REQ-LATE",
            section_id="SEC-1",
            delivery_node_id="A",
            window_start=START,
            window_end=START + timedelta(minutes=20),
            required_volume_m3=10.0,
            maximum_delivery_m3s=1.0,
        )
        for requirement in (early_start, late_end):
            with pytest.raises(
                NetworkTransientError, match="within the prediction horizon"
            ):
                _predict(
                    service,
                    release,
                    gate_events=(GateFlowEvent("S", START, 0.5),),
                    requirements=(requirement,),
                )
