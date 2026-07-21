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
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.request_id import RequestIDMiddleware
from api.v1.endpoints import authority_grants
from core.config import settings
from core.deps import get_current_user, get_db, get_redis
from repositories.control_plan_repository import AuthorityEvidenceCounts
from services.authority_grant_service import AuthorityGrantService
from api.v1.operator_controls import (
    get_auth_step_up_client,
    get_scada_operator_client,
)
from services.clients.auth_step_up_client import StepUpUnavailableError
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


class _StepUpClient:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    async def verify_step_up(self, access_token, code):
        self.calls.append((access_token, code))
        if self.error is not None:
            raise self.error


class _ScadaClient:
    def __init__(self, *, capability_hash=SHA_C, error=None):
        self.capability_hash = capability_hash
        self.error = error
        self.calls = []

    async def is_healthy(self):
        self.calls.append("health")
        if self.error is not None:
            raise self.error
        return True

    async def get_device_capabilities(self, access_token):
        self.calls.append(("capabilities", access_token))
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            capability_release_id=CAPABILITY_RELEASE_ID,
            capability_hash=self.capability_hash,
            capabilities={GATE: object()},
        )


class _ReplayStore:
    def __init__(self):
        self.keys = set()

    async def set_if_absent(self, key, value, *, expire):
        if key in self.keys:
            return False
        self.keys.add(key)
        return True


def _build_app(
    repository,
    user=_SUPERVISOR,
    *,
    step_up_client=None,
    scada_client=None,
):
    app = FastAPI()
    replay_store = _ReplayStore()
    app.state.device_capability_snapshot = SimpleNamespace(
        capability_release_id=CAPABILITY_RELEASE_ID,
        capability_hash=SHA_C,
        capabilities={GATE: object()},
    )
    app.add_middleware(RequestIDMiddleware)
    app.include_router(authority_grants.router, prefix="/api/v1/authority-grants")

    async def override_db():
        yield None

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: replay_store
    app.dependency_overrides[
        authority_grants.get_authority_grant_service
    ] = lambda: _service(repository)
    app.dependency_overrides[get_auth_step_up_client] = lambda: (
        step_up_client or _StepUpClient()
    )
    app.dependency_overrides[get_scada_operator_client] = lambda: (
        scada_client or _ScadaClient()
    )
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


def _positive_headers(action, identity, version=None, code="123456"):
    suffix = f" v{version}" if version is not None else ""
    return {
        "Authorization": "Bearer operator-access-token",
        "X-Operator-Confirmation": f"{action.upper()} {identity}{suffix}",
        "X-Operator-Step-Up-Code": code,
    }


def _confirmation_header(action, identity, version=None):
    suffix = f" v{version}" if version is not None else ""
    return {"X-Operator-Confirmation": f"{action.upper()} {identity}{suffix}"}


@pytest.fixture
def strict_mode(monkeypatch):
    monkeypatch.setattr(settings, "jwt_claim_policy_mode", "strict")


def _issue(client, code="123456"):
    response = client.post(
        "/api/v1/authority-grants",
        json=_grant_body(),
        headers={
            "Authorization": "Bearer operator-access-token",
            "X-Operator-Confirmation": f"GRANT {PLAN_ID} v3",
            "X-Operator-Step-Up-Code": code,
        },
    )
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


