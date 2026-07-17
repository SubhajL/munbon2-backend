#!/usr/bin/env python3
"""Generate the engineering-prior hydraulic model release (PR 2.1c).

Deterministic: every constant comes from the committed policy JSON, the
canonical artifacts are loaded through the strict fail-closed loaders
(routing topology is re-derived), all sources are byte-hashed into the
release lineage, and no wall clock is read — regeneration from identical
inputs is byte-identical. `--check` regenerates and compares bytes
against the committed artifact instead of writing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT / "src"))

from core.config_loader import (  # noqa: E402
    file_sha256,
    load_gate_calibrations_config,
    load_routing_topology,
    load_strict_json_object,
)
from core.engineering_response_generator import (  # noqa: E402
    generate_engineering_model_release,
    load_engineering_policy,
    model_release_artifact_payload,
)
from core.model_release import SourceArtifact  # noqa: E402

DEFAULT_CONFIG_DIR = SERVICE_ROOT / "src" / "config"
DEFAULT_POLICY = (
    SERVICE_ROOT / "data" / "model-releases" / "engineering-prior-policy-v1.json"
)
DEFAULT_OUT = (
    SERVICE_ROOT / "data" / "model-releases" / "engineering-prior-v3-v1.json"
)


def artifact_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def build_release_bytes(policy_path: Path, config_dir: Path) -> tuple[bytes, dict]:
    policy = load_engineering_policy(load_strict_json_object(str(policy_path)))
    network_path = config_dir / "network.json"
    coverage_path = config_dir / "geometry_coverage.json"
    geometry_path = config_dir / "canal_geometry.json"
    calibrations_path = config_dir / "gate_calibrations.json"
    routing_path = config_dir / "routing_topology.json"

    topology = load_routing_topology(
        str(routing_path),
        str(network_path),
        str(coverage_path),
        str(geometry_path),
    )
    canal_geometry = load_strict_json_object(str(geometry_path))
    gate_calibrations = load_gate_calibrations_config(str(calibrations_path))

    workbook_sha = canal_geometry["metadata"]["source_sha256"]
    sources = tuple(
        SourceArtifact(source_id, version, file_sha256(str(path)))
        for source_id, version, path in (
            ("engineering_prior_policy", policy.get("policy_version"), policy_path),
            ("network", workbook_sha, network_path),
            ("geometry_coverage", workbook_sha, coverage_path),
            ("canal_geometry", workbook_sha, geometry_path),
            ("gate_calibrations", workbook_sha, calibrations_path),
            ("routing_topology", topology.content_hash, routing_path),
        )
    )
    release, diagnostics = generate_engineering_model_release(
        topology, canal_geometry, gate_calibrations, policy, sources
    )
    return artifact_bytes(model_release_artifact_payload(release)), diagnostics


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--config-dir", default=str(DEFAULT_CONFIG_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    payload_bytes, diagnostics = build_release_bytes(
        Path(args.policy), Path(args.config_dir)
    )
    parameterized = sum(
        1 for entry in diagnostics.values() if entry.get("status") == "parameterized"
    )
    unavailable = sum(
        1 for entry in diagnostics.values() if entry.get("status") == "unavailable"
    )
    out_path = Path(args.out)
    if args.check:
        committed = out_path.read_bytes()
        if committed != payload_bytes:
            print("DRIFT: committed release does not match regeneration")
            return 1
        print(
            f"check OK: {parameterized} parameterized, {unavailable} unavailable, "
            "bytes identical"
        )
        return 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(payload_bytes)
    print(
        f"wrote {out_path} ({parameterized} parameterized, "
        f"{unavailable} unavailable)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
