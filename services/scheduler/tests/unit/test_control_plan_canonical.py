"""Canonical serialization and content-hash identity for control-plan drafts."""

import json
import math

import pytest

from core.control_plan import (
    DRAFT_HASH_PREFIX,
    INPUT_HASH_PREFIX,
    canonical_json_text,
    control_plan_draft_hash,
    control_plan_input_hash,
)


class TestCanonicalJsonText:
    def test_sorts_keys_and_uses_compact_separators(self):
        text = canonical_json_text({"b": 1, "a": {"d": 2, "c": 3}})
        assert text == '{"a":{"c":3,"d":2},"b":1}'

    def test_rejects_nan_and_infinity(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with pytest.raises(ValueError):
                canonical_json_text({"value": value})

    def test_negative_zero_is_preserved_distinct_from_zero(self):
        negative = canonical_json_text({"value": -0.0})
        positive = canonical_json_text({"value": 0.0})
        assert negative != positive
        assert math.copysign(1.0, json.loads(negative)["value"]) == -1.0

    def test_unicode_is_not_ascii_escaped(self):
        assert canonical_json_text({"name": "อ่างเก็บน้ำ"}) == '{"name":"อ่างเก็บน้ำ"}'

    def test_rejects_non_string_keys(self):
        with pytest.raises(TypeError):
            canonical_json_text({1: "a"})


class TestContentHashes:
    def test_input_hash_is_sha256_hex_with_domain_prefix(self):
        document = {"identity_version": 1, "request": {"zones": [1, 2]}}
        digest = control_plan_input_hash(document)
        assert len(digest) == 64
        assert digest == control_plan_input_hash(dict(document))
        import hashlib

        expected = hashlib.sha256(
            (INPUT_HASH_PREFIX + canonical_json_text(document)).encode("utf-8")
        ).hexdigest()
        assert digest == expected

    def test_input_and_draft_hash_domains_are_disjoint(self):
        document = {"identity_version": 1}
        assert control_plan_input_hash(document) != control_plan_draft_hash(document)
        assert INPUT_HASH_PREFIX != DRAFT_HASH_PREFIX

    def test_key_order_does_not_change_hash(self):
        left = control_plan_input_hash({"a": 1, "b": [{"y": 2, "x": 3}]})
        right = control_plan_input_hash({"b": [{"x": 3, "y": 2}], "a": 1})
        assert left == right

    def test_list_order_changes_hash(self):
        left = control_plan_input_hash({"zones": [1, 2]})
        right = control_plan_input_hash({"zones": [2, 1]})
        assert left != right

    def test_value_change_changes_hash(self):
        left = control_plan_input_hash({"required_volume_m3": 1200.0})
        right = control_plan_input_hash({"required_volume_m3": 1200.0000001})
        assert left != right

    def test_negative_zero_changes_hash(self):
        left = control_plan_input_hash({"flow_m3s": 0.0})
        right = control_plan_input_hash({"flow_m3s": -0.0})
        assert left != right
