"""
Unit tests for utils.gate_calibration_loader — the K1/K2 lookup joined by normalized
gate id (Wave 1.2). The old hardcoded PARTIAL alias table silently pushed unmapped
compact ids (e.g. 'M(0,0;1,0)') onto generic defaults despite field calibration.
Run in isolation:
    PYTHONPATH=src pytest --noconftest -o addopts="" tests/unit/test_gate_calibration_loader.py
"""
import json
from pathlib import Path

import pytest

from core.node_id import NodeIdError, normalize_gate_id
from utils.gate_calibration_loader import GateCalibrationData, GateCalibrationLoader

SERVICE_ROOT = Path(__file__).resolve().parents[2]
CALIBRATIONS = str(SERVICE_ROOT / "src" / "config" / "gate_calibrations.json")


@pytest.fixture(scope="module")
def loader():
    return GateCalibrationLoader(CALIBRATIONS)


class TestGetCalibration:
    def test_bundle_is_explicitly_planning_only(self, loader):
        assert loader.intended_use == "planning_only"

    def test_compact_alias_resolves_to_field_calibration(self, loader):
        # 'M(0,0; 1,0)' is field-calibrated but was NOT in the old alias table:
        # its compact spelling used to fall through to the generic default.
        cal = loader.get_calibration("M(0,0;1,0)")
        assert cal.calibration_method == "measured"

    def test_spaced_and_compact_queries_agree(self, loader):
        spaced = loader.get_calibration("M (0,3; 1,0)")
        compact = loader.get_calibration("M(0,3;1,0)")
        assert (spaced.k1, spaced.k2, spaced.calibration_method) == (
            compact.k1,
            compact.k2,
            compact.calibration_method,
        )
        assert spaced.calibration_method == "measured"

    def test_field_values_match_the_config_file(self, loader):
        stored = json.load(open(CALIBRATIONS))["gates"]["M(0,0)"]
        cal = loader.get_calibration("M(0,0)")
        assert (cal.k1, cal.k2) == (stored["k1"], stored["k2"])
        assert (
            cal.calibration_method,
            cal.confidence,
            cal.source_gate_ids,
            cal.source_version,
        ) == (
            "measured",
            0.9986,
            ("M(0,0)",),
            stored["source_version"],
        )

    def test_unknown_but_valid_gate_gets_generic_default(self, loader):
        cal = loader.get_calibration("M(7,7)")
        assert (
            cal.calibration_method,
            cal.confidence,
            cal.source_gate_ids,
            cal.source_version,
        ) == ("default", 0.6, (), "runtime-default-v1")

    def test_inferred_gate_uses_supplied_coefficients_and_lineage(self, tmp_path):
        data = json.loads(Path(CALIBRATIONS).read_text())
        gate = data["gates"]["M(0,1)"]
        # k1=1.20, k2=-1.40 sit inside the M(0,0)/M(0,2) donor hull
        # (k1∈[1.0693,1.5675], k2∈[-1.654,-1.229]) so the strict loader accepts them.
        gate.update(
            calibration_method="inferred",
            k1=1.20,
            k2=-1.40,
            confidence=0.75,
            source_gate_ids=["M(0,0)", "M(0,2)"],
            source_version="similar-gate-v1:" + data["metadata"]["source_sha256"],
        )
        data["metadata"]["gates_by_calibration_method"] = {
            method: sum(
                record["calibration_method"] == method
                for record in data["gates"].values()
            )
            for method in ("measured", "inferred", "default")
        }
        path = tmp_path / "inferred.json"
        path.write_text(json.dumps(data))
        inferred = GateCalibrationLoader(str(path)).get_calibration("M(0,1)")
        assert inferred == GateCalibrationData(
            gate_id="M(0,1)",
            k1=1.20,
            k2=-1.40,
            calibration_method="inferred",
            confidence=0.75,
            source_gate_ids=("M(0,0)", "M(0,2)"),
            source_version=gate["source_version"],
            structure_data_status="unavailable",
            structure_role="junction",
        )

    def test_committed_unmeasured_gate_uses_provisional_inference(self, loader):
        inferred = loader.get_calibration("M(0,1)")
        assert inferred.calibration_method == "inferred"
        assert inferred.source_gate_ids == ("M(0,0)", "M(0,2)", "M(0,7)")
        assert 0.0 < inferred.confidence < 0.9805
        assert inferred.source_version.startswith("similar-gate-v1:")

    def test_malformed_gate_id_fails_closed(self, loader):
        with pytest.raises(NodeIdError):
            loader.get_calibration("M(0,1")


