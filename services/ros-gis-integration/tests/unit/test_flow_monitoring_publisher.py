from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from services.flow_monitoring_publisher import (
    FlowMonitoringDemandPublisher,
    build_flow_demand_records,
)

UTC = timezone.utc
RUN_ID = UUID("11111111-1111-4111-8111-111111111111")
REQUIREMENT_ID = UUID("22222222-2222-4222-8222-222222222222")


def _record():
    return {
        "requirement_id": REQUIREMENT_ID,
        "run_id": RUN_ID,
        "service_date": date(2026, 7, 16),
        "section_id": "01-01-01-03",
        "required_net_volume_m3": Decimal("73.600000"),
        "delivery_window_start": datetime(2026, 7, 15, 19, tzinfo=UTC),
        "delivery_window_end": datetime(2026, 7, 16, 19, tzinfo=UTC),
        "quality": "estimated",
        "input_versions": {"crop_register": "crop-v1"},
        "requirement_method_version": "daily-requirement-v2",
        "computed_at": datetime(2026, 7, 15, 19, tzinfo=UTC),
        "downstream_version": 2,
    }


def test_build_flow_demand_records_preserves_immutable_section_lineage():
    assert build_flow_demand_records([_record()]) == [
        {
            "area_type": "section",
            "area_id": "01-01-01-03",
            "period_start": "2026-07-15T19:00:00+00:00",
            "period_end": "2026-07-16T19:00:00+00:00",
            "timezone": "Asia/Bangkok",
            "volume_m3": 73.6,
            "scheduled_delivery_intervals": [
                {
                    "start": "2026-07-15T19:00:00+00:00",
                    "end": "2026-07-16T19:00:00+00:00",
                }
            ],
            "quality": "estimated",
            "input_versions": {
                "crop_register": "crop-v1",
                "local_requirement_id": str(REQUIREMENT_ID),
                "requirement_method": "daily-requirement-v2",
            },
            "method": "ros_daily_requirement_v1",
            "source_service": "ros-gis-integration",
            "source_version": str(RUN_ID),
            "synthetic": False,
            "computed_at": "2026-07-15T19:00:00+00:00",
            "version": 2,
            "idempotency_key": f"ros-gis-requirement:{REQUIREMENT_ID}",
        }
    ]


class _Response:
    def __init__(self, error=None):
        self.error = error

    def raise_for_status(self):
        if self.error is not None:
            raise self.error


class _Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def post(self, url, json):
        self.calls.append((url, json))
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_publisher_transport_retry_reuses_identical_idempotency_payload():
    client = _Client([_Response(RuntimeError("unavailable")), _Response()])
    publisher = FlowMonitoringDemandPublisher("http://flow:3011/", client=client)

    with pytest.raises(RuntimeError, match="unavailable"):
        await publisher.publish([_record()])
    await publisher.publish([_record()])

    assert client.calls[0] == client.calls[1]
    assert client.calls[0][0] == "http://flow:3011/api/v1/control/demands"
    assert client.calls[0][1]["demands"][0]["idempotency_key"] == (
        f"ros-gis-requirement:{REQUIREMENT_ID}"
    )


@pytest.mark.asyncio
async def test_publisher_skips_empty_batches_without_transport_call():
    client = _Client([])

    await FlowMonitoringDemandPublisher("http://flow:3011", client=client).publish([])

    assert client.calls == []
