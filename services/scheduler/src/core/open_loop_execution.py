"""Pure open-loop execution helpers (PR 5.2a).

Restart-safe authority. ``control_active_gate_authority`` (PR 4.3c) is a MUTABLE
materialized cache; its 0007 comment defers "restart-safe re-derivation" to 5.2.
The append-only ``control_state_transitions`` history is the audit truth, and the
scheduled requirement scope is immutable, so the exact set of authority rows the
cache SHOULD hold is a PURE function of those two: one row per (section, gate)
scope of every plan whose derived lifecycle state is ``shadow_active``. A restart
can therefore rebuild the cache and drop orphaned rows with no volatile in-memory
state — which is what makes the mutex provably a derived view, not authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Sequence

from core.control_plan_lifecycle import (
    STATE_ACTIVATED,
    TERMINAL_STATES,
    TRANSITION_SHADOW_ACTIVATED,
    LifecycleError,
    derive_control_plan_state,
)

# Re-export the ONE definition of the authority-granting transition type so the
# repository/service reference it without a second hardcoded copy.
ACTIVATION_TRANSITION_TYPE = TRANSITION_SHADOW_ACTIVATED


class RecoveryScopeConflictError(Exception):
    """Two distinct ``shadow_active`` plans derive to the SAME (section, gate).

    The one-per-scope mutex PK is supposed to make this impossible; observing it in
    the derived truth means the invariant was broken in history. Recovery cannot
    safely pick a winner (that would grant one plan authority over a contested
    gate), so it fails closed — leaving the durable mutex untouched for a human.
    """


@dataclass(frozen=True)
class RecoveryPlan:
    """The minimal per-plan slice recovery needs.

    ``transitions`` is the FULL append-only history (any object exposing
    ``transition_sequence``/``transition_type``/``from_state``/``to_state`` — ORM
    rows or test doubles) so the lifecycle state is re-derived, not trusted;
    ``scope_pairs`` are the plan's scheduled ``(section_id, gate_id)`` pairs (the
    same source an activation took its mutex rows from).
    """

    plan_id: object
    plan_version: int
    transitions: Sequence
    scope_pairs: frozenset


@dataclass(frozen=True)
class ExpectedScope:
    """One authority-mutex row the cache SHOULD hold for an active plan."""

    section_id: str
    gate_id: str
    plan_id: object
    plan_version: int
    activation_transition_sequence: int


@dataclass(frozen=True)
class RecoveryDerivation:
    """The partitioned outcome of re-deriving every candidate plan's state.

    ``expected_scopes`` — rows the mutex must hold (active plans); ``terminal_keys``
    — once-active plans now terminal, whose surviving mutex rows are orphans to
    delete; ``corrupt_keys`` — plans whose history could not be derived (isolated,
    not fatal: their durable mutex rows are left untouched); ``null_scope_keys`` —
    active plans carrying a NULL-member scope (a data fault activation would have
    refused), surfaced for logging.
    """

    expected_scopes: frozenset
    terminal_keys: frozenset
    corrupt_keys: frozenset
    null_scope_keys: frozenset


@dataclass(frozen=True)
class RecoveryReport:
    """The outcome of one reconcile: rows re-inserted, orphans deleted, rows seen."""

    inserted: int
    deleted: int
    checked: int


def _activation_sequence(transitions: Sequence) -> int:
    """The sequence of the plan's ``shadow_activated`` transition.

    A plan derived to be ``shadow_active`` has exactly one such transition (the
    state machine admits activation only once); its absence is corruption.
    """
    for transition in transitions:
        if transition.transition_type == ACTIVATION_TRANSITION_TYPE:
            return transition.transition_sequence
    raise ValueError("a shadow_active plan has no shadow_activated transition")


def derive_recovery_actions(plans: Sequence[RecoveryPlan]) -> RecoveryDerivation:
    """Partition candidate plans into the authority actions recovery must take.

    ONE ``derive_control_plan_state`` per plan (no double walk). A plan whose
    history is un-derivable is ISOLATED into ``corrupt_keys`` and skipped so a
    single corrupt plan never aborts the whole fleet's recovery. Two distinct
    active plans on the same scope raise ``RecoveryScopeConflictError`` (fail
    closed — a broken one-per-scope invariant must not be silently resolved). A
    NULL-member scope on an active plan is skipped (it can never be in the NOT-NULL
    mutex) but recorded so the caller can log the data fault.
    """
    expected: dict = {}
    terminal: set = set()
    corrupt: set = set()
    null_scope: set = set()
    owner_by_scope: dict = {}
    for plan in plans:
        key = (plan.plan_id, plan.plan_version)
        try:
            state = derive_control_plan_state(plan.transitions)
        except LifecycleError:
            corrupt.add(key)
            continue
        if state in TERMINAL_STATES:
            terminal.add(key)
        elif state == STATE_ACTIVATED:
            activation_sequence = _activation_sequence(plan.transitions)
            for section_id, gate_id in plan.scope_pairs:
                if section_id is None or gate_id is None:
                    null_scope.add(key)
                    continue
                scope = (section_id, gate_id)
                prior_owner = owner_by_scope.get(scope)
                if prior_owner is not None and prior_owner != key:
                    raise RecoveryScopeConflictError(
                        f"scope {scope} is claimed by both {prior_owner} and {key}"
                    )
                owner_by_scope[scope] = key
                expected[scope] = ExpectedScope(
                    section_id=section_id,
                    gate_id=gate_id,
                    plan_id=plan.plan_id,
                    plan_version=plan.plan_version,
                    activation_transition_sequence=activation_sequence,
                )
    return RecoveryDerivation(
        expected_scopes=frozenset(expected.values()),
        terminal_keys=frozenset(terminal),
        corrupt_keys=frozenset(corrupt),
        null_scope_keys=frozenset(null_scope),
    )


# --- PR 5.2b: per-intent open-loop execution state machine -------------------

INTENT_PENDING = "pending"
INTENT_CLAIMED = "claimed"
INTENT_MISSED = "missed"
INTENT_INVALIDATED = "invalidated"
INTENT_EXECUTION_STATES = frozenset(
    {INTENT_PENDING, INTENT_CLAIMED, INTENT_MISSED, INTENT_INVALIDATED}
)
# The per-intent execution event types (plan-level held/resumed are NOT per-intent).
_TERMINAL_INTENT_EVENTS = frozenset(
    {INTENT_CLAIMED, INTENT_MISSED, INTENT_INVALIDATED}
)

EXECUTION_HELD = "held"
EXECUTION_RESUMED = "resumed"

# Timing classification (pure due/missed decision).
TIMING_PENDING = "pending"
TIMING_DUE = "due"
TIMING_MISSED = "missed"


class IntentExecutionCorruptError(Exception):
    """An intent carries contradictory terminal execution events (fail closed)."""


def derive_intent_execution_state(events: Sequence) -> str:
    """Fold an intent's append-only execution events into its current state.

    In PR 5.2b an intent takes at most ONE terminal event (claimed | missed |
    invalidated) — the DB ``UNIQUE(intent_id, event_type)`` backstops it — so more
    than one DISTINCT terminal is corruption and fails closed.
    """
    terminals = {
        event.event_type
        for event in events
        if event.event_type in _TERMINAL_INTENT_EVENTS
    }
    if not terminals:
        return INTENT_PENDING
    if len(terminals) > 1:
        raise IntentExecutionCorruptError(
            f"intent has contradictory execution events: {sorted(terminals)}"
        )
    return next(iter(terminals))


def _require_aware(**instants) -> None:
    for label, value in instants.items():
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{label} must be timezone-aware")


def classify_intent_timing(
    *,
    not_before,
    deadline,
    now,
    premove_seconds: int,
) -> str:
    """Pure due/missed classification for one intent. All datetimes MUST be
    timezone-aware (a naive value is a bug → fail closed).

    Past the intent's own ``deadline`` the command is stale → ``missed``. Within the
    pre-move window before ``not_before`` it is ``due`` (claimable); earlier it is
    ``pending``.

    NOTE: 5.2b deliberately does NOT cap the deadline by the authority lease
    (``granted_at + lease``). The 24h lease is a RENEWABLE checkpoint (renewal is
    7.1); enforcing it here as a hard cap would self-invalidate every valid campaign
    longer than the lease. Lease-expiry enforcement lands with its renewal in 7.1.
    """
    _require_aware(not_before=not_before, deadline=deadline, now=now)
    if now >= deadline:
        return TIMING_MISSED
    if now >= not_before - timedelta(seconds=premove_seconds):
        return TIMING_DUE
    return TIMING_PENDING


def is_plan_held(events: Sequence) -> bool:
    """Whether the plan is currently on operator hold: its latest plan-level
    hold/resume event (``intent_id`` NULL) is a ``held``. Ordered by occurrence,
    then insertion, so a resume after a hold clears it."""
    plan_events = [
        event
        for event in events
        if event.event_type in (EXECUTION_HELD, EXECUTION_RESUMED)
    ]
    if not plan_events:
        return False
    latest = max(plan_events, key=lambda e: (e.occurred_at, e.created_at))
    return latest.event_type == EXECUTION_HELD


@dataclass(frozen=True)
class OpenLoopActions:
    """The actions one worker tick must take for a plan, decided purely.

    ``missed_intent`` is the earliest pending intent whose deadline has passed; when
    set, the open-loop sequence is broken, so ``invalidated_intents`` are every OTHER
    still-pending intent and no claim happens. When ``missed_intent`` is None,
    ``due_intents`` are the pending intents in their pre-move window ready to claim.
    """

    missed_intent: object
    invalidated_intents: tuple
    due_intents: tuple


def plan_open_loop_actions(
    outbox: Sequence,
    events_by_intent: dict,
    *,
    now,
    premove_seconds: int,
) -> OpenLoopActions:
    """Decide a worker tick over a plan's ordered outbox (pure).

    A missed deadline invalidates the WHOLE remaining campaign (a gap in an open-loop
    sequence can never be safely resumed): the earliest pending+missed intent is the
    ``missed_intent`` and every other pending intent is invalidated. Absent a miss,
    pending intents inside their pre-move window are due to claim. ``outbox`` MUST be
    ordered by ``event_sequence``.
    """
    missed_intent = None
    pending = []
    due = []
    for intent in outbox:
        events = events_by_intent.get(intent.intent_id, [])
        if derive_intent_execution_state(events) != INTENT_PENDING:
            continue
        pending.append(intent)
        timing = classify_intent_timing(
            not_before=intent.not_before,
            deadline=intent.deadline,
            now=now,
            premove_seconds=premove_seconds,
        )
        if timing == TIMING_MISSED and missed_intent is None:
            missed_intent = intent
        elif timing == TIMING_DUE:
            due.append(intent)
    if missed_intent is None:
        return OpenLoopActions(None, (), tuple(due))
    invalidated = tuple(
        intent for intent in pending if intent.intent_id != missed_intent.intent_id
    )
    return OpenLoopActions(missed_intent, invalidated, ())
