from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

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
from core.network_transient import GateFlowEvent, NetworkTransientError
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
from services.control_prediction_service import ControlPredictionService

START = datetime(2026, 7, 16, tzinfo=timezone.utc)


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


def test_prediction_service_returns_snapshot_bound_to_its_release_horizon():
    release = _model_release()
    service = ControlPredictionService(
        _topology((("S", "A"),)),
        reach_responses_from_model_release(release),
        release.operating_envelope.maximum_horizon_seconds,
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
