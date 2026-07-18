"""Opaque keyset cursor for the control-plan list projection (PR 4.4a-3).

The cursor pins the last-seen (created_at, plan_id, plan_version) AND a hash of
the active filter set, so it round-trips within one filter set but is REJECTED
across a different one (a keyset is only meaningful inside the ORDER BY that
produced it). The (plan_id, plan_version) pair is the row's TOTAL identity, so the
key is a strict total order and pagination is provably total. It is versioned and
opaque; a malformed / unknown-version / non-UTC / mismatched cursor fails closed
with a typed CursorError (the endpoint maps that to 422).
"""

import base64
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from core.control_plan_cursor import (
    CURSOR_SCHEMA_VERSION,
    CursorError,
    decode_plan_cursor,
    encode_plan_cursor,
    filters_sha256,
)

_CREATED_AT = datetime(2026, 7, 18, 9, 30, 15, 123456, tzinfo=timezone.utc)
_PLAN_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
_PLAN_VERSION = 7
_FILTERS = {"lifecycle_state": "approved_for_shadow", "requirement_version": 3}


def _forge(**overrides) -> str:
    payload = {
        "v": CURSOR_SCHEMA_VERSION,
        "created_at": _CREATED_AT.isoformat(),
        "plan_id": str(_PLAN_ID),
        "plan_version": _PLAN_VERSION,
        "filters_sha256": filters_sha256(_FILTERS),
    }
    payload.update(overrides)
    return base64.urlsafe_b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("ascii")


def test_plan_cursor_round_trips_created_at_plan_id_version_and_filters():
    cursor = encode_plan_cursor(_CREATED_AT, _PLAN_ID, _PLAN_VERSION, _FILTERS)
    # Opaque + URL-safe: base64url with no reserved characters.
    assert isinstance(cursor, str) and "/" not in cursor and "+" not in cursor
    created_at, plan_id, plan_version = decode_plan_cursor(cursor, _FILTERS)
    assert created_at == _CREATED_AT
    assert plan_id == _PLAN_ID
    assert plan_version == _PLAN_VERSION


def test_plan_cursor_round_trips_when_filter_key_order_differs():
    # The filter hash is order-independent: the same filters presented in a
    # different key order must decode the SAME cursor (query-param order is not
    # part of the client's identity).
    cursor = encode_plan_cursor(_CREATED_AT, _PLAN_ID, _PLAN_VERSION, _FILTERS)
    reordered = dict(reversed(list(_FILTERS.items())))
    assert decode_plan_cursor(cursor, reordered) == (
        _CREATED_AT,
        _PLAN_ID,
        _PLAN_VERSION,
    )


def test_plan_cursor_normalizes_absent_and_none_filters_identically():
    # An omitted filter and an explicit None must hash identically, so a page
    # with no filters accepts its own next_cursor.
    assert filters_sha256(None) == filters_sha256({})
    assert filters_sha256({"lifecycle_state": None}) == filters_sha256({})


def test_plan_cursor_rejects_reuse_across_a_different_filter_set():
    cursor = encode_plan_cursor(_CREATED_AT, _PLAN_ID, _PLAN_VERSION, _FILTERS)
    changed = {**_FILTERS, "requirement_version": 4}
    with pytest.raises(CursorError):
        decode_plan_cursor(cursor, changed)


def test_plan_cursor_rejects_unknown_version():
    with pytest.raises(CursorError):
        decode_plan_cursor(_forge(v=CURSOR_SCHEMA_VERSION + 1), _FILTERS)


def test_plan_cursor_rejects_boolean_version_masquerading_as_one():
    # In Python True == 1, so a forged {"v": true} must be rejected explicitly.
    with pytest.raises(CursorError):
        decode_plan_cursor(_forge(v=True), _FILTERS)


def test_plan_cursor_rejects_float_version_masquerading_as_one():
    # In Python 1.0 == 1, so a forged {"v": 1.0} must be rejected: the version is
    # required to be a genuine int, not merely equal to one.
    with pytest.raises(CursorError):
        decode_plan_cursor(_forge(v=1.0), _FILTERS)


def test_plan_cursor_rejects_non_utc_created_at():
    non_utc = datetime(
        2026, 7, 18, 9, 30, tzinfo=timezone(timedelta(hours=7))
    ).isoformat()
    with pytest.raises(CursorError):
        decode_plan_cursor(_forge(created_at=non_utc), _FILTERS)


def test_plan_cursor_rejects_malformed_base64_and_json():
    with pytest.raises(CursorError):
        decode_plan_cursor("!!!not base64!!!", _FILTERS)
    not_json = base64.urlsafe_b64encode(b"not json").decode("ascii")
    with pytest.raises(CursorError):
        decode_plan_cursor(not_json, _FILTERS)
    with pytest.raises(CursorError):
        decode_plan_cursor("", _FILTERS)


def test_plan_cursor_rejects_trailing_junk_after_valid_cursor():
    # urlsafe_b64decode is lenient about trailing bytes; a valid cursor with
    # appended junk must fail closed rather than decode to a valid-looking prefix.
    cursor = encode_plan_cursor(_CREATED_AT, _PLAN_ID, _PLAN_VERSION, _FILTERS)
    with pytest.raises(CursorError):
        decode_plan_cursor(cursor + "!!!", _FILTERS)


def test_plan_cursor_rejects_embedded_whitespace():
    cursor = encode_plan_cursor(_CREATED_AT, _PLAN_ID, _PLAN_VERSION, _FILTERS)
    with pytest.raises(CursorError):
        decode_plan_cursor(cursor + "\n", _FILTERS)
    with pytest.raises(CursorError):
        decode_plan_cursor("  " + cursor, _FILTERS)


def test_plan_cursor_rejects_non_uuid_plan_id():
    with pytest.raises(CursorError):
        decode_plan_cursor(_forge(plan_id="not-a-uuid"), _FILTERS)


def test_plan_cursor_rejects_non_integer_plan_version():
    # A forged non-integer plan_version (float or string) fails closed rather than
    # collapsing the total-order tie-break.
    with pytest.raises(CursorError):
        decode_plan_cursor(_forge(plan_version=1.5), _FILTERS)
    with pytest.raises(CursorError):
        decode_plan_cursor(_forge(plan_version="1"), _FILTERS)
    with pytest.raises(CursorError):
        decode_plan_cursor(_forge(plan_version=True), _FILTERS)


def test_plan_cursor_encode_requires_timezone_aware_created_at():
    with pytest.raises(CursorError):
        encode_plan_cursor(
            datetime(2026, 7, 18, 9, 30), _PLAN_ID, _PLAN_VERSION, _FILTERS
        )
