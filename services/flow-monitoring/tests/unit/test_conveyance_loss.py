"""
Unit tests for core.conveyance_loss — Tier-1 seepage + operational loss model (B5),
multi-segment reach geometry (Wave 2.1a, WAVE_2-4_PLAN §1.5 amendment #2).
Pure/stdlib; run in isolation:
    pytest --noconftest tests/unit/test_conveyance_loss.py

Oracles are hand-computed from raw formulas (not from the functions under test):
    wetted_perimeter P = b + 2*y*sqrt(1 + m^2)     [trapezoid, y = operating depth]
    segment seepage    = rate * P * length_m
    reach seepage      = sum over ordered segments
    uplift             = reach seepage + (sum of segment op_fracs) * throughflow

A reach is an ORDERED list of surveyed segments: the pre-2.1a indexer silently kept
only the LAST row for a duplicated (from, to) edge — exactly what the 99-subsegment
Characteristics survey would have triggered.
"""
import json
import math
from pathlib import Path

import pytest

from core.config_loader import ConfigError
from core.conveyance_loss import (
    SEEPAGE_RATE_BY_LINING,
    make_reach_loss,
    parse_chainage_m,
    reach_loss_uplift,
    reach_seepage_m3s,
    sections_by_edge_from_geometry,
    seepage_rate_for_lining,
    wetted_perimeter,
)
from core.demand_aggregation import required_flow_per_reach

GEOMETRY_CFG = Path(__file__).resolve().parents[2] / "src" / "config" / "canal_geometry.json"

# A synthetic trapezoidal reach used across several tests (all values explained).
CS = {"bottom_width_m": 10.0, "depth_m": 2.0, "side_slope": 1.5}
Y = 0.7 * CS["depth_m"]  # operating depth = 0.7 * design depth = 1.4 m
P = CS["bottom_width_m"] + 2 * Y * math.sqrt(1 + CS["side_slope"] ** 2)  # ~15.0478 m

# A second, narrower cross-section for multi-segment reaches.
CS2 = {"bottom_width_m": 4.0, "depth_m": 1.5, "side_slope": 1.0}
Y2 = 0.7 * CS2["depth_m"]
P2 = CS2["bottom_width_m"] + 2 * Y2 * math.sqrt(1 + CS2["side_slope"] ** 2)


def _segment(rate, length=1000.0, op=0.05, cs=CS, **extra):
    seg = {"length_m": length, "cross_section": cs, "seepage_rate_m_s": rate,
           "operational_loss_frac": op}
    seg.update(extra)
    return seg


def _reach(rate, length=1000.0, op=0.05, cs=CS):
    """A single-segment reach — the pre-2.1a shape wrapped in the new list contract."""
    return [_segment(rate, length, op, cs)]


class TestSeepageRateForLining:
    def test_known_linings(self):
        # Aged/deteriorated ~50-yr field values (Turkey field studies); NOT the new-concrete
        # USBR standard (2.4e-7). See docs/remediation/SEEPAGE_CALIBRATION.md.
        assert seepage_rate_for_lining("concrete") == 1.0e-5
        assert seepage_rate_for_lining("earth") == 2.0e-5

    def test_unknown_and_missing_default_to_unknown_rate(self):
        assert seepage_rate_for_lining("steel") == SEEPAGE_RATE_BY_LINING["unknown"]
        assert seepage_rate_for_lining(None) == SEEPAGE_RATE_BY_LINING["unknown"]

    def test_earth_leaks_more_than_concrete(self):
        assert seepage_rate_for_lining("earth") > seepage_rate_for_lining("concrete")


class TestWettedPerimeter:
    def test_trapezoid_matches_hand_computed(self):
        assert wetted_perimeter(CS, Y) == pytest.approx(15.047771, abs=1e-5)

    def test_rectangular_channel_has_no_slope_term(self):
        # side_slope 0 -> P = bottom width + 2*depth (vertical walls).
        assert wetted_perimeter({"bottom_width_m": 8.0, "side_slope": 0.0}, 2.0) == pytest.approx(12.0)


