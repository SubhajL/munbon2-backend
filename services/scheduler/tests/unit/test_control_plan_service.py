"""Draft orchestration: pinning, idempotency, infeasibility, fail-closed."""

import json
from dataclasses import replace
from functools import partial
from uuid import uuid4

import pytest

from algorithms.hydraulic_schedule_optimizer import (
    optimize_limited_adjustment_plan,
)
from repositories.control_plan_repository import PlanContentConflictError
from schemas.control_plan import DraftControlPlanRequest
from services.clients.control_client_errors import (
    FlowLineageConflictError,
    UpstreamContractViolation,
    UpstreamUnavailableError,
)
from services.control_plan_service import (
    ControlPlanDraftService,
    ModelIncompleteError,
)
from tests.control_plan_test_support import (
    REQ_ID,
    FakeControlFlowClient,
    FakeRepository,
    FakeRosGisClient,
    draft_payload,
    requirement_item,
    snapshot_mirror,
)


def _request(**overrides):
    return DraftControlPlanRequest.model_validate(draft_payload(**overrides))


async def _run_blocking(func, *args, **kwargs):
    return func(*args, **kwargs)


def _service(ros=None, flow=None, repository=None):
    ros = ros if ros is not None else FakeRosGisClient([requirement_item()])
    flow = flow if flow is not None else FakeControlFlowClient(
        snapshot_mirror()
    )
    repository = repository if repository is not None else FakeRepository()
    service = ControlPlanDraftService(
        ros_client=ros,
        flow_client=flow,
        repository=repository,
        optimizer=partial(
            optimize_limited_adjustment_plan,
            model_step_seconds=3600,
            max_intermediate_trims=1,
            solver_timeout_seconds=60,
        ),
        run_blocking=_run_blocking,
        model_step_seconds=3600,
        max_intermediate_trims=1,
        solver_timeout_seconds=60,
    )
    return service, ros, flow, repository


