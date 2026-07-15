"""
Unit tests for core.config_loader — strict, fail-closed loading of the canonical runtime
configs (Wave 1.1, PROGRAM_REVIEW_2026-07-09 §2.2). Three failure classes must never
reach the hydraulics: corrupt JSON (bare NaN/Infinity), missing schema, and
metadata<->content drift. Pure/stdlib; run in isolation:
    PYTHONPATH=src pytest --noconftest -o addopts="" tests/unit/test_config_loader.py
"""
import json
from pathlib import Path

import pytest

from core.config_loader import (
    ConfigError,
    load_canal_geometry_config,
    load_gate_calibrations_config,
    load_network_config,
    load_strict_json_object,
    load_zone_topology_config,
)

SERVICE_ROOT = Path(__file__).resolve().parents[2]
NETWORK = str(SERVICE_ROOT / "src" / "config" / "network.json")
GEOMETRY = str(SERVICE_ROOT / "src" / "config" / "canal_geometry.json")
CALIBRATIONS = str(SERVICE_ROOT / "src" / "config" / "gate_calibrations.json")
ZONE_TOPOLOGY = str(SERVICE_ROOT / "src" / "config" / "zone_topology.json")


def _unavailable_structure(role):
    return {
        "design_fsl_msl_m": None,
        "sill_msl_m": None,
        "structure_max_flow_m3s": None,
        "design_fsl_reference_side": None,
        "structure_data_status": "unavailable",
        "structure_role": role,
    }


def _write(tmp_path, payload, name="cfg.json"):
    p = tmp_path / name
    p.write_text(payload if isinstance(payload, str) else json.dumps(payload))
    return str(p)


def _valid_network():
    return {
        "metadata": {"canonical": True, "total_gates": 2, "total_connections": 2},
        "gates": {"M(0,0)": {"q_max": 11.2}, "M(0,1)": {"q_max": None}},
        "edges": [["S", "M(0,0)"], ["M(0,0)", "M(0,1)"]],
    }


def _valid_geometry():
    return {
        "metadata": {"source": "unit fixture"},
        "canal_sections": [
            {
                "from_node": "M(0,0)",
                "to_node": "M(0,1)",
                "geometry": {
                    "length_m": 1000.0,
                    "cross_section": {
                        "type": "trapezoidal",
                        "depth_m": 2.5,
                        "bottom_width_m": 4.0,
                        "side_slope": 1.5,
                    },
                    "hydraulic_params": {"lining_type": "concrete"},
                },
            }
        ],
        "summary": {"total_sections": 1},
    }


def _valid_calibrations():
    return {
        "metadata": {
            "source_workbook": "fixture.xlsx",
            "source_sha256": "workbook-sha",
            "intended_use": "planning_only",
            "design_fsl_reference_side": "upstream",
            "total_gates": 2,
            "gates_by_calibration_method": {
                "measured": 1,
                "inferred": 0,
                "default": 1,
            },
        },
        "gates": {
            "M(0,0)": {
                "gate_id": "M(0,0)",
                "calibration_method": "measured",
                "k1": 1.0693,
                "k2": -1.229,
                "confidence": 0.9986,
                "source_gate_ids": ["M(0,0)"],
                "source_version": "workbook-sha",
                "design_fsl_msl_m": 221.0,
                "sill_msl_m": 204.5,
                "structure_max_flow_m3s": 11.2,
                "design_fsl_reference_side": "upstream",
                "structure_data_status": "complete",
                "structure_role": "control",
            },
            "M(0,1)": {
                "gate_id": "M(0,1)",
                "calibration_method": "default",
                "confidence": 0.8,
                "source_gate_ids": [],
                "source_version": "workbook-sha",
                **_unavailable_structure("junction"),
            },
        },
    }


def _valid_zone_topology():
    return {
        "metadata": {
            "source": "operator-approved topology 2026-07-15",
            "total_zones": 6,
            "outlet_gate_id": "M(0,0)",
        },
        "canals": {"LMC": {"zones": [1, 2, 3, 4, 5]}, "RMC": {"zones": [6]}},
        "zones": [
            {
                "zone": zone,
                "canal": "RMC" if zone == 6 else "LMC",
                "entrance_gate_id": gate,
                "branches_from_zone": parent,
            }
            for zone, gate, parent in (
                (1, "M(0,2)", None),
                (2, "M(0,7)", None),
                (3, "M(0,3;1,0)", 1),
                (4, "M(0,12;1,0)", 2),
                (5, "M(0,12;1,2)", 2),
                (6, "M(0,1;1,0)", None),
            )
        ],
    }


