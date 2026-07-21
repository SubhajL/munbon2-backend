"""Pure control-plane trust functions (PR 4.4a-1): fail-closed by construction.

These cover ``core.auth`` (claim-shape validation, hashed revocation identity,
authorization evidence, trusted-approval predicate) and the strong-secret
Settings validator. All functions here are I/O-free and unit-tested directly.
"""

import hashlib

import pytest

from core.auth import (
    ClaimPolicy,
    InvalidClaimsError,
    build_authorization_evidence,
    is_trusted_shadow_approval,
    policy_from_settings,
    token_revocation_key,
    validate_access_token_claims,
)
from core.config import Settings

_STRONG_SECRET = "prod-grade-jwt-secret-with-enough-entropy-32b"


def _settings(**overrides):
    base = {
        "database_url": "postgresql://u:p@localhost:5432/db",
        "redis_url": "redis://localhost:6379/4",
        "ros_service_url": "http://localhost:3047",
        "gis_service_url": "http://localhost:3007",
        "flow_monitoring_url": "http://localhost:3011",
        "ros_gis_url": "http://localhost:3047",
        "weather_service_url": "http://localhost:3006",
        "auth_service_url": "http://localhost:3001",
        "jwt_secret_key": _STRONG_SECRET,
        "jwt_issuer": "munbon-auth",
        "jwt_audience": "munbon-scheduler",
        "jwt_claim_policy_mode": "compat",
    }
    base.update(overrides)
    return Settings(**base)


def _strict_policy():
    return ClaimPolicy(
        issuer="munbon-auth",
        audience="munbon-scheduler",
        access_token_type="access",
        mode="strict",
        policy_version="control-plan-rbac-v1",
    )


def _compat_policy():
    return ClaimPolicy(
        issuer="munbon-auth",
        audience="munbon-scheduler",
        access_token_type="access",
        mode="compat",
        policy_version="control-plan-rbac-v1",
    )


def _strict_token(**overrides):
    payload = {
        "sub": "user-1",
        "iss": "munbon-auth",
        "aud": "munbon-scheduler",
        "type": "access",
        "jti": "jti-abc",
        "roles": ["operator"],
    }
    payload.update(overrides)
    return payload


class TestStrongSecretValidator:
    @pytest.mark.parametrize(
        "weak",
        [
            "change-me",
            "CHANGE-ME",
            "secret",
            "password",
            "dev",
            "test",
            "short",  # < 32 bytes
            "a" * 40,  # single repeated character
            "ab" * 16,  # >=32 bytes but a period-2 repeated pattern
            "abcd" * 8,  # period-4 repeated pattern
            "a" * 31 + "b",  # >=32 bytes but only two distinct characters
            "   ",  # blank/whitespace
            "",
        ],
    )
    def test_settings_rejects_default_or_short_jwt_secret(self, weak):
        with pytest.raises(Exception) as info:
            _settings(jwt_secret_key=weak)
        # Fail-closed: it must be the SECRET that is rejected, not some other
        # unrelated field.
        assert (
            "jwt_secret_key" in str(info.value).lower()
            or "secret" in str(info.value).lower()
        )

    def test_settings_accepts_a_strong_secret(self):
        settings = _settings(jwt_secret_key=_STRONG_SECRET)
        assert settings.jwt_secret_key == _STRONG_SECRET

    def test_settings_rejects_non_hs256_algorithm(self):
        with pytest.raises(Exception):
            _settings(jwt_algorithm="none")

    def test_settings_rejects_unknown_claim_policy_mode(self):
        with pytest.raises(Exception):
            _settings(jwt_claim_policy_mode="permissive")

    def test_policy_from_settings_maps_all_fields(self):
        policy = policy_from_settings(_settings(jwt_claim_policy_mode="strict"))
        assert (policy.issuer, policy.audience, policy.mode) == (
            "munbon-auth",
            "munbon-scheduler",
            "strict",
        )
        assert policy.access_token_type == "access"
        assert policy.policy_version == "control-plan-rbac-v1"


