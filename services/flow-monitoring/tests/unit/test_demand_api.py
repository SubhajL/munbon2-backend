"""
Unit tests for the Wave 2.4 demand/allocation/delivery contract API
(POST + GET /api/v1/control/demands). Mirrors test_control_api isolation:
api/control.py is loaded standalone with an InMemoryDemandStore injected, so the
suite runs DB-free while exercising the exact runtime handler.

Schema tests live in the API-changing PR itself (plan MED #16).
"""
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.demand_store import InMemoryDemandStore

SERVICE_ROOT = Path(__file__).resolve().parents[2]
CONTROL_PY = SERVICE_ROOT / "src" / "api" / "control.py"

UTC = timezone.utc


def _load_control():
    spec = importlib.util.spec_from_file_location(
        "flowmon_demand_api_under_test", str(CONTROL_PY)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _client(store=None):
    control = _load_control()
    control.demand_store = store
    app = FastAPI()
    app.include_router(control.router, prefix="/api/v1/control")
    return TestClient(app), control


def _iso(day: int, hour: int = 0) -> str:
    return datetime(2026, 7, day, hour, tzinfo=UTC).isoformat()


def demand_record(**overrides) -> dict:
    """A valid weekly demand: 311,040 m3 over a 72 h scheduled window -> 1.2 m3/s."""
    record = {
        "area_type": "zone",
        "area_id": "Z1",
        "period_start": _iso(1),
        "period_end": _iso(8),
        "timezone": "Asia/Bangkok",
        "volume_m3": 311040.0,
        "scheduled_delivery_intervals": [{"start": _iso(1), "end": _iso(4)}],
        "method": "ros",
        "source_service": "bff-water-planning",
        "source_version": "1.4.0",
        "synthetic": False,
        "quality": "estimated",
        "computed_at": _iso(1),
        "version": 1,
        "idempotency_key": "demand-Z1-w27-v1",
    }
    record.update(overrides)
    return record


def allocation_record(**overrides) -> dict:
    record = {
        "area_type": "zone",
        "area_id": "Z1",
        "period_start": _iso(1),
        "period_end": _iso(8),
        "timezone": "Asia/Bangkok",
        "intervals": [{"start": _iso(1), "end": _iso(4), "flow_m3s": 1.2}],
        "method": "annual_plan",
        "source_service": "rid-operator",
        "source_version": "annual-plan-2569-draft",
        "synthetic": False,
        "computed_at": _iso(1),
        "version": 1,
        "idempotency_key": "alloc-Z1-w27-v1",
    }
    record.update(overrides)
    return record


def delivery_observation(**overrides) -> dict:
    record = {
        "area_type": "zone",
        "area_id": "Z1",
        "start": _iso(1),
        "end": _iso(4),
        "timezone": "Asia/Bangkok",
        "volume_m3": 298000.0,
        "quality": "measured",
        "sensor_ids": ["wl-014"],
        "method": "sensor_volume",
        "source_service": "sensor-data",
        "source_version": "2.1.0",
        "synthetic": False,
        "computed_at": _iso(4, 6),
        "version": 1,
        "idempotency_key": "deliv-Z1-w27-v1",
    }
    record.update(overrides)
    return record


@pytest.fixture
def client():
    return _client(InMemoryDemandStore())[0]


class TestPostDemands:
    def test_valid_demand_is_accepted_with_ratified_flow_conversion(self, client):
        resp = client.post(
            "/api/v1/control/demands", json={"demands": [demand_record()]}
        )
        assert resp.status_code == 200
        (result,) = resp.json()["results"]
        assert result["kind"] == "demand"
        assert result["version"] == 1 and result["replayed"] is False
        # m3/s = m3 / SCHEDULED seconds (72 h), not the 7-day period
        assert result["required_flow_m3s"] == pytest.approx(1.2)

    def test_identical_resubmission_replays_idempotently(self, client):
        body = {"demands": [demand_record()]}
        assert client.post("/api/v1/control/demands", json=body).status_code == 200
        resp = client.post("/api/v1/control/demands", json=body)
        assert resp.status_code == 200
        assert resp.json()["results"][0]["replayed"] is True

    def test_next_version_supersedes_in_current_view(self, client):
        client.post("/api/v1/control/demands", json={"demands": [demand_record()]})
        v2 = demand_record(
            volume_m3=320000.0, version=2, idempotency_key="demand-Z1-w27-v2"
        )
        assert (
            client.post("/api/v1/control/demands", json={"demands": [v2]}).status_code
            == 200
        )
        current = client.get(
            "/api/v1/control/demands", params={"kind": "demand"}
        ).json()
        assert len(current["records"]) == 1
        assert current["records"][0]["version"] == 2
        assert current["records"][0]["record"]["volume_m3"] == 320000.0

    def test_version_gap_is_conflict(self, client):
        client.post("/api/v1/control/demands", json={"demands": [demand_record()]})
        v3 = demand_record(version=3, idempotency_key="demand-Z1-w27-v3")
        resp = client.post("/api/v1/control/demands", json={"demands": [v3]})
        assert resp.status_code == 409
        assert "expected version 2" in resp.json()["detail"]

    def test_rewriting_a_version_is_conflict(self, client):
        client.post("/api/v1/control/demands", json={"demands": [demand_record()]})
        rewrite = demand_record(volume_m3=1.0, idempotency_key="demand-Z1-w27-v1b")
        resp = client.post("/api/v1/control/demands", json={"demands": [rewrite]})
        assert resp.status_code == 409

    def test_synthetic_lineage_is_rejected_by_policy(self, client):
        resp = client.post(
            "/api/v1/control/demands", json={"demands": [demand_record(synthetic=True)]}
        )
        assert resp.status_code == 400
        assert "ynthetic" in resp.json()["detail"]

    def test_naive_datetime_is_a_schema_error(self, client):
        bad = demand_record(period_start="2026-07-01T00:00:00")  # no offset
        resp = client.post("/api/v1/control/demands", json={"demands": [bad]})
        assert resp.status_code == 422

    def test_unknown_timezone_is_rejected(self, client):
        bad = demand_record(timezone="Bangkok/Nowhere")
        resp = client.post("/api/v1/control/demands", json={"demands": [bad]})
        assert resp.status_code == 400
        assert "timezone" in resp.json()["detail"]

    def test_interval_outside_period_is_rejected(self, client):
        bad = demand_record(
            scheduled_delivery_intervals=[{"start": _iso(7), "end": _iso(9)}]
        )
        resp = client.post("/api/v1/control/demands", json={"demands": [bad]})
        assert resp.status_code == 400
        assert "within" in resp.json()["detail"]

    def test_overlapping_intervals_are_rejected(self, client):
        bad = demand_record(
            scheduled_delivery_intervals=[
                {"start": _iso(1), "end": _iso(3)},
                {"start": _iso(2), "end": _iso(4)},
            ]
        )
        resp = client.post("/api/v1/control/demands", json={"demands": [bad]})
        assert resp.status_code == 400
        assert "overlap" in resp.json()["detail"]

    def test_overflowing_volume_is_400_not_500(self, client):
        # 1e400 parses to +inf; the PlanRequest serialization trap (422 echoing inf
        # breaks JSON) must not recur on the demands surface.
        body = json.dumps({"demands": [demand_record()]}).replace("311040.0", "1e400")
        resp = client.post(
            "/api/v1/control/demands",
            content=body,
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400
        assert "volume" in resp.json()["detail"]

    def test_future_computed_at_is_rejected(self, client):
        future = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
        resp = client.post(
            "/api/v1/control/demands",
            json={"demands": [demand_record(computed_at=future)]},
        )
        assert resp.status_code == 400
        assert "future" in resp.json()["detail"]

    def test_node_area_ids_are_canonicalized(self, client):
        record = demand_record(area_type="node", area_id="M (0,3)")
        resp = client.post("/api/v1/control/demands", json={"demands": [record]})
        assert resp.status_code == 200
        assert "M(0,3)" in resp.json()["results"][0]["logical_key"]

    def test_invalid_node_id_is_rejected(self, client):
        record = demand_record(area_type="node", area_id="not-a-gate")
        resp = client.post("/api/v1/control/demands", json={"demands": [record]})
        assert resp.status_code == 400

    def test_empty_submission_is_rejected(self, client):
        resp = client.post("/api/v1/control/demands", json={})
        assert resp.status_code == 400
        assert "at least one" in resp.json()["detail"]

    def test_regenerated_transport_fields_replay_instead_of_conflict(self, client):
        # QCHECK tier-1 #1 / tier-2: a crash-recovered producer resubmits the
        # semantically identical record with a fresh idempotency key and a new
        # computed_at — that is a replay, never a 409 rewrite.
        assert (
            client.post(
                "/api/v1/control/demands", json={"demands": [demand_record()]}
            ).status_code
            == 200
        )
        retry = demand_record(
            idempotency_key="demand-Z1-w27-v1-retry", computed_at=_iso(1, 6)
        )
        resp = client.post("/api/v1/control/demands", json={"demands": [retry]})
        assert resp.status_code == 200
        assert resp.json()["results"][0]["replayed"] is True

    def test_pipe_bearing_fields_stay_distinct_series(self, client):
        # QCHECK tier-1 #3 / tier-2 MEDIUM: the logical key must be injective —
        # 'a|b'+'c' and 'a'+'b|c' were one series under the raw '|' join.
        first = demand_record(
            method="ros|bff-water-planning",
            source_service="x",
            idempotency_key="collide-1",
        )
        second = demand_record(
            method="ros",
            source_service="bff-water-planning|x",
            idempotency_key="collide-2",
        )
        r1 = client.post("/api/v1/control/demands", json={"demands": [first]})
        r2 = client.post("/api/v1/control/demands", json={"demands": [second]})
        assert r1.status_code == 200 and r2.status_code == 200
        keys = {
            r1.json()["results"][0]["logical_key"],
            r2.json()["results"][0]["logical_key"],
        }
        assert len(keys) == 2
        current = client.get("/api/v1/control/demands").json()
        assert len(current["records"]) == 2

    def test_version_gap_does_not_poison_subsequent_reads(self, client):
        # QCHECK tier-1 #4: a 409 must leave no empty history that turns every
        # later GET into a 500.
        gap = demand_record(version=2, idempotency_key="gap-first")
        assert (
            client.post("/api/v1/control/demands", json={"demands": [gap]}).status_code
            == 409
        )
        resp = client.get("/api/v1/control/demands")
        assert resp.status_code == 200
        assert resp.json()["records"] == []


class TestPostAllocationsAndDeliveries:
    def test_allocation_record_is_accepted(self, client):
        resp = client.post(
            "/api/v1/control/demands", json={"allocations": [allocation_record()]}
        )
        assert resp.status_code == 200
        (result,) = resp.json()["results"]
        assert result["kind"] == "allocation" and result["version"] == 1

    def test_negative_allocation_flow_is_rejected(self, client):
        bad = allocation_record(
            intervals=[{"start": _iso(1), "end": _iso(4), "flow_m3s": -0.5}]
        )
        resp = client.post("/api/v1/control/demands", json={"allocations": [bad]})
        assert resp.status_code == 400
        assert "flow" in resp.json()["detail"]

    def test_delivery_observation_is_accepted(self, client):
        resp = client.post(
            "/api/v1/control/demands", json={"deliveries": [delivery_observation()]}
        )
        assert resp.status_code == 200
        (result,) = resp.json()["results"]
        assert result["kind"] == "delivery" and result["replayed"] is False

    def test_negative_delivered_volume_is_rejected(self, client):
        bad = delivery_observation(volume_m3=-5.0)
        resp = client.post("/api/v1/control/demands", json={"deliveries": [bad]})
        assert resp.status_code == 400

    def test_future_delivery_window_is_rejected(self, client):
        # QCHECK tier-1 #5: an "actual" delivery for a window that has not
        # elapsed yet must never enter the actuals store.
        start = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        end = (datetime.now(UTC) + timedelta(days=2)).isoformat()
        bad = delivery_observation(start=start, end=end)
        resp = client.post("/api/v1/control/demands", json={"deliveries": [bad]})
        assert resp.status_code == 400
        assert "past" in resp.json()["detail"]

    def test_demand_and_allocation_stores_stay_separate(self, client):
        client.post(
            "/api/v1/control/demands",
            json={"demands": [demand_record()], "allocations": [allocation_record()]},
        )
        demand_view = client.get(
            "/api/v1/control/demands", params={"kind": "demand"}
        ).json()
        alloc_view = client.get(
            "/api/v1/control/demands", params={"kind": "allocation"}
        ).json()
        assert len(demand_view["records"]) == 1
        assert len(alloc_view["records"]) == 1
        assert demand_view["records"][0]["record"]["volume_m3"] == 311040.0
        assert alloc_view["records"][0]["record"]["intervals"][0]["flow_m3s"] == 1.2


class TestGetDemands:
    def test_defaults_to_demand_kind_and_empty_store(self, client):
        resp = client.get("/api/v1/control/demands")
        assert resp.status_code == 200
        assert resp.json() == {"kind": "demand", "records": []}

    def test_unknown_kind_is_rejected(self, client):
        resp = client.get("/api/v1/control/demands", params={"kind": "weekly"})
        assert resp.status_code == 422


class TestStoreLifecycleFailureModes:
    def test_uninitialized_store_is_503(self):
        client, _ = _client(store=None)
        resp = client.post(
            "/api/v1/control/demands", json={"demands": [demand_record()]}
        )
        assert resp.status_code == 503

    def test_unavailable_store_is_503_never_silent(self):
        from core.demand_store import DemandStoreUnavailable

        class _DownStore:
            async def put(self, kind, logical_key, version, idempotency_key, record):
                raise DemandStoreUnavailable("db down")

            async def current(self, kind):
                raise DemandStoreUnavailable("db down")

        client, _ = _client(store=_DownStore())
        post = client.post(
            "/api/v1/control/demands", json={"demands": [demand_record()]}
        )
        assert post.status_code == 503
        get = client.get("/api/v1/control/demands")
        assert get.status_code == 503


class TestOpenApiContractLock:
    """MED #16: the schema is locked in the PR that changes the API."""

    def test_demand_record_required_fields_are_locked(self, client):
        schema = client.get("/openapi.json").json()
        demand = schema["components"]["schemas"]["DemandRecord"]
        assert sorted(demand["required"]) == [
            "area_id",
            "area_type",
            "computed_at",
            "idempotency_key",
            "method",
            "period_end",
            "period_start",
            "quality",
            "scheduled_delivery_intervals",
            "source_service",
            "source_version",
            "synthetic",
            "timezone",
            "version",
            "volume_m3",
        ]

    def test_demands_surface_exposes_post_and_get(self, client):
        schema = client.get("/openapi.json").json()
        assert set(schema["paths"]["/api/v1/control/demands"]) == {"post", "get"}
