"""The active crop week sent to ROS comes from source-provided plot dates."""

import inspect
from datetime import date

import pytest

from clients.ros_client import ROSClient
from services.daily_demand_calculator import DailyDemandCalculator

PLOT = {
    "plot_id": "P-1",
    "crop_type": "rice",
    "area_rai": 10,
    "section_id": None,
}


class RecordingROSClient:
    def __init__(self):
        self.demand_inputs = []

    async def calculate_water_demand(self, demand_input: dict):
        self.demand_inputs.append(demand_input)
        return {"netWaterDemandM3": 700}


class SilentLogger:
    def error(self, *args, **kwargs):
        raise AssertionError(f"unexpected error log: {args} {kwargs}")

    def warning(self, *args, **kwargs):
        pass


def _calculator(ros_client):
    calculator = DailyDemandCalculator.__new__(DailyDemandCalculator)
    calculator.ros_client = ros_client
    calculator.water_level_client = None
    calculator.logger = SilentLogger()
    return calculator


def test_fake_ros_client_pins_the_real_pricing_interface():
    real = inspect.signature(ROSClient.calculate_water_demand)
    fake = inspect.signature(RecordingROSClient.calculate_water_demand)
    assert list(real.parameters) == list(fake.parameters)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "observed_on, crop_week",
    [
        (date(2026, 7, 15), 1),
        (date(2026, 7, 21), 1),
        (date(2026, 7, 22), 2),
        (date(2026, 12, 15), 22),
    ],
)
async def test_active_crop_week_is_sent_to_ros_without_reloading_a_calendar(
    observed_on,
    crop_week,
):
    ros_client = RecordingROSClient()

    await _calculator(ros_client)._calculate_ros_demand(
        PLOT,
        observed_on,
        crop_week,
    )

    assert ros_client.demand_inputs == [
        {
            "areaId": "P-1",
            "cropType": "rice",
            "areaType": "plot",
            "areaRai": 10,
            "cropWeek": crop_week,
            "calendarWeek": observed_on.isocalendar()[1],
            "calendarYear": observed_on.year,
            "growthStage": "seedling" if crop_week <= 3 else "maturity",
        }
    ]
