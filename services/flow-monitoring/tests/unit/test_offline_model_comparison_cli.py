"""Offline comparison CLI contract: the golden gate must equal the startup
gate. Cases run against the real committed canonical artifacts; reference
expectations come from an independent flow-fraction traversal, never from
the candidate engine itself."""

import importlib.util
import json
import shutil
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.config_loader import file_sha256, load_routing_topology
from core.demand_contract import content_hash
from core.model_release import load_hydraulic_model_release
from core.model_snapshot import build_model_snapshot
from core.network_transient import BranchAllocation, GateFlowEvent
from core.offline_model_comparison import (
    OfflineModelComparisonError,
    build_offline_simulation_case,
    write_offline_simulation_case,
)
from core.reach_response import ResponseMember, reach_responses_from_model_release
from core.routing_topology import (
    RoutingElement,
    RoutingGeometryStatus,
    RoutingRole,
    build_routing_topology,
)

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "compare_offline_hydraulic_model.py"
SPEC = importlib.util.spec_from_file_location("offline_comparison_cli", SCRIPT_PATH)
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)

CONFIG_DIR = SERVICE_ROOT / "src" / "config"
CANONICAL_FILES = (
    "network.json",
    "canal_geometry.json",
    "gate_calibrations.json",
    "geometry_coverage.json",
    "routing_topology.json",
)

START = datetime(2026, 7, 16, tzinfo=timezone.utc)
DT_S = 60.0
RELEASE_ID = "engineering-prior-canonical-cli-v1"
SOURCE_FLOW_M3S = 2.0

CANON_TOPOLOGY = load_routing_topology(
    str(CONFIG_DIR / "routing_topology.json"),
    str(CONFIG_DIR / "network.json"),
    str(CONFIG_DIR / "geometry_coverage.json"),
    str(CONFIG_DIR / "canal_geometry.json"),
)


def _write_json(path, payload):
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _uniform_allocations(topology):
    children = defaultdict(list)
    for upstream, downstream in topology.routing_edges():
        children[upstream].append(downstream)
    return tuple(
        BranchAllocation(upstream, downstream, 1.0 / len(children[upstream]))
        for upstream, downstream in topology.routing_edges()
        if len(children[upstream]) > 1
    )


def _expected_transport_flows(topology, source_flow_m3s):
    """Independent oracle: propagate uniform-fraction flow down the routing
    tree (valid for zero delay/loss and ample capacity)."""
    children = defaultdict(list)
    for element in topology.elements:
        children[element.upstream_node_id].append(element)
    flows = {}
    node_flow = {"S": source_flow_m3s}
    queue = ["S"]
    while queue:
        node = queue.pop(0)
        branch_count = len(children.get(node, []))
        for element in children.get(node, []):
            fraction = 1.0 / branch_count if branch_count > 1 else 1.0
            flow = node_flow[node] * fraction
            if element.role is RoutingRole.TRANSPORT:
                flows[element.element_id] = flow
            node_flow[element.downstream_node_id] = flow
            queue.append(element.downstream_node_id)
    return flows


def _model_release_payload(topology):
    payload = {
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "generated_at": "2026-07-16T00:00:00Z",
        "evidence_class": "engineering_prior",
        "commandable": False,
        "lineage": {
            "generator": "canonical-cli-contract-fixture",
            "generator_version": "1.0.0",
            "sources": [
                {
                    "source_id": "workbook",
                    "version": "v3",
                    "sha256": topology.source_sha256,
                }
            ],
        },
        "operating_envelope": {
            "minimum_flow_m3s": 0.0,
            "maximum_flow_m3s": 100.0,
            "minimum_timestep_seconds": DT_S,
            "maximum_timestep_seconds": DT_S,
            "maximum_horizon_seconds": 2 * DT_S,
        },
        "reach_parameters": [
            {
                "reach_id": reach_id,
                "delay_seconds": {"lower": 0.0, "nominal": 0.0, "upper": 0.0},
                "loss_fraction": {"lower": 0.0, "nominal": 0.0, "upper": 0.0},
                "dispersion_seconds": {
                    "lower": 0.0,
                    "nominal": 0.0,
                    "upper": 0.0,
                },
                "capacity_m3s": {
                    "lower": 100.0,
                    "nominal": 100.0,
                    "upper": 100.0,
                },
                "evidence_refs": ["workbook"],
            }
            for reach_id in sorted(topology.transport_reach_ids())
        ],
        "unavailable_reaches": [],
    }
    return {**payload, "content_hash": content_hash(payload)}


