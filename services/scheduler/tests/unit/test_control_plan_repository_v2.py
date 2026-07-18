"""v2 artifact-reference draft verification (PR 4.4b-2).

A v2 draft stores a bounded reference — engine pins + artifact metadata + coverage
/member summaries + ledger hash — with the full prediction response DISCARDED.
``verify_stored_draft`` must verify such a row WITHOUT the response (which is NULL),
fail closed on any drift, and the bounded read path must never select the response.
"""

import hashlib
import json
from dataclasses import replace
from functools import partial

import pytest
from sqlalchemy.dialects import postgresql

from algorithms.hydraulic_schedule_optimizer import (
    optimize_limited_adjustment_plan,
)
from core.control_plan import control_plan_draft_hash
from repositories.control_plan_projection_repository import build_summary_query
from repositories.control_plan_repository import (
    DraftStoreCorruptError,
    build_draft_hash_document,
    build_provenance_reference_document,
    provenance_reference_document_for_record,
    provenance_reference_sha256,
    verify_stored_draft,
)
from schemas.control_plan import ControlPlanListFilters, DraftControlPlanRequest
from services.control_plan_service import ControlPlanDraftService
from tests.control_plan_test_support import (
    FakeControlFlowClient,
    FakeRepository,
    FakeRosGisClient,
    draft_payload,
    requirement_item,
    snapshot_mirror,
)


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


class TestVerifyStoredDraftV2:
    @pytest.mark.asyncio
    async def test_v2_stored_draft_verifies_without_flow_network_call(self):
        # The record is self-contained: verification touches no flow client and
        # never reads a full response (there is none to read).
        record = await _v2_record()
        assert record.provenance_version == 2
        assert record.prediction_response_document_text is None
        verify_stored_draft(record)  # must not raise

    @pytest.mark.asyncio
    async def test_v2_rejects_a_restored_prediction_response_copy(self):
        record = await _v2_record()
        tampered = replace(
            record, prediction_response_document_text='{"members":[]}'
        )
        with pytest.raises(DraftStoreCorruptError, match="must not copy"):
            verify_stored_draft(tampered)

    @pytest.mark.asyncio
    async def test_v2_rejects_a_tampered_artifact_sha(self):
        record = await _v2_record()
        tampered = replace(record, artifact_sha256="0" * 64)
        with pytest.raises(DraftStoreCorruptError):
            verify_stored_draft(tampered)

    @pytest.mark.asyncio
    async def test_v2_rejects_a_tampered_engine_pin(self):
        # An engine pin edited independently of the snapshot is caught by the
        # engine-vs-snapshot cross-check (which runs before the draft-hash check):
        # the stored pin no longer equals the snapshot's embedded prediction_engine.
        record = await _v2_record()
        tampered = replace(record, engine_descriptor_content_hash="0" * 64)
        with pytest.raises(DraftStoreCorruptError, match="disagree"):
            verify_stored_draft(tampered)

    @pytest.mark.asyncio
    async def test_v2_rejects_a_tampered_coverage_summary(self):
        record = await _v2_record()
        tampered = replace(
            record,
            coverage_summary_document_text=(
                record.coverage_summary_document_text + " "
            ),
        )
        with pytest.raises(DraftStoreCorruptError, match="coverage summary"):
            verify_stored_draft(tampered)

    @pytest.mark.asyncio
    async def test_v2_rejects_a_tampered_ledger_hash(self):
        record = await _v2_record()
        tampered = replace(record, predicted_delivery_ledger_sha256="0" * 64)
        with pytest.raises(DraftStoreCorruptError, match="ledger hash"):
            verify_stored_draft(tampered)

    @pytest.mark.asyncio
    async def test_v2_rejects_a_missing_engine_column(self):
        record = await _v2_record()
        tampered = replace(record, engine_build_digest=None)
        with pytest.raises(DraftStoreCorruptError, match="missing columns"):
            verify_stored_draft(tampered)

    @pytest.mark.asyncio
    async def test_v2_rejects_engine_columns_that_disagree_with_snapshot(self):
        # The engine columns stay internally self-consistent (draft hash intact),
        # but the STORED model snapshot embeds a DIFFERENT prediction_engine — the
        # "engine-B pins recorded over an engine-A snapshot" corruption the draft
        # hash alone cannot catch. The snapshot cross-check must reject it.
        record = await _v2_record()
        snapshot = json.loads(record.model_snapshot_document_text)
        snapshot["prediction_engine"]["build_digest"] = "1" * 64
        tampered = replace(
            record, model_snapshot_document_text=json.dumps(snapshot)
        )
        with pytest.raises(DraftStoreCorruptError, match="disagree"):
            verify_stored_draft(tampered)

    @pytest.mark.asyncio
    async def test_v2_rejects_snapshot_without_embedded_prediction_engine(self):
        record = await _v2_record()
        snapshot = json.loads(record.model_snapshot_document_text)
        del snapshot["prediction_engine"]
        tampered = replace(
            record, model_snapshot_document_text=json.dumps(snapshot)
        )
        with pytest.raises(
            DraftStoreCorruptError, match="no embedded"
        ):
            verify_stored_draft(tampered)


