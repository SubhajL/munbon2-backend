"""Scheduler side of the shared v1 machine-boundary contract (PR 6.5b).

The BFF validates the SAME fixtures against its own strict mirrors; if either side drifts from
`contracts/control-plans/v1/`, that side's fixture test fails. A shared fixture that BOTH strict
models accept — with the exact same field set — is the cross-service drift trip-wire.
"""

import json
from pathlib import Path

from schemas.control_plan import (
    ControlPlanExecutionStateResponse,
    ControlPlanIntentTimelineResponse,
    ControlPlanReadbackObservationsResponse,
    HoldEventOut,
    IntentTimelineEntryOut,
    ReadbackObservationOut,
)

_CONTRACT_DIR = Path(__file__).resolve().parents[4] / "contracts" / "control-plans" / "v1"


def _load(name: str) -> dict:
    return json.loads((_CONTRACT_DIR / name).read_text(encoding="utf-8"))


def test_scheduler_accepts_the_shared_intent_timeline_fixture():
    timeline = ControlPlanIntentTimelineResponse.model_validate(
        _load("intent-timeline.example.json")
    )
    assert timeline.intents[0].execution_state == "claimed"
    assert timeline.intents[0].reason_code == "freshness_failed"


def test_scheduler_accepts_the_shared_readback_observations_fixture():
    obs = ControlPlanReadbackObservationsResponse.model_validate(
        _load("readback-observations.example.json")
    )
    assert obs.observations[0].verdict == "mismatch"


def test_scheduler_accepts_the_shared_execution_state_fixture():
    state = ControlPlanExecutionStateResponse.model_validate(
        _load("execution-state.example.json")
    )
    assert state.is_held is True


def test_scheduler_out_models_and_fixtures_agree_on_the_exact_item_field_set():
    assert set(IntentTimelineEntryOut.model_fields) == set(
        _load("intent-timeline.example.json")["intents"][0]
    )
    assert set(ReadbackObservationOut.model_fields) == set(
        _load("readback-observations.example.json")["observations"][0]
    )
    assert set(HoldEventOut.model_fields) == set(
        _load("execution-state.example.json")["hold_events"][0]
    )
