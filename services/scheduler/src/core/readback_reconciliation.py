"""PR 6.3b — pure readback-reconciliation predicate.

Under SHADOW the gate is never actuated, so comparing the observed readback to the intent
TARGET is vacuous (it would flag every plan the moment a window opens). The non-vacuous check
is DRIFT vs the plan's BASELINE — the level the plan believes the gate currently holds: a
divergence means a competing actor, a manual gate move, or a sensor fault has invalidated the
open-loop plan's starting assumptions, so the plan must be held.

I/O-free. Only a ``mismatch`` (both fresh, levels differ) is actionable; an ``unavailable``
reading (null level or non-``ok`` quality) is NEVER reconciled to a hold — acting on
unreliable data would spuriously pause a healthy plan.
"""

from __future__ import annotations

from typing import Optional

VERDICT_OK = "ok"
VERDICT_MISMATCH = "mismatch"
VERDICT_UNAVAILABLE = "unavailable"


def reconcile_gate_readback(
    observed_level: Optional[int],
    expected_level: int,
    observed_quality: str,
) -> str:
    """Return the reconciliation verdict for one gate.

    ``unavailable`` when the reading is missing (null level) or not fresh (quality != 'ok') —
    reconciliation is impossible, so never a mismatch. Otherwise ``ok`` iff the observed level
    equals the plan's expected baseline level, else ``mismatch``.
    """
    if observed_level is None or observed_quality != "ok":
        return VERDICT_UNAVAILABLE
    return VERDICT_OK if observed_level == expected_level else VERDICT_MISMATCH