class TestProvenanceVersionDispatch:
    @pytest.mark.asyncio
    async def test_unknown_provenance_version_is_rejected_not_treated_as_v1(self):
        # An unknown non-null provenance_version must fail closed, NEVER dispatch
        # to the v1 path (which would skip every v2 artifact-reference check).
        record = await _v2_record()
        tampered = replace(record, provenance_version=3)
        with pytest.raises(
            DraftStoreCorruptError, match="unknown provenance_version"
        ):
            verify_stored_draft(tampered)

    @pytest.mark.asyncio
    async def test_v2_requires_prediction_identity_version_exactly_two(self):
        # Present-but-wrong identity version (1, not 2) is rejected — a v2 row
        # pins Flow's identity-v2 contract exactly.
        record = await _v2_record()
        tampered = replace(record, prediction_identity_version=1)
        with pytest.raises(
            DraftStoreCorruptError, match="prediction_identity_version"
        ):
            verify_stored_draft(tampered)


class TestV2ReadsNeverLoadTheResponse:
    @pytest.mark.asyncio
    async def test_scheduler_never_selects_legacy_response_for_v2_reads(self):
        # A v2 row carries NO response bytes to leak ...
        record = await _v2_record()
        assert record.prediction_response_document_text is None
        assert record.prediction_response_sha256 is None
        # ... and the bounded list read never selects the response column.
        compiled = str(
            build_summary_query(ControlPlanListFilters(), None, 25).compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).lower()
        assert "prediction_response_document_text" not in compiled


# --- FIX 6: an INDEPENDENT oracle for the provenance reference ---------------
# The v2 integrity tests above use the production writer + verifier as mutual
# oracles (a field omitted from BOTH would stay green). These pin the canonical
# document shape and digest to values computed WITHOUT the production code, and
# prove every provenance input actually flows into the draft hash.

_ORACLE_INPUTS = dict(
    prediction_run_id="a" * 64,
    prediction_identity_version=2,
    engine_id="engine-x",
    engine_semantic_contract_version=1,
    engine_build_digest="b" * 64,
    engine_descriptor_content_hash="c" * 64,
    artifact_sha256="d" * 64,
    artifact_uncompressed_size_bytes=123,
    artifact_media_type="application/json",
    artifact_encoding="canonical-json+zlib",
    artifact_encoding_version=1,
    prediction_member_summaries_sha256="e" * 64,
    coverage_summary_sha256="f" * 64,
    predicted_delivery_ledger_sha256="0" * 64,
)

# The canonical text a correct builder MUST produce for _ORACLE_INPUTS — written
# out by hand (sorted keys, no spaces), independent of canonical_json_text.
_ORACLE_CANONICAL_TEXT = (
    '{"artifact":{"artifact_sha256":"' + "d" * 64 + '",'
    '"encoding":"canonical-json+zlib","encoding_version":1,'
    '"media_type":"application/json","uncompressed_size_bytes":123},'
    '"engine":{"build_digest":"' + "b" * 64 + '",'
    '"engine_descriptor_content_hash":"' + "c" * 64 + '",'
    '"engine_id":"engine-x","semantic_contract_version":1},'
    '"predicted_delivery_ledger_sha256":"' + "0" * 64 + '",'
    '"prediction_identity_version":2,'
    '"prediction_run_id":"' + "a" * 64 + '","provenance_version":2,'
    '"summaries":{"coverage_summary_sha256":"' + "f" * 64 + '",'
    '"prediction_member_summaries_sha256":"' + "e" * 64 + '"}}'
)
_ORACLE_PREFIX = "scheduler:control-plan-provenance:v2\n"
# Frozen digest precomputed offline; also reconstructed below from the hand text.
_ORACLE_DIGEST = (
    "92e4c3adebd11fb91da6784f0cf440068aa32e63019a39079f074afc3318a4ee"
)


