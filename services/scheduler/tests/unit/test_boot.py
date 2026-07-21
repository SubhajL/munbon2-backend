import importlib
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[2]


def test_scheduler_boots_with_declared_loguru(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requirements = (SERVICE_ROOT / "requirements.txt").read_text().splitlines()
    normalized_requirements = [line.lower() for line in requirements]

    assert "loguru==0.7.3" in requirements
    assert "sqlalchemy[asyncio]==2.0.23" in normalized_requirements

    for name, value in {
        "POSTGRES_URL": "postgresql://boot:boot@127.0.0.1:5432/boot",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "ROS_SERVICE_URL": "http://127.0.0.1:3047",
        "GIS_SERVICE_URL": "http://127.0.0.1:3007",
        "FLOW_MONITORING_URL": "http://127.0.0.1:3011",
        "ROS_GIS_URL": "http://127.0.0.1:3047",
        "WEATHER_SERVICE_URL": "http://127.0.0.1:3006",
        "AUTH_SERVICE_URL": "http://127.0.0.1:3001",
    }.items():
        monkeypatch.setenv(name, value)

    logger_module = importlib.import_module("core.logger")
    main_module = importlib.import_module("main")

    assert logger_module.get_logger("boot-test") is not None
    assert main_module.app.title == "scheduler"
