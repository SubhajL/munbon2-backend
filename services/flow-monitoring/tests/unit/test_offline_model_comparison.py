import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.demand_contract import content_hash
from core.network_transient import (
    BranchAllocation,
    GateFlowEvent,
    SectionRequirement,
    simulate_network_timeline,
)
from core.offline_model_comparison import (
    ComparisonStatus,
    ComparisonTolerance,
    OfflineModelComparisonError,
    build_golden_comparison_report,
    build_offline_simulation_case,
    golden_comparison_report_payload,
    load_offline_reference_result,
    load_offline_simulation_case,
    offline_simulation_case_payload,
    write_golden_comparison_report,
    write_offline_simulation_case,
)
from core.reach_response import ReachResponse, ReachState, ResponseMember

START = datetime(2026, 7, 16, tzinfo=timezone.utc)
DT_S = 60.0
EDGES = (("S", "A"), ("A", "B"))
CONFIG_SHA256 = {
    "network": "a" * 64,
    "canal_geometry": "b" * 64,
    "gate_calibrations": "c" * 64,
}
MODEL_SNAPSHOT_ID = "d" * 64
MODEL_RELEASE_HASH = "e" * 64
REFERENCE_SOURCE_HASH = "f" * 64
CANDIDATE_SOURCE_HASH = "9" * 64
CANONICAL_NETWORK = (
    Path(__file__).resolve().parents[2] / "src" / "config" / "network.json"
)


def _response(upstream: str, downstream: str) -> ReachResponse:
    return ReachResponse(
        model_release_id="engineering-prior-2569-v1",
        reach_id=f"C_{upstream}_{downstream}",
        member=ResponseMember.NOMINAL,
        delay_seconds=0.0,
        loss_fraction=0.0,
        dispersion_seconds=0.0,
        capacity_m3s=5.0,
        minimum_timestep_seconds=DT_S,
        maximum_timestep_seconds=DT_S,
    )


def _timeline():
    responses = tuple(_response(*edge) for edge in EDGES)
    return simulate_network_timeline(
        EDGES,
        responses,
        tuple(
            ReachState(response.model_release_id, response.reach_id, response.member)
            for response in responses
        ),
        (
            GateFlowEvent("S", START, 2.0),
            GateFlowEvent("S", START + timedelta(seconds=DT_S), 0.0),
        ),
        (),
        (),
        START,
        START + timedelta(seconds=2 * DT_S),
        DT_S,
    )


def _case(**overrides):
    values = {
        "case_id": "serial-pulse-v1",
        "model_snapshot_id": MODEL_SNAPSHOT_ID,
        "model_release_id": "engineering-prior-2569-v1",
        "model_release_content_hash": MODEL_RELEASE_HASH,
        "member": ResponseMember.NOMINAL,
        "config_sha256": CONFIG_SHA256,
        "network_edges": EDGES,
        "starts_at": START,
        "ends_at": START + timedelta(seconds=2 * DT_S),
        "timestep_seconds": DT_S,
        "gate_events": (
            GateFlowEvent("S", START, 2.0),
            GateFlowEvent("S", START + timedelta(seconds=DT_S), 0.0),
        ),
        "requirements": (),
        "branch_allocations": (),
    }
    values.update(overrides)
    return build_offline_simulation_case(**values)


