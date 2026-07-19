"""Pure review-lifecycle: state derivation, edges, coverage, approval freeze."""

from dataclasses import dataclass, field
from typing import Optional

import pytest

from core.control_plan_lifecycle import (
    ApprovalCoverageError,
    ApprovalFreezeMismatchError,
    IllegalTransitionError,
    LifecycleHistoryCorruptError,
    build_shadow_approval_freeze,
    control_plan_requirement_set_sha256,
    derive_control_plan_state,
    next_state,
    shadow_approval_freeze_text,
    validate_shadow_approval_coverage,
    verify_shadow_approval_freeze,
)


@dataclass
class _Transition:
    transition_sequence: int
    transition_type: str
    from_state: Optional[str]
    to_state: str


def _history(*edges):
    result = []
    for index, (transition_type, from_state, to_state) in enumerate(
        edges, start=1
    ):
        result.append(
            _Transition(index, transition_type, from_state, to_state)
        )
    return result


DRAFT = ("draft_created", None, "draft")
REVIEW = ("review_requested", "draft", "under_review")
APPROVE = ("shadow_approved", "under_review", "approved_for_shadow")


class TestDeriveState:
    def test_draft_only_history_is_draft(self):
        assert derive_control_plan_state(_history(DRAFT)) == "draft"

    def test_full_approval_chain(self):
        assert (
            derive_control_plan_state(_history(DRAFT, REVIEW, APPROVE))
            == "approved_for_shadow"
        )

    def test_unordered_input_is_sorted(self):
        transitions = list(reversed(_history(DRAFT, REVIEW)))
        assert derive_control_plan_state(transitions) == "under_review"

    def test_empty_history_is_corrupt(self):
        with pytest.raises(LifecycleHistoryCorruptError):
            derive_control_plan_state([])

    def test_sequence_gap_is_corrupt(self):
        transitions = _history(DRAFT, REVIEW)
        transitions[1].transition_sequence = 3
        with pytest.raises(LifecycleHistoryCorruptError):
            derive_control_plan_state(transitions)

    def test_from_state_drift_is_corrupt(self):
        transitions = _history(DRAFT, REVIEW)
        transitions[1].from_state = "under_review"
        with pytest.raises(LifecycleHistoryCorruptError):
            derive_control_plan_state(transitions)

    def test_undeclared_edge_is_corrupt(self):
        transitions = _history(
            DRAFT, ("shadow_approved", "draft", "approved_for_shadow")
        )
        with pytest.raises(LifecycleHistoryCorruptError):
            derive_control_plan_state(transitions)

    def test_missing_initial_creation_is_corrupt(self):
        transitions = [_Transition(1, "review_requested", "draft", "under_review")]
        with pytest.raises(LifecycleHistoryCorruptError):
            derive_control_plan_state(transitions)


class TestNextState:
    def test_legal_edges(self):
        assert next_state("draft", "review_requested") == "under_review"
        assert next_state("under_review", "shadow_approved") == (
            "approved_for_shadow"
        )
        assert next_state("approved_for_shadow", "superseded") == "superseded"
        assert next_state("draft", "cancelled") == "cancelled"
        assert next_state("approved_for_shadow", "invalidated") == "invalidated"

    def test_approve_requires_review_first(self):
        with pytest.raises(IllegalTransitionError):
            next_state("draft", "shadow_approved")

    def test_terminal_state_rejects_action(self):
        for terminal in ("cancelled", "superseded", "invalidated"):
            with pytest.raises(IllegalTransitionError):
                next_state(terminal, "review_requested")

    def test_supersede_requires_approved(self):
        with pytest.raises(IllegalTransitionError):
            next_state("under_review", "superseded")


ACTIVATE = ("shadow_activated", "approved_for_shadow", "shadow_active")