class TestParseChainage:
    def test_survey_marker_to_metres(self):
        assert parse_chainage_m("0+000") == 0.0
        assert parse_chainage_m("0+300") == 300.0
        assert parse_chainage_m("11+800") == 11800.0

    def test_decimal_metres_part(self):
        assert parse_chainage_m("2+075.5") == 2075.5

    def test_unparseable_and_absent_are_none(self):
        assert parse_chainage_m("km 3") is None
        assert parse_chainage_m("") is None
        assert parse_chainage_m(None) is None
        assert parse_chainage_m(1200) is None


class TestReachSeepage:
    def test_single_segment_matches_rate_times_perimeter_times_length(self):
        expected = 3.0e-7 * P * 1000.0  # ~0.0045143 m3/s
        assert reach_seepage_m3s(_reach(3.0e-7)) == pytest.approx(expected, rel=1e-9)

    def test_earth_reach_seeps_more_than_concrete_same_geometry(self):
        assert reach_seepage_m3s(_reach(1.5e-6)) > reach_seepage_m3s(_reach(3.0e-7))

    def test_scales_linearly_with_length(self):
        assert reach_seepage_m3s(_reach(3.0e-7, length=2000)) == pytest.approx(
            2 * reach_seepage_m3s(_reach(3.0e-7, length=1000)), rel=1e-9
        )

    def test_multi_segment_reach_sums_per_segment_seepage(self):
        # 1000 m of CS at concrete + 500 m of CS2 at earth: each segment uses its
        # OWN perimeter and rate — the old single-record model could only hold one.
        segments = [
            _segment(1.0e-5, length=1000.0, op=0.0, cs=CS),
            _segment(2.0e-5, length=500.0, op=0.0, cs=CS2),
        ]
        expected = 1.0e-5 * P * 1000.0 + 2.0e-5 * P2 * 500.0
        assert reach_seepage_m3s(segments) == pytest.approx(expected, rel=1e-9)


class TestReachLossUplift:
    def test_is_seepage_plus_operational_fraction_of_throughflow(self):
        seep = 3.0e-7 * P * 1000.0
        assert reach_loss_uplift(_reach(3.0e-7, op=0.05), 8.0) == pytest.approx(
            seep + 0.05 * 8.0, rel=1e-9
        )

    def test_operational_term_scales_with_throughflow(self):
        reach = _reach(3.0e-7, op=0.05)
        assert reach_loss_uplift(reach, 20.0) - reach_loss_uplift(reach, 10.0) == pytest.approx(
            0.05 * 10.0, rel=1e-9
        )

    def test_zero_operational_fraction_leaves_seepage_only(self):
        assert reach_loss_uplift(_reach(3.0e-7, op=0.0), 8.0) == pytest.approx(
            reach_seepage_m3s(_reach(3.0e-7)), rel=1e-9
        )

    def test_multi_segment_operational_fractions_sum(self):
        segments = [
            _segment(1.0e-5, length=1000.0, op=0.02, cs=CS),
            _segment(1.0e-5, length=500.0, op=0.03, cs=CS),
        ]
        seep = 1.0e-5 * P * 1000.0 + 1.0e-5 * P * 500.0
        assert reach_loss_uplift(segments, 10.0) == pytest.approx(
            seep + (0.02 + 0.03) * 10.0, rel=1e-9
        )

    def test_default_op_fraction_applies_once_per_reach_not_per_segment(self, monkeypatch):
        # QCHECK 2.1a HIGH: a 99-subsegment reach with no explicit op fractions must
        # charge the reach default ONCE, not 99x. (The default is currently 0.0 — this
        # locks the semantics for any future non-zero default.)
        import core.conveyance_loss as cl

        monkeypatch.setattr(cl, "DEFAULT_OPERATIONAL_LOSS_FRAC", 0.05)
        segments = [
            {"length_m": 1000.0, "cross_section": CS, "seepage_rate_m_s": 1.0e-5,
             "operational_loss_frac": None},
            {"length_m": 500.0, "cross_section": CS, "seepage_rate_m_s": 1.0e-5,
             "operational_loss_frac": None},
        ]
        seep = 1.0e-5 * P * 1000.0 + 1.0e-5 * P * 500.0
        assert reach_loss_uplift(segments, 10.0) == pytest.approx(
            seep + 0.05 * 10.0, rel=1e-9
        )

    def test_explicit_fractions_win_over_the_reach_default(self, monkeypatch):
        import core.conveyance_loss as cl

        monkeypatch.setattr(cl, "DEFAULT_OPERATIONAL_LOSS_FRAC", 0.05)
        segments = [
            {"length_m": 1000.0, "cross_section": CS, "seepage_rate_m_s": 1.0e-5,
             "operational_loss_frac": 0.01},
            {"length_m": 500.0, "cross_section": CS, "seepage_rate_m_s": 1.0e-5,
             "operational_loss_frac": None},
        ]
        seep = 1.0e-5 * P * 1000.0 + 1.0e-5 * P * 500.0
        # One explicit fraction: the reach charges exactly the explicit sum (0.01),
        # never explicit + default.
        assert reach_loss_uplift(segments, 10.0) == pytest.approx(
            seep + 0.01 * 10.0, rel=1e-9
        )


