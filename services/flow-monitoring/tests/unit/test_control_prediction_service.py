from datetime import datetime, timedelta, timezone

import pytest

from core.fulfillment import (
    ClosureProjection,
    ClosureRequirement,
    VolumeBounds,
)
from core.network_transient import GateFlowEvent, NetworkTransientError
from core.reach_response import ReachResponse, ReachState, ResponseMember
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
