"""
Wave 2.1b — strict SCADA workbook generator (scripts/build_scada_config.py).

The generator replaces scripts/excel_to_canal_sections.py (whose Sheet1
`ระยะทาง (เมตร)` column actually holds KILOMETRES — the 1000x length bug) with a
fail-closed pipeline: Sheet1 gate positions (per-gate `km`) cut the
Characteristics survey rows (canal + chainage spans, true metres) into
gate-to-gate edge segments in the 2.1a multi-segment geometry model, plus a
59-edge coverage report. Every artifact is versioned with the workbook SHA-256,
and the committed artifacts are locked to regeneration (no hand-edit drift).

Semantics locked here (documented in the generator):
- Gate position authority is Sheet1's `km` column (the `Km. -> Km.` span text
  disagrees on 4L-38R-LMC and several canal tails; `km` is the column the
  ระยะทาง deltas are consistent with).
- Segment q_max is the Characteristics design discharge `Qd` (complete on every
  hydraulic row); `Qmax (จากแผนรอบเวรส่งน้ำ)` is a rotation-plan operational
  value and is patchy (absent for the whole RMC group).
- side_slope is DERIVED from the design flow area: z = (A/D - B)/D. The old
  file's 0.06 was the `t` column — the 6 cm concrete lining THICKNESS misread
  as a slope. The derivation yields 1.5 on all 99 survey rows.
- Survey rows that cross a gate position are split at the gate; chainage
  arithmetic only, lengths conserved (every row's length equals its chainage
  delta — validated, fail-closed).
- Rows that cannot be emitted (the Flume row has no cross-section; the 7R tail
  lies beyond the last gate) are REPORTED, never defaulted. Sill/control
  structures are RID-gated and never emitted.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from core.config_loader import (
    load_canal_geometry_config,
    load_network_config,
)
from core.conveyance_loss import parse_chainage_m, sections_by_edge_from_geometry
from core.network_topology import edges_from_names

SERVICE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = SERVICE_ROOT.parents[1]
WORKBOOK = REPO_ROOT / "SCADA Section Detailed Information 2025-08-23 V1.0 SL.xlsx"
CONFIG_DIR = SERVICE_ROOT / "src" / "config"

_SPEC = importlib.util.spec_from_file_location(
    "build_scada_config", SERVICE_ROOT / "scripts" / "build_scada_config.py"
)
bsc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bsc)


class TestParseKmMarker:
    @pytest.mark.parametrize("text,metres", [
        ("0+000", 0.0), ("0+300", 300.0), ("6+880", 6880.0),
        ("39+050", 39050.0), ("1+620.5", 1620.5),
    ])
    def test_parses_km_plus_metres(self, text, metres):
        assert bsc.parse_km_marker(text) == metres

    @pytest.mark.parametrize("bad", [None, "", "abc", "6-880", "6+", "+880", 12.5])
    def test_rejects_unparseable_markers(self, bad):
        # The extractor must fail closed: a silent None here becomes a silently
        # unmapped survey row downstream.
        with pytest.raises(bsc.WorkbookError):
            bsc.parse_km_marker(bad)

    @pytest.mark.parametrize("metres,text", [
        (0.0, "0+000"), (300.0, "0+300"), (50.0, "0+050"),
        (6880.0, "6+880"), (39050.0, "39+050"),
    ])
    def test_formats_zero_padded_markers(self, metres, text):
        assert bsc.format_km_marker(metres) == text

    @pytest.mark.parametrize("metres", [0.0, 130.0, 6880.0, 39050.0, 1620.5])
    def test_round_trips_through_the_runtime_parser(self, metres):
        # The emitted from_km/to_km strings are consumed by
        # core.conveyance_loss.parse_chainage_m — the two parsers must agree.
        assert parse_chainage_m(bsc.format_km_marker(metres)) == metres


class TestDeriveSideSlope:
    def test_recovers_the_trapezoid_side_slope_from_design_area(self):
        # LMC 0+170-1+620: A=11.609, B=3.5, D=1.85 -> z = (A/D - B)/D = 1.5
        assert bsc.derive_side_slope(11.609, 3.5, 1.85) == 1.5

    def test_exact_trapezoid_round_trip(self):
        b, d, z = 2.4, 1.55, 1.5
        area = d * (b + z * d)
        assert bsc.derive_side_slope(area, b, d) == z

    def test_rectangular_section_yields_zero(self):
        assert bsc.derive_side_slope(2.0 * 1.5, 2.0, 1.5) == 0.0

    def test_rejects_negative_slope(self):
        # An area smaller than the rectangle B*D means the inputs are
        # inconsistent — never emit a negative slope.
        with pytest.raises(bsc.WorkbookError):
            bsc.derive_side_slope(1.0, 2.0, 1.5)

    def test_rejects_implausibly_flat_slope(self):
        with pytest.raises(bsc.WorkbookError):
            bsc.derive_side_slope(100.0, 1.0, 1.0)  # z = 99

    @pytest.mark.parametrize("area,b,d", [(1.0, 0.0, 1.0), (1.0, 1.0, 0.0)])
    def test_rejects_nonpositive_dimensions(self, area, b, d):
        with pytest.raises(bsc.WorkbookError):
            bsc.derive_side_slope(area, b, d)


class TestLiningFromNote:
    @pytest.mark.parametrize("note,lining", [
        ("คลองดาดคอนกรีต", "concrete"),
        ("คลองคาดคอนกรีต", "concrete"),  # the 5R-4L-38R-LMC typo spelling
        ("คลองดิน", "earth"),
        (None, None),
        ("Hl=3.00-6.00", None),   # a remark, not a lining statement
        ("Flume", None),
    ])
    def test_maps_survey_notes_to_lining(self, note, lining):
        assert bsc.lining_from_note(note) == lining


GATES_SYNTH = ["M(0,0)", "M(0,1)", "M(0,2)", "M(0,1;1,0)", "M(0,1;1,1)",
               "M(0,1;1,1;1,0)", "M(0,1;1,1;2,0)"]


class TestBuildSerialChains:
    def test_groups_gates_into_serial_chains(self):
        chains = bsc.build_serial_chains(GATES_SYNTH)
        assert sorted(chains, key=len, reverse=True)[0] == ["M(0,0)", "M(0,1)", "M(0,2)"]
        assert ["M(0,1;1,0)", "M(0,1;1,1)"] in chains

    def test_distinct_branch_indexes_are_distinct_chains(self):
        # 7R (branch 1) and 7L (branch 2) hang off the same parent gate but are
        # different canals — they must never merge into one chainage axis.
        chains = bsc.build_serial_chains(GATES_SYNTH)
        assert ["M(0,1;1,1;1,0)"] in chains
        assert ["M(0,1;1,1;2,0)"] in chains

    def test_every_gate_lands_in_exactly_one_chain(self):
        chains = bsc.build_serial_chains(GATES_SYNTH)
        flat = [g for chain in chains for g in chain]
        assert sorted(flat) == sorted(GATES_SYNTH)

    def test_chain_order_follows_serial_position_not_input_order(self):
        chains = bsc.build_serial_chains(["M(0,2)", "M(0,0)", "M(0,1)"])
        assert chains == [["M(0,0)", "M(0,1)", "M(0,2)"]]


class TestMatchChainsToSurvey:
    CHAINS = [["M(0,0)", "M(0,1)", "M(0,2)"], ["M(0,1;1,0)", "M(0,1;1,1)"]]
    CANALS = {"M(0,0)": "Outlet", "M(0,1)": None, "M(0,2)": "LMC",
              "M(0,1;1,0)": "RMC", "M(0,1;1,1)": "RMC"}

    def test_matches_survey_canals_by_member_gate_names(self):
        matched = bsc.match_chains_to_survey(self.CHAINS, self.CANALS, ["LMC", "RMC"])
        assert matched["LMC"] == self.CHAINS[0]
        assert matched["RMC"] == self.CHAINS[1]

    def test_survey_canal_with_no_chain_fails_closed(self):
        # A surveyed canal that maps to no gate chain would silently drop its
        # whole geometry — that is exactly the drift this generator forbids.
        with pytest.raises(bsc.WorkbookError):
            bsc.match_chains_to_survey(self.CHAINS, self.CANALS, ["LMC", "9R-LMC"])

    def test_ambiguous_name_across_two_chains_fails_closed(self):
        canals = dict(self.CANALS, **{"M(0,1;1,1;1,0)": "RMC"})
        chains = self.CHAINS + [["M(0,1;1,1;1,0)"]]
        with pytest.raises(bsc.WorkbookError):
            bsc.match_chains_to_survey(chains, canals, ["RMC"])


def _row(from_m, to_m, **over):
    row = {
        "canal": "LMC", "from_m": float(from_m), "to_m": float(to_m),
        "length_m": float(to_m - from_m), "qd": 5.0, "area_m2": 7.84,
        "manning_n": 0.018, "bed_slope": 0.0002,
        "bottom_width_m": 2.5, "depth_m": 1.6, "note": "คลองดาดคอนกรีต",
        "excel_row": 99,
    }
    row.update(over)
    return row


class TestAssignRowsToEdges:
    POSITIONS = [("M(0,0)", 0.0), ("M(0,1)", 300.0), ("M(0,2)", 1620.0)]

    def test_exact_boundary_rows_map_one_to_one(self):
        pieces, skipped, coverage = bsc.assign_rows_to_edges(
            self.POSITIONS, [_row(0, 300), _row(300, 1620)]
        )
        assert [len(v) for v in pieces.values()] == [1, 1]
        assert skipped == []
        assert all(e["status"] == "full" for e in coverage)

    def test_row_crossing_a_gate_splits_at_the_gate(self):
        pieces, skipped, _ = bsc.assign_rows_to_edges(
            self.POSITIONS, [_row(0, 1620)]
        )
        first = pieces[("M(0,0)", "M(0,1)")]
        second = pieces[("M(0,1)", "M(0,2)")]
        assert [(p["from_m"], p["to_m"]) for p in first] == [(0.0, 300.0)]
        assert [(p["from_m"], p["to_m"]) for p in second] == [(300.0, 1620.0)]
        # both pieces inherit the row's payload
        assert first[0]["row"]["depth_m"] == second[0]["row"]["depth_m"] == 1.6
        assert skipped == []

    def test_lengths_are_conserved_across_splits(self):
        pieces, _, _ = bsc.assign_rows_to_edges(self.POSITIONS, [_row(0, 1620)])
        total = sum(p["to_m"] - p["from_m"] for segs in pieces.values() for p in segs)
        assert total == 1620.0

    def test_row_beyond_the_last_gate_is_reported_not_emitted(self):
        pieces, skipped, coverage = bsc.assign_rows_to_edges(
            self.POSITIONS, [_row(0, 300), _row(300, 1620), _row(1620, 1820)]
        )
        assert sum(len(v) for v in pieces.values()) == 2
        assert [s["reason"] for s in skipped] == ["beyond_last_gate"]
        assert skipped[0]["from_m"] == 1620.0 and skipped[0]["to_m"] == 1820.0

    def test_row_without_cross_section_is_reported_not_defaulted(self):
        # The real case: LMC 0+000-0+170 is a Flume with no B/D/n/s survey.
        flume = _row(0, 170, bottom_width_m=None, depth_m=None,
                     manning_n=None, bed_slope=None, area_m2=None, note="Flume")
        pieces, skipped, coverage = bsc.assign_rows_to_edges(
            self.POSITIONS, [flume, _row(170, 1620)]
        )
        assert [s["reason"] for s in skipped] == ["missing_cross_section"]
        [first_edge] = [e for e in coverage if e["downstream"] == "M(0,1)"]
        assert first_edge["status"] == "partial"
        assert first_edge["covered_m"] == 130.0
        assert first_edge["gap_m"] == 170.0
        assert first_edge["missing"] == [
            {"from_km": "0+000", "to_km": "0+170",
             "reason": "survey_row_missing_cross_section"}
        ]

    def test_unsurveyed_interior_and_trailing_chainage_is_measured(self):
        pieces, skipped, coverage = bsc.assign_rows_to_edges(
            self.POSITIONS, [_row(0, 300), _row(300, 800), _row(900, 1500)]
        )
        [edge2] = [e for e in coverage if e["downstream"] == "M(0,2)"]
        assert edge2["status"] == "partial"
        assert edge2["covered_m"] == 1100.0
        assert edge2["gap_m"] == 220.0
        assert edge2["missing"] == [
            {"from_km": "0+800", "to_km": "0+900", "reason": "unsurveyed"},
            {"from_km": "1+500", "to_km": "1+620", "reason": "unsurveyed"},
        ]

    def test_edge_with_no_rows_at_all_is_status_none(self):
        _, _, coverage = bsc.assign_rows_to_edges(self.POSITIONS, [_row(0, 300)])
        [edge2] = [e for e in coverage if e["downstream"] == "M(0,2)"]
        assert edge2["status"] == "none"
        assert edge2["covered_m"] == 0.0 and edge2["gap_m"] == 1320.0

    def test_non_increasing_gate_positions_fail_closed(self):
        with pytest.raises(bsc.WorkbookError):
            bsc.assign_rows_to_edges(
                [("M(0,0)", 0.0), ("M(0,1)", 300.0), ("M(0,2)", 300.0)],
                [_row(0, 300)],
            )

    def test_row_missing_design_area_or_discharge_is_reported_not_emitted(self):
        # A stale-formula workbook (saved without recalculation) presents as
        # blank A/Qd cells — emitting without slope/q_max would make consumers
        # default divergently (0.0 vs 1.0) and silently lose the capacity bound.
        no_area = _row(0, 300, area_m2=None)
        no_qd = _row(300, 1620, qd=None)
        pieces, skipped, _ = bsc.assign_rows_to_edges(
            self.POSITIONS, [no_area, no_qd]
        )
        assert pieces == {}
        assert [s["reason"] for s in skipped] == [
            "missing_design_values", "missing_design_values",
        ]


class TestExtractionValidation:
    def test_overlapping_survey_rows_fail_closed(self):
        with pytest.raises(bsc.WorkbookError):
            bsc.validate_survey_rows([_row(0, 300), _row(200, 500)])

    def test_length_must_equal_chainage_delta(self):
        # The 1000x bug class: a length column that stops matching its own
        # chainage span must halt generation, not emit one of the two.
        with pytest.raises(bsc.WorkbookError):
            bsc.validate_survey_rows([_row(0, 300, length_m=3000.0)])

    def test_reversed_span_fails_closed(self):
        with pytest.raises(bsc.WorkbookError):
            bsc.validate_survey_rows([_row(300, 0, length_m=300.0)])

    def test_numeric_cell_holding_text_fails_closed(self):
        # Excel type drift: a q_max/Qd cell stored as the TEXT '9.961' must halt
        # generation, not silently become null and drop the capacity bound.
        with pytest.raises(bsc.WorkbookError):
            bsc.cell_number("9.961", "Sheet1 row 5 q_max")
        assert bsc.cell_number(None, "x") is None
        assert bsc.cell_number("-", "x") is None
        assert bsc.cell_number(" ", "x") is None
        assert bsc.cell_number(9.961, "x") == 9.961

    def test_separator_row_with_stray_hydraulic_cells_fails_closed(self, tmp_path):
        # A row whose chainage cells were cleared but that still carries ANY
        # hydraulic value (e.g. only manning n / bed slope) is survey data being
        # silently dropped — not a separator.
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Characteristics"
        for col, text in bsc.CHAR_HEADERS_R2.items():
            ws.cell(row=2, column=col, value=text)
        for col, text in bsc.CHAR_HEADERS_R3.items():
            ws.cell(row=3, column=col, value=text)
        ws.cell(row=4, column=2, value="LMC")
        ws.cell(row=4, column=13, value=0.018)  # manning n, no chainage span
        path = tmp_path / "drift.xlsx"
        wb.save(path)
        loaded = openpyxl.load_workbook(path, data_only=True, read_only=True)
        with pytest.raises(bsc.WorkbookError, match="without a chainage span"):
            bsc.extract_survey_rows(loaded["Characteristics"])


@pytest.fixture(scope="module")
def artifacts():
    return bsc.build_all(WORKBOOK)


class TestRealWorkbookGeneration:
    def test_all_artifacts_carry_the_workbook_sha256(self, artifacts):
        digest = hashlib.sha256(WORKBOOK.read_bytes()).hexdigest()
        for name in ("network", "canal_geometry", "geometry_coverage"):
            meta = artifacts[name]["metadata"]
            assert meta["source_sha256"] == digest
            assert meta["source_workbook"] == WORKBOOK.name

    def test_geometry_passes_the_strict_runtime_loader(self, artifacts, tmp_path):
        path = tmp_path / "canal_geometry.json"
        path.write_text(json.dumps(artifacts["canal_geometry"]), encoding="utf-8")
        data = load_canal_geometry_config(str(path))
        # 99 survey rows - 1 flume (no cross-section) - 1 beyond-last-gate tail
        # + 6 split-at-gate pieces = 103 emitted segments.
        assert data["summary"]["total_sections"] == len(data["canal_sections"]) == 103

    def test_network_passes_the_strict_runtime_loader(self, artifacts, tmp_path):
        path = tmp_path / "network.json"
        path.write_text(json.dumps(artifacts["network"]), encoding="utf-8")
        data = load_network_config(str(path))
        assert len(data["gates"]) == 59 and len(data["edges"]) == 59

    def test_network_edges_equal_the_naming_grammar_derivation(self, artifacts):
        net = artifacts["network"]
        assert net["edges"] == [list(e) for e in edges_from_names(list(net["gates"]))]

    def test_geometry_feeds_the_multisegment_runtime_indexer(self, artifacts):
        sections = sections_by_edge_from_geometry(artifacts["canal_geometry"])
        assert len(sections) == 42  # every serial gate-to-gate reach is surveyed

    def test_first_lmc_reach_is_the_post_flume_concrete_piece(self, artifacts):
        # Edge M(0,0)->M(0,1) spans 0+000-0+300; the flume [0,170] has no
        # cross-section, so the only emitted segment is [170,300] of the
        # 0+170-1+620 concrete row.
        sections = sections_by_edge_from_geometry(artifacts["canal_geometry"])
        [seg] = sections[("M(0,0)", "M(0,1)")]
        assert seg["length_m"] == 130
        assert seg["from_km_m"] == 170.0 and seg["to_km_m"] == 300.0
        assert seg["q_max"] == 9.961  # Qd of the source row
        assert seg["seepage_rate_m_s"] == 1.0e-5  # concrete

    def test_lmc_tail_reach_aggregates_four_segments_ending_in_earth(self, artifacts):
        sections = sections_by_edge_from_geometry(artifacts["canal_geometry"])
        segs = sections[("M(0,13)", "M(0,14)")]
        assert [s["length_m"] for s in segs] == [240, 160, 200, 350]
        assert segs[-1]["seepage_rate_m_s"] == 2.0e-5  # คลองดิน tail

    def test_side_slope_is_derived_not_the_lining_thickness(self, artifacts):
        slopes = {
            s["geometry"]["cross_section"]["side_slope"]
            for s in artifacts["canal_geometry"]["canal_sections"]
        }
        assert slopes == {1.5}

    def test_zone_summary_is_consistent(self, artifacts):
        sections = artifacts["canal_geometry"]["canal_sections"]
        by_zone = {}
        for s in sections:
            by_zone[f"zone_{s['zone']}"] = by_zone.get(f"zone_{s['zone']}", 0) + 1
        assert artifacts["canal_geometry"]["summary"]["by_zone"] == by_zone

    def test_coverage_report_covers_all_59_edges(self, artifacts):
        edges = artifacts["geometry_coverage"]["edges"]
        assert len(edges) == 59
        by_status = {}
        for e in edges:
            by_status[e["status"]] = by_status.get(e["status"], 0) + 1
        assert by_status == {"full": 37, "partial": 5, "not_applicable": 17}
        by_category = {}
        for e in edges:
            by_category[e["category"]] = by_category.get(e["category"], 0) + 1
        assert by_category == {
            "serial": 42, "junction_head": 13, "offtake": 3, "source": 1,
        }

    def test_partial_reaches_and_gaps_match_the_survey(self, artifacts):
        gaps = {
            (e["upstream"], e["downstream"]): e["gap_m"]
            for e in artifacts["geometry_coverage"]["edges"]
            if e["status"] == "partial"
        }
        assert gaps == {
            ("M(0,0)", "M(0,1)"): 170.0,            # flume, no cross-section
            ("M (0,12; 1,1; 1,1)", "M (0,12; 1,1; 1,2)"): 30.0,
            ("M (0,12; 1,2; 1,1)", "M (0,12; 1,2; 1,2)"): 1200.0,
            ("M (0,12; 1,2; 1,0; 1,0)", "M (0,12; 1,2; 1,0; 1,1)"): 410.0,
            ("M (0,1; 1,3)", "M (0,1; 1,4)"): 80.0,
        }

    def test_skipped_rows_are_reported(self, artifacts):
        skipped = artifacts["geometry_coverage"]["summary"]["skipped_rows"]
        assert skipped == {"missing_cross_section": 1, "beyond_last_gate": 1}

    def test_sills_and_control_structures_are_never_emitted(self, artifacts):
        # RID-gated (WAVE_2-4_PLAN §1.5 HIGH #1): the สบ.1 join is unapproved.
        text = json.dumps(artifacts)
        assert "control_structures" not in text
        assert "sill" not in text

    def test_reaches_block_carries_every_serial_span(self, artifacts):
        # The runtime needs the gate-to-gate span to measure head/tail survey
        # gaps (reach_chainage_gap_m) and physical reach length (legacy solver).
        reaches = artifacts["canal_geometry"]["reaches"]
        assert len(reaches) == 42
        by_edge = {(r["from_node"], r["to_node"]): r for r in reaches}
        first = by_edge[("M(0,0)", "M(0,1)")]
        assert (first["from_km"], first["to_km"]) == ("0+000", "0+300")
        assert first["span_m"] == 300
        assert first["covered_m"] == 130 and first["gap_m"] == 170
        assert all(r["span_m"] == r["covered_m"] + r["gap_m"] for r in reaches)

    def test_rotation_plan_q_is_retained_alongside_qd(self, artifacts):
        # Qd is the binding q_max; the rotation-plan Qmax column is preserved as
        # q_rotation_plan so no committed capacity information is deleted
        # (capacity governance moves to the 2.3 calibration schema).
        sections = artifacts["canal_geometry"]["canal_sections"]
        first = sections[0]["geometry"]["hydraulic_params"]
        assert first["q_max"] == 9.961
        assert first["q_rotation_plan"] == 9.926
        rmc = [s for s in sections if s["canal_name"] == "RMC"]
        assert rmc and all(
            "q_rotation_plan" not in s["geometry"]["hydraulic_params"] for s in rmc
        )

    def test_blank_zone_omits_the_key_instead_of_null(self, artifacts):
        # zone: null breaks legacy consumers doing gate.get('zone', 0) — the key
        # existing with null returns None. Absence keeps the .get default and is
        # honest strict JSON.
        gate = artifacts["network"]["gates"]["M(0,1)"]
        assert "zone" not in gate
        others = [g for k, g in artifacts["network"]["gates"].items() if k != "M(0,1)"]
        assert all(isinstance(g["zone"], int) for g in others)

    def test_every_section_carries_slope_and_q_max(self, artifacts):
        # area_m2 and qd are emission-required, so no section can ship without
        # its slope or capacity bound — consumers never fall back to divergent
        # defaults (conveyance uses 0.0, the legacy solver 1.0).
        for section in artifacts["canal_geometry"]["canal_sections"]:
            assert "side_slope" in section["geometry"]["cross_section"]
            assert "q_max" in section["geometry"]["hydraulic_params"]


class TestCoverageClassifier:
    GATES = {
        "M(0,0)": {"canal": "Outlet"}, "M(0,1)": {"canal": "LMC"},
        "M(0,0;1,0)": {"canal": "WW"},
        "M(0,1;1,0)": {"canal": "New"}, "M(0,1;1,1)": {"canal": "New"},
    }

    def test_unmatched_multi_gate_chain_edges_are_serial_none_not_offtake(self):
        # QCHECK 2.1b HIGH: if a whole canal's survey block disappears from the
        # workbook, its serial reaches must show as status 'none' — labelling
        # them 'offtake'/'not_applicable' certifies the loss as normal.
        entries = bsc.classify_edges(
            gate_ids=list(self.GATES),
            canal_by_gate={k: v["canal"] for k, v in self.GATES.items()},
            km_by_gate={"M(0,0)": "0+000", "M(0,1)": "0+300", "M(0,0;1,0)": "0+160",
                        "M(0,1;1,0)": "0+000", "M(0,1;1,1)": "2+600"},
            matched_head_canals={"M(0,0)": "LMC"},
            serial_coverage={("M(0,0)", "M(0,1)"): {
                "span_m": 300, "covered_m": 300, "gap_m": 0, "segments": 1,
                "status": "full", "missing": [],
            }},
        )
        by_edge = {(e["upstream"], e["downstream"]): e for e in entries}
        assert by_edge[("S", "M(0,0)")]["category"] == "source"
        assert by_edge[("M(0,0)", "M(0,1)")]["category"] == "serial"
        # single-gate unmatched chain -> offtake (no canal of its own to survey)
        assert by_edge[("M(0,0)", "M(0,0;1,0)")]["category"] == "offtake"
        # unmatched MULTI-gate chain: head is a junction, serial edge is a
        # visible survey hole
        assert by_edge[("M(0,1)", "M(0,1;1,0)")]["category"] == "junction_head"
        serial_none = by_edge[("M(0,1;1,0)", "M(0,1;1,1)")]
        assert serial_none["category"] == "serial"
        assert serial_none["status"] == "none"
        assert serial_none["missing"] == [{"reason": "canal_not_in_survey"}]


class TestRegenerationLock:
    """The committed artifacts must be BYTE-exactly what the committed workbook
    regenerates — hand edits, reformatting, and stale artifacts fail the suite."""

    @pytest.mark.parametrize("name,filename", [
        ("network", "network.json"),
        ("canal_geometry", "canal_geometry.json"),
        ("geometry_coverage", "geometry_coverage.json"),
    ])
    def test_committed_artifact_equals_regeneration(self, artifacts, name, filename):
        expected = (
            json.dumps(artifacts[name], indent=2, ensure_ascii=False) + "\n"
        ).encode("utf-8")
        assert (CONFIG_DIR / filename).read_bytes() == expected


class TestMainCli:
    def test_writes_three_deterministic_artifacts(self, tmp_path):
        out1, out2 = tmp_path / "a", tmp_path / "b"
        bsc.main([str(WORKBOOK), "--out-dir", str(out1)])
        bsc.main([str(WORKBOOK), "--out-dir", str(out2)])
        names = ["network.json", "canal_geometry.json", "geometry_coverage.json"]
        for n in names:
            b1, b2 = (out1 / n).read_bytes(), (out2 / n).read_bytes()
            assert b1 == b2  # deterministic: no timestamps, stable ordering
            assert b1.endswith(b"\n")