class TestGeometryFileConsistency:
    def test_summary_matches_the_actual_section_list(self):
        # The summary block previously claimed 46 sections (wrong per-zone counts too)
        # while the list held 37 — code must never trust a hand-written summary, and
        # the file must not lie to human readers (Wave 0.5).
        geometry = json.loads(GEOMETRY_CFG.read_text())
        sections = geometry["canal_sections"]
        summary = geometry["summary"]
        assert summary["total_sections"] == len(sections)
        by_zone = {}
        for s in sections:
            by_zone[f"zone_{s['zone']}"] = by_zone.get(f"zone_{s['zone']}", 0) + 1
        assert summary["by_zone"] == by_zone

    def test_geometry_is_strict_json(self):
        def _reject(constant):
            raise AssertionError(f"non-strict JSON constant {constant!r} in canal_geometry.json")

        json.loads(GEOMETRY_CFG.read_text(), parse_constant=_reject)


def _survey_row(from_node, to_node, from_km, to_km, length, lining="concrete", q_max=None):
    hp = {"lining_type": lining}
    if q_max is not None:
        hp["q_max"] = q_max
    return {
        "from_node": from_node,
        "to_node": to_node,
        "from_km": from_km,
        "to_km": to_km,
        "geometry": {
            "length_m": length,
            "cross_section": dict(CS),
            "hydraulic_params": hp,
        },
    }


