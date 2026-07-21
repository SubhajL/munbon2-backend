import base64
import json

import pytest

import verify_bearer


def _token(claims: dict) -> str:
    encode = (
        lambda value: base64.urlsafe_b64encode(json.dumps(value).encode())
        .decode()
        .rstrip("=")
    )
    return f"{encode({'alg': 'HS256'})}.{encode(claims)}.signature"


@pytest.mark.parametrize("audience", [None, "", "   "])
def test_config_requires_explicit_expected_audience(monkeypatch, audience):
    monkeypatch.setenv("MUNBON_OPERATOR_EMAIL", "operator@example.invalid")
    monkeypatch.setenv("MUNBON_OPERATOR_PASSWORD", "runtime-only-password")
    if audience is None:
        monkeypatch.delenv("MUNBON_EXPECTED_JWT_AUDIENCE", raising=False)
    else:
        monkeypatch.setenv("MUNBON_EXPECTED_JWT_AUDIENCE", audience)

    with pytest.raises(
        verify_bearer.VerificationError, match="expected_audience_missing"
    ):
        verify_bearer.Config.from_environment()


def test_config_uses_explicit_expected_audience(monkeypatch):
    monkeypatch.setenv("MUNBON_OPERATOR_EMAIL", "operator@example.invalid")
    monkeypatch.setenv("MUNBON_OPERATOR_PASSWORD", "runtime-only-password")
    monkeypatch.setenv("MUNBON_EXPECTED_JWT_AUDIENCE", "munbon-services")

    config = verify_bearer.Config.from_environment()

    assert config.audience == "munbon-services"


def test_decode_claims_and_validate_required_operator_identity():
    claims = {
        "iss": "munbon-auth",
        "aud": "munbon-api",
        "type": "access",
        "sub": "operator-id",
        "jti": "token-id",
        "roles": ["operator"],
    }

    decoded = verify_bearer.decode_jwt_claims(_token(claims))

    assert decoded == claims
    assert (
        verify_bearer.claim_errors(
            decoded, issuer="munbon-auth", audience="munbon-api", role="operator"
        )
        == []
    )


@pytest.mark.parametrize(
    "claims,expected",
    [
        ({}, ["issuer", "audience", "type", "subject", "jti", "role"]),
        (
            {
                "iss": "wrong",
                "aud": ["other"],
                "type": "refresh",
                "sub": "",
                "jti": "",
                "roles": ["viewer"],
            },
            ["issuer", "audience", "type", "subject", "jti", "role"],
        ),
    ],
)
def test_claim_validation_fails_closed(claims, expected):
    assert (
        verify_bearer.claim_errors(
            claims, issuer="munbon-auth", audience="munbon-api", role="operator"
        )
        == expected
    )


def test_decode_rejects_malformed_token_without_echoing_it():
    with pytest.raises(
        verify_bearer.VerificationError, match="malformed_access_token"
    ) as exc:
        verify_bearer.decode_jwt_claims("credential-bearing-secret")

    assert "credential-bearing-secret" not in str(exc.value)


def test_verify_projection_requires_v2_list_shape():
    verify_bearer.verify_projection_page(
        200, {"projection_schema_version": 2, "items": [], "next_cursor": None}
    )

    with pytest.raises(
        verify_bearer.VerificationError, match="invalid_projection_page"
    ):
        verify_bearer.verify_projection_page(
            200, {"projection_schema_version": 1, "items": []}
        )


def test_safe_reporter_never_prints_credentials(capsys):
    reporter = verify_bearer.SafeReporter()
    reporter.ok("central_login")
    reporter.fail("operator_reads", verify_bearer.VerificationError("safe_code"))

    output = capsys.readouterr().out
    assert output.splitlines() == [
        "PASS central_login",
        "FAIL operator_reads: safe_code",
    ]
