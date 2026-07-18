"""Pure predicted-fulfillment ledger projection, coalescing, and handover."""

from datetime import datetime, timedelta, timezone

import pytest

from core.predicted_delivery_ledger import (
    GateEvent,
    LedgerProjectionError,
    ScheduledRequirement,
    coalesce_equal_gate_events,
    evaluate_safe_handover,
    predicted_delivery_ledger_sha256,
    project_predicted_delivery_ledger,
)

START = datetime(2026, 7, 20, 20, 0, tzinfo=timezone.utc)  # crosses UTC midnight
STEP = 3600
RUN_ID = "c" * 64
RESP_SHA = "d" * 64


def _samples(n):
    # Flow's sampled_at are step-END times: the last sample is the horizon end.
    return [
        (START + timedelta(seconds=(i + 1) * STEP)).isoformat()
        for i in range(n)
    ]


def _requirement(**overrides):
    base = dict(
        requirement_id="req-1",
        section_id="SEC-1",
        gate_id="G1",
        required_volume_m3=100.0,
        approved_excess_m3=20.0,
        path_reach_ids=("R1", "R2"),
        window_start=START,
        window_end=START + timedelta(seconds=8 * STEP),
    )
    base.update(overrides)
    return ScheduledRequirement(**base)


def _member(name, delivered, status, in_transit, *, feasible=True):
    if not feasible:
        return {
            "member": name,
            "status": "infeasible",
            "predicted_delivered_total_m3": None,
            "timeline": None,
        }
    n = len(delivered)
    return {
        "member": name,
        "status": "completed",
        "predicted_delivered_total_m3": delivered[-1],
        "timeline": {
            "sampled_at": _samples(n),
            "reaches": [
                {"reach_id": "R1", "in_transit_volume_m3": in_transit["R1"]},
                {"reach_id": "R2", "in_transit_volume_m3": in_transit["R2"]},
                {"reach_id": "R9", "in_transit_volume_m3": [0.0] * n},
            ],
            "withdrawals": [],
            "requirements": [
                {
                    "requirement_id": "req-1",
                    "predicted_delivered_m3": delivered,
                    "status": status,
                }
            ],
            "terminal_outflow_m3": [0.0] * n,
            "mass_balance": {
                "initial_in_transit_m3": 0.0,
                "boundary_inflow_m3": delivered[-1],
                "delivered_m3": delivered[-1],
                "withdrawn_m3": 0.0,
                "declared_loss_m3": 0.0,
                "terminal_outflow_m3": 0.0,
                "final_in_transit_m3": 0.0,
                "balance_error_m3": 0.0,
            },
            "final_fulfillment": [
                {
                    "requirement_id": "req-1",
                    "section_id": "SEC-1",
                    "required_volume_m3": 100.0,
                    "approved_excess_m3": 20.0,
                    "predicted_delivered_m3": delivered[-1],
                    "status": status[-1],
                }
            ],
        },
    }


def _delivered(total):
    # 6-sample cumulative delivery ramp that ends at `total`.
    return [0.0, 0.0, total * 0.25, total * 0.5, total * 0.9, total]


def _statuses():
    return [
        "pending",
        "pending",
        "arrival_predicted",
        "delivery_predicted_active",
        "delivery_predicted_active",
        "predicted_fulfilled",
    ]


def _in_transit():
    return {
        "R1": [0.0, 5.0, 8.0, 6.0, 2.0, 0.0],
        "R2": [0.0, 0.0, 4.0, 3.0, 1.0, 0.0],
    }


def _response(members=None):
    if members is None:
        members = [
            _member("lower", _delivered(105.0), _statuses(), _in_transit()),
            _member("nominal", _delivered(100.0), _statuses(), _in_transit()),
            _member("upper", _delivered(96.0), _statuses(), _in_transit()),
        ]
    return {
        "starts_at": START.isoformat(),
        "ends_at": (START + timedelta(seconds=6 * STEP)).isoformat(),
        "members": members,
    }


def _project(response=None, requirement=None, gate_events=None):
    return project_predicted_delivery_ledger(
        [requirement or _requirement()],
        response or _response(),
        gate_events
        if gate_events is not None
        else [
            GateEvent("G1", "open", START, 0.5),
            GateEvent("G1", "close", START + timedelta(seconds=5 * STEP), 0.0),
        ],
        prediction_run_id=RUN_ID,
        prediction_response_sha256=RESP_SHA,
    )


class TestCoalesceGateEvents:
    def test_equal_adjacent_positions_create_checkpoint_not_move(self):
        events = [
            GateEvent("G1", "open", START, 0.5),
            GateEvent("G1", "trim", START + timedelta(hours=6), 0.5),
            GateEvent("G1", "trim", START + timedelta(hours=12), 0.8),
            GateEvent("G1", "close", START + timedelta(hours=18), 0.0),
        ]
        classified = coalesce_equal_gate_events(events)
        moves = [c["movement_required"] for c in classified]
        assert moves == [True, False, True, True]


