"""Acceptance spec for PR 3.3 — POST /api/v1/control/predictions.

Claude-authored executable contract (g-coding-ds): the implementation must make
these pass WITHOUT modifying this file. The endpoint is strictly non-persistent
and non-commanding: it runs the exact pinned model snapshot for all three
response members over the typed routing topology and reports timelines plus
explicit violations. Unavailable transports are tolerated only when provably
dry and unrequested; anything else fails closed.
"""

import importlib.util
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.config_loader import (
    file_sha256,
    load_gate_calibrations_config,
    load_routing_topology,
)
from core.model_release import (
    EvidenceClass,
    HydraulicModelRelease,
    ModelLineage,
    OperatingEnvelope,
    ParameterDistribution,
    ReachResponseParameters,
    SourceArtifact,
    load_configured_hydraulic_model_release,
    model_release_content_hash,
)
from core.network_flow_controller import NetworkFlowController
from core.reach_response import reach_responses_from_model_release
from core.routing_topology import (
    RoutingElement,
    RoutingGeometryStatus,
    RoutingRole,
    build_routing_topology,
)
from services.control_prediction_service import (
    ControlPredictionService,
    build_withdrawal_structure_max_flow_map,
)

SERVICE_ROOT = Path(__file__).resolve().parents[2]
NETWORK = str(SERVICE_ROOT / "src" / "config" / "network.json")
GEOMETRY = str(SERVICE_ROOT / "src" / "config" / "canal_geometry.json")
CALIBRATIONS = str(SERVICE_ROOT / "src" / "config" / "gate_calibrations.json")
GEOMETRY_COVERAGE = str(SERVICE_ROOT / "src" / "config" / "geometry_coverage.json")
ROUTING_TOPOLOGY = str(SERVICE_ROOT / "src" / "config" / "routing_topology.json")
RELEASE_PATH = str(
    SERVICE_ROOT / "data" / "model-releases" / "engineering-prior-v3-v1.json"
)
CONTROL_PY = SERVICE_ROOT / "src" / "api" / "control.py"

TOPOLOGY = load_routing_topology(
    ROUTING_TOPOLOGY, NETWORK, GEOMETRY_COVERAGE, GEOMETRY
)

FLUME_REACH_ID = "C_M(0,0)_J(LMC,0+170)"
WASTE_WAY_STRUCTURE_ID = "M(0,0;1,0)"
RMC_FTO_STRUCTURE_ID = "M(0,0;2,0;1,0)"
RMC_DELIVERY_NODE_ID = "M(0,0;2,1)"
LMC_DELIVERY_NODE_ID = "M(0,2)"

STARTS_AT = datetime(2026, 7, 20, 23, 0, tzinfo=timezone.utc)
ENDS_AT = datetime(2026, 7, 21, 5, 0, tzinfo=timezone.utc)
MIDNIGHT = datetime(2026, 7, 21, 0, 0, tzinfo=timezone.utc)
TIMESTEP_SECONDS = 300.0
STEP_COUNT = 72

VIOLATION_KINDS = {
    "requirement_shortfall",
    "withdrawal_shortfall",
    "withdrawal_capacity_exceeded",
    "withdrawal_capacity_unavailable",
}


