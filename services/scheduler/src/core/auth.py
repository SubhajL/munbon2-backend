"""Pure control-plane trust functions (PR 4.4a-1).

I/O-free by design so they are unit-testable and reusable from both the request
dependency layer (``core.deps``) and the approval evidence path. Signature and
``exp`` are validated by ``jwt.decode`` upstream; here we validate the CLAIM
SHAPE, derive fail-closed revocation identities that never embed the raw token
or jti, and build the authorization evidence that a strict-mode approval pins.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Mapping, Optional

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
# The approval route is gated by require_supervisor, so a genuine strict-mode
# approval's evidence carries a supervisor-or-admin role.
_APPROVAL_ROLES = frozenset({"supervisor", "admin"})


class TrustError(Exception):
    """Base control-plane trust failure."""


class InvalidClaimsError(TrustError):
    """A token's claim shape violates the active claim policy."""


@dataclass(frozen=True)
class ClaimPolicy:
    issuer: str
    audience: str
    access_token_type: str
    mode: str  # "compat" | "strict"
    policy_version: str


def policy_from_settings(settings) -> ClaimPolicy:
    return ClaimPolicy(
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        access_token_type=settings.jwt_access_token_type,
        mode=settings.jwt_claim_policy_mode,
        policy_version=settings.control_plan_authorization_policy_version,
    )


