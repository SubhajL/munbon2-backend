import copy
import importlib.util
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from core.commandability_approval import commandability_approval_content_hash
from core.demand_contract import content_hash
from core.model_release import (
    EvidenceClass,
    HydraulicModelRelease,
    ModelLineage,
    OperatingEnvelope,
    ParameterDistribution,
    ReachResponseParameters,
    SourceArtifact,
    UnavailableReach,
    model_release_content_hash,
)
from core.config_loader import load_routing_topology
from core.network_flow_controller import NetworkFlowController
from core.prediction_engine import build_prediction_engine_descriptor
from core.reach_response import reach_responses_from_model_release
from schemas.control import ModelSnapshotResponse
from services.control_prediction_service import ControlPredictionService

SERVICE_ROOT = Path(__file__).resolve().parents[2]
NETWORK = str(SERVICE_ROOT / "src" / "config" / "network.json")
GEOMETRY = str(SERVICE_ROOT / "src" / "config" / "canal_geometry.json")
CALIBRATIONS = str(SERVICE_ROOT / "src" / "config" / "gate_calibrations.json")
GEOMETRY_COVERAGE = str(SERVICE_ROOT / "src" / "config" / "geometry_coverage.json")
ROUTING_TOPOLOGY = str(SERVICE_ROOT / "src" / "config" / "routing_topology.json")
CONTROL_PY = SERVICE_ROOT / "src" / "api" / "control.py"
ENGINE_DESCRIPTOR = build_prediction_engine_descriptor(SERVICE_ROOT)

TOPOLOGY = load_routing_topology(ROUTING_TOPOLOGY, NETWORK, GEOMETRY_COVERAGE, GEOMETRY)


