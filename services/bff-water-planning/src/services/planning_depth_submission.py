from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Sequence

from schemas.planning_depth import (
    PlanningDepthExpandedValue,
    PlanningDepthLevelInput,
    PlanningDepthSubmissionRequest,
)

if TYPE_CHECKING:
    from schemas.planning_depth_v2 import PlanningDepthSubmissionRequestV2


class PlanningDepthValidationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CanonicalDocument:
    text: str
    sha256: str


@dataclass(frozen=True)
class RosterSection:
    section_id: str
    zone_id: str
    area_rai: Decimal


def _three_places(value: Decimal) -> str:
    return format(value, ".3f")


def _canonical_document(value) -> CanonicalDocument:
    text = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return CanonicalDocument(
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def canonicalize_planning_depth_request(
    request: PlanningDepthSubmissionRequest,
) -> CanonicalDocument:
    levels = []
    for level in sorted(
        request.levels,
        key=lambda item: (item.area_type, item.area_id),
    ):
        item = {
            "area_id": level.area_id,
            "area_type": level.area_type,
            "planning_depth_mm": _three_places(level.planning_depth_mm),
        }
        if level.zone_id is not None:
            item["zone_id"] = level.zone_id
        levels.append(item)
    return _canonical_document(
        {
            "levels": levels,
            "project_key": request.project_key,
            "schema_version": request.schema_version,
            "week_date": request.week_date.isoformat(),
            "week_key": request.week_key,
        }
    )


def canonicalize_planning_depth_request_v2(
    request: PlanningDepthSubmissionRequestV2,
) -> CanonicalDocument:
    levels = []
    for level in sorted(
        request.levels,
        key=lambda item: (item.area_type, item.area_id),
    ):
        item = {
            "area_id": level.area_id,
            "area_type": level.area_type,
            "planning_depth_mm": _three_places(level.planning_depth_mm),
        }
        if level.zone_id is not None:
            item["zone_id"] = level.zone_id
        levels.append(item)
    return _canonical_document(
        {
            "calendar_system": request.calendar_system,
            "levels": levels,
            "project_key": request.project_key,
            "schema_version": request.schema_version,
            "week_date": request.week_date.isoformat(),
            "week_key": request.week_key,
        }
    )


def validate_canonical_roster(roster: Sequence[RosterSection]) -> None:
    section_ids = [item.section_id for item in roster]
    section_numbers = set()
    try:
        for item in roster:
            project, zone, canal, section = item.section_id.split("-")
            zone_number = int(zone)
            section_number = int(section)
            if (
                item.section_id != f"01-{zone_number:02d}-01-{section_number:02d}"
                or project != "01"
                or canal != "01"
                or item.zone_id != f"01-{zone_number:02d}"
            ):
                raise ValueError
            section_numbers.add(section_number)
    except ValueError as exc:
        raise PlanningDepthValidationError("invalid_canonical_roster") from exc
    if (
        len(roster) != 41
        or len(set(section_ids)) != 41
        or section_numbers != set(range(3, 44))
        or {item.zone_id for item in roster}
        != {f"01-{zone_number:02d}" for zone_number in range(1, 7)}
        or any(item.area_rai <= 0 for item in roster)
        or sum((item.area_rai for item in roster), Decimal("0")) != Decimal("45204")
    ):
        raise PlanningDepthValidationError("invalid_canonical_roster")


def validate_planning_depth_roster(
    levels: Sequence[PlanningDepthLevelInput],
    roster: Sequence[RosterSection],
) -> None:
    validate_canonical_roster(roster)
    area_ids = [item.area_id for item in levels]
    if len(area_ids) != len(set(area_ids)):
        raise PlanningDepthValidationError("duplicate_area")

    roster_by_section = {item.section_id: item for item in roster}
    roster_zones = {item.zone_id for item in roster}
    submitted_zones = set()
    for level in levels:
        if level.area_type == "zone":
            if level.area_id not in roster_zones:
                raise PlanningDepthValidationError("unknown_area")
            submitted_zones.add(level.area_id)
            continue
        section = roster_by_section.get(level.area_id)
        if section is None:
            raise PlanningDepthValidationError("unknown_area")
        if level.zone_id != section.zone_id:
            raise PlanningDepthValidationError("wrong_section_zone")
    if submitted_zones != roster_zones:
        raise PlanningDepthValidationError("missing_zone_coverage")


def expand_planning_depth_values(
    levels: Sequence[PlanningDepthLevelInput],
    roster: Sequence[RosterSection],
) -> list[PlanningDepthExpandedValue]:
    validate_planning_depth_roster(levels, roster)
    zone_defaults = {
        item.area_id: item.planning_depth_mm
        for item in levels
        if item.area_type == "zone"
    }
    overrides = {item.area_id: item for item in levels if item.area_type == "section"}
    expanded = []
    for section in sorted(roster, key=lambda item: item.section_id):
        override = overrides.get(section.section_id)
        if override is None:
            expanded.append(
                PlanningDepthExpandedValue(
                    section_id=section.section_id,
                    zone_id=section.zone_id,
                    planning_depth_mm=zone_defaults[section.zone_id],
                    source_kind="zone_default",
                    source_area_id=section.zone_id,
                )
            )
        else:
            expanded.append(
                PlanningDepthExpandedValue(
                    section_id=section.section_id,
                    zone_id=section.zone_id,
                    planning_depth_mm=override.planning_depth_mm,
                    source_kind="section_override",
                    source_area_id=section.section_id,
                )
            )
    return expanded


def canonicalize_expanded_planning_depth_values(
    values: Sequence[PlanningDepthExpandedValue],
) -> CanonicalDocument:
    return _canonical_document(
        [
            {
                "planning_depth_mm": _three_places(item.planning_depth_mm),
                "section_id": item.section_id,
                "source_area_id": item.source_area_id,
                "source_kind": item.source_kind,
                "zone_id": item.zone_id,
            }
            for item in sorted(values, key=lambda item: item.section_id)
        ]
    )


class PlanningDepthRateLimitExceeded(RuntimeError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("planning-depth write limit exceeded")
        self.retry_after_seconds = retry_after_seconds


class PlanningDepthRateLimitUnavailable(RuntimeError):
    pass


_RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
if ttl < 0 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
  ttl = tonumber(ARGV[1])
end
return {count, ttl}
"""


async def consume_planning_depth_write_limit(
    redis_client,
    subject: str,
    *,
    limit: int,
    window_seconds: int,
) -> None:
    digest = hashlib.sha256(subject.encode("utf-8")).hexdigest()
    key = f"bff-water-planning:rate:planning_depth.submit:{digest}"
    try:
        count, ttl = await redis_client.eval(
            _RATE_LIMIT_SCRIPT,
            1,
            key,
            window_seconds,
        )
    except Exception as exc:
        raise PlanningDepthRateLimitUnavailable(
            "planning-depth write limiter is unavailable"
        ) from exc
    if int(count) > limit:
        retry_after = int(ttl)
        if retry_after < 1:
            retry_after = window_seconds
        raise PlanningDepthRateLimitExceeded(retry_after)
