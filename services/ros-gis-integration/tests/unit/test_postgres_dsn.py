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
        f"postgresql://producer:{password}@localhost:5432/munbon_dev"
    )

    assert dsn.asyncpg_connect_args() == {
        "user": "producer",
        "password": RAW_PASSWORD,
        "host": "localhost",
        "database": "munbon_dev",
        "port": 5432,
    }


def test_percent_encoded_literal_is_not_decoded_twice():
    dsn = parse_postgres_dsn(
        "postgresql://producer:literal%252Fvalue@localhost/munbon_dev"
    )

    assert dsn.password == "literal%2Fvalue"


def test_ipv6_port_and_query_parameters_reach_both_drivers():
    dsn = parse_postgres_dsn(
        "postgresql://producer:secret@[2001:db8::1]:6543/munbon_dev"
        "?application_name=requirement%20producer&sslmode=require"
    )

    assert dsn.asyncpg_connect_args() == {
        "user": "producer",
        "password": "secret",
        "host": "2001:db8::1",
        "database": "munbon_dev",
        "port": 6543,
        "ssl": "require",
        "server_settings": {"application_name": "requirement producer"},
    }
    assert dsn.sqlalchemy_connect_args() == {
        "ssl": "require",
        "server_settings": {"application_name": "requirement producer"},
    }
    assert dsn.sqlalchemy_url() == URL.create(
        "postgresql+asyncpg",
        username="producer",
        password="secret",
        host="2001:db8::1",
        port=6543,
        database="munbon_dev",
    )


def test_sqlalchemy_url_redacts_password_when_rendered():
    url = parse_postgres_dsn(
        f"postgresql://producer:{ENCODED_PASSWORD}@localhost/munbon_dev"
    ).sqlalchemy_url()

    assert RAW_PASSWORD not in str(url)
    assert RAW_PASSWORD not in repr(url)
    assert "***" in str(url)


@pytest.mark.parametrize(
    "raw_url",
    [
        "mysql://producer:do-not-leak@secret-host/munbon_dev",
        "postgresql://producer:do-not-leak-secret-host/munbon_dev",
        "postgresql://producer:do-not-leak@secret-host",
        "postgresql://producer:do-not-leak@secret-host:not-a-port/munbon_dev",
        "postgresql://producer:do-not-leak@secret-host/munbon_dev?x=1&x=2",
    ],
)
def test_malformed_urls_raise_fixed_redacted_error(raw_url):
    with pytest.raises(PostgresDsnError) as caught:
        parse_postgres_dsn(raw_url)

    assert str(caught.value) == "Invalid PostgreSQL URL"
    assert "do-not-leak" not in str(caught.value)
    assert "secret-host" not in str(caught.value)


@pytest.mark.asyncio
async def test_database_manager_uses_main_and_source_asyncpg_kwargs(monkeypatch):
    from db import database_manager as module

    main_url = (
        f"postgresql://producer:{ENCODED_PASSWORD}@localhost:5432/munbon_dev"
        "?application_name=ros&sslmode=require"
    )
    source_url = (
        f"postgresql://source:{ENCODED_PASSWORD}@[2001:db8::2]:6543/postgres"
        "?application_name=requirement-source"
    )
    main_pool = Mock()
    source_pool = Mock()
    create_pool = AsyncMock(side_effect=[main_pool, source_pool])
    engine = Mock()
    create_engine = Mock(return_value=engine)
    redis_client = Mock()
    redis_from_url = AsyncMock(return_value=redis_client)
    monkeypatch.setattr(module.settings, "postgres_url", main_url)
    monkeypatch.setattr(module.settings, "requirement_source_postgres_url", source_url)
    monkeypatch.setattr(module.settings, "daily_requirement_enabled", True)
    monkeypatch.setattr(module.settings, "environment", "production")
    monkeypatch.setattr(module.asyncpg, "create_pool", create_pool)
    monkeypatch.setattr(module, "create_async_engine", create_engine)
    monkeypatch.setattr(module.redis, "from_url", redis_from_url)
    manager = DatabaseManager()
    monkeypatch.setattr(manager, "_test_connections", AsyncMock())

    await manager.initialize()

    assert len(create_pool.call_args_list) == 2
    main_kwargs = create_pool.call_args_list[0].kwargs
    source_kwargs = create_pool.call_args_list[1].kwargs
    assert main_kwargs["password"] == RAW_PASSWORD
    assert main_kwargs["ssl"] == "require"
    assert main_kwargs["server_settings"]["application_name"] == "ros"
    assert source_kwargs["password"] == RAW_PASSWORD
    assert source_kwargs["host"] == "2001:db8::2"
    assert source_kwargs["server_settings"] == {
        "application_name": "requirement-source"
    }
    engine_url = create_engine.call_args.args[0]
    assert isinstance(engine_url, URL)
    assert engine_url.password == RAW_PASSWORD
    assert RAW_PASSWORD not in repr(engine_url)
