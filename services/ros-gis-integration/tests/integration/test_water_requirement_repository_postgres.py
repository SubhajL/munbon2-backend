"""PostgreSQL contract test for migration-owned requirement publication tables."""

import os
import json
import importlib.util
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import ANY
from uuid import uuid4

import asyncpg
import pytest

import services.requirement_source_loader as source_loader_module
from db.water_requirement_repository import (
    fail_requirement_run,
    get_daily_requirements,
    get_flow_records_for_run,
    get_published_requirements,
    get_section_requirement_history,
    publish_requirement_run,
    start_requirement_run,
)
from services.requirement_source_loader import (
    AuthoritativeRequirementSourceLoader,
    _activate_section_dataset,
    _effective_section_master,
    _section_dataset_hash,
    load_requirement_source_manifest,
)

POSTGRES_URL = os.environ.get("WATER_REQUIREMENT_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="WATER_REQUIREMENT_TEST_POSTGRES_URL is not configured",
)
UTC = timezone.utc
AS_OF = date(2026, 7, 16)
SEED_MODULE_PATH = (
    Path(__file__).resolve().parents[4]
    / "ops/control-plan-read-local/seed-approved-sources.py"
)
SEED_SPEC = importlib.util.spec_from_file_location(
    "local_approved_sources_integration", SEED_MODULE_PATH
)
assert SEED_SPEC is not None and SEED_SPEC.loader is not None
approved_sources = importlib.util.module_from_spec(SEED_SPEC)
SEED_SPEC.loader.exec_module(approved_sources)


