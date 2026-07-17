from core.config import Settings


def test_database_url_normalized_to_asyncpg(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
    # Provide required settings for instantiation
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/4")
    monkeypatch.setenv("ROS_SERVICE_URL", "http://localhost:3047")
    monkeypatch.setenv("GIS_SERVICE_URL", "http://localhost:3007")
    monkeypatch.setenv("FLOW_MONITORING_URL", "http://localhost:3011")
    monkeypatch.setenv("WEATHER_SERVICE_URL", "http://localhost:3006")
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://localhost:3001")
    monkeypatch.setenv("JWT_SECRET_KEY", "dev")

    s = Settings()
    assert s.database_url.startswith("postgresql+asyncpg://")
