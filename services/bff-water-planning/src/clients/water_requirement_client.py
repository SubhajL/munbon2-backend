from datetime import date
from urllib.parse import quote

import httpx

from config import settings
from core import get_logger

logger = get_logger(__name__)


class WaterRequirementClientError(RuntimeError):
    pass


class WaterRequirementClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.ros_service_url).rstrip("/")
        self.timeout = httpx.Timeout(30.0, connect=5.0)

    async def _get(self, path: str, params: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}{path}", params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.error(
                "Canonical water requirement request failed",
                path=path,
                error=str(exc),
            )
            raise WaterRequirementClientError(str(exc)) from exc
        if not isinstance(payload, dict):
            raise WaterRequirementClientError(
                "canonical water requirement response must be an object"
            )
        return payload

    async def get_daily_requirements(self, service_date: date, zone: int) -> dict:
        return await self._get(
            "/api/v1/water-requirements/daily",
            {"service_date": service_date.isoformat(), "zone": zone},
        )

    async def get_section_requirement_history(
        self,
        section_id: str,
        from_date: date,
        to_date: date,
    ) -> dict:
        encoded_section_id = quote(section_id, safe="")
        return await self._get(
            f"/api/v1/water-requirements/sections/{encoded_section_id}",
            {"from": from_date.isoformat(), "to": to_date.isoformat()},
        )
