from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hmac import compare_digest
from typing import Annotated, Literal, Mapping
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from db.water_requirement_repository import (
    get_daily_requirements,
    get_section_requirement_history,
)
from services.requirement_source_loader import RequirementSourceError

DataStatus = Literal["no_publication", "stale", "published", "superseded"]
NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
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


class ManualRequirementRunRequest(BaseModel):
    asOfDate: date


class ManualRequirementRunResponse(BaseModel):
    status: Literal["published", "deduplicated"]
    runId: UUID
    asOfDate: date
    requirementCount: int


class IncompleteSourceDetail(BaseModel):
    status: Literal["failed_incomplete_source"]
    reason: str
    asOfDate: date


class IncompleteSourceResponse(BaseModel):
    detail: IncompleteSourceDetail


class SectionCropSettingRequest(BaseModel):
    cropType: NonBlankString
    plantedAreaRai: Decimal = Field(gt=0)
    expectedHarvestDate: date
    source: NonBlankString
    asOfDate: date
    updatedBy: NonBlankString


class SectionCropSettingResponse(SectionCropSettingRequest):
    settingId: UUID
    sectionId: str


async def get_requirement_connection(request: Request):
    async with request.app.state.db_manager.get_connection() as conn:
        yield conn


def get_daily_requirement_job(request: Request):
    job = getattr(request.app.state, "daily_requirement_job", None)
    if job is None:
        raise HTTPException(status_code=503, detail="daily requirement job is disabled")
    return job


def require_manual_requirement_token(
    request: Request,
    x_munbon_internal_token: Annotated[
        str | None,
        Header(alias="X-Munbon-Internal-Token"),
    ] = None,
) -> None:
    expected = getattr(request.app.state, "daily_requirement_manual_token", None)
    if not isinstance(expected, str) or not expected:
        raise HTTPException(
            status_code=503,
            detail="manual requirement trigger is disabled",
        )
    if not isinstance(x_munbon_internal_token, str) or not compare_digest(
        x_munbon_internal_token, expected
    ):
        raise HTTPException(status_code=403, detail="manual trigger forbidden")


def get_current_time() -> datetime:
    return datetime.now(timezone.utc)


@router.post(
    "/runs",
    response_model=ManualRequirementRunResponse,
    responses={
        409: {
            "model": IncompleteSourceResponse,
            "description": (
                "Authoritative source inputs are incomplete for the requested "
                "operational date; nothing was published."
            ),
        }
    },
)
async def trigger_daily_requirement_run(
    request: ManualRequirementRunRequest,
    _manual_trigger=Depends(require_manual_requirement_token),
    job=Depends(get_daily_requirement_job),
) -> ManualRequirementRunResponse:
    try:
        result = await job.run_once(request.asOfDate)
    except RequirementSourceError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "failed_incomplete_source",
                "reason": str(exc),
                "asOfDate": request.asOfDate.isoformat(),
            },
        ) from exc
    return ManualRequirementRunResponse(
        status=result.status,
        runId=result.run_id,
        asOfDate=result.as_of_date,
        requirementCount=result.requirement_count,
    )


@router.post("/crop-settings/{section_id}", response_model=SectionCropSettingResponse)
async def create_section_crop_setting(
    section_id: str,
    request: SectionCropSettingRequest,
    conn=Depends(get_requirement_connection),
) -> SectionCropSettingResponse:
    section = await conn.fetchrow(
        """
        SELECT area_rai
        FROM ros_gis.sections_current
        WHERE section_id = $1
        """,
        section_id,
    )
    if section is None:
        raise HTTPException(
            status_code=404,
            detail=f"section {section_id} is not in the active D1 master",
        )
    maximum_area = Decimal(str(section["area_rai"]))
    if request.plantedAreaRai > maximum_area:
        raise HTTPException(
            status_code=422,
            detail=(
                f"plantedAreaRai exceeds authoritative GIS section area "
                f"{maximum_area} rai"
            ),
        )
    setting_id = uuid4()
    row = await conn.fetchrow(
        """
        INSERT INTO ros_gis.section_crop_settings (
            setting_id, section_id, crop_type, planted_area_rai,
            expected_harvest_date, source, as_of_date, updated_by
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING setting_id, section_id, crop_type, planted_area_rai,
                  expected_harvest_date, source, as_of_date, updated_by
        """,
        setting_id,
        section_id,
        request.cropType,
        request.plantedAreaRai,
        request.expectedHarvestDate,
        request.source,
        request.asOfDate,
        request.updatedBy,
    )
    return SectionCropSettingResponse(
        settingId=row["setting_id"],
        sectionId=row["section_id"],
        cropType=row["crop_type"],
        plantedAreaRai=row["planted_area_rai"],
        expectedHarvestDate=row["expected_harvest_date"],
        source=row["source"],
        asOfDate=row["as_of_date"],
        updatedBy=row["updated_by"],
    )


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
