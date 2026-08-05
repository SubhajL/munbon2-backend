from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
from pathlib import Path
import re
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest

from services.requirement_source_loader import (
    AuthoritativeRequirementSourceLoader,
    RequirementSourceError,
    _effective_section_master,
    _section_dataset_hash,
    build_requirement_snapshot,
    load_requirement_source_manifest,
)

UTC = timezone.utc
CUTOFF = datetime(2026, 7, 16, 1, tzinfo=UTC)
REPO_ROOT = Path(__file__).resolve().parents[4]
EXCEL_AREAS = {
    3: 972,
    4: 689,
    5: 1778,
    6: 2357,
    7: 1726,
    8: 693,
    9: 1434,
    10: 1527,
    11: 2611,
    12: 449,
    13: 65,
    14: 104,
    15: 2620,
    16: 1348,
    17: 5366,
    18: 760,
    19: 1133,
    20: 654,
    21: 503,
    22: 1907,
    23: 73,
    24: 2124,
    25: 1121,
    26: 1555,
    27: 139,
    28: 694,
    29: 813,
    30: 1009,
    31: 591,
    32: 686,
    33: 1185,
    34: 1434,
}
GIS_TAIL_AREAS = {
    35: 358,
    36: 995,
    37: 743,
    38: 1206,
    39: 229,
    40: 277,
    41: 193,
    42: 465,
    43: 618,
}
XLSX_NAMESPACE = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


