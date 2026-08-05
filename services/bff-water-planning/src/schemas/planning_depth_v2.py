from __future__ import annotations

import re
from datetime import date
from typing import Literal, Optional
from uuid import UUID

from core.rid_calendar import IrrigationWeek, IrrigationYear, irrigation_week_span
from pydantic import AwareDatetime, Field, model_validator
from schemas.planning_depth import (
    DateOnly,
    PlanningDepthExpandedValue,
    PlanningDepthLevelInput,
    StrictPlanningDepthModel,
)

RID_CALENDAR_SYSTEM = "rid-irrigation-v1"
RID_WEEK_KEY_PATTERN = r"^[0-9]{4}-R(?:0[1-9]|[1-4][0-9]|5[0-3])$"


def parse_rid_week_key(week_key: str) -> IrrigationWeek:
    match = re.fullmatch(RID_WEEK_KEY_PATTERN, week_key)
    if match is None:
        raise ValueError("week_key must identify a RID week")
    ending_year_text, week_text = week_key.split("-R", 1)
    try:
        return IrrigationWeek(
            irrigation_year=IrrigationYear.from_ce(int(ending_year_text)),
            irrigation_week=int(week_text),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("week_key is outside the supported RID calendar") from exc


def _require_rid_week_start(
    calendar_system: str,
    week_key: str,
    week_date: date,
) -> None:
    if calendar_system != RID_CALENDAR_SYSTEM:
        raise ValueError("calendar_system and week_key must identify a RID week")
    identity = parse_rid_week_key(week_key)
    if week_date != irrigation_week_span(identity).start:
        raise ValueError("week_date must be the first day represented by week_key")


class PlanningDepthSubmissionRequestV2(StrictPlanningDepthModel):
    schema_version: Literal[2]
    client_submission_id: UUID
    project_key: Literal["mun-bon"]
    calendar_system: Literal["rid-irrigation-v1"]
    week_key: str = Field(pattern=RID_WEEK_KEY_PATTERN)
    week_date: DateOnly
    expected_active_submission_id: Optional[UUID]
    levels: list[PlanningDepthLevelInput] = Field(min_length=1, max_length=47)

    @model_validator(mode="after")
    def require_rid_week_start(self):
        _require_rid_week_start(
            self.calendar_system,
            self.week_key,
            self.week_date,
        )
        return self


class PlanningDepthSubmissionReceiptV2(StrictPlanningDepthModel):
    schema_version: Literal[2]
    submission_id: UUID
    client_submission_id: UUID
    project_key: Literal["mun-bon"]
    calendar_system: Literal["rid-irrigation-v1"]
    week_key: str = Field(pattern=RID_WEEK_KEY_PATTERN)
    week_date: DateOnly
    submitted_at: AwareDatetime
    submitted_by: str = Field(min_length=1)
    supersedes_submission_id: Optional[UUID]
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    replayed: bool

    @model_validator(mode="after")
    def require_rid_week_start(self):
        _require_rid_week_start(
            self.calendar_system,
            self.week_key,
            self.week_date,
        )
        return self


class PlanningDepthActiveSubmissionV2(StrictPlanningDepthModel):
    schema_version: Literal[2]
    submission_id: UUID
    client_submission_id: UUID
    project_key: Literal["mun-bon"]
    calendar_system: Literal["rid-irrigation-v1"]
    week_key: str = Field(pattern=RID_WEEK_KEY_PATTERN)
    week_date: DateOnly
    submitted_at: AwareDatetime
    submitted_by: str = Field(min_length=1)
    supersedes_submission_id: Optional[UUID]
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    levels: list[PlanningDepthExpandedValue] = Field(min_length=41, max_length=41)

    @model_validator(mode="after")
    def require_rid_week_start(self):
        _require_rid_week_start(
            self.calendar_system,
            self.week_key,
            self.week_date,
        )
        return self