class TestActivationEdges:
    def test_activation_chain_derives_to_shadow_active(self):
        assert (
            derive_control_plan_state(_history(DRAFT, REVIEW, APPROVE, ACTIVATE))
            == "shadow_active"
        )

    def test_shadow_active_is_not_terminal(self):
        from core.control_plan_lifecycle import STATE_ACTIVATED, TERMINAL_STATES

        assert STATE_ACTIVATED not in TERMINAL_STATES

    def test_activate_is_legal_only_from_approved(self):
        assert next_state("approved_for_shadow", "shadow_activated") == "shadow_active"
        for illegal in ("draft", "under_review", "shadow_active"):
            with pytest.raises(IllegalTransitionError):
                next_state(illegal, "shadow_activated")

    def test_active_plan_can_be_emergency_invalidated(self):
        assert next_state("shadow_active", "invalidated") == "invalidated"
        assert (
            derive_control_plan_state(
                _history(
                    DRAFT,
                    REVIEW,
                    APPROVE,
                    ACTIVATE,
                    ("invalidated", "shadow_active", "invalidated"),
                )
            )
            == "invalidated"
        )

    def test_active_plan_cannot_be_cancelled_or_reviewed(self):
        for illegal_action in ("cancelled", "review_requested", "shadow_activated"):
            with pytest.raises(IllegalTransitionError):
                next_state("shadow_active", illegal_action)


class TestRequirementSetHash:
    def test_order_independent(self):
        pairs = [("r1", '{"v":1}'), ("r2", '{"v":2}')]
        assert control_plan_requirement_set_sha256(pairs) == (
            control_plan_requirement_set_sha256(list(reversed(pairs)))
        )

    def test_document_change_changes_hash(self):
        assert control_plan_requirement_set_sha256(
            [("r1", '{"v":1}')]
        ) != control_plan_requirement_set_sha256([("r1", '{"v":2}')])

    def test_is_sha256_hex(self):
        digest = control_plan_requirement_set_sha256([("r1", "{}")])
        assert len(digest) == 64


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


from datetime import datetime, timezone

HORIZON_END = datetime(2026, 7, 21, tzinfo=timezone.utc)


def _valid_prediction_response():
    import json

    return json.dumps(
        {
            "members": [
                {"member": m, "status": "completed"}
                for m in ("lower", "nominal", "upper")
            ]
        }
    )


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
    prediction_response_document_text: Optional[str] = field(
        default_factory=_valid_prediction_response
    )
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


class TestCoverageGate:
    def test_complete_coverage_passes(self):
        validate_shadow_approval_coverage(_Record())

    def test_infeasible_optimizer_rejected(self):
        with pytest.raises(ApprovalCoverageError):
            validate_shadow_approval_coverage(
                _Record(optimizer_status="infeasible")
            )

    def test_prediction_not_completed_rejected(self):
        with pytest.raises(ApprovalCoverageError):
            validate_shadow_approval_coverage(
                _Record(prediction_status="infeasible")
            )

    def test_manual_review_ledger_row_rejected(self):
        with pytest.raises(ApprovalCoverageError):
            validate_shadow_approval_coverage(
                _Record(
                    ledger_entries=[
                        _LedgerEntry("req-1", status="manual_review")
                    ]
                )
            )

    def test_predicted_excess_risk_is_still_approvable(self):
        validate_shadow_approval_coverage(
            _Record(
                ledger_entries=[
                    _LedgerEntry("req-1", status="predicted_excess_risk")
                ]
            )
        )

    def test_ledger_coverage_mismatch_rejected(self):
        with pytest.raises(ApprovalCoverageError):
            validate_shadow_approval_coverage(
                _Record(ledger_entries=[_LedgerEntry("other")])
            )

    def test_missing_terminal_row_rejected(self):
        with pytest.raises(ApprovalCoverageError):
            validate_shadow_approval_coverage(
                _Record(
                    ledger_entries=[
                        _LedgerEntry("req-1", checkpoint_reasons=("first_sample",))
                    ]
                )
            )

    def test_no_scheduled_requirement_rejected(self):
        with pytest.raises(ApprovalCoverageError):
            validate_shadow_approval_coverage(_Record(requirements=[]))

    def test_empty_path_rejected(self):
        with pytest.raises(ApprovalCoverageError):
            validate_shadow_approval_coverage(
                _Record(
                    requirements=[
                        _Requirement("req-1", path_reach_ids_document_text="[]")
                    ]
                )
            )

    def test_non_list_path_rejected(self):
        with pytest.raises(ApprovalCoverageError):
            validate_shadow_approval_coverage(
                _Record(
                    requirements=[
                        _Requirement("req-1", path_reach_ids_document_text="{}")
                    ]
                )
            )

    def test_terminal_shortfall_status_rejected(self):
        # A feasible completed prediction can still project a shortfall at the
        # horizon (predicted_in_progress terminal row) — not fully covered.
        with pytest.raises(ApprovalCoverageError):
            validate_shadow_approval_coverage(
                _Record(
                    ledger_entries=[
                        _LedgerEntry("req-1", status="predicted_in_progress")
                    ]
                )
            )

    def test_terminal_row_at_wrong_time_rejected(self):
        with pytest.raises(ApprovalCoverageError):
            validate_shadow_approval_coverage(
                _Record(
                    ledger_entries=[
                        _LedgerEntry(
                            "req-1",
                            checkpoint_at=datetime(
                                2026, 7, 20, 12, tzinfo=timezone.utc
                            ),
                        )
                    ]
                )
            )

    def test_ledger_prediction_lineage_mismatch_rejected(self):
        # A self-consistent ledger projected over a DIFFERENT prediction than
        # the plan header must not be certifiable.
        with pytest.raises(ApprovalCoverageError):
            validate_shadow_approval_coverage(
                _Record(
                    ledger_entries=[
                        _LedgerEntry("req-1", prediction_run_id="9" * 64)
                    ]
                )
            )

    def test_malformed_prediction_response_rejected(self):
        with pytest.raises(ApprovalCoverageError):
            validate_shadow_approval_coverage(
                _Record(prediction_response_document_text="{}")
            )

    def test_shadow_approval_rejects_incomplete_path_coverage(self):
        # The roadmap gate: every way a draft can be "incomplete" fails closed.
        incomplete_records = [
            _Record(optimizer_status="infeasible"),
            _Record(prediction_status="infeasible"),
            _Record(prediction_response_document_text="{}"),
            _Record(
                requirements=[
                    _Requirement("req-1", path_reach_ids_document_text="[]")
                ]
            ),
            _Record(
                ledger_entries=[
                    _LedgerEntry("req-1", status="manual_review")
                ]
            ),
            _Record(
                ledger_entries=[
                    _LedgerEntry("req-1", status="predicted_in_progress")
                ]
            ),
            _Record(ledger_entries=[_LedgerEntry("other")]),
        ]
        for record in incomplete_records:
            with pytest.raises(ApprovalCoverageError):
                validate_shadow_approval_coverage(record)


