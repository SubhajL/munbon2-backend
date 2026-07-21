import os
import re

import asyncpg
import pytest

from db.postgres_dsn import parse_postgres_dsn


POSTGRES_URL = os.environ.get("POSTGRES_DSN_TEST_URL")


@pytest.mark.skipif(
    not POSTGRES_URL,
    reason="POSTGRES_DSN_TEST_URL is not configured",
)
@pytest.mark.asyncio
async def test_percent_encoded_credential_connects_without_dsn_rewrite():
    userinfo = POSTGRES_URL.split("://", 1)[1].rsplit("@", 1)[0]
    assert re.search(r"%[0-9A-Fa-f]{2}", userinfo)

    connection = await asyncpg.connect(
        **parse_postgres_dsn(POSTGRES_URL).asyncpg_connect_args()
    )
    try:
        assert await connection.fetchval("SELECT 1") == 1
    finally:
        await connection.close()
