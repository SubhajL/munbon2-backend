"""Problem composition: topology walk, derivations, and optimizer contract fit."""

from datetime import date, datetime, timezone

import pytest

from algorithms.hydraulic_schedule_optimizer import (
    LimitedAdjustmentProblem,
    optimize_limited_adjustment_plan,
)
from core.control_plan import (
    DraftInputError,
    UpstreamContractError,
    build_limited_adjustment_problem,
    build_parent_elements,
    derive_delivery_fractions,
    derive_path_reach_ids,
    derive_reach_capacities,
    derive_travel_delay_seconds,
    index_response_members,
    validate_branch_allocations,
    validate_operator_withdrawals,
)

HORIZON_START = datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc)
HORIZON_END = datetime(2026, 7, 21, 0, 0, tzinfo=timezone.utc)
STEP_SECONDS = 3600


def _elements():
    # N1 is a genuine branching node (children N2, NX); delivery for SEC-1 is at
    # N3 via the N2 branch; NW is a withdrawal structure (never allocated).
    return [
        {
            "element_id": "R1",
            "upstream_node_id": "S",
            "downstream_node_id": "N1",
            "role": "transport",
        },
        {
            "element_id": "B1",
            "upstream_node_id": "N1",
            "downstream_node_id": "N2",
            "role": "branch_structure",
        },
        {
            "element_id": "B2",
            "upstream_node_id": "N1",
            "downstream_node_id": "NX",
            "role": "branch_structure",
        },
        {
            "element_id": "R2",
            "upstream_node_id": "N2",
            "downstream_node_id": "N3",
            "role": "transport",
        },
        {
            "element_id": "W1",
            "upstream_node_id": "N1",
            "downstream_node_id": "NW",
            "role": "withdrawal_structure",
        },
    ]


def _branch_allocations():
    return [
        {"upstream_node_id": "N1", "downstream_node_id": "N2", "fraction": 0.6},
        {"upstream_node_id": "N1", "downstream_node_id": "NX", "fraction": 0.4},
    ]


def _members():
    rows = []
    profile = {
        "R1": {
            "lower": (500.0, 0.10, 5.0),
            "nominal": (600.0, 0.05, 5.5),
            "upper": (700.0, 0.02, 6.0),
        },
        "R2": {
            "lower": (1000.0, 0.05, 3.2),
            "nominal": (1100.0, 0.04, 3.0),
            "upper": (1150.0, 0.02, 3.1),
        },
    }
    for reach_id, members in profile.items():
        for member, (delay, loss, capacity) in members.items():
            rows.append(
                {
                    "reach_id": reach_id,
                    "member": member,
                    "delay_seconds": delay,
                    "loss_fraction": loss,
                    "capacity_m3s": capacity,
                }
            )
    return rows


def _envelope():
    return {
        "minimum_flow_m3s": 0.0,
        "maximum_flow_m3s": 10.0,
        "minimum_timestep_seconds": 300.0,
        "maximum_timestep_seconds": 3600.0,
        "maximum_horizon_seconds": 7 * 86400.0,
    }


def _requirement(requirement_id="req-1", volume=1200.0, section_id="SEC-1"):
    return {
        "requirement_id": requirement_id,
        "run_id": "8e0b0e6a-6c1e-5f5e-9d5c-2f6a8b1c2d3e",
        "version": 3,
        "service_date": date(2026, 7, 20),
        "section_id": section_id,
        "zone": 1,
        "required_volume_m3": volume,
        "window_start": datetime(2026, 7, 20, 6, 0, tzinfo=timezone.utc),
        "window_end": datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc),
        "quality": "estimated",
        "published_at": datetime(2026, 7, 19, 19, 5, tzinfo=timezone.utc),
        "as_of_date": date(2026, 7, 19),
        "data_status": "published",
    }


def _binding(section_id="SEC-1", delivery_node_id="N3", gate_id="G1"):
    return {
        "section_id": section_id,
        "delivery_node_id": delivery_node_id,
        "gate_id": gate_id,
        "maximum_delivery_m3s": 2.5,
    }


def _policy(requirement_id="req-1"):
    return {
        "requirement_id": requirement_id,
        "approved_excess_m3": 100.0,
        "rotation_windows": [
            {
                "starts_at": datetime(2026, 7, 20, 6, 0, tzinfo=timezone.utc),
                "ends_at": datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc),
            }
        ],
    }