class _CapturedSourceRows(RuntimeError):
    pass


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
async def test_source_loader_excludes_every_row_newer_than_input_cutoff(monkeypatch):
    conn = await asyncpg.connect(POSTGRES_URL)
    transaction = conn.transaction()
    await transaction.start()
    cutoff = _instant(1)
    before = cutoff - timedelta(seconds=1)
    after = cutoff + timedelta(seconds=1)
    try:
        await conn.execute("""
            CREATE SCHEMA gis;
            CREATE SCHEMA water_planning;
            CREATE SCHEMA ros;
            CREATE TABLE gis.zone (
                code TEXT PRIMARY KEY,
                props JSONB NOT NULL,
                geom geometry(POLYGON, 4326) NOT NULL,
                create_date TIMESTAMPTZ NOT NULL
            );
            CREATE TABLE water_planning.zone_planting_dates (
                project_key TEXT NOT NULL,
                zone_number INTEGER PRIMARY KEY,
                planting_date DATE NOT NULL,
                updated_by TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            );
            CREATE TABLE ros.eto_monthly (
                month INTEGER PRIMARY KEY,
                eto_value NUMERIC NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            );
            CREATE TABLE ros.kc_weekly (
                crop_type TEXT NOT NULL,
                crop_week INTEGER NOT NULL,
                kc_value NUMERIC NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (crop_type, crop_week)
            );
            CREATE TABLE ros.effective_rainfall_monthly (
                crop_type TEXT NOT NULL,
                month INTEGER NOT NULL,
                effective_rainfall_mm NUMERIC NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (crop_type, month)
            );
            """)
        await conn.execute(
            """
            INSERT INTO gis.zone (code, props, geom, create_date) VALUES
                ('before-zone', '{"Zone":"Zone1","Area_Rai":"1"}',
                 ST_GeomFromText('POLYGON((102 15,102.001 15,102.001 15.001,102 15.001,102 15))', 4326), $1),
                ('after-zone', '{"Zone":"Zone1","Area_Rai":"1"}',
                 ST_GeomFromText('POLYGON((102 15,102.001 15,102.001 15.001,102 15.001,102 15))', 4326), $2)
            """,
            before,
            after,
        )
        await conn.execute(
            """
            INSERT INTO water_planning.zone_planting_dates VALUES
                ('mun-bon', 1, $3, 'before', $1),
                ('mun-bon', 2, $3, 'after', $2)
            """,
            before,
            after,
            AS_OF,
        )
        await conn.execute(
            """
            INSERT INTO ros.eto_monthly VALUES
                (1, 10, $1), (2, 20, $2)
            """,
            before,
            after,
        )
        await conn.execute(
            """
            INSERT INTO ros.kc_weekly VALUES
                ('before', 1, 1, $1), ('after', 1, 2, $2)
            """,
            before,
            after,
        )
        await conn.execute(
            """
            INSERT INTO ros.effective_rainfall_monthly VALUES
                ('before', 1, 1, $1), ('after', 2, 2, $2)
            """,
            before,
            after,
        )
        await conn.executemany(
            """
            INSERT INTO ros_gis.section_crop_settings (
                setting_id, section_id, crop_type, planted_area_rai,
                expected_harvest_date, source, as_of_date, updated_by, created_at
            ) VALUES ($1, $2, 'rice', 1, $3, 'test', $3, 'test', $4)
            """,
            [
                (uuid4(), "before-section", AS_OF, before),
                (uuid4(), "after-section", AS_OF, after),
            ],
        )

        captured = {}

        def capture_rows(**rows):
            captured.update(rows)
            raise _CapturedSourceRows

        monkeypatch.setattr(
            source_loader_module, "_effective_section_master", lambda rows, _: rows
        )
        monkeypatch.setattr(
            source_loader_module, "build_requirement_snapshot", capture_rows
        )

        @asynccontextmanager
        async def source_connection():
            yield conn

        loader = AuthoritativeRequirementSourceLoader(source_connection, 24)
        with pytest.raises(_CapturedSourceRows):
            await loader.load(
                conn,
                source_effective_date=AS_OF,
                input_cutoff_at=cutoff,
            )

        assert {
            "gis": [row["code"] for row in captured["gis_sections"]],
            "planting": [row["updated_by"] for row in captured["planting_dates"]],
            "crop": [row["section_id"] for row in captured["crop_settings"]],
            "eto": [row["month"] for row in captured["eto_rows"]],
            "kc": [row["crop_type"] for row in captured["kc_rows"]],
            "rainfall": [row["crop_type"] for row in captured["rainfall_rows"]],
        } == {
            "gis": ["before-zone"],
            "planting": ["before"],
            "crop": ["before-section"],
            "eto": [1],
            "kc": ["before"],
            "rainfall": ["before"],
        }
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_v6_local_seed_replaces_legacy_fixture_before_source_load(monkeypatch):
    conn = await asyncpg.connect(POSTGRES_URL)
    transaction = conn.transaction()
    await transaction.start()
    try:
        await conn.execute(
            """
            INSERT INTO ros_gis.section_crop_settings (
                setting_id, section_id, crop_type, planted_area_rai,
                expected_harvest_date, source, as_of_date, updated_by, created_at
            ) VALUES ($1, '01-01-01-03', 'rice', 1, $2,
                      'local-ac-1-v5', $2, 'legacy-seeder', $3)
            """,
            uuid4(),
            AS_OF,
            _instant(2),
        )
        scenario = approved_sources.build_approved_source_scenario(
            approved_sources.load_manifest(
                Path(__file__).resolve().parents[2] / "data/requirement_sources.json"
            ),
            AS_OF,
        )

        await approved_sources._seed_connection(conn, scenario)

        captured = {}

        def capture_rows(**rows):
            captured.update(rows)
            raise _CapturedSourceRows

        monkeypatch.setattr(
            source_loader_module, "build_requirement_snapshot", capture_rows
        )

        @asynccontextmanager
        async def source_connection():
            yield conn

        loader = AuthoritativeRequirementSourceLoader(source_connection)
        with pytest.raises(_CapturedSourceRows):
            await loader.load(
                conn,
                source_effective_date=AS_OF,
                input_cutoff_at=_instant(0),
            )

        assert {row["source"] for row in captured["crop_settings"]} == {"local-ac-1-v6"}
        assert await conn.fetchval("""
            SELECT count(*)
            FROM ros_gis.section_crop_settings
            WHERE source = 'local-ac-1-v5'
            """) == 0
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_section_activation_preserves_real_postgis_geometry_and_hybrid_area():
    conn = await asyncpg.connect(POSTGRES_URL)
    transaction = conn.transaction()
    await transaction.start()
    try:
        await conn.execute("""
            CREATE SCHEMA gis;
            CREATE TABLE gis.zone (
                code TEXT PRIMARY KEY,
                props JSONB NOT NULL,
                geom geometry(POLYGON, 4326) NOT NULL,
                create_date TIMESTAMPTZ NOT NULL
            )
            """)
        manifest = load_requirement_source_manifest()
        expected_gis_areas = {
            int(row["section_number"]): row["area_rai"]
            for row in manifest["section_master"]["gis_expected_areas"]
        }
        expected_membership = {
            int(row["section_number"]): int(row["zone_number"])
            for row in manifest["section_master"]["section_memberships"]
        }
        source_rows = []
        for section_number in range(3, 44):
            zone = expected_membership[section_number]
            source_rows.append(
                (
                    f"01-{zone:02d}-01-{section_number:02d}",
                    json.dumps(
                        {
                            "Zone": f"Zone{zone}",
                            "Area_Rai": expected_gis_areas.get(section_number, "1"),
                            "Crop_1": "rice",
                            "NameArea": f"source-{section_number}",
                        }
                    ),
                    _instant(0),
                )
            )
        await conn.executemany(
            """
            INSERT INTO gis.zone (code, props, geom, create_date)
            VALUES (
                $1, $2::jsonb,
                ST_GeomFromText('POLYGON((102 15,102.001 15,102.001 15.001,102 15.001,102 15))', 4326),
                $3
            )
            """,
            source_rows,
        )
        raw = await conn.fetch("""
            SELECT code,
                   props->>'Zone' AS zone,
                   (props->>'Area_Rai')::numeric AS area_rai,
                   props->>'Crop_1' AS crop_type,
                   props->>'NameArea' AS name_area,
                   ST_AsEWKB(ST_Multi(geom)) AS geometry_wkb,
                   create_date
            FROM gis.zone
            ORDER BY code
            """)
        effective = _effective_section_master(raw, manifest)
        source_hash = _section_dataset_hash(raw, effective, manifest)

        await _activate_section_dataset(
            conn,
            effective,
            manifest,
            source_hash,
            _instant(0),
        )

        projection = await conn.fetchrow("""
            SELECT count(*) AS section_count,
                   sum(area_rai) AS total_area_rai,
                   min(GeometryType(geometry)) AS geometry_type
            FROM ros_gis.sections_current
            """)

        assert dict(projection) == {
            "section_count": 41,
            "total_area_rai": Decimal("45204.00"),
            "geometry_type": "MULTIPOLYGON",
        }
    finally:
        await transaction.rollback()
        await conn.close()


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
            **{**run_args, "method_version": "daily-requirement-v2"},
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
                "method_version": "daily-requirement-v2",
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
        flow_records = await get_flow_records_for_run(conn, second["run_id"])
        assert flow_records[0]["requirement_method_version"] == "daily-requirement-v2"
    finally:
        await transaction.rollback()
        await conn.close()
