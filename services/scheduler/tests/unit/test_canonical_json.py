"""RFC-8785 (JCS) canonicalizer — cross-language conformance against the 6.1a golden.

The scheduler (PR 4.3c) is the Python producer/verifier the 6.1a golden vector was
built for: it MUST reproduce the exact canonical JSON + capability_hash the
TypeScript `canonicalize` reference lib emits, or a cross-language capability_hash
would diverge and every SCADA validation (6.2) would reject.
"""

import hashlib
import json
from pathlib import Path

import pytest

from core.canonical_json import canonicalize, sha256_hex

_GOLDEN_PATH = (
    Path(__file__).resolve().parents[4]
    / "contracts"
    / "machine-boundary"
    / "golden"
    / "device-capability-hash.golden.json"
)
_GOLDEN = json.loads(_GOLDEN_PATH.read_text("utf-8"))


@pytest.mark.parametrize(
    "case",
    _GOLDEN["number_canonicalization_vectors"]["cases"],
    ids=[
        json.dumps(c["raw"]) for c in _GOLDEN["number_canonicalization_vectors"]["cases"]
    ],
)
def test_number_vectors_match_the_golden(case):
    # Each raw JSON number MUST canonicalize to the golden's `canonical` string —
    # the same ES6/RFC-8785 form the TS lib emits (a naive json.dumps diverges).
    assert canonicalize({"v": case["raw"]}) == f'{{"v":{case["canonical"]}}}'


def test_reproduces_the_golden_canonical_json_byte_for_byte():
    assert canonicalize(_GOLDEN["snapshot"]) == _GOLDEN["canonical_json"]


def test_reproduces_the_golden_capability_hash():
    canonical = canonicalize(_GOLDEN["snapshot"])
    digest = sha256_hex(_GOLDEN["domain_prefix"] + canonical)
    assert digest == _GOLDEN["capability_hash"]


def test_is_key_order_independent():
    # Canonicalization sorts keys, so insertion order cannot change the output.
    reordered = {
        "capabilities": _GOLDEN["snapshot"]["capabilities"],
        "schema_version": _GOLDEN["snapshot"]["schema_version"],
        "capability_release_id": _GOLDEN["snapshot"]["capability_release_id"],
    }
    assert canonicalize(reordered) == _GOLDEN["canonical_json"]


def test_sorts_nested_object_keys_and_preserves_array_order():
    value = {"b": 1, "a": [{"y": 2, "x": 1}, {"n": 4, "m": 3}]}
    assert canonicalize(value) == '{"a":[{"x":1,"y":2},{"m":3,"n":4}],"b":1}'


def test_serializes_scalars_and_escapes_strings():
    assert canonicalize(True) == "true"
    assert canonicalize(False) == "false"
    assert canonicalize(None) == "null"
    assert canonicalize("a\tb\"c") == '"a\\tb\\"c"'


def test_integers_never_grow_a_decimal_and_negative_zero_collapses():
    assert canonicalize(2.0) == "2"
    assert canonicalize(-0.0) == "0"
    assert canonicalize(1000) == "1000"


def test_rejects_a_non_finite_number():
    with pytest.raises(ValueError):
        canonicalize(float("inf"))
    with pytest.raises(ValueError):
        canonicalize(float("nan"))


def test_rejects_an_unserialisable_type():
    with pytest.raises(ValueError):
        canonicalize({"k": object()})


def test_sha256_hex_matches_hashlib():
    assert sha256_hex("munbon") == hashlib.sha256(b"munbon").hexdigest()