def _reference_payload(case, topology, perturb_reach_id=None):
    flows = _expected_transport_flows(topology, SOURCE_FLOW_M3S)
    samples = sorted(
        (
            {
                "sampled_at": sampled_at,
                "reach_id": reach_id,
                "outflow_m3s": (
                    flow + 0.5
                    if reach_id == perturb_reach_id
                    and sampled_at == "2026-07-16T00:01:00Z"
                    else flow
                ),
            }
            for reach_id in topology.transport_reach_ids()
            for sampled_at, flow in (
                ("2026-07-16T00:01:00Z", flows[reach_id]),
                ("2026-07-16T00:02:00Z", 0.0),
            )
        ),
        key=lambda sample: (sample["reach_id"], sample["sampled_at"]),
    )
    payload = {
        "schema_version": 2,
        "case_id": case.case_id,
        "case_content_hash": case.content_hash,
        "evidence_class": "offline_high_fidelity_simulation",
        "sample_semantics": "mean_outflow_m3s_for_interval_ending_at_sampled_at",
        "simulator": {
            "simulator_id": "independent-fraction-traversal",
            "simulator_version": "1.0.0",
            "source_sha256": "3" * 64,
        },
        "validates_real_canal_behavior": False,
        "samples": samples,
    }
    return {**payload, "content_hash": content_hash(payload)}


def _artifacts(
    tmp_path,
    perturb_reach_id=None,
    case_topology=None,
    geometry_payload=None,
    routing_artifact_mutate=None,
):
    paths = {}
    for filename in CANONICAL_FILES:
        target = tmp_path / filename
        shutil.copyfile(CONFIG_DIR / filename, target)
        paths[filename] = target
    if geometry_payload is not None:
        _write_json(paths["canal_geometry.json"], geometry_payload)
    if routing_artifact_mutate is not None:
        artifact = json.loads(
            paths["routing_topology.json"].read_text(encoding="utf-8")
        )
        routing_artifact_mutate(artifact)
        _write_json(paths["routing_topology.json"], artifact)

    release_path = tmp_path / "model_release.json"
    case_path = tmp_path / "case.json"
    reference_path = tmp_path / "reference.json"
    report_path = tmp_path / "report.json"
    canonical_case_path = tmp_path / "canonical-case.json"

    topology = case_topology if case_topology is not None else CANON_TOPOLOGY
    release_payload = _model_release_payload(CANON_TOPOLOGY)
    _write_json(release_path, release_payload)
    release = load_hydraulic_model_release(
        str(release_path), CANON_TOPOLOGY.transport_reach_ids()
    )
    config_sha256 = {
        "network": file_sha256(str(paths["network.json"])),
        "canal_geometry": file_sha256(str(paths["canal_geometry.json"])),
        "gate_calibrations": file_sha256(str(paths["gate_calibrations.json"])),
        "geometry_coverage": file_sha256(str(paths["geometry_coverage.json"])),
        "routing_topology": file_sha256(str(paths["routing_topology.json"])),
    }
    responses = reach_responses_from_model_release(release)
    snapshot = build_model_snapshot(
        CANON_TOPOLOGY,
        responses,
        release,
        config_sha256,
        actuation_approved=False,
    )
    case = build_offline_simulation_case(
        case_id="cli-canonical-pulse-v1",
        model_snapshot_id=snapshot["snapshot_id"],
        model_release_id=release.release_id,
        model_release_content_hash=release.content_hash,
        member=ResponseMember.NOMINAL,
        config_sha256=config_sha256,
        routing_topology=topology,
        starts_at=START,
        ends_at=START + timedelta(seconds=2 * DT_S),
        timestep_seconds=DT_S,
        gate_events=(
            GateFlowEvent("S", START, SOURCE_FLOW_M3S),
            GateFlowEvent("S", START + timedelta(seconds=DT_S), 0.0),
        ),
        requirements=(),
        branch_allocations=_uniform_allocations(topology),
    )
    write_offline_simulation_case(case_path, case)
    _write_json(
        reference_path,
        _reference_payload(case, CANON_TOPOLOGY, perturb_reach_id),
    )
    return {
        "network": paths["network.json"],
        "geometry": paths["canal_geometry.json"],
        "calibrations": paths["gate_calibrations.json"],
        "geometry_coverage": paths["geometry_coverage.json"],
        "routing_topology": paths["routing_topology.json"],
        "release": release_path,
        "case": case_path,
        "reference": reference_path,
        "report": report_path,
        "canonical_case": canonical_case_path,
    }


