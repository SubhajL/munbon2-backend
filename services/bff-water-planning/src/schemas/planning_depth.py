from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal, Optional
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_serializer,
    model_serializer,
    model_validator,
)

MAX_PLANNING_DEPTH_MM = Decimal("999999999.999")
MILLIMETER_QUANTUM = Decimal("0.001")


def _planning_depth_decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("planning_depth_mm must be a JSON number")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("planning_depth_mm must be finite")
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("planning_depth_mm must be decimal") from exc
    if not decimal.is_finite():
        raise ValueError("planning_depth_mm must be finite")
    if not Decimal("0") <= decimal <= MAX_PLANNING_DEPTH_MM:
        raise ValueError("planning_depth_mm is outside NUMERIC(12,3)")
    try:
        quantized = decimal.quantize(MILLIMETER_QUANTUM)
    except InvalidOperation as exc:
        raise ValueError("planning_depth_mm is outside NUMERIC(12,3)") from exc
    if decimal != quantized:
        raise ValueError("planning_depth_mm supports at most three decimal places")
    return quantized


def _date_only(value: Any) -> date:
    if isinstance(value, datetime):
        raise ValueError("week_date must be a date-only value")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("week_date must be a date-only value") from exc
        if parsed.isoformat() == value:
            return parsed
    raise ValueError("week_date must be a date-only value")


PlanningDepthDecimal = Annotated[
    Decimal,
    BeforeValidator(_planning_depth_decimal),
]
DateOnly = Annotated[date, BeforeValidator(_date_only)]
AreaType = Literal["zone", "section"]
SourceKind = Literal["zone_default", "section_override"]
EffectiveRole = Literal["admin", "supervisor", "operator", "field_team"]
CANONICAL_ROLE_PROJECTIONS = {
    ("field_team",),
    ("field_team", "operator"),
    ("field_team", "operator", "supervisor"),
    ("admin", "field_team", "operator", "supervisor"),
}


class StrictPlanningDepthModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanningDepthLevelInput(StrictPlanningDepthModel):
    area_type: AreaType
    area_id: str = Field(min_length=1)
    zone_id: Optional[str] = Field(default=None, min_length=1)
    planning_depth_mm: PlanningDepthDecimal

    @model_validator(mode="after")
    def require_exact_identity_shape(self):
        if self.area_type == "zone" and self.zone_id is not None:
            raise ValueError("zone levels cannot carry zone_id")
        if self.area_type == "section" and self.zone_id is None:
            raise ValueError("section levels require zone_id")
        return self

    @field_serializer("planning_depth_mm", when_used="json")
    def serialize_planning_depth(self, value: Decimal) -> float:
        return float(value)

    @model_serializer(mode="wrap")
    def omit_absent_zone_id(self, handler):
        serialized = handler(self)
        if self.zone_id is None:
            serialized.pop("zone_id", None)
        return serialized


class PlanningDepthSubmissionRequest(StrictPlanningDepthModel):
    schema_version: Literal[1]
    client_submission_id: UUID
    project_key: Literal["mun-bon"]
    week_key: str = Field(pattern=r"^[0-9]{4}-W[0-9]{2}$")
    week_date: DateOnly
    expected_active_submission_id: Optional[UUID]
    levels: list[PlanningDepthLevelInput] = Field(min_length=1, max_length=47)

    @model_validator(mode="after")
    def require_rid_week_monday(self):
        iso_year, iso_week, iso_weekday = self.week_date.isocalendar()
        if iso_weekday != 1 or self.week_key != f"{iso_year:04d}-W{iso_week:02d}":
            raise ValueError("week_date must be the Monday represented by week_key")
        return self


class PlanningDepthExpandedValue(StrictPlanningDepthModel):
    section_id: str = Field(min_length=1)
    zone_id: str = Field(min_length=1)
    planning_depth_mm: PlanningDepthDecimal
    source_kind: SourceKind
    source_area_id: str = Field(min_length=1)

    @field_serializer("planning_depth_mm", when_used="json")
    def serialize_planning_depth(self, value: Decimal) -> float:
        return float(value)


class EffectivePrincipalProjection(StrictPlanningDepthModel):
    subject: str = Field(min_length=1)
    effective_roles: list[EffectiveRole] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def require_canonical_role_projection(self):
        if tuple(self.effective_roles) not in CANONICAL_ROLE_PROJECTIONS:
            raise ValueError("effective_roles must be a canonical role projection")
        return self


class PlanningDepthSubmissionReceipt(StrictPlanningDepthModel):
    schema_version: Literal[1]
    submission_id: UUID
    client_submission_id: UUID
    project_key: Literal["mun-bon"]
    week_key: str = Field(pattern=r"^[0-9]{4}-W[0-9]{2}$")
    week_date: DateOnly
    submitted_at: AwareDatetime
    submitted_by: str = Field(min_length=1)
    supersedes_submission_id: Optional[UUID]
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    replayed: bool


class PlanningDepthActiveSubmission(StrictPlanningDepthModel):
    schema_version: Literal[1]
    submission_id: UUID
    client_submission_id: UUID
    project_key: Literal["mun-bon"]
    week_key: str = Field(pattern=r"^[0-9]{4}-W[0-9]{2}$")
    week_date: DateOnly
    submitted_at: AwareDatetime
    submitted_by: str = Field(min_length=1)
    supersedes_submission_id: Optional[UUID]
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    levels: list[PlanningDepthExpandedValue] = Field(min_length=41, max_length=41)
