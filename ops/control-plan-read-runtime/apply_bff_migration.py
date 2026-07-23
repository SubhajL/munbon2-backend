#!/usr/bin/env python3
"""Apply the BFF's idempotent tracked SQL migration using canonical DSN args."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from pathlib import Path

RUNTIME_DIR = Path(__file__).resolve().parent
REPO_ROOT = RUNTIME_DIR.parents[1]
BFF_ROOT = REPO_ROOT / "services" / "bff-water-planning"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


async def apply() -> None:
    import asyncpg

    migration_runner = _load_module(
        "bff_migration_runner",
        BFF_ROOT / "src" / "db" / "migration_runner.py",
    )
    postgres_dsn = _load_module(
        "bff_postgres_dsn",
        BFF_ROOT / "src" / "db" / "postgres_dsn.py",
    )

    url = os.environ.get("POSTGRES_URL")
    if not url:
        raise RuntimeError
    dsn = postgres_dsn.parse_postgres_dsn(url)
    connection = await asyncpg.connect(**dsn.asyncpg_connect_args())
    try:
        await migration_runner.apply_migrations(
            connection,
            BFF_ROOT / "migrations",
        )
    finally:
        await connection.close()


def main() -> int:
    try:
        asyncio.run(apply())
    except Exception as error:
        print(f"BFF migration failed: {type(error).__name__}")
        return 1
    print("BFF migrations applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
