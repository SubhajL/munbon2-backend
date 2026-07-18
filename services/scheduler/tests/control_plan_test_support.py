"""Shared fakes and fixture builders for the PR 4.3a control-plan tests.

Non-test filename: never collected. The fakes pin the real client/repository
interfaces — tests/unit/test_control_service_clients.py asserts their method
signatures match the production classes exactly.
"""

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from core.control_plan import canonical_json_text
from services.clients.control_flow_client import (
    FlowArtifactReference,
    FlowPredictionResult,
)
from core.control_plan_cursor import decode_plan_cursor, encode_plan_cursor
from core.control_plan_lifecycle import derive_control_plan_state
from core.auth import is_trusted_shadow_approval
from repositories.control_plan_repository import (
    PlanContentConflictError,
    TransitionConflictError,
    TransitionRecord,
)
from schemas.control_plan import (
    PROJECTION_SCHEMA_VERSION,
    ControlPlanListFilters,
    ControlPlanListPage,
    ControlPlanSummaryOut,
)

RUN_ID = UUID("8e0b0e6a-6c1e-5f5e-9d5c-2f6a8b1c2d3e")
REQ_ID = "7c8a4c62-4b0e-5efd-9c3a-111111111111"


def requirement_item(volume=6000.0, run_id=None, requirement_id=None, version=3):
    return {
        "requirement_id": requirement_id or REQ_ID,
        "run_id": str(run_id or RUN_ID),
        "version": version,
        "service_date": date(2026, 7, 20),
        "section_id": "SEC-1",
        "zone": 1,
        "required_volume_m3": volume,
        "window_start": datetime(2026, 7, 20, 6, 0, tzinfo=timezone.utc),
        "window_end": datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc),
        "quality": "estimated",
        "published_at": datetime(2026, 7, 19, 19, 5, tzinfo=timezone.utc),
        "as_of_date": date(2026, 7, 19),
        "data_status": "published",
    }


def snapshot_mirror():
    return {
        "schema_version": 3,
        "snapshot_id": "a" * 64,
        "data_status": "complete",
        # The PR 4.4b-1 schema-v3 snapshot embeds the prediction engine descriptor
        # verbatim; these four fields are the authority the served prediction's
        # engine pins must equal (they match FakeControlFlowClient's defaults).
        "prediction_engine": {
            "schema_version": 1,
            "engine_id": "munbon.flow-monitoring.network-transient",
            "semantic_contract_version": 1,
            "build_digest": "e" * 64,
            "content_hash": "f" * 64,
        },
        "routing_topology": {
            # N1 is a genuine branching node (children N2, N3), matching flow's
            # network-wide allocation contract. Delivery for SEC-1 is at N4 via
            # the N2 branch; N3 is the sibling branch, NW the withdrawal.
            "elements": [
                {
                    "element_id": "R1",
                    "upstream_node_id": "S",
                    "downstream_node_id": "N1",
                    "role": "transport",
                },
                {
                    "element_id": "B1",
                    "upstream_node_id": "N1",
                    "downstream_node_id": "N2",
                    "role": "branch_structure",
                },
                {
                    "element_id": "B2",
                    "upstream_node_id": "N1",
                    "downstream_node_id": "N3",
                    "role": "branch_structure",
                },
                {
                    "element_id": "R2",
                    "upstream_node_id": "N2",
                    "downstream_node_id": "N4",
                    "role": "transport",
                },
                {
                    "element_id": "W1",
                    "upstream_node_id": "N1",
                    "downstream_node_id": "NW",
                    "role": "withdrawal_structure",
                },
            ]
        },
        "action_model": {
            "operating_envelope": {
                "minimum_flow_m3s": 0.0,
                "maximum_flow_m3s": 10.0,
                "minimum_timestep_seconds": 300.0,
                "maximum_timestep_seconds": 3600.0,
                "maximum_horizon_seconds": 604800.0,
            }
        },
        "response_model_release": {
            "release_id": "release-2026-07",
            "content_hash": "b" * 64,
            "response_members": [
                {
                    "reach_id": reach_id,
                    "member": member,
                    "delay_seconds": delay,
                    "loss_fraction": loss,
                    "capacity_m3s": capacity,
                }
                for reach_id, rows in {
                    "R1": [
                        ("lower", 500.0, 0.10, 5.0),
                        ("nominal", 600.0, 0.05, 5.5),
                        ("upper", 700.0, 0.02, 6.0),
                    ],
                    "R2": [
                        ("lower", 1000.0, 0.05, 3.2),
                        ("nominal", 1100.0, 0.04, 3.0),
                        ("upper", 1150.0, 0.02, 3.1),
                    ],
                }.items()
                for member, delay, loss, capacity in rows
            ],
        },
        "unavailable_transport_reaches": [],
    }


