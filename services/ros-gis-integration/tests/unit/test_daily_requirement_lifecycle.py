"""Lifecycle-split locks for the daily requirement job (PR 0.3a).

Covers the tracked root PM2 surface and the flag-driven lifespan behavior:
base enable exposes manual runs only; startup catch-up and the recurring
schedule each require their own explicit opt-in flag; misconfigured or
downgraded states are logged, never silent.
"""

import inspect
import re
from pathlib import Path

import pytest

import main as ros_gis_main
from config.settings import Settings
from services.daily_requirement_job import DailyRequirementJob

REPO_ROOT = Path(__file__).resolve().parents[4]

DAILY_REQUIREMENT_FLAG_KEYS = (
    "DAILY_REQUIREMENT_ENABLED",
    "DAILY_REQUIREMENT_STARTUP_CATCHUP_ENABLED",
    "DAILY_REQUIREMENT_SCHEDULE_ENABLED",
)


def _settings(base=False, catchup=False, schedule=False) -> Settings:
    return Settings(
        _env_file=None,
        daily_requirement_enabled=base,
        daily_requirement_startup_catchup_enabled=catchup,
        daily_requirement_schedule_enabled=schedule,
    )


class _FakeJob:
    def __init__(self, catch_up_error: Exception | None = None):
        self.catch_up_calls = 0
        self.start_schedule_calls = 0
        self.catch_up_error = catch_up_error
        self.schedule_running = False

    async def catch_up(self):
        self.catch_up_calls += 1
        if self.catch_up_error is not None:
            raise self.catch_up_error

    async def start_schedule(self):
        self.start_schedule_calls += 1
        self.schedule_running = True


class _RecordingLogger:
    def __init__(self):
        self.warnings = []
        self.errors = []
        self.infos = []

    def warning(self, message, **kwargs):
        self.warnings.append((message, kwargs))

    def error(self, message, **kwargs):
        self.errors.append((message, kwargs))

    def info(self, message, **kwargs):
        self.infos.append((message, kwargs))


@pytest.fixture()
def recording_logger(monkeypatch):
    logger = _RecordingLogger()
    monkeypatch.setattr(ros_gis_main, "logger", logger)
    return logger


def test_fake_job_pins_real_daily_requirement_job_interface():
    assert inspect.iscoroutinefunction(DailyRequirementJob.catch_up)
    assert inspect.iscoroutinefunction(DailyRequirementJob.start_schedule)
    assert inspect.iscoroutinefunction(DailyRequirementJob.stop)
    assert isinstance(
        inspect.getattr_static(DailyRequirementJob, "schedule_running"), property
    )
    fake_only = {"catch_up_calls", "start_schedule_calls", "catch_up_error"}
    fake_public = {name for name in vars(_FakeJob) if not name.startswith("_")}
    real_public = {name for name in dir(DailyRequirementJob) if not name.startswith("_")}
    assert fake_public <= real_public | fake_only


def test_disabled_base_constructs_no_job():
    job = ros_gis_main.build_daily_requirement_job(_settings(base=False), object())

    assert job is None


def test_base_enable_constructs_manual_job():
    job = ros_gis_main.build_daily_requirement_job(
        _settings(base=True), ros_gis_main.db_manager
    )

    assert job is not None
    assert job.schedule_running is False


@pytest.mark.asyncio
async def test_base_enable_exposes_manual_run_without_startup_or_schedule(
    recording_logger,
):
    fake = _FakeJob()

    await ros_gis_main.start_daily_requirement_lifecycle(fake, _settings(base=True))

    assert fake.catch_up_calls == 0
    assert fake.start_schedule_calls == 0


@pytest.mark.asyncio
async def test_manual_only_mode_logs_an_explicit_downgrade_warning(recording_logger):
    await ros_gis_main.start_daily_requirement_lifecycle(
        _FakeJob(), _settings(base=True)
    )

    assert any("manual-only" in message for message, _ in recording_logger.warnings)


@pytest.mark.asyncio
async def test_enabled_automatic_paths_do_not_log_the_downgrade_warning(
    recording_logger,
):
    await ros_gis_main.start_daily_requirement_lifecycle(
        _FakeJob(), _settings(base=True, catchup=True, schedule=True)
    )

    assert recording_logger.warnings == []


@pytest.mark.asyncio
async def test_automatic_flags_without_base_flag_log_an_ignored_warning(
    recording_logger,
):
    await ros_gis_main.start_daily_requirement_lifecycle(
        None, _settings(base=False, catchup=True, schedule=True)
    )

    assert any(
        "DAILY_REQUIREMENT_ENABLED" in message
        for message, _ in recording_logger.warnings
    )


@pytest.mark.asyncio
async def test_lifecycle_is_a_no_op_without_a_job_or_flags(recording_logger):
    await ros_gis_main.start_daily_requirement_lifecycle(None, _settings(base=False))

    assert recording_logger.warnings == []
    assert recording_logger.errors == []