class TestApprovalFreeze:
    def test_shadow_approval_freezes_all_lineage(self):
        # Assert the COMPLETE freeze document so dropping any pinned field fails.
        record = _Record()
        freeze = build_shadow_approval_freeze(
            record, ledger_sha256="1" * 64, requirement_set_sha256="2" * 64
        )
        assert freeze == {
            "schema_version": 1,
            "approval_mode": "shadow",
            "machine_authority_granted": False,
            "plan": {
                "plan_id": record.plan_id,
                "plan_version": 1,
                "input_content_hash": "a" * 64,
                "draft_content_hash": "b" * 64,
                "optimizer_result_sha256": "e" * 64,
            },
            "requirements": {
                "requirement_run_id": str(record.requirement_run_id),
                "requirement_version": 3,
                "requirement_set_sha256": "2" * 64,
            },
            "model": {
                "model_snapshot_id": "f" * 64,
                "model_release_id": "release-1",
                "model_release_content_hash": "0" * 64,
            },
            "prediction": {
                "prediction_run_id": "c" * 64,
                "prediction_response_sha256": "d" * 64,
            },
            "ledger": {
                "ledger_sha256": "1" * 64,
                "entry_count": 1,
                "scheduled_requirement_count": 1,
            },
        }

    def test_verify_accepts_matching_document(self):
        record = _Record()
        freeze = build_shadow_approval_freeze(
            record, ledger_sha256="1" * 64, requirement_set_sha256="2" * 64
        )
        verify_shadow_approval_freeze(
            shadow_approval_freeze_text(freeze),
            record,
            ledger_sha256="1" * 64,
            requirement_set_sha256="2" * 64,
        )

    def test_verify_rejects_pin_drift(self):
        record = _Record()
        freeze = build_shadow_approval_freeze(
            record, ledger_sha256="1" * 64, requirement_set_sha256="2" * 64
        )
        text = shadow_approval_freeze_text(freeze)
        drifted = _Record(draft_content_hash="9" * 64)
        with pytest.raises(ApprovalFreezeMismatchError):
            verify_shadow_approval_freeze(
                text,
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
