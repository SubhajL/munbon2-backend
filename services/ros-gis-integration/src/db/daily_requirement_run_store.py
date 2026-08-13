"""PostgreSQL-backed orchestration adapter for the daily requirement job."""

import hashlib
from contextlib import asynccontextmanager

from db.water_requirement_repository import (
    fail_requirement_run,
    get_flow_records_for_run,
    publish_requirement_run,
    start_requirement_run,
)
from services.daily_requirement_producer import METHOD_VERSION

DAILY_REQUIREMENT_LOCK_ID = int.from_bytes(
    hashlib.sha256(b"ros_gis.daily_requirement_job").digest()[:8],
    "big",
    signed=True,
)


class SupersededRequirementRunError(ValueError):
    def __init__(self, as_of_date):
        self.as_of_date = as_of_date
        super().__init__(f"requirement lineage for {as_of_date} is superseded")


class PostgresDailyRequirementRunStore:
    def __init__(self, database_manager):
        self.database_manager = database_manager

    @asynccontextmanager
    async def locked_connection(self):
        async with self.database_manager.get_connection() as conn:
            await conn.execute("SELECT pg_advisory_lock($1)", DAILY_REQUIREMENT_LOCK_ID)
            try:
                yield conn
            finally:
                await conn.execute(
                    "SELECT pg_advisory_unlock($1)", DAILY_REQUIREMENT_LOCK_ID
                )

    async def find_matching_run(self, conn, as_of_date, content_hash):
        row = await conn.fetchrow(
            """
            SELECT run_id, as_of_date, content_hash, status
            FROM ros_gis.water_requirement_runs
            WHERE as_of_date = $1
              AND content_hash = $2
              AND status IN ('calculating', 'published', 'superseded')
            ORDER BY status = 'calculating' DESC,
                     status = 'published' DESC
            LIMIT 1
            """,
            as_of_date,
            content_hash,
        )
        if row is None:
            return None
        if row["status"] == "calculating":
            await fail_requirement_run(
                conn,
                row["run_id"],
                "recovered abandoned daily requirement calculation",
            )
            return None
        if row["status"] == "superseded":
            raise SupersededRequirementRunError(row["as_of_date"])
        return dict(row)

    async def start(
        self,
        conn,
        snapshot,
        as_of_date,
        horizon_end,
        content_hash,
        now,
    ):
        return await start_requirement_run(
            conn,
            as_of_date=as_of_date,
            horizon_start=as_of_date,
            horizon_end=horizon_end,
            input_cutoff_at=snapshot.input_cutoff_at,
            section_dataset_version_id=snapshot.section_dataset_version_id,
            gate_mapping_dataset_version_id=snapshot.gate_mapping_dataset_version_id,
            crop_register_version=snapshot.crop_register_version,
            weather_version=snapshot.weather_version,
            method_version=METHOD_VERSION,
            content_hash=content_hash,
            computed_at=now,
        )

    async def publish(self, conn, run, batch, now):
        await publish_requirement_run(
            conn,
            run["run_id"],
            [item.__dict__ for item in batch.requirements],
            [item.__dict__ for item in batch.contributions],
            published_at=now,
        )

    async def fail(self, conn, run_id, reason):
        return await fail_requirement_run(conn, run_id, reason)

    async def flow_records(self, conn, run_id):
        return await get_flow_records_for_run(conn, run_id)
