"""Source-flow event algebra and prediction-request construction."""

from datetime import datetime, timezone

import pytest

from algorithms.hydraulic_schedule_optimizer import (
    GateEventKind,
    GatePlanEvent,
)
from core.control_plan import (
    InternalPlanInvariantError,
    UpstreamContractError,
    build_control_prediction_request,
    build_source_flow_events,
    summarize_prediction_status,
)

STARTS_AT = datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc)
ENDS_AT = datetime(2026, 7, 21, 0, 0, tzinfo=timezone.utc)

CANDIDATES = [
    {"gate_id": "G1", "target_position_m": 0.5, "source_flow_m3s": 2.0},
    {"gate_id": "G1", "target_position_m": 0.8, "source_flow_m3s": 3.0},
    {"gate_id": "G2", "target_position_m": 0.4, "source_flow_m3s": 1.5},
]


def _at(hour):
    return datetime(2026, 7, 20, hour, 0, tzinfo=timezone.utc)


class TestBuildSourceFlowEvents:
    def test_open_emits_candidate_flow_and_close_returns_to_zero(self):
        events = (
            GatePlanEvent("G1", GateEventKind.OPEN, _at(6), 0.5),
            GatePlanEvent("G1", GateEventKind.CLOSE, _at(12), 0.0),
        )
        result = build_source_flow_events(events, CANDIDATES, STARTS_AT, ENDS_AT)
        assert result == [
            {"node_id": "S", "effective_at": STARTS_AT, "flow_m3s": 0.0},
            {"node_id": "S", "effective_at": _at(6), "flow_m3s": 2.0},
            {"node_id": "S", "effective_at": _at(12), "flow_m3s": 0.0},
        ]

    def test_simultaneous_gates_sum_their_candidate_flows(self):
        events = (
            GatePlanEvent("G1", GateEventKind.OPEN, STARTS_AT, 0.5),
            GatePlanEvent("G2", GateEventKind.OPEN, STARTS_AT, 0.4),
            GatePlanEvent("G2", GateEventKind.CLOSE, _at(6), 0.0),
            GatePlanEvent("G1", GateEventKind.CLOSE, _at(12), 0.0),
        )
        result = build_source_flow_events(events, CANDIDATES, STARTS_AT, ENDS_AT)
        assert result == [
            {"node_id": "S", "effective_at": STARTS_AT, "flow_m3s": 3.5},
            {"node_id": "S", "effective_at": _at(6), "flow_m3s": 2.0},
            {"node_id": "S", "effective_at": _at(12), "flow_m3s": 0.0},
        ]

    def test_trim_switches_to_new_candidate_flow(self):
        events = (
            GatePlanEvent("G1", GateEventKind.OPEN, STARTS_AT, 0.5),
            GatePlanEvent("G1", GateEventKind.TRIM, _at(6), 0.8),
            GatePlanEvent("G1", GateEventKind.CLOSE, _at(12), 0.0),
        )
        result = build_source_flow_events(events, CANDIDATES, STARTS_AT, ENDS_AT)
        assert [entry["flow_m3s"] for entry in result] == [2.0, 3.0, 0.0]

    def test_unchanged_total_is_suppressed(self):
        # G1 closes exactly when G2 opens with an equal flow: total is unchanged.
        candidates = CANDIDATES + [
            {"gate_id": "G2", "target_position_m": 0.9, "source_flow_m3s": 2.0}
        ]
        events = (
            GatePlanEvent("G1", GateEventKind.OPEN, STARTS_AT, 0.5),
            GatePlanEvent("G1", GateEventKind.CLOSE, _at(6), 0.0),
            GatePlanEvent("G2", GateEventKind.OPEN, _at(6), 0.9),
            GatePlanEvent("G2", GateEventKind.CLOSE, _at(12), 0.0),
        )
        result = build_source_flow_events(events, candidates, STARTS_AT, ENDS_AT)
        assert result == [
            {"node_id": "S", "effective_at": STARTS_AT, "flow_m3s": 2.0},
            {"node_id": "S", "effective_at": _at(12), "flow_m3s": 0.0},
        ]

    def test_close_at_horizon_end_is_omitted_from_prediction_input(self):
        events = (
            GatePlanEvent("G1", GateEventKind.OPEN, _at(6), 0.5),
            GatePlanEvent("G1", GateEventKind.CLOSE, ENDS_AT, 0.0),
        )
        result = build_source_flow_events(events, CANDIDATES, STARTS_AT, ENDS_AT)
        assert result[-1] == {
            "node_id": "S",
            "effective_at": _at(6),
            "flow_m3s": 2.0,
        }

    def test_starts_at_event_is_always_present(self):
        events = (
            GatePlanEvent("G1", GateEventKind.OPEN, _at(6), 0.5),
            GatePlanEvent("G1", GateEventKind.CLOSE, _at(12), 0.0),
        )
        result = build_source_flow_events(events, CANDIDATES, STARTS_AT, ENDS_AT)
        assert result[0] == {
            "node_id": "S",
            "effective_at": STARTS_AT,
            "flow_m3s": 0.0,
        }

    def test_unknown_candidate_position_is_internal_invariant_error(self):
        events = (GatePlanEvent("G1", GateEventKind.OPEN, _at(6), 0.77),)
        with pytest.raises(InternalPlanInvariantError):
            build_source_flow_events(events, CANDIDATES, STARTS_AT, ENDS_AT)

    def test_event_after_horizon_end_is_internal_invariant_error(self):
        events = (
            GatePlanEvent("G1", GateEventKind.OPEN, _at(6), 0.5),
            GatePlanEvent(
                "G1",
                GateEventKind.CLOSE,
                datetime(2026, 7, 21, 1, 0, tzinfo=timezone.utc),
                0.0,
            ),
        )
        with pytest.raises(InternalPlanInvariantError):
            build_source_flow_events(events, CANDIDATES, STARTS_AT, ENDS_AT)


