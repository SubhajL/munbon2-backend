"""PR 6.3b — ReadbackReconciliationService: config-gated observe/enforce, hold-on-drift.

The done-gate `test_readback_mismatch_holds_plan` uses an INJECTED readback (actuation-
independent) — a drift from the plan's expected BASELINE holds the plan in enforce mode.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from services.readback_reconciliation_service import ReadbackReconciliationService

NOW = datetime(2026, 7, 20, 3, 0, 0, tzinfo=timezone.utc)
PLAN_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
GATE = "M(0,0;1,0)"


def _held_event():
    return SimpleNamespace(event_type="held", intent_id=None, occurred_at=NOW, created_at=NOW)


class FakeRepo:
    def __init__(self, *, held_events=None):
        self.observations = []
        self._held_events = held_events or []

    async def record_readback_observation(self, session, row):
        self.observations.append(row)

    async def load_open_loop_context(self, session, plan_id, plan_version):
        return SimpleNamespace(
            events=self._held_events, transitions=[], outbox=[], granted_at=NOW
        )


class FakeOpenLoop:
    def __init__(self):
        self.holds = []

    async def hold_control_plan(self, session, plan_id, plan_version, actor_subject, reason=None, *, now=None):
        self.holds.append((plan_id, plan_version, actor_subject, reason))


def _service(mode, *, held_events=None):
    fake_repo = FakeRepo(held_events=held_events)
    open_loop = FakeOpenLoop()
    svc = ReadbackReconciliationService(fake_repo, open_loop, mode=mode, clock=lambda: NOW)
    return svc, fake_repo, open_loop


async def _reconcile(svc, *, observed_level, expected_level, quality="ok"):
    return await svc.reconcile_plan_readback(
        None, PLAN_ID, 1,
        readings={GATE: {"observed_level": observed_level, "quality": quality}},
        expected_levels={GATE: expected_level},
        now=NOW,
    )


class TestReadbackReconciliation:
    @pytest.mark.asyncio
    async def test_readback_mismatch_holds_plan(self):
        # DONE-GATE: a fresh readback that drifts from the baseline holds the plan (enforce).
        svc, repo, open_loop = _service("enforce")
        report = await _reconcile(svc, observed_level=4, expected_level=2)
        assert report.held is True
        assert GATE in report.mismatched_gate_ids
        assert len(open_loop.holds) == 1
        assert open_loop.holds[0][:2] == (PLAN_ID, 1)
        assert repo.observations[0].verdict == "mismatch"
        assert repo.observations[0].reconciliation_mode == "enforce"

    @pytest.mark.asyncio
    async def test_an_already_held_plan_is_not_re_held(self):
        # M1: a sustained drift must NOT append a fresh `held` event every tick.
        svc, repo, open_loop = _service("enforce", held_events=[_held_event()])
        report = await _reconcile(svc, observed_level=4, expected_level=2)
        assert report.held is False  # already held → no re-hold
        assert open_loop.holds == []
        assert repo.observations[0].verdict == "mismatch"  # still recorded

    @pytest.mark.asyncio
    async def test_matching_readback_does_not_hold(self):
        svc, repo, open_loop = _service("enforce")
        report = await _reconcile(svc, observed_level=2, expected_level=2)
        assert report.held is False
        assert open_loop.holds == []
        assert repo.observations[0].verdict == "ok"

    @pytest.mark.asyncio
    async def test_observe_mode_records_but_never_holds(self):
        svc, repo, open_loop = _service("observe")
        report = await _reconcile(svc, observed_level=4, expected_level=2)
        assert report.held is False
        assert open_loop.holds == []
        assert len(repo.observations) == 1  # still recorded
        assert repo.observations[0].verdict == "mismatch"

    @pytest.mark.asyncio
    async def test_off_mode_is_dark_no_record_no_hold(self):
        svc, repo, open_loop = _service("off")
        report = await _reconcile(svc, observed_level=4, expected_level=2)
        assert report.mode == "off"
        assert report.held is False
        assert repo.observations == []
        assert open_loop.holds == []

    @pytest.mark.asyncio
    async def test_unavailable_reading_records_but_never_holds(self):
        svc, repo, open_loop = _service("enforce")
        report = await _reconcile(svc, observed_level=4, expected_level=2, quality="stale")
        assert report.held is False
        assert open_loop.holds == []
        assert repo.observations[0].verdict == "unavailable"

    @pytest.mark.asyncio
    async def test_missing_reading_is_unavailable_not_a_hold(self):
        svc, repo, open_loop = _service("enforce")
        report = await svc.reconcile_plan_readback(
            None, PLAN_ID, 1,
            readings={},  # no reading for the gate
            expected_levels={GATE: 2},
            now=NOW,
        )
        assert report.held is False
        assert repo.observations[0].verdict == "unavailable"
        assert repo.observations[0].observed_level is None
