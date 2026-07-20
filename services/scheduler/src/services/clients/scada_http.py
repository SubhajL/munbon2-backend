"""Shared HTTP config for the SCADA machine-boundary clients (validation + readback).

Defines the host-only base-URL guard and the request timeout ONCE so the two clients cannot
drift (root CLAUDE.md: don't fork), and so neither has to import the other's privates.
"""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

SCADA_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


def require_hostonly_base_url(base_url: str) -> str:
    """Reject a base URL that carries any path/query/fragment/userinfo — defense-in-depth so a
    misconfigured base can never smuggle an operator/execute path into ``{base}{path}``, nor ship
    the bearer SERVICE TOKEN to a userinfo-decoded host."""
    trimmed = base_url.rstrip("/")
    parsed = urlparse(trimmed)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"SCADA base URL must be an absolute http(s) URL: {base_url!r}")
    if parsed.path not in ("", "/"):
        raise ValueError(
            f"SCADA base URL must carry no path (got path {parsed.path!r}); the client "
            "appends only its fixed endpoint path"
        )
    if parsed.query or parsed.fragment:
        raise ValueError("SCADA base URL must carry no query or fragment")
    if parsed.username or parsed.password:
        raise ValueError("SCADA base URL must not embed userinfo (credentials)")
    return trimmed
