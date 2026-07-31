"""Crop activity gates every demand engine before pricing or persistence."""

from datetime import date
from unittest.mock import AsyncMock

import pytest

from core.rid_calendar import CropActivityState, crop_activity
from services.daily_demand_calculator import DailyDemandCalculator

PLOT = {
    "plot_id": "P-1",
    "section_id": "SEC-1",
    "zone": 1,
    "area_rai": 10,
    "crop_type": "rice",
    "planting_date": date(2026, 7, 15),
    "expected_harvest_date": date(2026, 12, 15),
}
POSITIVE_ROS = {"net_demand_m3": 100, "source": "ros"}
POSITIVE_AQUACROP = {"net_demand_m3": 200, "source": "aquacrop"}


class SilentLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        raise AssertionError(f"unexpected error log: {args} {kwargs}")


def _calculator():
    calculator = DailyDemandCalculator.__new__(DailyDemandCalculator)
    calculator._initialized = True
    calculator.logger = SilentLogger()
    calculator._get_active_plots = AsyncMock(return_value=[PLOT])
    calculator._calculate_ros_demand = AsyncMock(return_value=POSITIVE_ROS)
    calculator._get_aquacrop_demand = AsyncMock(return_value=POSITIVE_AQUACROP)
    calculator._calculate_awd_demand = AsyncMock(
        return_value={"awd_enabled": False, "awd_demand_m3": 200}
    )
    calculator._store_daily_demands = AsyncMock()
    return calculator


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "observed_on, expected_state",
    [
        (date(2026, 7, 14), CropActivityState.NOT_PLANTED),
        (date(2026, 12, 16), CropActivityState.HARVESTED),
    ],
)
async def test_inactive_crop_skips_positive_engines_and_persistence(
    observed_on,
    expected_state,
):
    calculator = _calculator()

    result = await calculator.calculate_daily_demands(observed_on)

    assert (
        crop_activity(
            PLOT["planting_date"],
            PLOT["expected_harvest_date"],
            observed_on,
        ).state
        == expected_state
    )
    assert result == {}
    calculator._calculate_ros_demand.assert_not_awaited()
    calculator._get_aquacrop_demand.assert_not_awaited()
    calculator._calculate_awd_demand.assert_not_awaited()
    calculator._store_daily_demands.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_dates",
    [
        {"planting_date": None},
        {
            "planting_date": date(2026, 7, 15),
            "expected_harvest_date": date(2026, 7, 14),
        },
    ],
)
async def test_invalid_crop_window_skips_positive_engines_and_persistence(
    invalid_dates,
):
    calculator = _calculator()
    calculator._get_active_plots.return_value = [{**PLOT, **invalid_dates}]

    result = await calculator.calculate_daily_demands(date(2026, 7, 15))

    assert result == {}
    calculator._calculate_ros_demand.assert_not_awaited()
    calculator._get_aquacrop_demand.assert_not_awaited()
    calculator._calculate_awd_demand.assert_not_awaited()
    calculator._store_daily_demands.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "observed_on, expected_crop_week",
    [
        (date(2026, 7, 15), 1),
        (date(2026, 12, 15), 22),
    ],
)
async def test_planting_and_harvest_dates_are_active(
    observed_on,
    expected_crop_week,
):
    calculator = _calculator()

    result = await calculator.calculate_daily_demands(observed_on)

    assert result["P-1"]["combined_demand_m3"] == 200
    calculator._calculate_ros_demand.assert_awaited_once_with(
        PLOT,
        observed_on,
        expected_crop_week,
    )
    calculator._get_aquacrop_demand.assert_awaited_once_with("P-1", observed_on)
    calculator._calculate_awd_demand.assert_awaited_once()
    calculator._store_daily_demands.assert_awaited_once_with(result)
