import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.config_loader import file_sha256
from core.demand_contract import canonical_json, content_hash
from core.model_release import load_hydraulic_model_release
from core.model_snapshot import build_model_snapshot
from core.network_transient import GateFlowEvent
from core.offline_model_comparison import (
    OfflineModelComparisonError,
    build_offline_simulation_case,
    write_offline_simulation_case,
)
from core.reach_response import ResponseMember, reach_responses_from_model_release

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "compare_offline_hydraulic_model.py"
SPEC = importlib.util.spec_from_file_location("offline_comparison_cli", SCRIPT_PATH)
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)

START = datetime(2026, 7, 16, tzinfo=timezone.utc)
DT_S = 60.0
EDGES = (("S", "M(0,0)"), ("M(0,0)", "M(0,1)"))
RELEASE_ID = "engineering-prior-synthetic-v1"


def _write_json(path, payload):
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")


def _network_payload():
    return {
        "metadata": {
            "canonical": True,
            "total_gates": 2,
            "total_connections": 2,
        },
        "gates": {
            "M(0,0)": {"q_max": 5.0},
            "M(0,1)": {"q_max": 5.0},
        },
        "edges": [list(edge) for edge in EDGES],
    }


def _geometry_payload():
    return {
        "metadata": {"source": "synthetic contract fixture"},
        "canal_sections": [
            {
                "from_node": upstream,
                "to_node": downstream,
                "geometry": {
                    "length_m": 100.0,
                    "cross_section": {
                        "depth_m": 1.0,
                        "bottom_width_m": 2.0,
                        "side_slope": 1.5,
                    },
                },
            }
            for upstream, downstream in EDGES
        ],
        "summary": {"total_sections": len(EDGES)},
    }


def _calibrations_payload():
    source_sha256 = "4" * 64
    return {
        "metadata": {
            "source_workbook": "synthetic.xlsx",
            "source_sha256": source_sha256,
            "intended_use": "planning_only",
            "design_fsl_reference_side": "upstream",
            "total_gates": 2,
            "gates_by_calibration_method": {
                "measured": 0,
                "inferred": 0,
                "default": 2,
            },
        },
        "gates": {
            gate_id: {
                "gate_id": gate_id,
                "calibration_method": "default",
                "confidence": 0.6,
                "shape": None,
                "width_m": None,
                "height_m": None,
                "structure_role": "unknown",
                "design_fsl_msl_m": None,
                "sill_msl_m": None,
                "structure_max_flow_m3s": None,
                "design_fsl_reference_side": None,
                "structure_data_status": "unavailable",
                "source_version": source_sha256,
                "source_gate_ids": [],
            }
            for gate_id in ("M(0,0)", "M(0,1)")
        },
    }


def _model_release_payload():
    payload = {
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "generated_at": "2026-07-16T00:00:00Z",
        "evidence_class": "engineering_prior",
        "commandable": False,
        "lineage": {
            "generator": "synthetic-offline-contract-fixture",
            "generator_version": "1.0.0",
            "sources": [
                {
                    "source_id": "synthetic-source",
                    "version": "v1",
                    "sha256": "1" * 64,
                }
            ],
        },
        "operating_envelope": {
            "minimum_flow_m3s": 0.0,
            "maximum_flow_m3s": 5.0,
            "minimum_timestep_seconds": DT_S,
            "maximum_timestep_seconds": DT_S,
            "maximum_horizon_seconds": 2 * DT_S,
        },
        "reach_parameters": [
            {
                "reach_id": f"C_{upstream}_{downstream}",
                "delay_seconds": {"lower": 0.0, "nominal": 0.0, "upper": 0.0},
                "loss_fraction": {"lower": 0.0, "nominal": 0.0, "upper": 0.0},
                "dispersion_seconds": {
                    "lower": 0.0,
                    "nominal": 0.0,
                    "upper": 0.0,
                },
                "capacity_m3s": {"lower": 5.0, "nominal": 5.0, "upper": 5.0},
                "evidence_refs": ["synthetic-source"],
            }
            for upstream, downstream in sorted(
                EDGES, key=lambda edge: f"C_{edge[0]}_{edge[1]}"
            )
        ],
        "unavailable_reaches": [],
    }
    return {**payload, "content_hash": content_hash(payload)}


