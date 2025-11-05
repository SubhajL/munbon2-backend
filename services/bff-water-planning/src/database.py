from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import asyncpg
import os


class Database:
    """
    Minimal async database helper for query modules.
    Exposes get_connection() used across API routes and queries.
    """

    def __init__(self, dsn: Optional[str] = None):
        # Prefer explicit DSN, otherwise build from environment
        self._dsn = dsn or os.getenv(
            "BFF_POSTGRES_URL",
            # Fallback to a common local-dev DSN if not provided via env
            f"postgresql://postgres:postgres@localhost:5432/postgres",
        )
        self._pool: Optional[asyncpg.Pool] = None

    async def _ensure_pool(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self._dsn, command_timeout=60)

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Async context manager that yields an asyncpg connection from a pool.
        """
        await self._ensure_pool()
        assert self._pool is not None
        conn = await self._pool.acquire()
        try:
            yield conn
        finally:
            await self._pool.release(conn)