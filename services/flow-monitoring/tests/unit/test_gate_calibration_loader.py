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
from utils.gate_calibration_loader import GateCalibrationLoader

SERVICE_ROOT = Path(__file__).resolve().parents[2]
CALIBRATIONS = str(SERVICE_ROOT / "src" / "config" / "gate_calibrations.json")


@pytest.fixture(scope="module")
def loader():
    return GateCalibrationLoader(CALIBRATIONS)


class TestGetCalibration:
    def test_compact_alias_resolves_to_field_calibration(self, loader):
        # 'M(0,0; 1,0)' is field-calibrated but was NOT in the old alias table:
        # its compact spelling used to fall through to the generic default.
        cal = loader.get_calibration("M(0,0;1,0)")
        assert cal.source == "field_measurement"

    def test_spaced_and_compact_queries_agree(self, loader):
        spaced = loader.get_calibration("M (0,3; 1,0)")
        compact = loader.get_calibration("M(0,3;1,0)")
        assert (spaced.k1, spaced.k2, spaced.source) == (
            compact.k1, compact.k2, compact.source
        )
        assert spaced.source == "field_measurement"

    def test_field_values_match_the_config_file(self, loader):
        stored = json.load(open(CALIBRATIONS))["gates"]["M(0,0)"]
        cal = loader.get_calibration("M(0,0)")
        assert (cal.k1, cal.k2) == (stored["k1"], stored["k2"])
        assert cal.confidence == 0.95

    def test_known_uncalibrated_gate_gets_size_based_default(self, loader):
        # 'M(0,1)' exists with has_calibration=false and no shape/width data.
        cal = loader.get_calibration("M(0,1)")
        assert cal.source == "default_by_size"
        assert cal.confidence == 0.80

    def test_unknown_but_valid_gate_gets_generic_default(self, loader):
        cal = loader.get_calibration("M(7,7)")
        assert cal.source == "generic_default"
        assert cal.confidence == 0.60

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
    def test_returns_all_ten_field_calibrated_gates_keyed_canonically(self, loader):
        calibrated = loader.get_all_calibrated_gates()
        assert len(calibrated) == 10
        assert all(" " not in gate_id for gate_id in calibrated)

    def test_keys_cover_every_has_calibration_gate_in_the_file(self, loader):
        stored = json.load(open(CALIBRATIONS))["gates"]
        expected = {
            normalize_gate_id(g)
            for g, v in stored.items()
            if v.get("has_calibration") is True
        }
        assert set(loader.get_all_calibrated_gates()) == expected
