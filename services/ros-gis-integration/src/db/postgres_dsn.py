from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

from sqlalchemy import URL


class PostgresDsnError(ValueError):
    """A PostgreSQL URL cannot be parsed without exposing its contents."""


@dataclass(frozen=True)
class PostgresDsn:
    username: str
    password: str | None
    host: str
    port: int | None
    database: str
    query: tuple[tuple[str, str], ...]

    def asyncpg_connect_args(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "user": self.username,
            "password": self.password,
            "host": self.host,
            "database": self.database,
        }
        if self.port is not None:
            result["port"] = self.port
        result.update(self.sqlalchemy_connect_args())
        return result

    def sqlalchemy_url(self) -> URL:
        return URL.create(
            "postgresql+asyncpg",
            username=self.username,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
        )

    def sqlalchemy_connect_args(self) -> dict[str, Any]:
        query = dict(self.query)
        result: dict[str, Any] = {}
        ssl_mode = query.pop("sslmode", query.pop("ssl", None))
        if ssl_mode is not None:
            result["ssl"] = ssl_mode
        target_session_attrs = query.pop("target_session_attrs", None)
        if target_session_attrs is not None:
            result["target_session_attrs"] = target_session_attrs
        if query:
            result["server_settings"] = query
        return result


def parse_postgres_dsn(raw_url: str) -> PostgresDsn:
    try:
        scheme, separator, remainder = raw_url.partition("://")
        if separator != "://" or scheme not in {"postgres", "postgresql"}:
            raise ValueError
        if "#" in remainder:
            raise ValueError
        authority_and_path, query_separator, raw_query = remainder.partition("?")
        credential_separator = authority_and_path.rfind("@")
        if credential_separator <= 0:
            raise ValueError
        userinfo = authority_and_path[:credential_separator]
        destination = authority_and_path[credential_separator + 1 :]
        path_separator = destination.find("/")
        if path_separator <= 0:
            raise ValueError
        hostinfo = destination[:path_separator]
        raw_database = destination[path_separator + 1 :]
        if not raw_database or "/" in raw_database:
            raise ValueError

        raw_username, password_separator, raw_password = userinfo.partition(":")
        username = unquote(raw_username)
        password = unquote(raw_password) if password_separator else None
        database = unquote(raw_database)
        parsed_host = urlsplit(f"//{hostinfo}")
        host = parsed_host.hostname
        port = parsed_host.port
        if not username or not host or not database or parsed_host.path:
            raise ValueError

        query = (
            tuple(parse_qsl(raw_query, keep_blank_values=True, strict_parsing=True))
            if query_separator
            else ()
        )
        query_keys = [key for key, _ in query]
        if len(query_keys) != len(set(query_keys)):
            raise ValueError
        if set(query_keys) & {
            "host",
            "port",
            "user",
            "password",
            "database",
            "dbname",
            "passfile",
            "sslcert",
            "sslkey",
            "sslrootcert",
            "sslcrl",
            "sslpassword",
        }:
            raise ValueError
        if "ssl" in query_keys and "sslmode" in query_keys:
            raise ValueError
        return PostgresDsn(username, password, host, port, database, query)
    except (AttributeError, TypeError, ValueError):
        raise PostgresDsnError("Invalid PostgreSQL URL") from None
