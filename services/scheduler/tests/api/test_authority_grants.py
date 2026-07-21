"""Authority-grant ROUTES (PR 7.1a): RBAC matrix, the strict-policy dark gate,
the revoke safety-valence asymmetry, and the fail-closed error taxonomy.

Grant/renew/review are IMPOSSIBLE in compat deployments (503 before any body
validation reaches the service); revoke deliberately works in compat. Service
semantics are proven in tests/unit/test_authority_grant_service.py; these
tests prove the HTTP surface."""

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.request_id import RequestIDMiddleware
from api.v1.endpoints import authority_grants
from core.config import settings
from core.deps import get_current_user, get_db
from repositories.control_plan_repository import AuthorityEvidenceCounts
from services.authority_grant_service import AuthorityGrantService
from tests.control_plan_test_support import (
    FakeRepository,
    _transition_chain,
    authority_model_snapshot,
    authority_outbox_rows,
)

NOW = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
PLAN_ID = uuid4()
RELEASE_ID = "hydraulic-model-2026.06"
CAPABILITY_RELEASE_ID = "field-registry-2026.06"
GATE = "MC-01"
SECTION = "S-1"
PATH = ["R-1", "R-2"]

_SUPERVISOR = {"sub": "supervisor-1", "roles": ["supervisor"], "iss": "munbon-auth"}
_OPERATOR = {"sub": "operator-1", "roles": ["operator"], "iss": "munbon-auth"}


INTENT_HASH_1 = "1" * 64
INTENT_HASH_2 = "2" * 64


def _record():
    snapshot = authority_model_snapshot(
        model_release_id=RELEASE_ID,
        model_release_content_hash=SHA_A,
        engine_descriptor_content_hash=SHA_B,
    )
    return SimpleNamespace(
        plan_id=PLAN_ID,
        plan_version=3,
        provenance_version=2,
        model_snapshot_id=snapshot["snapshot_id"],
        model_snapshot_document_text=json.dumps(snapshot),
        model_release_id=RELEASE_ID,
        model_release_content_hash=SHA_A,
        engine_descriptor_content_hash=SHA_B,
        max_intermediate_trims=1,
        horizon_end=NOW + 10 * HOUR,
        requirements=(
            SimpleNamespace(
                section_id=SECTION,
                gate_id=GATE,
                path_reach_ids_document_text=json.dumps(PATH),
            ),
        ),
        events=(
            SimpleNamespace(
                gate_id=GATE,
                source_flow_m3s=5.0,
                target_position_m=0.5,
                planned_at=NOW + 1 * HOUR,
            ),
            SimpleNamespace(
                gate_id=GATE,
                source_flow_m3s=0.0,
                target_position_m=0.0,
                planned_at=NOW + 4 * HOUR,
            ),
        ),
        transitions=_transition_chain("shadow_active", None),
    )


def _seeded_repository():
    repository = FakeRepository()
    repository.by_key[(PLAN_ID, 3)] = _record()
    repository.authority_evidence_counts[(PLAN_ID, 3)] = AuthorityEvidenceCounts(
        outbox_intent_count=2,
        accepted_receipt_intent_count=2,
        matching_receipt_intent_count=2,
    )
    repository.outbox[(PLAN_ID, 3)] = list(
        authority_outbox_rows(
            plan_id=PLAN_ID,
            plan_version=3,
            model_release_id=RELEASE_ID,
            model_release_content_hash=SHA_A,
            engine_descriptor_content_hash=SHA_B,
            capability_release_id=CAPABILITY_RELEASE_ID,
            capability_hash=SHA_C,
            canonical_gate_id=GATE,
            now=NOW,
        )
    )
    return repository


def _service(repository):
    snapshot = SimpleNamespace(
        capability_release_id=CAPABILITY_RELEASE_ID,
        capability_hash=SHA_C,
        capabilities={GATE: object()},
    )
    return AuthorityGrantService(
        repository, snapshot=snapshot, lease_hours=24, clock=lambda: NOW
    )


def _build_app(repository, user=_SUPERVISOR):
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.include_router(authority_grants.router, prefix="/api/v1/authority-grants")

    async def override_db():
        yield None

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[
        authority_grants.get_authority_grant_service
    ] = lambda: _service(repository)
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return app


