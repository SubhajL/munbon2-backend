"""Open-loop execution service (PR 5.2a recovery + PR 5.2b worker).

Orchestrates the pure open-loop logic (``core.open_loop_execution``) over the
repository. PR 5.2a: restart-safe authority recovery. PR 5.2b: the worker tick —
claim due intents, invalidate-and-release on a missed deadline, operator hold — all
LOCAL, with external dispatch STILL DISABLED (6.2 validates / 6.3 dispatches). The
worker only runs in ``shadow`` execution mode; ``disabled`` is dark and
``operator_approved`` is defined-but-refused (the execute path is 7.x).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from core.config import settings
from core.control_plan_lifecycle import (
    STATE_ACTIVATED,
    LifecycleHistoryCorruptError,
    derive_control_plan_state,
)
from core.logger import get_logger
from core.open_loop_execution import (
    EXECUTION_HELD,
    EXECUTION_RESUMED,
    INTENT_INVALIDATED,
    INTENT_MISSED,
    RecoveryReport,
    derive_recovery_actions,
    is_plan_held,
    plan_open_loop_actions,
)
from repositories.control_plan_repository import ExecutionEventRow, TransitionRecord

logger = get_logger(__name__)

EXECUTION_MODE_DISABLED = "disabled"
EXECUTION_MODE_SHADOW = "shadow"


class ExecutionModeNotEnabledError(Exception):
    """The configured execution mode does not permit local claiming (fail closed)."""


class HoldNotAllowedError(Exception):
    """Only a shadow_active plan can be placed on operator hold."""


class OpenLoopPlanNotFoundError(Exception):
    """No control plan exists for the given (plan_id, plan_version)."""


@dataclass(frozen=True)
class AdvanceResult:
    """The outcome of one worker tick: what it did and to which intents."""

    action: str  # disabled | not_active | invalidated | held | claimed
    claimed_intent_ids: tuple
    invalidated: bool


class OpenLoopExecutionService:
    def __init__(
        self,
        repository,
        *,
        clock=None,
        execution_mode: Optional[str] = None,
        premove_seconds: Optional[int] = None,
    ):
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._execution_mode = (
            execution_mode
            if execution_mode is not None
            else settings.control_execution_mode
        )
        # NOTE: control_authority_lease_hours is intentionally NOT consumed in 5.2b —
        # lease-expiry enforcement needs the renewal path that lands in 7.1, so the
        # worker classifies missed purely on the intent's own deadline.
        self._premove_seconds = (
            premove_seconds
            if premove_seconds is not None
            else settings.control_premove_validation_seconds
        )

    # --- PR 5.2a: restart-safe authority recovery ----------------------------

    async def recover_execution_state(self, session) -> RecoveryReport:
        """Rebuild the authority mutex from the append-only transition truth.

        Acquires the global recovery lock FIRST, then — within that one txn — scans
        the plausibly-active plans (+ current mutex holders), re-derives each state,
        and reconciles: delete terminal orphans, rebuild missing active rows. Because
        every mutex writer takes the same lock, the read-then-reconcile is atomic
        w.r.t. activation/release, so it can never resurrect or drop a row mid-flight.
        """
        await self._repository.acquire_recovery_lock(session)
        plans = await self._repository.load_recovery_plans(session)
        derivation = derive_recovery_actions(plans)
        if derivation.corrupt_keys:
            logger.warning(
                "authority recovery skipped {} plan(s) with un-derivable history: {}",
                len(derivation.corrupt_keys),
                sorted(str(key) for key in derivation.corrupt_keys),
            )
        if derivation.null_scope_keys:
            logger.warning(
                "authority recovery: {} active plan(s) carry a NULL-member scope "
                "(data fault activation would refuse): {}",
                len(derivation.null_scope_keys),
                sorted(str(key) for key in derivation.null_scope_keys),
            )
        report = await self._repository.reconcile_active_gate_authority(
            session,
            expected=derivation.expected_scopes,
            terminal_keys=derivation.terminal_keys,
        )
        logger.info(
            "authority recovery complete: scanned={} inserted={} deleted={} "
            "checked={}",
            len(plans),
            report.inserted,
            report.deleted,
            report.checked,
        )
        return report

    # --- PR 5.2b: open-loop worker (dispatch still disabled) -----------------

    def _require_worker_enabled(self) -> bool:
        """True if the worker should run (shadow mode); False if dark (disabled);
        raise for any non-dark, non-shadow mode (e.g. operator_approved is 7.x)."""
        if self._execution_mode == EXECUTION_MODE_DISABLED:
            return False
        if self._execution_mode != EXECUTION_MODE_SHADOW:
            raise ExecutionModeNotEnabledError(
                f"execution mode {self._execution_mode!r} is not enabled in 5.2 "
                "(only disabled/shadow)"
            )
        return True

    async def advance_open_loop_execution(
        self, session, plan_id, plan_version, *, worker_id: str = "scheduler", now=None
    ) -> AdvanceResult:
        """One worker tick for a plan. In shadow mode: if the earliest pending intent
        has passed its effective deadline (own deadline or authority lease), record a
        missed break — mark it ``missed``, ``invalidated`` every other pending intent,
        move the plan to lifecycle ``invalidated`` and release its authority mutex,
        all atomically. Otherwise (not held) claim the due intents. NEVER dispatches.
        """
        if not self._require_worker_enabled():
            # Dark in 'disabled' mode: no claiming and no invalidation runs. A plan
            # that reached shadow_active while disabled retains its authority until an
            # operator invalidates/supersedes — the worker is a 'shadow'-mode feature.
            return AdvanceResult("disabled", (), False)
        now = now or self._clock()
        context = await self._repository.load_open_loop_context(
            session, plan_id, plan_version
        )
        if not context.transitions:
            raise OpenLoopPlanNotFoundError(
                f"no control plan {plan_id} v{plan_version}"
            )
        state = derive_control_plan_state(context.transitions)
        if state != STATE_ACTIVATED:
            return AdvanceResult("not_active", (), False)
        if context.granted_at is None:
            # A shadow_active plan MUST hold its authority row (activation inserts it
            # atomically; 5.2a recovery rebuilds it). Its absence is a cache/state
            # inconsistency — fail closed (503, so a dispatcher alarms and recovery
            # runs) rather than 404, which would drop a still-live campaign.
            raise LifecycleHistoryCorruptError(
                f"shadow_active plan {plan_id} v{plan_version} has no authority row"
            )
        events_by_intent = _group_events_by_intent(context.events)
        actions = plan_open_loop_actions(
            context.outbox,
            events_by_intent,
            now=now,
            premove_seconds=self._premove_seconds,
        )
        if actions.missed_intent is not None:
            event_rows = [
                _intent_event(
                    actions.missed_intent.intent_id, INTENT_MISSED, worker_id, now
                )
            ] + [
                _intent_event(intent.intent_id, INTENT_INVALIDATED, worker_id, now)
                for intent in actions.invalidated_intents
            ]
            transition = TransitionRecord(
                transition_sequence=len(context.transitions) + 1,
                transition_type="invalidated",
                from_state=state,
                to_state="invalidated",
                actor_subject=worker_id,
                reason="open-loop missed deadline",
                transition_document_text=None,
                occurred_at=now,
            )
            await self._repository.record_missed_and_invalidate(
                session,
                plan_id,
                plan_version,
                event_rows=event_rows,
                transition=transition,
            )
            return AdvanceResult("invalidated", (), True)
        if is_plan_held(context.events):
            return AdvanceResult("held", (), False)
        # Delegate the claim to the public claim path (one claim implementation),
        # reusing the context/events already loaded this tick (no second DB round).
        claimed = await self.claim_due_intents(
            session, plan_id, plan_version, worker_id=worker_id, now=now,
            context=context,
        )
        return AdvanceResult("claimed", claimed, False)

    async def claim_due_intents(
        self,
        session,
        plan_id,
        plan_version,
        *,
        worker_id: str = "scheduler",
        now=None,
        context=None,
    ) -> tuple:
        """Claim the plan's due intents locally (shadow mode only), appending one
        ``claimed`` execution event each — idempotent, and it NEVER dispatches (no
        SCADA/execute call anywhere). A missed deadline is NOT claimed over: it must
        be handled by ``advance_open_loop_execution`` (invalidation). A held plan
        claims nothing. ``context`` may be a context ``advance`` already loaded this
        tick, avoiding a redundant reload."""
        if not self._require_worker_enabled():
            return ()
        now = now or self._clock()
        if context is None:
            context = await self._repository.load_open_loop_context(
                session, plan_id, plan_version
            )
        if not context.transitions:
            raise OpenLoopPlanNotFoundError(
                f"no control plan {plan_id} v{plan_version}"
            )
        if derive_control_plan_state(context.transitions) != STATE_ACTIVATED:
            return ()
        if context.granted_at is None or is_plan_held(context.events):
            return ()
        actions = plan_open_loop_actions(
            context.outbox,
            _group_events_by_intent(context.events),
            now=now,
            premove_seconds=self._premove_seconds,
        )
        if actions.missed_intent is not None or not actions.due_intents:
            return ()
        rows = [
            _intent_event(intent.intent_id, "claimed", worker_id, now)
            for intent in actions.due_intents
        ]
        # Report only the intents this call actually claimed (ON CONFLICT skips any
        # that a concurrent worker/invalidate already terminalized) — never merely
        # attempted, so a downstream dispatcher never double-acts.
        claimed = await self._repository.append_execution_events(
            session, plan_id, plan_version, rows, ignore_conflicts=True
        )
        return tuple(claimed)

    async def hold_control_plan(
        self,
        session,
        plan_id,
        plan_version,
        actor_subject: str,
        reason: Optional[str] = None,
        *,
        now=None,
    ) -> None:
        """Place a shadow_active plan on operator hold: append a plan-level ``held``
        execution event that pauses claiming. Hold is NOT a lifecycle transition — the
        plan stays ``shadow_active`` and KEEPS its authority mutex row (a lifecycle
        exit would wrongly release the scope). Reversible via ``resume_control_plan``.

        Deliberately NOT gated by ``control_execution_mode``: hold is an operator
        SAFETY brake, usable to pin a plan paused in any mode (a missed-deadline
        invalidation still overrides it — safety wins over a stale pause)."""
        await self._append_plan_event(
            session, plan_id, plan_version, EXECUTION_HELD, reason, now
        )

    async def resume_control_plan(
        self,
        session,
        plan_id,
        plan_version,
        actor_subject: str,
        reason: Optional[str] = None,
        *,
        now=None,
    ) -> None:
        """Lift an operator hold: append a plan-level ``resumed`` event so claiming can
        proceed again (``is_plan_held`` honors the latest hold/resume). Symmetric with
        ``hold_control_plan`` — without it, hold would be a one-way door."""
        await self._append_plan_event(
            session, plan_id, plan_version, EXECUTION_RESUMED, reason, now
        )

    async def _append_plan_event(
        self, session, plan_id, plan_version, event_type, reason, now
    ) -> None:
        now = now or self._clock()
        context = await self._repository.load_open_loop_context(
            session, plan_id, plan_version
        )
        if not context.transitions:
            raise OpenLoopPlanNotFoundError(
                f"no control plan {plan_id} v{plan_version}"
            )
        if derive_control_plan_state(context.transitions) != STATE_ACTIVATED:
            raise HoldNotAllowedError(
                "only a shadow_active plan can be held or resumed"
            )
        row = ExecutionEventRow(
            event_id=uuid4(),
            intent_id=None,
            event_type=event_type,
            worker_id=None,
            detail_document_text=reason,
            occurred_at=now,
        )
        await self._repository.append_execution_events(
            session, plan_id, plan_version, [row]
        )


def _group_events_by_intent(events) -> dict:
    grouped: dict = {}
    for event in events:
        grouped.setdefault(event.intent_id, []).append(event)
    return grouped


def _intent_event(intent_id, event_type: str, worker_id: str, now) -> ExecutionEventRow:
    return ExecutionEventRow(
        event_id=uuid4(),
        intent_id=intent_id,
        event_type=event_type,
        worker_id=worker_id,
        detail_document_text=None,
        occurred_at=now,
    )
