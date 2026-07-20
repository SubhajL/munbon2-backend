"""PR 6.3a — mint the scheduler -> SCADA machine-boundary service token.

Pure and I/O-free (takes the signing time as ``now``). This is the scheduler's FIRST
token-minting capability — ``core.auth`` is verify-only. The token is CRYPTOGRAPHICALLY
SEPARATE from operator auth: it is signed with the DEDICATED
``SCHEDULER_SERVICE_JWT_SECRET`` (never ``jwt_secret_key``) and carries ``type:'service'``
with NO roles, so a service token can never cross over into the operator API.

The claim set is EXACTLY what SCADA's ``verifySchedulerServiceToken``
(services/scada-gate-control/src/api/service-auth.ts) requires: HS256, ``iss``, ``aud``,
non-blank ``sub``, ``type:'service'``, a present ``exp``, and an ``iat`` — ``iat`` is
LOAD-BEARING because jsonwebtoken measures its ``maxAge`` staleness window from it; omit it
and SCADA throws. Mint FRESH per dispatch (short-lived) so the token is well within maxAge
when SCADA verifies it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import jwt


def mint_scheduler_service_token(
    *,
    secret: str,
    issuer: str,
    audience: str,
    subject: str,
    now: datetime,
    max_age_seconds: int = 300,
    jti: Optional[str] = None,
) -> str:
    """Return a signed HS256 service token valid from ``now`` for ``max_age_seconds``."""
    aware = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(
        timezone.utc
    )
    issued_at = int(aware.timestamp())
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "type": "service",
        "iat": issued_at,
        "exp": issued_at + max_age_seconds,
    }
    if jti is not None:
        payload["jti"] = jti
    return jwt.encode(payload, secret, algorithm="HS256")