class TestLoadStrictJsonObject:
    def test_loads_plain_object(self, tmp_path):
        path = _write(tmp_path, {"a": 1})
        assert load_strict_json_object(path) == {"a": 1}

    @pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
    def test_rejects_non_finite_constants(self, tmp_path, constant):
        # Python's json.dump happily emits these; strict JSON forbids them (Wave 0.5).
        path = _write(tmp_path, '{"q_max": %s}' % constant)
        with pytest.raises(ConfigError, match="cfg.json"):
            load_strict_json_object(path)

    def test_rejects_malformed_json(self, tmp_path):
        path = _write(tmp_path, '{"unterminated": ')
        with pytest.raises(ConfigError, match="cfg.json"):
            load_strict_json_object(path)

    def test_rejects_missing_file(self, tmp_path):
        with pytest.raises(ConfigError, match="nowhere.json"):
            load_strict_json_object(str(tmp_path / "nowhere.json"))

    def test_rejects_non_object_top_level(self, tmp_path):
        path = _write(tmp_path, [1, 2, 3])
        with pytest.raises(ConfigError, match="object"):
            load_strict_json_object(path)


class TestLoadNetworkConfig:
    def test_accepts_committed_canonical_file(self):
        data = load_network_config(NETWORK)
        assert len(data["gates"]) == 59
        assert len(data["edges"]) == 59

    def test_accepts_minimal_consistent_network(self, tmp_path):
        data = load_network_config(_write(tmp_path, _valid_network()))
        assert data["edges"] == [["S", "M(0,0)"], ["M(0,0)", "M(0,1)"]]

    def test_rejects_gate_count_drift(self, tmp_path):
        net = _valid_network()
        net["metadata"]["total_gates"] = 3
        with pytest.raises(ConfigError, match="drift"):
            load_network_config(_write(tmp_path, net))

    def test_rejects_connection_count_drift(self, tmp_path):
        net = _valid_network()
        net["metadata"]["total_connections"] = 1
        with pytest.raises(ConfigError, match="drift"):
            load_network_config(_write(tmp_path, net))

    @pytest.mark.parametrize("canonical", [False, None, "true"])
    def test_rejects_non_canonical_marker(self, tmp_path, canonical):
        net = _valid_network()
        if canonical is None:
            del net["metadata"]["canonical"]
        else:
            net["metadata"]["canonical"] = canonical
        with pytest.raises(ConfigError, match="canonical"):
            load_network_config(_write(tmp_path, net))

    @pytest.mark.parametrize("count", [True, "2", 2.0])
    def test_rejects_non_integer_declared_counts(self, tmp_path, count):
        # bool is an int subclass and "2"/2.0 are truthy lookalikes — all must be rejected,
        # otherwise metadata like {"total_gates": true} slips through count checks.
        net = _valid_network()
        net["gates"] = {"M(0,0)": {}}
        net["edges"] = [["S", "M(0,0)"]]
        net["metadata"]["total_connections"] = 1
        net["metadata"]["total_gates"] = count
        with pytest.raises(ConfigError, match="total_gates"):
            load_network_config(_write(tmp_path, net))

    @pytest.mark.parametrize("key", ["metadata", "gates", "edges"])
    def test_rejects_missing_required_key(self, tmp_path, key):
        net = _valid_network()
        del net[key]
        with pytest.raises(ConfigError, match=key):
            load_network_config(_write(tmp_path, net))

    @pytest.mark.parametrize(
        "edge", [["S"], ["S", "M(0,0)", "M(0,1)"], ["S", 7], "S->M(0,0)"]
    )
    def test_rejects_malformed_edge_shape(self, tmp_path, edge):
        net = _valid_network()
        net["edges"][1] = edge
        with pytest.raises(ConfigError, match="edge"):
            load_network_config(_write(tmp_path, net))

    def test_rejects_edge_child_not_a_gate(self, tmp_path):
        net = _valid_network()
        net["edges"][1] = ["M(0,0)", "M(9,9)"]
        with pytest.raises(ConfigError, match=r"M\(9,9\)"):
            load_network_config(_write(tmp_path, net))

    def test_rejects_edge_parent_not_gate_or_source(self, tmp_path):
        net = _valid_network()
        net["edges"][1] = ["X", "M(0,1)"]
        with pytest.raises(ConfigError, match="'X'"):
            load_network_config(_write(tmp_path, net))

    def test_rejects_duplicate_edges(self, tmp_path):
        # Two copies of one edge keep the declared count right but corrupt the graph.
        net = _valid_network()
        net["edges"][1] = ["S", "M(0,0)"]
        net["gates"] = {"M(0,0)": {}, "M(0,1)": {}}
        with pytest.raises(ConfigError, match="duplicate"):
            load_network_config(_write(tmp_path, net))

    def test_rejects_non_object_gate_value(self, tmp_path):
        # build_capacity_index silently skips non-dict gates -> default capacity;
        # the loader must refuse them instead.
        net = _valid_network()
        net["gates"]["M(0,1)"] = "not-an-object"
        with pytest.raises(ConfigError, match=r"gates\['M\(0,1\)'\]"):
            load_network_config(_write(tmp_path, net))

    @pytest.mark.parametrize("q_max", [0, -3.5, "11.2", True])
    def test_rejects_invalid_q_max(self, tmp_path, q_max):
        # q_max must be null (unknown, surfaced downstream) or a finite positive number.
        net = _valid_network()
        net["gates"]["M(0,0)"]["q_max"] = q_max
        with pytest.raises(ConfigError, match="q_max"):
            load_network_config(_write(tmp_path, net))

    def test_accepts_null_q_max(self, tmp_path):
        data = load_network_config(_write(tmp_path, _valid_network()))
        assert data["gates"]["M(0,1)"]["q_max"] is None

    def test_rejects_grammar_invalid_gate_key(self, tmp_path):
        # Canonical networks are regenerated from the naming grammar (F-11b); a key
        # like "M(00,1)" is a textual alias of another node and must not load.
        net = _valid_network()
        net["gates"]["M(00,1)"] = {}
        net["metadata"]["total_gates"] = 3
        with pytest.raises(ConfigError, match="invalid gate id"):
            load_network_config(_write(tmp_path, net))

    def test_rejects_gate_keys_that_collide_when_normalized(self, tmp_path):
        net = _valid_network()
        net["gates"]["M (0,1)"] = {}
        net["metadata"]["total_gates"] = 3
        with pytest.raises(ConfigError, match="collide"):
            load_network_config(_write(tmp_path, net))


