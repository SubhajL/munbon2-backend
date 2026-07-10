"""
Unit tests for core.node_id — the canonical home of the M(i,j;...) gate-id grammar
(Wave 1.2, PROGRAM_REVIEW_2026-07-09 §2.2). Pure/stdlib; run in isolation:
    PYTHONPATH=src pytest --noconftest -o addopts="" tests/unit/test_node_id.py
"""
import pytest

from core.node_id import (
    NodeIdError,
    format_gate_tuples,
    normalize_gate_id,
    normalize_node_id,
    parse_gate_id,
)


class TestParseGateId:
    @pytest.mark.parametrize(
        "alias",
        ["M(0,3;1,0)", "M (0,3; 1,0)", "M( 0 , 3 ; 1 , 0 )", "M\t(0,3;\n1,0)"],
    )
    def test_accepts_any_spacing(self, alias):
        assert parse_gate_id(alias) == [(0, 3), (1, 0)]

    @pytest.mark.parametrize(
        "bad",
        ["M(0,3", "N(0,3)", "M()", "M(0)", "M(0,3;)", "M(0,-1)", "M(00,3)", "M(0,03)", ""],
    )
    def test_rejects_grammar_violations(self, bad):
        with pytest.raises(NodeIdError):
            parse_gate_id(bad)


class TestFormatAndNormalize:
    def test_format_emits_compact_canonical(self):
        assert format_gate_tuples([(0, 1), (1, 0)]) == "M(0,1;1,0)"

    def test_normalize_strips_all_spacing(self):
        assert normalize_gate_id("M (0,12; 1,0)") == "M(0,12;1,0)"

    def test_normalize_is_idempotent(self):
        once = normalize_gate_id("M (0,1; 1,1; 1,2)")
        assert normalize_gate_id(once) == once


class TestNormalizeNodeId:
    def test_canonicalizes_gate_ids(self):
        assert normalize_node_id("M (0,3; 1,0)") == "M(0,3;1,0)"

    @pytest.mark.parametrize("passthrough", ["S", "Zone2", ""])
    def test_passes_non_gate_ids_through_unchanged(self, passthrough):
        # Joins downstream reject unknown ids by membership; the normalizer must not
        # invent or mangle non-gate ids (the source "S" above all).
        assert normalize_node_id(passthrough) == passthrough
