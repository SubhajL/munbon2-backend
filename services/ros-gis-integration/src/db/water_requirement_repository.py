"""Append-only canonical daily water-requirement publication repository."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Mapping, Sequence
from uuid import UUID, uuid4

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
VOLUME_QUANTUM = Decimal("0.000001")

INSERT_RUN = """
INSERT INTO ros_gis.water_requirement_runs (
    run_id, as_of_date, horizon_start, horizon_end, input_cutoff_at,
    section_dataset_version_id, gate_mapping_dataset_version_id,
    crop_register_version, weather_version, method_version, content_hash, computed_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
RETURNING *
"""

LOCK_RUN = """
SELECT run_id, as_of_date, horizon_start, horizon_end, status
     , computed_at
FROM ros_gis.water_requirement_runs
WHERE run_id = $1
FOR UPDATE
"""

INSERT_REQUIREMENTS = """
INSERT INTO ros_gis.daily_water_requirements (
    requirement_id, run_id, service_date, zone, section_id,
    required_net_volume_m3, required_gross_volume_m3,
    delivery_window_start, delivery_window_end, quality, input_versions, content_hash
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12)
"""

INSERT_CONTRIBUTIONS = """
INSERT INTO ros_gis.water_requirement_contributions (
    requirement_id, area_id, area_rai, crop_type, crop_stage,
    net_volume_m3, source_payload_hash
) VALUES ($1, $2, $3, $4, $5, $6, $7)
"""

SUPERSEDE_PUBLISHED_RUN = """
UPDATE ros_gis.water_requirement_runs
SET status = 'superseded'
WHERE as_of_date = $1 AND status = 'published' AND run_id <> $2
"""

MARK_PUBLISHED = """
UPDATE ros_gis.water_requirement_runs
SET status = 'published', published_at = $2
WHERE run_id = $1 AND status = 'calculating'
RETURNING *
"""

MARK_FAILED = """
UPDATE ros_gis.water_requirement_runs
SET status = 'failed', failure_reason = $2
WHERE run_id = $1 AND status = 'calculating'
RETURNING *
"""

SELECT_PUBLISHED_REQUIREMENTS = """
SELECT requirement.*,
       run.as_of_date,
       run.horizon_start,
       run.horizon_end,
       run.input_cutoff_at,
       run.section_dataset_version_id,
       run.gate_mapping_dataset_version_id,
       run.crop_register_version,
       run.weather_version,
       run.method_version,
       run.content_hash AS run_content_hash,
       run.computed_at,
       run.published_at
FROM ros_gis.water_requirement_runs AS run
JOIN ros_gis.daily_water_requirements AS requirement USING (run_id)
WHERE run.as_of_date = $1 AND run.status = 'published'
ORDER BY requirement.service_date, requirement.zone, requirement.section_id
"""


class RequirementRepositoryError(ValueError):
    """A requirement run cannot make the requested state transition."""


def _date(value, field: str) -> date:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise RequirementRepositoryError(f"{field} must be a date")
    return value


def _aware(value, field: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise RequirementRepositoryError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _positive_int(value, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise RequirementRepositoryError(f"{field} must be a positive integer")
    return value


def _nonblank(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RequirementRepositoryError(f"{field} must be non-empty")
    return value.strip()


def _sha256(value, field: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise RequirementRepositoryError(f"{field} must be lowercase SHA-256")
    return value


def _uuid(value, field: str) -> UUID:
    if not isinstance(value, UUID):
        raise RequirementRepositoryError(f"{field} must be a UUID")
    return value


def _decimal(value, field: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise RequirementRepositoryError(f"{field} must be a finite number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RequirementRepositoryError(f"{field} must be a finite number") from exc
    if not result.is_finite() or result < 0 or (positive and result <= 0):
        qualifier = "positive" if positive else "non-negative"
        raise RequirementRepositoryError(f"{field} must be finite and {qualifier}")
    try:
        rounded = result.quantize(VOLUME_QUANTUM)
    except InvalidOperation as exc:
        raise RequirementRepositoryError(
            f"{field} exceeds NUMERIC(18, 6) precision"
        ) from exc
    if rounded != result:
        raise RequirementRepositoryError(
            f"{field} must have no more than six decimal places"
        )
    return result


def _row_dict(row) -> dict:
    result = dict(row)
    input_versions = result.get("input_versions")
    if isinstance(input_versions, str):
        result["input_versions"] = json.loads(input_versions)
    return result


def _validate_requirement(
    requirement: Mapping,
    as_of_date: date,
    horizon_start: date,
    horizon_end: date,
) -> dict:
    try:
        service_date = _date(requirement["service_date"], "service_date")
        net = _decimal(requirement["required_net_volume_m3"], "required_net_volume_m3")
        gross = _decimal(
            requirement["required_gross_volume_m3"], "required_gross_volume_m3"
        )
        window_start = _aware(
            requirement["delivery_window_start"], "delivery_window_start"
        )
        window_end = _aware(requirement["delivery_window_end"], "delivery_window_end")
        input_versions = requirement["input_versions"]
        if not isinstance(input_versions, dict) or not input_versions:
            raise RequirementRepositoryError(
                "input_versions must be a non-empty object"
            )
        try:
            json.dumps(
                input_versions,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise RequirementRepositoryError(
                "input_versions must contain JSON values"
            ) from exc
        quality = requirement["quality"]
        if quality not in ("estimated", "forecast"):
            raise RequirementRepositoryError(
                "quality must be 'estimated' or 'forecast'"
            )
        if not horizon_start <= service_date <= horizon_end:
            raise RequirementRepositoryError(
                "service_date must lie within the run horizon"
            )
        if service_date == as_of_date and quality != "estimated":
            raise RequirementRepositoryError(
                "the as_of_date requirement quality must be estimated"
            )
        if service_date > as_of_date and quality != "forecast":
            raise RequirementRepositoryError(
                "future requirement quality must be forecast"
            )
        if gross < net:
            raise RequirementRepositoryError(
                "required_gross_volume_m3 must be at least required_net_volume_m3"
            )
        if window_start >= window_end:
            raise RequirementRepositoryError(
                "delivery_window_start must come before delivery_window_end"
            )
        return {
            "requirement_id": _uuid(requirement["requirement_id"], "requirement_id"),
            "service_date": service_date,
            "zone": _positive_int(requirement["zone"], "zone"),
            "section_id": _nonblank(requirement["section_id"], "section_id"),
            "required_net_volume_m3": net,
            "required_gross_volume_m3": gross,
            "delivery_window_start": window_start,
            "delivery_window_end": window_end,
            "quality": quality,
            "input_versions": dict(input_versions),
            "content_hash": _sha256(
                requirement["content_hash"], "requirement content_hash"
            ),
        }
    except KeyError as exc:
        raise RequirementRepositoryError(
            f"requirement is missing {exc.args[0]}"
        ) from exc


def _validate_contribution(contribution: Mapping, requirement_ids: set[UUID]) -> dict:
    try:
        requirement_id = _uuid(
            contribution["requirement_id"], "contribution requirement_id"
        )
        if requirement_id not in requirement_ids:
            raise RequirementRepositoryError(
                "contribution references a requirement outside this publication"
            )
        return {
            "requirement_id": requirement_id,
            "area_id": _nonblank(contribution["area_id"], "area_id"),
            "area_rai": _decimal(contribution["area_rai"], "area_rai", positive=True),
            "crop_type": _nonblank(contribution["crop_type"], "crop_type"),
            "crop_stage": _nonblank(contribution["crop_stage"], "crop_stage"),
            "net_volume_m3": _decimal(
                contribution["net_volume_m3"], "contribution net_volume_m3"
            ),
            "source_payload_hash": _sha256(
                contribution["source_payload_hash"], "source_payload_hash"
            ),
        }
    except KeyError as exc:
        raise RequirementRepositoryError(
            f"contribution is missing {exc.args[0]}"
        ) from exc


async def start_requirement_run(
    conn,
    *,
    as_of_date: date,
    horizon_start: date,
    horizon_end: date,
    input_cutoff_at: datetime,
    section_dataset_version_id: int,
    gate_mapping_dataset_version_id: int,
    crop_register_version: str,
    weather_version: str,
    method_version: str,
    content_hash: str,
    run_id: UUID | None = None,
    computed_at: datetime | None = None,
) -> dict:
    as_of = _date(as_of_date, "as_of_date")
    start = _date(horizon_start, "horizon_start")
    end = _date(horizon_end, "horizon_end")
    if start != as_of or start > end:
        raise RequirementRepositoryError(
            "horizon_start must equal as_of_date and not follow horizon_end"
        )
    run_uuid = uuid4() if run_id is None else _uuid(run_id, "run_id")
    cutoff = _aware(input_cutoff_at, "input_cutoff_at")
    computed = _aware(
        datetime.now(timezone.utc) if computed_at is None else computed_at,
        "computed_at",
    )
    if cutoff > computed:
        raise RequirementRepositoryError("input_cutoff_at must not follow computed_at")
    row = await conn.fetchrow(
        INSERT_RUN,
        run_uuid,
        as_of,
        start,
        end,
        cutoff,
        _positive_int(section_dataset_version_id, "section_dataset_version_id"),
        _positive_int(
            gate_mapping_dataset_version_id, "gate_mapping_dataset_version_id"
        ),
        _nonblank(crop_register_version, "crop_register_version"),
        _nonblank(weather_version, "weather_version"),
        _nonblank(method_version, "method_version"),
        _sha256(content_hash, "content_hash"),
        computed,
    )
    return _row_dict(row)


async def publish_requirement_run(
    conn,
    run_id: UUID,
    requirements: Sequence[Mapping],
    contributions: Sequence[Mapping] = (),
    *,
    published_at: datetime | None = None,
) -> list[dict]:
    run_uuid = _uuid(run_id, "run_id")
    if not requirements:
        raise RequirementRepositoryError(
            "a publication must contain at least one requirement"
        )
    published = _aware(
        datetime.now(timezone.utc) if published_at is None else published_at,
        "published_at",
    )
    async with conn.transaction():
        run = await conn.fetchrow(LOCK_RUN, run_uuid)
        if run is None:
            raise RequirementRepositoryError(
                f"requirement run {run_uuid} does not exist"
            )
        if run["status"] != "calculating":
            raise RequirementRepositoryError(
                f"requirement run must be calculating, got {run['status']!r}"
            )
        if published < run["computed_at"]:
            raise RequirementRepositoryError(
                "published_at must not precede computed_at"
            )
        validated_requirements = [
            _validate_requirement(
                item,
                run["as_of_date"],
                run["horizon_start"],
                run["horizon_end"],
            )
            for item in requirements
        ]
        for item in validated_requirements:
            if item["zone"] > 6:
                raise RequirementRepositoryError("zone must be between 1 and 6")
        identities = [
            (item["service_date"], item["section_id"])
            for item in validated_requirements
        ]
        requirement_ids = [item["requirement_id"] for item in validated_requirements]
        if len(set(identities)) != len(identities):
            raise RequirementRepositoryError(
                "requirements must be unique per service_date and section_id"
            )
        if len(set(requirement_ids)) != len(requirement_ids):
            raise RequirementRepositoryError("requirement_id values must be unique")

        validated_contributions = [
            _validate_contribution(item, set(requirement_ids)) for item in contributions
        ]
        contribution_keys = [
            (item["requirement_id"], item["area_id"])
            for item in validated_contributions
        ]
        if len(set(contribution_keys)) != len(contribution_keys):
            raise RequirementRepositoryError(
                "contributions must be unique per requirement_id and area_id"
            )
        contributed_volume: dict[UUID, Decimal] = defaultdict(Decimal)
        for item in validated_contributions:
            contributed_volume[item["requirement_id"]] += item["net_volume_m3"]
        requirement_by_id = {
            item["requirement_id"]: item for item in validated_requirements
        }
        for requirement_id, volume in contributed_volume.items():
            if volume != requirement_by_id[requirement_id]["required_net_volume_m3"]:
                raise RequirementRepositoryError(
                    "contribution net volume must equal requirement net volume"
                )

        await conn.executemany(
            INSERT_REQUIREMENTS,
            [
                (
                    item["requirement_id"],
                    run_uuid,
                    item["service_date"],
                    item["zone"],
                    item["section_id"],
                    item["required_net_volume_m3"],
                    item["required_gross_volume_m3"],
                    item["delivery_window_start"],
                    item["delivery_window_end"],
                    item["quality"],
                    json.dumps(
                        item["input_versions"],
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    ),
                    item["content_hash"],
                )
                for item in validated_requirements
            ],
        )
        if validated_contributions:
            await conn.executemany(
                INSERT_CONTRIBUTIONS,
                [
                    (
                        item["requirement_id"],
                        item["area_id"],
                        item["area_rai"],
                        item["crop_type"],
                        item["crop_stage"],
                        item["net_volume_m3"],
                        item["source_payload_hash"],
                    )
                    for item in validated_contributions
                ],
            )
        await conn.execute(SUPERSEDE_PUBLISHED_RUN, run["as_of_date"], run_uuid)
        result = await conn.fetchrow(MARK_PUBLISHED, run_uuid, published)
        if result is None:
            raise RequirementRepositoryError(
                "requirement run was no longer calculating during publication"
            )
    return [{**item, "run_id": run_uuid} for item in validated_requirements]


async def fail_requirement_run(conn, run_id: UUID, failure_reason: str) -> dict:
    run_uuid = _uuid(run_id, "run_id")
    reason = _nonblank(failure_reason, "failure_reason")
    row = await conn.fetchrow(MARK_FAILED, run_uuid, reason)
    if row is None:
        raise RequirementRepositoryError(
            "requirement run must exist and be calculating to fail"
        )
    return _row_dict(row)


async def get_published_requirements(conn, as_of_date: date) -> list[dict]:
    rows = await conn.fetch(
        SELECT_PUBLISHED_REQUIREMENTS, _date(as_of_date, "as_of_date")
    )
    return [_row_dict(row) for row in rows]
