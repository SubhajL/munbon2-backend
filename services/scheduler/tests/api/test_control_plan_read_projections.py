"""Bounded read-projection ROUTES: RBAC, 404, and fail-closed 503 (PR 4.4b-3).

The equivalence + boundedness of the projections themselves is proven in
tests/unit/test_control_plan_read_projections.py; here the three dedicated routes
are proven to be require_operator, to 404 an absent plan, and to fail closed with a
503 (never a partial body) when a bounded read hits corruption.
"""

import asyncio
import inspect
import json
from dataclasses import replace
from functools import partial
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from algorithms.hydraulic_schedule_optimizer import (
    optimize_limited_adjustment_plan,
)
from api.middleware.request_id import RequestIDMiddleware
from api.v1.endpoints import control_plans
from core.deps import get_current_user, get_db
from repositories.control_plan_projection_repository import (
    PostgresControlPlanProjectionRepository,
    ProjectionCorruptError,
)
from schemas.control_plan import DraftControlPlanRequest
from services.control_plan_service import ControlPlanDraftService
from tests.control_plan_test_support import (
    FakeControlFlowClient,
    FakeReadProjectionRepository,
    FakeRepository,
    FakeRosGisClient,
    draft_payload,
    requirement_item,
    snapshot_mirror,
)

_OPERATOR = {"sub": "operator-1", "roles": ["operator"], "iss": "munbon-auth"}
_FIELD_TEAM = {"sub": "ft-1", "roles": ["field_team"]}

_SUFFIXES = ("/prediction-coverage", "/lifecycle-history", "/ledger")


async def _run_blocking(func, *args, **kwargs):
    return func(*args, **kwargs)


async def _seed_repository():
    repository = FakeRepository()
    service = ControlPlanDraftService(
        ros_client=FakeRosGisClient([requirement_item()]),
        flow_client=FakeControlFlowClient(snapshot_mirror()),
        repository=repository,
        optimizer=partial(
            optimize_limited_adjustment_plan,
            model_step_seconds=3600,
            max_intermediate_trims=1,
            solver_timeout_seconds=60,
        ),
        run_blocking=_run_blocking,
        model_step_seconds=3600,
        max_intermediate_trims=1,
        solver_timeout_seconds=60,
    )
    record, _ = await service.create_draft(
        None, DraftControlPlanRequest.model_validate(draft_payload()), "operator-1"
    )
    return repository, record


def _build_app(projection_repo, user=_OPERATOR):
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.include_router(control_plans.router, prefix="/api/v1/control-plans")

    async def override_db():
        yield None

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[
        control_plans.get_control_plan_projection_repository
    ] = lambda: projection_repo
    app.dependency_overrides[get_current_user] = lambda: user
    return app


class _RaisingProjectionRepo:
    """Every bounded read hits corruption — proves the routes fail closed (503)."""

    async def load_prediction_coverage(self, session, plan_id, plan_version):
        raise ProjectionCorruptError("stored coverage document is corrupt")

    async def load_lifecycle_history(self, session, plan_id, plan_version):
        raise ProjectionCorruptError("stored history document is corrupt")

    async def load_ledger_projection(self, session, plan_id, plan_version):
        raise ProjectionCorruptError("stored ledger row is corrupt")


def _base(plan_id, plan_version=1):
    return f"/api/v1/control-plans/{plan_id}/versions/{plan_version}"


@pytest.mark.parametrize("suffix", _SUFFIXES)
def test_read_projection_routes_require_operator(suffix):
    repository, record = asyncio.run(_seed_repository())
    projection_repo = FakeReadProjectionRepository(repository)

    # An operator can read ...
    app = _build_app(projection_repo, user=_OPERATOR)
    ok = TestClient(app).get(f"{_base(record.plan_id)}{suffix}")
    assert ok.status_code == 200, ok.text

    # ... a present-but-insufficient field_team token is 403 ...
    app = _build_app(projection_repo, user=_FIELD_TEAM)
    assert TestClient(app).get(f"{_base(record.plan_id)}{suffix}").status_code == 403

    # ... and no bearer at all is 403 (HTTPBearer).
    app = _build_app(projection_repo, user=_OPERATOR)
    del app.dependency_overrides[get_current_user]
    assert TestClient(app).get(f"{_base(record.plan_id)}{suffix}").status_code == 403


