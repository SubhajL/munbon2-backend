"""Pure canonical D..D+6 section water-requirement calculation."""

import calendar
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Mapping
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

BANGKOK = ZoneInfo("Asia/Bangkok")
METHOD_VERSION = "daily-requirement-v1"
PERCOLATION_MM_PER_DAY = Decimal("2")
RAI_MM_TO_M3 = Decimal("1.6")
VOLUME_QUANTUM = Decimal("0.000001")
REQUIREMENT_NAMESPACE = UUID("6e8b72b8-91b5-40d0-8b67-714c89b13231")


@dataclass(frozen=True)
class SectionCropInput:
    section_id: str
    zone: int
    area_rai: Decimal
    crop_type: str | None
    planting_date: date | None
    expected_harvest_date: date | None
    delivery_gate: str | None
    source: str
    as_of_date: date


@dataclass(frozen=True)
class RequirementSnapshot:
    sections: tuple[SectionCropInput, ...]
    eto_monthly_mm: Mapping[int, Decimal]
    kc_weekly: Mapping[tuple[str, int], Decimal]
    effective_rainfall_monthly_mm: Mapping[tuple[str, int], Decimal]
    section_dataset_version_id: int
    gate_mapping_dataset_version_id: int
    crop_register_version: str
    weather_version: str
    annual_plan_version: str
    input_cutoff_at: datetime


@dataclass(frozen=True)
class CalculatedRequirement:
    requirement_id: UUID
    service_date: date
    zone: int
    section_id: str
    required_net_volume_m3: Decimal
    required_gross_volume_m3: Decimal
    delivery_window_start: datetime
    delivery_window_end: datetime
    quality: str
    input_versions: Mapping[str, str]
    content_hash: str


@dataclass(frozen=True)
class RequirementContribution:
    requirement_id: UUID
    area_id: str
    area_rai: Decimal
    crop_type: str
    crop_stage: str
    net_volume_m3: Decimal
    source_payload_hash: str


@dataclass(frozen=True)
class RequirementBatch:
    content_hash: str
    requirements: tuple[CalculatedRequirement, ...]
    contributions: tuple[RequirementContribution, ...]


class RequirementInputError(ValueError):
    """One or more authoritative inputs are incomplete or inconsistent."""