def _reference_payload(case, downstream_first_flow=2.0):
    samples = [
        {
            "sampled_at": sampled_at,
            "reach_id": reach_id,
            "outflow_m3s": (
                downstream_first_flow
                if reach_id == "C_M(0,0)_M(0,1)"
                and sampled_at == "2026-07-16T00:01:00Z"
                else flow_m3s
            ),
        }
        for reach_id in ("C_M(0,0)_M(0,1)", "C_S_M(0,0)")
        for sampled_at, flow_m3s in (
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
            "simulator_id": "independent-synthetic-solver",
            "simulator_version": "1.0.0",
            "source_sha256": "3" * 64,
        },
        "validates_real_canal_behavior": False,
        "samples": samples,
    }
    return {**payload, "content_hash": content_hash(payload)}


def _artifacts(
    tmp_path,
    downstream_first_flow=2.0,
    geometry_payload=None,
    calibrations_payload=None,
):
    network = tmp_path / "network.json"
    geometry = tmp_path / "canal_geometry.json"
    calibrations = tmp_path / "gate_calibrations.json"
    release_path = tmp_path / "model_release.json"
    case_path = tmp_path / "case.json"
    reference_path = tmp_path / "reference.json"
    report_path = tmp_path / "report.json"
    canonical_case_path = tmp_path / "canonical-case.json"
    _write_json(network, _network_payload())
    _write_json(
        geometry,
        _geometry_payload() if geometry_payload is None else geometry_payload,
    )
    _write_json(
        calibrations,
        (
            _calibrations_payload()
            if calibrations_payload is None
            else calibrations_payload
        ),
    )
    release_payload = _model_release_payload()
    _write_json(release_path, release_payload)
    release = load_hydraulic_model_release(
        str(release_path),
        (f"C_{upstream}_{downstream}" for upstream, downstream in EDGES),
    )
    config_sha256 = {
        "network": file_sha256(str(network)),
        "canal_geometry": file_sha256(str(geometry)),
        "gate_calibrations": file_sha256(str(calibrations)),
    }
    responses = reach_responses_from_model_release(release)
    snapshot = build_model_snapshot(
        tuple(sorted(EDGES, key=lambda edge: f"C_{edge[0]}_{edge[1]}")),
        responses,
        release,
        config_sha256,
        actuation_approved=False,
    )
    case = build_offline_simulation_case(
        case_id="cli-serial-pulse-v1",
        model_snapshot_id=snapshot["snapshot_id"],
        model_release_id=release.release_id,
        model_release_content_hash=release.content_hash,
        member=ResponseMember.NOMINAL,
        config_sha256=config_sha256,
        network_edges=EDGES,
        starts_at=START,
        ends_at=START + timedelta(seconds=2 * DT_S),
        timestep_seconds=DT_S,
        gate_events=(
            GateFlowEvent("S", START, 2.0),
            GateFlowEvent("S", START + timedelta(seconds=DT_S), 0.0),
        ),
        requirements=(),
        branch_allocations=(),
    )
    write_offline_simulation_case(case_path, case)
    _write_json(reference_path, _reference_payload(case, downstream_first_flow))
    return {
        "network": network,
        "geometry": geometry,
        "calibrations": calibrations,
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


def test_cli_runs_reduced_model_and_writes_passing_golden_report(tmp_path):
    artifacts = _artifacts(tmp_path)

    exit_code = CLI.main(_argv(artifacts))
    report = json.loads(artifacts["report"].read_text(encoding="utf-8"))
    canonical_case = json.loads(artifacts["canonical_case"].read_text(encoding="utf-8"))

    assert (exit_code, report["status"], report["summary"]) == (
        0,
        "passed",
        {"compared_reaches": 2, "compared_samples": 4, "failing_reaches": []},
    )
    assert canonical_case == json.loads(artifacts["case"].read_text(encoding="utf-8"))


def test_cli_writes_failed_report_and_returns_nonzero_for_golden_drift(tmp_path):
    artifacts = _artifacts(tmp_path, downstream_first_flow=1.5)

    exit_code = CLI.main(_argv(artifacts))
    report = json.loads(artifacts["report"].read_text(encoding="utf-8"))

    assert (exit_code, report["status"], report["summary"]["failing_reaches"]) == (
        1,
        "failed",
        ["C_M(0,0)_M(0,1)"],
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


def test_cli_rejects_output_paths_that_overwrite_input_artifacts(tmp_path):
    artifacts = _artifacts(tmp_path)
    original_case = artifacts["case"].read_text(encoding="utf-8")
    argv = _argv(artifacts)
    argv[argv.index("--report") + 1] = str(artifacts["case"])

    with pytest.raises(OfflineModelComparisonError, match="output paths"):
        CLI.main(argv)

    assert artifacts["case"].read_text(encoding="utf-8") == original_case
