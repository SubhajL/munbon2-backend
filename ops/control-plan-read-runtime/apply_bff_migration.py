#!/usr/bin/env python3
"""Apply the BFF's idempotent tracked SQL migration using canonical DSN args."""

from __future__ import annotations

import asyncio
import importlib.util
import os
from pathlib import Path


RUNTIME_DIR = Path(__file__).resolve().parent
REPO_ROOT = RUNTIME_DIR.parents[1]
BFF_ROOT = REPO_ROOT / "services" / "bff-water-planning"


def _load_parser():
    path = BFF_ROOT / "src" / "db" / "postgres_dsn.py"
    spec = importlib.util.spec_from_file_location("bff_postgres_dsn", path)
    if spec is None or spec.loader is None:
        raise RuntimeError
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse_postgres_dsn


async def apply() -> None:
    import asyncpg

    url = os.environ.get("POSTGRES_URL")
    if not url:
        raise RuntimeError
    parse_postgres_dsn = _load_parser()
    dsn = parse_postgres_dsn(url)
    sql = (BFF_ROOT / "migrations" / "009_crop_registry.sql").read_text(
        encoding="utf-8"
    )
    connection = await asyncpg.connect(**dsn.asyncpg_connect_args())
    try:
        async with connection.transaction():
            await connection.execute(sql)
    finally:
        await connection.close()


def main() -> int:
    try:
        asyncio.run(apply())
    except Exception as error:
        print(f"BFF migration failed: {type(error).__name__}")
        return 1
    print("BFF migration applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
