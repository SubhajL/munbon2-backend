from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import URL

from db.database_manager import DatabaseManager
from db.postgres_dsn import PostgresDsnError, parse_postgres_dsn


RAW_PASSWORD = "p@ss%:word/raw"
ENCODED_PASSWORD = "p%40ss%25%3Aword%2Fraw"


@pytest.mark.parametrize("password", [RAW_PASSWORD, ENCODED_PASSWORD])
def test_raw_or_encoded_reserved_password_decodes_once(password):
    dsn = parse_postgres_dsn(
        f"postgresql://planner:{password}@localhost:5432/munbon_dev"
    )

    assert dsn.asyncpg_connect_args() == {
        "user": "planner",
        "password": RAW_PASSWORD,
        "host": "localhost",
        "database": "munbon_dev",
        "port": 5432,
    }


def test_percent_encoded_literal_is_not_decoded_twice():
    dsn = parse_postgres_dsn(
        "postgresql://planner:literal%252Fvalue@localhost/munbon_dev"
    )

    assert dsn.password == "literal%2Fvalue"


def test_ipv6_port_and_query_parameters_reach_both_drivers():
    dsn = parse_postgres_dsn(
        "postgresql://planner:secret@[2001:db8::1]:6543/munbon_dev"
        "?application_name=water%20planning&sslmode=require"
    )

    assert dsn.asyncpg_connect_args() == {
        "user": "planner",
        "password": "secret",
        "host": "2001:db8::1",
        "database": "munbon_dev",
        "port": 6543,
        "ssl": "require",
        "server_settings": {"application_name": "water planning"},
    }
    assert dsn.sqlalchemy_connect_args() == {
        "ssl": "require",
        "server_settings": {"application_name": "water planning"},
    }
    assert dsn.sqlalchemy_url() == URL.create(
        "postgresql+asyncpg",
        username="planner",
        password="secret",
        host="2001:db8::1",
        port=6543,
        database="munbon_dev",
    )


def test_sqlalchemy_url_redacts_password_when_rendered():
    url = parse_postgres_dsn(
        f"postgresql://planner:{ENCODED_PASSWORD}@localhost/munbon_dev"
    ).sqlalchemy_url()

    assert RAW_PASSWORD not in str(url)
    assert RAW_PASSWORD not in repr(url)
    assert "***" in str(url)


@pytest.mark.parametrize(
    "raw_url",
    [
        "mysql://planner:do-not-leak@secret-host/munbon_dev",
        "postgresql://planner:do-not-leak-secret-host/munbon_dev",
        "postgresql://planner:do-not-leak@secret-host",
        "postgresql://planner:do-not-leak@secret-host:not-a-port/munbon_dev",
        "postgresql://planner:do-not-leak@secret-host/munbon_dev?x=1&x=2",
    ],
)
def test_malformed_urls_raise_fixed_redacted_error(raw_url):
    with pytest.raises(PostgresDsnError) as caught:
        parse_postgres_dsn(raw_url)

    assert str(caught.value) == "Invalid PostgreSQL URL"
    assert "do-not-leak" not in str(caught.value)
    assert "secret-host" not in str(caught.value)


@pytest.mark.asyncio
async def test_database_manager_uses_asyncpg_kwargs_and_sqlalchemy_url(monkeypatch):
    from db import database_manager as module

    raw_url = (
        f"postgresql://planner:{ENCODED_PASSWORD}@[2001:db8::1]:6543/munbon_dev"
        "?application_name=bff&sslmode=require"
    )
    pool = Mock()
    engine = Mock()
    create_pool = AsyncMock(return_value=pool)
    create_engine = Mock(return_value=engine)
    redis_client = Mock()
    redis_from_url = AsyncMock(return_value=redis_client)
    monkeypatch.setattr(module.settings, "postgres_url", raw_url)
    monkeypatch.setattr(module.settings, "environment", "production")
    monkeypatch.setattr(module.asyncpg, "create_pool", create_pool)
    monkeypatch.setattr(module, "create_async_engine", create_engine)
    monkeypatch.setattr(module.redis, "from_url", redis_from_url)
    manager = DatabaseManager()
    monkeypatch.setattr(manager, "_test_connections", AsyncMock())

    await manager.initialize()

    assert create_pool.call_args.args == ()
    assert create_pool.call_args.kwargs["password"] == RAW_PASSWORD
    assert create_pool.call_args.kwargs["host"] == "2001:db8::1"
    assert create_pool.call_args.kwargs["ssl"] == "require"
    assert create_pool.call_args.kwargs["server_settings"]["application_name"] == "bff"
    engine_url = create_engine.call_args.args[0]
    assert isinstance(engine_url, URL)
    assert engine_url.password == RAW_PASSWORD
    assert create_engine.call_args.kwargs["connect_args"]["ssl"] == "require"
    assert RAW_PASSWORD not in repr(engine_url)
