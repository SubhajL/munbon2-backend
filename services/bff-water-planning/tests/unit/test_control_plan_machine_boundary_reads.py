"""PR 6.5b — BFF strict pass-through of the scheduler machine-boundary reads.

The three new bearer-forwarded GETs (intent-timeline, readback-observations, execution-state)
preserve exact scheduler state, require a bearer, and fail closed (502) on contract drift and the
scheduler taxonomy (404→404, 503→503). Mirror of the existing PR 4.4 read-route tests.
"""

from __future__ import annotations

from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import control_plans
from clients.scheduler_client import (
    SchedulerAuthError,
    SchedulerBadRequestError,
    SchedulerClient,
    SchedulerControlPlanNotFoundError,
    SchedulerUnavailableError,
)

PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
INTENT_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
PLAN_VERSION = 3
AUTH = {"Authorization": "Bearer operator-jwt-token"}


def _timeline_payload() -> dict:
    return {
        "plan_id": PLAN_ID,
        "plan_version": PLAN_VERSION,
        "intents": [
            {
                "intent_id": INTENT_ID,
                "canonical_gate_id": "M(0,0;1,0)",
                "event_kind": "open",
                "event_sequence": 1,
                "not_before": "2026-07-20T06:00:00+00:00",
                "deadline": "2026-07-21T00:00:00+00:00",
                "execution_state": "claimed",
                "claimed_at": "2026-07-20T06:05:00+00:00",
                "receipt_status": "validation_rejected",
                "reason_code": "freshness_failed",
                "validated_at": "2026-07-20T06:05:01+00:00",
                "dispatched_at": "2026-07-20T06:05:00+00:00",
                "receipt_content_sha256": "a" * 64,
            }
        ],
    }


def _observations_payload() -> dict:
    return {
        "plan_id": PLAN_ID,
        "plan_version": PLAN_VERSION,
        "observations": [
            {
                "canonical_gate_id": "M(0,0;1,0)",
                "observed_level": None,
                "expected_level": 3,
                "quality": "unavailable",
                "verdict": "unavailable",
                "reconciliation_mode": "observe",
                "observed_at": "2026-07-20T06:10:00+00:00",
            }
        ],
    }


def _execution_state_payload() -> dict:
    return {
        "plan_id": PLAN_ID,
        "plan_version": PLAN_VERSION,
        "is_held": True,
        "hold_events": [
            {
                "event_type": "held",
                "worker_id": "readback-reconciler",
                "occurred_at": "2026-07-20T06:12:00+00:00",
            }
        ],
    }


class _StubSchedulerClient:
    def __init__(self, *, timeline=None, observations=None, execution_state=None, error=None):
        self._timeline = timeline
        self._observations = observations
        self._execution_state = execution_state
        self._error = error
        self.calls: list[tuple] = []

    async def get_intent_timeline(self, plan_id, plan_version, bearer_token):
        self.calls.append(("intent-timeline", str(plan_id), plan_version, bearer_token))
        if self._error is not None:
            raise self._error
        return self._timeline

    async def get_readback_observations(self, plan_id, plan_version, bearer_token):
        self.calls.append(("readback-observations", str(plan_id), plan_version, bearer_token))
        if self._error is not None:
            raise self._error
        return self._observations

    async def get_execution_state(self, plan_id, plan_version, bearer_token):
        self.calls.append(("execution-state", str(plan_id), plan_version, bearer_token))
        if self._error is not None:
            raise self._error
        return self._execution_state


def _app(stub: _StubSchedulerClient) -> TestClient:
    app = FastAPI()
    app.include_router(control_plans.router)
    app.dependency_overrides[control_plans.get_scheduler_client] = lambda: stub
    return TestClient(app)


def _base(suffix: str) -> str:
    return f"/api/v1/control-plans/{PLAN_ID}/versions/{PLAN_VERSION}{suffix}"


def test_intent_timeline_passthrough_preserves_exact_state():
    stub = _StubSchedulerClient(timeline=_timeline_payload())
    response = _app(stub).get(_base("/intent-timeline"), headers=AUTH)
    assert response.status_code == 200, response.text
    body = response.json()
    entry = body["intents"][0]
    assert entry["execution_state"] == "claimed"
    assert entry["receipt_status"] == "validation_rejected"
    assert entry["reason_code"] == "freshness_failed"
    # the operator bearer was forwarded to the scheduler
    assert stub.calls[0][3] == "operator-jwt-token"


def test_readback_observations_preserves_unavailable_and_null_level():
    stub = _StubSchedulerClient(observations=_observations_payload())
    response = _app(stub).get(_base("/readback-observations"), headers=AUTH)
    assert response.status_code == 200, response.text
    obs = response.json()["observations"][0]
    assert obs["verdict"] == "unavailable"
    assert obs["observed_level"] is None  # never masked to 0


def test_execution_state_passthrough_preserves_hold():
    stub = _StubSchedulerClient(execution_state=_execution_state_payload())
    response = _app(stub).get(_base("/execution-state"), headers=AUTH)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_held"] is True
    assert body["hold_events"][0]["event_type"] == "held"


@pytest.mark.parametrize(
    "suffix", ["/intent-timeline", "/readback-observations", "/execution-state"]
)
def test_missing_bearer_is_rejected(suffix):
    stub = _StubSchedulerClient(
        timeline=_timeline_payload(),
        observations=_observations_payload(),
        execution_state=_execution_state_payload(),
    )
    response = _app(stub).get(_base(suffix))  # no Authorization header
    assert response.status_code == 403