def _reference_payload(case, samples=None, source_sha256=REFERENCE_SOURCE_HASH):
    if samples is None:
        samples = [
            {
                "sampled_at": sampled_at,
                "reach_id": reach_id,
                "outflow_m3s": outflow_m3s,
            }
            for reach_id in ("C_A_B", "C_S_A")
            for sampled_at, outflow_m3s in (
                ("2026-07-16T00:01:00Z", 2.0),
                ("2026-07-16T00:02:00Z", 0.0),
            )
        ]
    payload = {
        "schema_version": 1,
        "case_id": case.case_id,
        "case_content_hash": case.content_hash,
        "evidence_class": "offline_high_fidelity_simulation",
        "sample_semantics": "mean_outflow_m3s_for_interval_ending_at_sampled_at",
        "simulator": {
            "simulator_id": "hec-ras-offline",
            "simulator_version": "6.6",
            "source_sha256": source_sha256,
        },
        "validates_real_canal_behavior": False,
        "samples": samples,
    }
    return {**payload, "content_hash": content_hash(payload)}


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _load_reference(tmp_path, case, samples=None, source_sha256=REFERENCE_SOURCE_HASH):
    path = tmp_path / "reference.json"
    _write_json(path, _reference_payload(case, samples, source_sha256))
    return load_offline_reference_result(path, case)


def _tolerance(**overrides):
    values = {
        "maximum_flow_error_m3s": 0.1,
        "maximum_volume_error_m3": 1.0,
        "maximum_arrival_time_error_seconds": 0.0,
        "arrival_flow_threshold_m3s": 0.01,
    }
    values.update(overrides)
    return ComparisonTolerance(**values)


def test_offline_case_export_is_deterministic_and_round_trips_strictly(tmp_path):
    case = _case(
        network_edges=tuple(reversed(EDGES)),
        gate_events=tuple(
            reversed(
                (
                    GateFlowEvent("S", START, 2.0),
                    GateFlowEvent("S", START + timedelta(seconds=DT_S), 0.0),
                )
            )
        ),
    )
    path = tmp_path / "case.json"

    write_offline_simulation_case(path, case)
    loaded = load_offline_simulation_case(path)
    payload = offline_simulation_case_payload(loaded)

    assert payload == {
        "schema_version": 1,
        "case_id": "serial-pulse-v1",
        "model_snapshot_id": MODEL_SNAPSHOT_ID,
        "model_release_id": "engineering-prior-2569-v1",
        "model_release_content_hash": MODEL_RELEASE_HASH,
        "member": "nominal",
        "sample_semantics": "mean_outflow_m3s_for_interval_ending_at_sampled_at",
        "config_sha256": CONFIG_SHA256,
        "network_edges": [
            {
                "reach_id": "C_A_B",
                "upstream_node_id": "A",
                "downstream_node_id": "B",
            },
            {
                "reach_id": "C_S_A",
                "upstream_node_id": "S",
                "downstream_node_id": "A",
            },
        ],
        "initial_state_kind": "dry",
        "starts_at": "2026-07-16T00:00:00Z",
        "ends_at": "2026-07-16T00:02:00Z",
        "timestep_seconds": 60.0,
        "gate_events": [
            {
                "node_id": "S",
                "effective_at": "2026-07-16T00:00:00Z",
                "flow_m3s": 2.0,
            },
            {
                "node_id": "S",
                "effective_at": "2026-07-16T00:01:00Z",
                "flow_m3s": 0.0,
            },
        ],
        "requirements": [],
        "branch_allocations": [],
        "content_hash": case.content_hash,
    }
    assert loaded == case


@pytest.mark.parametrize(
    "overrides,match",
    [
        ({"network_edges": list(EDGES)}, "immutable tuple"),
        ({"gate_events": [GateFlowEvent("S", START, 1.0)]}, "immutable tuple"),
        (
            {"gate_events": (GateFlowEvent("A", START, 1.0),)},
            "network root",
        ),
        ({"config_sha256": {"network": "a" * 64}}, "exactly"),
        ({"ends_at": START + timedelta(seconds=30)}, "aligned"),
    ],
)
def test_offline_case_export_fails_closed_on_invalid_contract(overrides, match):
    with pytest.raises(OfflineModelComparisonError, match=match):
        _case(**overrides)


