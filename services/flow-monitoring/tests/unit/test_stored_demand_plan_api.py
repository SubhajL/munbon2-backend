"""Stored immutable demand versions driving the canonical read-only flow plan."""

import asyncio
import hashlib
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.demand_store import DemandStoreUnavailable, InMemoryDemandStore
from core.network_flow_controller import NetworkFlowController

SERVICE_ROOT = Path(__file__).resolve().parents[2]
CONTROL_PY = SERVICE_ROOT / "src" / "api" / "control.py"
NETWORK = SERVICE_ROOT / "src" / "config" / "network.json"
GEOMETRY = SERVICE_ROOT / "src" / "config" / "canal_geometry.json"
CALIBRATIONS = SERVICE_ROOT / "src" / "config" / "gate_calibrations.json"
UTC = timezone.utc


def _iso(day: int, hour: int = 0) -> str:
    return datetime(2026, 7, day, hour, tzinfo=UTC).isoformat()


def _record(**overrides) -> dict:
    record = {
        "area_type": "node",
        "area_id": "M(0,1)",
        "timezone": "Asia/Bangkok",
        "method": "daily_requirement",
        "source_service": "ros-gis-integration",
        "source_version": "run-2026-07-01-v1",
        "synthetic": False,
        "computed_at": _iso(1),
        "version": 1,
        "idempotency_key": "requirement-M(0,1)-2026-07-01-v1",
        "period_start": _iso(1),
        "period_end": _iso(2),
        "volume_m3": 21_600.0,
        "scheduled_delivery_intervals": [{"start": _iso(1, 6), "end": _iso(1, 12)}],
        "quality": "estimated",
        "input_versions": {"run_id": "run-2026-07-01-v1"},
    }
    record.update(overrides)
    return record


