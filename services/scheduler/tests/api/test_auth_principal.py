"""Effective-principal API contract for planning-depth authorization."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.v1.endpoints import auth
from api.v1.routes import api_router
from core.auth import token_revocation_key
from core.config import settings
from schemas.auth import EffectivePrincipalProjection


class _FakeRedis:
    def __init__(self, *, client=object(), revoked=frozenset(), raises=None):
        self.client = client
        self._revoked = set(revoked)
        self._raises = raises

    async def exists(self, key):
        if self._raises is not None:
            raise self._raises
        return key in self._revoked


def _token(*, subject="operator-1", roles=("operator",), expires=None):
    claims = {
        "sub": subject,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "type": settings.jwt_access_token_type,
        "jti": f"{subject}-jti",
        "roles": list(roles),
        "exp": expires or datetime.now(timezone.utc) + timedelta(minutes=5),
        "email": f"{subject}@example.invalid",
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm="HS256")


def _build_client(redis=None):
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.dependency_overrides[auth.get_redis] = lambda: redis or _FakeRedis()
    return TestClient(app)


def _get(client, token):
    return client.get(
        "/api/v1/auth/principal",
        headers={"Authorization": f"Bearer {token}"},
    )


class TestGetEffectivePrincipal:
    def test_operator_returns_only_sorted_inherited_canonical_roles(self):
        response = _get(_build_client(), _token(roles=("operator", "operator")))

        assert response.status_code == 200
        assert response.json() == {
            "subject": "operator-1",
            "effective_roles": ["field_team", "operator"],
        }
        assert response.headers["cache-control"] == "no-store"

    @pytest.mark.parametrize("role", ["rid_admin", "super_admin"])
    def test_admin_alias_returns_canonical_roles_without_sensitive_fields(self, role):
        response = _get(_build_client(), _token(subject="admin-1", roles=(role,)))

        assert response.status_code == 200
        assert response.json() == {
            "subject": "admin-1",
            "effective_roles": [
                "admin",
                "field_team",
                "operator",
                "supervisor",
            ],
        }
        assert response.headers["cache-control"] == "no-store"

    @pytest.mark.parametrize(
        ("roles", "expected_roles"),
        [
            (("zone_manager",), ["field_team", "operator"]),
            (
                ("operator", "government_official"),
                ["field_team", "operator"],
            ),
        ],
    )
    def test_noncanonical_roles_never_leak_into_a_recognized_projection(
        self, roles, expected_roles
    ):
        response = _get(_build_client(), _token(roles=roles))

        assert response.status_code == 200
        assert response.json() == {
            "subject": "operator-1",
            "effective_roles": expected_roles,
        }
        assert response.headers["cache-control"] == "no-store"

    def test_unknown_role_is_forbidden_without_role_leakage(self):
        response = _get(
            _build_client(),
            _token(roles=("government_official",)),
        )

        assert response.status_code == 403
        assert response.json() == {"detail": "Insufficient permissions"}
        assert response.headers["cache-control"] == "no-store"

    def test_revoked_token_is_unauthorized(self):
        token = _token()
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
        )
        redis = _FakeRedis(revoked={token_revocation_key(token, payload)})

        response = _get(_build_client(redis), token)

        assert response.status_code == 401
        assert response.json() == {"detail": "Token has been revoked"}
        assert response.headers["cache-control"] == "no-store"

    def test_revocation_store_outage_is_service_unavailable(self):
        response = _get(
            _build_client(_FakeRedis(raises=ConnectionError("redis down"))),
            _token(),
        )

        assert response.status_code == 503
        assert response.json() == {"detail": "token revocation store is unavailable"}
        assert response.headers["cache-control"] == "no-store"

    def test_missing_revocation_store_is_service_unavailable(self):
        response = _get(_build_client(_FakeRedis(client=None)), _token())

        assert response.status_code == 503
        assert response.json() == {"detail": "token revocation store is unavailable"}
        assert response.headers["cache-control"] == "no-store"

    def test_expired_token_is_unauthorized(self):
        response = _get(
            _build_client(),
            _token(expires=datetime.now(timezone.utc) - timedelta(minutes=5)),
        )

        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid or expired token"}
        assert response.headers["cache-control"] == "no-store"

    @pytest.mark.parametrize(
        ("headers", "expected_detail"),
        [
            ({}, "Not authenticated"),
            ({"Authorization": "Bearer garbage"}, "Invalid or expired token"),
        ],
    )
    def test_missing_or_invalid_bearer_is_unauthorized(self, headers, expected_detail):
        response = _build_client().get("/api/v1/auth/principal", headers=headers)

        assert response.status_code == 401
        assert response.json() == {"detail": expected_detail}
        assert response.headers["cache-control"] == "no-store"


class TestEffectivePrincipalProjection:
    @pytest.mark.parametrize(
        "payload",
        [
            {"subject": "", "effective_roles": ["field_team"]},
            {"subject": "operator-1", "effective_roles": ["operator", "field_team"]},
            {"subject": "operator-1", "effective_roles": ["operator", "operator"]},
            {"subject": "operator-1", "effective_roles": ["rid_admin"]},
            {
                "subject": "operator-1",
                "effective_roles": ["field_team"],
                "email": "operator@example.invalid",
            },
        ],
    )
    def test_projection_rejects_noncanonical_or_sensitive_payloads(self, payload):
        with pytest.raises(ValidationError):
            EffectivePrincipalProjection.model_validate(payload)
