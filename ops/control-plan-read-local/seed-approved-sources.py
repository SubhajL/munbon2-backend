#!/usr/bin/env python3
"""Seed deterministic LOCAL-AC-1 inputs into the disposable local database."""

from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5

SCENARIO_VERSION = "local-ac-1-v5"
SOURCE_TABLES = (
    "gis.zone",
    "water_planning.zone_planting_dates",
    "ros_gis.section_crop_settings",
    "ros.eto_monthly",
    "ros.kc_weekly",
    "ros.effective_rainfall_monthly",
)


class ApprovedSourceError(RuntimeError):
    """The deterministic local source contract was not satisfied."""


def load_manifest(path: Path) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ApprovedSourceError("approved_manifest_invalid") from exc
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: dict) -> None:
    expected_keys = {
        "project_key",
        "section_master",
        "scada",
        "annual_plan",
        "crosswalk",
    }
    crosswalk = manifest.get("crosswalk") if isinstance(manifest, dict) else None
    section_master = (
        manifest.get("section_master", {}) if isinstance(manifest, dict) else {}
    )
    excel_overrides = section_master.get("excel_overrides")
    gis_expected_areas = section_master.get("gis_expected_areas")
    try:
        excel_numbers, excel_total = _validated_area_rows(
            excel_overrides,
            {
                "section_number",
                "source_row",
                "canal_name",
                "start_km",
                "end_km",
                "area_rai",
            },
        )
        gis_numbers, gis_total = _validated_area_rows(
            gis_expected_areas,
            {"section_number", "area_rai"},
        )
        crosswalk_numbers = [int(row["section_number"]) for row in crosswalk]
        source_rows = [int(row["source_row"]) for row in excel_overrides]
    except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
        raise ApprovedSourceError("approved_manifest_invalid") from exc
    if (
        set(manifest) != expected_keys
        or manifest.get("project_key") != "mun-bon"
        or section_master.get("section_count") != 41
        or section_master.get("total_area_rai") != "45204"
        or not isinstance(crosswalk, list)
        or len(crosswalk_numbers) != 41
        or set(crosswalk_numbers) != set(range(3, 44))
        or excel_numbers != set(range(3, 35))
        or gis_numbers != set(range(35, 44))
        or len(source_rows) != len(set(source_rows))
        or excel_total != Decimal("40120")
        or gis_total != Decimal("5084")
        or excel_total + gis_total != Decimal("45204")
    ):
        raise ApprovedSourceError("approved_manifest_invalid")


def _validated_area_rows(rows, expected_keys: set[str]) -> tuple[set[int], Decimal]:
    if not isinstance(rows, list):
        raise ApprovedSourceError("approved_manifest_invalid")
    section_numbers: list[int] = []
    total = Decimal("0")
    for row in rows:
        if not isinstance(row, dict) or set(row) != expected_keys:
            raise ApprovedSourceError("approved_manifest_invalid")
        section_number = int(row["section_number"])
        area_rai = Decimal(str(row["area_rai"]))
        if area_rai <= 0:
            raise ApprovedSourceError("approved_manifest_invalid")
        if "source_row" in row:
            start_match = re.fullmatch(r"(\d+)\+(\d{3})", str(row["start_km"]))
            end_match = re.fullmatch(r"(\d+)\+(\d{3})", str(row["end_km"]))
            if start_match is None or end_match is None:
                raise ApprovedSourceError("approved_manifest_invalid")
            start_metres = int(start_match.group(1)) * 1000 + int(start_match.group(2))
            end_metres = int(end_match.group(1)) * 1000 + int(end_match.group(2))
            if (
                int(row["source_row"]) <= 0
                or not str(row["canal_name"]).strip()
                or start_metres >= end_metres
            ):
                raise ApprovedSourceError("approved_manifest_invalid")
        section_numbers.append(section_number)
        total += area_rai
    if len(section_numbers) != len(set(section_numbers)):
        raise ApprovedSourceError("approved_manifest_invalid")
    return set(section_numbers), total


def _zone_for_section(section_number: int) -> int:
    for upper_bound, zone in ((7, 1), (14, 2), (19, 3), (26, 4), (34, 5)):
        if section_number <= upper_bound:
            return zone
    return 6