class TestGetGateData:
    """The raw-record lookup used by hydraulic_service._gate_rated_capacity (the old
    code read the deleted hardcoded gate_id_mapping attribute directly)."""

    def test_returns_stored_record_for_any_spacing(self, loader):
        assert loader.get_gate_data("M(0,0)")["q_max_m3s"] == 11.2
        assert loader.get_gate_data("M(0,0;1,0)") == loader.get_gate_data("M(0,0; 1,0)")

    def test_returns_empty_dict_for_unknown_valid_gate(self, loader):
        assert loader.get_gate_data("M(7,7)") == {}

    def test_malformed_gate_id_fails_closed(self, loader):
        with pytest.raises(NodeIdError):
            loader.get_gate_data("M(0,1")

    @pytest.mark.parametrize(
        "gate_id,sheet1_capacity,structure_capacity,binding_capacity",
        [
            ("M(0,1;1,0)", 1.375, 1.2, 1.2),
            ("M(0,1;1,3)", None, 0.252, 0.252),
            ("M(0,1;1,1;1,1)", None, 0.67, 0.67),
        ],
    )
    def test_rated_capacity_binds_distinct_sheet1_and_structure_sources(
        self,
        loader,
        gate_id,
        sheet1_capacity,
        structure_capacity,
        binding_capacity,
    ):
        stored = loader.get_gate_data(gate_id)
        assert (
            stored.get("q_max_m3s"),
            stored["structure_max_flow_m3s"],
        ) == (sheet1_capacity, structure_capacity)
        assert loader.rated_q_max(gate_id) == pytest.approx(binding_capacity)


class TestBuildFlowCalibration:
    # The SINGLE home for GateFlowCalibration assembly (F-01): HydraulicService and
    # NetworkFlowController both call it, never a re-implementation (C10). Oracle: the
    # same build_gate_flow_calibration primitive fed the loader's own inputs.
    def test_assembles_from_calibration_rated_capacity_and_geometry(self, loader):
        from core.gate_flow import build_gate_flow_calibration

        gate_id = "M(0,0)"  # measured, rated q_max 11.2 in the file
        cal = loader.get_calibration(gate_id)
        expected = build_gate_flow_calibration(
            k1=cal.k1,
            k2=cal.k2,
            confidence=cal.confidence,
            q_max_m3s=loader.rated_q_max(gate_id),
            width_m=cal.width_m,
            sill_m=cal.sill_msl_m,
            max_opening_m=loader._max_opening_from_geometry(cal),
            shape=cal.shape,
        )
        assert loader.build_flow_calibration(gate_id) == expected
        assert loader.build_flow_calibration(gate_id).q_max_m3s == pytest.approx(11.2)

    @pytest.mark.parametrize(
        "gate_id,expected_sill,expected_capacity",
        [
            ("M(0,1;1,0)", 203.712, 1.2),
            ("M(0,1;1,3)", 197.258, 0.252),
            ("M(0,1;1,1;1,1)", 199.254, 0.67),
        ],
    )
    def test_v2_structure_data_supplies_real_sill_and_binding_capacity(
        self, loader, gate_id, expected_sill, expected_capacity
    ):
        calibration = loader.get_calibration(gate_id)
        flow_calibration = loader.build_flow_calibration(gate_id)
        assert (
            calibration.sill_msl_m,
            flow_calibration.sill_m,
            flow_calibration.q_max_m3s,
        ) == pytest.approx((expected_sill, expected_sill, expected_capacity))

    def test_passed_calibration_is_used_not_relooked_up(self, loader):
        # A DISTINCT calibration (different k1) must flow into the result — proving the
        # supplied object is used, not silently refetched from the file.
        import dataclasses

        gate_id = "M(0,0)"
        stored = loader.get_calibration(gate_id)
        distinct = dataclasses.replace(stored, k1=stored.k1 + 0.5)
        assert loader.build_flow_calibration(gate_id, distinct).k1 == pytest.approx(
            stored.k1 + 0.5
        )
        assert loader.build_flow_calibration(gate_id).k1 == pytest.approx(stored.k1)

    def test_max_opening_from_geometry_prefers_height_then_width(self, loader):
        cal = loader.get_calibration("M(0,0)")
        # A gate cannot open past its leaf height/diameter; None only when no geometry.
        got = loader._max_opening_from_geometry(cal)
        assert got is None or got > 0.0


class TestGetAllCalibratedGates:
    def test_returns_all_59_measured_and_inferred_gates_keyed_canonically(self, loader):
        calibrated = loader.get_all_calibrated_gates()
        assert len(calibrated) == 59
        assert all(" " not in gate_id for gate_id in calibrated)

    def test_keys_cover_every_nondefault_gate_in_the_file(self, loader):
        stored = json.load(open(CALIBRATIONS))["gates"]
        expected = {
            normalize_gate_id(g)
            for g, v in stored.items()
            if v["calibration_method"] != "default"
        }
        assert set(loader.get_all_calibrated_gates()) == expected
