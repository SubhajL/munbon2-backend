from config.settings import Settings


def test_postgres_url_mapped_and_validated(monkeypatch):
    url = "postgresql://postgres:pass@localhost:5432/postgres"
    monkeypatch.setenv("POSTGRES_URL", url)
    s = Settings()
    assert s.postgres_url == url