class TestBuildControlPredictionRequest:
    def test_request_reuses_exact_pins_and_documents(self):
        events = (
            GatePlanEvent("G1", GateEventKind.OPEN, STARTS_AT, 0.5),
            GatePlanEvent("G1", GateEventKind.CLOSE, _at(12), 0.0),
        )
        request = build_control_prediction_request(
            model_snapshot_id="a" * 64,
            model_release_id="release-2026-07",
            model_release_content_hash="b" * 64,
            starts_at=STARTS_AT,
            ends_at=ENDS_AT,
            timestep_seconds=3600.0,
            plan_events=events,
            flow_candidates=CANDIDATES,
            operator_withdrawals=[
                {
                    "structure_id": "WW-1",
                    "effective_at": _at(3),
                    "planned_flow_m3s": 0.4,
                    "purpose": "flushing",
                    "operator_reference": None,
                }
            ],
            branch_allocations=[
                {
                    "upstream_node_id": "N1",
                    "downstream_node_id": "N2",
                    "fraction": 0.6,
                }
            ],
            section_requirements=[
                {
                    "requirement_id": "req-1",
                    "section_id": "SEC-1",
                    "delivery_node_id": "N3",
                    "window_start": _at(6),
                    "window_end": _at(18),
                    "required_volume_m3": 1200.0,
                    "maximum_delivery_m3s": 2.5,
                    "approved_excess_m3": 100.0,
                }
            ],
        )
        assert request["model_snapshot_id"] == "a" * 64
        assert request["model_release_id"] == "release-2026-07"
        assert request["model_release_content_hash"] == "b" * 64
        assert request["initialization"] == {"kind": "dry"}
        assert request["starts_at"] == "2026-07-20T00:00:00+00:00"
        assert request["ends_at"] == "2026-07-21T00:00:00+00:00"
        assert request["timestep_seconds"] == 3600.0
        assert request["source_flow_events"] == [
            {
                "node_id": "S",
                "effective_at": "2026-07-20T00:00:00+00:00",
                "flow_m3s": 2.0,
            },
            {
                "node_id": "S",
                "effective_at": "2026-07-20T12:00:00+00:00",
                "flow_m3s": 0.0,
            },
        ]
        assert request["operator_withdrawal_events"][0]["structure_id"] == "WW-1"
        assert request["branch_allocations"][0]["fraction"] == 0.6
        requirement = request["section_requirements"][0]
        assert requirement["window_start"] == "2026-07-20T06:00:00+00:00"
        assert requirement["maximum_delivery_m3s"] == 2.5
        expected_keys = {
            "model_snapshot_id",
            "model_release_id",
            "model_release_content_hash",
            "initialization",
            "starts_at",
            "ends_at",
            "timestep_seconds",
            "source_flow_events",
            "operator_withdrawal_events",
            "branch_allocations",
            "section_requirements",
        }
        assert set(request) == expected_keys


class TestSummarizePredictionStatus:
    def _response(self, statuses):
        members = [
            {"member": member, "status": status}
            for member, status in zip(("lower", "nominal", "upper"), statuses)
        ]
        return {"members": members}

    def test_all_completed_is_completed(self):
        response = self._response(["completed"] * 3)
        assert summarize_prediction_status(response) == "completed"

    def test_any_infeasible_member_is_infeasible(self):
        response = self._response(["completed", "infeasible", "completed"])
        assert summarize_prediction_status(response) == "infeasible"

    def test_wrong_member_count_is_contract_error(self):
        with pytest.raises(UpstreamContractError):
            summarize_prediction_status({"members": [{"status": "completed"}]})

    def test_unknown_status_is_contract_error(self):
        response = self._response(["completed", "running", "completed"])
        with pytest.raises(UpstreamContractError):
            summarize_prediction_status(response)

    def test_wrong_member_identities_is_contract_error(self):
        response = {
            "members": [
                {"member": "nominal", "status": "completed"},
                {"member": "nominal", "status": "completed"},
                {"member": "nominal", "status": "completed"},
            ]
        }
        with pytest.raises(UpstreamContractError):
            summarize_prediction_status(response)