class TestProvenanceReferenceOracle:
    def test_builder_matches_hardcoded_canonical_document(self):
        document = build_provenance_reference_document(**_ORACLE_INPUTS)
        assert document == {
            "provenance_version": 2,
            "prediction_run_id": "a" * 64,
            "prediction_identity_version": 2,
            "engine": {
                "engine_id": "engine-x",
                "semantic_contract_version": 1,
                "build_digest": "b" * 64,
                "engine_descriptor_content_hash": "c" * 64,
            },
            "artifact": {
                "artifact_sha256": "d" * 64,
                "uncompressed_size_bytes": 123,
                "media_type": "application/json",
                "encoding": "canonical-json+zlib",
                "encoding_version": 1,
            },
            "summaries": {
                "prediction_member_summaries_sha256": "e" * 64,
                "coverage_summary_sha256": "f" * 64,
            },
            "predicted_delivery_ledger_sha256": "0" * 64,
        }

    def test_reference_digest_matches_independent_oracle(self):
        document = build_provenance_reference_document(**_ORACLE_INPUTS)
        # Independent reconstruction: hand-built canonical text under the prefix.
        independent = hashlib.sha256(
            (_ORACLE_PREFIX + _ORACLE_CANONICAL_TEXT).encode("utf-8")
        ).hexdigest()
        assert independent == _ORACLE_DIGEST
        assert provenance_reference_sha256(document) == _ORACLE_DIGEST


def _draft_hash_of(record) -> str:
    """The v2 draft hash exactly as production binds it: over the input,
    optimizer, prediction request, and the record's provenance-reference sha."""
    return control_plan_draft_hash(
        build_draft_hash_document(
            record.canonical_input_document_text,
            record.optimizer_result_document_text,
            record.prediction_request_document_text,
            provenance_reference_sha256(
                provenance_reference_document_for_record(record)
            ),
        )
    )


class TestProvenanceInputsBindIntoDraftHash:
    @pytest.mark.asyncio
    async def test_each_provenance_field_changes_the_draft_hash(self):
        # If any of these were omitted from the reference document, mutating it
        # would leave the draft hash unchanged and this test would fail — which is
        # exactly the omission the mutual writer/verifier oracle cannot catch.
        record = await _v2_record()
        baseline = _draft_hash_of(record)
        assert baseline == record.draft_content_hash
        assert _draft_hash_of(replace(record, artifact_sha256="1" * 64)) != baseline
        assert (
            _draft_hash_of(replace(record, engine_build_digest="1" * 64))
            != baseline
        )
        assert (
            _draft_hash_of(
                replace(
                    record,
                    prediction_member_summaries=(
                        record.prediction_member_summaries + " "
                    ),
                )
            )
            != baseline
        )
        assert (
            _draft_hash_of(
                replace(record, predicted_delivery_ledger_sha256="1" * 64)
            )
            != baseline
        )

    @pytest.mark.asyncio
    async def test_v1_and_v2_drafts_of_same_plan_cannot_share_a_draft_hash(self):
        # v1 binds the raw response sha; v2 binds the provenance-reference sha over
        # the SAME plan's input/optimizer/prediction-request. The two bindings are
        # distinct values, so the two drafts can never collide on the draft hash.
        record = await _v2_record()
        v2_hash = _draft_hash_of(record)
        # In the fake, artifact_sha256 IS the sha of the canonical response bytes,
        # i.e. exactly the response sha a v1 draft of this plan would bind.
        v1_hash = control_plan_draft_hash(
            build_draft_hash_document(
                record.canonical_input_document_text,
                record.optimizer_result_document_text,
                record.prediction_request_document_text,
                record.artifact_sha256,
            )
        )
        assert v1_hash != v2_hash