def _compose(**overrides):
    arguments = {
        "snapshot_id": "a" * 64,
        "routing_elements": _elements(),
        "response_members": _members(),
        "operating_envelope": _envelope(),
        "unavailable_reach_ids": ["R9"],
        "requirement_items": [_requirement()],
        "section_bindings": {"SEC-1": _binding()},
        "requirement_policies": {"req-1": _policy()},
        "flow_candidates": [
            {"gate_id": "G1", "target_position_m": 0.5, "source_flow_m3s": 2.0}
        ],
        "pulse_duties": [
            {
                "gate_id": "G1",
                "minimum_open_seconds": 3600,
                "maximum_open_seconds": 86400,
            }
        ],
        "branch_allocations": _branch_allocations(),
        "operator_withdrawals": [],
        "horizon_start": HORIZON_START,
        "horizon_end": HORIZON_END,
        "model_step_seconds": STEP_SECONDS,
    }
    arguments.update(overrides)
    return build_limited_adjustment_problem(**arguments)


class TestTopologyWalk:
    def test_path_retains_transport_elements_only_in_hydraulic_order(self):
        parents = build_parent_elements(_elements())
        assert derive_path_reach_ids(parents, "N3") == ("R1", "R2")

    def test_unknown_delivery_node_fails_closed(self):
        parents = build_parent_elements(_elements())
        with pytest.raises(DraftInputError):
            derive_path_reach_ids(parents, "N9")

    def test_delivery_node_source_is_rejected(self):
        parents = build_parent_elements(_elements())
        with pytest.raises(DraftInputError):
            derive_path_reach_ids(parents, "S")

    def test_duplicate_downstream_node_is_upstream_contract_error(self):
        elements = _elements() + [
            {
                "element_id": "R2b",
                "upstream_node_id": "N1",
                "downstream_node_id": "N3",
                "role": "transport",
            }
        ]
        with pytest.raises(UpstreamContractError):
            build_parent_elements(elements)

    def test_cycle_is_upstream_contract_error(self):
        elements = [
            {
                "element_id": "R1",
                "upstream_node_id": "N2",
                "downstream_node_id": "N1",
                "role": "transport",
            },
            {
                "element_id": "R2",
                "upstream_node_id": "N1",
                "downstream_node_id": "N2",
                "role": "transport",
            },
        ]
        parents = build_parent_elements(elements)
        with pytest.raises(UpstreamContractError):
            derive_path_reach_ids(parents, "N2")


class TestBranchAllocationContract:
    def test_full_sibling_coverage_summing_to_one_is_valid(self):
        validate_branch_allocations(_elements(), _branch_allocations())

    def test_partial_sibling_coverage_fails_closed(self):
        allocations = [
            {"upstream_node_id": "N1", "downstream_node_id": "N2",
             "fraction": 1.0}
        ]
        with pytest.raises(DraftInputError):
            validate_branch_allocations(_elements(), allocations)

    def test_siblings_not_summing_to_one_fails_closed(self):
        allocations = [
            {"upstream_node_id": "N1", "downstream_node_id": "N2",
             "fraction": 0.5},
            {"upstream_node_id": "N1", "downstream_node_id": "NX",
             "fraction": 0.4},
        ]
        with pytest.raises(DraftInputError):
            validate_branch_allocations(_elements(), allocations)

    def test_negative_fraction_fails_closed(self):
        allocations = [
            {"upstream_node_id": "N1", "downstream_node_id": "N2",
             "fraction": 1.2},
            {"upstream_node_id": "N1", "downstream_node_id": "NX",
             "fraction": -0.2},
        ]
        with pytest.raises(DraftInputError):
            validate_branch_allocations(_elements(), allocations)

    def test_zero_fraction_sibling_is_allowed(self):
        allocations = [
            {"upstream_node_id": "N1", "downstream_node_id": "N2",
             "fraction": 1.0},
            {"upstream_node_id": "N1", "downstream_node_id": "NX",
             "fraction": 0.0},
        ]
        validate_branch_allocations(_elements(), allocations)

    def test_unknown_branch_edge_fails_closed(self):
        allocations = _branch_allocations() + [
            {"upstream_node_id": "N1", "downstream_node_id": "NBOGUS",
             "fraction": 0.0}
        ]
        with pytest.raises(DraftInputError):
            validate_branch_allocations(_elements(), allocations)

    def test_allocation_on_withdrawal_edge_fails_closed(self):
        allocations = _branch_allocations() + [
            {"upstream_node_id": "N1", "downstream_node_id": "NW",
             "fraction": 0.0}
        ]
        with pytest.raises(DraftInputError):
            validate_branch_allocations(_elements(), allocations)