def test_offline_case_export_requires_complete_explicit_branch_allocations():
    edges = (("S", "A"), ("A", "B"), ("A", "C"))

    with pytest.raises(OfflineModelComparisonError, match="branch allocation"):
        _case(network_edges=edges)

    case = _case(
        network_edges=edges,
        branch_allocations=(
            BranchAllocation("A", "B", 0.5),
            BranchAllocation("A", "C", 0.5),
        ),
    )

    assert tuple(
        (allocation.upstream_node_id, allocation.downstream_node_id)
        for allocation in case.branch_allocations
    ) == (("A", "B"), ("A", "C"))


def test_offline_case_export_rejects_colliding_derived_reach_ids():
    edges = (("S", "A"), ("S", "A_B"), ("A", "B_C"), ("A_B", "C"))

    with pytest.raises(OfflineModelComparisonError, match="reach_id"):
        _case(
            network_edges=edges,
            branch_allocations=(
                BranchAllocation("S", "A", 0.5),
                BranchAllocation("S", "A_B", 0.5),
            ),
        )


def test_offline_case_export_normalizes_numeric_and_timezone_equivalents(tmp_path):
    local_start = START.astimezone(timezone(timedelta(hours=7)))
    case = _case(
        starts_at=local_start,
        ends_at=local_start + timedelta(seconds=2 * DT_S),
        timestep_seconds=60,
        gate_events=(
            GateFlowEvent("S", local_start, 2),
            GateFlowEvent("S", local_start + timedelta(seconds=DT_S), 0),
        ),
        requirements=(
            SectionRequirement(
                "requirement-1",
                "section-1",
                "A",
                local_start,
                local_start + timedelta(seconds=DT_S),
                60,
                1,
                0,
            ),
        ),
    )
    path = tmp_path / "normalized-case.json"

    write_offline_simulation_case(path, case)

    assert load_offline_simulation_case(path) == case


def test_offline_case_export_rejects_requirement_ids_that_collide_after_normalization():
    requirements = tuple(
        SectionRequirement(
            requirement_id,
            f"section-{index}",
            "A",
            START,
            START + timedelta(seconds=DT_S),
            60.0,
            1.0,
            0.0,
        )
        for index, requirement_id in enumerate(
            ("requirement-1", " requirement-1 "), start=1
        )
    )

    with pytest.raises(OfflineModelComparisonError, match="duplicate requirement_id"):
        _case(requirements=requirements)


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda payload: payload.update({"unexpected": True}), "unexpected"),
        (lambda payload: payload.update({"content_hash": "0" * 64}), "drift"),
        (
            lambda payload: payload["gate_events"][0].update(
                {"flow_m3s": float("nan")}
            ),
            "strict JSON",
        ),
    ],
)
def test_offline_case_import_rejects_unknown_hash_drift_and_nonfinite_json(
    tmp_path, mutation, match
):
    payload = offline_simulation_case_payload(_case())
    mutation(payload)
    path = tmp_path / "invalid-case.json"
    _write_json(path, payload)

    with pytest.raises(OfflineModelComparisonError, match=match):
        load_offline_simulation_case(path)


def test_offline_reference_import_requires_exact_reach_time_coverage(tmp_path):
    case = _case()
    payload = _reference_payload(case)
    payload["samples"].pop()
    unhashed = {key: value for key, value in payload.items() if key != "content_hash"}
    payload["content_hash"] = content_hash(unhashed)
    path = tmp_path / "missing-sample.json"
    _write_json(path, payload)

    with pytest.raises(OfflineModelComparisonError, match="sample coverage"):
        load_offline_reference_result(path, case)


def test_offline_interchange_covers_all_59_canonical_reaches(tmp_path):
    network = json.loads(CANONICAL_NETWORK.read_text(encoding="utf-8"))
    edges = tuple(tuple(edge) for edge in network["edges"])
    child_counts = {
        upstream: sum(1 for parent, _ in edges if parent == upstream)
        for upstream, _ in edges
    }
    allocations = tuple(
        BranchAllocation(upstream, downstream, 1.0 / child_counts[upstream])
        for upstream, downstream in edges
        if child_counts[upstream] > 1
    )
    case = _case(
        network_edges=edges,
        ends_at=START + timedelta(seconds=DT_S),
        gate_events=(),
        branch_allocations=allocations,
    )
    samples = [
        {
            "sampled_at": "2026-07-16T00:01:00Z",
            "reach_id": f"C_{upstream}_{downstream}",
            "outflow_m3s": 0.0,
        }
        for upstream, downstream in case.network_edges
    ]
    reference = _load_reference(tmp_path, case, samples)

    assert (
        len(offline_simulation_case_payload(case)["network_edges"]),
        len(reference.samples),
    ) == (59, 59)