@pytest.mark.asyncio
async def test_startup_catchup_runs_only_when_explicitly_enabled(recording_logger):
    fake = _FakeJob()

    await ros_gis_main.start_daily_requirement_lifecycle(
        fake, _settings(base=True, catchup=True)
    )

    assert fake.catch_up_calls == 1
    assert fake.start_schedule_calls == 0


@pytest.mark.asyncio
async def test_schedule_starts_only_when_explicitly_enabled(recording_logger):
    fake = _FakeJob()

    await ros_gis_main.start_daily_requirement_lifecycle(
        fake, _settings(base=True, schedule=True)
    )

    assert fake.catch_up_calls == 0
    assert fake.start_schedule_calls == 1


@pytest.mark.asyncio
async def test_both_automatic_paths_can_be_enabled_explicitly(recording_logger):
    fake = _FakeJob()

    await ros_gis_main.start_daily_requirement_lifecycle(
        fake, _settings(base=True, catchup=True, schedule=True)
    )

    assert fake.catch_up_calls == 1
    assert fake.start_schedule_calls == 1


@pytest.mark.asyncio
async def test_catchup_failure_logs_and_does_not_prevent_schedule_start(
    recording_logger,
):
    fake = _FakeJob(catch_up_error=RuntimeError("source database unavailable"))

    await ros_gis_main.start_daily_requirement_lifecycle(
        fake, _settings(base=True, catchup=True, schedule=True)
    )

    assert fake.catch_up_calls == 1
    assert fake.start_schedule_calls == 1
    assert any("catch-up failed" in message for message, _ in recording_logger.errors)


@pytest.mark.asyncio
async def test_schedule_start_failure_logs_a_schedule_specific_error(recording_logger):
    class _BrokenScheduleJob(_FakeJob):
        async def start_schedule(self):
            raise ValueError("DAILY_REQUIREMENT_CRON minute/hour is out of range")

    await ros_gis_main.start_daily_requirement_lifecycle(
        _BrokenScheduleJob(), _settings(base=True, schedule=True)
    )

    assert any(
        "schedule start failed" in message for message, _ in recording_logger.errors
    )


@pytest.mark.asyncio
async def test_lifespan_wires_job_into_app_state_and_stops_it_on_shutdown(monkeypatch):
    class _LifespanJob(_FakeJob):
        def __init__(self):
            super().__init__()
            self.stop_calls = 0

        async def stop(self):
            self.stop_calls += 1

    fake = _LifespanJob()

    async def _noop():
        return None

    monkeypatch.setattr(ros_gis_main.db_manager, "initialize", _noop)
    monkeypatch.setattr(ros_gis_main.db_manager, "close", _noop)
    monkeypatch.setattr(ros_gis_main.settings, "use_mock_server", True)
    monkeypatch.setattr(
        ros_gis_main, "build_daily_requirement_job", lambda job_settings, manager: fake
    )
    try:
        async with ros_gis_main.lifespan(ros_gis_main.app):
            assert ros_gis_main.app.state.daily_requirement_job is fake
        assert fake.stop_calls == 1
    finally:
        ros_gis_main.app.state.daily_requirement_job = None


def test_status_reports_base_catchup_schedule_cron_and_timezone_truthfully(
    monkeypatch,
):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(ros_gis_main.settings, "daily_requirement_enabled", True)
    monkeypatch.setattr(
        ros_gis_main.settings, "daily_requirement_startup_catchup_enabled", False
    )
    monkeypatch.setattr(
        ros_gis_main.settings, "daily_requirement_schedule_enabled", False
    )
    monkeypatch.setattr(ros_gis_main.settings, "daily_requirement_cron", "30 1 * * *")
    monkeypatch.setattr(
        ros_gis_main.settings, "daily_requirement_timezone", "Asia/Bangkok"
    )
    fake = _FakeJob()
    fake.schedule_running = True
    ros_gis_main.app.state.daily_requirement_job = fake
    try:
        response = TestClient(ros_gis_main.app).get("/api/v1/status")
    finally:
        ros_gis_main.app.state.daily_requirement_job = None

    assert response.status_code == 200
    body = response.json()["daily_requirement"]
    assert body == {
        "enabled": True,
        "startup_catchup_enabled": False,
        "schedule_enabled": False,
        "schedule_running": True,
        "cron": "30 1 * * *",
        "timezone": "Asia/Bangkok",
    }


def test_root_pm2_surface_pins_all_automatic_flags_false():
    source = (REPO_ROOT / "pm2-services.ecosystem.config.js").read_text(
        encoding="utf-8"
    )
    start = source.index("munbon-ros-gis-integration")
    following = source[start:]
    match = re.search(r"\n\s*name: ", following)
    block = following if match is None else following[: match.start()]
    for key in DAILY_REQUIREMENT_FLAG_KEYS:
        assert re.search(
            rf"{key}:\s*['\"]false['\"]", block
        ), f"pm2-services.ecosystem.config.js must pin {key} 'false' for ros-gis"
