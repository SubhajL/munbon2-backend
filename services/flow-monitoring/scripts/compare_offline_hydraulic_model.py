#!/usr/bin/env python3
"""Compare the reduced reach model with an independent offline simulation result.

The sealed case and reference result use content-addressed strict JSON. Reference
flows are interval means for the interval ending at ``sampled_at`` and must cover
every reach at every case timestep. A passing report verifies software agreement
within explicit tolerances; it never claims measured or real-canal validation.

Exit status is zero for a passing report and one for a completed comparison whose
tolerances fail. Malformed, stale, incomplete, same-source, or lineage-drifted
artifacts fail closed before a report is written.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT / "src"))

from core.offline_model_comparison import (  # noqa: E402
    ComparisonStatus,
    ComparisonTolerance,
    GoldenComparisonReport,
    OfflineModelComparisonError,
    build_golden_comparison_report,
    load_offline_reference_result,
    load_offline_simulation_case,
    write_golden_comparison_report,
    write_offline_simulation_case,
)
from core.config_loader import (  # noqa: E402
    ConfigError,
    file_sha256,
    load_canal_geometry_config,
    load_gate_calibrations_config,
)
from core.demand_contract import content_hash  # noqa: E402
from core.model_release import load_hydraulic_model_release  # noqa: E402
from core.model_snapshot import build_model_snapshot  # noqa: E402
from core.network_topology import load_validated_network  # noqa: E402
from core.reach_response import (  # noqa: E402
    ReachState,
    reach_responses_from_model_release,
)
from services.control_prediction_service import ControlPredictionService  # noqa: E402


def run_comparison(
    network_path: str,
    canal_geometry_path: str,
    gate_calibrations_path: str,
    model_release_path: str,
    case_path: str,
    canonical_case_output_path: str,
    reference_path: str,
    report_path: str,
    tolerance: ComparisonTolerance,
) -> GoldenComparisonReport:
    _validate_output_paths(
        (
            network_path,
            canal_geometry_path,
            gate_calibrations_path,
            model_release_path,
            case_path,
            reference_path,
        ),
        (canonical_case_output_path, report_path),
    )
    case = load_offline_simulation_case(case_path)
    actual_config_sha256 = {
        "network": file_sha256(network_path),
        "canal_geometry": file_sha256(canal_geometry_path),
        "gate_calibrations": file_sha256(gate_calibrations_path),
    }
    if actual_config_sha256 != dict(case.config_sha256):
        raise OfflineModelComparisonError(
            "config_sha256 does not match the exported offline case"
        )
    try:
        load_canal_geometry_config(canal_geometry_path)
    except ConfigError as exc:
        raise OfflineModelComparisonError(
            f"canal geometry config is invalid: {exc}"
        ) from exc
    try:
        load_gate_calibrations_config(gate_calibrations_path)
    except ConfigError as exc:
        raise OfflineModelComparisonError(
            f"gate calibrations config is invalid: {exc}"
        ) from exc
    network_edges = tuple(
        sorted(
            load_validated_network(network_path),
            key=lambda edge: f"C_{edge[0]}_{edge[1]}",
        )
    )
    if network_edges != case.network_edges:
        raise OfflineModelComparisonError(
            "network edges do not match the exported offline case"
        )
    expected_reach_ids = tuple(
        f"C_{upstream}_{downstream}" for upstream, downstream in network_edges
    )
    release = load_hydraulic_model_release(model_release_path, expected_reach_ids)
    if (release.release_id, release.content_hash) != (
        case.model_release_id,
        case.model_release_content_hash,
    ):
        raise OfflineModelComparisonError(
            "model release lineage does not match the exported offline case"
        )
    responses = reach_responses_from_model_release(release)
    snapshot = build_model_snapshot(
        network_edges,
        responses,
        release,
        actual_config_sha256,
        actuation_approved=False,
    )
    if snapshot["snapshot_id"] != case.model_snapshot_id:
        raise OfflineModelComparisonError(
            "model snapshot lineage does not match the exported offline case"
        )
    write_offline_simulation_case(canonical_case_output_path, case)
    member_responses = tuple(
        response for response in responses if response.member is case.member
    )
    initial_states = tuple(
        ReachState(response.model_release_id, response.reach_id, response.member)
        for response in member_responses
    )
    service = ControlPredictionService(
        network_edges,
        responses,
        release.operating_envelope.maximum_horizon_seconds,
    )
    candidate = service.predict_member(
        case.member,
        initial_states,
        case.gate_events,
        case.requirements,
        case.branch_allocations,
        case.starts_at,
        case.ends_at,
        case.timestep_seconds,
    )
    reference = load_offline_reference_result(reference_path, case)
    report = build_golden_comparison_report(
        case,
        candidate,
        reference,
        tolerance,
        _candidate_source_sha256(),
    )
    write_golden_comparison_report(report_path, report)
    return report


def _candidate_source_sha256() -> str:
    source_paths = (
        SERVICE_ROOT / "src" / "core" / "model_release.py",
        SERVICE_ROOT / "src" / "core" / "reach_response.py",
        SERVICE_ROOT / "src" / "core" / "network_topology.py",
        SERVICE_ROOT / "src" / "core" / "network_transient.py",
        SERVICE_ROOT / "src" / "core" / "fulfillment.py",
        SERVICE_ROOT / "src" / "services" / "control_prediction_service.py",
    )
    return content_hash(
        {
            str(path.relative_to(SERVICE_ROOT)): file_sha256(str(path))
            for path in source_paths
        }
    )


def _validate_output_paths(
    input_paths: tuple[str, ...], output_paths: tuple[str, ...]
) -> None:
    resolved_inputs = {Path(path).resolve() for path in input_paths}
    resolved_outputs = tuple(Path(path).resolve() for path in output_paths)
    if len(set(resolved_outputs)) != len(resolved_outputs) or any(
        path in resolved_inputs for path in resolved_outputs
    ):
        raise OfflineModelComparisonError(
            "output paths must be distinct and must not overwrite input artifacts"
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network", required=True)
    parser.add_argument("--canal-geometry", required=True)
    parser.add_argument("--gate-calibrations", required=True)
    parser.add_argument("--model-release", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--canonical-case-output", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--maximum-flow-error-m3s", required=True, type=float)
    parser.add_argument("--maximum-volume-error-m3", required=True, type=float)
    parser.add_argument(
        "--maximum-arrival-time-error-seconds", required=True, type=float
    )
    parser.add_argument("--arrival-flow-threshold-m3s", required=True, type=float)
    args = parser.parse_args(argv)
    report = run_comparison(
        args.network,
        args.canal_geometry,
        args.gate_calibrations,
        args.model_release,
        args.case,
        args.canonical_case_output,
        args.reference,
        args.report,
        ComparisonTolerance(
            args.maximum_flow_error_m3s,
            args.maximum_volume_error_m3,
            args.maximum_arrival_time_error_seconds,
            args.arrival_flow_threshold_m3s,
        ),
    )
    return 0 if report.status is ComparisonStatus.PASSED else 1


if __name__ == "__main__":
    raise SystemExit(main())
