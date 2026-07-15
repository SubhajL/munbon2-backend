from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from services.requirement_source_loader import (
    AuthoritativeRequirementSourceLoader,
    RequirementSourceError,
    build_requirement_snapshot,
    load_requirement_source_manifest,
)

UTC = timezone.utc
CUTOFF = datetime(2026, 7, 16, 1, tzinfo=UTC)


def _zone(number: int) -> int:
    if number <= 7:
        return 1
    if number <= 14:
        return 2
    if number <= 19:
        return 3
    if number <= 26:
        return 4
    if number <= 34:
        return 5
    return 6


def _gis_sections():
    rows = []
    for number in range(3, 44):
        area = Decimal("47345") if number == 43 else Decimal("1")
        rows.append(
            {
                "code": f"01-{_zone(number):02}-01-{number:02}",
                "zone": f"Zone{_zone(number)}",
                "area_rai": area,
                "crop_type": None if number == 15 else "นาข้าว",
                "name_area": f"section {number}",
                "create_date": datetime(2026, 7, 14),
            }
        )
    return rows


def _planting_dates():
    return [
        {
            "project_key": "mun-bon",
            "zone_number": zone,
            "planting_date": date(2026, 7, zone),
            "updated_by": "operator",
            "updated_at": CUTOFF,
        }
        for zone in range(1, 7)
    ]


def _build(**overrides):
    values = {
        "gis_sections": _gis_sections(),
        "planting_dates": _planting_dates(),
        "crop_settings": [],
        "eto_rows": [{"month": 7, "eto_value": Decimal("93"), "updated_at": CUTOFF}],
        "kc_rows": [
            {
                "crop_type": "rice",
                "crop_week": week,
                "kc_value": Decimal("1.2"),
                "updated_at": CUTOFF,
            }
            for week in (1, 2)
        ],
        "rainfall_rows": [
            {
                "crop_type": "rice",
                "month": 7,
                "effective_rainfall_mm": Decimal("31"),
                "updated_at": CUTOFF,
            }
        ],
        "manifest": load_requirement_source_manifest(),
        "section_dataset_version_id": 11,
        "gate_mapping_dataset_version_id": 12,
        "input_cutoff_at": CUTOFF,
    }
    values.update(overrides)
    return build_requirement_snapshot(**values)


def test_approved_manifest_pins_d1_d3_d4_and_explicit_tail_crosswalk():
    manifest = load_requirement_source_manifest()

    assert manifest["section_master"] == {
        "source": "postgres.gis.zone",
        "area_field": "props.Area_Rai",
        "section_count": 41,
        "total_area_rai": "47385",
    }
    assert manifest["annual_plan"]["sheet"] == "แผนการส่งน้ำ 1-6"
    assert manifest["annual_plan"]["rate_unit"] == "m3/s"
    assert {row["section_number"] for row in manifest["crosswalk"]} == set(range(3, 44))
    tail = next(row for row in manifest["crosswalk"] if row["section_number"] == 43)
    assert tail == {
        "section_number": 43,
        "gate_id": "M(0,1;1,1;1,4)",
        "irrigation_channel": "4L-RMC",
    }


def test_build_snapshot_uses_gis_identity_area_and_zone_planting_date_per_section():
    snapshot = _build()

    assert len(snapshot.sections) == 41
    assert sum(section.area_rai for section in snapshot.sections) == Decimal("47385")
    section = next(
        item for item in snapshot.sections if item.section_id.endswith("-03")
    )
    assert section.zone == 1
    assert section.crop_type == "rice"
    assert section.planting_date == date(2026, 7, 1)
    assert section.expected_harvest_date == date(2026, 7, 14)
    assert section.delivery_gate == "M(0,2)"
    assert section.source == "gis.zone+water_planning.zone_planting_dates"
    missing_crop = next(
        item for item in snapshot.sections if item.section_id.endswith("-15")
    )
    assert missing_crop.crop_type is None
    assert missing_crop.expected_harvest_date is None


def test_build_snapshot_applies_section_level_fe_crop_and_planted_area_override():
    settings = [
        {
            "section_id": "01-01-01-03",
            "crop_type": "corn",
            "planted_area_rai": Decimal("0.75"),
            "expected_harvest_date": date(2026, 10, 1),
            "source": "operator-fe",
            "as_of_date": date(2026, 7, 15),
        }
    ]
    snapshot = _build(
        crop_settings=settings,
        kc_rows=[
            {
                "crop_type": "corn",
                "crop_week": 1,
                "kc_value": Decimal("1.1"),
                "updated_at": CUTOFF,
            },
            {
                "crop_type": "rice",
                "crop_week": 1,
                "kc_value": Decimal("1.2"),
                "updated_at": CUTOFF,
            },
        ],
    )

    section = next(
        item for item in snapshot.sections if item.section_id.endswith("-03")
    )
    assert (
        section.crop_type,
        section.area_rai,
        section.expected_harvest_date,
        section.source,
        section.as_of_date,
    ) == (
        "corn",
        Decimal("0.75"),
        date(2026, 10, 1),
        "operator-fe",
        date(2026, 7, 15),
    )