def _grant_body(**overrides):
    body = {
        "plan_id": str(PLAN_ID),
        "plan_version": 3,
        "model_release_id": RELEASE_ID,
        "model_release_content_hash": SHA_A,
        "engine_descriptor_content_hash": SHA_B,
        "commandability_evidence": {
            "schema_version": 1,
            "model_release_id": RELEASE_ID,
            "model_release_content_hash": SHA_A,
            "engine_descriptor_content_hash": SHA_B,
            "commandable": True,
            "approval_refs": ["RID-approval-2026-118"],
        },
        "capability_release_id": CAPABILITY_RELEASE_ID,
        "capability_hash": SHA_C,
        "scope": {
            "schema_version": 1,
            "gate_paths": [
                {
                    "section_id": SECTION,
                    "canonical_gate_id": GATE,
                    "path_reach_ids": PATH,
                }
            ],
        },
        "flow_lower_exclusive_m3s": 0.0,
        "flow_upper_inclusive_m3s": 8.0,
        "initialization": {"kind": "dry"},
        "maximum_continuous_open_seconds": 6 * 3600,
        "maximum_intermediate_trims": 1,
        "shadow_evidence_sha256": "d" * 64,
        "hold_drill_evidence_sha256": "e" * 64,
        "rollback_drill_evidence_sha256": "f" * 64,
        "evidence_manifest": {"schema_version": 1, "refs": ["drill-log-1"]},
        "expires_at": (NOW + 12 * HOUR).isoformat(),
        "reason": "pilot authority",
    }
    body.update(overrides)
    return body


def _renewal_body():
    return {
        "new_expires_at": (NOW + 20 * HOUR).isoformat(),
        "shadow_evidence_sha256": "d" * 64,
        "hold_drill_evidence_sha256": "e" * 64,
        "rollback_drill_evidence_sha256": "f" * 64,
        "evidence_manifest": {"schema_version": 1, "refs": ["drill-log-2"]},
        "reason": "lease checkpoint",
    }


@pytest.fixture
def strict_mode(monkeypatch):
    monkeypatch.setattr(settings, "jwt_claim_policy_mode", "strict")


def _issue(client):
    response = client.post("/api/v1/authority-grants", json=_grant_body())
    assert response.status_code == 200, response.text
    return response.json()


class TestDarkGates:
    def test_grant_review_renew_are_503_in_compat(self):
        # The tracked deployment posture: compat -> issuance is IMPOSSIBLE.
        client = TestClient(_build_app(_seeded_repository()))
        assert (
            client.post("/api/v1/authority-grants", json=_grant_body()).status_code
            == 503
        )
        assert (
            client.post(
                "/api/v1/authority-grants/reviews", json=_grant_body()
            ).status_code
            == 503
        )
        assert (
            client.post(
                f"/api/v1/authority-grants/{uuid4()}/renewals",
                json=_renewal_body(),
            ).status_code
            == 503
        )

    def test_operator_cannot_grant_or_revoke(self, strict_mode):
        client = TestClient(_build_app(_seeded_repository(), user=_OPERATOR))
        assert (
            client.post("/api/v1/authority-grants", json=_grant_body()).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/authority-grants/{uuid4()}/revocations",
                json={"reason": "nope"},
            ).status_code
            == 403
        )

    def test_no_bearer_is_403(self):
        client = TestClient(_build_app(_seeded_repository(), user=None))
        assert client.get(f"/api/v1/authority-grants/{uuid4()}").status_code == 403