def requirement_run_content_hash(
    snapshot: RequirementSnapshot,
    as_of_date: date,
    horizon_days: int,
) -> str:
    if not isinstance(as_of_date, date) or isinstance(as_of_date, datetime):
        raise RequirementInputError("as_of_date must be a date")
    if not isinstance(horizon_days, int) or isinstance(horizon_days, bool):
        raise RequirementInputError("horizon_days must be an integer")
    if not 1 <= horizon_days <= 31:
        raise RequirementInputError("horizon_days must be between 1 and 31")
    payload = {
        "annual_plan_version": snapshot.annual_plan_version,
        "as_of_date": as_of_date.isoformat(),
        "crop_register_version": snapshot.crop_register_version,
        "effective_rainfall_monthly_mm": sorted(
            (crop, month, str(value))
            for (crop, month), value in snapshot.effective_rainfall_monthly_mm.items()
        ),
        "eto_monthly_mm": sorted(
            (month, str(value)) for month, value in snapshot.eto_monthly_mm.items()
        ),
        "horizon_days": horizon_days,
        "kc_weekly": sorted(
            (crop, week, str(value))
            for (crop, week), value in snapshot.kc_weekly.items()
        ),
        "method_version": METHOD_VERSION,
        "sections": sorted(
            (
                item.section_id,
                item.zone,
                str(item.area_rai),
                item.crop_type,
                item.planting_date.isoformat() if item.planting_date else None,
                (
                    item.expected_harvest_date.isoformat()
                    if item.expected_harvest_date
                    else None
                ),
                item.delivery_gate,
                item.source,
                item.as_of_date.isoformat(),
            )
            for item in snapshot.sections
        ),
        "weather_version": snapshot.weather_version,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _input_errors(snapshot: RequirementSnapshot) -> list[str]:
    if not snapshot.sections:
        return ["section master contains no sections"]
    errors: list[str] = []
    seen: set[str] = set()
    for section in sorted(snapshot.sections, key=lambda item: item.section_id):
        if not section.section_id.strip():
            errors.append("section master contains a blank section id")
        elif section.section_id in seen:
            errors.append(f"section {section.section_id} is duplicated")
        seen.add(section.section_id)
        if not section.crop_type or not section.crop_type.strip():
            errors.append(f"section {section.section_id} has no crop type")
        if not section.delivery_gate or not section.delivery_gate.strip():
            errors.append(f"section {section.section_id} has no delivery gate")
        if section.planting_date is None:
            errors.append(f"section {section.section_id} has no zone planting date")
        if section.expected_harvest_date is None:
            errors.append(f"section {section.section_id} has no expected harvest date")
        elif (
            section.planting_date is not None
            and section.expected_harvest_date < section.planting_date
        ):
            errors.append(
                f"section {section.section_id} harvest date precedes planting date"
            )
        if not 1 <= section.zone <= 6:
            errors.append(
                f"section {section.section_id} has invalid zone {section.zone}"
            )
        if not section.area_rai.is_finite() or section.area_rai <= 0:
            errors.append(f"section {section.section_id} has invalid planted area")
        if section.as_of_date > snapshot.input_cutoff_at.date():
            errors.append(
                f"section {section.section_id} is newer than the input cutoff"
            )
    return errors


def _growth_stage(crop_type: str, crop_week: int) -> str:
    if crop_type != "rice":
        return f"week_{crop_week}"
    if crop_week <= 3:
        return "seedling"
    if crop_week <= 7:
        return "tillering"
    if crop_week <= 11:
        return "flowering"
    if crop_week <= 14:
        return "grain_filling"
    return "maturity"


def _hash_payload(payload: Mapping) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _volume(value: Decimal) -> Decimal:
    return value.quantize(VOLUME_QUANTUM)


def calculate_daily_water_requirements(
    snapshot: RequirementSnapshot,
    as_of_date: date,
    horizon_days: int = 7,
) -> RequirementBatch:
    run_hash = requirement_run_content_hash(snapshot, as_of_date, horizon_days)
    errors = _input_errors(snapshot)
    if errors:
        raise RequirementInputError(
            "authoritative requirement inputs are incomplete:\n"
            + "\n".join(f"- {error}" for error in errors)
        )

    input_versions = {
        "annual_plan": snapshot.annual_plan_version,
        "crop_register": snapshot.crop_register_version,
        "gate_mapping": str(snapshot.gate_mapping_dataset_version_id),
        "section_master": str(snapshot.section_dataset_version_id),
        "weather": snapshot.weather_version,
    }
    requirements: list[CalculatedRequirement] = []
    contributions: list[RequirementContribution] = []
    calculation_errors: set[str] = set()
    for service_offset in range(horizon_days):
        service_date = as_of_date + timedelta(days=service_offset)
        month_days = Decimal(
            calendar.monthrange(service_date.year, service_date.month)[1]
        )
        eto_monthly = snapshot.eto_monthly_mm.get(service_date.month)
        if eto_monthly is None:
            calculation_errors.add(
                f"month {service_date.month} has no reference evapotranspiration"
            )
        window_start = datetime.combine(
            service_date, time(hour=2), tzinfo=BANGKOK
        ).astimezone(timezone.utc)
        window_end = window_start + timedelta(days=1)
        for section in sorted(snapshot.sections, key=lambda item: item.section_id):
            if (
                section.crop_type is None
                or section.planting_date is None
                or section.expected_harvest_date is None
            ):
                raise RequirementInputError(
                    f"section {section.section_id} lost validated crop inputs"
                )
            crop_type = section.crop_type.strip()
            planting_date = section.planting_date
            expected_harvest_date = section.expected_harvest_date
            days_since_planting = (service_date - planting_date).days
            crop_week = days_since_planting // 7 + 1
            maximum_crop_week = max(
                (week for crop, week in snapshot.kc_weekly if crop == crop_type),
                default=0,
            )
            if days_since_planting < 0:
                stage = "not_planted"
                gross_mm = Decimal(0)
                net_mm = Decimal(0)
            elif service_date > expected_harvest_date:
                stage = "harvested"
                gross_mm = Decimal(0)
                net_mm = Decimal(0)
            else:
                kc = snapshot.kc_weekly.get((crop_type, crop_week))
                rainfall_monthly = snapshot.effective_rainfall_monthly_mm.get(
                    (crop_type, service_date.month)
                )
                if maximum_crop_week == 0:
                    calculation_errors.add(
                        f"crop {crop_type} has no crop-coefficient schedule"
                    )
                elif kc is None:
                    calculation_errors.add(
                        f"crop {crop_type} week {crop_week} has no crop coefficient"
                    )
                if rainfall_monthly is None:
                    calculation_errors.add(
                        f"crop {crop_type} month {service_date.month} has no effective rainfall"
                    )
                if eto_monthly is None or kc is None or rainfall_monthly is None:
                    continue
                stage = _growth_stage(crop_type, crop_week)
                gross_mm = eto_monthly / month_days * kc + PERCOLATION_MM_PER_DAY
                net_mm = max(Decimal(0), gross_mm - rainfall_monthly / month_days)
            net_volume = _volume(net_mm * section.area_rai * RAI_MM_TO_M3)
            gross_volume = net_volume
            identity = f"{run_hash}:{service_date.isoformat()}:{section.section_id}"
            requirement_id = uuid5(REQUIREMENT_NAMESPACE, identity)
            source_payload = {
                "area_rai": str(section.area_rai),
                "crop_stage": stage,
                "crop_type": crop_type,
                "delivery_gate": section.delivery_gate,
                "net_volume_m3": str(net_volume),
                "planting_date": planting_date.isoformat(),
                "expected_harvest_date": expected_harvest_date.isoformat(),
                "service_date": service_date.isoformat(),
                "source": section.source,
            }
            quality = "estimated" if service_offset == 0 else "forecast"
            requirement_payload = {
                **source_payload,
                "gross_volume_m3": str(gross_volume),
                "input_versions": input_versions,
                "quality": quality,
                "section_id": section.section_id,
                "zone": section.zone,
            }
            requirements.append(
                CalculatedRequirement(
                    requirement_id=requirement_id,
                    service_date=service_date,
                    zone=section.zone,
                    section_id=section.section_id,
                    required_net_volume_m3=net_volume,
                    required_gross_volume_m3=gross_volume,
                    delivery_window_start=window_start,
                    delivery_window_end=window_end,
                    quality=quality,
                    input_versions=input_versions,
                    content_hash=_hash_payload(requirement_payload),
                )
            )
            contributions.append(
                RequirementContribution(
                    requirement_id=requirement_id,
                    area_id=section.section_id,
                    area_rai=section.area_rai.quantize(VOLUME_QUANTUM),
                    crop_type=crop_type,
                    crop_stage=stage,
                    net_volume_m3=net_volume,
                    source_payload_hash=_hash_payload(source_payload),
                )
            )
    if calculation_errors:
        raise RequirementInputError(
            "authoritative requirement inputs are incomplete:\n"
            + "\n".join(f"- {error}" for error in sorted(calculation_errors))
        )
    return RequirementBatch(
        content_hash=run_hash,
        requirements=tuple(requirements),
        contributions=tuple(contributions),
    )
