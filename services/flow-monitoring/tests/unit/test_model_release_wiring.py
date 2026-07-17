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
