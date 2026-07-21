from core.config import Settings


def _seed_required_env(monkeypatch):
    """Seed every non-database required Settings field so a test can isolate the
    database_url resolution without a developer .env leaking in."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/4")
    monkeypatch.setenv("ROS_SERVICE_URL", "http://localhost:3047")
    monkeypatch.setenv("GIS_SERVICE_URL", "http://localhost:3007")
    monkeypatch.setenv("FLOW_MONITORING_URL", "http://localhost:3011")
    monkeypatch.setenv("ROS_GIS_URL", "http://localhost:3047")
    monkeypatch.setenv("WEATHER_SERVICE_URL", "http://localhost:3006")
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://localhost:3001")
    # PR 4.4a-1: the JWT secret must be strong and the claim policy explicit, or
    # Settings construction fails closed.
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "strong-enough-jwt-secret-for-tests-0123456789"
    )
    monkeypatch.setenv("JWT_ISSUER", "munbon-auth-test")
    monkeypatch.setenv("JWT_AUDIENCE", "munbon-scheduler-test")
    monkeypatch.setenv("JWT_CLAIM_POLICY_MODE", "compat")


def test_database_url_normalized_to_asyncpg(monkeypatch):
    _seed_required_env(monkeypatch)
    # POSTGRES_URL absent → database_url falls back to DATABASE_URL (still upgraded
    # to the asyncpg driver). `_env_file=None` isolates the resolution to the OS
    # environment so the developer .env (which carries a POSTGRES_URL) can't leak
    # in and mask the fallback path being asserted.
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
    )

    s = Settings(_env_file=None)
    assert s.database_url.startswith("postgresql+asyncpg://")
    assert s.database_url.endswith("@localhost:5432/postgres")
    # PR 4.3a: the ros-gis-integration URL lives in the ACTIVE settings
    # (core/config.py), not the orphan src/config/settings.py.
    assert s.ros_gis_url == "http://localhost:3047"


def test_database_url_prefers_canonical_postgres_url_over_database_url(monkeypatch):
    # PR 4.4a-2: when a deployment sets BOTH, the runtime MUST bind to POSTGRES_URL
    # (the DB migrate.py + PM2 target) — never DATABASE_URL — so the service can
    # never serve a different database than migrations were applied to.
    _seed_required_env(monkeypatch)
    monkeypatch.setenv(
        "POSTGRES_URL", "postgresql://canon:canon@canonical-host:5432/canon_db"
    )
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://other:other@stale-host:5432/stale_db"
    )

    s = Settings(_env_file=None)
    assert (
        s.database_url
        == "postgresql+asyncpg://canon:canon@canonical-host:5432/canon_db"
    )
    assert "stale-host" not in s.database_url


def _seed_db(monkeypatch):
    monkeypatch.setenv("POSTGRES_URL", "postgresql://p:p@localhost:5432/p")


def test_shadow_dispatcher_settings_are_dark_by_default(monkeypatch):
    # PR 6.3a: unset SCADA url + service secret => the dispatcher is dark.
    _seed_required_env(monkeypatch)
    _seed_db(monkeypatch)
    for key in ("SCHEDULER_SCADA_BASE_URL", "SCHEDULER_SERVICE_JWT_SECRET"):
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)
    assert s.scheduler_scada_base_url is None
    assert s.scheduler_service_jwt_secret is None
    # Defaults match what SCADA's verifier expects.
    assert s.scheduler_service_jwt_issuer == "munbon-scheduler"
    assert s.scheduler_service_jwt_audience == "munbon-scada-machine-boundary"
    assert s.scheduler_service_jwt_max_age_seconds == 300


def test_execution_mode_accepts_only_the_three_deliberate_modes(monkeypatch):
    import pytest

    _seed_required_env(monkeypatch)
    _seed_db(monkeypatch)
    for mode in ("disabled", "shadow", "operator_approved_open_loop"):
        monkeypatch.setenv("CONTROL_EXECUTION_MODE", mode)
        assert Settings(_env_file=None).control_execution_mode == mode
    monkeypatch.setenv("CONTROL_EXECUTION_MODE", "operator_approved")
    with pytest.raises(ValueError, match="control_execution_mode"):
        Settings(_env_file=None)


def test_a_strong_service_secret_is_accepted(monkeypatch):
    _seed_required_env(monkeypatch)
    _seed_db(monkeypatch)
    monkeypatch.setenv(
        "SCHEDULER_SERVICE_JWT_SECRET",
        "a-strong-dedicated-service-secret-0123456789xyz",
    )
    s = Settings(_env_file=None)
    assert s.scheduler_service_jwt_secret.startswith("a-strong-dedicated")


def test_a_weak_service_secret_breaks_settings(monkeypatch):
    import pytest

    _seed_required_env(monkeypatch)
    _seed_db(monkeypatch)
    monkeypatch.setenv("SCHEDULER_SERVICE_JWT_SECRET", "change-me")
    with pytest.raises(Exception):
        Settings(_env_file=None)


def test_service_token_max_age_capped_at_scada_default(monkeypatch):
    import pytest

    _seed_required_env(monkeypatch)
    _seed_db(monkeypatch)
    # M3: a max-age beyond SCADA's default maxAge (5m) is rejected so a token can't outlive it.
    monkeypatch.setenv("SCHEDULER_SERVICE_JWT_MAX_AGE_SECONDS", "600")
    with pytest.raises(Exception):
        Settings(_env_file=None)


def test_readback_reconciliation_mode_defaults_off(monkeypatch):
    _seed_required_env(monkeypatch)
    _seed_db(monkeypatch)
    monkeypatch.delenv("CONTROL_READBACK_RECONCILIATION_MODE", raising=False)
    assert Settings(_env_file=None).control_readback_reconciliation_mode == "off"


def test_unknown_readback_reconciliation_mode_is_rejected(monkeypatch):
    import pytest

    _seed_required_env(monkeypatch)
    _seed_db(monkeypatch)
    monkeypatch.setenv("CONTROL_READBACK_RECONCILIATION_MODE", "haywire")
    with pytest.raises(Exception):
        Settings(_env_file=None)