class TestLoadCanalGeometryConfig:
    def test_accepts_committed_canonical_file(self):
        # 103 = 99 survey rows - flume - beyond-last-gate tail + 6 splits (2.1b).
        data = load_canal_geometry_config(GEOMETRY)
        assert len(data["canal_sections"]) == 103

    def test_accepts_minimal_consistent_geometry(self, tmp_path):
        data = load_canal_geometry_config(_write(tmp_path, _valid_geometry()))
        assert data["canal_sections"][0]["from_node"] == "M(0,0)"

    def test_accepts_valid_reaches_block(self, tmp_path):
        geo = _valid_geometry()
        geo["reaches"] = [
            {
                "from_node": "M(0,0)",
                "to_node": "M(0,1)",
                "from_km": "0+000",
                "to_km": "1+000",
                "span_m": 1000,
                "covered_m": 1000,
                "gap_m": 0,
            }
        ]
        data = load_canal_geometry_config(_write(tmp_path, geo))
        assert data["reaches"][0]["span_m"] == 1000

    def test_rejects_reach_without_span(self, tmp_path):
        geo = _valid_geometry()
        geo["reaches"] = [
            {
                "from_node": "M(0,0)",
                "to_node": "M(0,1)",
                "from_km": "0+000",
                "to_km": "1+000",
                "covered_m": 1000,
                "gap_m": 0,
            }
        ]
        with pytest.raises(ConfigError, match="span_m"):
            load_canal_geometry_config(_write(tmp_path, geo))

    def test_rejects_reach_with_blank_node(self, tmp_path):
        geo = _valid_geometry()
        geo["reaches"] = [
            {
                "from_node": "",
                "to_node": "M(0,1)",
                "from_km": "0+000",
                "to_km": "1+000",
                "span_m": 1000,
                "covered_m": 1000,
                "gap_m": 0,
            }
        ]
        with pytest.raises(ConfigError, match="from_node"):
            load_canal_geometry_config(_write(tmp_path, geo))

    def test_rejects_summary_count_drift(self, tmp_path):
        geo = _valid_geometry()
        geo["summary"]["total_sections"] = 46
        with pytest.raises(ConfigError, match="drift"):
            load_canal_geometry_config(_write(tmp_path, geo))

    def test_rejects_empty_sections(self, tmp_path):
        geo = _valid_geometry()
        geo["canal_sections"] = []
        geo["summary"]["total_sections"] = 0
        with pytest.raises(ConfigError, match="canal_sections"):
            load_canal_geometry_config(_write(tmp_path, geo))

    @pytest.mark.parametrize("key", ["from_node", "to_node", "geometry"])
    def test_rejects_section_missing_required_field(self, tmp_path, key):
        geo = _valid_geometry()
        del geo["canal_sections"][0][key]
        with pytest.raises(ConfigError, match=key):
            load_canal_geometry_config(_write(tmp_path, geo))

    @pytest.mark.parametrize("length", [0, -120.0, None, "1000", True])
    def test_rejects_non_positive_or_non_numeric_length(self, tmp_path, length):
        geo = _valid_geometry()
        geo["canal_sections"][0]["geometry"]["length_m"] = length
        with pytest.raises(ConfigError, match="length_m"):
            load_canal_geometry_config(_write(tmp_path, geo))

    def test_rejects_cross_section_not_an_object(self, tmp_path):
        geo = _valid_geometry()
        geo["canal_sections"][0]["geometry"]["cross_section"] = "trapezoidal"
        with pytest.raises(ConfigError, match="cross_section"):
            load_canal_geometry_config(_write(tmp_path, geo))

    @pytest.mark.parametrize("key", ["depth_m", "bottom_width_m"])
    @pytest.mark.parametrize("value", [None, 0, -2.0, "2.5"])
    def test_rejects_unusable_cross_section_dimension(self, tmp_path, key, value):
        # The B5 loss runtime needs these to compute the wetted perimeter; an empty
        # cross_section must fail at load, not as a KeyError under apply_losses.
        geo = _valid_geometry()
        if value is None:
            del geo["canal_sections"][0]["geometry"]["cross_section"][key]
        else:
            geo["canal_sections"][0]["geometry"]["cross_section"][key] = value
        with pytest.raises(ConfigError, match=key):
            load_canal_geometry_config(_write(tmp_path, geo))

    def test_rejects_negative_side_slope(self, tmp_path):
        geo = _valid_geometry()
        geo["canal_sections"][0]["geometry"]["cross_section"]["side_slope"] = -1.0
        with pytest.raises(ConfigError, match="side_slope"):
            load_canal_geometry_config(_write(tmp_path, geo))

    def test_accepts_absent_side_slope(self, tmp_path):
        # side_slope is optional (rectangular sections); absence is not an error.
        geo = _valid_geometry()
        del geo["canal_sections"][0]["geometry"]["cross_section"]["side_slope"]
        assert load_canal_geometry_config(_write(tmp_path, geo))

    @pytest.mark.parametrize("key", ["metadata", "summary"])
    def test_rejects_missing_top_level_block(self, tmp_path, key):
        geo = _valid_geometry()
        del geo[key]
        with pytest.raises(ConfigError, match=key):
            load_canal_geometry_config(_write(tmp_path, geo))


