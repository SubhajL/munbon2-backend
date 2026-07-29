"""Properties of the administrative irrigation calendar and crop activity."""

from datetime import date, datetime, timedelta

import pytest

from core.rid_calendar import (
    CropActivityState,
    IrrigationYear,
    crop_activity,
    irrigation_week,
    irrigation_week_span,
    irrigation_year,
)

IRRIGATION_YEAR_CE_VALUES = range(2024, 2032)
EDGE_IRRIGATION_YEAR_CE_VALUES = (1901, 2100, 2101, 2401)


def _expected_irrigation_year_span(irrigation_year_ce: int) -> tuple[date, date]:
    return date(irrigation_year_ce - 1, 11, 1), date(irrigation_year_ce, 10, 31)


def _every_day(irrigation_year_ce: int):
    day, end = _expected_irrigation_year_span(irrigation_year_ce)
    while day <= end:
        yield day
        day += timedelta(days=1)


def test_every_date_maps_to_the_ending_year_identity():
    for irrigation_year_ce in IRRIGATION_YEAR_CE_VALUES:
        for day in _every_day(irrigation_year_ce):
            identity = irrigation_year(day)
            assert (identity.ce, identity.be) == (
                irrigation_year_ce,
                irrigation_year_ce + 543,
            )


def test_week_numbers_are_non_decreasing_and_cover_exactly_1_to_53():
    for irrigation_year_ce in IRRIGATION_YEAR_CE_VALUES:
        observed = [
            irrigation_week(day).irrigation_week
            for day in _every_day(irrigation_year_ce)
        ]
        assert observed == sorted(observed)
        assert set(observed) == set(range(1, 54))


def test_week_spans_tile_the_irrigation_year_without_gap_or_overlap():
    for irrigation_year_ce in IRRIGATION_YEAR_CE_VALUES:
        year_start, year_end = _expected_irrigation_year_span(irrigation_year_ce)
        cursor = year_start
        first_identity = irrigation_week(year_start)
        for week_number in range(1, 54):
            identity = type(first_identity)(
                irrigation_year=first_identity.irrigation_year,
                irrigation_week=week_number,
            )
            span = irrigation_week_span(identity)
            assert span.start == cursor
            assert span.end >= span.start
            assert irrigation_week(span.start) == identity
            cursor = span.end + timedelta(days=1)
        assert cursor == year_end + timedelta(days=1)


def test_irrigation_year_boundary_is_adjacent_and_uses_ending_label():
    assert irrigation_week(date(2024, 10, 31)).key == "2024-R53"
    assert irrigation_week(date(2024, 11, 1)).key == "2025-R01"
    assert irrigation_week(date(2025, 10, 31)).key == "2025-R53"
    assert irrigation_week(date(2025, 11, 1)).key == "2026-R01"


def test_irrigation_year_converts_between_matching_ce_and_be_values():
    expected = IrrigationYear(ce=2025, be=2568)

    assert IrrigationYear.from_ce(2025) == expected
    assert IrrigationYear.from_be(2568) == expected


def test_irrigation_year_rejects_a_mismatched_era_pair():
    with pytest.raises(ValueError, match=r"CE \+ 543"):
        IrrigationYear(ce=2025, be=2567)


def test_irrigation_calendar_rejects_datetime_instants():
    with pytest.raises(TypeError):
        irrigation_week(datetime(2024, 11, 1, 12, 0))


@pytest.mark.parametrize(
    "irrigation_year_ce",
    EDGE_IRRIGATION_YEAR_CE_VALUES,
)
def test_century_and_supported_range_boundaries(irrigation_year_ce):
    import calendar

    start, end = _expected_irrigation_year_span(irrigation_year_ce)
    assert irrigation_year(start).ce == irrigation_year_ce
    assert irrigation_week(end).irrigation_week == 53
    week_53 = irrigation_week_span(irrigation_week(end))
    expected_length = 2 if calendar.isleap(irrigation_year_ce) else 1
    assert (week_53.end - week_53.start).days + 1 == expected_length


def test_supported_range_is_enforced_at_both_ends():
    assert irrigation_week(date(1900, 11, 1)).key == "1901-R01"
    assert irrigation_week(date(2401, 10, 31)).key == "2401-R53"
    with pytest.raises(ValueError):
        irrigation_week(date(1900, 10, 31))


@pytest.mark.parametrize(
    "observed_on, expected_state, expected_crop_week",
    [
        (date(2026, 7, 14), CropActivityState.NOT_PLANTED, None),
        (date(2026, 7, 15), CropActivityState.ACTIVE, 1),
        (date(2026, 7, 21), CropActivityState.ACTIVE, 1),
        (date(2026, 7, 22), CropActivityState.ACTIVE, 2),
        (date(2026, 12, 15), CropActivityState.ACTIVE, 22),
        (date(2026, 12, 16), CropActivityState.HARVESTED, None),
    ],
)
def test_crop_activity_is_bounded_by_source_provided_dates(
    observed_on,
    expected_state,
    expected_crop_week,
):
    observed = crop_activity(
        date(2026, 7, 15),
        date(2026, 12, 15),
        observed_on,
    )
    assert (observed.state, observed.crop_week) == (
        expected_state,
        expected_crop_week,
    )


def test_crop_activity_rejects_a_harvest_before_planting():
    with pytest.raises(ValueError, match="harvest"):
        crop_activity(
            date(2026, 7, 15),
            date(2026, 7, 14),
            date(2026, 7, 15),
        )