class TestSectionsByEdgeFromGeometry:
    def test_parses_all_survey_sections_keyed_by_normalized_edge(self):
        geo = json.loads(GEOMETRY_CFG.read_text())
        sections = sections_by_edge_from_geometry(geo)
        assert len(sections) == 42  # 2.1b: every serial reach carries survey rows
        # First LMC reach runs M(0,0) -> M(0,1) over 0+000-0+300: the flume
        # [0,170] has no cross-section survey, so the reach carries ONE emitted
        # segment — the [170,300] piece of the 0+170-1+620 concrete row.
        [seg] = sections[("M(0,0)", "M(0,1)")]
        assert seg["length_m"] == 130
        assert seg["seepage_rate_m_s"] == 1.0e-5  # enriched from lining_type=concrete (aged)
        assert "cross_section" in seg
        assert seg["from_km_m"] == 170.0 and seg["to_km_m"] == 300.0

    def test_duplicate_edge_rows_become_ordered_segments_not_overwrites(self):
        # Input deliberately OUT of chainage order; pre-2.1a this dict-overwrote to
        # one row and lost the other silently.
        geo = {"canal_sections": [
            _survey_row("M(0,1)", "M(0,2)", "1+000", "1+500", 500, lining="earth"),
            _survey_row("M(0,1)", "M(0,2)", "0+000", "1+000", 1000, lining="concrete"),
        ]}
        sections = sections_by_edge_from_geometry(geo)
        segments = sections[("M(0,1)", "M(0,2)")]
        assert [seg["from_km_m"] for seg in segments] == [0.0, 1000.0]
        assert [seg["seepage_rate_m_s"] for seg in segments] == [1.0e-5, 2.0e-5]
        assert reach_seepage_m3s(segments) == pytest.approx(
            1.0e-5 * P * 1000.0 + 2.0e-5 * P * 500.0, rel=1e-9
        )

    def test_overlapping_segments_fail_closed(self):
        geo = {"canal_sections": [
            _survey_row("M(0,1)", "M(0,2)", "0+000", "1+000", 1000),
            _survey_row("M(0,1)", "M(0,2)", "0+800", "1+500", 700),
        ]}
        with pytest.raises(ConfigError, match="overlap"):
            sections_by_edge_from_geometry(geo)

    def test_multiple_rows_without_chainage_fail_closed(self):
        # Two rows for one edge with no parseable chainage are un-orderable — the
        # old behavior (keep the last) was a silent data loss.
        geo = {"canal_sections": [
            _survey_row("M(0,1)", "M(0,2)", None, None, 1000),
            _survey_row("M(0,1)", "M(0,2)", None, None, 500),
        ]}
        with pytest.raises(ConfigError, match="chainage"):
            sections_by_edge_from_geometry(geo)

    def test_inverted_segment_span_fails_closed(self):
        geo = {"canal_sections": [
            _survey_row("M(0,1)", "M(0,2)", "1+000", "0+500", 500),
            _survey_row("M(0,1)", "M(0,2)", "1+500", "2+000", 500),
        ]}
        with pytest.raises(ConfigError, match="span"):
            sections_by_edge_from_geometry(geo)

    def test_single_row_without_chainage_is_fine(self):
        geo = {"canal_sections": [_survey_row("M(0,1)", "M(0,2)", None, None, 1000)]}
        [seg] = sections_by_edge_from_geometry(geo)[("M(0,1)", "M(0,2)")]
        assert seg["from_km_m"] is None

    def test_single_row_inverted_span_fails_closed(self):
        # QCHECK 2.1a MED: span sanity must not be skipped on the single-row fast path.
        geo = {"canal_sections": [_survey_row("M(0,1)", "M(0,2)", "1+000", "0+500", 500)]}
        with pytest.raises(ConfigError, match="span"):
            sections_by_edge_from_geometry(geo)

    def test_chainage_gaps_are_measured_not_silently_accepted(self):
        # QCHECK 2.1a MED: partial surveys are LEGAL (6 gates lack lengths) but must be
        # measurable, so coverage consumers (2.1b report / 2.8a observability) can
        # surface incomplete reaches instead of understating seepage silently.
        from core.conveyance_loss import reach_chainage_gap_m

        geo = {"canal_sections": [
            _survey_row("M(0,1)", "M(0,2)", "0+000", "1+000", 1000),
            _survey_row("M(0,1)", "M(0,2)", "1+400", "2+000", 600),
        ]}
        segments = sections_by_edge_from_geometry(geo)[("M(0,1)", "M(0,2)")]
        assert reach_chainage_gap_m(segments) == pytest.approx(400.0)

    def test_touching_spans_have_zero_gap(self):
        from core.conveyance_loss import reach_chainage_gap_m

        geo = {"canal_sections": [
            _survey_row("M(0,1)", "M(0,2)", "0+000", "1+000", 1000),
            _survey_row("M(0,1)", "M(0,2)", "1+000", "1+500", 500),
        ]}
        segments = sections_by_edge_from_geometry(geo)[("M(0,1)", "M(0,2)")]
        assert reach_chainage_gap_m(segments) == 0.0

    def test_gap_is_none_when_chainage_is_unknown(self):
        from core.conveyance_loss import reach_chainage_gap_m

        geo = {"canal_sections": [_survey_row("M(0,1)", "M(0,2)", None, None, 1000)]}
        segments = sections_by_edge_from_geometry(geo)[("M(0,1)", "M(0,2)")]
        assert reach_chainage_gap_m(segments) is None

    def test_reach_span_exposes_head_and_tail_gaps(self):
        # QCHECK 2.1b HIGH: all five real partial reaches have their gaps at the
        # reach HEAD or TAIL (flume 0-170 on M(0,0)->M(0,1); trailing 30-1200 m
        # elsewhere) — between-segment measurement alone reports {} for all of
        # them. With the reach span, boundary gaps are measured too.
        from core.conveyance_loss import reach_chainage_gap_m

        geo = {"canal_sections": [
            _survey_row("M(0,1)", "M(0,2)", "0+170", "0+300", 130),
        ]}
        segments = sections_by_edge_from_geometry(geo)[("M(0,1)", "M(0,2)")]
        assert reach_chainage_gap_m(segments) == 0.0  # no interior gap
        assert reach_chainage_gap_m(segments, span=(0.0, 300.0)) == pytest.approx(170.0)
        assert reach_chainage_gap_m(segments, span=(170.0, 500.0)) == pytest.approx(200.0)

    def test_reach_span_adds_boundary_to_interior_gaps(self):
        from core.conveyance_loss import reach_chainage_gap_m

        geo = {"canal_sections": [
            _survey_row("M(0,1)", "M(0,2)", "0+100", "0+400", 300),
            _survey_row("M(0,1)", "M(0,2)", "0+600", "0+900", 300),
        ]}
        segments = sections_by_edge_from_geometry(geo)[("M(0,1)", "M(0,2)")]
        assert reach_chainage_gap_m(segments) == pytest.approx(200.0)
        assert reach_chainage_gap_m(segments, span=(0.0, 1000.0)) == pytest.approx(400.0)

    def test_reach_spans_from_geometry_keys_by_normalized_edge(self):
        from core.conveyance_loss import reach_spans_from_geometry

        geo = {"reaches": [
            {"from_node": "M (0,3; 1,0)", "to_node": "M (0,3; 1,1)",
             "from_km": "0+000", "to_km": "5+750"},
        ]}
        spans = reach_spans_from_geometry(geo)
        assert spans == {("M(0,3;1,0)", "M(0,3;1,1)"): (0.0, 5750.0)}

    def test_reach_spans_absent_block_is_empty(self):
        from core.conveyance_loss import reach_spans_from_geometry

        assert reach_spans_from_geometry({"canal_sections": []}) == {}

    def test_segment_q_max_is_retained_when_valid(self):
        geo = {"canal_sections": [
            _survey_row("M(0,1)", "M(0,2)", "0+000", "1+000", 1000, q_max=6.5),
            _survey_row("M(0,1)", "M(0,2)", "1+000", "1+500", 500, q_max="bad"),
        ]}
        segments = sections_by_edge_from_geometry(geo)[("M(0,1)", "M(0,2)")]
        assert segments[0]["q_max"] == 6.5
        assert segments[1]["q_max"] is None


