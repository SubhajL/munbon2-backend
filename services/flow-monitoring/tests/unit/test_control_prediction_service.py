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
from services.control_prediction_service import ControlPredictionService

START = datetime(2026, 7, 16, tzinfo=timezone.utc)
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
    service = ControlPredictionService((("S", "A"),), (RESPONSE,), 3600.0)
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
    service = ControlPredictionService((("S", "A"),), (RESPONSE,), 60.0)

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
    service = ControlPredictionService((("S", "A"), ("A", "B"), ("A", "C")), (), None)
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


def test_prediction_service_returns_snapshot_bound_to_its_release_horizon():
    release = _model_release()
    service = ControlPredictionService(
        (("S", "A"),),
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
        (("S", "A"),),
        reach_responses_from_model_release(release),
        1800.0,
    )

    with pytest.raises(ModelSnapshotError, match="horizon"):
        service.model_snapshot(release, CONFIG_SHA256, False)


@pytest.mark.parametrize(
    "network_edges,reach_responses,maximum_horizon_seconds",
    [
        ([("S", "A")], (RESPONSE,), 60.0),
        ((("S", "A"),), [RESPONSE], 60.0),
        ((("S", "A"),), (RESPONSE,), None),
        ((("S", "A"),), (RESPONSE,), float("nan")),
    ],
)
def test_prediction_service_rejects_mutable_or_missing_release_contract(
    network_edges, reach_responses, maximum_horizon_seconds
):
    with pytest.raises(NetworkTransientError):
        ControlPredictionService(
            network_edges, reach_responses, maximum_horizon_seconds
        )