@pytest.mark.parametrize(
    "mutation,match",
    [
        (
            lambda payload: payload.update({"validates_real_canal_behavior": True}),
            "must be false",
        ),
        (lambda payload: payload.update({"evidence_class": "measured"}), "evidence"),
        (lambda payload: payload.update({"case_content_hash": "0" * 64}), "case"),
        (lambda payload: payload.update({"content_hash": "0" * 64}), "drift"),
    ],
)
def test_offline_reference_import_rejects_false_authority_or_lineage_drift(
    tmp_path, mutation, match
):
    case = _case()
    payload = _reference_payload(case)
    mutation(payload)
    if match != "drift":
        unhashed = {
            key: value for key, value in payload.items() if key != "content_hash"
        }
        payload["content_hash"] = content_hash(unhashed)
    path = tmp_path / "invalid-reference.json"
    _write_json(path, payload)

    with pytest.raises(OfflineModelComparisonError, match=match):
        load_offline_reference_result(path, case)


def test_golden_comparison_passes_exact_independent_serial_pulse(tmp_path):
    case = _case()
    reference = _load_reference(tmp_path, case)

    report = build_golden_comparison_report(
        case, _timeline(), reference, _tolerance(), CANDIDATE_SOURCE_HASH
    )

    assert (
        report.status,
        report.software_verification_only,
        report.validates_real_canal_behavior,
        report.compared_reaches,
        report.compared_samples,
        report.failing_reaches,
    ) == (ComparisonStatus.PASSED, True, False, 2, 4, ())
    assert golden_comparison_report_payload(report)["sample_semantics"] == (
        "mean_outflow_m3s_for_interval_ending_at_sampled_at"
    )
    assert report.content_hash == (
        "de993273df36fa996533c2a202b4cc6a19c7e6e5921060c154000729e100f6d7"
    )
    assert tuple(
        (
            comparison.reach_id,
            comparison.maximum_absolute_flow_error_m3s,
            comparison.root_mean_square_flow_error_m3s,
            comparison.candidate_volume_m3,
            comparison.reference_volume_m3,
            comparison.absolute_volume_error_m3,
            comparison.arrival_time_error_seconds,
            comparison.passed,
        )
        for comparison in report.reach_comparisons
    ) == (
        ("C_A_B", 0.0, 0.0, 120.0, 120.0, 0.0, 0.0, True),
        ("C_S_A", 0.0, 0.0, 120.0, 120.0, 0.0, 0.0, True),
    )


def test_golden_comparison_fails_and_itemizes_biased_reach(tmp_path):
    case = _case()
    samples = _reference_payload(case)["samples"]
    samples[0]["outflow_m3s"] = 1.5
    reference = _load_reference(tmp_path, case, samples)

    report = build_golden_comparison_report(
        case, _timeline(), reference, _tolerance(), CANDIDATE_SOURCE_HASH
    )

    assert (report.status, report.failing_reaches) == (
        ComparisonStatus.FAILED,
        ("C_A_B",),
    )
    assert report.reach_comparisons[0] == replace(
        report.reach_comparisons[0],
        maximum_absolute_flow_error_m3s=0.5,
        root_mean_square_flow_error_m3s=pytest.approx(0.3535533905932738),
        reference_volume_m3=90.0,
        absolute_volume_error_m3=30.0,
        passed=False,
    )