class TestValidateAccessTokenClaims:
    def test_validate_claims_accepts_legacy_only_in_compat(self):
        legacy = {"sub": "user-1"}  # no iss/aud/type/jti/roles
        principal = validate_access_token_claims(legacy, _compat_policy())
        assert principal["subject"] == "user-1"
        assert principal["roles"] == []
        with pytest.raises(InvalidClaimsError):
            validate_access_token_claims(legacy, _strict_policy())

    def test_legacy_user_id_is_accepted_as_subject(self):
        principal = validate_access_token_claims(
            {"user_id": "legacy-7"}, _compat_policy()
        )
        assert principal["subject"] == "legacy-7"

    def test_blank_subject_is_rejected_in_both_modes(self):
        for policy in (_compat_policy(), _strict_policy()):
            with pytest.raises(InvalidClaimsError):
                validate_access_token_claims({"sub": "   "}, policy)

    def test_validate_claims_requires_every_control_claim_in_strict(self):
        policy = _strict_policy()
        assert validate_access_token_claims(_strict_token(), policy)["jti"] == (
            "jti-abc"
        )
        for broken in (
            _strict_token(jti=""),
            _strict_token(iss="evil"),
            _strict_token(aud="other-service"),
            _strict_token(type="refresh"),
            _strict_token(roles=[]),
            {k: v for k, v in _strict_token().items() if k != "jti"},
            {k: v for k, v in _strict_token().items() if k != "roles"},
        ):
            with pytest.raises(InvalidClaimsError):
                validate_access_token_claims(broken, policy)

    def test_strict_audience_accepts_list_containing_audience(self):
        principal = validate_access_token_claims(
            _strict_token(aud=["other", "munbon-scheduler"]), _strict_policy()
        )
        assert principal["subject"] == "user-1"

    def test_compat_validates_present_claims(self):
        policy = _compat_policy()
        # A present-but-WRONG issuer is rejected even in compat.
        with pytest.raises(InvalidClaimsError):
            validate_access_token_claims({"sub": "user-1", "iss": "evil"}, policy)
        # A present-but-blank jti is rejected even in compat.
        with pytest.raises(InvalidClaimsError):
            validate_access_token_claims({"sub": "user-1", "jti": "  "}, policy)
        # Present roles that are not a list of strings are rejected.
        with pytest.raises(InvalidClaimsError):
            validate_access_token_claims({"sub": "user-1", "roles": ["ok", 3]}, policy)

    def test_compat_accepts_present_valid_claims_and_normalizes(self):
        principal = validate_access_token_claims(
            {
                "sub": "user-1",
                "iss": "munbon-auth",
                "aud": "munbon-scheduler",
                "type": "access",
                "jti": "jti-9",
                "roles": ["supervisor"],
            },
            _compat_policy(),
        )
        assert principal == {
            "subject": "user-1",
            "roles": ["supervisor"],
            "jti": "jti-9",
            "issuer": "munbon-auth",
            "token_type": "access",
            "mode": "compat",
        }


class TestRevocationKey:
    def test_revocation_key_never_contains_raw_token_or_jti(self):
        raw = "header.body.signature-secret-material"
        jti = "super-secret-jti-value"
        key = token_revocation_key(raw, {"jti": jti, "iss": "munbon-auth"})
        assert key.startswith("token:blacklist:jti:")
        assert jti not in key
        assert raw not in key
        # The digest binds issuer + jti so the SAME jti under a different issuer
        # yields a different key (cross-issuer collisions cannot revoke).
        other = token_revocation_key(raw, {"jti": jti, "iss": "other-issuer"})
        assert other != key

    def test_revocation_key_falls_back_to_token_hash_without_jti(self):
        raw = "opaque.legacy.token"
        key = token_revocation_key(raw, {"sub": "user-1"})
        assert key.startswith("token:blacklist:sha256:")
        assert raw not in key
        assert key.endswith(hashlib.sha256(raw.encode()).hexdigest())


class TestAuthorizationEvidence:
    def test_build_authorization_evidence_hashes_identity_and_sorts_roles(self):
        principal = {
            "subject": "user-1",
            "roles": ["operator", "admin", "supervisor"],
            "jti": "jti-xyz",
            "issuer": "munbon-auth",
            "token_type": "access",
            "mode": "strict",
        }
        evidence = build_authorization_evidence(
            principal=principal,
            request_id="req-42",
            policy=_strict_policy(),
            evidence_refs=["ref-b", "ref-a"],
        )
        assert evidence["authorization_policy_version"] == "control-plan-rbac-v1"
        assert evidence["claim_policy_mode"] == "strict"
        assert evidence["subject"] == "user-1"
        assert evidence["roles"] == ["admin", "operator", "supervisor"]
        assert evidence["request_id"] == "req-42"
        assert evidence["evidence_refs"] == ["ref-b", "ref-a"]
        # The identity fingerprint must equal the revocation digest (sans prefix)
        # and must never leak the raw jti.
        expected = hashlib.sha256(
            ("munbon-auth" + "\x00" + "jti-xyz").encode()
        ).hexdigest()
        assert evidence["token_identity_sha256"] == expected
        serialized = str(evidence)
        assert "jti-xyz" not in serialized

    def test_evidence_defaults_refs_to_empty_list(self):
        evidence = build_authorization_evidence(
            principal={"subject": "u", "roles": [], "jti": "j", "issuer": "i"},
            request_id=None,
            policy=_strict_policy(),
        )
        assert evidence["evidence_refs"] == []
        assert evidence["request_id"] is None


