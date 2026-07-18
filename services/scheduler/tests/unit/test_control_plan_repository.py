"""Stored-draft integrity verification fails closed on any document drift."""

from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID

import pytest

from core.control_plan import (
    canonical_json_text,
    control_plan_draft_hash,
    control_plan_input_hash,
)
from repositories.control_plan_repository import (
    DraftPlanRecord,
    DraftStoreCorruptError,
    TransitionRecord,
    build_draft_hash_document,
    text_sha256,
    verify_stored_draft,
)


def _record():
    input_document = {
        "identity_version": 1,
        "request": {"zones": [1]},
        "snapshot_pins": {
            "model_snapshot_id": "a" * 64,
            "model_release_id": "release-2026-07",
            "model_release_content_hash": "b" * 64,
        },
    }
    input_text = canonical_json_text(input_document)
    optimizer_document = {"status": "infeasible", "infeasible_reasons": ["x"]}
    optimizer_text = canonical_json_text(optimizer_document)
    draft_hash = control_plan_draft_hash(
        build_draft_hash_document(input_text, optimizer_text, None, None)
    )
    return DraftPlanRecord(
        plan_id=UUID("00000000-0000-4000-8000-000000000001"),
        plan_version=1,
        identity_version=1,
        input_content_hash=control_plan_input_hash(input_document),
        draft_content_hash=draft_hash,
        lifecycle_state="draft",
        optimizer_status="infeasible",
        prediction_status="not_requested",
        requirement_run_id=UUID("00000000-0000-4000-8000-000000000002"),
        requirement_version=3,
        model_snapshot_id="a" * 64,
        model_release_id="release-2026-07",
        model_release_content_hash="b" * 64,
        prediction_run_id=None,
        prediction_member_summaries=None,
        horizon_start=datetime(2026, 7, 20, tzinfo=timezone.utc),
        horizon_end=datetime(2026, 7, 21, tzinfo=timezone.utc),
        model_step_seconds=3600,
        max_intermediate_trims=1,
        canonical_input_document_text=input_text,
        model_snapshot_document_text="{}",
        optimizer_result_document_text=optimizer_text,
        optimizer_result_sha256=text_sha256(optimizer_text),
        prediction_request_document_text=None,
        prediction_response_document_text=None,
        prediction_response_sha256=None,
        created_by_subject="operator-1",
        requirements=(),
        events=(),
        transitions=(
            TransitionRecord(
                transition_sequence=1,
                transition_type="draft_created",
                from_state=None,
                to_state="draft",
                actor_subject="operator-1",
                reason=None,
                transition_document_text=None,
            ),
        ),
    )


class TestVerifyStoredDraft:
    def test_untampered_record_verifies(self):
        verify_stored_draft(_record())

    def test_tampered_input_document_fails_closed(self):
        record = replace(
            _record(),
            canonical_input_document_text=canonical_json_text(
                {"identity_version": 1, "request": {"zones": [2]}}
            ),
        )
        with pytest.raises(DraftStoreCorruptError):
            verify_stored_draft(record)

    def test_non_json_input_document_fails_closed(self):
        record = replace(_record(), canonical_input_document_text="{broken")
        with pytest.raises(DraftStoreCorruptError):
            verify_stored_draft(record)

    def test_tampered_optimizer_document_fails_closed(self):
        record = replace(
            _record(),
            optimizer_result_document_text=canonical_json_text(
                {"status": "feasible"}
            ),
        )
        with pytest.raises(DraftStoreCorruptError):
            verify_stored_draft(record)

    def test_prediction_document_without_hash_fails_closed(self):
        record = replace(
            _record(), prediction_response_document_text='{"members":[]}'
        )
        with pytest.raises(DraftStoreCorruptError):
            verify_stored_draft(record)

    def test_tampered_draft_hash_fails_closed(self):
        record = replace(_record(), draft_content_hash="e" * 64)
        with pytest.raises(DraftStoreCorruptError):
            verify_stored_draft(record)

    def test_header_pin_edited_independently_fails_closed(self):
        # A header pin column changed without touching the hashed input document.
        record = replace(_record(), model_release_id="tampered-release")
        with pytest.raises(DraftStoreCorruptError):
            verify_stored_draft(record)
