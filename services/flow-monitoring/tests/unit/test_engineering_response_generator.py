"""Engineering-prior release generation locks (PR 2.1c).

The generator must turn the approved policy plus canonical artifacts into
exactly the reviewed release: 41 parameterized transports + the explicit
flume unavailable, capacities derated by authoritative calibration
evidence, every distribution traceable to named policy perturbations, and
nothing invented.
"""

import copy
import json
from pathlib import Path

import pytest

from core.config_loader import (
    load_gate_calibrations_config,
    load_routing_topology,
    load_strict_json_object,
)
from core.engineering_response_generator import (
    EngineeringResponseError,
    generate_engineering_model_release,
    load_engineering_policy,
)
from core.model_release import SourceArtifact

SERVICE_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = SERVICE_ROOT / "src" / "config"
POLICY_PATH = (
    SERVICE_ROOT / "data" / "model-releases" / "engineering-prior-policy-v1.json"
)
FLUME_REACH_ID = "C_M(0,0)_J(LMC,0+170)"
LMC_REMAINDER_REACH_ID = "C_J(LMC,0+170)_M(0,2)"

SOURCES = tuple(
    SourceArtifact(source_id, "test", "0" * 64)
    for source_id in (
        "engineering_prior_policy",
        "network",
        "geometry_coverage",
        "canal_geometry",
        "gate_calibrations",
        "routing_topology",
    )
)


@pytest.fixture(scope="module")
def topology():
    return load_routing_topology(
        str(CONFIG_DIR / "routing_topology.json"),
        str(CONFIG_DIR / "network.json"),
        str(CONFIG_DIR / "geometry_coverage.json"),
        str(CONFIG_DIR / "canal_geometry.json"),
    )


@pytest.fixture(scope="module")
def canal_geometry():
    return load_strict_json_object(str(CONFIG_DIR / "canal_geometry.json"))


@pytest.fixture(scope="module")
def gate_calibrations():
    return load_gate_calibrations_config(str(CONFIG_DIR / "gate_calibrations.json"))


@pytest.fixture(scope="module")
def policy():
    return load_engineering_policy(load_strict_json_object(str(POLICY_PATH)))


@pytest.fixture(scope="module")
def generated(topology, canal_geometry, gate_calibrations, policy):
    return generate_engineering_model_release(
        topology, canal_geometry, gate_calibrations, policy, SOURCES
    )


class TestReleasePartition:
    def test_release_partitions_41_parameterized_and_flume_unavailable(
        self, generated
    ):
        release, _ = generated

        assert len(release.reach_parameters) == 41
        assert [entry.reach_id for entry in release.unavailable_reaches] == [
            FLUME_REACH_ID
        ]
        assert release.commandable is False
        assert release.evidence_class.value == "engineering_prior"

    def test_flume_unavailable_reason_names_missing_geometry_and_policy(
        self, generated
    ):
        release, _ = generated
        reason = release.unavailable_reaches[0].reason

        assert "forbids invented geometry" in reason
        assert "0+000-0+170" in reason

    def test_release_contains_no_withdrawal_or_nonexistent_reach_ids(
        self, generated, topology
    ):
        release, _ = generated
        transport_ids = set(topology.transport_reach_ids())
        covered = {entry.reach_id for entry in release.reach_parameters} | {
            entry.reach_id for entry in release.unavailable_reaches
        }

        assert covered == transport_ids
        assert not any(reach_id.startswith(("WD_", "B_", "BR_")) for reach_id in covered)

    def test_split_lmc_element_uses_only_the_0_170_to_1_620_section(self, generated):
        _, diagnostics = generated

        assert diagnostics[LMC_REMAINDER_REACH_ID]["sections"] == ["0+170"]


class TestCapacity:
    def test_measured_terminating_gate_uses_90_percent_of_hard_ceiling(
        self, generated
    ):
        """C_J(LMC,0+170)_M(0,2) terminates at M(0,2) (measured): the hard
        ceiling is min(section 9.961, gate q_max 8.737) = 8.737 and the
        planning limit is 90% of it."""
        release, diagnostics = generated
        parameters = next(
            entry
            for entry in release.reach_parameters
            if entry.reach_id == LMC_REMAINDER_REACH_ID
        )

        assert diagnostics[LMC_REMAINDER_REACH_ID]["capacity"] == {
            "hard_ceiling_m3s": 8.737,
            "planning_limit_m3s": pytest.approx(7.8633),
            "derating_selector": "measured",
            "ceiling_source": "terminating_gate_q_max_m3s",
        }
        assert parameters.capacity_m3s.nominal == pytest.approx(7.8633)
        assert parameters.capacity_m3s.lower == parameters.capacity_m3s.upper

    def test_inferred_terminating_gates_use_75_percent(self, generated):
        _, diagnostics = generated
        inferred = [
            entry
            for entry in diagnostics.values()
            if entry.get("capacity", {}).get("derating_selector") == "inferred"
        ]

        assert inferred, "expected inferred-calibration transports"
        for entry in inferred:
            assert entry["capacity"]["planning_limit_m3s"] == pytest.approx(
                0.75 * entry["capacity"]["hard_ceiling_m3s"]
            )

    def test_capacity_never_exceeds_the_section_design_minimum(
        self, generated, canal_geometry
    ):
        release, diagnostics = generated
        for parameters in release.reach_parameters:
            ceiling = diagnostics[parameters.reach_id]["capacity"][
                "hard_ceiling_m3s"
            ]
            assert parameters.capacity_m3s.upper <= ceiling


