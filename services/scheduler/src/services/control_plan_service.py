"""Draft control-plan orchestration (PR 4.3a).

`create_draft_control_plan` verifies caller-pinned exact requirements, obtains
one model snapshot, composes the limited-adjustment problem, optimizes,
predicts feasible results through Flow, and persists one immutable
content-addressed draft. Optimizer infeasibility is a valid persisted draft;
every upstream failure aborts with nothing persisted.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from algorithms.hydraulic_schedule_optimizer import (
    GateEventKind,
    LimitedAdjustmentPlan,
    PlanStatus,
)
from core.control_plan import (
    UpstreamContractError,
    build_control_prediction_request,
    build_limited_adjustment_problem,
    canonical_instant,
    canonical_json_text,
    control_plan_draft_hash,
    control_plan_input_hash,
    serialize_limited_adjustment_plan,
    summarize_prediction_status,
)
from core.predicted_delivery_ledger import (
    GateEvent,
    ScheduledRequirement,
    predicted_delivery_ledger_sha256,
    project_predicted_delivery_ledger,
)
from repositories.control_plan_repository import (
    PROVENANCE_VERSION_V2,
    DraftPlanRecord,
    GateEventRecord,
    PlanContentConflictError,
    RequirementRecord,
    TransitionRecord,
    build_draft_hash_document,
    build_provenance_reference_document,
    provenance_reference_sha256,
    text_sha256,
)
from services.clients.control_client_errors import UpstreamContractViolation
from schemas.control_plan import DraftControlPlanRequest

IDENTITY_VERSION = 1
OPTIMIZER_CONTRACT_VERSION = 1


class PlanNotFoundError(Exception):
    """No stored draft carries the requested plan id and version."""


class ModelIncompleteError(Exception):
    """The model snapshot cannot support drafting (HTTP 503)."""


class ControlPlanDraftService:
    def __init__(
        self,
        *,
        ros_client,
        flow_client,
        repository,
        optimizer: Callable[..., LimitedAdjustmentPlan],
        run_blocking: Callable[..., Awaitable[Any]],
        model_step_seconds: int,
        max_intermediate_trims: int,
        solver_timeout_seconds: int,
        clock: Callable[[], datetime] = None,
    ) -> None:
        self._ros = ros_client
        self._flow = flow_client
        self._repository = repository
        self._optimizer = optimizer
        self._run_blocking = run_blocking
        self._model_step_seconds = model_step_seconds
        self._max_intermediate_trims = max_intermediate_trims
        self._solver_timeout_seconds = solver_timeout_seconds
        # An explicit creation instant lets the repository commit the full
        # record atomically without a post-commit reload (which could fail
        # after a successful commit and wrongly report 503).
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def create_draft(
        self,
        session: AsyncSession,
        request: DraftControlPlanRequest,
        actor_subject: str,
    ) -> tuple[DraftPlanRecord, bool]:
        snapshot_text, snapshot = await self._flow.create_model_snapshot()
        release = snapshot.get("response_model_release")
        envelope = (snapshot.get("action_model") or {}).get(
            "operating_envelope"
        )
        if release is None or envelope is None:
            raise ModelIncompleteError(
                "flow-monitoring serves no committed model release; "
                "drafting is unavailable"
            )
        if snapshot["data_status"] not in ("complete", "partial"):
            raise ModelIncompleteError(
                f"model snapshot data_status is "
                f"{snapshot['data_status']!r}; drafting is unavailable"
            )

        scopes = [
            (scope.service_date, scope.zone)
            for scope in request.requirement_scopes
        ]
        items = await self._ros.get_exact_requirements(
            request.requirement_run_id,
            request.requirement_version,
            scopes,
        )

        problem, derived_document = build_limited_adjustment_problem(
            snapshot_id=snapshot["snapshot_id"],
            routing_elements=snapshot["routing_topology"]["elements"],
            response_members=release["response_members"],
            operating_envelope=envelope,
            unavailable_reach_ids=[
                entry["reach_id"]
                for entry in snapshot["unavailable_transport_reaches"]
            ],
            requirement_items=items,
            section_bindings={
                binding.section_id: binding.model_dump()
                for binding in request.section_bindings
            },
            requirement_policies={
                policy.requirement_id: policy.model_dump()
                for policy in request.requirement_policies
            },
            flow_candidates=[
                candidate.model_dump()
                for candidate in request.flow_candidates
            ],
            pulse_duties=[duty.model_dump() for duty in request.pulse_duties],
            branch_allocations=[
                allocation.model_dump()
                for allocation in request.branch_allocations
            ],
            operator_withdrawals=[
                withdrawal.model_dump()
                for withdrawal in request.operator_withdrawals
            ],
            horizon_start=request.starts_at,
            horizon_end=request.ends_at,
            model_step_seconds=self._model_step_seconds,
        )

        item_documents = sorted(
            (self._requirement_document(item) for item in items),
            key=lambda document: document["requirement_id"],
        )
        # The optional campaign_id joined the request schema in PR 4.4b-4, but it
        # must NOT perturb the content-addressed identity of a request that omits
        # it: a byte-identical pre-4.4b-4 request (which had no campaign_id field at
        # all) has to keep the SAME input_content_hash and replay its stored draft.
        # So a NULL campaign_id is EXCLUDED from the hashed request document, making
        # the new-campaign path serialize exactly as it did pre-4.4b-4; a PRESENT
        # campaign_id stays in (a campaign-pinned request is a distinct draft).
        request_document = request.model_dump(
            mode="json",
            exclude={"campaign_id"} if request.campaign_id is None else set(),
        )
        input_document = {
            "identity_version": IDENTITY_VERSION,
            "request": request_document,
            "requirements": item_documents,
            "snapshot_pins": {
                "model_snapshot_id": snapshot["snapshot_id"],
                "model_release_id": release["release_id"],
                "model_release_content_hash": release["content_hash"],
            },
            "derived_problem": derived_document,
            "optimizer": {
                "contract_version": OPTIMIZER_CONTRACT_VERSION,
                "model_step_seconds": self._model_step_seconds,
                "max_intermediate_trims": self._max_intermediate_trims,
                "solver_timeout_seconds": self._solver_timeout_seconds,
            },
        }
        input_text = canonical_json_text(input_document)
        input_hash = control_plan_input_hash(input_document)

        existing = await self._repository.find_by_input_hash(
            session, input_hash
        )
        if existing is not None:
            if existing.canonical_input_document_text != input_text:
                raise PlanContentConflictError(
                    "an identical input hash is stored with different content"
                )
            return existing, True

        plan = await self._run_blocking(self._optimizer, problem)
        optimizer_document = serialize_limited_adjustment_plan(plan)
        optimizer_text = canonical_json_text(optimizer_document)

        candidate_flow = {
            (candidate.gate_id, candidate.target_position_m):
                candidate.source_flow_m3s
            for candidate in request.flow_candidates
        }
        events = self._event_records(plan, candidate_flow)

        prediction_run_id: Optional[str] = None
        prediction_status = "not_requested"
        member_summaries_text: Optional[str] = None
        prediction_request_text: Optional[str] = None
        prediction_response_text: Optional[str] = None
        prediction_response_sha: Optional[str] = None
        ledger_entries: tuple = ()
        # Draft-hash prediction binding: None for infeasible, the provenance
        # reference sha256 for a feasible v2 draft (see below).
        prediction_binding: Optional[str] = None
        provenance: dict[str, Any] = {}
        if plan.status is PlanStatus.FEASIBLE:
            obligation_by_id = {
                entry["requirement_id"]: entry
                for entry in derived_document["obligations"]
            }
            prediction_document = build_control_prediction_request(
                model_snapshot_id=snapshot["snapshot_id"],
                model_release_id=release["release_id"],
                model_release_content_hash=release["content_hash"],
                starts_at=request.starts_at,
                ends_at=request.ends_at,
                timestep_seconds=float(self._model_step_seconds),
                plan_events=plan.events,
                flow_candidates=[
                    candidate.model_dump()
                    for candidate in request.flow_candidates
                ],
                operator_withdrawals=[
                    withdrawal.model_dump()
                    for withdrawal in request.operator_withdrawals
                ],
                branch_allocations=[
                    allocation.model_dump()
                    for allocation in request.branch_allocations
                ],
                section_requirements=[
                    {
                        "requirement_id": item["requirement_id"],
                        "section_id": item["section_id"],
                        "delivery_node_id": obligation_by_id[
                            item["requirement_id"]
                        ]["delivery_node_id"],
                        "window_start": item["window_start"],
                        "window_end": item["window_end"],
                        "required_volume_m3": item["required_volume_m3"],
                        "maximum_delivery_m3s": self._binding_for(
                            request, item["section_id"]
                        ).maximum_delivery_m3s,
                        "approved_excess_m3": self._policy_for(
                            request, item["requirement_id"]
                        ).approved_excess_m3,
                    }
                    for item in items
                    if item["requirement_id"] in obligation_by_id
                ],
            )
            prediction_request_text = canonical_json_text(prediction_document)
            # The full response is used ONLY in-memory (ledger projection +
            # bounded summaries) and then DISCARDED: only the verified artifact
            # reference and bounded summaries are persisted (v2). The client has
            # already recomputed + verified the artifact sha/size vs headers.
            prediction_result = await self._flow.create_prediction(
                prediction_document
            )
            # Tie the RECORDED engine pins to the snapshot's OWN embedded engine
            # descriptor: a Flow/proxy returning engine-B headers on an engine-A
            # snapshot is refused here, before anything is projected or persisted.
            self._require_prediction_engine_matches_snapshot(
                snapshot, prediction_result
            )
            prediction_parsed = prediction_result.parsed
            prediction_run_id = prediction_result.prediction_run_id
            prediction_status = summarize_prediction_status(prediction_parsed)
            member_summaries_text = canonical_json_text(
                [
                    {
                        "member": member.get("member"),
                        "status": member.get("status"),
                    }
                    for member in prediction_parsed["members"]
                ]
            )
            artifact = prediction_result.artifact
            ledger_entries = tuple(
                project_predicted_delivery_ledger(
                    self._scheduled_requirements(
                        request, items, derived_document
                    ),
                    prediction_parsed,
                    self._gate_events(plan),
                    prediction_run_id=prediction_run_id,
                    prediction_response_sha256=artifact.artifact_sha256,
                )
            )
            coverage_summary_text = canonical_json_text(
                self._coverage_summary(
                    request,
                    prediction_run_id,
                    prediction_status,
                    prediction_parsed,
                    ledger_entries,
                )
            )
            coverage_summary_sha = text_sha256(coverage_summary_text)
            ledger_sha = predicted_delivery_ledger_sha256(ledger_entries)
            provenance = {
                "provenance_version": PROVENANCE_VERSION_V2,
                "prediction_identity_version": prediction_result.identity_version,
                "engine_id": prediction_result.engine_id,
                "engine_semantic_contract_version": (
                    prediction_result.semantic_contract_version
                ),
                "engine_build_digest": prediction_result.build_digest,
                "engine_descriptor_content_hash": (
                    prediction_result.engine_descriptor_content_hash
                ),
                "artifact_sha256": artifact.artifact_sha256,
                "artifact_uncompressed_size_bytes": (
                    artifact.uncompressed_size_bytes
                ),
                "artifact_media_type": artifact.media_type,
                "artifact_encoding": artifact.encoding,
                "artifact_encoding_version": artifact.encoding_version,
                "coverage_summary_document_text": coverage_summary_text,
                "coverage_summary_sha256": coverage_summary_sha,
                "predicted_delivery_ledger_sha256": ledger_sha,
            }
            prediction_binding = provenance_reference_sha256(
                build_provenance_reference_document(
                    prediction_run_id=prediction_run_id,
                    prediction_identity_version=(
                        prediction_result.identity_version
                    ),
                    engine_id=prediction_result.engine_id,
                    engine_semantic_contract_version=(
                        prediction_result.semantic_contract_version
                    ),
                    engine_build_digest=prediction_result.build_digest,
                    engine_descriptor_content_hash=(
                        prediction_result.engine_descriptor_content_hash
                    ),
                    artifact_sha256=artifact.artifact_sha256,
                    artifact_uncompressed_size_bytes=(
                        artifact.uncompressed_size_bytes
                    ),
                    artifact_media_type=artifact.media_type,
                    artifact_encoding=artifact.encoding,
                    artifact_encoding_version=artifact.encoding_version,
                    prediction_member_summaries_sha256=text_sha256(
                        member_summaries_text
                    ),
                    coverage_summary_sha256=coverage_summary_sha,
                    predicted_delivery_ledger_sha256=ledger_sha,
                )
            )

        draft_hash = control_plan_draft_hash(
            build_draft_hash_document(
                input_text,
                optimizer_text,
                prediction_request_text,
                prediction_binding,
            )
        )

        # Only a GENUINE new input reaches here (the replay check above returned
        # early), so allocate exactly one campaign version now — after all compute
        # succeeded, minimizing the advisory-lock hold. A present-but-unknown
        # campaign_id fails closed here; a failed store consumes no version (the
        # lock releases at txn end without a committed mapping row).
        campaign_id, plan_version, plan_id = (
            await self._repository.allocate_campaign_version(
                session, request.campaign_id
            )
        )
        created_at = self._clock()
        record = DraftPlanRecord(
            plan_id=plan_id,
            plan_version=plan_version,
            campaign_id=campaign_id,
            identity_version=IDENTITY_VERSION,
            input_content_hash=input_hash,
            draft_content_hash=draft_hash,
            lifecycle_state="draft",
            optimizer_status=plan.status.value,
            prediction_status=prediction_status,
            requirement_run_id=request.requirement_run_id,
            requirement_version=request.requirement_version,
            model_snapshot_id=snapshot["snapshot_id"],
            model_release_id=release["release_id"],
            model_release_content_hash=release["content_hash"],
            prediction_run_id=prediction_run_id,
            prediction_member_summaries=member_summaries_text,
            horizon_start=request.starts_at,
            horizon_end=request.ends_at,
            model_step_seconds=self._model_step_seconds,
            max_intermediate_trims=self._max_intermediate_trims,
            canonical_input_document_text=input_text,
            model_snapshot_document_text=snapshot_text,
            optimizer_result_document_text=optimizer_text,
            optimizer_result_sha256=text_sha256(optimizer_text),
            prediction_request_document_text=prediction_request_text,
            prediction_response_document_text=prediction_response_text,
            prediction_response_sha256=prediction_response_sha,
            provenance_version=provenance.get("provenance_version"),
            prediction_identity_version=provenance.get(
                "prediction_identity_version"
            ),
            engine_id=provenance.get("engine_id"),
            engine_semantic_contract_version=provenance.get(
                "engine_semantic_contract_version"
            ),
            engine_build_digest=provenance.get("engine_build_digest"),
            engine_descriptor_content_hash=provenance.get(
                "engine_descriptor_content_hash"
            ),
            artifact_sha256=provenance.get("artifact_sha256"),
            artifact_uncompressed_size_bytes=provenance.get(
                "artifact_uncompressed_size_bytes"
            ),
            artifact_media_type=provenance.get("artifact_media_type"),
            artifact_encoding=provenance.get("artifact_encoding"),
            artifact_encoding_version=provenance.get(
                "artifact_encoding_version"
            ),
            coverage_summary_document_text=provenance.get(
                "coverage_summary_document_text"
            ),
            coverage_summary_sha256=provenance.get("coverage_summary_sha256"),
            predicted_delivery_ledger_sha256=provenance.get(
                "predicted_delivery_ledger_sha256"
            ),
            created_by_subject=actor_subject,
            requirements=self._requirement_records(
                request, items, derived_document
            ),
            events=events,
            transitions=(
                TransitionRecord(
                    transition_sequence=1,
                    transition_type="draft_created",
                    from_state=None,
                    to_state="draft",
                    actor_subject=actor_subject,
                    reason=None,
                    transition_document_text=None,
                    occurred_at=created_at,
                ),
            ),
            ledger_entries=ledger_entries,
            created_at=created_at,
        )
        return await self._repository.store_draft_plan(session, record)

    async def get_draft(
        self, session: AsyncSession, plan_id: UUID, plan_version: int
    ) -> DraftPlanRecord:
        record = await self._repository.load_draft_plan(
            session, plan_id, plan_version
        )
        if record is None:
            raise PlanNotFoundError(
                f"no control plan {plan_id} version {plan_version}"
            )
        return record

    @staticmethod
    def _require_prediction_engine_matches_snapshot(
        snapshot: dict[str, Any], prediction_result
    ) -> None:
        """Fail closed unless the served prediction's engine identity EXACTLY
        equals the prediction_engine descriptor the model snapshot embeds.

        The snapshot's descriptor is the authority (its content_hash enters the
        snapshot id); the response headers are only trusted once they match it, so
        engine-B headers served over an engine-A snapshot can never be recorded."""
        engine = snapshot.get("prediction_engine")
        if not isinstance(engine, dict):
            raise UpstreamContractViolation(
                "model snapshot carries no embedded prediction_engine descriptor; "
                "the engine identity cannot be bound to the snapshot"
            )
        if (
            prediction_result.engine_id != engine.get("engine_id")
            or prediction_result.semantic_contract_version
            != engine.get("semantic_contract_version")
            or prediction_result.build_digest != engine.get("build_digest")
            or prediction_result.engine_descriptor_content_hash
            != engine.get("content_hash")
        ):
            raise UpstreamContractViolation(
                "prediction engine identity does not match the model snapshot's "
                "embedded prediction_engine descriptor"
            )

    @staticmethod
    def _binding_for(request: DraftControlPlanRequest, section_id: str):
        for binding in request.section_bindings:
            if binding.section_id == section_id:
                return binding
        raise UpstreamContractError(
            f"section {section_id!r} lost its binding mid-orchestration"
        )

    @staticmethod
    def _policy_for(request: DraftControlPlanRequest, requirement_id: str):
        for policy in request.requirement_policies:
            if policy.requirement_id == requirement_id:
                return policy
        raise UpstreamContractError(
            f"requirement {requirement_id!r} lost its policy mid-orchestration"
        )

    def _scheduled_requirements(
        self,
        request: DraftControlPlanRequest,
        items: list[dict[str, Any]],
        derived_document: dict[str, Any],
    ) -> list[ScheduledRequirement]:
        obligation_by_id = {
            entry["requirement_id"]: entry
            for entry in derived_document["obligations"]
        }
        item_by_id = {item["requirement_id"]: item for item in items}
        scheduled = []
        for requirement_id, obligation in obligation_by_id.items():
            item = item_by_id[requirement_id]
            policy = self._policy_for(request, requirement_id)
            scheduled.append(
                ScheduledRequirement(
                    requirement_id=requirement_id,
                    section_id=item["section_id"],
                    gate_id=obligation["gate_id"],
                    required_volume_m3=float(item["required_volume_m3"]),
                    approved_excess_m3=float(policy.approved_excess_m3),
                    path_reach_ids=tuple(obligation["path_reach_ids"]),
                    window_start=item["window_start"],
                    window_end=item["window_end"],
                )
            )
        return scheduled

    @staticmethod
    def _coverage_summary(
        request: DraftControlPlanRequest,
        prediction_run_id: str,
        prediction_status: str,
        prediction_parsed: dict[str, Any],
        ledger_entries: tuple,
    ) -> dict[str, Any]:
        """A BOUNDED per-member delivery-coverage summary — never the trajectory.

        Captures the three member labels/statuses/totals plus the horizon and the
        set of ledger-covered requirements, so a v2 read can prove completion
        without the full response."""
        return {
            "prediction_run_id": prediction_run_id,
            "prediction_status": prediction_status,
            "horizon_start": canonical_instant(request.starts_at),
            "horizon_end": canonical_instant(request.ends_at),
            "scheduled_requirement_ids": sorted(
                {entry.requirement_id for entry in ledger_entries}
            ),
            "ledger_entry_count": len(ledger_entries),
            "members": [
                {
                    "member": member.get("member"),
                    "status": member.get("status"),
                    "predicted_delivered_total_m3": member.get(
                        "predicted_delivered_total_m3"
                    ),
                }
                for member in prediction_parsed["members"]
            ],
        }

    @staticmethod
    def _gate_events(plan: LimitedAdjustmentPlan) -> list[GateEvent]:
        return [
            GateEvent(
                gate_id=event.gate_id,
                kind=event.kind.value,
                planned_at=event.planned_at,
                target_position_m=event.target_position_m,
            )
            for event in plan.events
        ]

    @staticmethod
    def _requirement_document(item: dict[str, Any]) -> dict[str, Any]:
        document = dict(item)
        document["service_date"] = item["service_date"].isoformat()
        document["as_of_date"] = item["as_of_date"].isoformat()
        document["window_start"] = canonical_instant(item["window_start"])
        document["window_end"] = canonical_instant(item["window_end"])
        document["published_at"] = canonical_instant(item["published_at"])
        return document

    def _requirement_records(
        self,
        request: DraftControlPlanRequest,
        items: list[dict[str, Any]],
        derived_document: dict[str, Any],
    ) -> tuple[RequirementRecord, ...]:
        obligation_by_id = {
            entry["requirement_id"]: entry
            for entry in derived_document["obligations"]
        }
        records = []
        for item in sorted(items, key=lambda entry: entry["requirement_id"]):
            requirement_id = item["requirement_id"]
            obligation = obligation_by_id.get(requirement_id)
            if obligation is None:
                planning: dict[str, Any] = {
                    "planning_disposition": "no_delivery_required",
                    "delivery_node_id": None,
                    "gate_id": None,
                    "maximum_delivery_m3s": None,
                    "approved_excess_m3": None,
                    "travel_delay_seconds": None,
                    "minimum_delivery_fraction": None,
                    "maximum_delivery_fraction": None,
                    "path_reach_ids_document_text": None,
                    "rotation_windows_document_text": None,
                }
            else:
                binding = self._binding_for(request, item["section_id"])
                policy = self._policy_for(request, requirement_id)
                planning = {
                    "planning_disposition": "scheduled",
                    "delivery_node_id": obligation["delivery_node_id"],
                    "gate_id": obligation["gate_id"],
                    "maximum_delivery_m3s": binding.maximum_delivery_m3s,
                    "approved_excess_m3": policy.approved_excess_m3,
                    "travel_delay_seconds": obligation[
                        "travel_delay_seconds"
                    ],
                    "minimum_delivery_fraction": obligation[
                        "minimum_delivery_fraction"
                    ],
                    "maximum_delivery_fraction": obligation[
                        "maximum_delivery_fraction"
                    ],
                    "path_reach_ids_document_text": canonical_json_text(
                        obligation["path_reach_ids"]
                    ),
                    "rotation_windows_document_text": canonical_json_text(
                        [
                            {
                                "starts_at": canonical_instant(
                                    window.starts_at
                                ),
                                "ends_at": canonical_instant(window.ends_at),
                            }
                            for window in policy.rotation_windows
                        ]
                    ),
                }
            records.append(
                RequirementRecord(
                    requirement_id=UUID(requirement_id),
                    run_id=UUID(item["run_id"]),
                    source_version=item["version"],
                    service_date=item["service_date"],
                    section_id=item["section_id"],
                    zone=item["zone"],
                    required_volume_m3=item["required_volume_m3"],
                    window_start=item["window_start"],
                    window_end=item["window_end"],
                    quality=item["quality"],
                    published_at=item["published_at"],
                    as_of_date=item["as_of_date"],
                    source_data_status=item["data_status"],
                    requirement_document_text=canonical_json_text(
                        self._requirement_document(item)
                    ),
                    **planning,
                )
            )
        return tuple(records)

    @staticmethod
    def _event_records(
        plan: LimitedAdjustmentPlan,
        candidate_flow: dict[tuple[str, float], float],
    ) -> tuple[GateEventRecord, ...]:
        records = []
        gate_sequence: dict[str, int] = defaultdict(int)
        trim_count: dict[str, int] = defaultdict(int)
        for index, event in enumerate(plan.events, start=1):
            gate_sequence[event.gate_id] += 1
            if event.kind is GateEventKind.CLOSE:
                flow = 0.0
                trim_ordinal = None
            else:
                flow = candidate_flow[
                    (event.gate_id, event.target_position_m)
                ]
                if event.kind is GateEventKind.TRIM:
                    trim_count[event.gate_id] += 1
                    trim_ordinal = trim_count[event.gate_id]
                else:
                    trim_ordinal = None
            records.append(
                GateEventRecord(
                    event_sequence=index,
                    gate_event_sequence=gate_sequence[event.gate_id],
                    gate_id=event.gate_id,
                    event_kind=event.kind.value,
                    planned_at=event.planned_at,
                    target_position_m=event.target_position_m,
                    source_flow_m3s=flow,
                    trim_ordinal=trim_ordinal,
                )
            )
        return tuple(records)


def parse_member_summaries(record: DraftPlanRecord) -> list[dict[str, Any]]:
    if record.prediction_member_summaries is None:
        return []
    return json.loads(record.prediction_member_summaries)