def _load_control():
    spec = importlib.util.spec_from_file_location(
        "flowmon_control_prediction_api_under_test",
        str(CONTROL_PY),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _controller() -> NetworkFlowController:
    return NetworkFlowController(NETWORK, GEOMETRY, CALIBRATIONS)


def _config_sha256(controller: NetworkFlowController) -> dict:
    return {
        **controller.config_sha256,
        "geometry_coverage": file_sha256(GEOMETRY_COVERAGE),
        "routing_topology": file_sha256(ROUTING_TOPOLOGY),
    }


def _app(
    control,
    controller: NetworkFlowController,
    release: HydraulicModelRelease | None,
    topology=TOPOLOGY,
    config_sha256: dict | None = None,
    withdrawal_capacity: tuple | None = None,
) -> FastAPI:
    responses = () if release is None else reach_responses_from_model_release(release)
    maximum_horizon_seconds = (
        None if release is None else release.operating_envelope.maximum_horizon_seconds
    )
    if withdrawal_capacity is None:
        withdrawal_capacity = build_withdrawal_structure_max_flow_map(
            topology, load_gate_calibrations_config(CALIBRATIONS)
        )
    control.flow_controller = controller
    app = FastAPI()
    app.state.hydraulic_model_release = release
    app.state.control_prediction_service = ControlPredictionService(
        topology,
        responses,
        maximum_horizon_seconds,
        withdrawal_capacity,
    )
    app.state.model_config_sha256 = (
        _config_sha256(controller) if config_sha256 is None else config_sha256
    )
    app.include_router(control.router, prefix="/api/v1/control")
    return app


def _trunk_branch_allocations(topology, wet_path: list[str]) -> list[dict]:
    """Cover EVERY multi-child allocation node: 1.0 along the wet path (or to the
    first sorted child off-path, where the water never arrives), 0.0 elsewhere."""
    children = defaultdict(list)
    for upstream, downstream in topology.allocation_edges():
        children[upstream].append(downstream)
    path_edges = set(zip(wet_path, wet_path[1:]))
    allocations = []
    for upstream in sorted(children):
        downstream_nodes = sorted(children[upstream])
        if len(downstream_nodes) <= 1:
            continue
        wet_children = [
            node for node in downstream_nodes if (upstream, node) in path_edges
        ]
        preferred = wet_children[0] if wet_children else downstream_nodes[0]
        for node in downstream_nodes:
            allocations.append(
                {
                    "upstream_node_id": upstream,
                    "downstream_node_id": node,
                    "fraction": 1.0 if node == preferred else 0.0,
                }
            )
    return allocations


@pytest.fixture(scope="module")
def real_setup():
    control = _load_control()
    controller = _controller()
    release = load_configured_hydraulic_model_release(
        RELEASE_PATH, TOPOLOGY.transport_reach_ids()
    )
    app = _app(control, controller, release)
    snapshot = app.state.control_prediction_service.model_snapshot(
        release, app.state.model_config_sha256, controller.actuation_approved
    )
    return {
        "client": TestClient(app),
        "release": release,
        "snapshot_id": snapshot["snapshot_id"],
        "config_sha256": app.state.model_config_sha256,
    }


def _base_request(setup, **overrides) -> dict:
    request = {
        "model_snapshot_id": setup["snapshot_id"],
        "model_release_id": setup["release"].release_id,
        "model_release_content_hash": setup["release"].content_hash,
        "initialization": {"kind": "dry"},
        "starts_at": STARTS_AT.isoformat(),
        "ends_at": ENDS_AT.isoformat(),
        "timestep_seconds": TIMESTEP_SECONDS,
        "source_flow_events": [
            {
                "node_id": "S",
                "effective_at": STARTS_AT.isoformat(),
                "flow_m3s": 0.5,
            }
        ],
        "operator_withdrawal_events": [],
        "branch_allocations": _trunk_branch_allocations(
            TOPOLOGY, ["S", "M(0,0)", "M(0,0;2,0)", RMC_DELIVERY_NODE_ID]
        ),
        "section_requirements": [
            {
                "requirement_id": "REQ-RMC-1",
                "section_id": "SEC-RMC-1",
                "delivery_node_id": RMC_DELIVERY_NODE_ID,
                "window_start": STARTS_AT.isoformat(),
                "window_end": ENDS_AT.isoformat(),
                "required_volume_m3": 50000.0,
                "maximum_delivery_m3s": 1.0,
                "approved_excess_m3": 0.0,
            }
        ],
    }
    request.update(overrides)
    return request


def _assert_member_series_aligned(member: dict) -> None:
    timeline = member["timeline"]
    length = len(timeline["sampled_at"])
    assert length == STEP_COUNT
    assert len(timeline["terminal_outflow_m3"]) == length
    for reach in timeline["reaches"]:
        for series in (
            "inflow_m3s",
            "outflow_m3s",
            "in_transit_volume_m3",
            "cumulative_declared_loss_m3",
        ):
            assert len(reach[series]) == length, (reach["reach_id"], series)
    for withdrawal in timeline["withdrawals"]:
        for series in (
            "planned_flow_m3s",
            "hydraulically_available_flow_m3s",
            "predicted_withdrawal_m3s",
            "shortfall_m3s",
            "capacity_check_status",
        ):
            assert len(withdrawal[series]) == length, (
                withdrawal["structure_id"],
                series,
            )
    for requirement in timeline["requirements"]:
        for series in (
            "predicted_delivered_m3",
            "status",
        ):
            assert len(requirement[series]) == length, (
                requirement["requirement_id"],
                series,
            )


class TestPredictionDoneGate:
    def test_prediction_runs_three_members_from_exact_snapshot(self, real_setup):
        request = _base_request(real_setup)
        first = real_setup["client"].post(
            "/api/v1/control/predictions", json=request
        )
        second = real_setup["client"].post(
            "/api/v1/control/predictions", json=request
        )

        assert first.status_code == 200, first.text
        assert first.content == second.content  # deterministic replay
        body = first.json()

        assert body["schema_version"] == 1
        assert body["mode"] == "open_loop_prediction"
        assert body["open_loop"] is True
        assert body["actual_state_known"] is False
        assert body["commandable"] is False
        assert body["persistence"] == "none"
        assert body["model_snapshot_id"] == real_setup["snapshot_id"]
        assert body["model_release_id"] == real_setup["release"].release_id
        assert (
            body["model_release_content_hash"]
            == real_setup["release"].content_hash
        )
        assert body["config_sha256"] == real_setup["config_sha256"]

        coverage = body["coverage"]
        assert coverage["excluded_transport_reaches"] == [
            {
                "reach_id": FLUME_REACH_ID,
                "reason": real_setup["release"].unavailable_reaches[0].reason,
            }
        ]
        assert len(coverage["modeled_transport_reach_ids"]) == 41
        assert FLUME_REACH_ID not in coverage["modeled_transport_reach_ids"]

        members = body["members"]
        assert [member["member"] for member in members] == [
            "lower",
            "nominal",
            "upper",
        ]
        for member in members:
            assert member["status"] == "completed"
            assert member["infeasibility"] is None
            timeline = member["timeline"]
            assert timeline is not None
            sampled_at = timeline["sampled_at"]
            assert sampled_at[0] == (
                STARTS_AT + timedelta(seconds=TIMESTEP_SECONDS)
            ).isoformat().replace("+00:00", "Z")
            assert sampled_at[-1] == ENDS_AT.isoformat().replace("+00:00", "Z")
            reach_ids = [reach["reach_id"] for reach in timeline["reaches"]]
            assert sorted(reach_ids) == sorted(
                coverage["modeled_transport_reach_ids"]
            )
            assert FLUME_REACH_ID not in reach_ids
            _assert_member_series_aligned(member)
            audit = timeline["mass_balance"]
            assert abs(audit["balance_error_m3"]) < 1e-6
            assert member["predicted_delivered_total_m3"] > 0.0
            kinds = {violation["kind"] for violation in member["violations"]}
            assert kinds <= VIOLATION_KINDS
            assert "requirement_shortfall" in kinds  # 50000 m3 is not deliverable

        delivered = [member["predicted_delivered_total_m3"] for member in members]
        # Lower parameters (less loss, shorter delay) must deliver strictly more.
        assert delivered[0] > delivered[1] + 1.0
        assert delivered[1] > delivered[2] + 1.0

    def test_prediction_runs_continuously_across_midnight(self, real_setup):
        response = real_setup["client"].post(
            "/api/v1/control/predictions", json=_base_request(real_setup)
        )

        assert response.status_code == 200, response.text
        nominal = response.json()["members"][1]
        timeline = nominal["timeline"]
        midnight_index = timeline["sampled_at"].index(
            MIDNIGHT.isoformat().replace("+00:00", "Z")
        )
        in_transit_at_midnight = sum(
            reach["in_transit_volume_m3"][midnight_index]
            for reach in timeline["reaches"]
        )
        assert in_transit_at_midnight > 0.0  # water in flight is carried over
        for requirement in timeline["requirements"]:
            series = requirement["predicted_delivered_m3"]
            assert all(
                later >= earlier for earlier, later in zip(series, series[1:])
            )  # no daily reset of delivered volume
        # Carry-over oracle: with the nominal ~64 min travel time, nothing is
        # delivered by midnight yet the horizon ends with real delivery — all
        # of it from water released BEFORE midnight, which a midnight state
        # reset would destroy.
        delivered = timeline["requirements"][0]["predicted_delivered_m3"]
        assert delivered[midnight_index] == 0.0
        assert delivered[-1] > 0.0


class TestPredictionFailClosed:
    def test_prediction_rejects_snapshot_or_release_drift(self, real_setup):
        drifted_snapshot = _base_request(real_setup)
        drifted_snapshot["model_snapshot_id"] = (
            "0" * 63 + ("1" if real_setup["snapshot_id"][63] != "1" else "2")
        )
        drifted_release_id = _base_request(
            real_setup, model_release_id="engineering-prior-v999"
        )
        drifted_hash = _base_request(real_setup)
        drifted_hash["model_release_content_hash"] = (
            "f" * 63 + ("0" if drifted_hash["model_release_content_hash"][63] != "0" else "1")
        )

        for request in (drifted_snapshot, drifted_release_id, drifted_hash):
            response = real_setup["client"].post(
                "/api/v1/control/predictions", json=request
            )
            assert response.status_code == 409, response.text

    def test_prediction_rejects_unavailable_transport_on_requested_path(
        self, real_setup
    ):
        requirement_below_flume = _base_request(real_setup)
        requirement_below_flume["section_requirements"][0] = {
            **requirement_below_flume["section_requirements"][0],
            "delivery_node_id": LMC_DELIVERY_NODE_ID,
        }

        positive_flume_allocation = _base_request(real_setup)
        for allocation in positive_flume_allocation["branch_allocations"]:
            if allocation["upstream_node_id"] == "M(0,0)":
                allocation["fraction"] = 0.5

        withdrawal_below_flume = _base_request(
            real_setup,
            operator_withdrawal_events=[
                {
                    "structure_id": WASTE_WAY_STRUCTURE_ID,
                    "effective_at": STARTS_AT.isoformat(),
                    "planned_flow_m3s": 0.1,
                    "purpose": "ecological release",
                    "operator_reference": None,
                }
            ],
        )

        for request in (
            requirement_below_flume,
            positive_flume_allocation,
            withdrawal_below_flume,
        ):
            response = real_setup["client"].post(
                "/api/v1/control/predictions", json=request
            )
            assert response.status_code == 400, response.text
            assert FLUME_REACH_ID in response.json()["detail"]

    def test_prediction_rejects_out_of_envelope_timestep_horizon_or_flow(
        self, real_setup
    ):
        too_fine = _base_request(real_setup, timestep_seconds=30.0)
        too_coarse = _base_request(real_setup, timestep_seconds=600.0)
        too_long = _base_request(
            real_setup,
            ends_at=(STARTS_AT + timedelta(days=8)).isoformat(),
        )
        too_much_flow = _base_request(real_setup)
        too_much_flow["source_flow_events"][0]["flow_m3s"] = 12.0

        for request in (too_fine, too_coarse, too_long, too_much_flow):
            response = real_setup["client"].post(
                "/api/v1/control/predictions", json=request
            )
            assert response.status_code == 400, response.text

    def test_prediction_requires_source_event_at_horizon_start(self, real_setup):
        late_start = _base_request(real_setup)
        late_start["source_flow_events"][0]["effective_at"] = (
            STARTS_AT + timedelta(seconds=TIMESTEP_SECONDS)
        ).isoformat()

        response = real_setup["client"].post(
            "/api/v1/control/predictions", json=late_start
        )
        assert response.status_code == 400, response.text

        empty_events = _base_request(real_setup, source_flow_events=[])
        response = real_setup["client"].post(
            "/api/v1/control/predictions", json=empty_events
        )
        assert response.status_code == 422, response.text

    def test_prediction_rejects_extra_fields_and_boolean_numbers(self, real_setup):
        extra_field = _base_request(real_setup)
        extra_field["persist"] = True

        boolean_flow = _base_request(real_setup)
        boolean_flow["source_flow_events"][0]["flow_m3s"] = True

        boolean_timestep = _base_request(real_setup, timestep_seconds=True)

        non_root_source = _base_request(real_setup)
        non_root_source["source_flow_events"][0]["node_id"] = "M(0,3)"

        wet_initialization = _base_request(
            real_setup, initialization={"kind": "actual"}
        )

        for request in (
            extra_field,
            boolean_flow,
            boolean_timestep,
            non_root_source,
            wet_initialization,
        ):
            response = real_setup["client"].post(
                "/api/v1/control/predictions", json=request
            )
            assert response.status_code == 422, response.text

    def test_prediction_without_configured_release_is_unavailable(self):
        control = _load_control()
        controller = _controller()
        client = TestClient(_app(control, controller, None))
        release = load_configured_hydraulic_model_release(
            RELEASE_PATH, TOPOLOGY.transport_reach_ids()
        )
        request = _base_request(
            {
                "release": release,
                "snapshot_id": "0" * 64,
                "config_sha256": {},
            }
        )

        response = client.post("/api/v1/control/predictions", json=request)
        assert response.status_code == 503, response.text


class TestPredictionHonesty:
    def test_withdrawal_capacity_unknown_is_not_approved(self, real_setup):
        request = _base_request(
            real_setup,
            operator_withdrawal_events=[
                {
                    "structure_id": RMC_FTO_STRUCTURE_ID,
                    "effective_at": STARTS_AT.isoformat(),
                    "planned_flow_m3s": 0.2,
                    "purpose": "farm turnout offtake",
                    "operator_reference": "RID-FTO-2450",
                }
            ],
        )

        response = real_setup["client"].post(
            "/api/v1/control/predictions", json=request
        )
        assert response.status_code == 200, response.text

        for member in response.json()["members"]:
            assert member["status"] == "completed"
            capacity_violations = [
                violation
                for violation in member["violations"]
                if violation["kind"] == "withdrawal_capacity_unavailable"
            ]
            assert [
                violation["structure_id"] for violation in capacity_violations
            ] == [RMC_FTO_STRUCTURE_ID]
            fto_series = next(
                withdrawal
                for withdrawal in member["timeline"]["withdrawals"]
                if withdrawal["structure_id"] == RMC_FTO_STRUCTURE_ID
            )
            assert set(fto_series["capacity_check_status"]) == {"unavailable"}

    def test_prediction_response_never_claims_actual_delivery(self, real_setup):
        response = real_setup["client"].post(
            "/api/v1/control/predictions", json=_base_request(real_setup)
        )
        assert response.status_code == 200, response.text
        body = response.json()

        forbidden = ("confirmed", "measured", "observed")
        offending: list[str] = []

        def _walk_keys(value):
            if isinstance(value, dict):
                for key, nested in value.items():
                    lowered = key.lower()
                    if key != "actual_state_known" and (
                        "actual" in lowered
                        or any(token in lowered for token in forbidden)
                    ):
                        offending.append(key)
                    _walk_keys(nested)
            elif isinstance(value, list):
                for item in value:
                    _walk_keys(item)

        _walk_keys(body)
        assert offending == []
        assert body["actual_state_known"] is False
        assert body["open_loop"] is True
        assert body["commandable"] is False

    def test_prediction_response_series_align_with_every_sample(self, real_setup):
        response = real_setup["client"].post(
            "/api/v1/control/predictions", json=_base_request(real_setup)
        )
        assert response.status_code == 200, response.text
        for member in response.json()["members"]:
            _assert_member_series_aligned(member)


def _mini_topology():
    return build_routing_topology(
        (
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
        )
    )


def _mini_release() -> HydraulicModelRelease:
    release = HydraulicModelRelease(
        schema_version=1,
        release_id="engineering-prior-mini-v1",
        generated_at=datetime(2026, 7, 16, 2, 0, tzinfo=timezone.utc),
        evidence_class=EvidenceClass.ENGINEERING_PRIOR,
        commandable=False,
        lineage=ModelLineage(
            "release-builder",
            "1.0.0",
            (SourceArtifact("network", "v1", "d" * 64),),
        ),
        operating_envelope=OperatingEnvelope(0.0, 12.0, 60.0, 300.0, 604800.0),
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


MINI_CONFIG_SHA256 = {
    "network": "a" * 64,
    "canal_geometry": "b" * 64,
    "gate_calibrations": "c" * 64,
    "geometry_coverage": "1" * 64,
    "routing_topology": "2" * 64,
}


class TestPredictionMemberInfeasibility:
    def test_member_capacity_failure_does_not_hide_other_members(self):
        control = _load_control()
        controller = _controller()
        release = _mini_release()
        topology = _mini_topology()
        app = _app(
            control,
            controller,
            release,
            topology=topology,
            config_sha256=MINI_CONFIG_SHA256,
            withdrawal_capacity=(),
        )
        snapshot = app.state.control_prediction_service.model_snapshot(
            release, MINI_CONFIG_SHA256, controller.actuation_approved
        )
        starts_at = datetime(2026, 7, 20, 23, 0, tzinfo=timezone.utc)
        ends_at = starts_at + timedelta(hours=1)
        request = {
            "model_snapshot_id": snapshot["snapshot_id"],
            "model_release_id": release.release_id,
            "model_release_content_hash": release.content_hash,
            "initialization": {"kind": "dry"},
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "timestep_seconds": 300.0,
            "source_flow_events": [
                {
                    "node_id": "S",
                    "effective_at": starts_at.isoformat(),
                    # Above the LOWER member capacity (1.0), below nominal/upper.
                    "flow_m3s": 1.2,
                }
            ],
            "operator_withdrawal_events": [],
            "branch_allocations": [],
            "section_requirements": [
                {
                    "requirement_id": "REQ-MINI-1",
                    "section_id": "SEC-MINI-1",
                    "delivery_node_id": "A",
                    "window_start": starts_at.isoformat(),
                    "window_end": ends_at.isoformat(),
                    "required_volume_m3": 100000.0,
                    "maximum_delivery_m3s": 2.0,
                    "approved_excess_m3": 0.0,
                }
            ],
        }

        response = TestClient(app).post(
            "/api/v1/control/predictions", json=request
        )
        assert response.status_code == 200, response.text
        members = response.json()["members"]

        lower = members[0]
        assert lower["member"] == "lower"
        assert lower["status"] == "infeasible"
        assert lower["timeline"] is None
        assert lower["predicted_delivered_total_m3"] is None
        assert lower["infeasibility"]["kind"] == "reach_capacity_exceeded"
        assert lower["infeasibility"]["reach_id"] == "C_S_A"

        for member in members[1:]:
            assert member["status"] == "completed"
            assert member["infeasibility"] is None
            assert member["timeline"] is not None
            kinds = {violation["kind"] for violation in member["violations"]}
            assert "requirement_shortfall" in kinds
