from config.settings import Settings
from db.database_manager import DatabaseManager
import pytest


def test_postgres_url_mapped_and_validated(monkeypatch):
    url = "postgresql://postgres:pass@localhost:5432/postgres"
    monkeypatch.setenv("POSTGRES_URL", url)
    s = Settings()
    assert s.postgres_url == url


def test_daily_requirement_job_configuration_maps_explicit_environment(monkeypatch):
    source_url = "postgresql://postgres:pass@localhost:5432/postgres"
    monkeypatch.setenv("REQUIREMENT_SOURCE_POSTGRES_URL", source_url)
    monkeypatch.setenv("DAILY_REQUIREMENT_ENABLED", "true")
    monkeypatch.setenv("DAILY_REQUIREMENT_CRON", "15 3 * * *")
    monkeypatch.setenv("DAILY_REQUIREMENT_TIMEZONE", "Asia/Bangkok")
    monkeypatch.setenv("DAILY_REQUIREMENT_HORIZON_DAYS", "7")
    monkeypatch.setenv("DAILY_REQUIREMENT_INPUT_MAX_AGE_HOURS", "4320")

    settings = Settings()

    assert settings.requirement_source_postgres_url == source_url
    assert settings.daily_requirement_enabled is True
    assert settings.daily_requirement_cron == "15 3 * * *"
    assert settings.daily_requirement_timezone == "Asia/Bangkok"
    assert settings.daily_requirement_horizon_days == 7
    assert settings.daily_requirement_input_max_age_hours == 4320


DAILY_REQUIREMENT_FLAG_ENVS = (
    ("DAILY_REQUIREMENT_ENABLED", "daily_requirement_enabled"),
    (
        "DAILY_REQUIREMENT_STARTUP_CATCHUP_ENABLED",
        "daily_requirement_startup_catchup_enabled",
    ),
    ("DAILY_REQUIREMENT_SCHEDULE_ENABLED", "daily_requirement_schedule_enabled"),
)


def test_daily_requirement_automatic_flags_default_false(monkeypatch):
    for env_name, _ in DAILY_REQUIREMENT_FLAG_ENVS:
        monkeypatch.delenv(env_name, raising=False)

    settings = Settings(_env_file=None)

    for _, field in DAILY_REQUIREMENT_FLAG_ENVS:
        assert getattr(settings, field) is False


@pytest.mark.parametrize(("env_name", "field"), DAILY_REQUIREMENT_FLAG_ENVS)
def test_daily_requirement_flags_map_explicit_environment_independently(
    monkeypatch, env_name, field
):
    for other_env, _ in DAILY_REQUIREMENT_FLAG_ENVS:
        monkeypatch.delenv(other_env, raising=False)
    monkeypatch.setenv(env_name, "true")

    settings = Settings(_env_file=None)

    for _, other_field in DAILY_REQUIREMENT_FLAG_ENVS:
        assert getattr(settings, other_field) is (other_field == field)


@pytest.mark.asyncio
async def test_requirement_source_connection_fails_closed_before_initialization():
    manager = DatabaseManager()

    with pytest.raises(RuntimeError, match="requirement source"):
        async with manager.get_requirement_source_connection():
            pass
