"""
core.demand_contract — pure Wave 2.4 demand/allocation/actual contract semantics.

The ratified conversion (WAVE_2-4_PLAN §1.5 HIGH #8) is m³/s = m³ ÷ SCHEDULED-delivery-
seconds: demand volume turns into flow over the scheduled delivery window(s), never over
whole-period elapsed time (a 7-day period with a 72 h window is 1.2 m³/s for 311,040 m³,
not 0.514). All instants are tz-aware and normalized to UTC; the record's IANA timezone
field only declares local interpretation. Synthetic lineage is rejected by policy
(HIGH #10) — fabricated inputs must never enter the versioned stores.

Pure module: no I/O, no clock reads (`now` is always an argument) — keep it that way.
"""
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

__all__ = [
    "DemandContractError",
    "MAX_CLOCK_SKEW",
    "canonical_json",
    "content_hash",
    "ensure_aware_utc",
    "flow_rate_m3s",
    "scheduled_delivery_seconds",
    "validate_computed_at",
    "validate_intervals_within_period",
    "validate_lineage",
    "validate_period_bounds",
    "validate_timezone_name",
]

MAX_CLOCK_SKEW = timedelta(minutes=5)


class DemandContractError(ValueError):
    """A record violates the demand/allocation/delivery contract."""


def ensure_aware_utc(instant: datetime, label: str) -> datetime:
    """The single UTC-normalization rule: tz-aware in, UTC out (schema + core)."""
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise DemandContractError(f"{label} must be timezone-aware")
    return instant.astimezone(timezone.utc)


def validate_period_bounds(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """Normalize period bounds to UTC; start must come strictly before end."""
    start_utc = ensure_aware_utc(start, "period start")
    end_utc = ensure_aware_utc(end, "period end")
    if start_utc >= end_utc:
        raise DemandContractError("period start must come before period end")
    return start_utc, end_utc


def scheduled_delivery_seconds(intervals: list[tuple[datetime, datetime]]) -> float:
    """Total scheduled delivery time: the divisor of the m³ → m³/s conversion.

    Intervals must be tz-aware, individually non-empty, and mutually non-overlapping
    (touching endpoints are contiguous scheduling, not overlap). Order is irrelevant.
    """
    if not intervals:
        raise DemandContractError("scheduled delivery needs at least one interval")
    normalized = [validate_period_bounds(start, end) for start, end in intervals]
    normalized.sort()
    for (_, prev_end), (next_start, _) in zip(normalized, normalized[1:]):
        if next_start < prev_end:
            raise DemandContractError("scheduled delivery intervals must not overlap")
    return sum((end - start).total_seconds() for start, end in normalized)


def flow_rate_m3s(volume_m3: float, scheduled_seconds: float) -> float:
    """m³/s = m³ ÷ scheduled-delivery-seconds (the ratified 2.4 semantics)."""
    if not math.isfinite(volume_m3) or volume_m3 < 0:
        raise DemandContractError("volume_m3 must be finite and non-negative")
    if not math.isfinite(scheduled_seconds) or scheduled_seconds <= 0:
        raise DemandContractError("scheduled seconds must be finite and positive")
    return volume_m3 / scheduled_seconds


def validate_intervals_within_period(
    period_start: datetime,
    period_end: datetime,
    intervals: list[tuple[datetime, datetime]],
) -> None:
    """Every scheduled interval must lie within the record's period bounds."""
    start_utc, end_utc = validate_period_bounds(period_start, period_end)
    for start, end in intervals:
        i_start, i_end = validate_period_bounds(start, end)
        if i_start < start_utc or i_end > end_utc:
            raise DemandContractError(
                "scheduled delivery intervals must lie within the record period"
            )


def validate_timezone_name(name: str) -> None:
    """The record's declared local timezone must be a real IANA name."""
    if not name or not name.strip():
        raise DemandContractError("timezone must be a non-empty IANA name")
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise DemandContractError(f"unknown IANA timezone: {name!r}") from exc


def validate_lineage(
    source_service: str, source_version: str, method: str, synthetic: bool
) -> None:
    """Reject synthetic lineage by policy and require every provenance field."""
    for field, value in (
        ("source_service", source_service),
        ("source_version", source_version),
        ("method", method),
    ):
        if not value or not value.strip():
            raise DemandContractError(f"{field} must be non-empty")
    if synthetic:
        raise DemandContractError(
            "synthetic records are rejected by policy — fabricated inputs must not "
            "enter the demand/allocation/delivery stores"
        )


def validate_computed_at(computed_at: datetime, now: datetime) -> None:
    """A record's computation instant may not sit in the future beyond clock skew."""
    computed_utc = ensure_aware_utc(computed_at, "computed_at")
    now_utc = ensure_aware_utc(now, "now")
    if computed_utc > now_utc + MAX_CLOCK_SKEW:
        raise DemandContractError("computed_at lies in the future")


def _reject_nonfinite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise DemandContractError("record values must be finite for hashing")
    if isinstance(value, dict):
        for nested in value.values():
            _reject_nonfinite(nested)
    if isinstance(value, (list, tuple)):
        for nested in value:
            _reject_nonfinite(nested)


def canonical_json(record: dict) -> str:
    """THE canonical serialization: what gets hashed is what gets stored.

    One algorithm on purpose (no second copy) — if these dump settings ever
    change, hash and stored payload move together.
    """
    _reject_nonfinite(record)
    return json.dumps(
        record, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str
    )


def content_hash(record: dict) -> str:
    """sha256 of the canonical serialization: key-order independent."""
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()