def _argv(artifacts):
    return [
        "--network",
        str(artifacts["network"]),
        "--canal-geometry",
        str(artifacts["geometry"]),
        "--gate-calibrations",
        str(artifacts["calibrations"]),
        "--geometry-coverage",
        str(artifacts["geometry_coverage"]),
        "--routing-topology",
        str(artifacts["routing_topology"]),
        "--model-release",
        str(artifacts["release"]),
        "--case",
        str(artifacts["case"]),
        "--reference",
        str(artifacts["reference"]),
        "--report",
        str(artifacts["report"]),
        "--canonical-case-output",
        str(artifacts["canonical_case"]),
        "--maximum-flow-error-m3s",
        "0.1",
        "--maximum-volume-error-m3",
        "1.0",
        "--maximum-arrival-time-error-seconds",
        "0.0",
        "--arrival-flow-threshold-m3s",
        "0.01",
    ]


def test_cli_runs_canonical_topology_and_writes_passing_golden_report(tmp_path):
    artifacts = _artifacts(tmp_path)

    exit_code = CLI.main(_argv(artifacts))
    report = json.loads(artifacts["report"].read_text(encoding="utf-8"))
    canonical_case = json.loads(
        artifacts["canonical_case"].read_text(encoding="utf-8")
    )

    assert (exit_code, report["status"], report["summary"]) == (
        0,
        "passed",
        {"compared_reaches": 42, "compared_samples": 84, "failing_reaches": []},
    )
    assert canonical_case == json.loads(
        artifacts["case"].read_text(encoding="utf-8")
    )


def test_cli_writes_failed_report_and_returns_nonzero_for_golden_drift(tmp_path):
    perturbed = "C_J(LMC,0+170)_M(0,2)"
    artifacts = _artifacts(tmp_path, perturb_reach_id=perturbed)

    exit_code = CLI.main(_argv(artifacts))
    report = json.loads(artifacts["report"].read_text(encoding="utf-8"))

    assert (exit_code, report["status"], report["summary"]["failing_reaches"]) == (
        1,
        "failed",
        [perturbed],
    )


def test_cli_rejects_config_hash_drift_before_simulation(tmp_path):
    artifacts = _artifacts(tmp_path)
    artifacts["geometry"].write_text('{"fixture":"drift"}\n', encoding="utf-8")

    with pytest.raises(OfflineModelComparisonError, match="config_sha256"):
        CLI.main(_argv(artifacts))
    assert not artifacts["canonical_case"].exists()


def test_cli_rejects_hash_matching_but_invalid_geometry_schema(tmp_path):
    artifacts = _artifacts(tmp_path, geometry_payload={"invalid": True})

    with pytest.raises(OfflineModelComparisonError, match="canal geometry"):
        CLI.main(_argv(artifacts))


def test_cli_rejects_routing_artifact_startup_would_reject(tmp_path):
    def drop_summary(artifact):
        del artifact["summary"]

    artifacts = _artifacts(tmp_path, routing_artifact_mutate=drop_summary)

    with pytest.raises(OfflineModelComparisonError, match="startup gate"):
        CLI.main(_argv(artifacts))
    assert not artifacts["canonical_case"].exists()


def test_cli_rejects_case_exported_against_a_different_topology(tmp_path):
    synthetic = build_routing_topology(
        tuple(
            RoutingElement(
                element_id=f"C_{upstream}_{downstream}",
                upstream_node_id=upstream,
                downstream_node_id=downstream,
                role=RoutingRole.TRANSPORT,
                canonical_edges=((upstream, downstream),),
                canal=None,
                span_m=100.0,
                geometry_status=RoutingGeometryStatus.SURVEYED,
                located_at_km=None,
            )
            for upstream, downstream in (("S", "M(0,0)"), ("M(0,0)", "M(0,2)"))
        )
    )
    artifacts = _artifacts(tmp_path, case_topology=synthetic)

    with pytest.raises(
        OfflineModelComparisonError, match="does not match the exported"
    ):
        CLI.main(_argv(artifacts))


def test_cli_rejects_output_paths_that_overwrite_input_artifacts(tmp_path):
    artifacts = _artifacts(tmp_path)
    original_case = artifacts["case"].read_text(encoding="utf-8")
    argv = _argv(artifacts)
    argv[argv.index("--report") + 1] = str(artifacts["case"])

    with pytest.raises(OfflineModelComparisonError, match="output paths"):
        CLI.main(argv)

    assert artifacts["case"].read_text(encoding="utf-8") == original_case