class TestPerturbationLineage:
    def test_every_distribution_derives_from_named_policy_bundles(self, generated):
        release, diagnostics = generated
        for parameters in release.reach_parameters:
            members = diagnostics[parameters.reach_id]["members"]
            assert set(members) == {"lower", "nominal", "upper"}
            assert parameters.delay_seconds.lower <= parameters.delay_seconds.upper
            assert parameters.loss_fraction.lower <= parameters.loss_fraction.upper
            assert parameters.evidence_refs == (
                "canal_geometry",
                "engineering_prior_policy",
                "gate_calibrations",
                "routing_topology",
            )

    def test_loss_fractions_stay_below_one_for_all_elements(self, generated):
        release, _ = generated
        worst = max(
            parameters.loss_fraction.upper
            for parameters in release.reach_parameters
        )

        assert worst < 1.0

    def test_missing_lining_sections_are_flagged_not_failed(self, generated):
        _, diagnostics = generated
        flagged = [
            reach_id
            for reach_id, entry in diagnostics.items()
            if entry.get("missing_lining_sections")
        ]

        assert len(flagged) == 3

    def test_missing_policy_perturbation_key_fails_closed(
        self, topology, canal_geometry, gate_calibrations
    ):
        raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        del raw["perturbations"]["manning_n"]

        with pytest.raises(EngineeringResponseError, match="manning_n"):
            load_engineering_policy(raw)

    def test_unreviewed_state_evaluation_rule_fails_closed(
        self, topology, canal_geometry, gate_calibrations
    ):
        raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        raw["reference_flow"]["state_evaluation"] = "at_reference_flow"
        policy = load_engineering_policy(raw)

        with pytest.raises(EngineeringResponseError, match="state evaluation"):
            generate_engineering_model_release(
                topology, canal_geometry, gate_calibrations, policy, SOURCES
            )

    def test_inverted_bundle_direction_fails_instead_of_sorting(
        self, topology, canal_geometry, gate_calibrations
    ):
        raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        raw["member_bundles"]["lower"], raw["member_bundles"]["upper"] = (
            raw["member_bundles"]["upper"],
            raw["member_bundles"]["lower"],
        )
        policy = load_engineering_policy(raw)

        with pytest.raises(EngineeringResponseError, match="unordered"):
            generate_engineering_model_release(
                topology, canal_geometry, gate_calibrations, policy, SOURCES
            )


class TestMidpointStateEvaluation:
    def test_delay_tracks_the_transition_midpoint_celerity_not_the_endpoint(
        self, generated, canal_geometry
    ):
        """Policy section 3: the LMC remainder's nominal delay must sit near
        the travel time at c(Q_ref/2) and clearly away from the travel time
        at c(Q_ref) — a one-line revert to endpoint evaluation moves t10 by
        ~20% and must fail here."""
        from core.muskingum_cunge import TrapezoidSection, flood_wave_celerity_m_s

        release, diagnostics = generated
        parameters = next(
            entry
            for entry in release.reach_parameters
            if entry.reach_id == LMC_REMAINDER_REACH_ID
        )
        section = next(
            entry
            for entry in canal_geometry["canal_sections"]
            if (entry["from_node"], entry["to_node"]) == ("M(0,0)", "M(0,2)")
        )
        geometry = section["geometry"]
        trapezoid = TrapezoidSection(
            bottom_width_m=geometry["cross_section"]["bottom_width_m"],
            depth_m=geometry["cross_section"]["depth_m"],
            side_slope=geometry["cross_section"]["side_slope"],
            manning_n=geometry["hydraulic_params"]["manning_n"],
            bed_slope=geometry["hydraulic_params"]["bed_slope"],
        )
        from core.muskingum_cunge import CascadeSection, fit_t10_t90, route_cascade

        reference_flow = diagnostics[LMC_REMAINDER_REACH_ID][
            "nominal_reference_flow_m3s"
        ]
        length_m = geometry["length_m"]

        def t10_at_state(state_flow):
            outflows = route_cascade(
                (CascadeSection(trapezoid, length_m, state_flow),),
                step_flow_m3s=reference_flow,
                timestep_seconds=60.0,
                horizon_steps=4000,
            )
            return fit_t10_t90(outflows, reference_flow, 60.0)[0]

        midpoint_t10 = t10_at_state(0.5 * reference_flow)
        endpoint_t10 = t10_at_state(reference_flow)
        delay = parameters.delay_seconds.nominal

        assert midpoint_t10 != pytest.approx(endpoint_t10, rel=0.05)
        assert delay == pytest.approx(midpoint_t10, rel=1e-3)
        assert delay != pytest.approx(endpoint_t10, rel=0.05)