def _non_blank_str(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_roles(value) -> list:
    if not isinstance(value, list) or not all(
        isinstance(role, str) and role.strip() for role in value
    ):
        raise InvalidClaimsError("roles must be a list of non-blank strings")
    return list(value)


def _audience_matches(aud, expected: str) -> bool:
    if isinstance(aud, str):
        return aud == expected
    if isinstance(aud, (list, tuple)):
        return expected in aud
    return False


def validate_access_token_claims(payload: Mapping, policy: ClaimPolicy) -> dict:
    """Validate the claim shape and return a normalized principal.

    A non-blank subject (``sub`` or legacy ``user_id``) is always required. In
    ``strict`` mode every control claim (iss/aud/type/jti/roles) is mandatory
    and must match. In ``compat`` mode legacy tokens may omit them, but any
    claim that IS present must still be valid — a present-but-wrong claim is a
    forgery signal and is rejected in both modes.
    """
    subject = payload.get("sub") or payload.get("user_id")
    if not _non_blank_str(subject):
        raise InvalidClaimsError("token carries no subject")

    issuer = payload.get("iss")
    audience = payload.get("aud")
    token_type = payload.get("type")
    jti = payload.get("jti")

    if policy.mode == "strict":
        if issuer != policy.issuer:
            raise InvalidClaimsError("issuer does not match the strict policy")
        if not _audience_matches(audience, policy.audience):
            raise InvalidClaimsError("audience does not match the strict policy")
        if token_type != policy.access_token_type:
            raise InvalidClaimsError("token type does not match the strict policy")
        if not _non_blank_str(jti):
            raise InvalidClaimsError("strict tokens require a non-blank jti")
        roles = _validate_roles(payload.get("roles"))
        if not roles:
            raise InvalidClaimsError("strict tokens require a non-empty roles list")
    elif policy.mode == "compat":
        if issuer is not None and issuer != policy.issuer:
            raise InvalidClaimsError("present issuer does not match the policy")
        if audience is not None and not _audience_matches(audience, policy.audience):
            raise InvalidClaimsError("present audience does not match the policy")
        if token_type is not None and token_type != policy.access_token_type:
            raise InvalidClaimsError("present token type does not match the policy")
        if jti is not None and not _non_blank_str(jti):
            raise InvalidClaimsError("present jti must be non-blank")
        roles = _validate_roles(payload.get("roles")) if "roles" in payload else []
    else:
        raise InvalidClaimsError(f"unknown claim policy mode {policy.mode!r}")

    return {
        "subject": str(subject),
        "roles": roles,
        "jti": jti if _non_blank_str(jti) else None,
        "issuer": issuer if _non_blank_str(issuer) else None,
        "token_type": token_type if _non_blank_str(token_type) else None,
        "mode": policy.mode,
    }


def _jti_identity_digest(jti: str, issuer) -> str:
    issuer_part = issuer if isinstance(issuer, str) else ""
    return hashlib.sha256((issuer_part + "\x00" + jti).encode("utf-8")).hexdigest()


def token_revocation_key(raw_token: str, payload: Mapping) -> str:
    """A revocation-store key that NEVER embeds the raw token or raw jti.

    A jti-bearing token is revoked by an issuer-bound jti hash (so a jti reused
    across issuers cannot cross-revoke); a legacy token falls back to a hash of
    the opaque token bytes.
    """
    jti = payload.get("jti")
    if _non_blank_str(jti):
        return "token:blacklist:jti:" + _jti_identity_digest(jti, payload.get("iss"))
    return (
        "token:blacklist:sha256:"
        + hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    )


def principal_from_user(current_user: Mapping) -> dict:
    """Derive a normalized principal from a stored JWT payload dict.

    ``get_current_user`` returns the raw payload (so ``_actor_subject`` keeps
    working); this extracts the fields the evidence builder needs.
    """
    subject = current_user.get("sub") or current_user.get("user_id")
    roles = current_user.get("roles")
    if not isinstance(roles, list):
        roles = []
    jti = current_user.get("jti")
    issuer = current_user.get("iss")
    token_type = current_user.get("type")
    return {
        "subject": str(subject) if _non_blank_str(subject) else "",
        "roles": [role for role in roles if isinstance(role, str)],
        "jti": jti if _non_blank_str(jti) else None,
        "issuer": issuer if _non_blank_str(issuer) else None,
        "token_type": token_type if _non_blank_str(token_type) else None,
        "mode": current_user.get("mode"),
    }


def build_authorization_evidence(
    *,
    principal: Mapping,
    request_id: Optional[str],
    policy: ClaimPolicy,
    evidence_refs: Optional[list] = None,
) -> dict:
    """Authorization evidence pinned into a strict-mode shadow approval.

    The token identity is stored ONLY as a hash — the same digest used for
    revocation, minus the ``token:blacklist:`` prefix — so no raw token or jti
    is ever persisted. With a jti the digest is issuer-bound; without one it
    falls back to hashing the subject (the only stable identity available here).
    """
    jti = principal.get("jti")
    if _non_blank_str(jti):
        token_identity_sha256 = _jti_identity_digest(jti, principal.get("issuer"))
    else:
        token_identity_sha256 = hashlib.sha256(
            str(principal.get("subject", "")).encode("utf-8")
        ).hexdigest()
    return {
        "authorization_policy_version": policy.policy_version,
        "claim_policy_mode": policy.mode,
        "subject": principal["subject"],
        "roles": sorted(principal.get("roles", [])),
        "token_identity_sha256": token_identity_sha256,
        "request_id": request_id,
        "evidence_refs": list(evidence_refs or []),
    }


def is_trusted_authorization_evidence(evidence) -> bool:
    """True iff ``evidence`` is a COMPLETE strict-mode authorization evidence.

    The full contract that ``build_authorization_evidence`` produces must be
    present and well-formed: a strict-mode action by a supervisor-effective
    principal, hashed token identity, request id, and non-empty evidence refs.
    Shadow approvals (supersede trust) and authority grants (PR 7.1a) validate
    this SAME contract — extracted here so neither forks it.
    """
    if not isinstance(evidence, Mapping):
        return False
    if evidence.get("claim_policy_mode") != "strict":
        return False
    if not _non_blank_str(evidence.get("subject")):
        return False
    roles = evidence.get("roles")
    if not isinstance(roles, list) or not (
        _APPROVAL_ROLES & {r for r in roles if isinstance(r, str)}
    ):
        return False
    if not _non_blank_str(evidence.get("authorization_policy_version")):
        return False
    digest = evidence.get("token_identity_sha256")
    if not isinstance(digest, str) or not _SHA256_HEX.fullmatch(digest):
        return False
    if not _non_blank_str(evidence.get("request_id")):
        return False
    refs = evidence.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        return False
    if not all(_non_blank_str(ref) for ref in refs):
        return False
    return True


def is_trusted_shadow_approval(document: Mapping) -> bool:
    """True iff the approval is a v2 document with a COMPLETE strict-mode evidence.

    Legacy v1 freezes and compat-approved v2 documents are not trusted, and a
    forged one-field ``{"claim_policy_mode":"strict"}`` is rejected: the full
    evidence contract that ``build_authorization_evidence`` produces must be
    present and well-formed (a strict-mode approval by a supervisor-effective
    principal, hashed token identity, request id, and non-empty evidence refs).
    Only such a document may back a supersede.
    """
    if not isinstance(document, Mapping):
        return False
    # schema_version must be EXACTLY int 2 (reject bool True, which == 1).
    schema_version = document.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != 2:
        return False
    return is_trusted_authorization_evidence(document.get("authorization_evidence"))