def draft_payload(**overrides):
    payload = {
        "requirement_run_id": str(RUN_ID),
        "requirement_version": 3,
        "requirement_scopes": [{"service_date": "2026-07-20", "zone": 1}],
        "starts_at": "2026-07-20T00:00:00+00:00",
        "ends_at": "2026-07-21T00:00:00+00:00",
        "section_bindings": [
            {
                "section_id": "SEC-1",
                "delivery_node_id": "N4",
                "gate_id": "G1",
                "maximum_delivery_m3s": 2.5,
            }
        ],
        "requirement_policies": [
            {
                "requirement_id": REQ_ID,
                "approved_excess_m3": 1000.0,
                "rotation_windows": [
                    {
                        "starts_at": "2026-07-20T06:00:00+00:00",
                        "ends_at": "2026-07-20T18:00:00+00:00",
                    }
                ],
            }
        ],
        "flow_candidates": [
            {"gate_id": "G1", "target_position_m": 0.5, "source_flow_m3s": 2.0}
        ],
        "pulse_duties": [
            {
                "gate_id": "G1",
                "minimum_open_seconds": 3600,
                "maximum_open_seconds": 86400,
            }
        ],
        "operator_withdrawals": [],
        "branch_allocations": [
            {"upstream_node_id": "N1", "downstream_node_id": "N2",
             "fraction": 0.6},
            {"upstream_node_id": "N1", "downstream_node_id": "N3",
             "fraction": 0.4},
        ],
    }
    payload.update(overrides)
    return payload


class FakeRosGisClient:
    def __init__(self, items):
        self.items = items
        self.calls = 0

    async def get_exact_requirements(
        self, requirement_run_id, requirement_version, scopes
    ):
        self.calls += 1
        return [dict(item) for item in self.items]