@pytest.mark.parametrize(
    "suffix", ["/intent-timeline", "/readback-observations", "/execution-state"]
)
def test_contract_drift_fails_closed_502(suffix):
    # An added field violates extra="forbid" → 502 (never a partial/laundered projection).
    drift = {
        "/intent-timeline": {**_timeline_payload(), "unexpected": 1},
        "/readback-observations": {**_observations_payload(), "unexpected": 1},
        "/execution-state": {**_execution_state_payload(), "unexpected": 1},
    }[suffix]
    stub = _StubSchedulerClient(
        timeline=drift, observations=drift, execution_state=drift
    )
    response = _app(stub).get(_base(suffix), headers=AUTH)
    assert response.status_code == 502


@pytest.mark.parametrize(
    "suffix", ["/intent-timeline", "/readback-observations", "/execution-state"]
)
@pytest.mark.parametrize(
    "error,expected",
    [
        (SchedulerControlPlanNotFoundError("gone"), 404),
        (SchedulerUnavailableError("scheduler is unavailable"), 503),
    ],
)
def test_error_taxonomy_is_preserved(suffix, error, expected):
    stub = _StubSchedulerClient(error=error)
    response = _app(stub).get(_base(suffix), headers=AUTH)
    assert response.status_code == expected


# --- client layer (real SchedulerClient over MockTransport) ------------------
def _capturing_client(json_body: dict):
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=json_body)

    client = SchedulerClient(
        base_url="http://scheduler.test", transport=httpx.MockTransport(handler)
    )
    return client, captured


@pytest.mark.parametrize(
    "suffix,mutate",
    [
        # a retyped scalar must fail closed, never coerce (StrictInt/StrictBool/StrictDatetime)
        ("/execution-state", lambda p: {**p, "is_held": 1}),  # int, not bool
        ("/intent-timeline", lambda p: {**p, "intents": [{**p["intents"][0], "event_sequence": "1"}]}),  # str int
        # a numeric epoch where an ISO datetime is expected (the laundering hole) → 502
        ("/readback-observations", lambda p: {**p, "observations": [{**p["observations"][0], "observed_at": 1770000000}]}),
        # a nested item with an extra field (extra="forbid" reaches the item level)
        ("/intent-timeline", lambda p: {**p, "intents": [{**p["intents"][0], "surprise": 1}]}),
        # a dropped required field
        ("/execution-state", lambda p: {k: v for k, v in p.items() if k != "is_held"}),
    ],
)
def test_retyped_or_malformed_field_fails_closed_502(suffix, mutate):
    base = {
        "/intent-timeline": _timeline_payload(),
        "/readback-observations": _observations_payload(),
        "/execution-state": _execution_state_payload(),
    }[suffix]
    broken = mutate(base)
    stub = _StubSchedulerClient(timeline=broken, observations=broken, execution_state=broken)
    response = _app(stub).get(_base(suffix), headers=AUTH)
    assert response.status_code == 502, response.text


@pytest.mark.parametrize(
    "suffix", ["/intent-timeline", "/readback-observations", "/execution-state"]
)
def test_mismatched_plan_identity_echo_fails_closed_502(suffix):
    # The scheduler echoing a DIFFERENT plan_id must be treated as contract drift, not trusted.
    wrong = {
        "/intent-timeline": {**_timeline_payload(), "plan_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"},
        "/readback-observations": {**_observations_payload(), "plan_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"},
        "/execution-state": {**_execution_state_payload(), "plan_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"},
    }[suffix]
    stub = _StubSchedulerClient(timeline=wrong, observations=wrong, execution_state=wrong)
    response = _app(stub).get(_base(suffix), headers=AUTH)
    assert response.status_code == 502


@pytest.mark.parametrize(
    "suffix", ["/intent-timeline", "/readback-observations", "/execution-state"]
)
@pytest.mark.parametrize(
    "error,expected",
    [
        (SchedulerAuthError(401, "token rejected"), 401),
        (SchedulerAuthError(403, "forbidden"), 403),
        (SchedulerBadRequestError(422, "bad filter"), 422),
    ],
)
def test_auth_and_bad_request_are_forwarded_verbatim(suffix, error, expected):
    # The scheduler stays the JWT authority: a 401/403/4xx is forwarded, never collapsed to 502/503.
    stub = _StubSchedulerClient(error=error)
    response = _app(stub).get(_base(suffix), headers=AUTH)
    assert response.status_code == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,suffix,payload",
    [
        ("get_intent_timeline", "/intent-timeline", _timeline_payload()),
        ("get_readback_observations", "/readback-observations", _observations_payload()),
        ("get_execution_state", "/execution-state", _execution_state_payload()),
    ],
)
async def test_client_builds_the_bounded_path_and_forwards_the_bearer(method, suffix, payload):
    client, captured = _capturing_client(payload)
    result = await getattr(client, method)(UUID(PLAN_ID), PLAN_VERSION, "operator-jwt-token")
    assert result == payload
    request = captured[0]
    assert request.url.path == (
        f"/api/v1/control-plans/{PLAN_ID}/versions/{PLAN_VERSION}{suffix}"
    )
    assert request.headers["Authorization"] == "Bearer operator-jwt-token"
