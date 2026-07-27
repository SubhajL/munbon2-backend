"""Load approved section, crop, and agronomic inputs for daily publication."""

import hashlib
import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from typing import Mapping, Sequence

from services.daily_requirement_producer import RequirementSnapshot, SectionCropInput

SOURCE_MANIFEST_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "requirement_sources.json"
)


class RequirementSourceError(ValueError):
    """The approved input snapshot cannot be constructed safely."""


class AuthoritativeRequirementSourceLoader:
    def __init__(self, source_connection, max_input_age_hours: int = 4320):
        if max_input_age_hours < 1:
            raise ValueError("max_input_age_hours must be positive")
        self.source_connection = source_connection
        self.max_input_age_hours = max_input_age_hours

    async def load(
        self,
        local_conn,
        as_of_date: date,
        now: datetime,
    ) -> RequirementSnapshot:
        if now.tzinfo is None or now.utcoffset() is None:
            raise RequirementSourceError("source load time must be timezone-aware")
        cutoff = now.astimezone(timezone.utc)
        manifest = load_requirement_source_manifest()
        async with self.source_connection() as source_conn:
            gis_sections = await source_conn.fetch(
                """
                SELECT code,
                       props->>'Zone' AS zone,
                       (props->>'Area_Rai')::numeric AS area_rai,
                       props->>'Crop_1' AS crop_type,
                       props->>'NameArea' AS name_area,
                       ST_AsEWKB(ST_Multi(geom)) AS geometry_wkb,
                       create_date
                FROM gis.zone
                ORDER BY code
                """
            )
            planting_dates = await source_conn.fetch(
                """
                SELECT project_key, zone_number, planting_date, updated_by, updated_at
                FROM water_planning.zone_planting_dates
                WHERE project_key = $1
                ORDER BY zone_number
                """,
                manifest["project_key"],
            )
        crop_settings = await local_conn.fetch(
            """
            SELECT DISTINCT ON (section_id)
                   section_id, crop_type, planted_area_rai, expected_harvest_date,
                   source, as_of_date
            FROM ros_gis.section_crop_settings
            WHERE as_of_date <= $1
            ORDER BY section_id, as_of_date DESC, created_at DESC, setting_id DESC
            """,
            as_of_date,
        )
        eto_rows = await local_conn.fetch(
            """
            SELECT month, eto_value, updated_at
            FROM ros.eto_monthly
            ORDER BY month
            """
        )
        kc_rows = await local_conn.fetch(
            """
            SELECT crop_type, crop_week, kc_value, updated_at
            FROM ros.kc_weekly
            ORDER BY crop_type, crop_week
            """
        )
        rainfall_rows = await local_conn.fetch(
            """
            SELECT crop_type, month, effective_rainfall_mm, updated_at
            FROM ros.effective_rainfall_monthly
            ORDER BY crop_type, month
            """
        )
        oldest_allowed = cutoff - timedelta(hours=self.max_input_age_hours)
        stale_zones = [
            str(row["zone_number"])
            for row in planting_dates
            if row["updated_at"] is None
            or row["updated_at"].astimezone(timezone.utc) < oldest_allowed
        ]
        if stale_zones:
            raise RequirementSourceError(
                "zone planting-date inputs are older than "
                f"{self.max_input_age_hours} hours for zones " + ", ".join(stale_zones)
            )
        effective_sections = _effective_section_master(gis_sections, manifest)
        preliminary = build_requirement_snapshot(
            gis_sections=effective_sections,
            planting_dates=planting_dates,
            crop_settings=crop_settings,
            eto_rows=eto_rows,
            kc_rows=kc_rows,
            rainfall_rows=rainfall_rows,
            manifest=manifest,
            section_dataset_version_id=1,
            gate_mapping_dataset_version_id=1,
            input_cutoff_at=cutoff,
        )
        section_hash = _section_dataset_hash(
            gis_sections,
            effective_sections,
            manifest,
        )
        gate_hash = _hash(
            {"crosswalk": manifest["crosswalk"], "scada": manifest["scada"]}
        )
        section_dataset_version_id = await _activate_section_dataset(
            local_conn,
            effective_sections,
            manifest,
            section_hash,
            cutoff,
        )
        gate_mapping_dataset_version_id = await _activate_gate_dataset(
            local_conn,
            gis_sections,
            manifest,
            gate_hash,
            cutoff,
        )
        return replace(
            preliminary,
            section_dataset_version_id=section_dataset_version_id,
            gate_mapping_dataset_version_id=gate_mapping_dataset_version_id,
        )


