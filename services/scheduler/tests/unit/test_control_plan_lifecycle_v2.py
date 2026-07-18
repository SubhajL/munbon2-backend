"""v2 approval: coverage + engine/artifact/ledger freeze (PR 4.4b-2).

A v2 (artifact-reference) draft proves shadow-approval coverage from the bounded
member/coverage summaries + ledger WITHOUT the full trajectory, and freezes the
engine descriptor + artifact identity + ledger hash into a schema-3 lineage
(still wrapped in the 4.4a-1 document v2 {schema_version, lineage_freeze,
authorization_evidence}).
"""

from dataclasses import replace
from functools import partial

import pytest

from algorithms.hydraulic_schedule_optimizer import (
    optimize_limited_adjustment_plan,
)
from core.control_plan_lifecycle import (
    ApprovalCoverageError,
    ApprovalFreezeMismatchError,
    build_shadow_approval_document,
    build_shadow_approval_freeze,
    control_plan_requirement_set_sha256,
    shadow_approval_document_text,
    validate_shadow_approval_coverage,
    verify_shadow_approval_freeze,
)
from core.predicted_delivery_ledger import predicted_delivery_ledger_sha256
from schemas.control_plan import DraftControlPlanRequest
from tests.control_plan_test_support import (
    FakeControlFlowClient,
    FakeRepository,
    FakeRosGisClient,
    draft_payload,
    requirement_item,
    snapshot_mirror,
)
from services.control_plan_service import ControlPlanDraftService


async def _run_blocking(func, *args, **kwargs):
    return func(*args, **kwargs)