@pytest.mark.parametrize("suffix", _SUFFIXES)
def test_read_projection_unknown_plan_is_404(suffix):
    repository, _ = asyncio.run(_seed_repository())
    app = _build_app(FakeReadProjectionRepository(repository))
    response = TestClient(app).get(f"{_base(uuid4())}{suffix}")
    assert response.status_code == 404


@pytest.mark.parametrize("suffix", _SUFFIXES)
def test_read_projection_corruption_returns_503_not_partial(suffix):
    app = _build_app(_RaisingProjectionRepo())
    response = TestClient(app).get(f"{_base(uuid4())}{suffix}")
    assert response.status_code == 503
    # A corrupt read yields ONLY an error detail — never a partial projection body.
    assert set(response.json()) == {"detail"}


def test_coverage_route_returns_completed_member_statuses():
    repository, record = asyncio.run(_seed_repository())
    app = _build_app(FakeReadProjectionRepository(repository))
    body = TestClient(app).get(
        f"{_base(record.plan_id)}/prediction-coverage"
    ).json()
    assert body["prediction_status"] == "completed"
    assert [m["status"] for m in body["prediction_member_statuses"]] == [
        "completed",
        "completed",
        "completed",
    ]
    # A bounded coverage read is a strict subset — no heavy detail leaks.
    for forbidden in ("optimizer_result", "requirements", "events",
                      "transitions", "entries", "handover"):
        assert forbidden not in body


def _reseed_record(repository, record, **changes):
    """Replace the stored record in-place so the route reads the tampered shape."""
    tampered = replace(record, **changes)
    repository.by_key[(record.plan_id, record.plan_version)] = tampered
    repository.by_input_hash[record.input_content_hash] = tampered
    return tampered


def test_coverage_unknown_member_status_route_returns_503():
    # FIX 4: a stored member-summary with an unknown status is well-formed JSON but
    # schema-invalid — the route must fail closed with a 503, never an opaque 500.
    repository, record = asyncio.run(_seed_repository())
    summaries = json.loads(record.prediction_member_summaries)
    summaries[0]["status"] = "bogus_status"
    _reseed_record(
        repository,
        record,
        prediction_member_summaries=json.dumps(summaries, separators=(",", ":")),
    )
    app = _build_app(FakeReadProjectionRepository(repository))
    response = TestClient(app).get(f"{_base(record.plan_id)}/prediction-coverage")
    assert response.status_code == 503
    assert set(response.json()) == {"detail"}


def test_lifecycle_history_array_document_route_returns_503():
    # FIX 4: a transition_document that is a JSON array (valid JSON, wrong shape) is
    # corruption → 503 at the route, not a 500.
    repository, record = asyncio.run(_seed_repository())
    _reseed_record(
        repository,
        record,
        transitions=(
            replace(record.transitions[0], transition_document_text="[1, 2, 3]"),
        ),
    )
    app = _build_app(FakeReadProjectionRepository(repository))
    response = TestClient(app).get(f"{_base(record.plan_id)}/lifecycle-history")
    assert response.status_code == 503
    assert set(response.json()) == {"detail"}


def test_read_projection_fake_pins_the_real_repository_interface():
    real = PostgresControlPlanProjectionRepository
    fake = FakeReadProjectionRepository
    for name in (
        "load_prediction_coverage",
        "load_lifecycle_history",
        "load_ledger_projection",
    ):
        real_sig = inspect.signature(getattr(real, name))
        fake_sig = inspect.signature(getattr(fake, name))
        assert list(real_sig.parameters) == list(fake_sig.parameters), name
        assert list(real_sig.parameters) == [
            "self",
            "session",
            "plan_id",
            "plan_version",
        ]
