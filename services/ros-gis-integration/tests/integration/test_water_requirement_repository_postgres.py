"""PostgreSQL contract test for migration-owned requirement publication tables."""

import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import ANY
from uuid import uuid4

import asyncpg
import pytest

from db.water_requirement_repository import (
    fail_requirement_run,
    get_daily_requirements,
    get_published_requirements,
    get_section_requirement_history,
    publish_requirement_run,
    start_requirement_run,
)

POSTGRES_URL = os.environ.get("WATER_REQUIREMENT_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="WATER_REQUIREMENT_TEST_POSTGRES_URL is not configured",
)
UTC = timezone.utc
AS_OF = date(2026, 7, 16)


def _instant(hour: int) -> datetime:
    return datetime(2026, 7, 16, hour, tzinfo=UTC)


def _requirement(requirement_id, volume: str, content_hash: str) -> dict:
    return {
        "requirement_id": requirement_id,
        "service_date": AS_OF,
        "zone": 1,
        "section_id": "section-1",
        "required_net_volume_m3": Decimal(volume),
        "required_gross_volume_m3": Decimal(volume) + Decimal("200.000000"),
        "delivery_window_start": _instant(6),
        "delivery_window_end": _instant(18),
        "quality": "estimated",
        "input_versions": {"crop": "crop-2026-07-16"},
        "content_hash": content_hash,
    }


@pytest.mark.asyncio
async def test_publication_is_immutable_and_correction_replaces_only_current_read():
    conn = await asyncpg.connect(POSTGRES_URL)
    transaction = conn.transaction()
    await transaction.start()
    try:
        section_version_id = await conn.fetchval(
            """
            INSERT INTO ros_gis.dataset_versions (dataset_kind, source_hash)
            VALUES ('section_master', $1)
            RETURNING dataset_version_id
            """,
            "1" * 64,
        )
        mapping_version_id = await conn.fetchval(
            """
            INSERT INTO ros_gis.dataset_versions (dataset_kind, source_hash)
            VALUES ('gate_crosswalk', $1)
            RETURNING dataset_version_id
            """,
            "2" * 64,
        )
        run_args = {
            "as_of_date": AS_OF,
            "horizon_start": AS_OF,
            "horizon_end": AS_OF + timedelta(days=6),
            "input_cutoff_at": _instant(1),
            "section_dataset_version_id": section_version_id,
            "gate_mapping_dataset_version_id": mapping_version_id,
            "crop_register_version": "crop-2026-07-16",
            "weather_version": "weather-2026-07-16T01:00Z",
            "method_version": "daily-requirement-v1",
        }

        first = await start_requirement_run(
            conn,
            **run_args,
            content_hash="a" * 64,
            computed_at=_instant(2),
        )
        first_requirement = _requirement(uuid4(), "800.000000", "a" * 64)
        contribution = {
            "requirement_id": first_requirement["requirement_id"],
            "area_id": "plot-1",
            "area_rai": Decimal("20.000000"),
            "crop_type": "rice",
            "crop_stage": "vegetative",
            "net_volume_m3": Decimal("800.000000"),
            "source_payload_hash": "3" * 64,
        }
        await publish_requirement_run(
            conn,
            first["run_id"],
            [first_requirement],
            [contribution],
            published_at=_instant(3),
        )

        with pytest.raises(asyncpg.RaiseError, match="immutable"):
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE ros_gis.daily_water_requirements
                    SET required_net_volume_m3 = 0
                    WHERE requirement_id = $1
                    """,
                    first_requirement["requirement_id"],
                )

        with pytest.raises(asyncpg.RaiseError, match="calculating"):
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO ros_gis.water_requirement_contributions (
                        requirement_id, area_id, area_rai, crop_type, crop_stage,
                        net_volume_m3, source_payload_hash
                    ) VALUES ($1, 'late-plot', 1, 'rice', 'vegetative', 0, $2)
                    """,
                    first_requirement["requirement_id"],
                    "4" * 64,
                )

        empty = await start_requirement_run(
            conn,
            **run_args,
            content_hash="d" * 64,
            computed_at=_instant(4),
        )
        with pytest.raises(asyncpg.RaiseError, match="at least one"):
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE ros_gis.water_requirement_runs
                    SET status = 'published', published_at = $2
                    WHERE run_id = $1
                    """,
                    empty["run_id"],
                    _instant(5),
                )

        second = await start_requirement_run(
            conn,
            **run_args,
            content_hash="b" * 64,
            computed_at=_instant(4),
        )
        second_requirement = _requirement(uuid4(), "900.000000", "b" * 64)
        await publish_requirement_run(
            conn,
            second["run_id"],
            [second_requirement],
            published_at=_instant(5),
        )
        with pytest.raises(asyncpg.UniqueViolationError):
            async with conn.transaction():
                await start_requirement_run(
                    conn,
                    **run_args,
                    content_hash="a" * 64,
                    computed_at=_instant(6),
                )
        failed = await start_requirement_run(
            conn,
            **run_args,
            content_hash="c" * 64,
            computed_at=_instant(6),
        )
        await fail_requirement_run(conn, failed["run_id"], "weather unavailable")

        assert (
            await conn.fetchval(
                "SELECT status FROM ros_gis.water_requirement_runs WHERE run_id = $1",
                first["run_id"],
            )
            == "superseded"
        )
        assert await get_published_requirements(conn, AS_OF) == [
            {
                **second_requirement,
                "run_id": second["run_id"],
                "as_of_date": AS_OF,
                "horizon_start": AS_OF,
                "horizon_end": AS_OF + timedelta(days=6),
                "input_cutoff_at": _instant(1),
                "section_dataset_version_id": section_version_id,
                "gate_mapping_dataset_version_id": mapping_version_id,
                "crop_register_version": "crop-2026-07-16",
                "weather_version": "weather-2026-07-16T01:00Z",
                "method_version": "daily-requirement-v1",
                "run_content_hash": "b" * 64,
                "computed_at": _instant(4),
                "published_at": _instant(5),
                "created_at": ANY,
            }
        ]
        assert await get_daily_requirements(conn, AS_OF, 1) == [
            {
                **second_requirement,
                "run_id": second["run_id"],
                "as_of_date": AS_OF,
                "published_at": _instant(5),
                "run_status": "published",
                "version": 2,
                "created_at": ANY,
            }
        ]
        assert await get_section_requirement_history(
            conn,
            "section-1",
            AS_OF,
            AS_OF,
        ) == [
            {
                **first_requirement,
                "run_id": first["run_id"],
                "as_of_date": AS_OF,
                "published_at": _instant(3),
                "run_status": "superseded",
                "version": 1,
                "created_at": ANY,
            },
            {
                **second_requirement,
                "run_id": second["run_id"],
                "as_of_date": AS_OF,
                "published_at": _instant(5),
                "run_status": "published",
                "version": 2,
                "created_at": ANY,
            },
        ]
    finally:
        await transaction.rollback()
        await conn.close()
