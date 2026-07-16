import json
from pathlib import Path

import pytest

from core.config_loader import ConfigError
from core.design_profile import DesignProfileError
from services.design_profile_service import DesignProfileService

SERVICE_ROOT = Path(__file__).resolve().parents[2]
CONFIG = SERVICE_ROOT / "src" / "config"


@pytest.fixture(scope="module")
def service():
    return DesignProfileService(
        str(CONFIG / "network.json"),
        str(CONFIG / "canal_geometry.json"),
        str(CONFIG / "gate_calibrations.json"),
        str(CONFIG / "zone_topology.json"),
    )


class TestDesignProfileService:
    def test_calibration_gate_set_drift_fails_closed(self, tmp_path):
        calibrations = json.loads((CONFIG / "gate_calibrations.json").read_text())
        old_id = "M(0,0;2,0)"
        extra_id = "M(9,9)"
        replacement = calibrations["gates"].pop(old_id)
        replacement["gate_id"] = extra_id
        replacement["source_gate_ids"] = [extra_id]
        calibrations["gates"][extra_id] = replacement
        for gate in calibrations["gates"].values():
            gate["source_gate_ids"] = [
                extra_id if source == old_id else source
                for source in gate["source_gate_ids"]
            ]
        calibration_path = tmp_path / "gate_calibrations.json"
        calibration_path.write_text(json.dumps(calibrations))
        with pytest.raises(ConfigError, match="calibration.*network"):
            DesignProfileService(
                str(CONFIG / "network.json"),
                str(CONFIG / "canal_geometry.json"),
                str(calibration_path),
                str(CONFIG / "zone_topology.json"),
            )

    def test_empty_zone_selection_fails_closed(self, service):
        with pytest.raises(DesignProfileError, match="zones"):
            service.calculate([], 0.5)

    def test_returns_exact_approved_all_zone_topology(self, service):
        result = service.calculate([1, 2, 3, 4, 5, 6], 0.5)
        assert result["outlet_gate_id"] == "M(0,0)"
        assert result["canals"] == {"LMC": [1, 2, 3, 4, 5], "RMC": [6]}
        assert [
            (
                item["zone"],
                item["canal"],
                item["entrance_gate_id"],
                item["branches_from_zone"],
            )
            for item in result["zones"]
        ] == [
            (1, "LMC", "M(0,2)", None),
            (2, "LMC", "M(0,7)", None),
            (3, "LMC", "M(0,3;1,0)", 1),
            (4, "LMC", "M(0,12;1,0)", 2),
            (5, "LMC", "M(0,12;1,2)", 2),
            (6, "RMC", "M(0,0;2,0)", None),
        ]

    def test_zone_6_design_point_uses_first_rmc_reach_geometry(self, service):
        [zone] = service.calculate([6], 1.0)["zones"]
        assert zone["status"] == "available"
        assert zone["reason"] is None
        assert (zone["reference_upstream"], zone["reference_downstream"]) == (
            "M(0,0;2,0)",
            "M(0,0;2,1)",
        )
        assert zone["flow_m3s"] == pytest.approx(1.2)
        assert zone["binding_capacity_m3s"] == pytest.approx(1.2)
        assert zone["forecast_level_msl_m"] == pytest.approx(205.561, abs=1e-9)
        assert zone["effective_bed_msl_m"] != pytest.approx(zone["sill_msl_m"])

    def test_zone_1_reports_its_tighter_sheet1_capacity(self, service):
        [zone] = service.calculate([1], 1.0)["zones"]
        assert zone["status"] == "over_capacity"
        assert zone["reason"] == "flow_exceeds_binding_capacity"
        assert zone["design_flow_m3s"] == pytest.approx(9.926)
        assert zone["binding_capacity_m3s"] == pytest.approx(8.737)
        assert zone["forecast_level_msl_m"] is None

    def test_zones_without_v3_structure_datum_stay_unavailable(self, service):
        result = service.calculate([2, 3, 4, 5], 0.5)
        assert [
            (zone["zone"], zone["status"], zone["reason"]) for zone in result["zones"]
        ] == [
            (2, "unavailable", "structure_data_unavailable"),
            (3, "unavailable", "structure_data_unavailable"),
            (4, "unavailable", "structure_data_unavailable"),
            (5, "unavailable", "structure_data_unavailable"),
        ]

    def test_response_is_provenanced_and_never_commandable(self, service):
        result = service.calculate([6], 0.5)
        assert {
            "mode": result["mode"],
            "open_loop": result["open_loop"],
            "actual_state_known": result["actual_state_known"],
            "commandable": result["commandable"],
            "source_workbook": result["source_workbook"],
            "source_sha256": result["source_sha256"],
        } == {
            "mode": "design_profile",
            "open_loop": True,
            "actual_state_known": False,
            "commandable": False,
            "source_workbook": "SCADA Section Detailed Information 2026-07-14 V3.0 SL.xlsx",
            "source_sha256": "528a3fe3978e916ce2048189239045c9ecae5d74f456a2100c9c946ca2787e1c",
        }
        assert set(result["config_sha256"]) == {
            "network",
            "canal_geometry",
            "gate_calibrations",
            "zone_topology",
        }
        assert all(len(value) == 64 for value in result["config_sha256"].values())
