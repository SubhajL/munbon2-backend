"""Unit tests for the pure open-loop recovery derivation (PR 5.2a).

Proves the mutex is a DERIVED view of the append-only transition truth: one pass
partitions candidate plans into the authority rows that SHOULD exist (active plans),
the terminal orphan-holders to drop, isolated corrupt plans, and NULL-scope data
faults — with no database.
"""

from uuid import uuid4

import pytest

from core.open_loop_execution import (
    ExpectedScope,
    RecoveryPlan,
    RecoveryScopeConflictError,
    derive_recovery_actions,
)


class _Transition:
    """A minimal transition double exposing exactly the attributes
    ``derive_control_plan_state`` reads."""

    def __init__(self, sequence, transition_type, from_state, to_state):
        self.transition_sequence = sequence
        self.transition_type = transition_type
        self.from_state = from_state
        self.to_state = to_state


_CHAIN = [
    ("draft_created", None, "draft"),
    ("review_requested", "draft", "under_review"),
    ("shadow_approved", "under_review", "approved_for_shadow"),
    ("shadow_activated", "approved_for_shadow", "shadow_active"),
]


def _history(final_state: str):
    """A valid contiguous transition history whose last to_state is ``final_state``.

    ``invalidated``/``superseded`` extend the active chain by their active-exit edge
    so the terminal cases are reached through real declared edges.
    """
    edges = list(_CHAIN)
    if final_state == "invalidated":
        edges.append(("invalidated", "shadow_active", "invalidated"))
    elif final_state == "superseded":
        edges.append(("superseded", "shadow_active", "superseded"))
    else:
        edges = edges[: [e[2] for e in _CHAIN].index(final_state) + 1]
    return [
        _Transition(index, ttype, frm, to)
        for index, (ttype, frm, to) in enumerate(edges, start=1)
    ]


def _plan(plan_id, version, final_state, scope_pairs):
    return RecoveryPlan(
        plan_id=plan_id,
        plan_version=version,
        transitions=_history(final_state),
        scope_pairs=frozenset(scope_pairs),
    )


def test_active_plan_yields_expected_scopes_with_activation_sequence():
    active_id = uuid4()
    active = _plan(active_id, 1, "shadow_active", {("sec-1", "G1"), ("sec-2", "G2")})

    result = derive_recovery_actions([active])

    # Exactly the two scopes, each pinned to the activation transition (seq 4).
    assert result.expected_scopes == frozenset(
        {
            ExpectedScope("sec-1", "G1", active_id, 1, 4),
            ExpectedScope("sec-2", "G2", active_id, 1, 4),
        }
    )
    assert result.terminal_keys == frozenset()
    assert result.corrupt_keys == frozenset()
    assert result.null_scope_keys == frozenset()


def test_terminal_and_preactive_plans_are_partitioned():
    invalidated_id, draft_id = uuid4(), uuid4()
    invalidated = _plan(invalidated_id, 3, "invalidated", {("sec-1", "G1")})
    draft = _plan(draft_id, 1, "draft", {("sec-2", "G2")})

    result = derive_recovery_actions([invalidated, draft])

    assert result.expected_scopes == frozenset()
    # The once-active-now-terminal plan is an orphan-holder candidate; a plan that
    # never activated is neither expected nor terminal (it holds no mutex row).
    assert result.terminal_keys == frozenset({(invalidated_id, 3)})


def test_null_scope_member_is_recorded_not_silently_dropped():
    active_id = uuid4()
    active = _plan(active_id, 1, "shadow_active", {("sec-1", "G1"), ("sec-1", None)})

    result = derive_recovery_actions([active])

    # The NULL member can never be in the NOT-NULL mutex, so it is skipped — but the
    # plan is recorded so the caller can log the data fault (not silently dropped).
    assert result.expected_scopes == frozenset(
        {ExpectedScope("sec-1", "G1", active_id, 1, 4)}
    )
    assert result.null_scope_keys == frozenset({(active_id, 1)})


def test_corrupt_history_is_isolated_not_fatal():
    corrupt_id, active_id = uuid4(), uuid4()
    # A history not beginning with draft_created is corruption.
    corrupt = RecoveryPlan(
        plan_id=corrupt_id,
        plan_version=1,
        transitions=[
            _Transition(1, "shadow_approved", "under_review", "approved_for_shadow")
        ],
        scope_pairs=frozenset({("sec-9", "G9")}),
    )
    active = _plan(active_id, 1, "shadow_active", {("sec-1", "G1")})

    result = derive_recovery_actions([corrupt, active])

    # The corrupt plan is isolated, NOT fatal: the active plan is still recovered.
    assert result.corrupt_keys == frozenset({(corrupt_id, 1)})
    assert result.expected_scopes == frozenset(
        {ExpectedScope("sec-1", "G1", active_id, 1, 4)}
    )


def test_two_active_plans_on_same_scope_fail_closed():
    # The one-per-scope PK should make this impossible; observing it means the
    # invariant was broken in history — recovery must fail closed, not pick a winner.
    plan_a = _plan(uuid4(), 1, "shadow_active", {("sec-1", "G1")})
    plan_b = _plan(uuid4(), 1, "shadow_active", {("sec-1", "G1")})

    with pytest.raises(RecoveryScopeConflictError):
        derive_recovery_actions([plan_a, plan_b])