class TestGrantRoutes:
    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("plan_version", "3"),
            ("maximum_continuous_open_seconds", "21600"),
            ("maximum_intermediate_trims", True),
            ("flow_upper_inclusive_m3s", "8.0"),
        ],
    )
    def test_coercible_numeric_scalars_are_rejected(self, strict_mode, field, value):
        client = TestClient(_build_app(_seeded_repository()))
        response = client.post(
            "/api/v1/authority-grants", json=_grant_body(**{field: value})
        )
        assert response.status_code == 422

    def test_grant_issues_and_reads_back(self, strict_mode):
        repository = _seeded_repository()
        client = TestClient(_build_app(repository))
        issued = _issue(client)
        assert issued["status"] == "active"
        assert issued["plan_version"] == 3
        assert [event["event_type"] for event in issued["events"]] == ["granted"]
        got = client.get(f"/api/v1/authority-grants/{issued['grant_id']}")
        assert got.status_code == 200
        assert got.headers["cache-control"] == "no-store"
        by_plan = client.get(
            "/api/v1/authority-grants",
            params={"plan_id": str(PLAN_ID), "plan_version": 3},
        )
        assert by_plan.status_code == 200
        assert by_plan.json()["grant_id"] == issued["grant_id"]

    def test_review_is_a_dry_run(self, strict_mode):
        repository = _seeded_repository()
        client = TestClient(_build_app(repository))
        response = client.post("/api/v1/authority-grants/reviews", json=_grant_body())
        assert response.status_code == 200
        assert len(response.json()["would_grant_content_sha256"]) == 64
        assert repository.authority_grants == {}

    def test_validation_failure_is_422_with_reason(self, strict_mode):
        repository = _seeded_repository()
        repository.authority_evidence_counts[(PLAN_ID, 3)] = AuthorityEvidenceCounts(
            outbox_intent_count=2,
            accepted_receipt_intent_count=0,
            matching_receipt_intent_count=0,
        )
        client = TestClient(_build_app(repository))
        response = client.post("/api/v1/authority-grants", json=_grant_body())
        assert response.status_code == 422
        assert "receipt_coverage_incomplete" in response.json()["detail"]

    def test_unknown_plan_is_404_and_conflict_is_409(self, strict_mode):
        repository = _seeded_repository()
        client = TestClient(_build_app(repository))
        missing = client.post(
            "/api/v1/authority-grants",
            json=_grant_body(plan_id=str(uuid4())),
        )
        assert missing.status_code == 404
        _issue(client)
        conflicting = client.post(
            "/api/v1/authority-grants",
            json=_grant_body(expires_at=(NOW + 6 * HOUR).isoformat()),
        )
        assert conflicting.status_code == 409

    def test_unknown_grant_reads_are_404(self, strict_mode):
        client = TestClient(_build_app(_seeded_repository(), user=_OPERATOR))
        assert client.get(f"/api/v1/authority-grants/{uuid4()}").status_code == 404
        assert (
            client.get(
                "/api/v1/authority-grants",
                params={"plan_id": str(uuid4()), "plan_version": 1},
            ).status_code
            == 404
        )

    def test_corrupt_ledger_is_503(self, strict_mode):
        repository = _seeded_repository()
        client = TestClient(_build_app(repository))
        issued = _issue(client)
        repository.authority_grant_events[
            __import__("uuid").UUID(issued["grant_id"])
        ].clear()
        assert (
            client.get(f"/api/v1/authority-grants/{issued['grant_id']}").status_code
            == 503
        )

    def test_corrupt_outbox_or_inconsistent_count_is_503(self, strict_mode):
        repository = _seeded_repository()
        repository.outbox[(PLAN_ID, 3)][0] = replace(
            repository.outbox[(PLAN_ID, 3)][0],
            intent_document_text='{"corrupt":true}',
        )
        corrupt = TestClient(_build_app(repository)).post(
            "/api/v1/authority-grants", json=_grant_body()
        )
        assert corrupt.status_code == 503
        assert corrupt.json()["detail"] == "authority grant evidence is unavailable"

        inconsistent_repository = _seeded_repository()
        inconsistent_repository.authority_evidence_counts[
            (PLAN_ID, 3)
        ] = AuthorityEvidenceCounts(
            outbox_intent_count=3,
            accepted_receipt_intent_count=3,
            matching_receipt_intent_count=3,
        )
        inconsistent = TestClient(_build_app(inconsistent_repository)).post(
            "/api/v1/authority-grants", json=_grant_body()
        )
        assert inconsistent.status_code == 503
        assert inconsistent.json()["detail"] == (
            "authority grant evidence is unavailable"
        )


class TestRenewAndRevokeRoutes:
    def test_renewal_extends(self, strict_mode):
        repository = _seeded_repository()
        client = TestClient(_build_app(repository))
        issued = _issue(client)
        renewed = client.post(
            f"/api/v1/authority-grants/{issued['grant_id']}/renewals",
            json=_renewal_body(),
        )
        assert renewed.status_code == 200, renewed.text
        assert [e["event_type"] for e in renewed.json()["events"]] == [
            "granted",
            "renewed",
        ]

    def test_renewal_after_revocation_is_409(self, strict_mode):
        repository = _seeded_repository()
        client = TestClient(_build_app(repository))
        issued = _issue(client)
        client.post(
            f"/api/v1/authority-grants/{issued['grant_id']}/revocations",
            json={"reason": "stand down"},
        )
        renewed = client.post(
            f"/api/v1/authority-grants/{issued['grant_id']}/renewals",
            json=_renewal_body(),
        )
        assert renewed.status_code == 409

    def test_revoke_works_in_compat_and_is_idempotent(self, strict_mode):
        # Issue under strict, then flip back to compat and revoke: the safety
        # brake must not depend on the strict policy OR on prior revocations.
        repository = _seeded_repository()
        client = TestClient(_build_app(repository))
        issued = _issue(client)
        settings.jwt_claim_policy_mode = "compat"
        try:
            first = client.post(
                f"/api/v1/authority-grants/{issued['grant_id']}/revocations",
                json={"reason": "compat emergency"},
            )
            second = client.post(
                f"/api/v1/authority-grants/{issued['grant_id']}/revocations",
                json={"reason": "repeat click"},
            )
        finally:
            settings.jwt_claim_policy_mode = "strict"
        assert first.status_code == 200, first.text
        assert second.status_code == 200
        assert first.json()["status"] == "revoked"
        assert second.json()["status"] == "revoked"
        assert [e["event_type"] for e in second.json()["events"]] == [
            "granted",
            "revoked",
        ]