class TestSchedulerMutationGuards:
    def test_grant_rejects_missing_or_inexact_confirmation(self, strict_mode):
        client = TestClient(_build_app(_seeded_repository()))
        headers = {
            "Authorization": "Bearer operator-access-token",
            "X-Operator-Step-Up-Code": "123456",
        }
        missing = client.post(
            "/api/v1/authority-grants", json=_grant_body(), headers=headers
        )
        wrong = client.post(
            "/api/v1/authority-grants",
            json=_grant_body(),
            headers={
                **headers,
                "X-Operator-Confirmation": f"grant {PLAN_ID} v3",
            },
        )
        assert (missing.status_code, wrong.status_code) == (400, 400)

    def test_grant_verifies_totp_and_live_scada_before_mutation(self, strict_mode):
        step_up = _StepUpClient()
        scada = _ScadaClient()
        repository = _seeded_repository()
        client = TestClient(
            _build_app(repository, step_up_client=step_up, scada_client=scada)
        )

        issued = _issue(client)

        assert issued["status"] == "active"
        assert step_up.calls == [("operator-access-token", "123456")]
        assert scada.calls == [
            "health",
            ("capabilities", "operator-access-token"),
        ]

    def test_grant_fails_closed_when_step_up_is_unavailable(self, strict_mode):
        repository = _seeded_repository()
        client = TestClient(
            _build_app(
                repository,
                step_up_client=_StepUpClient(
                    StepUpUnavailableError("auth unavailable")
                ),
            )
        )

        response = client.post(
            "/api/v1/authority-grants",
            json=_grant_body(),
            headers={
                "Authorization": "Bearer operator-access-token",
                "X-Operator-Confirmation": f"GRANT {PLAN_ID} v3",
                "X-Operator-Step-Up-Code": "345678",
            },
        )

        assert response.status_code == 503
        assert repository.authority_grants == {}

    def test_grant_rejects_live_capability_drift(self, strict_mode):
        repository = _seeded_repository()
        client = TestClient(
            _build_app(repository, scada_client=_ScadaClient(capability_hash="f" * 64))
        )

        response = client.post(
            "/api/v1/authority-grants",
            json=_grant_body(),
            headers={
                "Authorization": "Bearer operator-access-token",
                "X-Operator-Confirmation": f"GRANT {PLAN_ID} v3",
                "X-Operator-Step-Up-Code": "123456",
            },
        )

        assert response.status_code == 409
        assert repository.authority_grants == {}

    def test_revoke_uses_confirmation_without_auth_or_scada(self, strict_mode):
        repository = _seeded_repository()
        client = TestClient(_build_app(repository))
        issued = _issue(client)
        exploding_step_up = _StepUpClient(AssertionError("must not call Auth"))
        exploding_scada = _ScadaClient(error=AssertionError("must not call SCADA"))
        brake = TestClient(
            _build_app(
                repository,
                step_up_client=exploding_step_up,
                scada_client=exploding_scada,
            )
        )

        response = brake.post(
            f"/api/v1/authority-grants/{issued['grant_id']}/revocations",
            json={"reason": "emergency stand-down"},
            headers={"X-Operator-Confirmation": f"REVOKE {issued['grant_id']}"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "revoked"
        assert exploding_step_up.calls == []
        assert exploding_scada.calls == []


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
            "/api/v1/authority-grants",
            json=_grant_body(**{field: value}),
            headers={
                "Authorization": "Bearer operator-access-token",
                "X-Operator-Confirmation": f"GRANT {PLAN_ID} v3",
                "X-Operator-Step-Up-Code": "123456",
            },
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
        response = client.post(
            "/api/v1/authority-grants",
            json=_grant_body(),
            headers={
                "Authorization": "Bearer operator-access-token",
                "X-Operator-Confirmation": f"GRANT {PLAN_ID} v3",
                "X-Operator-Step-Up-Code": "123456",
            },
        )
        assert response.status_code == 422
        assert "receipt_coverage_incomplete" in response.json()["detail"]

    def test_unknown_plan_is_404_and_conflict_is_409(self, strict_mode):
        repository = _seeded_repository()
        client = TestClient(_build_app(repository))
        missing_id = uuid4()
        missing = client.post(
            "/api/v1/authority-grants",
            json=_grant_body(plan_id=str(missing_id)),
            headers=_positive_headers("grant", missing_id, 3),
        )
        assert missing.status_code == 404
        _issue(client, code="234567")
        conflicting = client.post(
            "/api/v1/authority-grants",
            json=_grant_body(expires_at=(NOW + 6 * HOUR).isoformat()),
            headers={
                "Authorization": "Bearer operator-access-token",
                "X-Operator-Confirmation": f"GRANT {PLAN_ID} v3",
                "X-Operator-Step-Up-Code": "345678",
            },
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
            "/api/v1/authority-grants",
            json=_grant_body(),
            headers=_positive_headers("grant", PLAN_ID, 3),
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
            "/api/v1/authority-grants",
            json=_grant_body(),
            headers=_positive_headers("grant", PLAN_ID, 3),
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
            headers=_positive_headers("renew", issued["grant_id"], code="234567"),
        )
        assert renewed.status_code == 200, renewed.text
        assert [e["event_type"] for e in renewed.json()["events"]] == [
            "granted",
            "renewed",
        ]

    def test_same_totp_cannot_authorize_grant_then_renew(self, strict_mode):
        repository = _seeded_repository()
        client = TestClient(_build_app(repository))
        issued = _issue(client)

        renewed = client.post(
            f"/api/v1/authority-grants/{issued['grant_id']}/renewals",
            json=_renewal_body(),
            headers=_positive_headers("renew", issued["grant_id"]),
        )

        assert (renewed.status_code, renewed.json()) == (
            403,
            {"detail": "operator step-up code was already used"},
        )
        assert [
            event.event_type
            for event in repository.authority_grant_events[UUID(issued["grant_id"])]
        ] == ["granted"]


class TestAuthorityApplicabilityRoute:
    def test_operator_reads_no_store_server_derived_applicability(self):
        client = TestClient(_build_app(_seeded_repository(), user=_OPERATOR))

        response = client.get(
            "/api/v1/authority-grants/applicability",
            params={"plan_id": str(PLAN_ID), "plan_version": 3},
        )

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {
            "plan_id": str(PLAN_ID),
            "plan_version": 3,
            "evaluated_at": NOW.isoformat().replace("+00:00", "Z"),
            "lifecycle_state": "shadow_active",
            "model_release_id": RELEASE_ID,
            "model_release_content_hash": SHA_A,
            "engine_descriptor_content_hash": SHA_B,
            "model_release_commandable": True,
            "capability_release_id": CAPABILITY_RELEASE_ID,
            "capability_hash": SHA_C,
            "capability_configured": True,
            "capability_matches_outbox": True,
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
            "flow_upper_inclusive_m3s": 5.0,
            "initialization": {"kind": "dry"},
            "maximum_continuous_open_seconds": 10800,
            "maximum_intermediate_trims": 1,
            "outbox_intent_count": 2,
            "accepted_receipt_intent_count": 2,
            "matching_receipt_intent_count": 2,
            "receipt_coverage_complete": True,
            "existing_grant_status": None,
            "existing_grant_id": None,
            "blockers": [],
            "can_grant": True,
        }

    def test_tampered_outbox_makes_applicability_unavailable(self):
        repository = _seeded_repository()
        repository.outbox[(PLAN_ID, 3)][0] = replace(
            repository.outbox[(PLAN_ID, 3)][0],
            intent_content_hash="9" * 64,
        )
        client = TestClient(_build_app(repository, user=_OPERATOR))

        response = client.get(
            "/api/v1/authority-grants/applicability",
            params={"plan_id": str(PLAN_ID), "plan_version": 3},
        )

        assert (response.status_code, response.json()) == (
            503,
            {"detail": "authority grant evidence is unavailable"},
        )

    def test_unknown_plan_is_404_not_dynamic_grant_id_validation(self):
        client = TestClient(_build_app(FakeRepository(), user=_OPERATOR))
        response = client.get(
            "/api/v1/authority-grants/applicability",
            params={"plan_id": str(PLAN_ID), "plan_version": 3},
        )
        assert response.status_code == 404

    def test_viewer_role_cannot_read_applicability(self):
        client = TestClient(
            _build_app(_seeded_repository(), user={"sub": "viewer", "roles": []})
        )
        response = client.get(
            "/api/v1/authority-grants/applicability",
            params={"plan_id": str(PLAN_ID), "plan_version": 3},
        )
        assert response.status_code == 403

    def test_renewal_after_revocation_is_409(self, strict_mode):
        repository = _seeded_repository()
        client = TestClient(_build_app(repository))
        issued = _issue(client)
        client.post(
            f"/api/v1/authority-grants/{issued['grant_id']}/revocations",
            json={"reason": "stand down"},
            headers=_confirmation_header("revoke", issued["grant_id"]),
        )
        renewed = client.post(
            f"/api/v1/authority-grants/{issued['grant_id']}/renewals",
            json=_renewal_body(),
            headers=_positive_headers("renew", issued["grant_id"], code="234567"),
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
                headers=_confirmation_header("revoke", issued["grant_id"]),
            )
            second = client.post(
                f"/api/v1/authority-grants/{issued['grant_id']}/revocations",
                json={"reason": "repeat click"},
                headers=_confirmation_header("revoke", issued["grant_id"]),
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