def _content_sha256(document: dict) -> str:
    encoded = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_approved_source_scenario(manifest: dict, as_of_date: date) -> dict:
    crosswalk = sorted(manifest["crosswalk"], key=lambda row: row["section_number"])
    areas = {
        int(row["section_number"]): int(row["area_rai"])
        for source in ("excel_overrides", "gis_expected_areas")
        for row in manifest["section_master"][source]
    }
    captured_at = datetime.combine(
        as_of_date, time(hour=0), tzinfo=timezone.utc
    ).isoformat()
    planting_date = as_of_date - timedelta(days=14)
    harvest_date = as_of_date + timedelta(days=98)
    sections = []
    crop_settings = []
    for mapping in crosswalk:
        section_number = mapping["section_number"]
        zone = _zone_for_section(section_number)
        section_id = f"01-{zone:02d}-01-{section_number:02d}"
        area = str(areas[section_number])
        planted_area = str(min(100, areas[section_number]))
        section_harvest_date = (
            harvest_date if section_number == 36 else as_of_date - timedelta(days=1)
        )
        sections.append(
            {
                "code": section_id,
                "props": {
                    "Zone": f"Zone{zone}",
                    "Area_Rai": area,
                    "Crop_1": "rice",
                    "NameArea": mapping["irrigation_channel"],
                    "GateId": mapping["gate_id"],
                    "IrrigationChannel": mapping["irrigation_channel"],
                },
                "create_date": captured_at,
            }
        )
        crop_settings.append(
            {
                "setting_id": str(
                    uuid5(
                        NAMESPACE_URL,
                        f"{SCENARIO_VERSION}:{as_of_date}:{section_id}",
                    )
                ),
                "section_id": section_id,
                "crop_type": "rice",
                "planted_area_rai": planted_area,
                "expected_harvest_date": section_harvest_date.isoformat(),
                "source": SCENARIO_VERSION,
                "as_of_date": as_of_date.isoformat(),
                "updated_by": "local-acceptance-operator",
            }
        )
    tables = {
        "gis.zone": sections,
        "water_planning.zone_planting_dates": [
            {
                "project_key": manifest["project_key"],
                "zone_number": zone,
                "planting_date": planting_date.isoformat(),
                "updated_by": "local-acceptance-operator",
                "updated_at": captured_at,
            }
            for zone in range(1, 7)
        ],
        "ros_gis.section_crop_settings": crop_settings,
        "ros.eto_monthly": [
            {"month": month, "eto_value": "93", "updated_at": captured_at}
            for month in range(1, 13)
        ],
        "ros.kc_weekly": [
            {
                "crop_type": "rice",
                "crop_week": crop_week,
                "kc_value": "1.1",
                "updated_at": captured_at,
            }
            for crop_week in range(1, 21)
        ],
        "ros.effective_rainfall_monthly": [
            {
                "crop_type": "rice",
                "month": month,
                "effective_rainfall_mm": "31",
                "updated_at": captured_at,
            }
            for month in range(1, 13)
        ],
    }
    document = {
        "scenario_version": SCENARIO_VERSION,
        "local_only": True,
        "as_of_date": as_of_date.isoformat(),
        "tables": tables,
    }
    return {**document, "content_sha256": _content_sha256(document)}


def validate_local_postgres_url(postgres_url: str) -> str:
    parsed = urlsplit(postgres_url)
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or parsed.hostname != "127.0.0.1"
        or parsed.port not in {None, 5432}
        or not parsed.username
        or parsed.password is None
        or unquote(parsed.path.lstrip("/")) != "munbon_local"
        or parsed.query
        or parsed.fragment
    ):
        raise ApprovedSourceError("local_postgres_url_not_accepted")
    return postgres_url