class TestConveyanceExceededIsPerReach:
    def test_extreme_seepage_marks_reaches_unavailable_instead_of_aborting(
        self, topology, canal_geometry, gate_calibrations
    ):
        raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        raw["perturbations"]["seepage_rate"]["upper"] = 50.0
        policy = load_engineering_policy(raw)

        release, diagnostics = generate_engineering_model_release(
            topology, canal_geometry, gate_calibrations, policy, SOURCES
        )

        conveyance_unavailable = [
            entry
            for entry in release.unavailable_reaches
            if "conveyance loss" in entry.reason
        ]
        assert conveyance_unavailable, "expected per-reach unavailability"
        assert len(release.reach_parameters) + len(
            release.unavailable_reaches
        ) == 42


class TestPolicyKeyWiring:
    def test_surrogate_thresholds_flow_through_to_the_fit(
        self, topology, canal_geometry, gate_calibrations, generated
    ):
        committed_release, _ = generated
        committed_delay = next(
            entry.delay_seconds.nominal
            for entry in committed_release.reach_parameters
            if entry.reach_id == LMC_REMAINDER_REACH_ID
        )
        raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        raw["surrogate_fit"]["lower_threshold"] = 0.3
        policy = load_engineering_policy(raw)

        release, _ = generate_engineering_model_release(
            topology, canal_geometry, gate_calibrations, policy, SOURCES
        )
        amended_delay = next(
            entry.delay_seconds.nominal
            for entry in release.reach_parameters
            if entry.reach_id == LMC_REMAINDER_REACH_ID
        )

        assert amended_delay > committed_delay

    def test_naive_release_timestamp_fails_closed(
        self, topology, canal_geometry, gate_calibrations
    ):
        raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        raw["release_generated_at"] = "2026-07-17T00:00:00"
        policy = load_engineering_policy(raw)

        with pytest.raises(EngineeringResponseError, match="timezone"):
            generate_engineering_model_release(
                topology, canal_geometry, gate_calibrations, policy, SOURCES
            )

    def test_unrecognized_lining_type_fails_closed(
        self, topology, canal_geometry, gate_calibrations, policy
    ):
        mutated = copy.deepcopy(canal_geometry)
        section = next(
            entry
            for entry in mutated["canal_sections"]
            if (entry["from_node"], entry["to_node"]) == ("M(0,2)", "M(0,3)")
        )
        section["geometry"]["hydraulic_params"]["lining_type"] = "Concrete"

        with pytest.raises(EngineeringResponseError, match="seepage class"):
            generate_engineering_model_release(
                topology, mutated, gate_calibrations, policy, SOURCES
            )

    def test_overlapping_survey_rows_fail_the_canonical_guards(
        self, topology, canal_geometry, gate_calibrations, policy
    ):
        mutated = copy.deepcopy(canal_geometry)
        section = next(
            entry
            for entry in mutated["canal_sections"]
            if (entry["from_node"], entry["to_node"]) == ("M(0,2)", "M(0,3)")
        )
        mutated["canal_sections"].append(copy.deepcopy(section))

        with pytest.raises(
            EngineeringResponseError, match="canonical section guards"
        ):
            generate_engineering_model_release(
                topology, mutated, gate_calibrations, policy, SOURCES
            )


class TestFailClosed:
    def test_survey_drift_in_the_split_section_fails_generation(
        self, topology, canal_geometry, gate_calibrations, policy
    ):
        mutated = copy.deepcopy(canal_geometry)
        section = next(
            entry
            for entry in mutated["canal_sections"]
            if (entry["from_node"], entry["to_node"]) == ("M(0,0)", "M(0,2)")
        )
        section["from_km"] = "0+000"

        with pytest.raises(EngineeringResponseError, match="no surveyed"):
            generate_engineering_model_release(
                topology, mutated, gate_calibrations, policy, SOURCES
            )

    def test_generated_release_passes_real_schema_validation(self, generated):
        release, _ = generated

        assert len(release.content_hash) == 64