class _RecordLike:
    def __init__(self, values):
        self.values = values

    def keys(self):
        return self.values.keys()

    def __getitem__(self, key):
        return self.values[key]


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
        area = Decimal(GIS_TAIL_AREAS.get(number, number * 100))
        rows.append(
            {
                "code": f"01-{_zone(number):02}-01-{number:02}",
                "zone": f"Zone{_zone(number)}",
                "area_rai": area,
                "crop_type": None if number == 15 else "นาข้าว",
                "name_area": f"section {number}",
                "geometry_wkb": b"test-geometry",
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


def _workbook_section_rows(workbook: Path, source_rows: set[int]) -> list[dict]:
    with ZipFile(workbook) as archive:
        shared_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        shared_strings = [
            "".join(node.text or "" for node in item.findall(".//x:t", XLSX_NAMESPACE))
            for item in shared_root.findall("x:si", XLSX_NAMESPACE)
        ]
        sheet_root = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    cells: dict[str, str] = {}
    for cell in sheet_root.findall(".//x:c", XLSX_NAMESPACE):
        value = cell.find("x:v", XLSX_NAMESPACE)
        if value is None:
            continue
        cells[cell.attrib["r"]] = (
            shared_strings[int(value.text)]
            if cell.attrib.get("t") == "s"
            else str(value.text)
        )

    rows = []
    for row_number in sorted(source_rows):
        start_km, end_km = (
            item.strip() for item in re.split(r"\s*-\s*", cells[f"D{row_number}"])
        )
        rows.append(
            {
                "section_number": int(Decimal(cells[f"C{row_number}"])),
                "source_row": row_number,
                "canal_name": cells[f"B{row_number}"].strip(),
                "start_km": start_km,
                "end_km": end_km,
                "area_rai": str(int(Decimal(cells[f"Q{row_number}"]))),
            }
        )
    return rows


def _build(**overrides):
    manifest = overrides.pop("manifest", load_requirement_source_manifest())
    gis_sections = overrides.pop("gis_sections", _gis_sections())
    values = {
        "gis_sections": _effective_section_master(gis_sections, manifest),
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
        "manifest": manifest,
        "section_dataset_version_id": 11,
        "gate_mapping_dataset_version_id": 12,
        "input_cutoff_at": CUTOFF,
    }
    values.update(overrides)
    return build_requirement_snapshot(**values)


def test_approved_manifest_pins_d1_d3_d4_and_explicit_tail_crosswalk():
    manifest = load_requirement_source_manifest()

    assert {
        key: value
        for key, value in manifest["section_master"].items()
        if key not in {"excel_overrides", "gis_expected_areas", "section_memberships"}
    } == {
        "identity_source": "postgres.gis.zone",
        "geometry_source": "postgres.gis.zone.geom",
        "gis_area_field": "props.Area_Rai",
        "excel_section_field": "Sheet1.C",
        "excel_canal_field": "Sheet1.B",
        "excel_span_field": "Sheet1.D",
        "excel_area_field": "Sheet1.Q",
        "excel_section_range": [3, 34],
        "gis_section_range": [35, 43],
        "section_count": 41,
        "total_area_rai": "45204",
    }
    overrides = manifest["section_master"]["excel_overrides"]
    gis_expected_areas = manifest["section_master"]["gis_expected_areas"]
    assert {row["section_number"] for row in overrides} == set(range(3, 35))
    assert sum(Decimal(row["area_rai"]) for row in overrides) == Decimal("40120")
    assert next(row for row in overrides if row["section_number"] == 21) == {
        "section_number": 21,
        "source_row": 43,
        "canal_name": "38R-LMC",
        "start_km": "1+720",
        "end_km": "3+000",
        "area_rai": "503",
    }
    assert {
        row["section_number"]: Decimal(row["area_rai"]) for row in gis_expected_areas
    } == {number: Decimal(area) for number, area in GIS_TAIL_AREAS.items()}
    assert {
        row["section_number"]: row["zone_number"]
        for row in manifest["section_master"]["section_memberships"]
    } == {number: _zone(number) for number in range(3, 44)}
    assert manifest["annual_plan"]["sheet"] == "แผนการส่งน้ำ 1-6"
    assert manifest["annual_plan"]["rate_unit"] == "m3/s"
    assert manifest["scada"] == {
        "file": "SCADA Section Detailed Information 2026-07-24 V5.0 SL.xlsx",
        "sheet": "Sheet1",
        "sha256": "bebf10a6b2b4ada2daac0615a453f38d374d9c84fcdc8d4d74983fc682589416",
    }
    assert {row["section_number"] for row in manifest["crosswalk"]} == set(range(3, 44))
    assert {
        row["section_number"]: row["gate_id"]
        for row in manifest["crosswalk"]
        if row["section_number"] >= 35
    } == {
        35: "M(0,0;2,0)",
        36: "M(0,0;2,1)",
        37: "M(0,0;2,2)",
        38: "M(0,0;2,3)",
        39: "M(0,0;2,1;1,0)",
        40: "M(0,0;2,1;1,1)",
        41: "M(0,0;2,1;1,2)",
        42: "M(0,0;2,1;1,3)",
        43: "M(0,0;2,1;1,4)",
    }


def test_approved_manifest_hash_matches_the_tracked_v5_workbook():
    manifest = load_requirement_source_manifest()
    workbook = (
        REPO_ROOT
        / "services/ros-gis-integration/data/sources"
        / manifest["scada"]["file"]
    )

    assert (
        hashlib.sha256(workbook.read_bytes()).hexdigest() == manifest["scada"]["sha256"]
    )
    overrides = manifest["section_master"]["excel_overrides"]
    assert {
        row["section_number"]: row
        for row in _workbook_section_rows(
            workbook,
            {int(row["source_row"]) for row in overrides},
        )
    } == {row["section_number"]: row for row in overrides}


def test_effective_section_master_uses_excel_03_34_and_gis_35_43_without_shifting():
    manifest = load_requirement_source_manifest()
    raw = _gis_sections()

    effective = _effective_section_master(raw, manifest)
    by_number = {int(row["code"].rsplit("-", 1)[1]): row for row in effective}

    assert len(effective) == 41
    assert sum(Decimal(row["area_rai"]) for row in effective) == Decimal("45204")
    assert {
        number: Decimal(by_number[number]["area_rai"]) for number in range(3, 35)
    } == {number: Decimal(area) for number, area in EXCEL_AREAS.items()}
    assert {
        number: Decimal(by_number[number]["area_rai"]) for number in range(35, 44)
    } == {number: Decimal(area) for number, area in GIS_TAIL_AREAS.items()}
    assert by_number[21] == {
        **raw[18],
        "area_rai": Decimal("503"),
        "name_area": "38R-LMC",
        "area_source": "scada_excel",
        "source_row": 43,
        "start_km": "1+720",
        "end_km": "3+000",
    }
    assert by_number[35] == {
        **raw[32],
        "area_source": "gis.zone",
    }


def test_build_snapshot_uses_hybrid_area_and_zone_planting_date_per_section():
    snapshot = _build()

    assert len(snapshot.sections) == 41
    assert sum(section.area_rai for section in snapshot.sections) == Decimal("45204")
    section = next(
        item for item in snapshot.sections if item.section_id.endswith("-03")
    )
    assert section.zone == 1
    assert section.crop_type == "rice"
    assert section.planting_date == date(2026, 7, 1)
    assert section.expected_harvest_date == date(2026, 7, 14)
    assert section.delivery_gate == "M(0,2)"
    assert section.source == "scada_excel+water_planning.zone_planting_dates"
    rmc = next(item for item in snapshot.sections if item.section_id.endswith("-35"))
    assert rmc.area_rai == Decimal("358")
    assert rmc.source == "gis.zone+water_planning.zone_planting_dates"
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


def test_build_snapshot_hashes_database_record_mappings_for_weather_lineage():
    expected = _build()

    actual = _build(
        eto_rows=[
            _RecordLike({"month": 7, "eto_value": Decimal("93"), "updated_at": CUTOFF})
        ],
        kc_rows=[
            _RecordLike(
                {
                    "crop_type": "rice",
                    "crop_week": week,
                    "kc_value": Decimal("1.2"),
                    "updated_at": CUTOFF,
                }
            )
            for week in (1, 2)
        ],
        rainfall_rows=[
            _RecordLike(
                {
                    "crop_type": "rice",
                    "month": 7,
                    "effective_rainfall_mm": Decimal("31"),
                    "updated_at": CUTOFF,
                }
            )
        ],
    )

    assert actual.weather_version == expected.weather_version


@pytest.mark.parametrize(
    "gis_sections",
    [
        lambda rows: rows[:-1],
        lambda rows: [*rows, rows[0]],
        lambda rows: [
            {**row, "code": "not-a-section"} if index == 0 else row
            for index, row in enumerate(rows)
        ],
    ],
)
def test_build_snapshot_rejects_unapproved_section_count_identity_or_area(gis_sections):
    with pytest.raises(RequirementSourceError, match="approved section master"):
        _build(gis_sections=gis_sections(_gis_sections()))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda rows: rows[:-1],
        lambda rows: [*rows, {**rows[0], "section_number": 34}],
        lambda rows: [
            {**row, "area_rai": "0"} if row["section_number"] == 21 else row
            for row in rows
        ],
    ],
)
def test_effective_section_master_rejects_incomplete_duplicate_or_nonpositive_excel_overrides(
    mutate,
):
    manifest = load_requirement_source_manifest()
    manifest["section_master"]["excel_overrides"] = mutate(
        manifest["section_master"]["excel_overrides"]
    )

    with pytest.raises(RequirementSourceError, match="Excel section overrides"):
        _effective_section_master(_gis_sections(), manifest)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda manifest: manifest["section_master"].pop("section_count"),
        lambda manifest: manifest["section_master"].update(
            {"excel_section_range": ["three", 34]}
        ),
        lambda manifest: manifest["crosswalk"][0].update({"section_number": "three"}),
    ],
)
def test_effective_section_master_rejects_malformed_authority_as_domain_error(mutate):
    manifest = load_requirement_source_manifest()
    mutate(manifest)

    with pytest.raises(RequirementSourceError, match="section authority"):
        _effective_section_master(_gis_sections(), manifest)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_row", 43),
        ("start_km", "7+000"),
        ("end_km", "1+000"),
        ("start_km", "1.720"),
    ],
)
def test_effective_section_master_rejects_duplicate_rows_or_invalid_chainage(
    field, value
):
    manifest = load_requirement_source_manifest()
    manifest["section_master"]["excel_overrides"][0][field] = value

    with pytest.raises(RequirementSourceError, match="Excel section overrides"):
        _effective_section_master(_gis_sections(), manifest)


