"""Strict upstream clients: contract enforcement without any network."""

import hashlib
import inspect
import json
from datetime import date
from uuid import UUID

import httpx
import pytest

from services.clients.control_client_errors import (
    FlowLineageConflictError,
    PredictionRequestRejectedError,
    RequirementStateError,
    RequirementsUnpublishedError,
    UpstreamContractViolation,
    UpstreamUnavailableError,
)
from services.clients.control_flow_client import ControlFlowClient
from services.clients.ros_gis_requirements_client import (
    RosGisRequirementsClient,
)

RUN_ID = UUID("8e0b0e6a-6c1e-5f5e-9d5c-2f6a8b1c2d3e")
OTHER_RUN_ID = UUID("00000000-0000-4000-8000-000000000001")
REQ_ID = "7c8a4c62-4b0e-5efd-9c3a-111111111111"
SCOPES = [(date(2026, 7, 20), 1)]


def _item(**overrides):
    item = {
        "requirementId": REQ_ID,
        "runId": str(RUN_ID),
        "version": 3,
        "serviceDate": "2026-07-20",
        "sectionId": "SEC-1",
        "zone": 1,
        "requiredVolumeM3": 1200.0,
        "deliveryWindow": {
            "start": "2026-07-20T06:00:00+00:00",
            "end": "2026-07-20T18:00:00+00:00",
        },
        "quality": "estimated",
        "publishedAt": "2026-07-19T19:05:00+00:00",
        "freshness": {"asOfDate": "2026-07-19", "publishedAgeSeconds": 3600},
        "dataStatus": "published",
    }
    item.update(overrides)
    return item


def _daily_body(items=None, data_status="published"):
    return {
        "serviceDate": "2026-07-20",
        "zone": 1,
        "dataStatus": data_status,
        "requirements": items if items is not None else [_item()],
    }


def _ros_client(handler):
    transport = httpx.MockTransport(handler)
    return RosGisRequirementsClient(
        "http://ros-gis", client=httpx.AsyncClient(transport=transport)
    )


def _flow_client(handler):
    transport = httpx.MockTransport(handler)
    return ControlFlowClient(
        "http://flow", client=httpx.AsyncClient(transport=transport)
    )