def test_single_plan_holding_many_scopes_is_not_a_conflict():
    # Same plan owning multiple scopes must not trip the cross-plan conflict guard.
    plan_id = uuid4()
    plan = _plan(plan_id, 1, "shadow_active", {("sec-1", "G1"), ("sec-2", "G2")})

    result = derive_recovery_actions([plan])

    assert {s.gate_id for s in result.expected_scopes} == {"G1", "G2"}


# --- PR 5.2b: intent execution state machine + timing ------------------------

from datetime import datetime, timedelta, timezone  # noqa: E402

from core.open_loop_execution import (  # noqa: E402
    IntentExecutionCorruptError,
    TIMING_DUE,
    TIMING_MISSED,
    TIMING_PENDING,
    classify_intent_timing,
    derive_intent_execution_state,
    is_plan_held,
)

_T0 = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)


class _Event:
    def __init__(self, event_type, occurred_at=_T0, created_at=_T0):
        self.event_type = event_type
        self.occurred_at = occurred_at
        self.created_at = created_at


def test_derive_intent_state_pending_when_no_terminal_event():
    assert derive_intent_execution_state([]) == "pending"


@pytest.mark.parametrize("terminal", ["claimed", "missed", "invalidated"])
def test_derive_intent_state_reflects_single_terminal_event(terminal):
    assert derive_intent_execution_state([_Event(terminal)]) == terminal


def test_derive_intent_state_contradictory_terminals_fail_closed():
    with pytest.raises(IntentExecutionCorruptError):
        derive_intent_execution_state([_Event("claimed"), _Event("invalidated")])


def _timing(now, *, not_before, deadline, premove=300):
    return classify_intent_timing(
        not_before=not_before,
        deadline=deadline,
        now=now,
        premove_seconds=premove,
    )


def test_classify_timing_pending_before_premove_window():
    not_before = _T0 + timedelta(hours=2)
    # 10 min before the 5-min pre-move window opens -> still pending.
    now = not_before - timedelta(seconds=600)
    assert _timing(now, not_before=not_before, deadline=_T0 + timedelta(hours=3)) == (
        TIMING_PENDING
    )


def test_classify_timing_due_within_premove_window():
    not_before = _T0 + timedelta(hours=2)
    now = not_before - timedelta(seconds=120)  # inside the 300s pre-move window
    assert _timing(now, not_before=not_before, deadline=_T0 + timedelta(hours=3)) == (
        TIMING_DUE
    )


def test_classify_timing_missed_past_deadline():
    deadline = _T0 + timedelta(hours=3)
    now = deadline + timedelta(seconds=1)
    assert _timing(
        now, not_before=_T0 + timedelta(hours=2), deadline=deadline
    ) == TIMING_MISSED


def test_classify_timing_naive_datetime_fails_closed():
    naive_now = datetime(2026, 7, 19, 12, 30)  # no tzinfo
    with pytest.raises(ValueError):
        _timing(
            naive_now,
            not_before=_T0 + timedelta(hours=2),
            deadline=_T0 + timedelta(hours=3),
        )


def test_is_plan_held_latest_hold_resume_event_wins():
    held = _Event("held", occurred_at=_T0, created_at=_T0)
    resumed = _Event("resumed", occurred_at=_T0 + timedelta(minutes=5),
                     created_at=_T0 + timedelta(minutes=5))
    assert is_plan_held([held]) is True
    assert is_plan_held([held, resumed]) is False
    assert is_plan_held([]) is False


from core.open_loop_execution import plan_open_loop_actions  # noqa: E402


class _Intent:
    def __init__(self, intent_id, not_before, deadline):
        self.intent_id = intent_id
        self.not_before = not_before
        self.deadline = deadline


def test_plan_actions_claims_due_intents_when_no_miss():
    now = _T0 + timedelta(hours=1)
    horizon = _T0 + timedelta(days=6)
    a = _Intent("a", not_before=now - timedelta(seconds=60), deadline=horizon)  # due
    b = _Intent("b", not_before=now + timedelta(hours=5), deadline=horizon)  # pending
    actions = plan_open_loop_actions(
        [a, b], {}, now=now, premove_seconds=300
    )
    assert actions.missed_intent is None
    assert [i.intent_id for i in actions.due_intents] == ["a"]


def test_plan_actions_missed_deadline_invalidates_all_remaining_pending():
    now = _T0 + timedelta(hours=25)
    past = now - timedelta(minutes=1)  # deadline already passed -> missed
    a = _Intent("a", not_before=_T0 + timedelta(hours=1), deadline=past)
    b = _Intent("b", not_before=_T0 + timedelta(hours=2), deadline=past)
    c = _Intent("c", not_before=_T0 + timedelta(hours=3), deadline=past)
    actions = plan_open_loop_actions(
        [a, b, c], {}, now=now, premove_seconds=300
    )
    assert actions.missed_intent.intent_id == "a"           # earliest pending
    assert {i.intent_id for i in actions.invalidated_intents} == {"b", "c"}
    assert actions.due_intents == ()                        # no claiming on a miss


def test_plan_actions_skips_already_claimed_intents():
    now = _T0 + timedelta(hours=1)
    horizon = _T0 + timedelta(days=6)
    a = _Intent("a", not_before=now - timedelta(seconds=60), deadline=horizon)
    b = _Intent("b", not_before=now - timedelta(seconds=60), deadline=horizon)
    # a is already claimed -> only b is due.
    actions = plan_open_loop_actions(
        [a, b], {"a": [_Event("claimed")]},
        now=now, premove_seconds=300
    )
    assert [i.intent_id for i in actions.due_intents] == ["b"]