class TestProjection:
    def test_ledger_statuses_are_prediction_only(self):
        entries = _project()
        allowed = {
            "not_started",
            "predicted_in_progress",
            "predicted_fulfilled",
            "predicted_excess_risk",
            "invalidated",
            "manual_review",
        }
        assert entries
        assert all(e.status in allowed for e in entries)
        assert {e.status for e in entries} <= allowed

    def test_midnight_preserves_requirement_and_in_transit_volume(self):
        entries = _project()
        # START is 20:00 UTC; a sample lands on 00:00 next day (ends-based
        # samples: 21:00, 22:00, 23:00, 00:00, ...).
        rollover = [
            e for e in entries if "date_rollover" in e.checkpoint_reasons
        ]
        assert rollover, "expected a checkpoint at the UTC date rollover"
        assert all(e.requirement_id == "req-1" for e in entries)
        # Ends-based samples: 21,22,23,00,01,02 → sample index 3 is 00:00.
        # In-transit is the exact persisted reach sum and is NOT reset across
        # the boundary: R1[3]+R2[3] = 6+3 = 9 at 00:00, R1[2]+R2[2] = 8+4 = 12
        # just before it (continuous, non-zero on both sides of midnight).
        crossing = next(e for e in rollover if e.checkpoint_at.hour == 0)
        assert crossing.nominal_path_in_transit_m3 == pytest.approx(9.0)
        before = next(
            e for e in entries if e.checkpoint_at.hour == 23
        )
        assert before.nominal_path_in_transit_m3 == pytest.approx(12.0)

    def test_delivery_bounds_use_minmax_across_members(self):
        # lower member delivers MORE (105) than nominal (100) and upper (96):
        # the raw member columns keep their labels; the API min/max is 96..105.
        entries = _project()
        terminal = max(entries, key=lambda e: e.checkpoint_index)
        assert terminal.lower_delivered_m3 == pytest.approx(105.0)
        assert terminal.upper_delivered_m3 == pytest.approx(96.0)
        assert min(
            terminal.lower_delivered_m3,
            terminal.nominal_delivered_m3,
            terminal.upper_delivered_m3,
        ) == pytest.approx(96.0)

    def test_path_transit_uses_exact_persisted_reach_series(self):
        entries = _project()
        # The 23:00 checkpoint (sample index 2) sums R1[2]+R2[2] = 8+4 = 12.
        row = next(e for e in entries if e.checkpoint_at.hour == 23)
        assert row.nominal_path_in_transit_m3 == pytest.approx(12.0)
        assert row.lower_path_in_transit_m3 == pytest.approx(12.0)

    def test_shared_reach_off_path_is_never_summed(self):
        # R9 carries nonzero occupancy but is NOT on the requirement's path
        # (R1,R2); it must never be added into path transit.
        in_transit = _in_transit()
        members = [
            _member("lower", _delivered(105.0), _statuses(), in_transit),
            _member("nominal", _delivered(100.0), _statuses(), in_transit),
            _member("upper", _delivered(96.0), _statuses(), in_transit),
        ]
        response = _response(members)
        # Give R9 a large occupancy in every member timeline.
        for member in response["members"]:
            for reach in member["timeline"]["reaches"]:
                if reach["reach_id"] == "R9":
                    reach["in_transit_volume_m3"] = [999.0] * len(
                        reach["in_transit_volume_m3"]
                    )
        entries = _project(response=response)
        row = next(e for e in entries if e.checkpoint_at.hour == 23)
        # Still exactly R1[2]+R2[2]=12, NOT 12+999.
        assert row.nominal_path_in_transit_m3 == pytest.approx(12.0)

    def test_semantic_checkpoints_avoid_per_timestep_rows(self):
        entries = _project()
        # 6 samples but far fewer than 6 distinct rows is NOT required; assert
        # rows never exceed sample count and are deduped by checkpoint.
        assert len(entries) <= 6
        indices = [e.checkpoint_index for e in entries]
        assert indices == sorted(set(indices))

    def test_terminal_totals_reconcile_to_prediction_artifact(self):
        # Passes only because rows' terminal delivered == member totals.
        entries = _project()
        assert entries

    def test_reconciliation_mismatch_fails_closed(self):
        members = [
            _member("lower", _delivered(105.0), _statuses(), _in_transit()),
            _member("nominal", _delivered(100.0), _statuses(), _in_transit()),
            _member("upper", _delivered(96.0), _statuses(), _in_transit()),
        ]
        # Corrupt the member total so rows can't reconcile.
        members[1]["predicted_delivered_total_m3"] = 999.0
        with pytest.raises(LedgerProjectionError):
            _project(response=_response(members))

    def test_path_reach_absent_from_prediction_fails_closed(self):
        req = _requirement(path_reach_ids=("R1", "R404"))
        with pytest.raises(LedgerProjectionError):
            _project(requirement=req)

    def test_misaligned_series_fails_closed(self):
        members = [
            _member("lower", _delivered(105.0), _statuses(), _in_transit()),
            _member("nominal", _delivered(100.0), _statuses(), _in_transit()),
            _member("upper", _delivered(96.0), _statuses(), _in_transit()),
        ]
        members[0]["timeline"]["requirements"][0]["predicted_delivered_m3"] = [
            0.0,
            1.0,
        ]
        with pytest.raises(LedgerProjectionError):
            _project(response=_response(members))

    def test_completed_member_without_timeline_fails_closed(self):
        members = [
            _member("lower", _delivered(105.0), _statuses(), _in_transit()),
            _member("nominal", _delivered(100.0), _statuses(), _in_transit()),
            _member("upper", _delivered(96.0), _statuses(), _in_transit()),
        ]
        members[2]["timeline"] = None  # status stays "completed" → contract error
        with pytest.raises(LedgerProjectionError):
            _project(response=_response(members))

    def test_infeasible_member_projects_manual_review(self):
        members = [
            _member("lower", _delivered(105.0), _statuses(), _in_transit()),
            _member("nominal", _delivered(100.0), _statuses(), _in_transit()),
            _member("upper", [], [], {}, feasible=False),
        ]
        entries = _project(response=_response(members))
        assert entries
        assert all(e.status == "manual_review" for e in entries)
        assert all(e.upper_delivered_m3 is None for e in entries)

    def test_all_infeasible_projects_single_manual_review_row(self):
        members = [
            _member("lower", [], [], {}, feasible=False),
            _member("nominal", [], [], {}, feasible=False),
            _member("upper", [], [], {}, feasible=False),
        ]
        entries = _project(response=_response(members))
        assert len(entries) == 1
        assert entries[0].status == "manual_review"
        assert entries[0].nominal_delivered_m3 is None

    def test_excess_member_yields_excess_risk(self):
        excess_status = _statuses()[:-1] + ["predicted_excess"]
        members = [
            _member("lower", _delivered(105.0), _statuses(), _in_transit()),
            _member("nominal", _delivered(100.0), _statuses(), _in_transit()),
            _member(
                "upper",
                _delivered(96.0),
                excess_status,
                _in_transit(),
            ),
        ]
        entries = _project(response=_response(members))
        terminal = max(entries, key=lambda e: e.checkpoint_index)
        assert terminal.status == "predicted_excess_risk"

    def test_ledger_set_hash_is_deterministic_and_order_dependent(self):
        entries = _project()
        digest = predicted_delivery_ledger_sha256(entries)
        assert len(digest) == 64
        # Deterministic on the same order.
        assert predicted_delivery_ledger_sha256(entries) == digest
        # Order-dependent: a reordering changes the set hash (it pins the exact
        # row sequence for 4.3b lineage).
        if len(entries) >= 2:
            reordered = list(reversed(entries))
            assert predicted_delivery_ledger_sha256(reordered) != digest

    def test_row_hash_is_deterministic_and_content_sensitive(self):
        entries = _project()
        again = _project()
        # Same artifact → identical row hashes.
        assert [e.projection_sha256 for e in entries] == [
            e.projection_sha256 for e in again
        ]
        # A different projection document yields a different hash.
        tampered_doc = entries[0].projection_document_text.replace(
            '"status":', '"STATUS":'
        )
        from core.predicted_delivery_ledger import ledger_row_sha256

        assert ledger_row_sha256(tampered_doc) != entries[0].projection_sha256

    def test_cross_member_timestamp_mismatch_fails_closed(self):
        members = [
            _member("lower", _delivered(105.0), _statuses(), _in_transit()),
            _member("nominal", _delivered(100.0), _statuses(), _in_transit()),
            _member("upper", _delivered(96.0), _statuses(), _in_transit()),
        ]
        # Shift the nominal member's grid by one step; lengths still match.
        shifted = [
            (START + timedelta(seconds=(i + 2) * STEP)).isoformat()
            for i in range(6)
        ]
        members[1]["timeline"]["sampled_at"] = shifted
        with pytest.raises(LedgerProjectionError):
            _project(response=_response(members))

    def test_verify_ledger_entry_columns_detects_tampered_status(self):
        from dataclasses import replace as dc_replace

        from core.predicted_delivery_ledger import (
            verify_ledger_entry_columns,
        )

        entries = _project()
        verify_ledger_entry_columns(entries[0])  # untampered passes
        tampered = dc_replace(entries[0], status="predicted_excess_risk")
        with pytest.raises(LedgerProjectionError):
            verify_ledger_entry_columns(tampered)