class TestRosGisRequirementsClient:
    @pytest.mark.asyncio
    async def test_published_items_are_normalized_snake_case(self):
        def handler(request):
            assert request.url.path == "/api/v1/water-requirements/daily"
            assert request.url.params["service_date"] == "2026-07-20"
            assert request.url.params["zone"] == "1"
            return httpx.Response(200, json=_daily_body())

        client = _ros_client(handler)
        items = await client.get_exact_requirements(RUN_ID, 3, SCOPES)
        assert len(items) == 1
        item = items[0]
        assert item["requirement_id"] == REQ_ID
        assert item["section_id"] == "SEC-1"
        assert item["service_date"] == date(2026, 7, 20)
        assert item["window_start"].isoformat() == "2026-07-20T06:00:00+00:00"
        assert "publishedAgeSeconds" not in json.dumps(list(item))

    @pytest.mark.asyncio
    async def test_run_drift_is_exact_version_conflict(self):
        def handler(request):
            return httpx.Response(
                200, json=_daily_body([_item(runId=str(OTHER_RUN_ID))])
            )

        client = _ros_client(handler)
        with pytest.raises(RequirementStateError) as excinfo:
            await client.get_exact_requirements(RUN_ID, 3, SCOPES)
        assert excinfo.value.detail["served_run_id"] == str(OTHER_RUN_ID)

    @pytest.mark.asyncio
    async def test_version_drift_is_exact_version_conflict(self):
        def handler(request):
            return httpx.Response(200, json=_daily_body([_item(version=4)]))

        client = _ros_client(handler)
        with pytest.raises(RequirementStateError):
            await client.get_exact_requirements(RUN_ID, 3, SCOPES)

    @pytest.mark.asyncio
    async def test_non_published_item_fails_closed(self):
        def handler(request):
            return httpx.Response(200, json=_daily_body([_item(dataStatus="stale")]))

        client = _ros_client(handler)
        with pytest.raises(RequirementStateError) as excinfo:
            await client.get_exact_requirements(RUN_ID, 3, SCOPES)
        assert excinfo.value.detail["data_status"] == "stale"

    @pytest.mark.asyncio
    async def test_no_publication_is_unavailable(self):
        def handler(request):
            return httpx.Response(
                200, json=_daily_body([], data_status="no_publication")
            )

        client = _ros_client(handler)
        with pytest.raises(RequirementsUnpublishedError):
            await client.get_exact_requirements(RUN_ID, 3, SCOPES)

    @pytest.mark.asyncio
    async def test_server_error_is_unavailable(self):
        def handler(request):
            return httpx.Response(500, text="boom")

        client = _ros_client(handler)
        with pytest.raises(UpstreamUnavailableError):
            await client.get_exact_requirements(RUN_ID, 3, SCOPES)

    @pytest.mark.asyncio
    async def test_network_error_is_unavailable(self):
        def handler(request):
            raise httpx.ConnectError("refused", request=request)

        client = _ros_client(handler)
        with pytest.raises(UpstreamUnavailableError):
            await client.get_exact_requirements(RUN_ID, 3, SCOPES)

    @pytest.mark.asyncio
    async def test_naive_upstream_datetime_is_contract_violation(self):
        body = _daily_body(
            [
                _item(
                    deliveryWindow={
                        "start": "2026-07-20T06:00:00",
                        "end": "2026-07-20T18:00:00+00:00",
                    }
                )
            ]
        )

        def handler(request):
            return httpx.Response(200, json=body)

        client = _ros_client(handler)
        with pytest.raises(UpstreamContractViolation):
            await client.get_exact_requirements(RUN_ID, 3, SCOPES)

    @pytest.mark.asyncio
    async def test_malformed_body_is_contract_violation(self):
        def handler(request):
            return httpx.Response(200, json={"unexpected": True})

        client = _ros_client(handler)
        with pytest.raises(UpstreamContractViolation):
            await client.get_exact_requirements(RUN_ID, 3, SCOPES)

    @pytest.mark.asyncio
    async def test_collection_scope_mismatch_is_contract_violation(self):
        body = _daily_body()
        body["zone"] = 2

        def handler(request):
            return httpx.Response(200, json=body)

        client = _ros_client(handler)
        with pytest.raises(UpstreamContractViolation):
            await client.get_exact_requirements(RUN_ID, 3, SCOPES)

    @pytest.mark.asyncio
    async def test_item_scope_mismatch_is_contract_violation(self):
        def handler(request):
            return httpx.Response(200, json=_daily_body([_item(zone=2)]))

        client = _ros_client(handler)
        with pytest.raises(UpstreamContractViolation):
            await client.get_exact_requirements(RUN_ID, 3, SCOPES)

    @pytest.mark.asyncio
    async def test_negative_volume_is_contract_violation(self):
        def handler(request):
            return httpx.Response(200, json=_daily_body([_item(requiredVolumeM3=-1.0)]))

        client = _ros_client(handler)
        with pytest.raises(UpstreamContractViolation):
            await client.get_exact_requirements(RUN_ID, 3, SCOPES)

    @pytest.mark.asyncio
    async def test_unknown_quality_is_contract_violation(self):
        def handler(request):
            return httpx.Response(200, json=_daily_body([_item(quality="measured")]))

        client = _ros_client(handler)
        with pytest.raises(UpstreamContractViolation):
            await client.get_exact_requirements(RUN_ID, 3, SCOPES)

    @pytest.mark.asyncio
    async def test_duplicate_section_on_service_date_is_contract_violation(self):
        def handler(request):
            return httpx.Response(
                200,
                json=_daily_body(
                    [
                        _item(),
                        _item(requirementId="7c8a4c62-4b0e-5efd-9c3a-222222222222"),
                    ]
                ),
            )

        client = _ros_client(handler)
        with pytest.raises(UpstreamContractViolation):
            await client.get_exact_requirements(RUN_ID, 3, SCOPES)

    @pytest.mark.asyncio
    async def test_non_finite_volume_is_contract_violation(self):
        # httpx serializes Infinity via json; the strict mirror must reject it
        # rather than let it reach canonical serialization as a 500.
        def handler(request):
            body = _daily_body()
            body["requirements"][0]["requiredVolumeM3"] = float("inf")
            return httpx.Response(200, content=json.dumps(body).encode())

        client = _ros_client(handler)
        with pytest.raises(UpstreamContractViolation):
            await client.get_exact_requirements(RUN_ID, 3, SCOPES)

    @pytest.mark.asyncio
    async def test_unknown_data_status_is_contract_violation(self):
        def handler(request):
            return httpx.Response(
                200, json=_daily_body([_item(dataStatus="in_review")])
            )

        client = _ros_client(handler)
        with pytest.raises(UpstreamContractViolation):
            await client.get_exact_requirements(RUN_ID, 3, SCOPES)

    @pytest.mark.asyncio
    async def test_duplicate_requirement_id_is_contract_violation(self):
        def handler(request):
            return httpx.Response(
                200,
                json=_daily_body(
                    [_item(), _item(sectionId="SEC-2")]  # same requirementId
                ),
            )

        client = _ros_client(handler)
        with pytest.raises(UpstreamContractViolation):
            await client.get_exact_requirements(RUN_ID, 3, SCOPES)