def _build_member_timeline(request_document, member_name):
    """A realistic, aligned, reconciling three-member timeline for the SEC-1
    delivery at N4 over reaches R1, R2. All members deliver exactly the required
    volume (degenerate bounds) so the projector's reconciliation holds."""
    from datetime import datetime, timedelta

    starts_at = datetime.fromisoformat(request_document["starts_at"])
    ends_at = datetime.fromisoformat(request_document["ends_at"])
    step = int(request_document["timestep_seconds"])
    count = int((ends_at - starts_at).total_seconds() // step)
    # Match flow: sampled_at are step-END times, so the last sample == ends_at.
    sampled = [
        (starts_at + timedelta(seconds=(i + 1) * step)).isoformat()
        for i in range(count)
    ]
    reach_ids = ["R1", "R2"]
    reaches = [
        {
            "reach_id": rid,
            "inflow_m3s": [0.0] * count,
            "outflow_m3s": [0.0] * count,
            "in_transit_volume_m3": [
                (2.0 if 0 < i < count - 1 else 0.0) for i in range(count)
            ],
            "cumulative_declared_loss_m3": [0.0] * count,
        }
        for rid in reach_ids
    ]
    requirements = []
    final = []
    total = 0.0
    for section in request_document["section_requirements"]:
        required = float(section["required_volume_m3"])
        total += required
        delivered = [
            required * min(1.0, (i + 1) / max(1, count - 1))
            for i in range(count)
        ]
        delivered[-1] = required
        status = [
            "pending" if i == 0
            else ("predicted_fulfilled" if i == count - 1
                  else "delivery_predicted_active")
            for i in range(count)
        ]
        requirements.append(
            {
                "requirement_id": section["requirement_id"],
                "predicted_delivered_m3": delivered,
                "status": status,
            }
        )
        final.append(
            {
                "requirement_id": section["requirement_id"],
                "section_id": section["section_id"],
                "required_volume_m3": required,
                "approved_excess_m3": float(section["approved_excess_m3"]),
                "predicted_delivered_m3": required,
                "status": "predicted_fulfilled",
            }
        )
    return total, {
        "sampled_at": sampled,
        "reaches": reaches,
        "withdrawals": [],
        "requirements": requirements,
        "terminal_outflow_m3": [0.0] * count,
        "mass_balance": {
            "initial_in_transit_m3": 0.0,
            "boundary_inflow_m3": total,
            "delivered_m3": total,
            "withdrawn_m3": 0.0,
            "declared_loss_m3": 0.0,
            "terminal_outflow_m3": 0.0,
            "final_in_transit_m3": 0.0,
            "balance_error_m3": 0.0,
        },
        "final_fulfillment": final,
    }


class FakeControlFlowClient:
    def __init__(
        self,
        snapshot,
        prediction_members=None,
        prediction_error=None,
        snapshot_error=None,
        with_timeline=True,
        infeasible_members=None,
        engine_id="munbon.flow-monitoring.network-transient",
        semantic_contract_version=1,
        build_digest="e" * 64,
        engine_descriptor_content_hash="f" * 64,
    ):
        self.snapshot = snapshot
        # When prediction_members is given, the caller controls the members
        # verbatim (used to exercise malformed responses). Otherwise a realistic
        # reconciling three-member timeline is built per request; members named
        # in infeasible_members are emitted as timeline-less infeasible members.
        self.prediction_members = prediction_members
        self.prediction_error = prediction_error
        self.snapshot_error = snapshot_error
        self.with_timeline = with_timeline
        self.infeasible_members = set(infeasible_members or ())
        # Identity-v2 engine pins the real client would read from Flow headers.
        self.engine_id = engine_id
        self.semantic_contract_version = semantic_contract_version
        self.build_digest = build_digest
        self.engine_descriptor_content_hash = engine_descriptor_content_hash
        self.prediction_requests = []

    async def create_model_snapshot(self):
        if self.snapshot_error is not None:
            raise self.snapshot_error
        # Mirror production: the stored document text IS the full snapshot (which
        # embeds prediction_engine), so a v2 row's engine pins can be cross-checked
        # against the snapshot itself on reload.
        return (
            canonical_json_text(self.snapshot),
            json.loads(json.dumps(self.snapshot)),
        )

    async def create_prediction(self, request_document):
        if self.prediction_error is not None:
            raise self.prediction_error
        self.prediction_requests.append(request_document)
        if self.prediction_members is not None:
            members = self.prediction_members
        elif self.with_timeline:
            members = []
            for name in ("lower", "nominal", "upper"):
                if name in self.infeasible_members:
                    members.append(
                        {
                            "member": name,
                            "status": "infeasible",
                            "predicted_delivered_total_m3": None,
                            "timeline": None,
                        }
                    )
                    continue
                total, timeline = _build_member_timeline(request_document, name)
                members.append(
                    {
                        "member": name,
                        "status": "completed",
                        "predicted_delivered_total_m3": total,
                        "timeline": timeline,
                    }
                )
        else:
            members = [
                {"member": "lower", "status": "completed"},
                {"member": "nominal", "status": "completed"},
                {"member": "upper", "status": "completed"},
            ]
        body = {
            "prediction_run_id": "c" * 64,
            "model_snapshot_id": request_document["model_snapshot_id"],
            "model_release_id": request_document["model_release_id"],
            "model_release_content_hash": request_document[
                "model_release_content_hash"
            ],
            "starts_at": request_document["starts_at"],
            "ends_at": request_document["ends_at"],
            "members": members,
        }
        response_text = canonical_json_text(body)
        response_bytes = response_text.encode("utf-8")
        return FlowPredictionResult(
            prediction_run_id=body["prediction_run_id"],
            identity_version=2,
            engine_id=self.engine_id,
            semantic_contract_version=self.semantic_contract_version,
            build_digest=self.build_digest,
            engine_descriptor_content_hash=(
                self.engine_descriptor_content_hash
            ),
            artifact=FlowArtifactReference(
                artifact_sha256=hashlib.sha256(response_bytes).hexdigest(),
                uncompressed_size_bytes=len(response_bytes),
                media_type="application/json",
                encoding="canonical-json+zlib",
                encoding_version=1,
            ),
            response_text=response_text,
            parsed=body,
        )


class FakeRepository:
    def __init__(self):
        self.by_input_hash = {}
        self.by_key = {}
        self.store_calls = 0

    async def find_by_input_hash(self, session, input_content_hash):
        return self.by_input_hash.get(input_content_hash)

    async def store_draft_plan(self, session, record):
        self.store_calls += 1
        # Mirror production exactly: the race-loser replays on canonical INPUT
        # only (solver nondeterminism must not 409), and the winning writer
        # returns its own in-memory record (with the service's injected-clock
        # timestamps) rather than a post-commit reload.
        existing = self.by_input_hash.get(record.input_content_hash)
        if existing is not None:
            if (
                existing.canonical_input_document_text
                != record.canonical_input_document_text
            ):
                raise PlanContentConflictError(
                    "an identical input hash is stored with different content"
                )
            return existing, True
        self.by_input_hash[record.input_content_hash] = record
        self.by_key[(record.plan_id, record.plan_version)] = record
        return record, False

    async def load_draft_plan(self, session, plan_id, plan_version):
        return self.by_key.get((plan_id, plan_version))

    async def append_state_transition(
        self, session, plan_id, plan_version, transition
    ):
        record = self.by_key.get((plan_id, plan_version))
        if record is None:
            raise KeyError((plan_id, plan_version))
        # The real repository's (plan, version, sequence) PK is the concurrency
        # backstop: a second append at the same sequence conflicts.
        if any(
            t.transition_sequence == transition.transition_sequence
            for t in record.transitions
        ):
            raise TransitionConflictError(
                "a concurrent lifecycle action already advanced this plan"
            )
        updated = replace(
            record, transitions=record.transitions + (transition,)
        )
        self.by_key[(plan_id, plan_version)] = updated
        self.by_input_hash[record.input_content_hash] = updated


# --- Bounded list-projection fixtures + fake (PR 4.4a-3) --------------------
# A complete strict-mode v2 approval evidence block (is_trusted_shadow_approval
# returns True) versus a compat-mode v2 block (returns False). Built as literals
# so the fake stays independent of the production freeze builders.
TRUSTED_APPROVAL_DOCUMENT = {
    "schema_version": 2,
    "lineage_freeze": {"machine_authority_granted": False},
    "authorization_evidence": {
        "authorization_policy_version": "control-plan-rbac-v1",
        "claim_policy_mode": "strict",
        "subject": "supervisor-1",
        "roles": ["supervisor"],
        "token_identity_sha256": "a" * 64,
        "request_id": "req-123",
        "evidence_refs": ["ticket-77"],
    },
}
UNTRUSTED_APPROVAL_DOCUMENT = {
    "schema_version": 2,
    "lineage_freeze": {"machine_authority_granted": False},
    "authorization_evidence": {
        "authorization_policy_version": "control-plan-rbac-v1",
        "claim_policy_mode": "compat",
        "subject": "supervisor-1",
        "roles": ["supervisor"],
        "token_identity_sha256": "a" * 64,
        "request_id": "req-123",
        "evidence_refs": ["ticket-77"],
    },
}

# The transition chain that reaches each lifecycle state (matching the declared
# edge graph in core.control_plan_lifecycle).
_CHAIN_TO_STATE = {
    "draft": [("draft_created", None, "draft")],
    "under_review": [
        ("draft_created", None, "draft"),
        ("review_requested", "draft", "under_review"),
    ],
    "approved_for_shadow": [
        ("draft_created", None, "draft"),
        ("review_requested", "draft", "under_review"),
        ("shadow_approved", "under_review", "approved_for_shadow"),
    ],
    "cancelled": [
        ("draft_created", None, "draft"),
        ("cancelled", "draft", "cancelled"),
    ],
    "invalidated": [
        ("draft_created", None, "draft"),
        ("invalidated", "draft", "invalidated"),
    ],
}


def _transition_chain(lifecycle: str, approval_document: Optional[dict]):
    chain = _CHAIN_TO_STATE[lifecycle]
    transitions = []
    for sequence, (kind, from_state, to_state) in enumerate(chain, start=1):
        document_text = None
        if kind == "shadow_approved" and approval_document is not None:
            document_text = json.dumps(approval_document, separators=(",", ":"))
        transitions.append(
            TransitionRecord(
                transition_sequence=sequence,
                transition_type=kind,
                from_state=from_state,
                to_state=to_state,
                actor_subject="actor",
                reason=None,
                transition_document_text=document_text,
            )
        )
    return tuple(transitions)


@dataclass(frozen=True)
class ProjectionRecord:
    """In-memory stand-in for a control_plan_runs header + its transition chain,
    carrying exactly the columns the bounded list projection reads."""

    plan_id: UUID
    plan_version: int
    created_at: datetime
    horizon_start: datetime
    horizon_end: datetime
    requirement_run_id: UUID
    requirement_version: int
    input_content_hash: str
    model_snapshot_id: str
    model_release_content_hash: str
    optimizer_status: str
    prediction_status: str
    prediction_run_id: Optional[str]
    prediction_response_sha256: Optional[str]
    artifact_sha256: Optional[str]
    created_by_subject: str
    transitions: tuple = field(default_factory=tuple)

    @property
    def prediction_content_sha256(self) -> Optional[str]:
        """The served/filterable content hash: the v1 response sha, else the v2
        artifact sha — the exact COALESCE the Postgres projection selects."""
        return self.prediction_response_sha256 or self.artifact_sha256


def projection_record(
    plan_id: UUID,
    created_at: datetime,
    *,
    plan_version: int = 1,
    lifecycle: str = "draft",
    approval_document: Optional[dict] = None,
    horizon_start: Optional[datetime] = None,
    horizon_end: Optional[datetime] = None,
    requirement_run_id: UUID = RUN_ID,
    requirement_version: int = 3,
    input_content_hash: str = "1" * 64,
    model_snapshot_id: str = "a" * 64,
    model_release_content_hash: str = "b" * 64,
    optimizer_status: str = "feasible",
    prediction_status: str = "completed",
    prediction_run_id: Optional[str] = "c" * 64,
    prediction_response_sha256: Optional[str] = "d" * 64,
    artifact_sha256: Optional[str] = None,
    created_by_subject: str = "operator-1",
) -> ProjectionRecord:
    return ProjectionRecord(
        plan_id=plan_id,
        plan_version=plan_version,
        created_at=created_at,
        horizon_start=horizon_start
        or datetime(2026, 7, 20, tzinfo=timezone.utc),
        horizon_end=horizon_end or datetime(2026, 7, 21, tzinfo=timezone.utc),
        requirement_run_id=requirement_run_id,
        requirement_version=requirement_version,
        input_content_hash=input_content_hash,
        model_snapshot_id=model_snapshot_id,
        model_release_content_hash=model_release_content_hash,
        optimizer_status=optimizer_status,
        prediction_status=prediction_status,
        prediction_run_id=prediction_run_id,
        prediction_response_sha256=prediction_response_sha256,
        artifact_sha256=artifact_sha256,
        created_by_subject=created_by_subject,
        transitions=_transition_chain(lifecycle, approval_document),
    )


def _record_matches(record: ProjectionRecord, filters: ControlPlanListFilters) -> bool:
    if filters.lifecycle_state is not None:
        if derive_control_plan_state(record.transitions) != filters.lifecycle_state:
            return False
    if filters.horizon_start_gte is not None and (
        record.horizon_start < filters.horizon_start_gte
    ):
        return False
    if filters.horizon_end_lte is not None and (
        record.horizon_end > filters.horizon_end_lte
    ):
        return False
    if filters.requirement_run_id is not None and (
        record.requirement_run_id != filters.requirement_run_id
    ):
        return False
    if filters.requirement_version is not None and (
        record.requirement_version != filters.requirement_version
    ):
        return False
    if filters.input_content_hash is not None and (
        record.input_content_hash != filters.input_content_hash
    ):
        return False
    if filters.model_snapshot_id is not None and (
        record.model_snapshot_id != filters.model_snapshot_id
    ):
        return False
    if filters.model_release_content_hash is not None and (
        record.model_release_content_hash != filters.model_release_content_hash
    ):
        return False
    if filters.prediction_run_id is not None and (
        record.prediction_run_id != filters.prediction_run_id
    ):
        return False
    if filters.prediction_content_sha256 is not None and (
        record.prediction_content_sha256 != filters.prediction_content_sha256
    ):
        return False
    return True


def _summary_from(record: ProjectionRecord) -> ControlPlanSummaryOut:
    trust = False
    for transition in record.transitions:
        if transition.transition_type != "shadow_approved":
            continue
        text = transition.transition_document_text
        trust = bool(text) and is_trusted_shadow_approval(json.loads(text))
    return ControlPlanSummaryOut(
        plan_id=record.plan_id,
        plan_version=record.plan_version,
        lifecycle_state=derive_control_plan_state(record.transitions),
        approval_trust=trust,
        horizon_start=record.horizon_start,
        horizon_end=record.horizon_end,
        requirement_run_id=record.requirement_run_id,
        requirement_version=record.requirement_version,
        input_content_hash=record.input_content_hash,
        model_snapshot_id=record.model_snapshot_id,
        model_release_content_hash=record.model_release_content_hash,
        optimizer_status=record.optimizer_status,
        prediction_status=record.prediction_status,
        prediction_run_id=record.prediction_run_id,
        prediction_response_sha256=record.prediction_content_sha256,
        created_by_subject=record.created_by_subject,
        created_at=record.created_at,
    )


class FakeControlPlanProjectionRepository:
    """In-memory twin of PostgresControlPlanProjectionRepository: same
    ``list_plan_summaries`` signature and identical keyset semantics (order
    ``created_at DESC, plan_id DESC, plan_version DESC``, row-value keyset over the
    row's TOTAL identity, limit+1 for next_cursor), implemented independently so a
    divergence fails a test. The Python ``(created_at, plan_id, plan_version)``
    tuple order matches Postgres's row-value comparison because ``UUID.__lt__`` is
    the same big-endian byte order Postgres uses for ``uuid`` and ``plan_version``
    is a plain integer."""

    def __init__(self, records):
        self.records = list(records)

    async def list_plan_summaries(
        self, session, *, filters: ControlPlanListFilters, cursor, limit: int
    ) -> ControlPlanListPage:
        identity = filters.cursor_identity()
        keyset = decode_plan_cursor(cursor, identity) if cursor is not None else None
        selected = [r for r in self.records if _record_matches(r, filters)]
        selected.sort(
            key=lambda r: (r.created_at, r.plan_id, r.plan_version), reverse=True
        )
        if keyset is not None:
            cursor_created_at, cursor_plan_id, cursor_plan_version = keyset
            selected = [
                r
                for r in selected
                if (r.created_at, r.plan_id, r.plan_version)
                < (cursor_created_at, cursor_plan_id, cursor_plan_version)
            ]
        window = selected[: limit + 1]
        has_more = len(window) > limit
        page = window[:limit]
        next_cursor = None
        if has_more and page:
            next_cursor = encode_plan_cursor(
                page[-1].created_at,
                page[-1].plan_id,
                page[-1].plan_version,
                identity,
            )
        return ControlPlanListPage(
            items=[_summary_from(r) for r in page],
            next_cursor=next_cursor,
            projection_schema_version=PROJECTION_SCHEMA_VERSION,
        )
