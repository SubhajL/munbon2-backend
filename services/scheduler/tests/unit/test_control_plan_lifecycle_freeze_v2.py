"""Freeze document v2 (PR 4.4a-1): authorization evidence lives OUTSIDE the
recomputed lineage.

``verify_shadow_approval_freeze`` recomputes the lineage from the immutable
rows and compares it canonically; authorization evidence is not derivable from
those rows, so it must be wrapped in a separate ``authorization_evidence`` key
and verify must compare only ``lineage_freeze``. These tests reuse the pure
``_Record`` fixture shape from the 4.3b lifecycle tests.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pytest

from core.control_plan_lifecycle import (
    ApprovalFreezeMismatchError,
    build_shadow_approval_document,
    build_shadow_approval_freeze,
    shadow_approval_document_text,
    shadow_approval_freeze_text,
    verify_shadow_approval_freeze,
)

HORIZON_END = datetime(2026, 7, 21, tzinfo=timezone.utc)


@dataclass
class _Requirement:
    requirement_id: str
    section_id: str = "SEC-1"
    gate_id: str = "G1"
    planning_disposition: str = "scheduled"
    path_reach_ids_document_text: str = '["R1","R2"]'
    required_volume_m3: float = 100.0
    approved_excess_m3: float = 20.0
    requirement_document_text: str = '{"requirement_id":"req-1"}'


@dataclass
class _LedgerEntry:
    requirement_id: str
    status: str = "predicted_fulfilled"
    checkpoint_reasons: tuple = ("horizon_end",)
    checkpoint_index: int = 1
    checkpoint_at: datetime = HORIZON_END
    prediction_run_id: str = "c" * 64
    prediction_response_sha256: str = "d" * 64


@dataclass
class _Record:
    optimizer_status: str = "feasible"
    prediction_status: str = "completed"
    prediction_run_id: Optional[str] = "c" * 64
    prediction_response_sha256: Optional[str] = "d" * 64
    horizon_end: datetime = HORIZON_END
    plan_id: str = "00000000-0000-4000-8000-000000000001"
    plan_version: int = 1
    input_content_hash: str = "a" * 64
    draft_content_hash: str = "b" * 64
    optimizer_result_sha256: str = "e" * 64
    requirement_run_id: str = "00000000-0000-4000-8000-000000000009"
    requirement_version: int = 3
    model_snapshot_id: str = "f" * 64
    model_release_id: str = "release-1"
    model_release_content_hash: str = "0" * 64
    requirements: list = field(
        default_factory=lambda: [_Requirement("req-1")]
    )
    ledger_entries: list = field(
        default_factory=lambda: [_LedgerEntry("req-1")]
    )


def _freeze(record):
    return build_shadow_approval_freeze(
        record, ledger_sha256="1" * 64, requirement_set_sha256="2" * 64
    )


def _evidence(mode="strict"):
    return {
        "authorization_policy_version": "control-plan-rbac-v1",
        "claim_policy_mode": mode,
        "subject": "user-1",
        "roles": ["supervisor"],
        "token_identity_sha256": "9" * 64,
        "request_id": "req-1",
        "evidence_refs": ["ticket-123"],
    }


class TestBuildDocument:
    def test_v2_document_wraps_lineage_and_evidence(self):
        record = _Record()
        lineage = _freeze(record)
        evidence = _evidence()
        document = build_shadow_approval_document(lineage, evidence)
        assert document == {
            "schema_version": 2,
            "lineage_freeze": lineage,
            "authorization_evidence": evidence,
        }
        # Evidence must NOT bleed into the hashed lineage.
        assert "authorization_evidence" not in document["lineage_freeze"]

    def test_verify_accepts_v2_document_against_record(self):
        record = _Record()
        document = build_shadow_approval_document(_freeze(record), _evidence())
        verify_shadow_approval_freeze(
            shadow_approval_document_text(document),
            record,
            ledger_sha256="1" * 64,
            requirement_set_sha256="2" * 64,
        )

    def test_verify_ignores_evidence_when_comparing_lineage(self):
        # Changing ONLY the authorization evidence must not break verification —
        # verify compares lineage, not evidence.
        record = _Record()
        doc_a = build_shadow_approval_document(_freeze(record), _evidence())
        doc_b = build_shadow_approval_document(
            _freeze(record), _evidence(mode="compat")
        )
        for document in (doc_a, doc_b):
            verify_shadow_approval_freeze(
                shadow_approval_document_text(document),
                record,
                ledger_sha256="1" * 64,
                requirement_set_sha256="2" * 64,
            )


class TestVerifyLegacyAndTamper:
    def test_verify_still_accepts_legacy_v1_freeze(self):
        record = _Record()
        bare = shadow_approval_freeze_text(_freeze(record))
        verify_shadow_approval_freeze(
            bare,
            record,
            ledger_sha256="1" * 64,
            requirement_set_sha256="2" * 64,
        )

    def test_verify_rejects_tampered_lineage_in_v2(self):
        record = _Record()
        lineage = _freeze(record)
        # Mutate a pinned hash inside the lineage after the fact.
        lineage["plan"]["draft_content_hash"] = "9" * 64
        tampered = build_shadow_approval_document(lineage, _evidence())
        with pytest.raises(ApprovalFreezeMismatchError):
            verify_shadow_approval_freeze(
                shadow_approval_document_text(tampered),
                record,
                ledger_sha256="1" * 64,
                requirement_set_sha256="2" * 64,
            )

    def test_verify_rejects_v2_when_record_drifts(self):
        record = _Record()
        document = build_shadow_approval_document(_freeze(record), _evidence())
        drifted = _Record(draft_content_hash="9" * 64)
        with pytest.raises(ApprovalFreezeMismatchError):
            verify_shadow_approval_freeze(
                shadow_approval_document_text(document),
                drifted,
                ledger_sha256="1" * 64,
                requirement_set_sha256="2" * 64,
            )

    def test_verify_rejects_non_json(self):
        with pytest.raises(ApprovalFreezeMismatchError):
            verify_shadow_approval_freeze(
                "{bad",
                _Record(),
                ledger_sha256="1" * 64,
                requirement_set_sha256="2" * 64,
            )