def _snapshot_body(**overrides):
    body = {
        "schema_version": 3,
        "snapshot_id": "a" * 64,
        "data_status": "complete",
        "commandable": False,
        "prediction_engine": {
            "schema_version": 1,
            "engine_id": "munbon.flow-monitoring.network-transient",
            "semantic_contract_version": 1,
            "build_digest": "a" * 64,
            "content_hash": "b" * 64,
        },
        "routing_topology": {
            "config_sha256": "c" * 64,
            "elements": [
                {
                    "element_id": "R1",
                    "upstream_node_id": "S",
                    "downstream_node_id": "N1",
                    "role": "transport",
                }
            ],
        },
        "action_model": {
            "commandable": False,
            "actuation_approved": False,
            "config_sha256": {
                "canal_geometry": "d" * 64,
                "gate_calibrations": "e" * 64,
                "geometry_coverage": "f" * 64,
            },
            "operating_envelope": {
                "minimum_flow_m3s": 0.0,
                "maximum_flow_m3s": 10.0,
                "minimum_timestep_seconds": 300.0,
                "maximum_timestep_seconds": 3600.0,
                "maximum_horizon_seconds": 604800.0,
            },
        },
        "response_model": {
            "release_id": "release-2026-07",
            "content_hash": "b" * 64,
            "commandable": False,
            "response_members": [
                {
                    "reach_id": "R1",
                    "member": "nominal",
                    "delay_seconds": 600.0,
                    "loss_fraction": 0.05,
                    "capacity_m3s": 5.0,
                }
            ],
        },
        "unavailable_transport_reaches": [],
    }
    body.update(overrides)
    return body


def _approved_snapshot_body():
    body = _snapshot_body(
        schema_version=4,
        commandable=True,
    )
    body["response_model"]["commandable"] = True
    body["action_model"]["commandable"] = True
    body["action_model"]["actuation_approved"] = True
    body["scada_graph"] = {"config_sha256": "1" * 64}
    body["commandability_approval"] = {
        "schema_version": 1,
        "approval_state": "approved",
        "base_model_release": {
            "release_id": "release-2026-07",
            "content_hash": "b" * 64,
        },
        "prediction_engine": {"content_hash": "b" * 64},
        "model_config_sha256": {
            "network": "1" * 64,
            "routing_topology": "c" * 64,
            "canal_geometry": "d" * 64,
            "gate_calibrations": "e" * 64,
            "geometry_coverage": "f" * 64,
        },
        "operating_envelope": body["action_model"]["operating_envelope"],
        "device_capability": {
            "capability_release_id": "field-registry-2026.07",
            "capability_hash": "8" * 64,
            "approved_gate_ids": ["MC-01"],
        },
        "approval": {
            "approved_by_role": "RID hydraulic model authority",
            "approved_at": "2026-07-21T08:00:00Z",
            "approval_reference": "RID-COMMISSIONING-2026-001",
            "evidence": [
                {
                    "kind": "signed-assessment",
                    "reference": "doc://rid/commissioning/2026-001",
                    "sha256": "7" * 64,
                }
            ],
        },
        "content_hash": "9" * 64,
    }
    return body


