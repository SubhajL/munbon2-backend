from pathlib import Path

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