class TestOperatorWithdrawalContract:
    def _withdrawal(self, effective_hour=6, structure_id="NW"):
        return {
            "structure_id": structure_id,
            "effective_at": datetime(
                2026, 7, 20, effective_hour, 0, tzinfo=timezone.utc
            ),
        }

    def test_valid_withdrawal_passes(self):
        validate_operator_withdrawals(
            [self._withdrawal()], _elements(), HORIZON_START, HORIZON_END,
            STEP_SECONDS,
        )

    def test_unknown_structure_fails_closed(self):
        with pytest.raises(DraftInputError):
            validate_operator_withdrawals(
                [self._withdrawal(structure_id="N2")], _elements(),
                HORIZON_START, HORIZON_END, STEP_SECONDS,
            )

    def test_withdrawal_at_horizon_end_fails_closed(self):
        event = {"structure_id": "NW", "effective_at": HORIZON_END}
        with pytest.raises(DraftInputError):
            validate_operator_withdrawals(
                [event], _elements(), HORIZON_START, HORIZON_END, STEP_SECONDS
            )

    def test_unaligned_withdrawal_fails_closed(self):
        event = {
            "structure_id": "NW",
            "effective_at": datetime(2026, 7, 20, 6, 30, tzinfo=timezone.utc),
        }
        with pytest.raises(DraftInputError):
            validate_operator_withdrawals(
                [event], _elements(), HORIZON_START, HORIZON_END, STEP_SECONDS
            )

    def test_duplicate_withdrawal_fails_closed(self):
        with pytest.raises(DraftInputError):
            validate_operator_withdrawals(
                [self._withdrawal(), self._withdrawal()], _elements(),
                HORIZON_START, HORIZON_END, STEP_SECONDS,
            )


class TestDerivations:
    def test_travel_delay_uses_max_member_and_rounds_up_once(self):
        members = index_response_members(_members())
        # max per reach: R1=700, R2=1150 -> 1850 -> one ceil to 3600
        assert (
            derive_travel_delay_seconds(members, ("R1", "R2"), STEP_SECONDS) == 3600
        )

    def test_travel_delay_zero_stays_zero(self):
        rows = [
            {
                "reach_id": "R1",
                "member": member,
                "delay_seconds": 0.0,
                "loss_fraction": 0.0,
                "capacity_m3s": 1.0,
            }
            for member in ("lower", "nominal", "upper")
        ]
        members = index_response_members(rows)
        assert derive_travel_delay_seconds(members, ("R1",), STEP_SECONDS) == 0

    def test_reach_capacity_is_min_across_members(self):
        members = index_response_members(_members())
        capacities = derive_reach_capacities(members, ("R1", "R2"))
        by_reach = {item.reach_id: item.maximum_flow_m3s for item in capacities}
        assert by_reach == {"R1": 5.0, "R2": 3.0}

    def test_delivery_fractions_bound_member_loss_products(self):
        members = index_response_members(_members())
        minimum, maximum = derive_delivery_fractions(members, ("R1", "R2"))
        assert minimum == pytest.approx(0.9 * 0.95)
        assert maximum == pytest.approx(0.98 * 0.98)

    def test_missing_member_for_used_reach_is_contract_error(self):
        rows = [row for row in _members() if row["member"] != "upper"]
        members = index_response_members(rows)
        with pytest.raises(UpstreamContractError):
            derive_travel_delay_seconds(members, ("R1",), STEP_SECONDS)

    def test_loss_fraction_at_or_above_one_is_contract_error(self):
        rows = _members()
        rows[0] = dict(rows[0], loss_fraction=1.0)
        members = index_response_members(rows)
        with pytest.raises(UpstreamContractError):
            derive_delivery_fractions(members, ("R1", "R2"))

    def test_duplicate_member_row_is_contract_error(self):
        with pytest.raises(UpstreamContractError):
            index_response_members(_members() + [_members()[0]])


