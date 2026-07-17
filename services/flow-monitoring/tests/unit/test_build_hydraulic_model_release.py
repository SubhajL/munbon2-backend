"""Release-generation CLI locks (PR 2.1c): byte-reproducible, clock-free,
lineage-hashed, drift-detecting."""

import importlib.util
import json
from pathlib import Path

import pytest

from core.config_loader import file_sha256

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "build_hydraulic_model_release.py"
SPEC = importlib.util.spec_from_file_location("build_release_cli", SCRIPT_PATH)
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)

POLICY_PATH = (
    SERVICE_ROOT / "data" / "model-releases" / "engineering-prior-policy-v1.json"
)
ARTIFACT_PATH = (
    SERVICE_ROOT / "data" / "model-releases" / "engineering-prior-v3-v1.json"
)
CONFIG_DIR = SERVICE_ROOT / "src" / "config"


@pytest.fixture(scope="module")
def generation():
    return CLI.build_release_bytes(POLICY_PATH, CONFIG_DIR)


def test_generation_is_byte_exact_across_two_runs(generation):
    first_bytes, _ = generation
    second_bytes, _ = CLI.build_release_bytes(POLICY_PATH, CONFIG_DIR)

    assert first_bytes == second_bytes


def test_committed_artifact_equals_regeneration(generation):
    generated_bytes, diagnostics = generation

    assert ARTIFACT_PATH.read_bytes() == generated_bytes
    statuses = [entry.get("status") for entry in diagnostics.values()]
    assert statuses.count("parameterized") == 41
    assert statuses.count("unavailable") == 1


def test_release_carries_no_wall_clock_timestamp():
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    assert artifact["generated_at"] == policy["release_generated_at"]


def test_lineage_sources_hash_the_actual_committed_files():
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    paths = {
        "engineering_prior_policy": POLICY_PATH,
        "network": CONFIG_DIR / "network.json",
        "geometry_coverage": CONFIG_DIR / "geometry_coverage.json",
        "canal_geometry": CONFIG_DIR / "canal_geometry.json",
        "gate_calibrations": CONFIG_DIR / "gate_calibrations.json",
        "routing_topology": CONFIG_DIR / "routing_topology.json",
    }
    sources = {
        source["source_id"]: source["sha256"]
        for source in artifact["lineage"]["sources"]
    }

    assert set(sources) == set(paths)
    for source_id, path in paths.items():
        assert sources[source_id] == file_sha256(str(path))


def test_check_mode_detects_artifact_drift(tmp_path):
    tampered = tmp_path / "release.json"
    payload = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    payload["release_id"] = "tampered"
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = CLI.main(
        [
            "--policy",
            str(POLICY_PATH),
            "--config-dir",
            str(CONFIG_DIR),
            "--out",
            str(tampered),
            "--check",
        ]
    )

    assert exit_code == 1


def test_check_mode_passes_on_the_committed_artifact():
    exit_code = CLI.main(
        [
            "--policy",
            str(POLICY_PATH),
            "--config-dir",
            str(CONFIG_DIR),
            "--out",
            str(ARTIFACT_PATH),
            "--check",
        ]
    )

    assert exit_code == 0