class TestMakeReachLoss:
    def _sections(self):
        return {("M(0,0)", "M(0,1)"): _reach(3.0e-7)}

    def test_covered_edge_returns_uplift(self):
        loss = make_reach_loss(self._sections())
        assert loss("M(0,0)", "M(0,1)", 8.0) == pytest.approx(
            reach_loss_uplift(_reach(3.0e-7), 8.0), rel=1e-9
        )

    def test_matches_by_normalized_id_despite_spacing(self):
        loss = make_reach_loss(self._sections())
        assert loss("M(0,0)", "M (0,1)", 8.0) > 0  # spaced id still joins

    def test_uncovered_edge_returns_zero(self):
        loss = make_reach_loss(self._sections())
        assert loss("M(0,1)", "M(0,2)", 8.0) == 0.0

    def test_source_edge_returns_zero(self):
        # "S" is not a gate id and no reach has geometry -> no loss, no crash.
        assert make_reach_loss(self._sections())("S", "M(0,0)", 8.0) == 0.0


class TestDryReachGating:
    # D1 (PROGRAM_REVIEW_2026-07-09 §2.0): seepage is charged only on reaches that carry
    # flow for THIS plan; `always_wet` keeps named trunk reaches charged; the legacy
    # charge-everything behavior stays behind an explicit flag.
    EDGE = ("M(0,1)", "M(0,2)")
    SECTIONS = {EDGE: _reach(1.0e-5, op=0.0)}
    SEEP = reach_seepage_m3s(_reach(1.0e-5, op=0.0))

    def test_dry_reach_takes_no_loss_by_default(self):
        rl = make_reach_loss(self.SECTIONS)
        assert rl("M(0,1)", "M(0,2)", 0.0) == 0.0

    def test_flowing_reach_is_still_charged(self):
        rl = make_reach_loss(self.SECTIONS)
        assert rl("M(0,1)", "M(0,2)", 1.0) == pytest.approx(self.SEEP)

    def test_charge_dry_reaches_restores_fixed_depth_seepage(self):
        rl = make_reach_loss(self.SECTIONS, charge_dry_reaches=True)
        assert rl("M(0,1)", "M(0,2)", 0.0) == pytest.approx(self.SEEP)

    def test_always_wet_reach_is_charged_when_dry(self):
        rl = make_reach_loss(self.SECTIONS, always_wet=frozenset({self.EDGE}))
        assert rl("M(0,1)", "M(0,2)", 0.0) == pytest.approx(self.SEEP)

    def test_always_wet_matches_by_normalized_id_despite_spacing(self):
        rl = make_reach_loss(self.SECTIONS, always_wet=frozenset({self.EDGE}))
        assert rl("M (0,1)", "M (0, 2)", 0.0) == pytest.approx(self.SEEP)

    def test_zero_demand_aggregation_charges_nothing(self):
        edges = [("S", "M(0,1)"), ("M(0,1)", "M(0,2)")]
        sections = {("S", "M(0,1)"): _reach(1.0e-5, op=0.0), self.EDGE: _reach(1.0e-5, op=0.0)}
        flow = required_flow_per_reach(edges, {}, reach_loss=make_reach_loss(sections))
        assert all(q == 0.0 for q in flow.values())

    # Branched fixture: S -> M(0,0) -> M(0,1) -> {M(0,2) wet, M(0,1;1,0) dry sibling}.
    BRANCH_EDGES = [("S", "M(0,0)"), ("M(0,0)", "M(0,1)"),
                    ("M(0,1)", "M(0,2)"), ("M(0,1)", "M(0,1;1,0)")]
    WET = ("M(0,1)", "M(0,2)")

    def _branch_sections(self, op=0.0):
        return {("M(0,0)", "M(0,1)"): _reach(1.0e-5, op=op),
                ("M(0,1)", "M(0,2)"): _reach(1.0e-5, op=op),
                ("M(0,1)", "M(0,1;1,0)"): _reach(1.0e-5, op=op)}

    def test_always_wet_charges_ancestors_but_not_the_dry_sibling(self):
        rl = make_reach_loss(self._branch_sections(), always_wet=frozenset({self.WET}))
        flow = required_flow_per_reach(self.BRANCH_EDGES, {}, reach_loss=rl)
        assert flow[self.WET] == pytest.approx(self.SEEP)          # its own seepage
        assert flow[("M(0,1)", "M(0,1;1,0)")] == 0.0               # dry sibling untouched
        # the ancestor now carries the wet reach's seepage AND, being in service, its own.
        assert flow[("M(0,0)", "M(0,1)")] == pytest.approx(2 * self.SEEP)
        assert flow[("S", "M(0,0)")] == pytest.approx(2 * self.SEEP)  # no geometry on S edge

    def test_always_wet_with_operational_fraction_charges_only_flowing_reaches(self):
        rl = make_reach_loss(self._branch_sections(op=0.05), always_wet=frozenset({self.WET}))
        flow = required_flow_per_reach(self.BRANCH_EDGES, {}, reach_loss=rl)
        assert flow[self.WET] == pytest.approx(self.SEEP)  # op term is 0.05 * 0 on the wet reach
        # ancestor: through=SEEP, uplift = SEEP + 0.05*SEEP -> total 2.05*SEEP.
        assert flow[("M(0,0)", "M(0,1)")] == pytest.approx(2.05 * self.SEEP)
        assert flow[("M(0,1)", "M(0,1;1,0)")] == 0.0


