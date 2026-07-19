"""Open-loop execution service (PR 5.2a): restart-safe authority recovery.

Thin orchestration over the pure recovery logic (``core.open_loop_execution``) and
the repository's advisory-locked reconcile. The worker surface (claim due intents,
missed-deadline invalidation, hold) arrives in PR 5.2b; this PR only makes the
``control_active_gate_authority`` mutex a provably-derived, restart-rebuildable
view of the append-only transition truth.
"""

from __future__ import annotations

from core.logger import get_logger
from core.open_loop_execution import RecoveryReport, derive_recovery_actions

logger = get_logger(__name__)


class OpenLoopExecutionService:
    def __init__(self, repository):
        self._repository = repository

    async def recover_execution_state(self, session) -> RecoveryReport:
        """Rebuild the authority mutex from the append-only transition truth.

        Acquires the global recovery lock FIRST, then — within that one txn — scans
        the plausibly-active plans (+ current mutex holders), re-derives each state,
        and reconciles: delete terminal orphans, rebuild missing active rows. Because
        every mutex writer takes the same lock, the read-then-reconcile is atomic
        w.r.t. activation/release, so it can never resurrect or drop a row mid-flight.
        A no-op in the normal ACID case — the mutex is written transactionally with
        each lifecycle transition — so this both self-heals and proves the cache is
        derived, never authority.
        """
        await self._repository.acquire_recovery_lock(session)
        plans = await self._repository.load_recovery_plans(session)
        derivation = derive_recovery_actions(plans)
        # Surface data faults the reconcile deliberately leaves untouched, so a
        # corrupt/degenerate plan is never silently invisible on the boot path.
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
