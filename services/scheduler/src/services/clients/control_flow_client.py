"""Strict flow-monitoring control client (PR 4.3a).

Consumes the bare-model control routes (`POST /api/v1/control/model-snapshots`,
`POST /api/v1/control/predictions`) — never the legacy `{"data": ...}`
envelope. Snapshot and prediction responses are stored verbatim (exact bytes)
for audit while a validated mirror feeds composition; echoed lineage pins must
equal the submitted pins or the response is refused.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Annotated, Any, Literal, Optional

import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError

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

# PR 4.4b-1 always emits identity-v2 predictions: the engine-identity headers
# are mandatory and a missing/mismatched artifact header is a contract violation
# (there is no legacy header-less Flow to fall back to).
FLOW_PREDICTION_IDENTITY_VERSION_V2 = 2

# PR 4.4b-1 model snapshots are schema v3 and embed the prediction engine
# descriptor VERBATIM, so a served prediction's engine headers can be tied back
# to the exact engine the snapshot was taken over.
SNAPSHOT_SCHEMA_VERSION_V3 = 3
SNAPSHOT_SCHEMA_VERSION_V4 = 4

_H_IDENTITY = "X-Prediction-Identity-Version"
_H_ARTIFACT_SHA = "X-Prediction-Artifact-SHA256"
_H_ARTIFACT_MEDIA = "X-Prediction-Artifact-Media-Type"
_H_ARTIFACT_ENCODING = "X-Prediction-Artifact-Encoding"
_H_ARTIFACT_ENCODING_VERSION = "X-Prediction-Artifact-Encoding-Version"
_H_ARTIFACT_SIZE = "X-Prediction-Artifact-Uncompressed-Size"
_H_ENGINE_ID = "X-Prediction-Engine-Id"
_H_SEMANTIC = "X-Prediction-Semantic-Contract-Version"
_H_BUILD_DIGEST = "X-Prediction-Build-Digest"
_H_ENGINE_CONTENT_HASH = "X-Prediction-Engine-Content-Hash"


@dataclass(frozen=True)
class FlowArtifactReference:
    """The BOUNDED, verified metadata of a served prediction artifact — never
    the trajectory bytes. ``artifact_sha256``/``uncompressed_size_bytes`` are the
    scheduler's OWN recomputation over the returned body, proven equal to the
    ``X-Prediction-Artifact-*`` headers before this is constructed."""

    artifact_sha256: str
    uncompressed_size_bytes: int
    media_type: str
    encoding: str
    encoding_version: int


@dataclass(frozen=True)
class FlowPredictionResult:
    """One prediction: the TRANSIENT full response (``response_text``/``parsed``,
    used only in-memory to project the ledger, then discarded) plus the durable
    artifact reference and identity-v2 engine pins the scheduler persists."""

    prediction_run_id: str
    identity_version: int
    engine_id: str
    semantic_contract_version: int
    build_digest: str
    engine_descriptor_content_hash: str
    artifact: FlowArtifactReference
    response_text: str
    parsed: dict[str, Any]


def _require_header(headers: httpx.Headers, name: str) -> str:
    value = headers.get(name)
    if value is None or not value.strip():
        raise UpstreamContractViolation(
            f"prediction response is missing the required {name} header"
        )
    return value


def _require_int_header(headers: httpx.Headers, name: str) -> int:
    raw = _require_header(headers, name)
    try:
        return int(raw)
    except ValueError as error:
        raise UpstreamContractViolation(
            f"prediction response {name} header {raw!r} is not an integer"
        ) from error


def _require_sha256_header(headers: httpx.Headers, name: str) -> str:
    value = _require_header(headers, name)
    if _SHA256_HEX.fullmatch(value) is None:
        raise UpstreamContractViolation(
            f"prediction response {name} header is not a sha256 digest"
        )
    return value


class _Mirror(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())


class _RoutingElementMirror(_Mirror):
    element_id: str
    upstream_node_id: str
    downstream_node_id: str
    role: str


class _RoutingTopologyMirror(_Mirror):
    config_sha256: str
    elements: list[_RoutingElementMirror]


class _OperatingEnvelopeMirror(_Mirror):
    minimum_flow_m3s: float
    maximum_flow_m3s: float
    minimum_timestep_seconds: float
    maximum_timestep_seconds: float
    maximum_horizon_seconds: float


class _ActionModelMirror(_Mirror):
    commandable: StrictBool
    actuation_approved: StrictBool
    config_sha256: dict[str, str]
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
    commandable: StrictBool
    response_members: list[_ResponseMemberMirror]


class _UnavailableReachMirror(_Mirror):
    reach_id: str
    reason: str


class _PredictionEngineMirror(_Mirror):
    """The snapshot's EMBEDDED prediction-engine descriptor (PR 4.4b-1). Its four
    identity fields are the authority the served prediction's engine headers must
    equal — the scheduler never trusts the response engine pins alone."""

    engine_id: str
    semantic_contract_version: int
    build_digest: str
    content_hash: str


_Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class _StrictApprovalMirror(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class _ApprovalReleaseMirror(_StrictApprovalMirror):
    release_id: str
    content_hash: _Sha256


class _ApprovalEngineMirror(_StrictApprovalMirror):
    content_hash: _Sha256


class _ApprovalConfigMirror(_StrictApprovalMirror):
    network: _Sha256
    canal_geometry: _Sha256
    gate_calibrations: _Sha256
    geometry_coverage: _Sha256
    routing_topology: _Sha256


class _ApprovalCapabilityMirror(_StrictApprovalMirror):
    capability_release_id: str
    capability_hash: _Sha256
    approved_gate_ids: list[str] = Field(min_length=1)


class _ApprovalEvidenceMirror(_StrictApprovalMirror):
    kind: str
    reference: str
    sha256: _Sha256


class _ApprovalAttestationMirror(_StrictApprovalMirror):
    approved_by_role: str
    approved_at: str
    approval_reference: str
    evidence: list[_ApprovalEvidenceMirror] = Field(min_length=1)


class _CommandabilityApprovalMirror(_StrictApprovalMirror):
    schema_version: Literal[1]
    approval_state: Literal["approved"]
    base_model_release: _ApprovalReleaseMirror
    prediction_engine: _ApprovalEngineMirror
    model_config_sha256: _ApprovalConfigMirror
    operating_envelope: _OperatingEnvelopeMirror
    device_capability: _ApprovalCapabilityMirror
    approval: _ApprovalAttestationMirror
    content_hash: _Sha256


class _ScadaGraphMirror(_Mirror):
    config_sha256: str


class _SnapshotMirror(_Mirror):
    schema_version: int
    snapshot_id: str
    data_status: str
    commandable: StrictBool
    prediction_engine: _PredictionEngineMirror
    scada_graph: Optional[_ScadaGraphMirror] = None
    routing_topology: _RoutingTopologyMirror
    action_model: _ActionModelMirror
    response_model_release: Optional[_ReleaseMirror] = Field(
        alias="response_model", default=None
    )
    unavailable_transport_reaches: list[_UnavailableReachMirror]
    commandability_approval: Optional[_CommandabilityApprovalMirror] = None


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
                f"flow-monitoring model snapshot unavailable: " f"{response.text[:500]}"
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
        if mirror.schema_version not in (
            SNAPSHOT_SCHEMA_VERSION_V3,
            SNAPSHOT_SCHEMA_VERSION_V4,
        ):
            raise UpstreamContractViolation(
                f"model snapshot schema_version {mirror.schema_version} is not "
                f"{SNAPSHOT_SCHEMA_VERSION_V3} or {SNAPSHOT_SCHEMA_VERSION_V4}; "
                "the embedded prediction engine contract is not satisfied"
            )
        response_commandable = bool(
            mirror.response_model_release and mirror.response_model_release.commandable
        )
        gates = (
            mirror.commandable,
            response_commandable,
            mirror.action_model.commandable,
            mirror.action_model.actuation_approved,
        )
        if mirror.schema_version == SNAPSHOT_SCHEMA_VERSION_V3:
            if any(gates) or mirror.commandability_approval is not None:
                raise UpstreamContractViolation(
                    "model snapshot v3 must remain dark without commandability approval"
                )
        else:
            approval = mirror.commandability_approval
            response_model = mirror.response_model_release
            if not all(gates) or approval is None or response_model is None:
                raise UpstreamContractViolation(
                    "model snapshot v4 requires every commandability gate and approval"
                )
            approved_gate_ids = approval.device_capability.approved_gate_ids
            if approved_gate_ids != sorted(set(approved_gate_ids)):
                raise UpstreamContractViolation(
                    "model snapshot v4 approval gate ids are not sorted and unique"
                )
            expected_action_config = approval.model_config_sha256.model_dump(
                exclude={"network", "routing_topology"}
            )
            if (
                mirror.scada_graph is None
                or approval.base_model_release.release_id != response_model.release_id
                or approval.base_model_release.content_hash
                != response_model.content_hash
                or approval.prediction_engine.content_hash
                != mirror.prediction_engine.content_hash
                or approval.model_config_sha256.network
                != mirror.scada_graph.config_sha256
                or approval.model_config_sha256.routing_topology
                != mirror.routing_topology.config_sha256
                or expected_action_config != mirror.action_model.config_sha256
                or approval.operating_envelope != mirror.action_model.operating_envelope
            ):
                raise UpstreamContractViolation(
                    "model snapshot v4 approval does not cross-bind its runtime model"
                )
        if _SHA256_HEX.fullmatch(mirror.snapshot_id) is None:
            raise UpstreamContractViolation("model snapshot_id is not a sha256 digest")
        return response.text, mirror.model_dump()

    async def create_prediction(
        self, request_document: dict[str, Any]
    ) -> FlowPredictionResult:
        """POST the composed prediction request; return a verified reference.

        The full response is parsed (for in-memory ledger projection) but the
        durable outcome is a BOUNDED reference: the identity-v2 engine pins and
        the artifact metadata read from the ``X-Prediction-*`` headers, with the
        artifact sha256/byte-size RECOMPUTED over the returned body and required
        to equal the headers. Any missing/mismatched header or engine field is a
        fail-closed contract violation — never a silently-trusted reference."""
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
                    f"prediction response pin {pin} does not echo the " "submitted pin"
                )
        _validate_prediction_members(parsed.get("members"))
        return self._verified_artifact_reference(response, run_id, parsed)

    def _verified_artifact_reference(
        self, response: httpx.Response, run_id: str, parsed: dict[str, Any]
    ) -> FlowPredictionResult:
        headers = response.headers
        identity_version = _require_int_header(headers, _H_IDENTITY)
        if identity_version != FLOW_PREDICTION_IDENTITY_VERSION_V2:
            raise UpstreamContractViolation(
                f"prediction response identity_version {identity_version} is "
                f"not {FLOW_PREDICTION_IDENTITY_VERSION_V2}; the engine-identity "
                "contract is not satisfied"
            )
        artifact_sha = _require_sha256_header(headers, _H_ARTIFACT_SHA)
        declared_size = _require_int_header(headers, _H_ARTIFACT_SIZE)
        media_type = _require_header(headers, _H_ARTIFACT_MEDIA)
        encoding = _require_header(headers, _H_ARTIFACT_ENCODING)
        encoding_version = _require_int_header(headers, _H_ARTIFACT_ENCODING_VERSION)
        engine_id = _require_header(headers, _H_ENGINE_ID)
        semantic_contract_version = _require_int_header(headers, _H_SEMANTIC)
        build_digest = _require_sha256_header(headers, _H_BUILD_DIGEST)
        engine_content_hash = _require_sha256_header(headers, _H_ENGINE_CONTENT_HASH)
        # Recompute over the EXACT returned bytes and reject any drift from the
        # upstream-declared headers before the reference is trusted.
        body_bytes = response.content
        recomputed_sha = hashlib.sha256(body_bytes).hexdigest()
        if recomputed_sha != artifact_sha:
            raise UpstreamContractViolation(
                "recomputed prediction artifact sha256 does not match the "
                f"{_H_ARTIFACT_SHA} header"
            )
        if len(body_bytes) != declared_size:
            raise UpstreamContractViolation(
                "recomputed prediction artifact byte size does not match the "
                f"{_H_ARTIFACT_SIZE} header"
            )
        return FlowPredictionResult(
            prediction_run_id=run_id,
            identity_version=identity_version,
            engine_id=engine_id,
            semantic_contract_version=semantic_contract_version,
            build_digest=build_digest,
            engine_descriptor_content_hash=engine_content_hash,
            artifact=FlowArtifactReference(
                artifact_sha256=artifact_sha,
                uncompressed_size_bytes=declared_size,
                media_type=media_type,
                encoding=encoding,
                encoding_version=encoding_version,
            ),
            response_text=response.text,
            parsed=parsed,
        )


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
