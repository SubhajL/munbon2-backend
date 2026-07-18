"""Strict flow-monitoring control client (PR 4.3a).

Consumes the bare-model control routes (`POST /api/v1/control/model-snapshots`,
`POST /api/v1/control/predictions`) — never the legacy `{"data": ...}`
envelope. Snapshot and prediction responses are stored verbatim (exact bytes)
for audit while a validated mirror feeds composition; echoed lineage pins must
equal the submitted pins or the response is refused.
"""

from __future__ import annotations

import re
from typing import Any, Optional

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .control_client_errors import (
    FlowLineageConflictError,
    PredictionRequestRejectedError,
    UpstreamContractViolation,
    UpstreamUnavailableError,
)

_TIMEOUT = httpx.Timeout(120.0, connect=5.0)
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_PREDICTION_MEMBERS = frozenset({"lower", "nominal", "upper"})
_PREDICTION_STATUSES = frozenset({"completed", "infeasible"})


class _Mirror(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())


class _RoutingElementMirror(_Mirror):
    element_id: str
    upstream_node_id: str
    downstream_node_id: str
    role: str


class _RoutingTopologyMirror(_Mirror):
    elements: list[_RoutingElementMirror]


class _OperatingEnvelopeMirror(_Mirror):
    minimum_flow_m3s: float
    maximum_flow_m3s: float
    minimum_timestep_seconds: float
    maximum_timestep_seconds: float
    maximum_horizon_seconds: float


class _ActionModelMirror(_Mirror):
    operating_envelope: Optional[_OperatingEnvelopeMirror]


class _ResponseMemberMirror(_Mirror):
    reach_id: str
    member: str
    delay_seconds: float
    loss_fraction: float
    capacity_m3s: float


class _ReleaseMirror(_Mirror):
    release_id: str
    content_hash: str
    response_members: list[_ResponseMemberMirror]


class _UnavailableReachMirror(_Mirror):
    reach_id: str
    reason: str


class _SnapshotMirror(_Mirror):
    snapshot_id: str
    data_status: str
    routing_topology: _RoutingTopologyMirror
    action_model: _ActionModelMirror
    response_model_release: Optional[_ReleaseMirror] = Field(
        alias="response_model", default=None
    )
    unavailable_transport_reaches: list[_UnavailableReachMirror]


class ControlFlowClient:
    def __init__(
        self,
        base_url: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=_TIMEOUT)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def create_model_snapshot(self) -> tuple[str, dict[str, Any]]:
        """Return (exact response text, validated mirror dump)."""
        url = f"{self._base_url}/api/v1/control/model-snapshots"
        try:
            response = await self._client.post(url)
        except httpx.RequestError as error:
            raise UpstreamUnavailableError(
                f"flow-monitoring is unreachable: {error}"
            ) from error
        if response.status_code == 503:
            raise UpstreamUnavailableError(
                f"flow-monitoring model snapshot unavailable: "
                f"{response.text[:500]}"
            )
        if response.status_code != 200:
            raise UpstreamContractViolation(
                f"model-snapshot route answered {response.status_code}: "
                f"{response.text[:500]}"
            )
        try:
            body = response.json()
        except ValueError as error:
            raise UpstreamContractViolation(
                f"model-snapshot response is not JSON: {error}"
            ) from error
        if not isinstance(body, dict):
            raise UpstreamContractViolation(
                "model-snapshot response is not the bare snapshot model"
            )
        try:
            mirror = _SnapshotMirror.model_validate(body)
        except ValidationError as error:
            raise UpstreamContractViolation(
                f"model-snapshot response violates its contract: {error}"
            ) from error
        if _SHA256_HEX.fullmatch(mirror.snapshot_id) is None:
            raise UpstreamContractViolation(
                "model snapshot_id is not a sha256 digest"
            )
        return response.text, mirror.model_dump()

    async def create_prediction(
        self, request_document: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        """POST the composed prediction request; return (exact text, parsed)."""
        url = f"{self._base_url}/api/v1/control/predictions"
        try:
            response = await self._client.post(url, json=request_document)
        except httpx.RequestError as error:
            raise UpstreamUnavailableError(
                f"flow-monitoring is unreachable: {error}"
            ) from error
        if response.status_code == 409:
            raise FlowLineageConflictError(
                f"flow-monitoring rejected the prediction pins: "
                f"{response.text[:500]}"
            )
        if response.status_code == 503:
            raise UpstreamUnavailableError(
                f"flow-monitoring prediction unavailable: {response.text[:500]}"
            )
        if response.status_code in (400, 422):
            raise PredictionRequestRejectedError(
                f"flow-monitoring rejected the composed prediction request "
                f"({response.status_code}): {response.text[:1000]}"
            )
        if response.status_code != 200:
            raise UpstreamContractViolation(
                f"prediction route answered {response.status_code}: "
                f"{response.text[:500]}"
            )
        try:
            parsed = response.json()
        except ValueError as error:
            raise UpstreamContractViolation(
                f"prediction response is not JSON: {error}"
            ) from error
        if not isinstance(parsed, dict):
            raise UpstreamContractViolation(
                "prediction response is not the bare prediction model"
            )
        run_id = parsed.get("prediction_run_id")
        if not isinstance(run_id, str) or _SHA256_HEX.fullmatch(run_id) is None:
            raise UpstreamContractViolation(
                "prediction response carries no content-addressed run id"
            )
        for pin in (
            "model_snapshot_id",
            "model_release_id",
            "model_release_content_hash",
        ):
            if parsed.get(pin) != request_document[pin]:
                raise UpstreamContractViolation(
                    f"prediction response pin {pin} does not echo the "
                    "submitted pin"
                )
        _validate_prediction_members(parsed.get("members"))
        return response.text, parsed


def _validate_prediction_members(members: Any) -> None:
    """The three-member envelope must be exactly lower/nominal/upper.

    A malformed members list (missing an envelope bound, a duplicate member, an
    unknown label or status) would otherwise persist as an immutable draft that
    then 500s on every read — this is the fail-closed 502 boundary instead.
    """
    if not isinstance(members, list) or len(members) != 3:
        raise UpstreamContractViolation(
            "prediction response must carry exactly three members"
        )
    labels = []
    for member in members:
        if not isinstance(member, dict):
            raise UpstreamContractViolation("prediction member is not an object")
        label = member.get("member")
        status = member.get("status")
        if label not in _PREDICTION_MEMBERS:
            raise UpstreamContractViolation(
                f"prediction member label {label!r} is not one of "
                f"{sorted(_PREDICTION_MEMBERS)}"
            )
        if status not in _PREDICTION_STATUSES:
            raise UpstreamContractViolation(
                f"prediction member {label!r} carries unknown status {status!r}"
            )
        labels.append(label)
    if set(labels) != _PREDICTION_MEMBERS:
        raise UpstreamContractViolation(
            "prediction response must carry each of lower, nominal, upper "
            f"exactly once; got {labels}"
        )