def test_effective_section_master_rejects_shifted_gis_tail_areas():
    rows = _gis_sections()
    shifted = [
        {
            **row,
            "area_rai": (
                Decimal("995")
                if row["code"].endswith("-35")
                else Decimal("358")
                if row["code"].endswith("-36")
                else row["area_rai"]
            ),
        }
        for row in rows
    ]

    with pytest.raises(RequirementSourceError, match="GIS-authoritative section area"):
        _effective_section_master(shifted, load_requirement_source_manifest())


def test_effective_section_master_rejects_section_moved_to_another_zone():
    rows = _gis_sections()
    rows[0] = {
        **rows[0],
        "code": "01-02-01-03",
        "zone": "Zone2",
    }

    with pytest.raises(RequirementSourceError, match="section zone membership"):
        _effective_section_master(rows, load_requirement_source_manifest())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda rows: rows[:-1],
        lambda rows: [*rows, {**rows[0]}],
        lambda rows: [
            {**row, "zone_number": 7} if row["section_number"] == 3 else row
            for row in rows
        ],
        lambda rows: [
            {**row, "section_number": "3"} if row["section_number"] == 3 else row
            for row in rows
        ],
        lambda rows: [
            {**row, "zone_number": True} if row["section_number"] == 3 else row
            for row in rows
        ],
    ],
)
def test_effective_section_master_rejects_invalid_section_membership_authority(
    mutate,
):
    manifest = load_requirement_source_manifest()
    manifest["section_master"]["section_memberships"] = mutate(
        manifest["section_master"]["section_memberships"]
    )

    with pytest.raises(RequirementSourceError, match="section zone membership"):
        _effective_section_master(_gis_sections(), manifest)


