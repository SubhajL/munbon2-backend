from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictInt,
    field_serializer,
    model_validator,
)

AREA_RAI_QUANTUM = Decimal("0.01")
CANONICAL_TOTAL_AREA_RAI = Decimal("45204.00")
CANONICAL_SECTION_NUMBERS_BY_ZONE = {
    1: range(3, 8),
    2: range(8, 15),
    3: range(15, 20),
    4: range(20, 27),
    5: range(27, 35),
    6: range(35, 44),
}
CANONICAL_SECTION_ZONE_IDS = {
    section_number: f"01-{zone_number:02d}"
    for zone_number, section_numbers in CANONICAL_SECTION_NUMBERS_BY_ZONE.items()
    for section_number in section_numbers
}
CANONICAL_SECTION_AREAS_RAI = {
    3: Decimal("972"),
    4: Decimal("689"),
    5: Decimal("1778"),
    6: Decimal("2357"),
    7: Decimal("1726"),
    8: Decimal("693"),
    9: Decimal("1434"),
    10: Decimal("1527"),
    11: Decimal("2611"),
    12: Decimal("449"),
    13: Decimal("65"),
    14: Decimal("104"),
    15: Decimal("2620"),
    16: Decimal("1348"),
    17: Decimal("5366"),
    18: Decimal("760"),
    19: Decimal("1133"),
    20: Decimal("654"),
    21: Decimal("503"),
    22: Decimal("1907"),
    23: Decimal("73"),
    24: Decimal("2124"),
    25: Decimal("1121"),
    26: Decimal("1555"),
    27: Decimal("139"),
    28: Decimal("694"),
    29: Decimal("813"),
    30: Decimal("1009"),
    31: Decimal("591"),
    32: Decimal("686"),
    33: Decimal("1185"),
    34: Decimal("1434"),
    35: Decimal("358"),
    36: Decimal("995"),
    37: Decimal("743"),
    38: Decimal("1206"),
    39: Decimal("229"),
    40: Decimal("277"),
    41: Decimal("193"),
    42: Decimal("465"),
    43: Decimal("618"),
}


def _area_rai_decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("area_rai must be a JSON number")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("area_rai must be finite")
    try:
        decimal = Decimal(str(value))
        quantized = decimal.quantize(AREA_RAI_QUANTUM)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("area_rai must be a finite decimal") from exc
    if not decimal.is_finite() or decimal <= 0:
        raise ValueError("area_rai must be positive")
    if decimal != quantized:
        raise ValueError("area_rai supports at most two decimal places")
    return quantized


AreaRaiDecimal = Annotated[Decimal, BeforeValidator(_area_rai_decimal)]


class StrictPlanningDepthRosterModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanningDepthRosterSection(StrictPlanningDepthRosterModel):
    section_id: str = Field(pattern=r"^01-[0-9]{2}-01-[0-9]{2}$")
    zone_id: str = Field(pattern=r"^01-0[1-6]$")
    area_rai: AreaRaiDecimal

    @field_serializer("area_rai", when_used="json")
    def serialize_area_rai(self, value: Decimal) -> float:
        return float(value)


class PlanningDepthRosterProjection(StrictPlanningDepthRosterModel):
    schema_version: Literal[1]
    project_key: Literal["mun-bon"]
    dataset_version_id: StrictInt = Field(gt=0)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    total_area_rai: AreaRaiDecimal
    sections: list[PlanningDepthRosterSection] = Field(min_length=41, max_length=41)

    @model_validator(mode="after")
    def require_canonical_section_membership(self):
        expected = [
            (
                f"{zone_id}-01-{section_number:02d}",
                zone_id,
                CANONICAL_SECTION_AREAS_RAI[section_number],
            )
            for section_number, zone_id in sorted(CANONICAL_SECTION_ZONE_IDS.items())
        ]
        actual = [(row.section_id, row.zone_id, row.area_rai) for row in self.sections]
        total = sum((row.area_rai for row in self.sections), Decimal("0"))
        if (
            actual != expected
            or total != CANONICAL_TOTAL_AREA_RAI
            or self.total_area_rai != CANONICAL_TOTAL_AREA_RAI
        ):
            raise ValueError("planning-depth roster authority is inconsistent")
        return self

    @field_serializer("total_area_rai", when_used="json")
    def serialize_total_area_rai(self, value: Decimal) -> float:
        return float(value)
