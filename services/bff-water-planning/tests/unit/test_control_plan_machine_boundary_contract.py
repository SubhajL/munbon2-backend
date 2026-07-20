"""BFF side of the shared v1 machine-boundary contract (PR 6.5b).

The scheduler validates the SAME fixtures against its own OUT models; if either side drifts from
`contracts/control-plans/v1/`, that side's fixture test fails. A shared fixture that BOTH strict
models accept — with the exact same field set — is the drift trip-wire the hand-copied mirror
otherwise lacks.
"""

import json
from pathlib import Path

from schemas.control_plan import (
    ControlPlanExecutionState,
    ControlPlanIntentTimeline,
    ControlPlanReadbackObservations,
    HoldEventProjection,
    IntentTimelineEntryProjection,
    ReadbackObservationProjection,
)

_CONTRACT_DIR = Path(__file__).resolve().parents[4] / "contracts" / "control-plans" / "v1"


def _load(name: str) -> dict:
    return json.loads((_CONTRACT_DIR / name).read_text(encoding="utf-8"))


def test_bff_accepts_the_shared_intent_timeline_fixture():
    timeline = ControlPlanIntentTimeline.model_validate(_load("intent-timeline.example.json"))
    entry = timeline.intents[0]
    assert entry.execution_state == "claimed"
    assert entry.receipt_status == "validation_rejected"
    assert entry.reason_code == "freshness_failed"


def test_bff_accepts_the_shared_readback_observations_fixture():
    obs = ControlPlanReadbackObservations.model_validate(
        _load("readback-observations.example.json")
    )
    assert obs.observations[0].verdict == "mismatch"
    assert obs.observations[0].reconciliation_mode == "enforce"


def test_bff_accepts_the_shared_execution_state_fixture():
    state = ControlPlanExecutionState.model_validate(_load("execution-state.example.json"))
    assert state.is_held is True
    assert state.hold_events[0].event_type == "held"


def test_bff_mirrors_and_fixtures_agree_on_the_exact_item_field_set():
    # The mirror's item fields must EXACTLY match the fixture's item keys — a field the
    # scheduler adds (and puts in the fixture) then fails this on the BFF side at PR time.
    assert set(IntentTimelineEntryProjection.model_fields) == set(
        _load("intent-timeline.example.json")["intents"][0]
    )
    assert set(ReadbackObservationProjection.model_fields) == set(
        _load("readback-observations.example.json")["observations"][0]
    )
    assert set(HoldEventProjection.model_fields) == set(
        _load("execution-state.example.json")["hold_events"][0]
    )