def test_golden_comparison_detects_arrival_disagreement_separately(tmp_path):
    case = _case()
    samples = _reference_payload(case)["samples"]
    samples[0]["outflow_m3s"] = 0.0
    samples[1]["outflow_m3s"] = 2.0
    reference = _load_reference(tmp_path, case, samples)

    report = build_golden_comparison_report(
        case,
        _timeline(),
        reference,
        _tolerance(
            maximum_flow_error_m3s=3.0,
            maximum_volume_error_m3=1.0,
            maximum_arrival_time_error_seconds=10.0,
        ),
        CANDIDATE_SOURCE_HASH,
    )

    comparison = report.reach_comparisons[0]
    assert (
        comparison.candidate_arrival_at,
        comparison.reference_arrival_at,
        comparison.arrival_time_error_seconds,
        comparison.passed,
    ) == (
        START + timedelta(seconds=DT_S),
        START + timedelta(seconds=2 * DT_S),
        DT_S,
        False,
    )


@pytest.mark.parametrize(
    "candidate,match",
    [
        (replace(_timeline(), model_release_id="drift"), "model release"),
        (replace(_timeline(), member=ResponseMember.UPPER), "member"),
        (replace(_timeline(), timestep_seconds=30.0), "timestep"),
        (replace(_timeline(), steps=_timeline().steps[:-1]), "step intervals"),
        (
            replace(
                _timeline(),
                steps=(
                    replace(
                        _timeline().steps[0],
                        starts_at=START - timedelta(seconds=DT_S),
                    ),
                    *_timeline().steps[1:],
                ),
            ),
            "step intervals",
        ),
    ],
)
def test_golden_comparison_rejects_candidate_lineage_or_coverage_drift(
    tmp_path, candidate, match
):
    case = _case()
    reference = _load_reference(tmp_path, case)

    with pytest.raises(OfflineModelComparisonError, match=match):
        build_golden_comparison_report(
            case, candidate, reference, _tolerance(), CANDIDATE_SOURCE_HASH
        )


@pytest.mark.parametrize("bad_outflow_m3s", [float("nan"), -1.0])
def test_golden_comparison_rejects_nonfinite_or_negative_candidate_outflow(
    tmp_path, bad_outflow_m3s
):
    case = _case()
    reference = _load_reference(tmp_path, case)
    candidate = _timeline()
    first_step = candidate.steps[0]
    candidate = replace(
        candidate,
        steps=(
            replace(
                first_step,
                reaches=(
                    replace(first_step.reaches[0], outflow_m3s=bad_outflow_m3s),
                    *first_step.reaches[1:],
                ),
            ),
            *candidate.steps[1:],
        ),
    )

    with pytest.raises(OfflineModelComparisonError, match="outflow_m3s"):
        build_golden_comparison_report(
            case, candidate, reference, _tolerance(), CANDIDATE_SOURCE_HASH
        )


def test_golden_report_serialization_is_content_addressed_and_canonical(tmp_path):
    case = _case()
    reference = _load_reference(tmp_path, case)
    report = build_golden_comparison_report(
        case, _timeline(), reference, _tolerance(), CANDIDATE_SOURCE_HASH
    )
    path = tmp_path / "report.json"

    write_golden_comparison_report(path, report)
    stored = json.loads(path.read_text(encoding="utf-8"))

    assert stored == golden_comparison_report_payload(report)
    unhashed = {key: value for key, value in stored.items() if key != "content_hash"}
    assert stored["content_hash"] == content_hash(unhashed)


def test_golden_comparison_rejects_reference_from_candidate_source(tmp_path):
    case = _case()
    reference = _load_reference(tmp_path, case, source_sha256=CANDIDATE_SOURCE_HASH)

    with pytest.raises(OfflineModelComparisonError, match="independent"):
        build_golden_comparison_report(
            case,
            _timeline(),
            reference,
            _tolerance(),
            CANDIDATE_SOURCE_HASH,
        )