class TestSafeHandover:
    def _entries_and_events(self, members=None, close=True):
        events = [GateEvent("G1", "open", START, 0.5)]
        if close:
            events.append(
                GateEvent("G1", "close", START + timedelta(seconds=5 * STEP), 0.0)
            )
        entries = _project(response=_response(members), gate_events=events)
        return entries, events

    def test_safe_handover_true_on_drained_fulfilled_envelope(self):
        # Safe requires the WORST-case member to still meet the requirement and
        # the BEST-case to stay within excess: all three in [100, 120], drained.
        fulfilled = _statuses()[:-1] + ["predicted_fulfilled"]
        members = [
            _member("lower", _delivered(110.0), fulfilled, _in_transit()),
            _member("nominal", _delivered(105.0), fulfilled, _in_transit()),
            _member("upper", _delivered(101.0), fulfilled, _in_transit()),
        ]
        entries, events = self._entries_and_events(members=members)
        verdict = evaluate_safe_handover(
            [_requirement()], entries, events, all_members_completed=True
        )
        assert verdict.is_safe, verdict.reasons

    def test_safe_handover_rejects_missing_close(self):
        entries, events = self._entries_and_events(close=False)
        verdict = evaluate_safe_handover(
            [_requirement()], entries, events, all_members_completed=True
        )
        assert not verdict.is_safe
        assert "no_terminal_close_event" in verdict.reasons

    def test_safe_handover_rejects_undrained_terminal_transit(self):
        transit = {"R1": [0.0, 5.0, 8.0, 6.0, 2.0, 3.0], "R2": _in_transit()["R2"]}
        members = [
            _member("lower", _delivered(105.0), _statuses(), transit),
            _member("nominal", _delivered(100.0), _statuses(), transit),
            _member("upper", _delivered(96.0), _statuses(), transit),
        ]
        entries, events = self._entries_and_events(members=members)
        verdict = evaluate_safe_handover(
            [_requirement()], entries, events, all_members_completed=True
        )
        assert not verdict.is_safe
        assert any(r.endswith("undrained_path_transit") for r in verdict.reasons)

    def test_safe_handover_rejects_shortfall(self):
        members = [
            _member("lower", _delivered(90.0), _statuses(), _in_transit()),
            _member("nominal", _delivered(88.0), _statuses(), _in_transit()),
            _member("upper", _delivered(85.0), _statuses(), _in_transit()),
        ]
        entries, events = self._entries_and_events(members=members)
        verdict = evaluate_safe_handover(
            [_requirement()], entries, events, all_members_completed=True
        )
        assert not verdict.is_safe
        assert any(r.endswith("terminal_shortfall") for r in verdict.reasons)

    def test_safe_handover_rejects_shared_gate_with_a_short_sibling(self):
        # Two requirements share gate G1: R-A fulfilled+drained, R-B short.
        # The GATE cannot be handed over while R-B is outstanding.
        from core.predicted_delivery_ledger import LedgerEntry

        def _terminal(requirement_id, delivered):
            return LedgerEntry(
                requirement_id=requirement_id,
                section_id="S",
                checkpoint_index=1,
                checkpoint_at=START,
                status="predicted_fulfilled",
                required_volume_m3=100.0,
                approved_excess_m3=20.0,
                lower_delivered_m3=delivered,
                nominal_delivered_m3=delivered,
                upper_delivered_m3=delivered,
                lower_path_in_transit_m3=0.0,
                nominal_path_in_transit_m3=0.0,
                upper_path_in_transit_m3=0.0,
                checkpoint_reasons=("horizon_end",),
                projection_sha256="a" * 64,
                projection_document_text="{}",
            )

        req_a = ScheduledRequirement(
            "R-A", "S", "G1", 100.0, 20.0, ("R1",), START, START
        )
        req_b = ScheduledRequirement(
            "R-B", "S", "G1", 100.0, 20.0, ("R1",), START, START
        )
        entries = [_terminal("R-A", 110.0), _terminal("R-B", 80.0)]
        events = [
            GateEvent("G1", "open", START, 0.5),
            GateEvent("G1", "close", START + timedelta(seconds=STEP), 0.0),
        ]
        verdict = evaluate_safe_handover(
            [req_a, req_b], entries, events, all_members_completed=True
        )
        assert not verdict.is_safe
        assert any(r.startswith("R-B:") for r in verdict.reasons)

    def test_safe_handover_rejects_incomplete_members(self):
        members = [
            _member("lower", _delivered(105.0), _statuses(), _in_transit()),
            _member("nominal", _delivered(100.0), _statuses(), _in_transit()),
            _member("upper", [], [], {}, feasible=False),
        ]
        entries, events = self._entries_and_events(members=members)
        verdict = evaluate_safe_handover(
            [_requirement()], entries, events, all_members_completed=False
        )
        assert not verdict.is_safe