def _prediction_request():
    return {
        "model_snapshot_id": "a" * 64,
        "model_release_id": "release-2026-07",
        "model_release_content_hash": "b" * 64,
        "initialization": {"kind": "dry"},
        "starts_at": "2026-07-20T00:00:00+00:00",
        "ends_at": "2026-07-21T00:00:00+00:00",
        "timestep_seconds": 300.0,
        "source_flow_events": [
            {
                "node_id": "S",
                "effective_at": "2026-07-20T00:00:00+00:00",
                "flow_m3s": 0.0,
            }
        ],
        "operator_withdrawal_events": [],
        "branch_allocations": [],
        "section_requirements": [],
    }


def _prediction_body(**overrides):
    request = _prediction_request()
    body = {
        "prediction_run_id": "c" * 64,
        "model_snapshot_id": request["model_snapshot_id"],
        "model_release_id": request["model_release_id"],
        "model_release_content_hash": request["model_release_content_hash"],
        "members": [
            {"member": "lower", "status": "completed"},
            {"member": "nominal", "status": "completed"},
            {"member": "upper", "status": "completed"},
        ],
    }
    body.update(overrides)
    return body


def _artifact_headers(content: bytes, overrides=None):
    """The PR 4.4b-1 identity-v2 artifact + engine headers over ``content``."""
    headers = {
        "X-Prediction-Identity-Version": "2",
        "X-Prediction-Artifact-SHA256": hashlib.sha256(content).hexdigest(),
        "X-Prediction-Artifact-Media-Type": "application/json",
        "X-Prediction-Artifact-Encoding": "canonical-json+zlib",
        "X-Prediction-Artifact-Encoding-Version": "1",
        "X-Prediction-Artifact-Uncompressed-Size": str(len(content)),
        "X-Prediction-Engine-Id": "munbon.flow-monitoring.network-transient",
        "X-Prediction-Semantic-Contract-Version": "1",
        "X-Prediction-Build-Digest": "a" * 64,
        "X-Prediction-Engine-Content-Hash": "b" * 64,
    }
    for key, value in (overrides or {}).items():
        if value is None:
            headers.pop(key, None)
        else:
            headers[key] = value
    return headers


def _prediction_response(body, header_overrides=None):
    """A 200 prediction response whose bytes ARE the canonical artifact and whose
    headers describe them (overridable to exercise the recompute/reject checks)."""
    content = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return httpx.Response(
        200, content=content, headers=_artifact_headers(content, header_overrides)
    )


