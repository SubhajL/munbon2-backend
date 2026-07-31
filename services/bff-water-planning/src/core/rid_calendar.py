"""Administrative irrigation calendar and source-driven crop activity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

CONTRACT_SET_SHA256 = "987006c64402e79b9cb7af29358283f4cb368203cbd46935490a7ff453115539"

ANCHOR_MONTH = 11
ANCHOR_DAY = 1
WEEKS_PER_IRRIGATION_YEAR = 53
MIN_IRRIGATION_YEAR_CE = 1901
MAX_IRRIGATION_YEAR_CE = 2401
BE_OFFSET = 543


def _check_civil_date(value: date, name: str) -> None:
    if type(value) is not date:
        raise TypeError(f"{name} must be a datetime.date, not {type(value).__name__}")


@dataclass(frozen=True)
class IrrigationYear:
    ce: int
    be: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.ce, bool)
            or not isinstance(self.ce, int)
            or isinstance(self.be, bool)
            or not isinstance(self.be, int)
        ):
            raise TypeError("irrigation year CE and BE values must be integers")
        if not MIN_IRRIGATION_YEAR_CE <= self.ce <= MAX_IRRIGATION_YEAR_CE:
            raise ValueError(
                f"irrigation year CE {self.ce} outside supported range "
                f"{MIN_IRRIGATION_YEAR_CE}..{MAX_IRRIGATION_YEAR_CE}"
            )
        if self.be != self.ce + BE_OFFSET:
            raise ValueError("irrigation year BE must equal CE + 543")

    @classmethod
    def from_ce(cls, value: int) -> IrrigationYear:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("irrigation year CE value must be an integer")
        return cls(ce=value, be=value + BE_OFFSET)

    @classmethod
    def from_be(cls, value: int) -> IrrigationYear:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("irrigation year BE value must be an integer")
        return cls(ce=value - BE_OFFSET, be=value)


@dataclass(frozen=True)
class DateSpan:
    start: date
    end: date

    def __post_init__(self) -> None:
        _check_civil_date(self.start, "start")
        _check_civil_date(self.end, "end")
        if self.end < self.start:
            raise ValueError("date span end must not precede start")


@dataclass(frozen=True)
class IrrigationWeek:
    irrigation_year: IrrigationYear
    irrigation_week: int

    def __post_init__(self) -> None:
        if type(self.irrigation_year) is not IrrigationYear:
            raise TypeError("irrigation_year must be an IrrigationYear")
        if isinstance(self.irrigation_week, bool) or not isinstance(
            self.irrigation_week,
            int,
        ):
            raise TypeError("irrigation_week must be an integer")
        if not 1 <= self.irrigation_week <= WEEKS_PER_IRRIGATION_YEAR:
            raise ValueError(
                "irrigation_week must be within " f"1..{WEEKS_PER_IRRIGATION_YEAR}"
            )

    @property
    def key(self) -> str:
        return f"{self.irrigation_year.ce:04d}-R{self.irrigation_week:02d}"


class CropActivityState(str, Enum):
    NOT_PLANTED = "not_planted"
    ACTIVE = "active"
    HARVESTED = "harvested"


@dataclass(frozen=True)
class CropActivity:
    state: CropActivityState
    crop_week: int | None

    def __post_init__(self) -> None:
        if type(self.state) is not CropActivityState:
            raise TypeError("state must be a CropActivityState")
        if self.state is CropActivityState.ACTIVE:
            if (
                isinstance(self.crop_week, bool)
                or not isinstance(self.crop_week, int)
                or self.crop_week < 1
            ):
                raise ValueError("active crop activity requires a positive crop week")
        elif self.crop_week is not None:
            raise ValueError("inactive crop activity must not carry a crop week")


def _irrigation_year_span(identity: IrrigationYear) -> DateSpan:
    return DateSpan(
        start=date(identity.ce - 1, ANCHOR_MONTH, ANCHOR_DAY),
        end=date(identity.ce, 10, 31),
    )


def irrigation_year(day: date) -> IrrigationYear:
    """Return the ending-year CE/BE identity containing the civil date."""
    _check_civil_date(day, "day")
    ending_year = (
        day.year + 1 if (day.month, day.day) >= (ANCHOR_MONTH, ANCHOR_DAY) else day.year
    )
    return IrrigationYear.from_ce(ending_year)


def irrigation_week(day: date) -> IrrigationWeek:
    """Return the administrative irrigation week containing the civil date."""
    identity = irrigation_year(day)
    offset = (day - _irrigation_year_span(identity).start).days
    return IrrigationWeek(
        irrigation_year=identity,
        irrigation_week=offset // 7 + 1,
    )


def irrigation_week_span(week: IrrigationWeek) -> DateSpan:
    """Return the inclusive span of an irrigation week."""
    if type(week) is not IrrigationWeek:
        raise TypeError("week must be an IrrigationWeek")
    year_span = _irrigation_year_span(week.irrigation_year)
    start = year_span.start + timedelta(days=7 * (week.irrigation_week - 1))
    return DateSpan(start=start, end=min(start + timedelta(days=6), year_span.end))


def crop_activity(
    planting_date: date,
    expected_harvest_date: date,
    on: date,
) -> CropActivity:
    """Return crop state and week for a source-provided active window."""
    _check_civil_date(planting_date, "planting_date")
    _check_civil_date(expected_harvest_date, "expected_harvest_date")
    _check_civil_date(on, "on")
    if expected_harvest_date < planting_date:
        raise ValueError("expected harvest date must not precede planting date")
    if on < planting_date:
        return CropActivity(CropActivityState.NOT_PLANTED, None)
    if on > expected_harvest_date:
        return CropActivity(CropActivityState.HARVESTED, None)
    return CropActivity(
        CropActivityState.ACTIVE,
        (on - planting_date).days // 7 + 1,
    )