async def _seed_connection(connection, scenario: dict) -> None:
    await connection.execute(
        """
        CREATE SCHEMA IF NOT EXISTS gis;
        CREATE SCHEMA IF NOT EXISTS water_planning;
        CREATE SCHEMA IF NOT EXISTS ros;
        CREATE TABLE IF NOT EXISTS gis.zone (
            code TEXT PRIMARY KEY,
            props JSONB NOT NULL,
            create_date TIMESTAMPTZ NOT NULL
        );
        ALTER TABLE gis.zone
            ADD COLUMN IF NOT EXISTS geom geometry(MULTIPOLYGON, 4326);
        CREATE TABLE IF NOT EXISTS water_planning.zone_planting_dates (
            project_key TEXT NOT NULL,
            zone_number INTEGER NOT NULL CHECK (zone_number BETWEEN 1 AND 6),
            planting_date DATE NOT NULL,
            updated_by TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (project_key, zone_number)
        );
        CREATE TABLE IF NOT EXISTS ros.eto_monthly (
            month INTEGER PRIMARY KEY CHECK (month BETWEEN 1 AND 12),
            eto_value NUMERIC NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ros.kc_weekly (
            crop_type TEXT NOT NULL,
            crop_week INTEGER NOT NULL CHECK (crop_week > 0),
            kc_value NUMERIC NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (crop_type, crop_week)
        );
        CREATE TABLE IF NOT EXISTS ros.effective_rainfall_monthly (
            crop_type TEXT NOT NULL,
            month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
            effective_rainfall_mm NUMERIC NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (crop_type, month)
        );
        """
    )
    tables = scenario["tables"]
    await connection.executemany(
        """
        INSERT INTO gis.zone (code, props, create_date)
        VALUES ($1, $2::jsonb, $3)
        ON CONFLICT (code) DO UPDATE
        SET props = EXCLUDED.props, create_date = EXCLUDED.create_date
        """,
        [
            (
                row["code"],
                json.dumps(row["props"], ensure_ascii=False, sort_keys=True),
                datetime.fromisoformat(row["create_date"]),
            )
            for row in tables["gis.zone"]
        ],
    )
    await connection.executemany(
        """
        INSERT INTO water_planning.zone_planting_dates (
            project_key, zone_number, planting_date, updated_by, updated_at
        ) VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (project_key, zone_number) DO UPDATE
        SET planting_date = EXCLUDED.planting_date,
            updated_by = EXCLUDED.updated_by,
            updated_at = EXCLUDED.updated_at
        """,
        [
            (
                row["project_key"],
                row["zone_number"],
                date.fromisoformat(row["planting_date"]),
                row["updated_by"],
                datetime.fromisoformat(row["updated_at"]),
            )
            for row in tables["water_planning.zone_planting_dates"]
        ],
    )
    await connection.executemany(
        """
        INSERT INTO ros_gis.section_crop_settings (
            setting_id, section_id, crop_type, planted_area_rai,
            expected_harvest_date, source, as_of_date, updated_by
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (setting_id) DO NOTHING
        """,
        [
            (
                UUID(row["setting_id"]),
                row["section_id"],
                row["crop_type"],
                Decimal(row["planted_area_rai"]),
                date.fromisoformat(row["expected_harvest_date"]),
                row["source"],
                date.fromisoformat(row["as_of_date"]),
                row["updated_by"],
            )
            for row in tables["ros_gis.section_crop_settings"]
        ],
    )
    await connection.executemany(
        """
        INSERT INTO ros.eto_monthly (month, eto_value, updated_at)
        VALUES ($1, $2, $3)
        ON CONFLICT (month) DO UPDATE
        SET eto_value = EXCLUDED.eto_value, updated_at = EXCLUDED.updated_at
        """,
        [
            (
                row["month"],
                Decimal(row["eto_value"]),
                datetime.fromisoformat(row["updated_at"]),
            )
            for row in tables["ros.eto_monthly"]
        ],
    )
    await connection.executemany(
        """
        INSERT INTO ros.kc_weekly (crop_type, crop_week, kc_value, updated_at)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (crop_type, crop_week) DO UPDATE
        SET kc_value = EXCLUDED.kc_value, updated_at = EXCLUDED.updated_at
        """,
        [
            (
                row["crop_type"],
                row["crop_week"],
                Decimal(row["kc_value"]),
                datetime.fromisoformat(row["updated_at"]),
            )
            for row in tables["ros.kc_weekly"]
        ],
    )
    await connection.executemany(
        """
        INSERT INTO ros.effective_rainfall_monthly (
            crop_type, month, effective_rainfall_mm, updated_at
        ) VALUES ($1, $2, $3, $4)
        ON CONFLICT (crop_type, month) DO UPDATE
        SET effective_rainfall_mm = EXCLUDED.effective_rainfall_mm,
            updated_at = EXCLUDED.updated_at
        """,
        [
            (
                row["crop_type"],
                row["month"],
                Decimal(row["effective_rainfall_mm"]),
                datetime.fromisoformat(row["updated_at"]),
            )
            for row in tables["ros.effective_rainfall_monthly"]
        ],
    )


async def seed_approved_sources(postgres_url: str, scenario: dict) -> dict:
    validate_local_postgres_url(postgres_url)
    try:
        import asyncpg

        connection = await asyncpg.connect(postgres_url)
        try:
            async with connection.transaction():
                await _seed_connection(connection, scenario)
        finally:
            await connection.close()
    except ApprovedSourceError:
        raise
    except Exception as exc:
        raise ApprovedSourceError("approved_source_seed_failed") from exc
    return {
        "scenario_version": scenario["scenario_version"],
        "content_sha256": scenario["content_sha256"],
        "section_count": len(scenario["tables"]["gis.zone"]),
        "total_area_rai": str(
            sum(
                Decimal(row["props"]["Area_Rai"])
                for row in scenario["tables"]["gis.zone"]
            )
        ),
        "tables": list(scenario["tables"]),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of-date", type=date.fromisoformat, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    postgres_url = os.environ.get("LOCAL_ACCEPTANCE_POSTGRES_URL", "")
    try:
        scenario = build_approved_source_scenario(
            load_manifest(args.manifest), args.as_of_date
        )
        result = asyncio.run(seed_approved_sources(postgres_url, scenario))
    except ApprovedSourceError as exc:
        print(f"FAIL approved_sources: {exc}")
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