class TestControlFlowClient:
    @pytest.mark.asyncio
    async def test_snapshot_returns_exact_text_and_mirror(self):
        body = _snapshot_body()

        def handler(request):
            assert request.url.path == "/api/v1/control/model-snapshots"
            return httpx.Response(200, json=body)

        client = _flow_client(handler)
        text, mirror = await client.create_model_snapshot()
        assert json.loads(text) == body
        assert mirror["snapshot_id"] == "a" * 64
        assert mirror["schema_version"] == 3
        assert mirror["response_model_release"]["release_id"] == ("release-2026-07")
        # The embedded engine descriptor is captured verbatim for the engine
        # cross-check the scheduler performs before recording a prediction.
        assert mirror["prediction_engine"] == {
            "engine_id": "munbon.flow-monitoring.network-transient",
            "semantic_contract_version": 1,
            "build_digest": "a" * 64,
            "content_hash": "b" * 64,
        }

    @pytest.mark.asyncio
    async def test_snapshot_non_v3_or_v4_schema_is_contract_violation(self):
        def handler(request):
            return httpx.Response(200, json=_snapshot_body(schema_version=2))

        client = _flow_client(handler)
        with pytest.raises(UpstreamContractViolation, match="schema_version"):
            await client.create_model_snapshot()

    @pytest.mark.asyncio
    async def test_snapshot_v4_requires_and_preserves_the_strict_approval(self):
        body = _approved_snapshot_body()

        def handler(request):
            return httpx.Response(200, json=body)

        _, mirror = await _flow_client(handler).create_model_snapshot()
        assert mirror["schema_version"] == 4
        assert mirror["commandability_approval"]["device_capability"] == {
            "capability_release_id": "field-registry-2026.07",
            "capability_hash": "8" * 64,
            "approved_gate_ids": ["MC-01"],
        }

    @pytest.mark.asyncio
    async def test_snapshot_v4_without_approval_is_contract_violation(self):
        body = _approved_snapshot_body()
        del body["commandability_approval"]

        def handler(request):
            return httpx.Response(200, json=body)

        with pytest.raises(UpstreamContractViolation, match="v4|approval"):
            await _flow_client(handler).create_model_snapshot()

    @pytest.mark.asyncio
    async def test_snapshot_v3_with_true_commandability_is_contract_violation(self):
        body = _snapshot_body(commandable=True)

        def handler(request):
            return httpx.Response(200, json=body)

        with pytest.raises(UpstreamContractViolation, match="v3|commandability"):
            await _flow_client(handler).create_model_snapshot()

    @pytest.mark.asyncio
    async def test_snapshot_without_prediction_engine_is_contract_violation(self):
        body = _snapshot_body()
        del body["prediction_engine"]

        def handler(request):
            return httpx.Response(200, json=body)

        client = _flow_client(handler)
        with pytest.raises(UpstreamContractViolation):
            await client.create_model_snapshot()

    @pytest.mark.asyncio
    async def test_snapshot_503_is_unavailable(self):
        def handler(request):
            return httpx.Response(503, json={"detail": "no release"})

        client = _flow_client(handler)
        with pytest.raises(UpstreamUnavailableError):
            await client.create_model_snapshot()

    @pytest.mark.asyncio
    async def test_snapshot_envelope_wrapper_is_contract_violation(self):
        def handler(request):
            return httpx.Response(200, json={"data": _snapshot_body()})

        client = _flow_client(handler)
        with pytest.raises(UpstreamContractViolation):
            await client.create_model_snapshot()

    @pytest.mark.asyncio
    async def test_flow_client_returns_verified_artifact_reference(self):
        body = _prediction_body()
        content = json.dumps(
            body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

        def handler(request):
            assert request.url.path == "/api/v1/control/predictions"
            return _prediction_response(body)

        client = _flow_client(handler)
        result = await client.create_prediction(_prediction_request())
        assert result.prediction_run_id == "c" * 64
        assert result.parsed["prediction_run_id"] == "c" * 64
        assert result.identity_version == 2
        assert result.engine_id == "munbon.flow-monitoring.network-transient"
        assert result.semantic_contract_version == 1
        assert result.build_digest == "a" * 64
        assert result.engine_descriptor_content_hash == "b" * 64
        # The reference sha/size are the client's OWN recomputation over the bytes.
        assert result.artifact.artifact_sha256 == hashlib.sha256(content).hexdigest()
        assert result.artifact.uncompressed_size_bytes == len(content)
        assert result.artifact.media_type == "application/json"
        assert result.artifact.encoding == "canonical-json+zlib"
        assert result.artifact.encoding_version == 1

    @pytest.mark.asyncio
    async def test_prediction_artifact_sha_mismatch_is_contract_violation(self):
        def handler(request):
            return _prediction_response(
                _prediction_body(),
                header_overrides={"X-Prediction-Artifact-SHA256": "0" * 64},
            )

        client = _flow_client(handler)
        with pytest.raises(UpstreamContractViolation, match="sha256"):
            await client.create_prediction(_prediction_request())

    @pytest.mark.asyncio
    async def test_prediction_artifact_size_mismatch_is_contract_violation(self):
        def handler(request):
            return _prediction_response(
                _prediction_body(),
                header_overrides={"X-Prediction-Artifact-Uncompressed-Size": "999999"},
            )

        client = _flow_client(handler)
        with pytest.raises(UpstreamContractViolation, match="byte size"):
            await client.create_prediction(_prediction_request())

    @pytest.mark.asyncio
    async def test_prediction_missing_artifact_header_is_contract_violation(self):
        def handler(request):
            return _prediction_response(
                _prediction_body(),
                header_overrides={"X-Prediction-Artifact-SHA256": None},
            )

        client = _flow_client(handler)
        with pytest.raises(UpstreamContractViolation, match="missing"):
            await client.create_prediction(_prediction_request())

    @pytest.mark.asyncio
    async def test_prediction_missing_engine_header_is_contract_violation(self):
        def handler(request):
            return _prediction_response(
                _prediction_body(),
                header_overrides={"X-Prediction-Engine-Id": None},
            )

        client = _flow_client(handler)
        with pytest.raises(UpstreamContractViolation, match="missing"):
            await client.create_prediction(_prediction_request())

    @pytest.mark.asyncio
    async def test_prediction_non_v2_identity_is_contract_violation(self):
        def handler(request):
            return _prediction_response(
                _prediction_body(),
                header_overrides={"X-Prediction-Identity-Version": "1"},
            )

        client = _flow_client(handler)
        with pytest.raises(UpstreamContractViolation, match="identity_version"):
            await client.create_prediction(_prediction_request())

    @pytest.mark.asyncio
    async def test_prediction_409_is_lineage_conflict(self):
        def handler(request):
            return httpx.Response(409, json={"detail": "pins drifted"})

        client = _flow_client(handler)
        with pytest.raises(FlowLineageConflictError):
            await client.create_prediction(_prediction_request())

    @pytest.mark.asyncio
    async def test_prediction_503_is_unavailable(self):
        def handler(request):
            return httpx.Response(503, json={"detail": "store down"})

        client = _flow_client(handler)
        with pytest.raises(UpstreamUnavailableError):
            await client.create_prediction(_prediction_request())

    @pytest.mark.asyncio
    async def test_prediction_400_is_rejected_request(self):
        def handler(request):
            return httpx.Response(400, json={"detail": "bad envelope"})

        client = _flow_client(handler)
        with pytest.raises(PredictionRequestRejectedError):
            await client.create_prediction(_prediction_request())

    @pytest.mark.asyncio
    async def test_prediction_pin_echo_mismatch_is_contract_violation(self):
        def handler(request):
            return httpx.Response(
                200, json=_prediction_body(model_release_id="other-release")
            )

        client = _flow_client(handler)
        with pytest.raises(UpstreamContractViolation):
            await client.create_prediction(_prediction_request())

    @pytest.mark.asyncio
    async def test_prediction_without_run_id_is_contract_violation(self):
        body = _prediction_body()
        del body["prediction_run_id"]

        def handler(request):
            return httpx.Response(200, json=body)

        client = _flow_client(handler)
        with pytest.raises(UpstreamContractViolation):
            await client.create_prediction(_prediction_request())

    @pytest.mark.asyncio
    async def test_prediction_with_duplicate_member_is_contract_violation(self):
        body = _prediction_body(
            members=[
                {"member": "nominal", "status": "completed"},
                {"member": "nominal", "status": "completed"},
                {"member": "nominal", "status": "completed"},
            ]
        )

        def handler(request):
            return httpx.Response(200, json=body)

        client = _flow_client(handler)
        with pytest.raises(UpstreamContractViolation):
            await client.create_prediction(_prediction_request())

    @pytest.mark.asyncio
    async def test_prediction_with_unknown_member_label_is_contract_violation(
        self,
    ):
        body = _prediction_body(
            members=[
                {"member": "low", "status": "completed"},
                {"member": "nominal", "status": "completed"},
                {"member": "upper", "status": "completed"},
            ]
        )

        def handler(request):
            return httpx.Response(200, json=body)

        client = _flow_client(handler)
        with pytest.raises(UpstreamContractViolation):
            await client.create_prediction(_prediction_request())


class TestFakeInterfacePins:
    def test_service_test_fakes_pin_real_client_interfaces(self):
        from tests.control_plan_test_support import (
            FakeControlFlowClient,
            FakeRepository,
            FakeRosGisClient,
        )
        from repositories.control_plan_repository import (
            PostgresControlPlanRepository,
        )

        pairs = [
            (FakeRosGisClient, RosGisRequirementsClient, ["get_exact_requirements"]),
            (
                FakeControlFlowClient,
                ControlFlowClient,
                ["create_model_snapshot", "create_prediction"],
            ),
            (
                FakeRepository,
                PostgresControlPlanRepository,
                [
                    "find_by_input_hash",
                    "store_draft_plan",
                    "load_draft_plan",
                    "allocate_campaign_version",
                ],
            ),
        ]
        for fake, real, methods in pairs:
            for method in methods:
                fake_signature = inspect.signature(getattr(fake, method))
                real_signature = inspect.signature(getattr(real, method))
                assert fake_signature.parameters.keys() == (
                    real_signature.parameters.keys()
                ), f"{fake.__name__}.{method} drifted from {real.__name__}"