class TestIsTrustedShadowApproval:
    @staticmethod
    def _complete_strict_evidence() -> dict:
        return {
            "authorization_policy_version": "control-plan-rbac-v1",
            "claim_policy_mode": "strict",
            "subject": "supervisor-1",
            "roles": ["supervisor"],
            "token_identity_sha256": "a" * 64,
            "request_id": "req-1",
            "evidence_refs": ["ticket-123"],
        }

    @staticmethod
    def _v2_doc(evidence: dict) -> dict:
        return {
            "schema_version": 2,
            "lineage_freeze": {"schema_version": 1},
            "authorization_evidence": evidence,
        }

    def test_is_trusted_shadow_approval_only_for_strict_v2(self):
        # Legacy v1 bare freeze and compat-mode v2 are never trusted.
        assert is_trusted_shadow_approval({"schema_version": 1}) is False
        compat = {**self._complete_strict_evidence(), "claim_policy_mode": "compat"}
        assert is_trusted_shadow_approval(self._v2_doc(compat)) is False
        # A forged one-field strict evidence must NOT read as trusted.
        assert (
            is_trusted_shadow_approval(self._v2_doc({"claim_policy_mode": "strict"}))
            is False
        )
        # A complete strict evidence IS trusted.
        assert (
            is_trusted_shadow_approval(self._v2_doc(self._complete_strict_evidence()))
            is True
        )

    def test_is_trusted_rejects_each_incomplete_or_malformed_field(self):
        for missing in (
            "authorization_policy_version",
            "subject",
            "roles",
            "token_identity_sha256",
            "request_id",
            "evidence_refs",
        ):
            evidence = self._complete_strict_evidence()
            del evidence[missing]
            assert (
                is_trusted_shadow_approval(self._v2_doc(evidence)) is False
            ), f"missing {missing} must not be trusted"
        # A non-supervisor approver role is not a valid approval evidence.
        operator_only = {**self._complete_strict_evidence(), "roles": ["operator"]}
        assert is_trusted_shadow_approval(self._v2_doc(operator_only)) is False
        # A malformed token identity digest is rejected.
        bad_digest = {
            **self._complete_strict_evidence(),
            "token_identity_sha256": "not-a-digest",
        }
        assert is_trusted_shadow_approval(self._v2_doc(bad_digest)) is False
        # An empty evidence_refs list is rejected.
        empty_refs = {**self._complete_strict_evidence(), "evidence_refs": []}
        assert is_trusted_shadow_approval(self._v2_doc(empty_refs)) is False
        # schema_version must be int 2 — bool True (== 1) is rejected.
        bool_version = {
            "schema_version": True,
            "authorization_evidence": self._complete_strict_evidence(),
        }
        assert is_trusted_shadow_approval(bool_version) is False


class TestIsTrustedAuthorizationEvidence:
    """PR 7.1a: the strict-evidence completeness check, extracted so authority
    grants and shadow approvals validate the SAME contract (no fork)."""

    @staticmethod
    def _evidence(**overrides) -> dict:
        base = {
            "authorization_policy_version": "control-plan-rbac-v1",
            "claim_policy_mode": "strict",
            "subject": "supervisor-1",
            "roles": ["supervisor"],
            "token_identity_sha256": "a" * 64,
            "request_id": "req-1",
            "evidence_refs": ["ticket-123"],
        }
        base.update(overrides)
        return base

    def test_complete_strict_evidence_is_trusted(self):
        from core.auth import is_trusted_authorization_evidence

        assert is_trusted_authorization_evidence(self._evidence()) is True

    @pytest.mark.parametrize(
        "overrides",
        [
            {"claim_policy_mode": "compat"},
            {"subject": " "},
            {"roles": ["operator"]},
            {"roles": "supervisor"},
            {"authorization_policy_version": ""},
            {"token_identity_sha256": "xyz"},
            {"request_id": None},
            {"evidence_refs": []},
            {"evidence_refs": ["ok", "  "]},
        ],
    )
    def test_incomplete_or_weak_evidence_is_untrusted(self, overrides):
        from core.auth import is_trusted_authorization_evidence

        assert is_trusted_authorization_evidence(self._evidence(**overrides)) is False

    def test_non_mapping_is_untrusted(self):
        from core.auth import is_trusted_authorization_evidence

        assert is_trusted_authorization_evidence(None) is False
