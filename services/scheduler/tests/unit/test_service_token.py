"""PR 6.3a — the scheduler service-token minter must produce EXACTLY the token
SCADA's `verifySchedulerServiceToken` (services/scada-gate-control/src/api/service-auth.ts)
accepts: HS256, iss/aud, non-blank sub, type:'service', present exp, and an `iat` within
maxAge. `iat` is load-bearing — jsonwebtoken measures maxAge from it."""

from datetime import datetime, timezone

import jwt
import pytest

from core.service_token import mint_scheduler_service_token

SECRET = "sched-service-secret-of-quite-sufficient-length-xyz"
OPERATOR_SECRET = "a-different-operator-secret-also-sufficiently-long-1"
ISSUER = "munbon-scheduler"
AUDIENCE = "munbon-scada-machine-boundary"
SUBJECT = "scheduler-shadow-dispatcher"
NOW = datetime(2026, 7, 20, 3, 0, 0, tzinfo=timezone.utc)


def _decode(token, *, secret=SECRET, verify_exp=False):
    # Claim-inspection decodes assert the claim VALUES (minted at the fixed test `now`),
    # not live expiry against the real wall clock — so verify_exp defaults off. The
    # dedicated expiry test flips it on.
    return jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        audience=AUDIENCE,
        issuer=ISSUER,
        options={"verify_exp": verify_exp},
    )


def _mint(**over):
    params = dict(
        secret=SECRET,
        issuer=ISSUER,
        audience=AUDIENCE,
        subject=SUBJECT,
        now=NOW,
        max_age_seconds=300,
    )
    params.update(over)
    return mint_scheduler_service_token(**params)


class TestMintSchedulerServiceToken:
    def test_carries_exactly_the_claims_scada_requires(self):
        payload = _decode(_mint())
        assert payload["iss"] == ISSUER
        assert payload["aud"] == AUDIENCE
        assert payload["sub"] == SUBJECT
        assert payload["type"] == "service"
        # iat present and equal to `now`; exp = iat + max_age.
        assert payload["iat"] == int(NOW.timestamp())
        assert payload["exp"] == int(NOW.timestamp()) + 300

    def test_carries_no_roles_a_service_is_not_an_operator(self):
        assert "roles" not in _decode(_mint())

    def test_is_signed_with_the_service_secret_not_the_operator_secret(self):
        token = _mint()
        with pytest.raises(jwt.InvalidSignatureError):
            _decode(token, secret=OPERATOR_SECRET)

    def test_exp_tracks_the_configured_max_age(self):
        payload = _decode(_mint(max_age_seconds=120))
        assert payload["exp"] - payload["iat"] == 120

    def test_a_naive_now_is_treated_as_utc(self):
        naive = datetime(2026, 7, 20, 3, 0, 0)
        payload = _decode(_mint(now=naive))
        assert payload["iat"] == int(NOW.timestamp())

    def test_wrong_audience_is_rejected_by_a_verifier(self):
        # A token minted for a different audience must not verify against SCADA's.
        token = _mint(audience="some-other-service")
        with pytest.raises(jwt.InvalidAudienceError):
            _decode(token)

    def test_expired_token_fails_decode(self):
        # Mint with an iat far in the past so exp has already passed against the real
        # wall clock — proves exp is actually set and short-lived (SCADA also enforces it).
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)
        token = _mint(now=past, max_age_seconds=300)
        with pytest.raises(jwt.ExpiredSignatureError):
            _decode(token, verify_exp=True)
