from pathlib import Path

import pytest

MAIN = Path(__file__).resolve().parents[2] / "src" / "main.py"


def test_lifespan_registers_configured_model_release_on_app_state():
    source = MAIN.read_text(encoding="utf-8")
    assert all(
        marker in source
        for marker in (
            "load_configured_hydraulic_model_release(",
            "settings.hydraulic_model_release_path",
            "app.state.hydraulic_model_release",
            "reach_responses_from_model_release(",
            "app.state.reach_responses",
            "ControlPredictionService(",
            "app.state.control_prediction_service",
        )
    )


def test_lifespan_loads_routing_before_optional_model_release():
    source = MAIN.read_text(encoding="utf-8")

    routing_load = source.index("load_routing_topology(")
    release_load = source.index("load_configured_hydraulic_model_release(")
    assert routing_load < release_load
    assert "app.state.routing_topology" in source
    assert "app.state.model_config_sha256" in source
    assert (
        "app.state.routing_topology.transport_reach_ids()"
        in source[release_load : release_load + 400]
    )


def test_missing_routing_artifact_fails_without_configured_release(tmp_path):
    from core.config_loader import ConfigError, load_routing_topology

    config_dir = MAIN.parent / "config"
    with pytest.raises(ConfigError, match="cannot read"):
        load_routing_topology(
            str(tmp_path / "absent-routing.json"),
            str(config_dir / "network.json"),
            str(config_dir / "geometry_coverage.json"),
            str(config_dir / "canal_geometry.json"),
        )


def test_lifespan_builds_withdrawal_capacity_from_gate_calibrations():
    source = MAIN.read_text(encoding="utf-8")

    assert "build_withdrawal_structure_max_flow_map(" in source
    assert "load_gate_calibrations_config(calibration_file)" in source
    assert "structure_max_flow_m3s_by_id=" in source


def test_withdrawal_capacity_map_resolves_from_committed_artifacts():
    from core.config_loader import (
        load_gate_calibrations_config,
        load_routing_topology,
    )
    from services.control_prediction_service import (
        build_withdrawal_structure_max_flow_map,
    )

    config_dir = MAIN.parent / "config"
    topology = load_routing_topology(
        str(config_dir / "routing_topology.json"),
        str(config_dir / "network.json"),
        str(config_dir / "geometry_coverage.json"),
        str(config_dir / "canal_geometry.json"),
    )
    calibrations = load_gate_calibrations_config(
        str(config_dir / "gate_calibrations.json")
    )

    capacity = build_withdrawal_structure_max_flow_map(topology, calibrations)

    assert capacity == (
        ("M(0,0;1,0)", None),
        ("M(0,0;2,0;1,0)", 1.234),
        ("M(0,0;2,1;1,2;1,0)", 0.159),
    )


def test_committed_release_loads_through_real_configured_loader():
    from core.config_loader import load_routing_topology
    from core.model_release import load_configured_hydraulic_model_release
    from core.reach_response import reach_responses_from_model_release

    config_dir = MAIN.parent / "config"
    release_path = (
        MAIN.parents[1] / "data" / "model-releases" / "engineering-prior-v5-v1.json"
    )
    topology = load_routing_topology(
        str(config_dir / "routing_topology.json"),
        str(config_dir / "network.json"),
        str(config_dir / "geometry_coverage.json"),
        str(config_dir / "canal_geometry.json"),
    )

    release = load_configured_hydraulic_model_release(
        str(release_path), topology.transport_reach_ids()
    )

    assert release is not None
    assert release.commandable is False
    assert len(release.reach_parameters) == 41
    assert len(release.unavailable_reaches) == 1
    members = reach_responses_from_model_release(release)
    assert len(members) == 123