def _load_control():
    spec = importlib.util.spec_from_file_location(
        "flowmon_model_snapshot_api_under_test",
        str(CONTROL_PY),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _controller() -> NetworkFlowController:
    return NetworkFlowController(NETWORK, GEOMETRY, CALIBRATIONS)


def _model_release(
    controller: NetworkFlowController,
) -> HydraulicModelRelease:
    reach_ids = TOPOLOGY.transport_reach_ids()
    release = HydraulicModelRelease(
        schema_version=1,
        release_id="engineering-prior-api-v1",
        generated_at=datetime(2026, 7, 16, 2, 0, tzinfo=timezone.utc),
        evidence_class=EvidenceClass.ENGINEERING_PRIOR,
        commandable=False,
        lineage=ModelLineage(
            "build_hydraulic_model_release",
            "1.0.0",
            (
                SourceArtifact(
                    "network",
                    "canonical-v1",
                    controller.config_sha256["network"],
                ),
            ),
        ),
        operating_envelope=OperatingEnvelope(
            0.0,
            12.0,
            60.0,
            300.0,
            604800.0,
        ),
        reach_parameters=(
            ReachResponseParameters(
                reach_ids[0],
                ParameterDistribution(0.0, 0.0, 0.0),
                ParameterDistribution(0.0, 0.0, 0.0),
                ParameterDistribution(0.0, 0.0, 0.0),
                ParameterDistribution(10.0, 11.0, 12.0),
                ("network",),
            ),
        ),
        unavailable_reaches=tuple(
            UnavailableReach(reach_id, "engineering evidence is unavailable")
            for reach_id in reach_ids[1:]
        ),
        content_hash="0" * 64,
    )
    return replace(release, content_hash=model_release_content_hash(release))


def _app(
    control,
    controller: NetworkFlowController,
    release: HydraulicModelRelease | None,
    approval: dict | None = None,
) -> FastAPI:
    responses = () if release is None else reach_responses_from_model_release(release)
    maximum_horizon_seconds = (
        None if release is None else release.operating_envelope.maximum_horizon_seconds
    )
    control.flow_controller = controller
    app = FastAPI()
    app.state.hydraulic_model_release = release
    app.state.commandability_approval = approval
    app.state.control_prediction_service = ControlPredictionService(
        TOPOLOGY,
        responses,
        maximum_horizon_seconds,
        _withdrawal_capacity(),
        prediction_engine_descriptor=ENGINE_DESCRIPTOR,
    )
    app.state.model_config_sha256 = _config_sha256(controller)
    app.include_router(control.router, prefix="/api/v1/control")
    return app


def _approval(
    controller: NetworkFlowController, release: HydraulicModelRelease
) -> dict:
    envelope = release.operating_envelope
    payload = {
        "schema_version": 1,
        "approval_state": "approved",
        "base_model_release": {
            "release_id": release.release_id,
            "content_hash": release.content_hash,
        },
        "prediction_engine": {"content_hash": ENGINE_DESCRIPTOR["content_hash"]},
        "model_config_sha256": _config_sha256(controller),
        "operating_envelope": {
            "minimum_flow_m3s": envelope.minimum_flow_m3s,
            "maximum_flow_m3s": envelope.maximum_flow_m3s,
            "minimum_timestep_seconds": envelope.minimum_timestep_seconds,
            "maximum_timestep_seconds": envelope.maximum_timestep_seconds,
            "maximum_horizon_seconds": envelope.maximum_horizon_seconds,
        },
        "device_capability": {
            "capability_release_id": "d6-pilot-v1",
            "capability_hash": "a" * 64,
            "approved_gate_ids": ["M(0,0)"],
        },
        "approval": {
            "approved_by_role": "RID hydraulic model authority",
            "approved_at": "2026-07-21T08:00:00Z",
            "approval_reference": "RID-COMMISSIONING-2026-001",
            "evidence": [
                {
                    "kind": "signed-assessment",
                    "reference": "doc://rid/commissioning/2026-001",
                    "sha256": "b" * 64,
                }
            ],
        },
    }
    return {**payload, "content_hash": commandability_approval_content_hash(payload)}


def _withdrawal_capacity() -> tuple:
    from core.routing_topology import RoutingRole

    return tuple(
        sorted(
            (element.downstream_node_id, None)
            for element in TOPOLOGY.elements
            if element.role is RoutingRole.WITHDRAWAL_STRUCTURE
        )
    )


def _config_sha256(controller: NetworkFlowController) -> dict:
    from core.config_loader import file_sha256

    return {
        **controller.config_sha256,
        "geometry_coverage": file_sha256(GEOMETRY_COVERAGE),
        "routing_topology": file_sha256(ROUTING_TOPOLOGY),
    }


class TestModelSnapshotEndpoint:
    def test_returns_strict_v4_only_for_the_loaded_approved_runtime_binding(self):
        control = _load_control()
        controller = _controller()
        release = _model_release(controller)
        approval = _approval(controller, release)

        response = TestClient(_app(control, controller, release, approval)).post(
            "/api/v1/control/model-snapshots"
        )

        assert response.status_code == 200
        body = response.json()
        assert {
            "schema_version": body["schema_version"],
            "commandable": body["commandable"],
            "response_commandable": body["response_model"]["commandable"],
            "action_commandable": body["action_model"]["commandable"],
            "actuation_approved": body["action_model"]["actuation_approved"],
            "approval": body["commandability_approval"],
        } == {
            "schema_version": 4,
            "commandable": True,
            "response_commandable": True,
            "action_commandable": True,
            "actuation_approved": True,
            "approval": approval,
        }
        ModelSnapshotResponse.model_validate(body)

    def test_returns_explicit_unavailable_state_without_configured_release(self):
        control = _load_control()
        controller = _controller()
        client = TestClient(_app(control, controller, None))

        first = client.post("/api/v1/control/model-snapshots")
        second = client.post("/api/v1/control/model-snapshots")

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        body = first.json()
        assert {
            "data_status": body["data_status"],
            "open_loop": body["open_loop"],
            "actual_state_known": body["actual_state_known"],
            "commandable": body["commandable"],
            "response_model": body["response_model"],
            "coverage": body["transport_response_coverage"],
        } == {
            "data_status": "unavailable",
            "open_loop": True,
            "actual_state_known": False,
            "commandable": False,
            "response_model": None,
            "coverage": {
                "total_transport_reaches": 42,
                "available_transport_reaches": 0,
                "unavailable_transport_reaches": 42,
            },
        }
        assert len(body["snapshot_id"]) == 64
        payload = {key: value for key, value in body.items() if key != "snapshot_id"}
        assert body["snapshot_id"] == content_hash(payload)
        assert body["schema_version"] == 3
        assert body["prediction_engine"] == ENGINE_DESCRIPTOR
        assert body["scada_graph"]["gate_count"] == 58
        assert len(body["scada_graph"]["edges"]) == 58
        assert body["routing_topology"]["element_count"] == 59
        assert body["routing_topology"]["role_counts"] == {
            "boundary": 1,
            "transport": 42,
            "branch_structure": 13,
            "withdrawal_structure": 3,
        }
        assert len(body["unavailable_transport_reaches"]) == 42
        assert {item["reason"] for item in body["unavailable_transport_reaches"]} == {
            "hydraulic model release is not configured"
        }

    def test_returns_configured_release_and_exact_action_lineage(self):
        control = _load_control()
        controller = _controller()
        release = _model_release(controller)
        response = TestClient(_app(control, controller, release)).post(
            "/api/v1/control/model-snapshots"
        )

        assert response.status_code == 200
        body = response.json()
        assert (
            body["data_status"],
            body["transport_response_coverage"],
            body["response_model"]["release_id"],
            body["response_model"]["content_hash"],
            len(body["response_model"]["response_members"]),
            body["action_model"]["config_sha256"],
            body["action_model"]["allowed_node_ids"],
            body["action_model"]["requires_explicit_branch_allocations"],
            body["action_model"]["commandable"],
        ) == (
            "partial",
            {
                "total_transport_reaches": 42,
                "available_transport_reaches": 1,
                "unavailable_transport_reaches": 41,
            },
            release.release_id,
            release.content_hash,
            3,
            {
                "canal_geometry": controller.config_sha256["canal_geometry"],
                "gate_calibrations": controller.config_sha256["gate_calibrations"],
                "geometry_coverage": _config_sha256(controller)["geometry_coverage"],
            },
            ["S"],
            True,
            False,
        )
        payload = {key: value for key, value in body.items() if key != "snapshot_id"}
        assert body["snapshot_id"] == content_hash(payload)

    @pytest.mark.parametrize("path", [(), ("action_model",)])
    def test_response_schema_rejects_fields_outside_snapshot_identity(self, path):
        control = _load_control()
        controller = _controller()
        body = (
            TestClient(_app(control, controller, None))
            .post("/api/v1/control/model-snapshots")
            .json()
        )
        tampered = copy.deepcopy(body)
        target = tampered
        for key in path:
            target = target[key]
        target["unhashed_field"] = "must not be projected away"

        with pytest.raises(ValidationError, match="extra"):
            ModelSnapshotResponse.model_validate(tampered)

    def test_returns_503_when_prediction_service_state_is_absent(self):
        control = _load_control()
        control.flow_controller = _controller()
        app = FastAPI()
        app.include_router(control.router, prefix="/api/v1/control")

        response = TestClient(app).post("/api/v1/control/model-snapshots")

        assert response.status_code == 503
        assert response.json() == {
            "detail": "Control prediction service not initialized"
        }

    def test_returns_503_when_release_state_is_absent(self):
        control = _load_control()
        controller = _controller()
        control.flow_controller = controller
        app = FastAPI()
        app.state.control_prediction_service = ControlPredictionService(
            TOPOLOGY, (), None, _withdrawal_capacity()
        )
        app.include_router(control.router, prefix="/api/v1/control")

        response = TestClient(app).post("/api/v1/control/model-snapshots")

        assert response.status_code == 503
        assert response.json() == {
            "detail": "Hydraulic model release state not initialized"
        }

    def test_returns_503_when_runtime_and_release_state_drift(self):
        control = _load_control()
        controller = _controller()
        release = _model_release(controller)
        app = _app(control, controller, release)
        app.state.hydraulic_model_release = None

        response = TestClient(app).post("/api/v1/control/model-snapshots")

        assert response.status_code == 503
        assert "model" in response.json()["detail"]

    def test_returns_503_when_prediction_service_state_has_wrong_type(self):
        control = _load_control()
        controller = _controller()
        control.flow_controller = controller
        app = FastAPI()
        app.state.control_prediction_service = object()
        app.state.hydraulic_model_release = None
        app.include_router(control.router, prefix="/api/v1/control")

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/v1/control/model-snapshots"
        )

        assert response.status_code == 503
        assert response.json() == {
            "detail": "Control prediction service state is invalid"
        }

    def test_returns_503_when_release_state_has_wrong_type(self):
        control = _load_control()
        controller = _controller()
        app = _app(control, controller, None)
        app.state.hydraulic_model_release = object()

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/v1/control/model-snapshots"
        )

        assert response.status_code == 503
        assert response.json() == {"detail": "Hydraulic model release state is invalid"}