def load_requirement_source_manifest(path: Path = SOURCE_MANIFEST_PATH) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RequirementSourceError(
            f"approved requirement source manifest cannot be loaded: {exc}"
        ) from exc
    required = {"project_key", "section_master", "scada", "annual_plan", "crosswalk"}
    if set(manifest) != required:
        raise RequirementSourceError(
            "approved requirement source manifest has invalid keys"
        )
    return manifest


def _decimal(value, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RequirementSourceError(f"{field} must be numeric") from exc
    if not result.is_finite():
        raise RequirementSourceError(f"{field} must be finite")
    return result


def _zone(value) -> int:
    text = str(value)
    if text.startswith("Zone"):
        text = text[4:]
    try:
        zone = int(text)
    except ValueError as exc:
        raise RequirementSourceError(f"invalid GIS zone {value!r}") from exc
    if not 1 <= zone <= 6:
        raise RequirementSourceError(f"invalid GIS zone {value!r}")
    return zone


def _crop(value) -> str | None:
    if value is None or not str(value).strip():
        return None
    normalized = str(value).strip().lower()
    aliases = {
        "นาข้าว": "rice",
        "ข้าว": "rice",
        "rice": "rice",
        "ข้าวโพด": "corn",
        "corn": "corn",
        "อ้อย": "sugarcane",
        "sugarcane": "sugarcane",
    }
    return aliases.get(normalized, normalized)


def _hash(value) -> str:
    def default(item):
        if isinstance(item, Mapping):
            return dict(item)
        keys = getattr(item, "keys", None)
        if callable(keys) and hasattr(item, "__getitem__"):
            return {key: item[key] for key in keys()}
        if isinstance(item, (date, datetime)):
            return item.isoformat()
        if isinstance(item, Decimal):
            return str(item)
        if isinstance(item, bytes):
            return item.hex()
        raise TypeError(f"cannot hash {type(item).__name__}")

    return hashlib.sha256(
        json.dumps(
            value,
            default=default,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _section_authority_numbers(
    manifest: Mapping,
) -> tuple[Mapping, set[int], set[int], set[int]]:
    try:
        section_master = manifest["section_master"]
        expected_count = int(section_master["section_count"])
        expected_numbers = {
            int(item["section_number"]) for item in manifest["crosswalk"]
        }
        excel_start, excel_end = (
            int(value) for value in section_master["excel_section_range"]
        )
        gis_start, gis_end = (
            int(value) for value in section_master["gis_section_range"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RequirementSourceError("approved section authority is invalid") from exc
    excel_numbers = set(range(excel_start, excel_end + 1))
    gis_numbers = set(range(gis_start, gis_end + 1))
    if (
        excel_numbers & gis_numbers
        or excel_numbers | gis_numbers != expected_numbers
        or len(expected_numbers) != expected_count
    ):
        raise RequirementSourceError("approved section authority is invalid")
    return section_master, expected_numbers, excel_numbers, gis_numbers


def _chainage_metres(value, field: str) -> int:
    match = re.fullmatch(r"(\d+)\+(\d{3})", str(value))
    if match is None:
        raise RequirementSourceError(f"{field} is invalid")
    return int(match.group(1)) * 1000 + int(match.group(2))


def _raw_sections_by_number(
    gis_sections: Sequence[Mapping],
    expected_count: int,
    expected_numbers: set[int],
) -> dict[int, dict]:
    raw_rows: dict[int, dict] = {}
    try:
        for source_row in gis_sections:
            row = dict(source_row)
            section_number = _section_number(row)
            if section_number in raw_rows:
                raise RequirementSourceError(
                    "approved section master contains duplicate section identities"
                )
            raw_rows[section_number] = row
    except (KeyError, TypeError) as exc:
        raise RequirementSourceError(
            "approved section master contains an invalid section identity"
        ) from exc
    if len(gis_sections) != expected_count or set(raw_rows) != expected_numbers:
        raise RequirementSourceError(
            "approved section master must contain exactly sections 03-43"
        )
    return raw_rows


def _excel_section_overrides(
    section_master: Mapping,
    excel_numbers: set[int],
) -> dict[int, Mapping]:
    required_override_keys = {
        "section_number",
        "source_row",
        "canal_name",
        "start_km",
        "end_km",
        "area_rai",
    }
    override_rows: dict[int, Mapping] = {}
    source_rows: set[int] = set()
    try:
        overrides = section_master["excel_overrides"]
        for override in overrides:
            if set(override) != required_override_keys:
                raise RequirementSourceError(
                    "Excel section overrides have invalid fields"
                )
            section_number = int(override["section_number"])
            if section_number in override_rows:
                raise RequirementSourceError(
                    "Excel section overrides contain duplicate sections"
                )
            area_rai = _decimal(
                override["area_rai"],
                f"Excel section {section_number} area",
            )
            source_row = int(override["source_row"])
            start_metres = _chainage_metres(
                override["start_km"],
                f"Excel section {section_number} start chainage",
            )
            end_metres = _chainage_metres(
                override["end_km"],
                f"Excel section {section_number} end chainage",
            )
            if (
                area_rai <= 0
                or source_row <= 0
                or source_row in source_rows
                or not str(override["canal_name"]).strip()
                or start_metres >= end_metres
            ):
                raise RequirementSourceError(
                    "Excel section overrides must contain positive areas and source rows"
                )
            source_rows.add(source_row)
            override_rows[section_number] = override
    except (KeyError, TypeError, ValueError) as exc:
        raise RequirementSourceError("Excel section overrides are invalid") from exc
    if set(override_rows) != excel_numbers:
        raise RequirementSourceError(
            "Excel section overrides must contain every Excel-authoritative section"
        )
    return override_rows


def _expected_gis_section_areas(
    section_master: Mapping,
    gis_numbers: set[int],
) -> dict[int, Decimal]:
    expected_gis_areas: dict[int, Decimal] = {}
    try:
        for expected in section_master["gis_expected_areas"]:
            if set(expected) != {"section_number", "area_rai"}:
                raise RequirementSourceError(
                    "GIS-authoritative section area expectations have invalid fields"
                )
            section_number = int(expected["section_number"])
            if section_number in expected_gis_areas:
                raise RequirementSourceError(
                    "GIS-authoritative section area expectations contain duplicates"
                )
            area_rai = _decimal(
                expected["area_rai"],
                f"GIS section {section_number} expected area",
            )
            if area_rai <= 0:
                raise RequirementSourceError(
                    "GIS-authoritative section area expectations must be positive"
                )
            expected_gis_areas[section_number] = area_rai
    except (KeyError, TypeError, ValueError) as exc:
        raise RequirementSourceError(
            "GIS-authoritative section area expectations are invalid"
        ) from exc
    if set(expected_gis_areas) != gis_numbers:
        raise RequirementSourceError(
            "GIS-authoritative section area expectations must cover every GIS section"
        )
    return expected_gis_areas


def _effective_section_master(
    gis_sections: Sequence[Mapping],
    manifest: Mapping,
) -> list[dict]:
    (
        section_master,
        expected_numbers,
        excel_numbers,
        gis_numbers,
    ) = _section_authority_numbers(manifest)
    raw_rows = _raw_sections_by_number(
        gis_sections,
        int(section_master["section_count"]),
        expected_numbers,
    )
    override_rows = _excel_section_overrides(section_master, excel_numbers)
    expected_gis_areas = _expected_gis_section_areas(section_master, gis_numbers)

    effective: list[dict] = []
    for section_number in sorted(expected_numbers):
        row = raw_rows[section_number]
        if section_number in excel_numbers:
            override = override_rows[section_number]
            row.update(
                area_rai=_decimal(
                    override["area_rai"],
                    f"Excel section {section_number} area",
                ),
                name_area=str(override["canal_name"]),
                area_source="scada_excel",
                source_row=int(override["source_row"]),
                start_km=str(override["start_km"]),
                end_km=str(override["end_km"]),
            )
        else:
            area_rai = _decimal(row["area_rai"], f"GIS section {section_number} area")
            if area_rai != expected_gis_areas[section_number]:
                raise RequirementSourceError(
                    f"GIS-authoritative section area mismatch for section {section_number}"
                )
            row.update(area_rai=area_rai, area_source="gis.zone")
        effective.append(row)

    expected_area = Decimal(section_master["total_area_rai"])
    effective_area = sum(
        (_decimal(row["area_rai"], "effective section area") for row in effective),
        Decimal(0),
    )
    if effective_area != expected_area:
        raise RequirementSourceError(
            f"approved section master must total {expected_area} rai"
        )
    return effective


def _section_dataset_hash(
    gis_sections: Sequence[Mapping],
    effective_sections: Sequence[Mapping],
    manifest: Mapping,
) -> str:
    return _hash(
        {
            "authority": {
                "section_master": manifest["section_master"],
                "scada": manifest["scada"],
                "crosswalk": manifest["crosswalk"],
            },
            "raw_gis": list(gis_sections),
            "effective_sections": list(effective_sections),
        }
    )


def _section_number(row: Mapping) -> int:
    code = str(row["code"])
    parts = code.split("-")
    if len(parts) != 4:
        raise RequirementSourceError(
            "approved section master contains an invalid section code"
        )
    project, zone_text, canal, section_text = parts
    try:
        zone = int(zone_text)
        section_number = int(section_text)
    except ValueError as exc:
        raise RequirementSourceError(
            "approved section master contains an invalid section code"
        ) from exc
    if (
        project != "01"
        or canal != "01"
        or code != f"01-{zone:02d}-01-{section_number:02d}"
        or _zone(row["zone"]) != zone
    ):
        raise RequirementSourceError(
            "approved section master contains an invalid section code"
        )
    return section_number


def _validated_section_sources(
    gis_sections: Sequence[Mapping],
    planting_dates: Sequence[Mapping],
    crop_settings: Sequence[Mapping],
    manifest: Mapping,
) -> tuple[dict[int, Mapping], dict[int, Mapping], dict[str, Mapping]]:
    expected_count = int(manifest["section_master"]["section_count"])
    expected_area = Decimal(manifest["section_master"]["total_area_rai"])
    expected_numbers = {int(item["section_number"]) for item in manifest["crosswalk"]}
    section_codes = [str(item["code"]) for item in gis_sections]
    section_numbers = {_section_number(item) for item in gis_sections}
    source_area = sum(
        (
            _decimal(item["area_rai"], f"section {item['code']} area")
            for item in gis_sections
        ),
        Decimal(0),
    )
    if (
        len(gis_sections) != expected_count
        or len(set(section_codes)) != expected_count
        or section_numbers != expected_numbers
        or source_area != expected_area
    ):
        raise RequirementSourceError(
            "approved section master must contain exactly sections 03-43 "
            f"and total {expected_area} rai"
        )
    crosswalk = {int(item["section_number"]): item for item in manifest["crosswalk"]}
    if len(crosswalk) != expected_count:
        raise RequirementSourceError(
            "approved D1 crosswalk contains duplicate sections"
        )
    planting_by_zone = {
        int(item["zone_number"]): item
        for item in planting_dates
        if item["project_key"] == manifest["project_key"]
    }
    if set(planting_by_zone) != set(range(1, 7)):
        raise RequirementSourceError(
            "zone planting-date register must contain zones 1-6 for project mun-bon"
        )
    setting_by_section = {str(item["section_id"]): item for item in crop_settings}
    if len(setting_by_section) != len(crop_settings):
        raise RequirementSourceError("section crop settings contain duplicate sections")
    unknown_settings = set(setting_by_section) - set(section_codes)
    if unknown_settings:
        raise RequirementSourceError(
            "section crop settings reference unknown sections: "
            + ", ".join(sorted(unknown_settings))
        )
    return crosswalk, planting_by_zone, setting_by_section


def _crop_coefficient_schedule(
    kc_rows: Sequence[Mapping],
) -> tuple[dict[tuple[str, int], Decimal], dict[str, int]]:
    kc_weekly = {
        (str(item["crop_type"]).strip().lower(), int(item["crop_week"])): _decimal(
            item["kc_value"], "crop coefficient"
        )
        for item in kc_rows
    }
    crop_duration_weeks: dict[str, int] = {}
    for kc_crop_type, crop_week in kc_weekly:
        crop_duration_weeks[kc_crop_type] = max(
            crop_duration_weeks.get(kc_crop_type, 0), crop_week
        )
    return kc_weekly, crop_duration_weeks


def _section_crop_inputs(
    gis_sections: Sequence[Mapping],
    crosswalk: Mapping[int, Mapping],
    planting_by_zone: Mapping[int, Mapping],
    setting_by_section: Mapping[str, Mapping],
    crop_duration_weeks: Mapping[str, int],
    input_cutoff_at: datetime,
) -> tuple[list[SectionCropInput], list[dict]]:
    sections: list[SectionCropInput] = []
    crop_lineage: list[dict] = []
    for row in sorted(gis_sections, key=lambda item: str(item["code"])):
        section_id = str(row["code"])
        section_number = int(section_id.rsplit("-", 1)[1])
        zone = _zone(row["zone"])
        planting = planting_by_zone[zone]
        planting_date = planting["planting_date"]
        setting = setting_by_section.get(section_id)
        crop_type = _crop(
            setting["crop_type"] if setting is not None else row["crop_type"]
        )
        source_area_rai = _decimal(row["area_rai"], f"section {section_id} area")
        area_rai = (
            _decimal(setting["planted_area_rai"], f"section {section_id} planted area")
            if setting is not None
            else source_area_rai
        )
        if area_rai <= 0 or area_rai > source_area_rai:
            raise RequirementSourceError(
                f"section {section_id} planted area must be positive and not exceed effective section area"
            )
        expected_harvest_date = (
            setting.get("expected_harvest_date") if setting is not None else None
        )
        if (
            expected_harvest_date is None
            and crop_type is not None
            and planting_date is not None
            and crop_type in crop_duration_weeks
        ):
            expected_harvest_date = planting_date + timedelta(
                days=crop_duration_weeks[crop_type] * 7 - 1
            )
        default_area_source = str(row.get("area_source", "gis.zone"))
        source = (
            str(setting["source"])
            if setting is not None
            else f"{default_area_source}+water_planning.zone_planting_dates"
        )
        as_of_date = (
            setting["as_of_date"] if setting is not None else input_cutoff_at.date()
        )
        mapping = crosswalk[section_number]
        sections.append(
            SectionCropInput(
                section_id=section_id,
                zone=zone,
                area_rai=area_rai,
                crop_type=crop_type,
                planting_date=planting_date,
                expected_harvest_date=expected_harvest_date,
                delivery_gate=str(mapping["gate_id"]),
                source=source,
                as_of_date=as_of_date,
            )
        )
        crop_lineage.append(
            {
                "area_rai": area_rai,
                "as_of_date": as_of_date,
                "crop_type": crop_type,
                "expected_harvest_date": expected_harvest_date,
                "planting_date": planting_date,
                "planting_updated_at": planting["updated_at"],
                "planting_updated_by": planting["updated_by"],
                "section_id": section_id,
                "source": source,
            }
        )
    return sections, crop_lineage


def _effective_rainfall_schedule(
    rainfall_rows: Sequence[Mapping],
    crop_types: Sequence[str],
) -> dict[tuple[str, int], Decimal]:
    rainfall_by_category = {
        (str(item["crop_type"]).strip().lower(), int(item["month"])): _decimal(
            item["effective_rainfall_mm"], "effective rainfall"
        )
        for item in rainfall_rows
    }
    effective_rainfall: dict[tuple[str, int], Decimal] = {}
    for kc_crop_type in crop_types:
        category = "rice" if kc_crop_type == "rice" else "field_crop"
        for (rainfall_crop, month), value in rainfall_by_category.items():
            if rainfall_crop == category:
                effective_rainfall[(kc_crop_type, month)] = value
    return effective_rainfall


def build_requirement_snapshot(
    *,
    gis_sections: Sequence[Mapping],
    planting_dates: Sequence[Mapping],
    crop_settings: Sequence[Mapping],
    eto_rows: Sequence[Mapping],
    kc_rows: Sequence[Mapping],
    rainfall_rows: Sequence[Mapping],
    manifest: Mapping,
    section_dataset_version_id: int,
    gate_mapping_dataset_version_id: int,
    input_cutoff_at: datetime,
) -> RequirementSnapshot:
    if input_cutoff_at.tzinfo is None or input_cutoff_at.utcoffset() is None:
        raise RequirementSourceError("input_cutoff_at must be timezone-aware")
    crosswalk, planting_by_zone, setting_by_section = _validated_section_sources(
        gis_sections, planting_dates, crop_settings, manifest
    )
    kc_weekly, crop_duration_weeks = _crop_coefficient_schedule(kc_rows)
    sections, crop_lineage = _section_crop_inputs(
        gis_sections,
        crosswalk,
        planting_by_zone,
        setting_by_section,
        crop_duration_weeks,
        input_cutoff_at,
    )
    effective_rainfall = _effective_rainfall_schedule(
        rainfall_rows, list(crop_duration_weeks)
    )
    weather_payload = {
        "eto": list(eto_rows),
        "kc": list(kc_rows),
        "rainfall": list(rainfall_rows),
    }
    return RequirementSnapshot(
        sections=tuple(sections),
        eto_monthly_mm={
            int(item["month"]): _decimal(
                item["eto_value"], "reference evapotranspiration"
            )
            for item in eto_rows
        },
        kc_weekly=kc_weekly,
        effective_rainfall_monthly_mm=effective_rainfall,
        section_dataset_version_id=section_dataset_version_id,
        gate_mapping_dataset_version_id=gate_mapping_dataset_version_id,
        crop_register_version=_hash(crop_lineage),
        weather_version=_hash(weather_payload),
        annual_plan_version=(
            f"sha256:{manifest['annual_plan']['sha256']};"
            f"sheet:{manifest['annual_plan']['sheet']};"
            f"rate_unit:{manifest['annual_plan']['rate_unit']}"
        ),
        input_cutoff_at=input_cutoff_at,
    )


async def _active_dataset(local_conn, kind: str, source_hash: str) -> int | None:
    row = await local_conn.fetchrow(
        """
        SELECT dataset_version_id, source_hash
        FROM ros_gis.dataset_versions
        WHERE dataset_kind = $1 AND status = 'active'
        """,
        kind,
    )
    if row is not None and row["source_hash"] == source_hash:
        return int(row["dataset_version_id"])
    return None


async def _create_dataset_version(
    local_conn,
    kind: str,
    source_hash: str,
    source_description: str,
    effective_from: datetime,
) -> int:
    await local_conn.execute(
        """
        UPDATE ros_gis.dataset_versions
        SET status = 'superseded', effective_to = $2
        WHERE dataset_kind = $1 AND status = 'active'
        """,
        kind,
        effective_from,
    )
    return int(
        await local_conn.fetchval(
            """
            INSERT INTO ros_gis.dataset_versions (
                dataset_kind, source_hash, source_description, status, effective_from
            ) VALUES ($1, $2, $3, 'active', $4)
            RETURNING dataset_version_id
            """,
            kind,
            source_hash,
            source_description,
            effective_from,
        )
    )


async def _activate_section_dataset(
    local_conn,
    gis_sections: Sequence[Mapping],
    manifest: Mapping,
    source_hash: str,
    effective_from: datetime,
) -> int:
    active = await _active_dataset(local_conn, "section_master", source_hash)
    if active is not None:
        return active
    crosswalk = {int(item["section_number"]): item for item in manifest["crosswalk"]}
    async with local_conn.transaction():
        dataset_id = await _create_dataset_version(
            local_conn,
            "section_master",
            source_hash,
            (
                f"{manifest['scada']['file']} Sheet1.Q sections 03-34; "
                "postgres.gis.zone props.Area_Rai sections 35-43; "
                f"approved total {manifest['section_master']['total_area_rai']} rai"
            ),
            effective_from,
        )
        await local_conn.executemany(
            """
            INSERT INTO ros_gis.section_master_history (
                dataset_version_id, section_id, valid_from, zone, source_code,
                area_hectares, area_rai, irrigation_channel, delivery_gate, geometry
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                      ST_GeomFromEWKB($10))
            """,
            [
                (
                    dataset_id,
                    str(row["code"]),
                    effective_from,
                    _zone(row["zone"]),
                    str(row["code"]),
                    (
                        _decimal(row["area_rai"], "section area") / Decimal("6.25")
                    ).quantize(Decimal("0.01")),
                    _decimal(row["area_rai"], "section area"),
                    str(crosswalk[_section_number(row)]["irrigation_channel"]),
                    crosswalk[_section_number(row)]["gate_id"],
                    row.get("geometry_wkb"),
                )
                for row in sorted(gis_sections, key=lambda item: str(item["code"]))
            ],
        )
    return dataset_id


async def _activate_gate_dataset(
    local_conn,
    gis_sections: Sequence[Mapping],
    manifest: Mapping,
    source_hash: str,
    effective_from: datetime,
) -> int:
    active = await _active_dataset(local_conn, "gate_crosswalk", source_hash)
    if active is not None:
        return active
    section_by_number = {
        int(str(row["code"]).rsplit("-", 1)[1]): str(row["code"])
        for row in gis_sections
    }
    async with local_conn.transaction():
        dataset_id = await _create_dataset_version(
            local_conn,
            "gate_crosswalk",
            source_hash,
            f"{manifest['scada']['file']}::{manifest['scada']['sheet']}",
            effective_from,
        )
        await local_conn.executemany(
            """
            INSERT INTO ros_gis.gate_mapping_history (
                dataset_version_id, section_id, gate_id, valid_from,
                is_primary, irrigation_channel
            ) VALUES ($1, $2, $3, $4, true, $5)
            """,
            [
                (
                    dataset_id,
                    section_by_number[int(row["section_number"])],
                    str(row["gate_id"]),
                    effective_from,
                    str(row["irrigation_channel"]),
                )
                for row in sorted(
                    manifest["crosswalk"], key=lambda item: int(item["section_number"])
                )
            ],
        )
    return dataset_id
