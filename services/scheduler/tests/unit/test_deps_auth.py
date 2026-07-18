"""Hardened auth dependencies (PR 4.4a-1): HS256 pinning, fail-closed
revocation, and RBAC role hierarchy.

These exercise the request-facing dependency layer of ``core.deps`` against
real ``jwt`` tokens and controllable fake revocation stores. The whole point is
fail-closed: a revocation-store outage must never let a token through, and the
HS256 algorithm is pinned from settings — never taken from the token header.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

from core import deps
from core.auth import token_revocation_key
from core.config import settings


def _token(**overrides):
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "user-1",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "type": settings.jwt_access_token_type,
        "jti": "jti-1",
        "roles": ["operator"],
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, settings.jwt_secret_key, algorithm="HS256")


class _FakeRedis:
    """A revocation store whose behaviour is fully controllable."""

    def __init__(self, *, client=object(), revoked=frozenset(), raises=None):
        self.client = client
        self._revoked = set(revoked)
        self._raises = raises
        self.checked = []

    async def exists(self, key):
        self.checked.append(key)
        if self._raises is not None:
            raise self._raises
        return key in self._revoked


class _Credentials:
    def __init__(self, token):
        self.credentials = token


class TestVerifyToken:
    @pytest.mark.asyncio
    async def test_verify_token_accepts_a_well_formed_token(self):
        payload = await deps.verify_token(_token())
        assert payload is not None
        assert payload["sub"] == "user-1"

    @pytest.mark.asyncio
    async def test_verify_token_pins_hs256_and_rejects_other_alg(self):
        # A token the client tries to pass with a different algorithm must be
        # rejected: the verifier pins settings.jwt_algorithm (HS256).
        hs512 = jwt.encode(
            {
                "sub": "user-1",
                "iss": settings.jwt_issuer,
                "aud": settings.jwt_audience,
                "type": settings.jwt_access_token_type,
                "jti": "jti-1",
                "roles": ["operator"],
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            settings.jwt_secret_key,
            algorithm="HS512",
        )
        assert await deps.verify_token(hs512) is None

    @pytest.mark.asyncio
    async def test_verify_token_requires_exp(self):
        no_exp = jwt.encode(
            {
                "sub": "user-1",
                "iss": settings.jwt_issuer,
                "aud": settings.jwt_audience,
                "type": settings.jwt_access_token_type,
                "jti": "jti-1",
                "roles": ["operator"],
            },
            settings.jwt_secret_key,
            algorithm="HS256",
        )
        assert await deps.verify_token(no_exp) is None

    @pytest.mark.asyncio
    async def test_verify_token_rejects_expired(self):
        expired = _token(
            exp=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        assert await deps.verify_token(expired) is None


class TestGetCurrentUserRevocation:
    @pytest.mark.asyncio
    async def test_valid_token_with_clean_store_returns_payload(self):
        token = _token()
        user = await deps.get_current_user(
            _Credentials(token), _FakeRedis()
        )
        assert user["sub"] == "user-1"

    @pytest.mark.asyncio
    async def test_get_current_user_fails_closed_when_store_client_missing(self):
        token = _token()
        with pytest.raises(HTTPException) as info:
            await deps.get_current_user(
                _Credentials(token), _FakeRedis(client=None)
            )
        assert info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_get_current_user_fails_closed_when_store_raises(self):
        token = _token()
        redis = _FakeRedis(raises=ConnectionError("redis down"))
        with pytest.raises(HTTPException) as info:
            await deps.get_current_user(_Credentials(token), redis)
        assert info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_get_current_user_rejects_revoked_by_hashed_key(self):
        token = _token()
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
        )
        key = token_revocation_key(token, payload)
        redis = _FakeRedis(revoked={key})
        with pytest.raises(HTTPException) as info:
            await deps.get_current_user(_Credentials(token), redis)
        assert info.value.status_code == 401
        # It must look up the HASHED key, never the raw token.
        assert redis.checked == [key]
        assert token not in redis.checked[0]

    @pytest.mark.asyncio
    async def test_revoked_by_legacy_raw_token_key(self):
        # Dual-read: a revocation written by an as-yet-unmigrated logout/auth
        # service using the OLD token:blacklist:<raw-token> scheme must still
        # deny the token even though this reader now computes a hashed key.
        token = _token()
        redis = _FakeRedis(revoked={f"token:blacklist:{token}"})
        with pytest.raises(HTTPException) as info:
            await deps.get_current_user(_Credentials(token), redis)
        assert info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_revoked_by_token_hash_fallback_when_no_jti(self, monkeypatch):
        # A legacy (compat) token without a jti is revoked via the
        # sha256(raw-token) fallback key, not a jti digest.
        monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", "compat")
        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {"sub": "legacy-1", "exp": now + timedelta(minutes=5)},
            settings.jwt_secret_key,
            algorithm="HS256",
        )
        key = token_revocation_key(token, {"sub": "legacy-1"})
        assert key.startswith("token:blacklist:sha256:")
        redis = _FakeRedis(revoked={key})
        with pytest.raises(HTTPException) as info:
            await deps.get_current_user(_Credentials(token), redis)
        assert info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_is_401_before_store_lookup(self):
        redis = _FakeRedis()
        with pytest.raises(HTTPException) as info:
            await deps.get_current_user(_Credentials("garbage"), redis)
        assert info.value.status_code == 401
        assert redis.checked == []


class TestRoleHierarchy:
    def _check(self, checker, roles, mode="strict"):
        from types import SimpleNamespace

        request = SimpleNamespace(url=SimpleNamespace(path="/x"))
        return checker(request, {"sub": "u", "roles": roles, "mode": mode})

    def test_role_hierarchy_admin_satisfies_operator_and_supervisor(self):
        for checker in (
            deps.require_operator,
            deps.require_supervisor,
            deps.require_admin,
            deps.require_field_team,
        ):
            assert self._check(checker, ["admin"])["sub"] == "u"

    def test_supervisor_satisfies_operator_but_not_admin(self):
        assert self._check(deps.require_operator, ["supervisor"])
        assert self._check(deps.require_supervisor, ["supervisor"])
        with pytest.raises(HTTPException) as info:
            self._check(deps.require_admin, ["supervisor"])
        assert info.value.status_code == 403

    def test_operator_cannot_satisfy_supervisor(self):
        with pytest.raises(HTTPException) as info:
            self._check(deps.require_supervisor, ["operator"])
        assert info.value.status_code == 403

    def test_present_but_insufficient_role_is_403_even_in_compat(self):
        with pytest.raises(HTTPException) as info:
            self._check(deps.require_supervisor, ["operator"], mode="compat")
        assert info.value.status_code == 403

    def test_roleless_token_denied_in_both_modes(self, monkeypatch):
        # RBAC always requires a matching effective role; compat relaxes only the
        # token claim SHAPE, never the authorization decision, so a role-less
        # principal is 403 on a supervisor-gated route in BOTH modes.
        for mode in ("compat", "strict"):
            monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", mode)
            with pytest.raises(HTTPException) as info:
                self._check(deps.require_supervisor, [], mode=mode)
            assert info.value.status_code == 403, mode

    def test_roleless_token_denied_on_operator_route_too(self, monkeypatch):
        monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", "compat")
        with pytest.raises(HTTPException) as info:
            self._check(deps.require_operator, [], mode="compat")
        assert info.value.status_code == 403


class TestStrictApprovalPolicyGuard:
    def test_require_strict_approval_policy_503_in_compat(self, monkeypatch):
        monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", "compat")
        with pytest.raises(HTTPException) as info:
            deps.require_strict_approval_policy()
        assert info.value.status_code == 503

    def test_require_strict_approval_policy_passes_in_strict(self, monkeypatch):
        monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", "strict")
        assert deps.require_strict_approval_policy() is None