def test_section_dataset_hash_binds_raw_gis_effective_rows_and_excel_authority():
    manifest = load_requirement_source_manifest()
    raw = _gis_sections()
    effective = _effective_section_master(raw, manifest)
    expected = _section_dataset_hash(raw, effective, manifest)
    raw_change = [{**raw[0], "area_rai": Decimal("999999")}, *raw[1:]]
    changed_authority = {
        **manifest,
        "scada": {**manifest["scada"], "sha256": "0" * 64},
    }
    changed_membership = {
        **manifest,
        "section_master": {
            **manifest["section_master"],
            "section_memberships": [
                {
                    **row,
                    "zone_number": 2,
                }
                if row["section_number"] == 3
                else row
                for row in manifest["section_master"]["section_memberships"]
            ],
        },
    }

    assert _section_dataset_hash(raw_change, effective, manifest) != expected
    assert _section_dataset_hash(raw, effective, changed_authority) != expected
    assert _section_dataset_hash(raw, effective, changed_membership) != expected


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
    assert any("ST_AsEWKB(ST_Multi(geom))" in sql for sql, _ in source.queries)
    assert any(
        "FROM water_planning.zone_planting_dates" in sql for sql, _ in source.queries
    )
    assert any("ros.eto_monthly" in sql for sql, _ in local.queries)
    assert len(local.batches) == 2
    assert "section_master_history" in local.batches[0][0]
    assert len(local.batches[0][1]) == 41
    assert local.batches[0][1][18][6:] == (
        Decimal("503"),
        "38R-LMC",
        "M(0,12;1,1)",
        b"test-geometry",
    )
    assert local.batches[0][1][32][7] == "RMC"
    section_activation = next(
        args
        for _, args in local.executions
        if len(args) == 4 and args[0] == "section_master"
    )
    assert "2026-07-24 V5.0" in section_activation[2]
    assert "approved total 45204 rai" in section_activation[2]
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
