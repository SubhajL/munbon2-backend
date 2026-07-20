"""PR 6.3b — shadow readback reconciliation.

Config-gated (``control_readback_reconciliation_mode``): ``off`` reads nothing and holds
nothing (dark, byte-identical to no-6.3b); ``observe`` records an observation per (plan, gate)
but NEVER holds; ``enforce`` additionally HOLDS the plan when a fresh readback drifts from the
plan's expected BASELINE level. The hold is 5.2's plan-level ``held`` event (reversible via
resume; keeps the authority mutex — a hold is not a lifecycle exit). Nothing here actuates.

The observed readings and the expected baseline levels are INPUTS (injected in tests, supplied
from the SCADA readback client + a baseline source in real ops) so the reconcile decision is
actuation-independent and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Optional
from uuid import uuid4

from core.config import settings
from core.logger import get_logger
from core.open_loop_execution import is_plan_held
from core.readback_reconciliation import VERDICT_MISMATCH, reconcile_gate_readback
from repositories.control_plan_repository import ReadbackObservationRow
from services.open_loop_execution_service import HoldNotAllowedError

logger = get_logger(__name__)

MODE_OFF = "off"
MODE_OBSERVE = "observe"
MODE_ENFORCE = "enforce"

_HOLD_ACTOR = "readback-reconciler"


@dataclass(frozen=True)
class ReconcileReport:
    mode: str
    mismatched_gate_ids: tuple
    held: bool


class ReadbackReconciliationService:
    def __init__(self, repository, open_loop_service, *, mode: Optional[str] = None, clock=None):
        self._repository = repository
        self._open_loop = open_loop_service
        self._mode = (
            mode if mode is not None else settings.control_readback_reconciliation_mode
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def reconcile_plan_readback(
        self,
        session,
        plan_id,
        plan_version,
        *,
        readings: Mapping[str, Mapping],
        expected_levels: Mapping[str, int],
        now=None,
    ) -> ReconcileReport:
        """Reconcile each baseline gate's observed readback against its expected level. ``off`` →
        dark (no record, no hold). Records one observation per gate; in ``enforce`` a fresh drift
        (``mismatch``) holds the plan — but only if it is not ALREADY held, so a sustained drift
        does not append a fresh ``held`` event every tick (the plan stays held until resume/clear).
        ``unavailable`` readings never hold.

        CONTRACT: ``expected_level`` (the baseline) MUST be in the SAME namespace as the readback
        ``observed_level`` — i.e. the discrete gate-level the device reads back (1..4 for the Waste
        Way gate), NOT the machine ``target_level`` (0..65535) or a position in metres. A future
        baseline source that feeds the wrong namespace would produce 100% spurious mismatches."""
        if self._mode == MODE_OFF:
            return ReconcileReport(MODE_OFF, (), False)
        now = now or self._clock()
        mismatched: list = []
        for gate_id, expected in expected_levels.items():
            reading = readings.get(gate_id) or {}
            observed_level = reading.get("observed_level")
            quality = reading.get("quality", "unavailable")
            verdict = reconcile_gate_readback(observed_level, expected, quality)
            await self._repository.record_readback_observation(
                session,
                ReadbackObservationRow(
                    observation_id=uuid4(),
                    plan_id=plan_id,
                    plan_version=plan_version,
                    canonical_gate_id=gate_id,
                    observed_level=observed_level,
                    expected_level=expected,
                    quality=quality,
                    verdict=verdict,
                    reconciliation_mode=self._mode,
                    observed_at=now,
                ),
            )
            if verdict == VERDICT_MISMATCH:
                mismatched.append(gate_id)

        held = False
        if self._mode == MODE_ENFORCE and mismatched:
            # Only hold if the plan is not ALREADY held — otherwise a sustained drift would
            # append a fresh `held` event every tick (unbounded), and re-hold a plan an operator
            # just resumed. A resume with the drift still present will re-hold on the next tick.
            context = await self._repository.load_open_loop_context(
                session, plan_id, plan_version
            )
            if not is_plan_held(context.events):
                logger.warning(
                    "readback drift on plan {} v{} gates {} — holding the plan",
                    plan_id,
                    plan_version,
                    sorted(mismatched),
                )
                try:
                    await self._open_loop.hold_control_plan(
                        session,
                        plan_id,
                        plan_version,
                        _HOLD_ACTOR,
                        reason=f"readback drift on gates {sorted(mismatched)}",
                        now=now,
                    )
                    held = True
                except HoldNotAllowedError:
                    # The plan left shadow_active (e.g. concurrently invalidated) between the
                    # context load and the hold — it is ALREADY stopped, so not holding is NOT
                    # fail-open. (NB: the observation was recorded before the hold; on a transient
                    # hold failure the observation stands and the next tick re-attempts the hold —
                    # benign because dispatch is validation-only, nothing actuates.)
                    logger.warning(
                        "plan {} v{} is no longer holdable (already terminal) — not held",
                        plan_id,
                        plan_version,
                    )
        return ReconcileReport(self._mode, tuple(mismatched), held)
