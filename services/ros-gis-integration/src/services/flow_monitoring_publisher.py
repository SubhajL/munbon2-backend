"""Immutable section-demand publication to flow-monitoring."""

from typing import Mapping, Sequence

import httpx


def build_flow_demand_records(records: Sequence[Mapping]) -> list[dict]:
    result: list[dict] = []
    for row in records:
        window_start = row["delivery_window_start"]
        window_end = row["delivery_window_end"]
        input_versions = dict(row["input_versions"])
        input_versions["local_requirement_id"] = str(row["requirement_id"])
        input_versions["requirement_method"] = row["requirement_method_version"]
        result.append(
            {
                "area_type": "section",
                "area_id": row["section_id"],
                "period_start": window_start.isoformat(),
                "period_end": window_end.isoformat(),
                "timezone": "Asia/Bangkok",
                "volume_m3": float(row["required_net_volume_m3"]),
                "scheduled_delivery_intervals": [
                    {"start": window_start.isoformat(), "end": window_end.isoformat()}
                ],
                "quality": row["quality"],
                "input_versions": input_versions,
                "method": "ros_daily_requirement_v1",
                "source_service": "ros-gis-integration",
                "source_version": str(row["run_id"]),
                "synthetic": False,
                "computed_at": row["computed_at"].isoformat(),
                "version": int(row["downstream_version"]),
                "idempotency_key": f"ros-gis-requirement:{row['requirement_id']}",
            }
        )
    return result


class FlowMonitoringDemandPublisher:
    def __init__(self, base_url: str, client=None):
        self.base_url = base_url.rstrip("/")
        self.client = client

    async def publish(self, records: Sequence[Mapping]) -> None:
        demands = build_flow_demand_records(records)
        if not demands:
            return
        url = f"{self.base_url}/api/v1/control/demands"
        if self.client is not None:
            response = await self.client.post(url, json={"demands": demands})
            response.raise_for_status()
            return
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json={"demands": demands})
            response.raise_for_status()
