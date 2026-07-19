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
