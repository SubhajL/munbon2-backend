from datetime import date, datetime, timedelta, timezone
from typing import Literal, Mapping
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from db.water_requirement_repository import (
    get_daily_requirements,
    get_section_requirement_history,
)

DataStatus = Literal["no_publication", "stale", "published", "superseded"]
BANGKOK = ZoneInfo("Asia/Bangkok")
PUBLICATION_ROLLOVER_HOUR = 2

router = APIRouter(prefix="/api/v1/water-requirements", tags=["water-requirements"])


class DeliveryWindow(BaseModel):
    start: datetime
    end: datetime


class PublicationFreshness(BaseModel):
    asOfDate: date
    publishedAgeSeconds: int


class WaterRequirementItem(BaseModel):
    requirementId: UUID
    runId: UUID
    version: int
    serviceDate: date
    sectionId: str
    zone: int
    requiredVolumeM3: float
    deliveryWindow: DeliveryWindow
    quality: Literal["estimated", "forecast"]
    publishedAt: datetime
    freshness: PublicationFreshness
    dataStatus: DataStatus


class DailyWaterRequirementResponse(BaseModel):
    serviceDate: date
    zone: int
    dataStatus: DataStatus
    requirements: list[WaterRequirementItem]


class SectionWaterRequirementResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sectionId: str
    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")
    dataStatus: DataStatus
    requirements: list[WaterRequirementItem]


async def get_requirement_connection(request: Request):
    async with request.app.state.db_manager.get_connection() as conn:
        yield conn


def get_current_time() -> datetime:
    return datetime.now(timezone.utc)


def _expected_operational_date(now: datetime) -> date:
    local_now = now.astimezone(BANGKOK)
    if local_now.hour < PUBLICATION_ROLLOVER_HOUR:
        return local_now.date() - timedelta(days=1)
    return local_now.date()


def _item_status(row: Mapping, now: datetime) -> DataStatus:
    if row["run_status"] == "superseded":
        return "superseded"
    if row["as_of_date"] < _expected_operational_date(now):
        return "stale"
    return "published"


def _requirement_item(row: Mapping, now: datetime) -> WaterRequirementItem:
    published_at = row["published_at"]
    published_age_seconds = max(
        0,
        int(
            (
                now.astimezone(timezone.utc) - published_at.astimezone(timezone.utc)
            ).total_seconds()
        ),
    )
    return WaterRequirementItem(
        requirementId=row["requirement_id"],
        runId=row["run_id"],
        version=row["version"],
        serviceDate=row["service_date"],
        sectionId=row["section_id"],
        zone=row["zone"],
        requiredVolumeM3=float(row["required_net_volume_m3"]),
        deliveryWindow=DeliveryWindow(
            start=row["delivery_window_start"],
            end=row["delivery_window_end"],
        ),
        quality=row["quality"],
        publishedAt=published_at,
        freshness=PublicationFreshness(
            asOfDate=row["as_of_date"],
            publishedAgeSeconds=published_age_seconds,
        ),
        dataStatus=_item_status(row, now),
    )


def _collection_status(items: list[WaterRequirementItem]) -> DataStatus:
    statuses = {item.dataStatus for item in items}
    if "published" in statuses:
        return "published"
    if "stale" in statuses:
        return "stale"
    if "superseded" in statuses:
        return "superseded"
    return "no_publication"


@router.get("/daily", response_model=DailyWaterRequirementResponse)
async def get_daily_water_requirements(
    service_date: date = Query(...),
    zone: int = Query(..., ge=1, le=6),
    conn=Depends(get_requirement_connection),
    now: datetime = Depends(get_current_time),
) -> DailyWaterRequirementResponse:
    rows = await get_daily_requirements(conn, service_date, zone)
    items = [_requirement_item(row, now) for row in rows]
    return DailyWaterRequirementResponse(
        serviceDate=service_date,
        zone=zone,
        dataStatus=_collection_status(items),
        requirements=items,
    )


@router.get("/sections/{section_id}", response_model=SectionWaterRequirementResponse)
async def get_section_water_requirement_history(
    section_id: str,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    conn=Depends(get_requirement_connection),
    now: datetime = Depends(get_current_time),
) -> SectionWaterRequirementResponse:
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from must not follow to")
    rows = await get_section_requirement_history(
        conn,
        section_id,
        from_date,
        to_date,
    )
    items = [_requirement_item(row, now) for row in rows]
    return SectionWaterRequirementResponse(
        sectionId=section_id,
        from_date=from_date,
        to_date=to_date,
        dataStatus=_collection_status(items),
        requirements=items,
    )
