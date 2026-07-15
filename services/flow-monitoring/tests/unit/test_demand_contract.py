"""
Unit tests for core.demand_contract — the pure Wave 2.4 demand/allocation/actual
contract semantics (WAVE_2-4_PLAN §1.5 HIGH #8):

- m³/s = m³ ÷ SCHEDULED-delivery-seconds, never whole-period elapsed seconds;
- explicit tz-aware interval bounds (UTC instants + IANA timezone declaration);
- non-synthetic lineage rejected by policy (HIGH #10 receiving side);
- deterministic content hashing for immutability checks.

Pure module: no I/O, no clock reads (now is always an argument).
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from core.demand_contract import (
    DemandContractError,
    canonical_json,
    content_hash,
    demand_flow_at,
    ensure_aware_utc,
    flow_rate_m3s,
    scheduled_delivery_seconds,
    validate_computed_at,
    validate_intervals_within_period,
    validate_lineage,
    validate_period_bounds,
    validate_timezone_name,
)
from schemas.demand import DemandRecord

UTC = timezone.utc


def _utc(day: int, hour: int = 0) -> datetime:
    """A tz-aware UTC instant inside an arbitrary reference week (July 2026)."""
    return datetime(2026, 7, day, hour, tzinfo=UTC)


class TestScheduledDeliverySeconds:
    def test_single_interval_returns_its_duration(self):
        assert scheduled_delivery_seconds([(_utc(1, 6), _utc(1, 12))]) == 6 * 3600.0

    def test_multiple_intervals_sum_their_durations(self):
        intervals = [(_utc(1, 6), _utc(1, 12)), (_utc(2, 6), _utc(2, 12))]
        assert scheduled_delivery_seconds(intervals) == 12 * 3600.0

    def test_touching_intervals_are_allowed(self):
        # end == next start is contiguous scheduling, not an overlap
        intervals = [(_utc(1, 6), _utc(1, 12)), (_utc(1, 12), _utc(1, 18))]
        assert scheduled_delivery_seconds(intervals) == 12 * 3600.0

    def test_unordered_input_is_accepted_and_summed(self):
        intervals = [(_utc(2, 6), _utc(2, 12)), (_utc(1, 6), _utc(1, 12))]
        assert scheduled_delivery_seconds(intervals) == 12 * 3600.0

    def test_empty_interval_list_is_rejected(self):
        with pytest.raises(DemandContractError, match="at least one"):
            scheduled_delivery_seconds([])

    @pytest.mark.parametrize(
        "interval",
        [
            (datetime(2026, 7, 1, 6), _utc(1, 12)),  # naive start
            (_utc(1, 6), datetime(2026, 7, 1, 12)),  # naive end
        ],
    )
    def test_naive_datetimes_are_rejected(self, interval):
        with pytest.raises(DemandContractError, match="timezone-aware"):
            scheduled_delivery_seconds([interval])

    @pytest.mark.parametrize("start_hour,end_hour", [(12, 6), (6, 6)])
    def test_empty_or_reversed_interval_is_rejected(self, start_hour, end_hour):
        with pytest.raises(DemandContractError, match="before"):
            scheduled_delivery_seconds([(_utc(1, start_hour), _utc(1, end_hour))])

    def test_overlapping_intervals_are_rejected(self):
        intervals = [(_utc(1, 6), _utc(1, 12)), (_utc(1, 11), _utc(1, 18))]
        with pytest.raises(DemandContractError, match="overlap"):
            scheduled_delivery_seconds(intervals)


class TestFlowRateM3s:
    def test_ratified_semantics_divide_by_scheduled_seconds_not_period(self):
        # The 2569 plan's own figure: 311,040 m3 delivered over a 72 h scheduled
        # window inside a 7-day period is 1.2 m3/s. Dividing by the whole-period
        # 604,800 s (the pre-2.4 bug) would understate it as ~0.514 m3/s.
        volume_m3 = 311_040.0
        scheduled = scheduled_delivery_seconds([(_utc(1, 0), _utc(4, 0))])  # 72 h
        assert flow_rate_m3s(volume_m3, scheduled) == pytest.approx(1.2)
        whole_period_seconds = 7 * 24 * 3600.0
        assert flow_rate_m3s(volume_m3, scheduled) != pytest.approx(
            volume_m3 / whole_period_seconds
        )

    def test_zero_volume_gives_zero_flow(self):
        assert flow_rate_m3s(0.0, 3600.0) == 0.0

    @pytest.mark.parametrize("volume", [-1.0, float("nan"), float("inf")])
    def test_negative_or_nonfinite_volume_is_rejected(self, volume):
        with pytest.raises(DemandContractError, match="volume"):
            flow_rate_m3s(volume, 3600.0)

    @pytest.mark.parametrize("seconds", [0.0, -60.0, float("nan"), float("inf")])
    def test_nonpositive_or_nonfinite_seconds_are_rejected(self, seconds):
        with pytest.raises(DemandContractError, match="seconds"):
            flow_rate_m3s(100.0, seconds)


class TestValidatePeriodBounds:
    def test_returns_bounds_normalized_to_utc(self):
        bangkok = timezone(timedelta(hours=7))
        start_local = datetime(2026, 7, 1, 7, 0, tzinfo=bangkok)  # == 00:00 UTC
        start, end = validate_period_bounds(start_local, _utc(8))
        assert start == _utc(1) and start.tzinfo == UTC
        assert end == _utc(8)

    def test_naive_bound_is_rejected(self):
        with pytest.raises(DemandContractError, match="timezone-aware"):
            validate_period_bounds(datetime(2026, 7, 1), _utc(8))

    def test_start_not_before_end_is_rejected(self):
        with pytest.raises(DemandContractError, match="before"):
            validate_period_bounds(_utc(8), _utc(1))


class TestValidateIntervalsWithinPeriod:
    def test_intervals_inside_period_pass(self):
        validate_intervals_within_period(_utc(1), _utc(8), [(_utc(2, 6), _utc(2, 12))])

    @pytest.mark.parametrize(
        "interval",
        [
            ((_utc(1, 0) - timedelta(hours=1)), _utc(1, 12)),  # starts before period
            (_utc(7, 6), _utc(8, 6)),  # ends after period
        ],
    )
    def test_interval_escaping_period_is_rejected(self, interval):
        with pytest.raises(DemandContractError, match="within"):
            validate_intervals_within_period(_utc(1), _utc(8), [interval])


class TestValidateTimezoneName:
    def test_iana_name_passes(self):
        validate_timezone_name("Asia/Bangkok")

    @pytest.mark.parametrize("name", ["", "Bangkok/Nowhere", "UTC+7"])
    def test_unknown_or_empty_name_is_rejected(self, name):
        with pytest.raises(DemandContractError, match="timezone"):
            validate_timezone_name(name)


class TestValidateLineage:
    def test_complete_non_synthetic_lineage_passes(self):
        validate_lineage(
            source_service="bff-water-planning",
            source_version="1.4.0",
            method="ros",
            synthetic=False,
        )

    def test_synthetic_records_are_rejected_by_policy(self):
        # HIGH #10: the receiving contract rejects synthetic lineage outright —
        # fabricated plots/demands must never enter the versioned store.
        with pytest.raises(DemandContractError, match="[Ss]ynthetic"):
            validate_lineage(
                source_service="bff-water-planning",
                source_version="1.4.0",
                method="ros",
                synthetic=True,
            )

    @pytest.mark.parametrize(
        "field,value",
        [("source_service", ""), ("source_version", " "), ("method", "")],
    )
    def test_blank_lineage_fields_are_rejected(self, field, value):
        kwargs = {
            "source_service": "bff-water-planning",
            "source_version": "1.4.0",
            "method": "ros",
            "synthetic": False,
        }
        kwargs[field] = value
        with pytest.raises(DemandContractError, match=field):
            validate_lineage(**kwargs)


class TestValidateComputedAt:
    def test_past_instant_passes(self):
        validate_computed_at(_utc(1, 0), now=_utc(1, 6))

    def test_small_clock_skew_is_tolerated(self):
        validate_computed_at(
            _utc(
                1,
                6,
            )
            + timedelta(seconds=60),
            now=_utc(1, 6),
        )

    def test_future_instant_beyond_skew_is_rejected(self):
        with pytest.raises(DemandContractError, match="future"):
            validate_computed_at(_utc(1, 7), now=_utc(1, 6))

    def test_naive_instant_is_rejected(self):
        with pytest.raises(DemandContractError, match="timezone-aware"):
            validate_computed_at(datetime(2026, 7, 1), now=_utc(1, 6))


class TestContentHash:
    def test_deterministic_and_key_order_independent(self):
        a = {"volume_m3": 311040.0, "area_id": "Z1", "nested": {"x": 1, "y": 2}}
        b = {"nested": {"y": 2, "x": 1}, "area_id": "Z1", "volume_m3": 311040.0}
        assert content_hash(a) == content_hash(b)
        assert len(content_hash(a)) == 64  # sha256 hex

    def test_value_change_changes_hash(self):
        base = {"volume_m3": 311040.0, "area_id": "Z1"}
        changed = {"volume_m3": 311041.0, "area_id": "Z1"}
        assert content_hash(base) != content_hash(changed)

    def test_nonfinite_values_are_rejected_not_serialized(self):
        with pytest.raises(DemandContractError, match="finite"):
            content_hash({"volume_m3": float("nan")})

    def test_hash_is_sha256_of_the_single_canonical_serialization(self):
        # One canonicalization algorithm: the stored payload and the hash input
        # must be the same bytes (QCHECK tier-1 #10).
        import hashlib

        record = {"b": 2, "a": {"y": [1.5, 2], "x": "ผ"}}
        blob = canonical_json(record)
        assert json.loads(blob) == record
        assert blob == canonical_json(json.loads(blob))  # round-trip stable
        assert content_hash(record) == hashlib.sha256(blob.encode("utf-8")).hexdigest()


class TestEnsureAwareUtc:
    def test_converts_offset_to_utc(self):
        bangkok = timezone(timedelta(hours=7))
        instant = ensure_aware_utc(
            datetime(2026, 7, 1, 7, tzinfo=bangkok), "computed_at"
        )
        assert instant == _utc(1) and instant.tzinfo == UTC

    def test_naive_is_rejected_with_the_labelled_field(self):
        with pytest.raises(DemandContractError, match="computed_at"):
            ensure_aware_utc(datetime(2026, 7, 1), "computed_at")


def _demand_record(intervals: list[tuple[datetime, datetime]]) -> DemandRecord:
    return DemandRecord(
        area_type="node",
        area_id="M(0,3)",
        timezone="Asia/Bangkok",
        method="daily_requirement",
        source_service="ros-gis-integration",
        source_version="run-2026-07-01-v1",
        synthetic=False,
        computed_at=_utc(1),
        version=1,
        idempotency_key="requirement-M(0,3)-2026-07-01-v1",
        period_start=_utc(1),
        period_end=_utc(3),
        volume_m3=43_200.0,
        scheduled_delivery_intervals=[
            {"start": start, "end": end} for start, end in intervals
        ],
        quality="estimated",
    )


class TestDemandFlowAt:
    def test_active_interval_uses_total_scheduled_seconds(self):
        record = _demand_record([(_utc(1, 6), _utc(1, 12)), (_utc(2, 6), _utc(2, 12))])

        assert demand_flow_at(record, _utc(1, 9)) == (True, 1.0)

    def test_interval_end_is_inactive(self):
        record = _demand_record([(_utc(1, 6), _utc(1, 12))])

        assert demand_flow_at(record, _utc(1, 12)) == (False, 0.0)

    def test_time_between_split_intervals_contributes_zero(self):
        record = _demand_record([(_utc(1, 6), _utc(1, 12)), (_utc(2, 6), _utc(2, 12))])

        assert demand_flow_at(record, _utc(1, 18)) == (False, 0.0)

    def test_naive_effective_at_is_rejected(self):
        record = _demand_record([(_utc(1, 6), _utc(1, 12))])

        with pytest.raises(DemandContractError, match="effective_at"):
            demand_flow_at(record, datetime(2026, 7, 1, 9))