async def _v2_record():
    service = ControlPlanDraftService(
        ros_client=FakeRosGisClient([requirement_item()]),
        flow_client=FakeControlFlowClient(snapshot_mirror()),
        repository=FakeRepository(),
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
    record, _ = await service.create_draft(
        None, DraftControlPlanRequest.model_validate(draft_payload()), "operator-1"
    )
    return record


def _freeze_inputs(record):
    return {
        "ledger_sha256": predicted_delivery_ledger_sha256(record.ledger_entries),
        "requirement_set_sha256": control_plan_requirement_set_sha256(
            [
                (str(r.requirement_id), r.requirement_document_text)
                for r in record.requirements
            ]
        ),
    }


class TestV2Coverage:
    @pytest.mark.asyncio
    async def test_v2_coverage_passes_from_bounded_summaries(self):
        record = await _v2_record()
        # No exception: coverage is proven from the member/coverage summaries and
        # the ledger, never the (absent) full response.
        assert record.prediction_response_document_text is None
        validate_shadow_approval_coverage(record)

    @pytest.mark.asyncio
    async def test_mismatched_coverage_summary_blocks_approval(self):
        record = await _v2_record()
        tampered = replace(record, coverage_summary_sha256="0" * 64)
        with pytest.raises(ApprovalCoverageError):
            validate_shadow_approval_coverage(tampered)

    @pytest.mark.asyncio
    async def test_mismatched_ledger_hash_blocks_approval(self):
        record = await _v2_record()
        tampered = replace(record, predicted_delivery_ledger_sha256="0" * 64)
        with pytest.raises(ApprovalCoverageError, match="ledger"):
            validate_shadow_approval_coverage(tampered)

    @pytest.mark.asyncio
    async def test_incomplete_member_summary_blocks_approval(self):
        record = await _v2_record()
        # Force a member summary to a non-completed status.
        broken = record.prediction_member_summaries.replace(
            "completed", "infeasible", 1
        )
        tampered = replace(record, prediction_member_summaries=broken)
        with pytest.raises(ApprovalCoverageError):
            validate_shadow_approval_coverage(tampered)


class TestV2Freeze:
    @pytest.mark.asyncio
    async def test_v2_approval_freezes_engine_artifact_and_ledger_identity(self):
        record = await _v2_record()
        inputs = _freeze_inputs(record)
        freeze = build_shadow_approval_freeze(record, **inputs)
        assert freeze["schema_version"] == 3
        prediction = freeze["prediction"]
        assert prediction["engine_descriptor_content_hash"] == (
            record.engine_descriptor_content_hash
        )
        assert prediction["engine_build_digest"] == record.engine_build_digest
        assert prediction["prediction_identity_version"] == (
            record.prediction_identity_version
        )
        assert prediction["artifact_sha256"] == record.artifact_sha256
        assert prediction["artifact_uncompressed_size_bytes"] == (
            record.artifact_uncompressed_size_bytes
        )
        assert prediction["coverage_summary_sha256"] == (
            record.coverage_summary_sha256
        )
        assert freeze["ledger"]["predicted_delivery_ledger_sha256"] == (
            record.predicted_delivery_ledger_sha256
        )
        # The v3 freeze carries no full-response sha (the reference replaces it).
        assert prediction.get("prediction_response_sha256") is None

    @pytest.mark.asyncio
    async def test_v2_freeze_wraps_and_verifies_against_the_record(self):
        record = await _v2_record()
        inputs = _freeze_inputs(record)
        document = build_shadow_approval_document(
            build_shadow_approval_freeze(record, **inputs),
            {"claim_policy_mode": "strict"},
        )
        # Recomputing the v3 lineage from the immutable record matches exactly.
        verify_shadow_approval_freeze(
            shadow_approval_document_text(document), record, **inputs
        )

    @pytest.mark.asyncio
    async def test_v2_verify_rejects_a_drifted_engine_pin(self):
        record = await _v2_record()
        inputs = _freeze_inputs(record)
        document = build_shadow_approval_document(
            build_shadow_approval_freeze(record, **inputs),
            {"claim_policy_mode": "strict"},
        )
        drifted = replace(record, engine_build_digest="0" * 64)
        with pytest.raises(ApprovalFreezeMismatchError):
            verify_shadow_approval_freeze(
                shadow_approval_document_text(document), drifted, **inputs
            )

    @pytest.mark.asyncio
    async def test_v3_freeze_covers_member_summaries_and_artifact_encoding(self):
        # The v3 freeze must pin the FULL summary/artifact identity: the member
        # summaries hash and the artifact encoding + encoding version.
        record = await _v2_record()
        inputs = _freeze_inputs(record)
        freeze = build_shadow_approval_freeze(record, **inputs)
        prediction = freeze["prediction"]
        import hashlib

        assert prediction["prediction_member_summaries_sha256"] == (
            hashlib.sha256(
                record.prediction_member_summaries.encode("utf-8")
            ).hexdigest()
        )
        assert prediction["artifact_encoding"] == record.artifact_encoding
        assert prediction["artifact_encoding_version"] == (
            record.artifact_encoding_version
        )

    @pytest.mark.asyncio
    async def test_v2_verify_rejects_drifted_member_summaries(self):
        record = await _v2_record()
        inputs = _freeze_inputs(record)
        document = build_shadow_approval_document(
            build_shadow_approval_freeze(record, **inputs),
            {"claim_policy_mode": "strict"},
        )
        # A member summary edited independently of the frozen hash no longer
        # matches — the freeze now covers prediction_member_summaries_sha256.
        drifted = replace(
            record,
            prediction_member_summaries=record.prediction_member_summaries.replace(
                "completed", "infeasible", 1
            ),
        )
        with pytest.raises(ApprovalFreezeMismatchError):
            verify_shadow_approval_freeze(
                shadow_approval_document_text(document), drifted, **inputs
            )

    @pytest.mark.asyncio
    async def test_v2_verify_rejects_drifted_artifact_encoding(self):
        record = await _v2_record()
        inputs = _freeze_inputs(record)
        document = build_shadow_approval_document(
            build_shadow_approval_freeze(record, **inputs),
            {"claim_policy_mode": "strict"},
        )
        drifted = replace(record, artifact_encoding="raw-json")
        with pytest.raises(ApprovalFreezeMismatchError):
            verify_shadow_approval_freeze(
                shadow_approval_document_text(document), drifted, **inputs
            )

    @pytest.mark.asyncio
    async def test_v2_verify_rejects_drifted_artifact_encoding_version(self):
        record = await _v2_record()
        inputs = _freeze_inputs(record)
        document = build_shadow_approval_document(
            build_shadow_approval_freeze(record, **inputs),
            {"claim_policy_mode": "strict"},
        )
        drifted = replace(record, artifact_encoding_version=99)
        with pytest.raises(ApprovalFreezeMismatchError):
            verify_shadow_approval_freeze(
                shadow_approval_document_text(document), drifted, **inputs
            )