class TestAggregationWithLoss:
    # Serial chain S -> M(0,0) -> M(0,1) -> M(0,2); geometry on both M-reaches.
    EDGES = [("S", "M(0,0)"), ("M(0,0)", "M(0,1)"), ("M(0,1)", "M(0,2)")]

    def test_seepage_only_head_equals_demand_plus_path_seepage(self):
        # operational_loss_frac = 0 -> seepage is constant per reach, no compounding:
        # head = demand + seepage(M(0,0)->M(0,1)) + seepage(M(0,1)->M(0,2)).
        sections = {
            ("M(0,0)", "M(0,1)"): _reach(3.0e-7, op=0.0),
            ("M(0,1)", "M(0,2)"): _reach(3.0e-7, op=0.0),
        }
        flow = required_flow_per_reach(self.EDGES, {"M(0,2)": 10.0},
                                       reach_loss=make_reach_loss(sections))
        seep = 3.0e-7 * P * 1000.0
        assert flow[("S", "M(0,0)")] == pytest.approx(10.0 + 2 * seep, rel=1e-9)

    def test_losses_lift_head_above_the_lossless_head(self):
        sections = {("M(0,0)", "M(0,1)"): _reach(3.0e-7), ("M(0,1)", "M(0,2)"): _reach(3.0e-7)}
        demand = {"M(0,2)": 10.0}
        lossy = required_flow_per_reach(self.EDGES, demand, reach_loss=make_reach_loss(sections))
        lossless = required_flow_per_reach(self.EDGES, demand)
        assert lossy[("S", "M(0,0)")] > lossless[("S", "M(0,0)")]

    def test_multi_segment_reach_contributes_its_summed_seepage_to_the_head(self):
        # The M(0,1)->M(0,2) reach split into two surveyed subsegments must charge
        # the head EXACTLY what the two segments sum to — not just the last row.
        sections = {
            ("M(0,0)", "M(0,1)"): _reach(3.0e-7, op=0.0),
            ("M(0,1)", "M(0,2)"): [
                _segment(1.0e-5, length=1000.0, op=0.0, cs=CS),
                _segment(2.0e-5, length=500.0, op=0.0, cs=CS2),
            ],
        }
        flow = required_flow_per_reach(self.EDGES, {"M(0,2)": 10.0},
                                       reach_loss=make_reach_loss(sections))
        expected_seep = (
            3.0e-7 * P * 1000.0            # single-segment reach
            + 1.0e-5 * P * 1000.0          # subsegment 1
            + 2.0e-5 * P2 * 500.0          # subsegment 2
        )
        assert flow[("S", "M(0,0)")] == pytest.approx(10.0 + expected_seep, rel=1e-9)