class TestCreateDraft:
    @pytest.mark.asyncio
    async def test_feasible_draft_persists_full_lineage(self):
        service, _, flow, repository = _service()
        record, replayed = await service.create_draft(
            None, _request(), "operator-1"
        )
        assert not replayed
        assert record.optimizer_status == "feasible"
        assert record.prediction_status == "completed"
        assert record.prediction_run_id == "c" * 64
        assert record.model_snapshot_id == "a" * 64
        assert record.model_release_id == "release-2026-07"
        assert record.created_by_subject == "operator-1"
        assert record.created_at is not None
        assert len(record.events) >= 2
        assert record.transitions[0].transition_type == "draft_created"
        assert record.transitions[0].from_state is None
        assert record.transitions[0].to_state == "draft"
        requirement = record.requirements[0]
        assert requirement.planning_disposition == "scheduled"
        assert json.loads(requirement.path_reach_ids_document_text) == [
            "R1",
            "R2",
        ]
        assert requirement.travel_delay_seconds == 3600
        assert repository.store_calls == 1

    @pytest.mark.asyncio
    async def test_prediction_request_covers_horizon_start(self):
        service, _, flow, _ = _service()
        await service.create_draft(None, _request(), "operator-1")
        prediction_request = flow.prediction_requests[0]
        first_event = prediction_request["source_flow_events"][0]
        assert first_event["effective_at"] == "2026-07-20T00:00:00+00:00"
        assert prediction_request["initialization"] == {"kind": "dry"}
        assert prediction_request["section_requirements"][0][
            "delivery_node_id"
        ] == "N4"

    @pytest.mark.asyncio
    async def test_draft_pins_exact_requirement_and_prediction_versions(self):
        service, ros, _, repository = _service()
        record, _ = await service.create_draft(None, _request(), "operator-1")
        original_document = record.requirements[0].requirement_document_text
        assert json.loads(original_document)["required_volume_m3"] == 6000.0

        # The latest pointer drifts: same run/version claim, new content.
        ros.items = [requirement_item(volume=6500.0)]
        drifted, drift_replayed = await service.create_draft(
            None, _request(), "operator-1"
        )
        assert not drift_replayed
        assert drifted.plan_id != record.plan_id
        stored = await repository.load_draft_plan(
            None, record.plan_id, record.plan_version
        )
        assert stored.requirements[0].requirement_document_text == (
            original_document
        )

    @pytest.mark.asyncio
    async def test_duplicate_draft_request_is_content_idempotent(self):
        service, _, _, repository = _service()
        first, first_replayed = await service.create_draft(
            None, _request(), "operator-1"
        )
        second, second_replayed = await service.create_draft(
            None, _request(), "operator-2"
        )
        assert not first_replayed
        assert second_replayed
        assert second.plan_id == first.plan_id
        assert second.input_content_hash == first.input_content_hash
        assert repository.store_calls == 1

    @pytest.mark.asyncio
    async def test_infeasible_optimizer_result_persists_reason_not_events(
        self,
    ):
        # 100 m3 with zero excess cannot be met by a 3600 s minimum pulse at
        # 2 m3/s: any release overshoots, no release undershoots.
        ros = FakeRosGisClient([requirement_item(volume=100.0)])
        service, _, flow, repository = _service(ros=ros)
        request = _request(
            requirement_policies=[
                {
                    "requirement_id": REQ_ID,
                    "approved_excess_m3": 0.0,
                    "rotation_windows": [
                        {
                            "starts_at": "2026-07-20T06:00:00+00:00",
                            "ends_at": "2026-07-20T18:00:00+00:00",
                        }
                    ],
                }
            ]
        )
        record, replayed = await service.create_draft(
            None, request, "operator-1"
        )
        assert not replayed
        assert record.optimizer_status == "infeasible"
        assert record.events == ()
        assert record.prediction_status == "not_requested"
        assert record.prediction_run_id is None
        assert record.prediction_request_document_text is None
        assert record.prediction_response_document_text is None
        assert flow.prediction_requests == []
        optimizer_result = json.loads(record.optimizer_result_document_text)
        assert optimizer_result["status"] == "infeasible"
        assert optimizer_result["infeasible_reasons"]
        assert repository.store_calls == 1

    @pytest.mark.asyncio
    async def test_prediction_member_infeasibility_persists_valid_draft(self):
        flow = FakeControlFlowClient(
            snapshot_mirror(),
            prediction_members=[
                {"member": "lower", "status": "infeasible"},
                {"member": "nominal", "status": "completed"},
                {"member": "upper", "status": "completed"},
            ],
        )
        service, _, _, repository = _service(flow=flow)
        record, _ = await service.create_draft(None, _request(), "operator-1")
        assert record.optimizer_status == "feasible"
        assert record.prediction_status == "infeasible"
        assert record.prediction_run_id == "c" * 64
        assert repository.store_calls == 1

    @pytest.mark.asyncio
    async def test_prediction_lineage_conflict_aborts_without_draft(self):
        flow = FakeControlFlowClient(
            snapshot_mirror(),
            prediction_error=FlowLineageConflictError("pins drifted"),
        )
        service, _, _, repository = _service(flow=flow)
        with pytest.raises(FlowLineageConflictError):
            await service.create_draft(None, _request(), "operator-1")
        assert repository.store_calls == 0
        assert repository.by_input_hash == {}

    @pytest.mark.asyncio
    async def test_prediction_unavailable_aborts_without_draft(self):
        flow = FakeControlFlowClient(
            snapshot_mirror(),
            prediction_error=UpstreamUnavailableError("store down"),
        )
        service, _, _, repository = _service(flow=flow)
        with pytest.raises(UpstreamUnavailableError):
            await service.create_draft(None, _request(), "operator-1")
        assert repository.by_input_hash == {}

    @pytest.mark.asyncio
    async def test_prediction_contract_violation_aborts_without_draft(self):
        flow = FakeControlFlowClient(
            snapshot_mirror(),
            prediction_error=UpstreamContractViolation("malformed members"),
        )
        service, _, _, repository = _service(flow=flow)
        with pytest.raises(UpstreamContractViolation):
            await service.create_draft(None, _request(), "operator-1")
        assert repository.by_input_hash == {}

    @pytest.mark.asyncio
    async def test_missing_release_fails_closed(self):
        mirror = snapshot_mirror()
        mirror["response_model_release"] = None
        service, _, _, repository = _service(
            flow=FakeControlFlowClient(mirror)
        )
        with pytest.raises(ModelIncompleteError):
            await service.create_draft(None, _request(), "operator-1")
        assert repository.by_input_hash == {}

    @pytest.mark.asyncio
    async def test_unavailable_data_status_fails_closed(self):
        mirror = snapshot_mirror()
        mirror["data_status"] = "unavailable"
        service, _, _, _ = _service(flow=FakeControlFlowClient(mirror))
        with pytest.raises(ModelIncompleteError):
            await service.create_draft(None, _request(), "operator-1")

    @pytest.mark.asyncio
    async def test_same_input_different_output_replays_at_store(self):
        # Solver nondeterminism: same input, a divergent draft hash/plan_id must
        # replay the stored winner, not 409 (production compares input text only).
        service, _, _, repository = _service()
        record, _ = await service.create_draft(None, _request(), "operator-1")
        divergent = replace(
            record, plan_id=uuid4(), draft_content_hash="d" * 64
        )
        stored, replayed = await repository.store_draft_plan(None, divergent)
        assert replayed
        assert stored.plan_id == record.plan_id

    @pytest.mark.asyncio
    async def test_genuinely_different_input_same_hash_conflicts(self):
        # A (hypothetical) input-hash collision with different canonical input
        # must still fail closed rather than replay a different draft.
        service, _, _, repository = _service()
        record, _ = await service.create_draft(None, _request(), "operator-1")
        collision = replace(
            record,
            plan_id=uuid4(),
            canonical_input_document_text=(
                record.canonical_input_document_text + " "
            ),
        )
        with pytest.raises(PlanContentConflictError):
            await repository.store_draft_plan(None, collision)
