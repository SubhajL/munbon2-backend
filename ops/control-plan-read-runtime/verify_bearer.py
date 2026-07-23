#!/usr/bin/env python3
"""Secret-safe central-auth to Scheduler/BFF control-plan read verifier."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

MISSING_PLAN_ID = "00000000-0000-0000-0000-000000000000"


class VerificationError(RuntimeError):
    """A verifier failure whose message is always a fixed safe code."""


@dataclass(frozen=True)
class HttpResult:
    status: int
    body: Any
    headers: dict[str, str]


@dataclass(frozen=True)
class Config:
    email: str
    password: str
    audience: str
    auth_url: str = "http://127.0.0.1:3005"
    scheduler_url: str = "http://127.0.0.1:3021"
    bff_url: str = "http://127.0.0.1:3022"
    issuer: str = "munbon-auth"
    role: str = "operator"

    @classmethod
    def from_environment(cls) -> "Config":
        email = os.environ.get("MUNBON_OPERATOR_EMAIL", "")
        password = os.environ.get("MUNBON_OPERATOR_PASSWORD", "")
        if not email or not password:
            raise VerificationError("operator_credentials_missing")
        audience = os.environ.get("MUNBON_EXPECTED_JWT_AUDIENCE", "").strip()
        if not audience:
            raise VerificationError("expected_audience_missing")
        return cls(
            email=email,
            password=password,
            audience=audience,
            auth_url=os.environ.get("MUNBON_AUTH_URL", cls.auth_url).rstrip("/"),
            scheduler_url=os.environ.get(
                "MUNBON_SCHEDULER_URL", cls.scheduler_url
            ).rstrip("/"),
            bff_url=os.environ.get("MUNBON_BFF_URL", cls.bff_url).rstrip("/"),
            issuer=os.environ.get("MUNBON_EXPECTED_JWT_ISSUER", cls.issuer),
            role=os.environ.get("MUNBON_EXPECTED_ROLE", cls.role),
        )


class SafeReporter:
    def ok(self, step: str) -> None:
        print(f"PASS {step}")

    def fail(self, step: str, error: VerificationError) -> None:
        print(f"FAIL {step}: {error}")


class VerificationClient:
    def __init__(self) -> None:
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def request(
        self,
        method: str,
        url: str,
        *,
        payload: dict | None = None,
        bearer: str | None = None,
    ) -> HttpResult:
        headers = {"Accept": "application/json"}
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        if bearer is not None:
            headers["Authorization"] = f"Bearer {bearer}"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=10)
        except HTTPError as error:
            response = error
        except (OSError, URLError) as error:
            raise VerificationError("network_request_failed") from error
        try:
            raw = response.read()
            body = json.loads(raw) if raw else None
        except (ValueError, TypeError):
            body = None
        return HttpResult(
            status=response.status,
            body=body,
            headers={key.lower(): value for key, value in response.headers.items()},
        )

    def refresh_cookie(self) -> str:
        for cookie in self.cookies:
            if cookie.name == "refreshToken" and cookie.value:
                return cookie.value
        raise VerificationError("refresh_cookie_missing")


def decode_jwt_claims(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        if not isinstance(claims, dict):
            raise ValueError
        return claims
    except Exception as exc:
        raise VerificationError("malformed_access_token") from exc


def claim_errors(claims: dict, *, issuer: str, audience: str, role: str) -> list[str]:
    errors = []
    if claims.get("iss") != issuer:
        errors.append("issuer")
    aud = claims.get("aud")
    if not (aud == audience or isinstance(aud, list) and audience in aud):
        errors.append("audience")
    if claims.get("type") != "access":
        errors.append("type")
    if not isinstance(claims.get("sub"), str) or not claims["sub"].strip():
        errors.append("subject")
    if not isinstance(claims.get("jti"), str) or not claims["jti"].strip():
        errors.append("jti")
    roles = claims.get("roles")
    if not isinstance(roles, list) or role not in roles:
        errors.append("role")
    return errors


def _require_status(result: HttpResult, expected: int, code: str) -> None:
    if result.status != expected:
        raise VerificationError(code)


def _require_no_store(result: HttpResult, code: str) -> None:
    if "no-store" not in result.headers.get("cache-control", "").lower():
        raise VerificationError(code)


def verify_projection_page(status: int, body: Any) -> None:
    if (
        status != 200
        or not isinstance(body, dict)
        or body.get("projection_schema_version") != 2
        or not isinstance(body.get("items"), list)
        or "next_cursor" not in body
    ):
        raise VerificationError("invalid_projection_page")


def run_verification(config: Config, reporter: SafeReporter) -> dict[str, dict]:
    client = VerificationClient()
    evidence: dict[str, dict] = {}
    list_paths = (
        ("scheduler", f"{config.scheduler_url}/api/v1/control-plans"),
        ("bff", f"{config.bff_url}/api/v1/control-plans"),
    )
    statuses = {}
    for name, url in list_paths:
        result = client.request("GET", url)
        _require_status(result, 403, f"{name}_missing_bearer_status")
        statuses[name] = result.status
        if name == "bff":
            _require_no_store(result, "bff_missing_bearer_cache")
    evidence["missing_bearer"] = {
        **statuses,
        "bff_no_store": True,
    }
    reporter.ok("missing_bearer_rejected")

    statuses = {}
    for name, url in list_paths:
        result = client.request("GET", url, bearer="malformed-access-token")
        _require_status(result, 401, f"{name}_malformed_bearer_status")
        statuses[name] = result.status
        if name == "bff":
            _require_no_store(result, "bff_malformed_bearer_cache")
    evidence["malformed_bearer"] = {
        **statuses,
        "bff_no_store": True,
    }
    reporter.ok("malformed_bearer_rejected")

    login = client.request(
        "POST",
        f"{config.auth_url}/api/v1/auth/login",
        payload={"email": config.email, "password": config.password},
    )
    _require_status(login, 200, "central_login_status")
    try:
        token = login.body["data"]["accessToken"]
    except (KeyError, TypeError) as exc:
        raise VerificationError("central_login_contract") from exc
    if not isinstance(token, str) or not token:
        raise VerificationError("central_login_contract")
    errors = claim_errors(
        decode_jwt_claims(token),
        issuer=config.issuer,
        audience=config.audience,
        role=config.role,
    )
    if errors:
        raise VerificationError("access_claims_invalid")
    refresh_token = client.refresh_cookie()
    evidence["login"] = {"status": login.status, "claims": "valid"}
    reporter.ok("central_login_and_claims")

    statuses = {}
    for name, url in list_paths:
        result = client.request("GET", url, bearer=token)
        verify_projection_page(result.status, result.body)
        statuses[name] = result.status
        if name == "bff":
            _require_no_store(result, "bff_list_cache")
    evidence["operator_list"] = {**statuses, "bff_no_store": True}
    reporter.ok("operator_list_reads")

    detail_suffix = f"/{MISSING_PLAN_ID}/versions/1"
    statuses = {}
    for name, url in list_paths:
        result = client.request("GET", f"{url}{detail_suffix}", bearer=token)
        _require_status(result, 404, f"{name}_missing_detail_status")
        statuses[name] = result.status
        if name == "bff":
            _require_no_store(result, "bff_detail_cache")
    evidence["missing_detail"] = {**statuses, "bff_no_store": True}
    reporter.ok("missing_detail_preserved")

    logout = client.request(
        "POST",
        f"{config.auth_url}/api/v1/auth/logout",
        payload={"refreshToken": refresh_token},
    )
    _require_status(logout, 200, "central_logout_status")
    reuse = client.request(
        "POST",
        f"{config.auth_url}/api/v1/auth/refresh",
        payload={"refreshToken": refresh_token},
    )
    _require_status(reuse, 401, "refresh_reuse_status")
    evidence["logout"] = {"status": logout.status, "refresh_reuse": reuse.status}
    reporter.ok("logout_and_refresh_reuse_rejected")
    return evidence


def main() -> int:
    reporter = SafeReporter()
    try:
        config = Config.from_environment()
        run_verification(config, reporter)
    except VerificationError as error:
        reporter.fail("verification", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
