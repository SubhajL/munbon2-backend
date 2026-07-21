"""Shared HTTP config for the SCADA machine-boundary clients (validation + readback).

Defines the host-only base-URL guard and the request timeout ONCE so the two clients cannot
drift (root CLAUDE.md: don't fork), and so neither has to import the other's privates.
"""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

SCADA_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


def require_hostonly_http_base_url(base_url: str, service_name: str) -> str:
    """Return an absolute host-only HTTP URL for a fixed-path service client."""
    trimmed = base_url.rstrip("/")
    parsed = urlparse(trimmed)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(
            f"{service_name} base URL must be an absolute http(s) URL: {base_url!r}"
        )
    if parsed.path not in ("", "/"):
        raise ValueError(
            f"{service_name} base URL must carry no path (got path {parsed.path!r}); the client "
            "appends only its fixed endpoint path"
        )
    if parsed.query or parsed.fragment:
        raise ValueError(f"{service_name} base URL must carry no query or fragment")
    if parsed.username or parsed.password:
        raise ValueError(
            f"{service_name} base URL must not embed userinfo (credentials)"
        )
    return trimmed


def require_hostonly_base_url(base_url: str) -> str:
    """Backwards-compatible SCADA-specific name used by machine clients."""
    return require_hostonly_http_base_url(base_url, "SCADA")