@pytest.mark.parametrize(
    "gis_sections",
    [
        lambda rows: rows[:-1],
        lambda rows: [*rows, rows[0]],
        lambda rows: [{**row, "area_rai": Decimal("1")} for row in rows],
    ],
)
def test_build_snapshot_rejects_unapproved_section_count_identity_or_area(gis_sections):
    with pytest.raises(RequirementSourceError, match="approved GIS section master"):
        _build(gis_sections=gis_sections(_gis_sections()))


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _SourceConnection:
    def __init__(self, planting_dates=None):
        self.queries = []
        self.planting_dates = planting_dates or _planting_dates()

    async def fetch(self, sql, *args):
        self.queries.append((sql, args))
        if "FROM gis.zone" in sql:
            return _gis_sections()
        if "FROM water_planning.zone_planting_dates" in sql:
            return self.planting_dates
        raise AssertionError(f"unexpected source query: {sql}")


class _LocalConnection:
    def __init__(self):
        self.queries = []
        self.executions = []
        self.batches = []
        self.next_dataset_id = 100

    async def fetch(self, sql, *args):
        self.queries.append((sql, args))
        if "section_crop_settings" in sql:
            return []
        if "ros.eto_monthly" in sql:
            return [{"month": 7, "eto_value": Decimal("93"), "updated_at": CUTOFF}]
        if "ros.kc_weekly" in sql:
            return [
                {
                    "crop_type": "rice",
                    "crop_week": week,
                    "kc_value": Decimal("1.2"),
                    "updated_at": CUTOFF,
                }
                for week in (1, 2)
            ]
        if "ros.effective_rainfall_monthly" in sql:
            return [
                {
                    "crop_type": "rice",
                    "month": 7,
                    "effective_rainfall_mm": Decimal("31"),
                    "updated_at": CUTOFF,
                }
            ]
        raise AssertionError(f"unexpected local query: {sql}")

    async def fetchrow(self, sql, *args):
        self.queries.append((sql, args))
        if "FROM ros_gis.dataset_versions" in sql:
            return None
        raise AssertionError(f"unexpected local query: {sql}")

    async def fetchval(self, sql, *args):
        self.executions.append((sql, args))
        self.next_dataset_id += 1
        return self.next_dataset_id

    async def execute(self, sql, *args):
        self.executions.append((sql, args))

    async def executemany(self, sql, args):
        self.batches.append((sql, list(args)))

    def transaction(self):
        return _Transaction()


@pytest.mark.asyncio
async def test_authoritative_loader_reads_exact_sources_and_activates_immutable_datasets():
    source = _SourceConnection()
    local = _LocalConnection()

    @asynccontextmanager
    async def source_connection():
        yield source

    snapshot = await AuthoritativeRequirementSourceLoader(source_connection).load(
        local, date(2026, 7, 16), CUTOFF
    )

    assert (
        snapshot.section_dataset_version_id,
        snapshot.gate_mapping_dataset_version_id,
    ) == (
        101,
        102,
    )
    assert any("FROM gis.zone" in sql for sql, _ in source.queries)
    assert any(
        "FROM water_planning.zone_planting_dates" in sql for sql, _ in source.queries
    )
    assert any("ros.eto_monthly" in sql for sql, _ in local.queries)
    assert len(local.batches) == 2
    assert "section_master_history" in local.batches[0][0]
    assert len(local.batches[0][1]) == 41
    assert "gate_mapping_history" in local.batches[1][0]
    assert len(local.batches[1][1]) == 41


@pytest.mark.asyncio
async def test_authoritative_loader_rejects_stale_operator_crop_inputs():
    stale = [
        {**row, "updated_at": datetime(2026, 7, 14, 1, tzinfo=UTC)}
        for row in _planting_dates()
    ]
    source = _SourceConnection(stale)

    @asynccontextmanager
    async def source_connection():
        yield source

    loader = AuthoritativeRequirementSourceLoader(
        source_connection, max_input_age_hours=24
    )

    with pytest.raises(RequirementSourceError, match="older than 24 hours"):
        await loader.load(_LocalConnection(), date(2026, 7, 16), CUTOFF)
