"""Strict ROS-GIS canonical-requirements client (PR 4.3a).

Reads `GET /api/v1/water-requirements/daily` per (service_date, zone) scope and
verifies every returned item against the caller-pinned run/version. The daily
route is a drifting latest-pointer, so any mismatch is surfaced as an exact-
version conflict instead of silently planning against different requirements.
No `{"data": ...}` envelope unwrapping: the route returns the bare model.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal, Optional, Sequence
from uuid import UUID

import httpx
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
)


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("upstream datetime carries no timezone offset")
    return value


_AwareDatetime = Annotated[datetime, AfterValidator(_require_aware)]

from .control_client_errors import (
    RequirementStateError,
    RequirementsUnpublishedError,
    UpstreamContractViolation,
    UpstreamUnavailableError,
)

_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


class _Mirror(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class _DeliveryWindowMirror(_Mirror):
    start: _AwareDatetime
    end: _AwareDatetime


class _FreshnessMirror(_Mirror):
    as_of_date: date = Field(alias="asOfDate")


class _RequirementItemMirror(_Mirror):
    # Constraints mirror the persistence CHECK/UNIQUE invariants so a
    # contract-violating feed fails as a 502 at parse time, never as a NaN that
    # bricks canonical serialization or a Postgres IntegrityError seen as 503.
    requirement_id: UUID = Field(alias="requirementId")
    run_id: UUID = Field(alias="runId")
    version: int = Field(alias="version", gt=0)
    service_date: date = Field(alias="serviceDate")
    section_id: str = Field(alias="sectionId", min_length=1)
    zone: int = Field(ge=1, le=6)
    required_volume_m3: float = Field(
        alias="requiredVolumeM3", ge=0, allow_inf_nan=False
    )
    delivery_window: _DeliveryWindowMirror = Field(alias="deliveryWindow")
    quality: Literal["estimated", "forecast"]
    published_at: _AwareDatetime = Field(alias="publishedAt")
    freshness: _FreshnessMirror
    data_status: Literal[
        "no_publication", "stale", "published", "superseded"
    ] = Field(alias="dataStatus")


class _DailyResponseMirror(_Mirror):
    service_date: date = Field(alias="serviceDate")
    zone: int = Field(ge=1, le=6)
    data_status: Literal[
        "no_publication", "stale", "published", "superseded"
    ] = Field(alias="dataStatus")
    requirements: list[_RequirementItemMirror]


class RosGisRequirementsClient:
    def __init__(
        self,
        base_url: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=_TIMEOUT)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_exact_requirements(
        self,
        requirement_run_id: UUID,
        requirement_version: int,
        scopes: Sequence[tuple[date, int]],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen_keys: set[tuple[date, str]] = set()
        seen_requirement_ids: set[str] = set()
        for service_date, zone in scopes:
            payload = await self._fetch_daily(service_date, zone)
            if payload.data_status == "no_publication":
                raise RequirementsUnpublishedError(
                    f"no published requirement run covers {service_date} "
                    f"zone {zone}"
                )
            # A cache/proxy could echo a different scope while keeping the
            # pinned run/version — treat any scope drift as a malformed
            # response (502), never plan against the wrong zone/date.
            if payload.service_date != service_date or payload.zone != zone:
                raise UpstreamContractViolation(
                    "ros-gis daily response scope "
                    f"({payload.service_date}, zone {payload.zone}) does not "
                    f"match the requested ({service_date}, zone {zone})"
                )
            for item in payload.requirements:
                if item.service_date != service_date or item.zone != zone:
                    raise UpstreamContractViolation(
                        f"requirement {item.requirement_id} scope "
                        f"({item.service_date}, zone {item.zone}) does not "
                        f"match the requested ({service_date}, zone {zone})"
                    )
                if item.data_status != "published":
                    raise RequirementStateError(
                        "requirement is not in the published state",
                        {
                            "requirement_id": str(item.requirement_id),
                            "data_status": item.data_status,
                            "service_date": service_date.isoformat(),
                            "zone": zone,
                        },
                    )
                if (
                    item.run_id != requirement_run_id
                    or item.version != requirement_version
                ):
                    raise RequirementStateError(
                        "the published requirement run drifted from the "
                        "pinned run/version",
                        {
                            "pinned_run_id": str(requirement_run_id),
                            "pinned_version": requirement_version,
                            "served_run_id": str(item.run_id),
                            "served_version": item.version,
                            "service_date": service_date.isoformat(),
                            "zone": zone,
                        },
                    )
                # Field bounds (volume >= 0 and finite, quality/status enums,
                # zone 1..6, version > 0) are enforced by the strict mirror at
                # parse time, so a contract-violating item is already a 502 by
                # here. Cross-item uniqueness is enforced below to match the
                # persistence UNIQUE(service_date, section_id) and the
                # optimizer's unique-requirement-id contract.
                key = (item.service_date, item.section_id)
                if key in seen_keys:
                    raise UpstreamContractViolation(
                        "ros-gis returned two requirements for section "
                        f"{item.section_id} on {item.service_date}"
                    )
                seen_keys.add(key)
                requirement_id = str(item.requirement_id)
                if requirement_id in seen_requirement_ids:
                    raise UpstreamContractViolation(
                        f"ros-gis returned duplicate requirement id "
                        f"{requirement_id}"
                    )
                seen_requirement_ids.add(requirement_id)
                items.append(
                    {
                        "requirement_id": str(item.requirement_id),
                        "run_id": str(item.run_id),
                        "version": item.version,
                        "service_date": item.service_date,
                        "section_id": item.section_id,
                        "zone": item.zone,
                        "required_volume_m3": item.required_volume_m3,
                        "window_start": item.delivery_window.start,
                        "window_end": item.delivery_window.end,
                        "quality": item.quality,
                        "published_at": item.published_at,
                        "as_of_date": item.freshness.as_of_date,
                        "data_status": item.data_status,
                    }
                )
        return items

    async def _fetch_daily(
        self, service_date: date, zone: int
    ) -> _DailyResponseMirror:
        url = f"{self._base_url}/api/v1/water-requirements/daily"
        try:
            response = await self._client.get(
                url,
                params={
                    "service_date": service_date.isoformat(),
                    "zone": zone,
                },
            )
        except httpx.RequestError as error:
            raise UpstreamUnavailableError(
                f"ros-gis-integration is unreachable: {error}"
            ) from error
        if response.status_code >= 500:
            raise UpstreamUnavailableError(
                f"ros-gis-integration answered {response.status_code}"
            )
        if response.status_code != 200:
            raise UpstreamContractViolation(
                "ros-gis-integration rejected a daily-requirements read "
                f"({response.status_code}): {response.text[:500]}"
            )
        try:
            return _DailyResponseMirror.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            raise UpstreamContractViolation(
                f"ros-gis daily response violates its contract: {error}"
            ) from error