class TestComposition:
    def test_composed_problem_carries_derived_values(self):
        problem, derived = _compose()
        assert isinstance(problem, LimitedAdjustmentProblem)
        obligation = problem.obligations[0]
        assert obligation.requirement_id == "req-1"
        assert obligation.gate_id == "G1"
        assert obligation.path_reach_ids == ("R1", "R2")
        assert obligation.travel_delay_seconds == 3600
        assert obligation.minimum_delivery_fraction == pytest.approx(0.855)
        assert obligation.maximum_delivery_fraction == pytest.approx(0.9604)
        assert obligation.maximum_excess_volume_m3 == 100.0
        capacity_by_reach = {
            item.reach_id: item.maximum_flow_m3s for item in problem.reach_capacities
        }
        assert capacity_by_reach == {"R1": 5.0, "R2": 3.0}
        assert derived["obligations"][0]["path_reach_ids"] == ["R1", "R2"]

    def test_composed_problem_satisfies_shipped_optimizer_contract(self):
        problem, _ = _compose()
        plan = optimize_limited_adjustment_plan(
            problem,
            model_step_seconds=STEP_SECONDS,
            max_intermediate_trims=1,
            solver_timeout_seconds=60,
        )
        assert plan.status.value in {"feasible", "infeasible"}

    def test_zero_volume_requirement_is_recorded_not_optimized(self):
        items = [_requirement(), _requirement("req-0", 0.0, "SEC-0")]
        problem, derived = _compose(requirement_items=items)
        assert [o.requirement_id for o in problem.obligations] == ["req-1"]
        assert derived["zero_volume_requirement_ids"] == ["req-0"]

    def test_all_zero_volumes_fail_closed(self):
        with pytest.raises(DraftInputError):
            _compose(
                requirement_items=[_requirement("req-0", 0.0)],
                requirement_policies={},
            )

    def test_missing_binding_for_positive_requirement_fails_closed(self):
        with pytest.raises(DraftInputError):
            _compose(section_bindings={})

    def test_orphan_policy_fails_closed(self):
        policies = {"req-1": _policy(), "req-9": _policy("req-9")}
        with pytest.raises(DraftInputError):
            _compose(requirement_policies=policies)

    def test_missing_policy_fails_closed(self):
        with pytest.raises(DraftInputError):
            _compose(requirement_policies={})

    def test_orphan_binding_fails_closed(self):
        bindings = {"SEC-1": _binding(), "SEC-9": _binding("SEC-9", "N3", "G1")}
        with pytest.raises(DraftInputError):
            _compose(section_bindings=bindings)

    def test_used_path_over_unavailable_reach_fails_closed(self):
        with pytest.raises(DraftInputError):
            _compose(unavailable_reach_ids=["R2"])

    def test_unused_unavailable_reach_does_not_block(self):
        problem, _ = _compose(unavailable_reach_ids=["R9"])
        assert problem.obligations

    def test_incomplete_branch_allocation_fails_closed(self):
        with pytest.raises(DraftInputError):
            _compose(branch_allocations=[])

    def test_candidate_flow_above_envelope_fails_closed(self):
        with pytest.raises(DraftInputError):
            _compose(
                flow_candidates=[
                    {
                        "gate_id": "G1",
                        "target_position_m": 0.5,
                        "source_flow_m3s": 10.5,
                    }
                ]
            )

    def test_candidate_gates_must_exactly_cover_binding_gates(self):
        with pytest.raises(DraftInputError):
            _compose(
                flow_candidates=[
                    {
                        "gate_id": "G9",
                        "target_position_m": 0.5,
                        "source_flow_m3s": 2.0,
                    }
                ]
            )

    def test_pulse_duties_must_exactly_cover_binding_gates(self):
        with pytest.raises(DraftInputError):
            _compose(pulse_duties=[])

    def test_pulse_duty_not_step_multiple_fails_closed(self):
        with pytest.raises(DraftInputError):
            _compose(
                pulse_duties=[
                    {
                        "gate_id": "G1",
                        "minimum_open_seconds": 1800,
                        "maximum_open_seconds": 86400,
                    }
                ]
            )

    def test_horizon_not_whole_step_multiple_fails_closed(self):
        with pytest.raises(DraftInputError):
            _compose(
                horizon_end=datetime(2026, 7, 20, 23, 30, tzinfo=timezone.utc)
            )

    def test_horizon_exceeding_envelope_fails_closed(self):
        with pytest.raises(DraftInputError):
            _compose(
                operating_envelope={**_envelope(), "maximum_horizon_seconds": 3600.0}
            )

    def test_service_date_outside_window_fails_closed(self):
        item = dict(_requirement(), service_date=date(2026, 7, 28))
        with pytest.raises(DraftInputError):
            _compose(requirement_items=[item])

    def test_window_outside_horizon_fails_closed(self):
        item = dict(
            _requirement(),
            window_end=datetime(2026, 7, 21, 6, 0, tzinfo=timezone.utc),
        )
        with pytest.raises(DraftInputError):
            _compose(requirement_items=[item])

    def test_unaligned_window_boundary_fails_closed(self):
        item = dict(
            _requirement(),
            window_end=datetime(2026, 7, 20, 17, 30, tzinfo=timezone.utc),
        )
        with pytest.raises(DraftInputError):
            _compose(requirement_items=[item])

    def test_derived_document_is_json_canonicalizable(self):
        from core.control_plan import canonical_json_text

        _, derived = _compose()
        assert canonical_json_text(derived)