def _load_control():
    spec = importlib.util.spec_from_file_location(
        "flowmon_stored_demand_plan_under_test", str(CONTROL_PY)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _client(store=None) -> tuple[TestClient, object]:
    control = _load_control()
    control.flow_controller = NetworkFlowController(
        str(NETWORK), str(GEOMETRY), str(CALIBRATIONS)
    )
    control.demand_store = store if store is not None else InMemoryDemandStore()
    app = FastAPI()
    app.include_router(control.router, prefix="/api/v1/control")
    return TestClient(app, raise_server_exceptions=False), control.demand_store


def _submit(client: TestClient, record: dict) -> dict:
    response = client.post("/api/v1/control/demands", json={"demands": [record]})
    assert response.status_code == 200
    result = response.json()["results"][0]
    return {
        "logical_key": result["logical_key"],
        "version": result["version"],
        "content_hash": result["content_hash"],
    }


def _plan(client: TestClient, refs: list[dict], effective_at: str | None = None):
    return client.post(
        "/api/v1/control/plan/from-demands",
        json={"effective_at": effective_at or _iso(1, 9), "demand_refs": refs},
    )


class TestStoredDemandPlanEndpoint:
    def test_stored_node_demand_produces_pinned_59_reach_plan(self):
        client, _ = _client()
        ref = _submit(client, _record())

        response = _plan(client, [ref])

        assert response.status_code == 200
        body = response.json()
        assert body["inputs"] == [
            {
                **ref,
                "node_id": "M(0,1)",
                "active": True,
                "required_flow_m3s": 1.0,
            }
        ]
        assert len(body["plan"]["reaches"]) == 59
        assert body["plan"]["head_flow_m3s"] == 1.0

    def test_two_active_records_for_same_node_are_summed(self):
        client, _ = _client()
        first = _submit(client, _record())
        second = _submit(
            client,
            _record(
                method="operator_correction",
                volume_m3=43_200.0,
                idempotency_key="requirement-M(0,1)-correction-v1",
            ),
        )

        response = _plan(client, [first, second])

        assert response.status_code == 200
        assert response.json()["plan"]["head_flow_m3s"] == 3.0

    def test_inactive_record_is_reported_and_contributes_zero(self):
        client, _ = _client()
        ref = _submit(client, _record())

        response = _plan(client, [ref], effective_at=_iso(1, 18))

        assert response.status_code == 200
        body = response.json()
        assert body["inputs"][0]["active"] is False
        assert body["inputs"][0]["required_flow_m3s"] == 0.0
        assert body["plan"]["head_flow_m3s"] == 0.0

    def test_exact_older_version_is_used_after_latest_changes(self):
        client, _ = _client()
        version_one = _submit(client, _record())
        _submit(
            client,
            _record(
                version=2,
                volume_m3=43_200.0,
                idempotency_key="requirement-M(0,1)-2026-07-01-v2",
            ),
        )

        response = _plan(client, [version_one])

        assert response.status_code == 200
        assert response.json()["plan"]["head_flow_m3s"] == 1.0

    def test_duplicate_reference_is_rejected_before_store_read(self):
        class CountingStore:
            def __init__(self):
                self.reads = 0

            async def get_version(self, kind, logical_key, version):
                self.reads += 1

        store = CountingStore()
        client, _ = _client(store)
        ref = {"logical_key": "demand-key", "version": 1, "content_hash": "a" * 64}

        response = _plan(client, [ref, ref])

        assert response.status_code == 400
        assert store.reads == 0

    def test_missing_exact_version_returns_404(self):
        client, _ = _client()
        missing = {
            "logical_key": "missing-demand",
            "version": 3,
            "content_hash": "a" * 64,
        }

        response = _plan(client, [missing])

        assert response.status_code == 404

    def test_content_hash_mismatch_returns_409(self):
        client, _ = _client()
        ref = _submit(client, _record())
        ref["content_hash"] = "f" * 64

        response = _plan(client, [ref])

        assert response.status_code == 409

    @pytest.mark.parametrize(
        ("field", "mismatched_value"),
        [("logical_key", "another-demand"), ("version", 2)],
    )
    def test_store_result_with_mismatched_identity_fails_closed(
        self, field, mismatched_value
    ):
        client, store = _client()
        ref = _submit(client, _record())
        stored = asyncio.run(
            store.get_version("demand", ref["logical_key"], ref["version"])
        )
        stored[field] = mismatched_value

        class MismatchedStore:
            async def get_version(self, kind, logical_key, version):
                return stored

        client, _ = _client(MismatchedStore())

        response = _plan(client, [ref])

        assert response.status_code == 503
        assert "identity does not match" in response.json()["detail"]

    def test_non_node_record_returns_400(self):
        client, _ = _client()
        ref = _submit(client, _record(area_type="section", area_id="section-1"))

        response = _plan(client, [ref])

        assert response.status_code == 400

    def test_synthetic_stored_lineage_fails_closed(self):
        store = InMemoryDemandStore()
        payload = _record(synthetic=True)
        put = asyncio.run(
            store.put("demand", "synthetic-demand", 1, "synthetic", payload)
        )
        client, _ = _client(store)
        ref = {
            "logical_key": "synthetic-demand",
            "version": 1,
            "content_hash": put.content_hash,
        }

        response = _plan(client, [ref])

        assert response.status_code == 503
        assert "invalid" in response.json()["detail"].lower()

    def test_corrupt_stored_record_returns_503(self):
        store = InMemoryDemandStore()
        payload = _record()
        del payload["volume_m3"]
        put = asyncio.run(store.put("demand", "corrupt-demand", 1, "corrupt", payload))
        client, _ = _client(store)
        ref = {
            "logical_key": "corrupt-demand",
            "version": 1,
            "content_hash": put.content_hash,
        }

        response = _plan(client, [ref])

        assert response.status_code == 503
        assert response.json()["detail"] == (
            "stored demand 'corrupt-demand' version 1 is invalid"
        )

    def test_demand_store_failure_returns_503(self):
        class DownStore:
            async def get_version(self, kind, logical_key, version):
                raise DemandStoreUnavailable("db down")

        client, _ = _client(DownStore())
        ref = {"logical_key": "demand-key", "version": 1, "content_hash": "a" * 64}

        response = _plan(client, [ref])

        assert response.status_code == 503

    def test_response_pins_exact_config_hashes(self):
        client, _ = _client()
        ref = _submit(client, _record())

        response = _plan(client, [ref])

        assert response.status_code == 200
        assert response.json()["config_sha256"] == {
            "network": hashlib.sha256(NETWORK.read_bytes()).hexdigest(),
            "canal_geometry": hashlib.sha256(GEOMETRY.read_bytes()).hexdigest(),
            "gate_calibrations": hashlib.sha256(CALIBRATIONS.read_bytes()).hexdigest(),
        }


class TestStoredDemandPlanOpenApi:
    def test_contract_requires_effective_time_and_pinned_refs(self):
        client, _ = _client()

        schema = client.get("/openapi.json").json()

        request = schema["components"]["schemas"]["StoredDemandPlanRequest"]
        ref = schema["components"]["schemas"]["DemandVersionRef"]
        assert sorted(request["required"]) == ["demand_refs", "effective_at"]
        assert sorted(ref["required"]) == ["content_hash", "logical_key", "version"]
        assert "/api/v1/control/plan/from-demands" in schema["paths"]

    @pytest.mark.parametrize(
        "invalid_ref",
        [
            {"logical_key": "demand-key", "version": True, "content_hash": "a" * 64},
            {"logical_key": " ", "version": 1, "content_hash": "a" * 64},
        ],
    )
    def test_invalid_reference_identity_is_rejected_by_schema(self, invalid_ref):
        client, _ = _client()

        response = _plan(client, [invalid_ref])

        assert response.status_code == 422
