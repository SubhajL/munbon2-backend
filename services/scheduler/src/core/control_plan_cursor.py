"""Opaque, versioned keyset cursor for the control-plan list projection (PR 4.4a-3).

A cursor pins the last-seen ``(created_at, plan_id, plan_version)`` of a page AND
a hash of the active filter set. The ``(created_at, plan_id, plan_version)`` triple
is the row's TOTAL identity, so the keyset order is provably a strict total order
and pagination can never skip or duplicate a row (two rows sharing a created_at
AND a plan_id but differing in plan_version are still separated by the final
tie-break). Keyset pagination is only meaningful within one ORDER BY over one
filtered set, so a cursor issued for one filter set must NOT be reusable against a
different one: ``decode`` fails closed (typed ``CursorError`` → the endpoint maps
it to 422) on a filter mismatch, an unknown schema version, a non-UTC timestamp,
or any malformed encoding. The cursor is ``base64url(canonical JSON)`` so it is
compact, URL-safe, and opaque to clients.

NOTE: this cursor is an UNSIGNED client-continuity token, NOT a security boundary.
An authenticated caller who forges one only repositions pagination WITHIN the
already-authorized, still-filtered, RBAC-gated set (the WHERE clause re-applies
require_operator + the filters + the keyset server-side); no row crosses a trust
boundary and no data is exposed, so it is deliberately NOT HMAC-signed.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional
from uuid import UUID

CURSOR_SCHEMA_VERSION = 1

# Exact urlsafe-base64 alphabet (RFC 4648 §5) plus 0-2 trailing '=' pad chars.
# ``urlsafe_b64decode`` is lenient (it silently tolerates embedded newlines and
# trailing junk), so we gate on this before decoding to fail closed on a cursor
# with appended garbage or whitespace.
_URLSAFE_B64_RE = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")
_URLSAFE_TO_STANDARD = str.maketrans("-_", "+/")


class CursorError(Exception):
    """A list cursor is malformed, stale, or bound to a different filter set."""


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def normalize_filters(filters: Optional[Mapping[str, Any]]) -> dict:
    """A stable, hashable view of the active filter set.

    ``None``-valued filters (absent query params) are dropped so an omitted
    filter and an explicit null collapse to the same identity; every remaining
    value is stringified and the keys are sorted so the hash is independent of
    query-parameter order.
    """
    normalized: dict[str, str] = {}
    for key, value in (filters or {}).items():
        if value is None:
            continue
        normalized[str(key)] = str(value)
    return dict(sorted(normalized.items()))


def filters_sha256(filters: Optional[Mapping[str, Any]]) -> str:
    text = _canonical_json(normalize_filters(filters))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def encode_plan_cursor(
    created_at: datetime,
    plan_id: UUID,
    plan_version: int,
    filters: Optional[Mapping[str, Any]],
) -> str:
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise CursorError("cursor created_at must be timezone-aware")
    payload = {
        "v": CURSOR_SCHEMA_VERSION,
        "created_at": created_at.astimezone(timezone.utc).isoformat(),
        "plan_id": str(plan_id),
        "plan_version": plan_version,
        "filters_sha256": filters_sha256(filters),
    }
    raw = _canonical_json(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _strict_urlsafe_b64decode(cursor: str) -> bytes:
    """Decode a urlsafe base64 string, rejecting any non-alphabet byte.

    ``base64.urlsafe_b64decode`` is lenient — it silently strips characters it
    does not recognize, so a cursor with trailing ``!!!`` or an embedded newline
    would decode to a valid-looking prefix. Gating on the exact alphabet (and
    validating padding via ``validate=True``) makes such a cursor fail closed.
    """
    if not _URLSAFE_B64_RE.fullmatch(cursor):
        raise CursorError("cursor is not valid base64url")
    standard = cursor.translate(_URLSAFE_TO_STANDARD)
    try:
        return base64.b64decode(standard, validate=True)
    except (binascii.Error, ValueError) as error:
        raise CursorError("cursor is not valid base64url") from error


def decode_plan_cursor(
    cursor: str, filters: Optional[Mapping[str, Any]]
) -> tuple[datetime, UUID, int]:
    """Return the ``(created_at, plan_id, plan_version)`` keyset a cursor encodes.

    Every failure mode is a ``CursorError``: the endpoint maps it to a 422 so a
    stale, forged, or cross-filter cursor is a client error, never a 500 and
    never a silently-wrong page.
    """
    if not isinstance(cursor, str) or not cursor:
        raise CursorError("cursor must be a non-empty string")
    raw = _strict_urlsafe_b64decode(cursor)
    try:
        payload = json.loads(raw)
    except ValueError as error:
        raise CursorError("cursor is not valid JSON") from error
    if not isinstance(payload, Mapping):
        raise CursorError("cursor payload must be a JSON object")

    version = payload.get("v")
    # Require a genuine int (reject bool True==1 and float 1.0==1): an unsigned
    # continuity token still fails closed on a subtly-retyped version field.
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != CURSOR_SCHEMA_VERSION
    ):
        raise CursorError("cursor has an unsupported version")
    if payload.get("filters_sha256") != filters_sha256(filters):
        raise CursorError("cursor was issued for a different filter set")

    created_at_text = payload.get("created_at")
    if not isinstance(created_at_text, str):
        raise CursorError("cursor created_at must be a string")
    try:
        created_at = datetime.fromisoformat(created_at_text)
    except ValueError as error:
        raise CursorError("cursor created_at is not a valid timestamp") from error
    if created_at.tzinfo is None or created_at.utcoffset() != timedelta(0):
        raise CursorError("cursor created_at must be UTC")

    plan_id_text = payload.get("plan_id")
    if not isinstance(plan_id_text, str):
        raise CursorError("cursor plan_id must be a string")
    try:
        plan_id = UUID(plan_id_text)
    except ValueError as error:
        raise CursorError("cursor plan_id is not a valid UUID") from error

    plan_version = payload.get("plan_version")
    if isinstance(plan_version, bool) or not isinstance(plan_version, int):
        raise CursorError("cursor plan_version must be an integer")

    return created_at, plan_id, plan_version
