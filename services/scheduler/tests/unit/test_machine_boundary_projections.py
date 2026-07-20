"""Unit tests for the PR 6.5a bounded machine-boundary read projections (pure build fns)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from repositories.control_plan_projection_repository import (
    ProjectionCorruptError,
    build_execution_state,
    build_intent_timeline,
    build_readback_observations,
)

NOW = datetime(2026, 7, 20, 3, 0, 0, tzinfo=timezone.utc)
PLAN = uuid4()


def _outbox(intent_id, *, gate="M(0,0;1,0)", kind="open", seq=1):
    return SimpleNamespace(
        intent_id=intent_id,
        canonical_gate_id=gate,
        event_kind=kind,
        event_sequence=seq,
        not_before=NOW,
        deadline=NOW + timedelta(hours=1),
    )


def _event(intent_id, event_type, occurred_at=NOW):
    return SimpleNamespace(intent_id=intent_id, event_type=event_type, occurred_at=occurred_at)


def _receipt(intent_id, status, reason_code=None):
    return SimpleNamespace(
        intent_id=intent_id,
        status=status,
        reason_code=reason_code,
        validated_at=NOW,
        dispatched_at=NOW,
        receipt_content_sha256="a" * 64,
    )


class TestBuildIntentTimeline:
    def test_pending_intent_has_no_state_claim_or_receipt(self):
        intent = uuid4()
        result = build_intent_timeline(PLAN, 1, [_outbox(intent)], [], [])
        entry = result.intents[0]
        assert entry.execution_state == "pending"
        assert entry.claimed_at is None
        assert entry.receipt_status is None
        assert entry.receipt_content_sha256 is None

    def test_claimed_with_accepted_receipt_folds_the_full_arc(self):
        intent = uuid4()
        result = build_intent_timeline(
            PLAN,
            1,
            [_outbox(intent)],
            [_event(intent, "claimed", NOW)],
            [_receipt(intent, "validation_accepted")],
        )
        entry = result.intents[0]
        assert entry.execution_state == "claimed"
        assert entry.claimed_at == NOW
        assert entry.receipt_status == "validation_accepted"
        assert entry.receipt_content_sha256 == "a" * 64

    def test_claimed_without_receipt_yet(self):
        intent = uuid4()
        result = build_intent_timeline(
            PLAN, 1, [_outbox(intent)], [_event(intent, "claimed")], []
        )
        entry = result.intents[0]
        assert entry.execution_state == "claimed"
        assert entry.receipt_status is None

    def test_preserves_outbox_event_sequence_order(self):
        a, b = uuid4(), uuid4()
        result = build_intent_timeline(
            PLAN, 1, [_outbox(a, seq=1), _outbox(b, seq=2)], [], []
        )
        assert [e.intent_id for e in result.intents] == [a, b]

    @pytest.mark.parametrize("terminal", ["missed", "invalidated"])
    def test_missed_and_invalidated_states_project(self, terminal):
        intent = uuid4()
        result = build_intent_timeline(
            PLAN, 1, [_outbox(intent)], [_event(intent, terminal)], []
        )
        entry = result.intents[0]
        assert entry.execution_state == terminal
        assert entry.claimed_at is None  # never claimed
        assert entry.receipt_status is None

    def test_rejected_receipt_surfaces_the_reason_code(self):
        intent = uuid4()
        result = build_intent_timeline(
            PLAN,
            1,
            [_outbox(intent)],
            [_event(intent, "claimed")],
            [_receipt(intent, "validation_rejected", reason_code="freshness_failed")],
        )
        entry = result.intents[0]
        assert entry.receipt_status == "validation_rejected"
        assert entry.reason_code == "freshness_failed"

    def test_contradictory_execution_events_fail_closed(self):
        intent = uuid4()
        with pytest.raises(ProjectionCorruptError):
            build_intent_timeline(
                PLAN,
                1,
                [_outbox(intent)],
                [_event(intent, "claimed"), _event(intent, "invalidated")],
                [],
            )

    def test_orphan_receipt_without_an_outbox_row_fails_closed(self):
        # A receipt whose intent has NO outbox row would otherwise be silently dropped.
        outbox_intent, orphan = uuid4(), uuid4()
        with pytest.raises(ProjectionCorruptError):
            build_intent_timeline(
                PLAN,
                1,
                [_outbox(outbox_intent)],
                [],
                [_receipt(orphan, "validation_accepted")],
            )

    def test_receipt_on_a_non_claimed_intent_fails_closed(self):
        # A receipt always follows a claim; a receipt on a pending intent is corruption.
        intent = uuid4()
        with pytest.raises(ProjectionCorruptError):
            build_intent_timeline(
                PLAN, 1, [_outbox(intent)], [], [_receipt(intent, "validation_accepted")]
            )


class TestBuildReadbackObservations:
    def test_projects_each_observation_verbatim(self):
        rows = [
            SimpleNamespace(
                canonical_gate_id="M(0,0;1,0)",
                observed_level=None,
                expected_level=3,
                quality="unavailable",
                verdict="unavailable",
                reconciliation_mode="observe",
                observed_at=NOW,
            ),
            SimpleNamespace(
                canonical_gate_id="M(0,0;1,0)",
                observed_level=2,
                expected_level=3,
                quality="ok",
                verdict="mismatch",
                reconciliation_mode="enforce",
                observed_at=NOW + timedelta(minutes=1),
            ),
        ]
        result = build_readback_observations(PLAN, 1, rows)
        assert [o.verdict for o in result.observations] == ["unavailable", "mismatch"]
        assert result.observations[0].observed_level is None  # explicit, not masked
        assert result.observations[1].reconciliation_mode == "enforce"


class TestBuildExecutionState:
    def test_no_events_is_not_held(self):
        result = build_execution_state(PLAN, 1, [])
        assert result.is_held is False
        assert result.hold_events == []

    def test_latest_held_wins(self):
        rows = [
            SimpleNamespace(event_type="held", worker_id="readback-reconciler", occurred_at=NOW, created_at=NOW),
        ]
        assert build_execution_state(PLAN, 1, rows).is_held is True

    def test_resume_after_hold_is_not_held(self):
        rows = [
            SimpleNamespace(event_type="held", worker_id="w", occurred_at=NOW, created_at=NOW),
            SimpleNamespace(
                event_type="resumed", worker_id="op", occurred_at=NOW + timedelta(minutes=5), created_at=NOW
            ),
        ]
        result = build_execution_state(PLAN, 1, rows)
        assert result.is_held is False
        assert [e.event_type for e in result.hold_events] == ["held", "resumed"]

    def test_hold_after_resume_is_held(self):
        rows = [
            SimpleNamespace(event_type="resumed", worker_id="op", occurred_at=NOW, created_at=NOW),
            SimpleNamespace(
                event_type="held", worker_id="w", occurred_at=NOW + timedelta(minutes=5), created_at=NOW
            ),
        ]
        assert build_execution_state(PLAN, 1, rows).is_held is True
