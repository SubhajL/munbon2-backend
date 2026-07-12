"""
Pydantic schemas for the Wave 2.4 demand/allocation/actual-delivery contract
(POST/GET /api/v1/control/demands).

Three separate record types for three separate concepts (HIGH #8): agronomic demand
(m³ over a period, delivered in scheduled windows), operator allocation (m³/s over
explicit intervals), and measured delivery observations. Every instant is tz-aware
and normalized to UTC at the schema boundary; the `timezone` field only declares the
local operational interpretation (Asia/Bangkok). Cross-field semantics (interval
containment/overlap, the m³ → m³/s conversion, synthetic-lineage policy, node-id
canonicalization) are enforced in the handler via core.demand_contract — single
source of truth, and non-finite floats get a clean 400 instead of the 422
serialization trap documented on PlanRequest.
"""
from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from core.demand_contract import ensure_aware_utc


def _aware_utc(value: datetime) -> datetime:
    # Same rule as the core contract (DemandContractError is a ValueError, so
    # pydantic reports it as a clean 422) — one normalization algorithm.
    return ensure_aware_utc(value, "datetime")


AwareUtc = Annotated[datetime, AfterValidator(_aware_utc)]
NonBlank = Annotated[str, StringConstraints(min_length=1)]

AreaType = Literal["section", "zone", "munbon", "node"]
RecordKind = Literal["demand", "allocation", "delivery"]


class _VersionedRecord(BaseModel):
    """Envelope every contract record carries: identity, lineage, and versioning."""

    area_type: AreaType
    area_id: NonBlank
    timezone: NonBlank = Field(
        description="IANA name declaring local interpretation (e.g. Asia/Bangkok); "
        "instants are stored as UTC regardless."
    )
    method: NonBlank
    source_service: NonBlank
    source_version: NonBlank
    synthetic: bool = Field(
        description="Must be false: synthetic/fabricated records are rejected by policy."
    )
    computed_at: AwareUtc
    version: int = Field(
        ge=1, description="Strictly latest+1 per logical key; append-only."
    )
    idempotency_key: NonBlank


class DeliveryInterval(BaseModel):
    start: AwareUtc
    end: AwareUtc


class DemandRecord(_VersionedRecord):
    """Agronomic demand: a volume over a period, delivered in scheduled windows.

    The ratified conversion m³/s = m³ ÷ scheduled-delivery-seconds uses ONLY the
    scheduled windows below — never whole-period elapsed time.
    """

    period_start: AwareUtc
    period_end: AwareUtc
    volume_m3: float
    scheduled_delivery_intervals: list[DeliveryInterval]
    quality: Literal["measured", "estimated", "forecast"]
    input_versions: dict[str, str] = Field(
        default_factory=dict,
        description="Versions of upstream inputs (crop register, weather, ...).",
    )


class AllocationInterval(BaseModel):
    start: AwareUtc
    end: AwareUtc
    flow_m3s: float


class AllocationRecord(_VersionedRecord):
    """Operator allocation: flow (m³/s) granted over explicit intervals."""

    period_start: AwareUtc
    period_end: AwareUtc
    intervals: list[AllocationInterval]


class DeliveryObservation(_VersionedRecord):
    """Actual delivery: measured volume over an observed interval."""

    start: AwareUtc
    end: AwareUtc
    volume_m3: float
    quality: Literal["measured", "estimated"]
    sensor_ids: list[str] = Field(default_factory=list)


class DemandSubmissionRequest(BaseModel):
    demands: list[DemandRecord] = Field(default_factory=list)
    allocations: list[AllocationRecord] = Field(default_factory=list)
    deliveries: list[DeliveryObservation] = Field(default_factory=list)


class RecordResult(BaseModel):
    kind: RecordKind
    logical_key: str
    version: int
    replayed: bool
    content_hash: str
    required_flow_m3s: Optional[float] = Field(
        default=None,
        description="Demand records only: volume ÷ scheduled-delivery-seconds.",
    )


class DemandSubmissionResponse(BaseModel):
    results: list[RecordResult]


class StoredRecordEnvelope(BaseModel):
    logical_key: str
    version: int
    content_hash: str
    record: dict


class CurrentRecordsResponse(BaseModel):
    kind: RecordKind
    records: list[StoredRecordEnvelope]