class TestLoadGateCalibrationsConfig:
    def test_accepts_committed_canonical_file(self):
        data = load_gate_calibrations_config(CALIBRATIONS)
        assert len(data["gates"]) == 59
        calibrated = [
            gate
            for gate in data["gates"].values()
            if gate["calibration_method"] == "measured"
        ]
        assert len(calibrated) == 10

    def test_accepts_minimal_consistent_calibrations(self, tmp_path):
        data = load_gate_calibrations_config(_write(tmp_path, _valid_calibrations()))
        assert data["gates"]["M(0,0)"]["k1"] == 1.0693

    @pytest.mark.parametrize("source_workbook", [None, "", True])
    def test_rejects_missing_or_invalid_source_workbook(
        self, tmp_path, source_workbook
    ):
        calibrations = _valid_calibrations()
        calibrations["metadata"]["source_workbook"] = source_workbook
        with pytest.raises(ConfigError, match="source_workbook"):
            load_gate_calibrations_config(_write(tmp_path, calibrations))

    def test_rejects_total_gates_drift(self, tmp_path):
        cal = _valid_calibrations()
        cal["metadata"]["total_gates"] = 59
        with pytest.raises(ConfigError, match="drift"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    def test_rejects_calibrated_count_drift(self, tmp_path):
        cal = _valid_calibrations()
        cal["metadata"]["gates_by_calibration_method"]["measured"] = 2
        with pytest.raises(ConfigError, match="drift"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    def test_rejects_unknown_calibration_method(self, tmp_path):
        cal = _valid_calibrations()
        cal["gates"]["M(0,1)"]["calibration_method"] = "similar"
        with pytest.raises(ConfigError, match="calibration_method"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    @pytest.mark.parametrize("k1", [None, "1.07", True])
    def test_rejects_calibrated_gate_with_bad_k1(self, tmp_path, k1):
        cal = _valid_calibrations()
        cal["gates"]["M(0,0)"]["k1"] = k1
        with pytest.raises(ConfigError, match="k1"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    def test_rejects_calibrated_gate_missing_k2(self, tmp_path):
        cal = _valid_calibrations()
        del cal["gates"]["M(0,0)"]["k2"]
        with pytest.raises(ConfigError, match="k2"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    @pytest.mark.parametrize("key,value", [("k1", 0.0), ("k2", 0.0)])
    def test_rejects_calibrated_gate_with_impossible_coefficient(
        self, tmp_path, key, value
    ):
        cal = _valid_calibrations()
        cal["gates"]["M(0,0)"][key] = value
        with pytest.raises(ConfigError, match=key):
            load_gate_calibrations_config(_write(tmp_path, cal))

    @pytest.mark.parametrize("key", ["confidence", "source_gate_ids", "source_version"])
    def test_rejects_missing_provenance_field(self, tmp_path, key):
        cal = _valid_calibrations()
        del cal["gates"]["M(0,0)"][key]
        with pytest.raises(ConfigError, match=key):
            load_gate_calibrations_config(_write(tmp_path, cal))

    @pytest.mark.parametrize("confidence", [-0.01, 1.01, "high", True])
    def test_rejects_invalid_confidence(self, tmp_path, confidence):
        cal = _valid_calibrations()
        cal["gates"]["M(0,0)"]["confidence"] = confidence
        with pytest.raises(ConfigError, match="confidence"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    @pytest.mark.parametrize(
        "width_m,height_m", [(2.0, 0.4), (None, 0.4), (None, None)]
    )
    def test_rejects_circular_gate_without_one_numeric_diameter(
        self, tmp_path, width_m, height_m
    ):
        cal = _valid_calibrations()
        cal["gates"]["M(0,1)"].update(
            shape="circular", width_m=width_m, height_m=height_m
        )
        with pytest.raises(ConfigError, match="circular.*width_m"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    def _two_donor_bundle(self):
        """A calibration bundle with two measured donors spanning k1∈[1.0693,1.30]
        and k2∈[-1.80,-1.229], plus an inferred gate whose coefficients this suite
        varies. Returned unloaded so tests can mutate the inferred record."""
        cal = _valid_calibrations()
        cal["gates"]["M(0,2)"] = {
            "gate_id": "M(0,2)",
            "calibration_method": "measured",
            "k1": 1.30,
            "k2": -1.80,
            "confidence": 0.95,
            "source_gate_ids": ["M(0,2)"],
            "source_version": "workbook-sha",
            **_unavailable_structure("control"),
        }
        inferred = cal["gates"]["M(0,1)"]
        inferred.update(
            calibration_method="inferred",
            k1=1.20,
            k2=-1.50,
            confidence=0.75,
            source_gate_ids=["M(0,0)", "M(0,2)"],
            source_version="similar-gate-v1:workbook-sha",
        )
        cal["metadata"]["total_gates"] = 3
        cal["metadata"]["gates_by_calibration_method"] = {
            "measured": 2,
            "inferred": 1,
            "default": 0,
        }
        return cal

    def test_accepts_inferred_coefficients_within_donor_range(self, tmp_path):
        cal = self._two_donor_bundle()  # k1=1.20, k2=-1.50 sit inside the range
        assert load_gate_calibrations_config(_write(tmp_path, cal)) == cal

    def test_accepts_inferred_coefficients_on_the_exact_range_bounds(self, tmp_path):
        cal = self._two_donor_bundle()
        # k1 at the donor MAX, k2 at the donor MIN — the inclusive boundary.
        cal["gates"]["M(0,1)"].update(k1=1.30, k2=-1.80)
        assert load_gate_calibrations_config(_write(tmp_path, cal)) == cal

    @pytest.mark.parametrize(
        "k1,k2",
        [
            (1.31, -1.50),  # k1 above the donor max (1.30)
            (1.05, -1.50),  # k1 below the donor min (1.0693)
            (1.20, -1.90),  # k2 below the donor min (-1.80)
            (1.20, -1.20),  # k2 above the donor max (-1.229)
            (100.0, -100.0),  # both wildly outside — the retro's example
        ],
    )
    def test_rejects_inferred_coefficients_outside_donor_range(self, tmp_path, k1, k2):
        cal = self._two_donor_bundle()
        cal["gates"]["M(0,1)"].update(k1=k1, k2=k2)
        with pytest.raises(ConfigError, match="range"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    def test_rejects_inferred_confidence_not_below_measured_sources(self, tmp_path):
        cal = _valid_calibrations()
        inferred = cal["gates"]["M(0,1)"]
        inferred.update(
            calibration_method="inferred",
            k1=1.0693,  # in the single-donor hull, so the confidence check is reached
            k2=-1.229,
            confidence=0.9986,
            source_gate_ids=["M(0,0)"],
            source_version="similar-gate-v1:workbook-sha",
        )
        counts = cal["metadata"]["gates_by_calibration_method"]
        counts.update(inferred=1, default=0)
        with pytest.raises(ConfigError, match="lower than every measured source"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    def test_rejects_inferred_source_version_drift(self, tmp_path):
        cal = _valid_calibrations()
        inferred = cal["gates"]["M(0,1)"]
        inferred.update(
            calibration_method="inferred",
            k1=1.0693,  # in the single-donor hull, so the source_version check is reached
            k2=-1.229,
            confidence=0.75,
            source_gate_ids=["M(0,0)"],
            source_version="similar-gate-v2:workbook-sha",
        )
        counts = cal["metadata"]["gates_by_calibration_method"]
        counts.update(inferred=1, default=0)
        with pytest.raises(ConfigError, match="source_version"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    def test_rejects_non_planning_calibration_bundle(self, tmp_path):
        cal = _valid_calibrations()
        cal["metadata"]["intended_use"] = "actuation"
        with pytest.raises(ConfigError, match="intended_use"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    @pytest.mark.parametrize(
        "key,value",
        [
            ("design_fsl_msl_m", "221"),
            ("sill_msl_m", True),
            ("structure_max_flow_m3s", 0.0),
        ],
    )
    def test_rejects_invalid_structure_numbers(self, tmp_path, key, value):
        cal = _valid_calibrations()
        cal["gates"]["M(0,0)"][key] = value
        with pytest.raises(ConfigError, match=key):
            load_gate_calibrations_config(_write(tmp_path, cal))

    def test_rejects_structure_status_that_disagrees_with_fields(self, tmp_path):
        cal = _valid_calibrations()
        cal["gates"]["M(0,0)"]["structure_max_flow_m3s"] = None
        with pytest.raises(ConfigError, match="structure_data_status"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    @pytest.mark.parametrize("side", [None, "downstream"])
    def test_rejects_design_fsl_without_upstream_reference_side(self, tmp_path, side):
        cal = _valid_calibrations()
        cal["gates"]["M(0,0)"]["design_fsl_reference_side"] = side
        with pytest.raises(ConfigError, match="design_fsl_reference_side"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    def test_rejects_unknown_structure_role(self, tmp_path):
        cal = _valid_calibrations()
        cal["gates"]["M(0,1)"]["structure_role"] = "valve"
        with pytest.raises(ConfigError, match="structure_role"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    def test_rejects_noncanonical_stored_gate_id(self, tmp_path):
        cal = _valid_calibrations()
        gate = cal["gates"].pop("M(0,1)")
        gate["gate_id"] = "M (0,1)"
        cal["gates"]["M (0,1)"] = gate
        with pytest.raises(ConfigError, match="canonical"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    @pytest.mark.parametrize("gate_id", ["M(0,0)", "M(0,1)"])
    def test_rejects_workbook_derived_source_version_drift(self, tmp_path, gate_id):
        cal = _valid_calibrations()
        cal["gates"][gate_id]["source_version"] = "different-workbook-sha"
        with pytest.raises(ConfigError, match="source_version"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    @pytest.mark.parametrize(
        "gate_id,source_gate_ids",
        [("M(0,0)", []), ("M(0,0)", ["M(0,1)"]), ("M(0,1)", ["M(0,0)"])],
    )
    def test_rejects_lineage_that_disagrees_with_method(
        self, tmp_path, gate_id, source_gate_ids
    ):
        cal = _valid_calibrations()
        cal["gates"][gate_id]["source_gate_ids"] = source_gate_ids
        with pytest.raises(ConfigError, match="source_gate_ids"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    @pytest.mark.parametrize("bad_id", ["M(0,1", "X(0,1)", "M(0,-1)", "M(00,1)"])
    def test_rejects_gate_id_that_violates_the_naming_grammar(self, tmp_path, bad_id):
        # A typo'd key would silently push its real gate onto generic defaults via
        # get_calibration's fallback; grammar-invalid ids must fail at load.
        # (Cross-checking ids against the network file itself is PR 1.2's join.)
        cal = _valid_calibrations()
        cal["gates"][bad_id] = cal["gates"].pop("M(0,1)")
        with pytest.raises(ConfigError, match="gate id"):
            load_gate_calibrations_config(_write(tmp_path, cal))

    def test_rejects_gate_ids_that_collide_when_normalized(self, tmp_path):
        # "M (0,1)" and "M(0,1)" are the same physical gate; both present = a corrupt file.
        cal = _valid_calibrations()
        cal["gates"]["M (0,1)"] = dict(cal["gates"]["M(0,1)"])
        cal["metadata"]["total_gates"] = 3
        with pytest.raises(ConfigError, match="collide"):
            load_gate_calibrations_config(_write(tmp_path, cal))


class TestLoadZoneTopologyConfig:
    def test_accepts_committed_approved_topology(self):
        data = load_zone_topology_config(ZONE_TOPOLOGY)
        assert data == _valid_zone_topology()

    def test_accepts_minimal_consistent_topology(self, tmp_path):
        data = load_zone_topology_config(_write(tmp_path, _valid_zone_topology()))
        assert [zone["zone"] for zone in data["zones"]] == [1, 2, 3, 4, 5, 6]

    @pytest.mark.parametrize("source", [None, "", True])
    def test_rejects_missing_or_invalid_source(self, tmp_path, source):
        topology = _valid_zone_topology()
        topology["metadata"]["source"] = source
        with pytest.raises(ConfigError, match="metadata.source"):
            load_zone_topology_config(_write(tmp_path, topology))

    @pytest.mark.parametrize("zones", [[1, 2, 3, 4, 5], [1, 2, 3, 4, 5, 5]])
    def test_rejects_missing_or_duplicate_zone(self, tmp_path, zones):
        topology = _valid_zone_topology()
        topology["zones"] = [topology["zones"][zone - 1] for zone in zones]
        with pytest.raises(ConfigError, match="zones"):
            load_zone_topology_config(_write(tmp_path, topology))

    def test_rejects_canal_partition_drift(self, tmp_path):
        topology = _valid_zone_topology()
        topology["canals"]["LMC"]["zones"] = [1, 2, 3, 4]
        with pytest.raises(ConfigError, match="partition"):
            load_zone_topology_config(_write(tmp_path, topology))

    def test_rejects_noncanonical_entrance_gate(self, tmp_path):
        topology = _valid_zone_topology()
        topology["zones"][5]["entrance_gate_id"] = "M (0,1; 1,0)"
        with pytest.raises(ConfigError, match="canonical"):
            load_zone_topology_config(_write(tmp_path, topology))

    def test_rejects_unknown_parent_zone(self, tmp_path):
        topology = _valid_zone_topology()
        topology["zones"][2]["branches_from_zone"] = 9
        with pytest.raises(ConfigError, match="parent"):
            load_zone_topology_config(_write(tmp_path, topology))

    def test_rejects_branch_cycle(self, tmp_path):
        topology = _valid_zone_topology()
        topology["zones"][0]["branches_from_zone"] = 3
        with pytest.raises(ConfigError, match="cycle"):
            load_zone_topology_config(_write(tmp_path, topology))


def test_calibration_ids_match_network_ids_when_normalized():
    # Locked cross-file consistency (deferred from 1.1): the calibration file must
    # describe exactly the canonical network's gates — no missing, no extras. The
    # provenance pipeline (PR 2.1) will generate both from one source; until then
    # this test is the drift tripwire.
    from core.node_id import normalize_gate_id

    network_gates = load_network_config(NETWORK)["gates"]
    calibration_gates = load_gate_calibrations_config(CALIBRATIONS)["gates"]
    assert {normalize_gate_id(g) for g in network_gates} == {
        normalize_gate_id(g) for g in calibration_gates
    }


class TestRuntimeWiring:
    """The strict loaders must actually guard the runtime entry points (Wave 1.1
    'used by all runtime loads') — not just exist beside them."""

    def test_load_validated_network_rejects_nan_network(self, tmp_path):
        from core.network_topology import load_validated_network

        bad = tmp_path / "nan_net.json"
        bad.write_text(
            '{"metadata": {"canonical": true, "total_gates": 1, "total_connections": 1},'
            ' "gates": {"M(0,0)": {"q_max": NaN}}, "edges": [["S", "M(0,0)"]]}'
        )
        with pytest.raises(ConfigError):
            load_validated_network(str(bad))

    def test_network_flow_controller_rejects_metadata_drift(self, tmp_path):
        from core.network_flow_controller import NetworkFlowController

        net = _valid_network()
        net["metadata"]["total_gates"] = 40
        with pytest.raises(ConfigError):
            NetworkFlowController(_write(tmp_path, net))

    def test_gate_calibration_loader_fails_closed_on_missing_file(self, tmp_path):
        from utils.gate_calibration_loader import GateCalibrationLoader

        with pytest.raises(ConfigError):
            GateCalibrationLoader(str(tmp_path / "missing.json"))

    def test_gate_calibration_loader_fails_closed_on_drift(self, tmp_path):
        # The old loader swallowed every error and served generic defaults for all
        # 59 gates (fail-open); a drifted file must now refuse to load at all.
        from utils.gate_calibration_loader import GateCalibrationLoader

        cal = _valid_calibrations()
        cal["metadata"]["gates_by_calibration_method"]["measured"] = 2
        with pytest.raises(ConfigError):
            GateCalibrationLoader(_write(tmp_path, cal))

    def test_network_flow_controller_rejects_orphan_geometry_sections(self, tmp_path):
        # A geometry section describing a reach that is not in the network means the
        # two files drifted apart — fail closed instead of silently dropping coverage.
        geo = _valid_geometry()
        geo["canal_sections"][0]["from_node"] = "M(5,5)"
        geo["canal_sections"][0]["to_node"] = "M(5,6)"
        from core.network_flow_controller import NetworkFlowController

        with pytest.raises(ValueError, match="not network reaches"):
            NetworkFlowController(
                _write(tmp_path, _valid_network(), name="net.json"),
                geometry_path=_write(tmp_path, geo, name="geo.json"),
            )

    def test_network_flow_controller_rejects_calibration_gate_set_drift(self, tmp_path):
        # Wave 2.8a fail-closed: a calibration file can be internally consistent (its
        # metadata counts match its own gates) yet MISS a network gate and carry an
        # extraneous one. The loader's per-gate fallback would then fabricate a generic
        # default (confidence 0.6) for the missing gate — a silent number the confidence
        # field exists to prevent. Construction must fail closed on that cross-file drift.
        from core.network_flow_controller import NetworkFlowController

        cal = _valid_calibrations()
        # The network needs M(0,0)+M(0,1); swap the extraneous M(5,5) in for M(0,1),
        # keeping total_gates and the per-method counts identical (both default).
        extra = cal["gates"].pop("M(0,1)")
        extra["gate_id"] = "M(5,5)"
        cal["gates"]["M(5,5)"] = extra
        with pytest.raises(ValueError, match="absent from the calibration file"):
            NetworkFlowController(
                _write(tmp_path, _valid_network(), name="net.json"),
                calibration_path=_write(tmp_path, cal, name="cal.json"),
            )

    def test_gate_calibration_loader_still_serves_canonical_file(self):
        from utils.gate_calibration_loader import GateCalibrationLoader

        loader = GateCalibrationLoader(CALIBRATIONS)
        assert len(loader.calibrations) == 59
        cal = loader.get_calibration("M(0,0)")
        assert cal.calibration_method == "measured"
        assert cal.k1 == 1.0693
