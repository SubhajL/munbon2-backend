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
