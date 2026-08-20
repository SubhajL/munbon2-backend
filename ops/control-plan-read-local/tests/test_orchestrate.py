import gzip
import importlib.util
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "orchestrate.py"
SPEC = importlib.util.spec_from_file_location(
    "control_plan_local_orchestrate", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
orchestrate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = orchestrate
SPEC.loader.exec_module(orchestrate)
EXPECTED_SUCCESSFUL_STAGE_ORDER = (
    "LOCAL-BASE-0",
    "LOCAL-RTA-1",
    "LOCAL-AC-1",
    "LOCAL-READ-ACT-1",
    "LOCAL-EVIDENCE-1",
    "LOCAL-GO-READ-1",
    "LOCAL-WRITE-FOUNDATION-1",
    "LOCAL-WRITE-UI-1",
    "LOCAL-PERSIST-ONLY-1",
)


def test_live_stage_order_extends_frozen_ledger_v1_order():
    assert orchestrate.CAMPAIGN_LEDGER_V1_STAGE_ORDER == EXPECTED_SUCCESSFUL_STAGE_ORDER
    assert orchestrate.STAGE_ORDER == (
        *EXPECTED_SUCCESSFUL_STAGE_ORDER,
        "LOCAL-WRITE-ACT-1",
    )
    assert orchestrate.REHEARSAL_STAGE_ORDER == EXPECTED_SUCCESSFUL_STAGE_ORDER[:3]


def test_build_machine_command_uses_native_arm64_and_both_isolation_flags():
    command = orchestrate.build_machine_command(orchestrate.MachineSpec())

    assert command == [
        "orb",
        "create",
        "--arch",
        "arm64",
        "--memory",
        "8G",
        "--cpus",
        "4",
        "--disk",
        "40G",
        "--user",
        "munbonlocal",
        "--isolated",
        "--isolate-network",
        "debian:12",
        "munbon-control-plan-local",
    ]


def test_rehearsal_machine_and_guest_commands_use_only_the_fixed_rehearsal_guest():
    assert orchestrate.build_rehearsal_machine_command() == [
        "orb",
        "create",
        "--arch",
        "arm64",
        "--memory",
        "8G",
        "--cpus",
        "4",
        "--disk",
        "40G",
        "--user",
        "munbonlocal",
        "--isolated",
        "--isolate-network",
        "debian:12",
        "munbon-control-plan-rehearsal",
    ]
    assert orchestrate.build_rehearsal_guest_command(["true"], user="root") == [
        "orb",
        "-m",
        "munbon-control-plan-rehearsal",
        "-u",
        "root",
        "true",
    ]


@pytest.mark.parametrize(
    "override",
    [
        {"memory": "4G"},
        {"cpus": "2"},
        {"disk": "20G"},
        {"distribution": "ubuntu:24.04"},
        {"user": "someone-else"},
    ],
)
def test_build_machine_command_refuses_any_weakened_or_changed_shape(override):
    with pytest.raises(
        orchestrate.OrchestrationError, match="machine_spec_not_accepted"
    ):
        orchestrate.build_machine_command(orchestrate.MachineSpec(**override))


@pytest.mark.parametrize(
    "requested_sha",
    ["8095bfe3", "G" * 40, "0" * 40],
)
def test_validate_release_sha_rejects_short_malformed_and_unaccepted_sha(requested_sha):
    with pytest.raises(
        orchestrate.OrchestrationError, match="release_sha_not_accepted"
    ):
        orchestrate.validate_release_sha(requested_sha)


def test_validate_release_sha_accepts_exact_base_or_explicit_current_origin_main():
    base = orchestrate.ACCEPTED_BASE_SHA
    later = "a" * 40

    assert orchestrate.validate_release_sha(base) == base
    assert (
        orchestrate.validate_release_sha(
            later,
            origin_main_sha=later,
            accept_later_origin_main=True,
        )
        == later
    )


def test_validate_release_sha_rejects_later_main_without_explicit_acceptance():
    later = "a" * 40

    with pytest.raises(
        orchestrate.OrchestrationError, match="release_sha_not_accepted"
    ):
        orchestrate.validate_release_sha(later, origin_main_sha=later)


def test_build_guest_command_uses_fixed_machine_user_and_argument_array():
    assert orchestrate.build_guest_command(
        ["python3", "/opt/munbon/harness/run-stage-suite.py", "LOCAL-BASE-0"],
        workdir="/opt/munbon/repo",
    ) == [
        "orb",
        "-m",
        "munbon-control-plan-local",
        "-u",
        "munbon",
        "--workdir",
        "/opt/munbon/repo",
        "python3",
        "/opt/munbon/harness/run-stage-suite.py",
        "LOCAL-BASE-0",
    ]


def test_build_diagnostic_command_cannot_target_the_canonical_guest():
    assert orchestrate.build_diagnostic_command(["uname", "-m"]) == [
        "orb",
        "-m",
        "munbon-control-plan-write-ui-diagnostic",
        "-u",
        "root",
        "uname",
        "-m",
    ]

    with pytest.raises(
        orchestrate.OrchestrationError, match="diagnostic_command_invalid"
    ):
        orchestrate.build_diagnostic_command([], user="munbonlocal")


def test_classify_machine_inventory_accepts_only_exact_owned_shape():
    machine = {
        "name": "munbon-control-plan-local",
        "image": {"distro": "debian", "version": "bookworm", "arch": "arm64"},
        "config": {
            "isolated": True,
            "isolate_network": True,
            "default_username": "munbonlocal",
            "memory_limit_mib": 8192,
            "cpu_limit": 4,
            "disk_limit_bytes": 40 * 1024**3,
        },
        "state": "running",
    }

    assert orchestrate.classify_machine_inventory("[]") == "missing"
    assert orchestrate.classify_machine_inventory(json.dumps([machine])) == "ready"

    machine["name"] = "munbon-control-plan-write-ui-diagnostic"
    assert (
        orchestrate.classify_diagnostic_machine_inventory(json.dumps([machine]))
        == "ready"
    )


def test_diagnostic_build_requires_explicit_confirmation_and_exact_owner_marker():
    with pytest.raises(
        orchestrate.OrchestrationError, match="diagnostic_build_not_authorized"
    ):
        orchestrate._prepare_diagnostic_machine(confirmed=False)

    marker = json.dumps(
        {
            "architecture": "arm64",
            "canonical": False,
            "machine": "munbon-control-plan-write-ui-diagnostic",
            "purpose": "dependency-build",
        }
    )
    assert orchestrate.validate_diagnostic_owner(marker) is None
    with pytest.raises(
        orchestrate.OrchestrationError, match="diagnostic_owner_not_accepted"
    ):
        orchestrate.validate_diagnostic_owner(marker.replace("false", "true"))


def test_diagnostic_build_preflights_flat_repository_toolchain(monkeypatch):
    machine = {
        "name": "munbon-control-plan-write-ui-diagnostic",
        "image": {"distro": "debian", "version": "bookworm", "arch": "arm64"},
        "config": {
            "isolated": True,
            "isolate_network": True,
            "default_username": "munbonlocal",
            "memory_limit_mib": 8192,
            "cpu_limit": 4,
            "disk_limit_bytes": 40 * 1024**3,
        },
        "state": "running",
    }
    marker = json.dumps(
        {
            "architecture": "arm64",
            "canonical": False,
            "machine": "munbon-control-plan-write-ui-diagnostic",
            "purpose": "dependency-build",
        }
    )
    outputs = {
        "diagnostic_orb_inventory": json.dumps([machine]),
        "diagnostic_owner": marker,
        "diagnostic_dpkg_scanpackages": "/usr/bin/dpkg-scanpackages\n",
    }
    calls = []

    def fake_run_checked(code, _argv, **_kwargs):
        calls.append(code)
        return outputs[code]

    monkeypatch.setattr(orchestrate, "_run_checked", fake_run_checked)

    assert orchestrate._prepare_diagnostic_machine(confirmed=True) is None
    assert calls == [
        "diagnostic_orb_inventory",
        "diagnostic_owner",
        "diagnostic_dpkg_scanpackages",
    ]


@pytest.mark.parametrize(
    "field,value",
    [
        ("architecture", "amd64"),
        ("isolated", False),
        ("isolate_network", False),
        ("username", "someone-else"),
        ("memory", 4096),
        ("cpus", 2),
        ("disk", 20 * 1024**3),
    ],
)
def test_classify_machine_inventory_refuses_same_name_with_wrong_shape(field, value):
    machine = {
        "name": "munbon-control-plan-local",
        "image": {"distro": "debian", "version": "bookworm", "arch": "arm64"},
        "config": {
            "isolated": True,
            "isolate_network": True,
            "default_username": "munbonlocal",
            "memory_limit_mib": 8192,
            "cpu_limit": 4,
            "disk_limit_bytes": 40 * 1024**3,
        },
        "state": "running",
    }
    if field == "architecture":
        machine["image"]["arch"] = value
    elif field == "username":
        machine["config"]["default_username"] = value
    elif field == "memory":
        machine["config"]["memory_limit_mib"] = value
    elif field == "cpus":
        machine["config"]["cpu_limit"] = value
    elif field == "disk":
        machine["config"]["disk_limit_bytes"] = value
    else:
        machine["config"][field] = value

    with pytest.raises(
        orchestrate.OrchestrationError, match="machine_shape_not_accepted"
    ):
        orchestrate.classify_machine_inventory(json.dumps([machine]))


def test_validate_machine_owner_accepts_only_harness_marker():
    orchestrate.validate_machine_owner(
        json.dumps(
            {
                "machine": "munbon-control-plan-local",
                "architecture": "arm64",
                "state": "ready",
                "release_sha": orchestrate.ACCEPTED_BASE_SHA,
                "frontend_sha": "b" * 40,
                "dependency_sha256": "c" * 64,
            }
        )
    )

    for marker in (
        "",
        "{}",
        json.dumps(
            {
                "machine": "someone-elses-machine",
                "architecture": "arm64",
                "release_sha": orchestrate.ACCEPTED_BASE_SHA,
            }
        ),
    ):
        with pytest.raises(
            orchestrate.OrchestrationError, match="machine_owner_not_accepted"
        ):
            orchestrate.validate_machine_owner(marker)


def test_validate_rehearsal_owner_requires_structural_non_acceptance_marker():
    marker = {
        "machine": "munbon-control-plan-rehearsal",
        "architecture": "arm64",
        "state": "ready",
        "release_sha": "a" * 40,
        "frontend_sha": "b" * 40,
        "dependency_sha256": "c" * 64,
        "execution_kind": "rehearsal",
        "acceptance_evidence": False,
    }

    assert orchestrate.validate_rehearsal_owner(json.dumps(marker)) is None
    for field, value in (
        ("machine", "munbon-control-plan-local"),
        ("execution_kind", "canonical"),
        ("acceptance_evidence", True),
    ):
        rejected = {**marker, field: value}
        with pytest.raises(
            orchestrate.OrchestrationError, match="rehearsal_owner_not_accepted"
        ):
            orchestrate.validate_rehearsal_owner(json.dumps(rejected))


def test_validate_existing_guest_allows_only_ready_state_with_matching_owner():
    release_sha = orchestrate.ACCEPTED_BASE_SHA
    frontend_sha = "b" * 40
    state = json.dumps(
        {
            "state": "ready",
            "dependency_sha256": "c" * 64,
            "release_sha": release_sha,
            "frontend_sha": frontend_sha,
            "phase": "ownership",
            "recorded_at": "2026-08-10T10:00:00Z",
            "substep": "owner-marker",
        }
    )
    owner = json.dumps(
        {
            "machine": "munbon-control-plan-local",
            "architecture": "arm64",
            "state": "ready",
            "dependency_sha256": "c" * 64,
            "frontend_sha": frontend_sha,
            "release_sha": release_sha,
        }
    )

    assert orchestrate.validate_existing_guest(state, owner) is None

    mismatched_owner = json.loads(owner)
    mismatched_owner["frontend_sha"] = "d" * 40
    with pytest.raises(
        orchestrate.OrchestrationError, match="machine_owner_state_mismatch"
    ):
        orchestrate.validate_existing_guest(state, json.dumps(mismatched_owner))

    terminal_state = json.loads(state)
    terminal_state["state"] = "failed"
    with pytest.raises(
        orchestrate.OrchestrationError, match="machine_failed_evidence_only"
    ):
        orchestrate.validate_stage_guest(
            json.dumps(terminal_state), owner, release_sha, frontend_sha
        )


@pytest.mark.parametrize("terminal_state", ["failed", "interrupted"])
def test_validate_existing_guest_keeps_terminal_guest_evidence_only(terminal_state):
    state = json.dumps(
        {
            "state": terminal_state,
            "dependency_sha256": "c" * 64,
            "release_sha": "a" * 40,
            "frontend_sha": "b" * 40,
            "phase": "dependency-staging",
            "recorded_at": "2026-08-10T10:00:00Z",
            "substep": "auth-npm-ci",
        }
    )

    with pytest.raises(
        orchestrate.OrchestrationError, match="machine_failed_evidence_only"
    ):
        orchestrate.validate_existing_guest(state, "")


def test_validate_existing_guest_rejects_owner_without_provision_state():
    owner = json.dumps(
        {
            "machine": "munbon-control-plan-local",
            "architecture": "arm64",
            "dependency_sha256": "c" * 64,
            "release_sha": "a" * 40,
        }
    )

    with pytest.raises(
        orchestrate.OrchestrationError, match="machine_provision_state_missing"
    ):
        orchestrate.validate_existing_guest("", owner)


def test_finalize_bootstrap_failure_bundle_verifies_inner_and_writes_outer_index(
    tmp_path,
):
    destination = tmp_path / "failure"
    bundle = destination / "bundle"
    bundle.mkdir(parents=True)
    log_body = "npm error code ERR_SOCKET_TIMEOUT\n"
    metadata = {
        "classification": "retryable-transport",
        "dependency_sha256": "c" * 64,
        "exit_code": 1,
        "frontend_sha": "b" * 40,
        "phase": "dependency-staging",
        "recorded_at": "2026-08-10T10:00:00Z",
        "release_sha": "a" * 40,
        "state": "failed",
        "substep": "auth-npm-ci",
        "tool_versions": {"node": "v22.23.1", "npm": "10.9.8"},
    }
    (bundle / "bootstrap-sanitized.log").write_text(log_body)
    (bundle / "metadata.json").write_text(json.dumps(metadata, sort_keys=True) + "\n")
    (bundle / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256((bundle / name).read_bytes()).hexdigest()}  {name}\n"
            for name in ("bootstrap-sanitized.log", "metadata.json")
        )
    )

    assert orchestrate.finalize_bootstrap_failure_bundle(destination) == metadata
    assert (destination / "OUTER-SHA256SUMS").read_text().splitlines() == [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  bundle/{path.name}"
        for path in sorted(bundle.iterdir())
    ]

    (bundle / "bootstrap-sanitized.log").write_text("tampered\n")
    with pytest.raises(
        orchestrate.OrchestrationError,
        match="bootstrap_failure_inner_checksum_mismatch",
    ):
        orchestrate.finalize_bootstrap_failure_bundle(destination)

    (bundle / "bootstrap-sanitized.log").write_text(log_body)
    (bundle / "SHA256SUMS").write_text(
        (bundle / "SHA256SUMS").read_text()
        + f"{hashlib.sha256(log_body.encode()).hexdigest()}  bootstrap-sanitized.log\n"
    )
    with pytest.raises(
        orchestrate.OrchestrationError,
        match="bootstrap_failure_inner_index_invalid",
    ):
        orchestrate.finalize_bootstrap_failure_bundle(destination)


def test_finalize_rehearsal_bootstrap_failure_is_structurally_non_authoritative(
    tmp_path,
):
    destination = tmp_path / "failure"
    bundle = destination / "bundle"
    bundle.mkdir(parents=True)
    metadata = {
        "classification": "retryable-transport",
        "dependency_sha256": "c" * 64,
        "exit_code": 1,
        "frontend_sha": "b" * 40,
        "phase": "dependency-staging",
        "recorded_at": "2026-08-10T10:00:00Z",
        "release_sha": "a" * 40,
        "state": "failed",
        "substep": "auth-npm-ci",
        "tool_versions": {"node": "v22.23.1", "npm": "10.9.8"},
    }
    (bundle / "bootstrap-sanitized.log").write_text("timeout\n")
    (bundle / "metadata.json").write_text(json.dumps(metadata, sort_keys=True) + "\n")
    (bundle / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256((bundle / name).read_bytes()).hexdigest()}  {name}\n"
            for name in ("bootstrap-sanitized.log", "metadata.json")
        )
    )

    summary = orchestrate.finalize_rehearsal_bootstrap_failure_bundle(destination)

    assert summary["acceptance_evidence"] is False
    assert summary["evidence_kind"] == "non_authoritative_rehearsal"
    assert not (destination / "OUTER-SHA256SUMS").exists()
    assert not (bundle / "SHA256SUMS").exists()
    assert (bundle / "REHEARSAL-SHA256SUMS").is_file()
    assert (destination / "REHEARSAL-BOOTSTRAP-SUMMARY.json").is_file()
    assert (destination / "REHEARSAL-BOOTSTRAP-OUTER-SHA256SUMS").is_file()


RC_PROCESS_NAMES = (
    "flow-monitoring",
    "scheduler",
    "ros-gis-integration",
    "bff-water-planning",
)


def _rc_test_processes():
    return [
        {
            "name": name,
            "status": "online",
            "restarts": index,
            "pid": 100 + index,
            "memory_bytes": 1024 + index,
            "cpu_percent": index / 10,
        }
        for index, name in enumerate(RC_PROCESS_NAMES)
    ]


def _rc_test_dark_contract():
    return {
        "flow_gates_api": False,
        "scheduler_execution": "disabled",
        "scheduler_readback": "off",
        "scheduler_scada_configured": False,
        "ros_manual_producer": False,
        "ros_startup_producer": False,
        "ros_recurring_producer": False,
        "ros_source_configured": False,
        "planning_depth_writes": False,
        "machine_commands_configured": False,
        "model_release_commandable": False,
        "control_plan_reads_visible": False,
        "planning_depth_writes_visible": False,
    }


def _rc_test_runtime_proof():
    return {
        "verified": True,
        "processes": _rc_test_processes(),
        "processes_online": sorted(RC_PROCESS_NAMES),
        "listeners": [
            {"address": "127.0.0.1", "port": port} for port in (3011, 3021, 3022, 3047)
        ],
        "dark_contract_after": _rc_test_dark_contract(),
        "final_activation_gates": {
            "control_plan_reads": False,
            "control_plan_evidence_reads": False,
            "water_planning_v2": False,
            "water_planning_submit": False,
        },
        "readiness": {
            name: {"status_code": 200, "status": "ready", "checks": {}}
            for name in RC_PROCESS_NAMES
        },
    }


def _authorized_rc_harness_hashes():
    harness_root = Path(orchestrate.__file__).resolve().parent
    return {
        name: hashlib.sha256(
            (
                harness_root / name
                if name != "verify_bearer.py"
                else harness_root.parent / "control-plan-read-runtime" / name
            ).read_bytes()
        ).hexdigest()
        for name in orchestrate.EVIDENCE_HARNESS_ARTIFACTS
    }


def _rc_preflight_record():
    return {
        "schema_version": 1,
        "phase": "preflight",
        "verdict": "PASS",
        "release_sha": "a" * 40,
        "frontend_sha": "b" * 40,
        "dependency_sha256": "d" * 64,
        "guest": {
            "name": "munbon-control-plan-local",
            "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
            "architecture": "arm64",
            "machine_id": "f" * 32,
        },
        "as_of_date": "2026-11-02",
        "checks": {
            "evidence_root_empty": True,
            "database_clean": True,
            "rate_state_clean": True,
            "actionable_commands": 0,
            "sources_clean": True,
            "runtime_dark": True,
        },
        "captured_at": "2026-11-02T01:02:03Z",
    }


def _rc_stage_attempt(*, as_of_date="2026-11-02"):
    preflight = _rc_preflight_record()
    preflight_bytes = (json.dumps(preflight, indent=2, sort_keys=True) + "\n").encode()
    return {
        "preflight_sha256": hashlib.sha256(preflight_bytes).hexdigest(),
        "dependency_sha256": "d" * 64,
        "guest": preflight["guest"],
        "as_of_date": as_of_date,
    }


def _bind_rc_stage_evidence(destination: Path) -> None:
    attempt = _rc_stage_attempt()
    for stage in orchestrate.STAGE_ORDER:
        for name in (f"{stage}.json", f"{stage}-failure.json"):
            path = destination / name
            if not path.exists():
                continue
            payload = json.loads(path.read_text())
            payload["rc_attempt"] = attempt
            path.write_text(json.dumps(payload, sort_keys=True) + "\n")


def _write_complete_acceptance_evidence(destination: Path) -> dict:
    release_sha = "a" * 40
    frontend_sha = "b" * 40
    state = {
        "release_sha": release_sha,
        "frontend_sha": frontend_sha,
        "harness_hashes": {
            name: "c" * 64 for name in orchestrate.EVIDENCE_HARNESS_ARTIFACTS
        },
        "completed": list(orchestrate.STAGE_ORDER),
    }
    artifacts = {
        "stage-state.json": json.dumps(state, sort_keys=True).encode() + b"\n",
        "LOCAL-WRITE-UI-1-browser-result.json": b'{"browser":"accepted"}\n',
        "LOCAL-WRITE-ACT-1-browser-result.json": b'{"browser":"accepted"}\n',
        "LOCAL-GO-READ-1-live.png": b"live-png",
        "LOCAL-GO-READ-1-outage.png": b"outage-png",
    }
    for stage in orchestrate.STAGE_ORDER:
        manifest = {
            "stage": stage,
            "verdict": "PASS",
            "release_sha": release_sha,
            "frontend_sha": frontend_sha,
        }
        if stage == "LOCAL-PERSIST-ONLY-1":
            manifest["steps"] = {"operator_principal": {"subject": "operator-persist"}}
        if stage == "LOCAL-WRITE-ACT-1":
            write_key = (
                "bff-water-planning:rate:planning_depth.submit:"
                + hashlib.sha256(b"operator-write").hexdigest()
            )
            manifest["steps"] = {
                "operator_principal": {"subject": "operator-write"},
                "runtime_restoration": _rc_test_runtime_proof(),
                "persist_snapshot_sha256": "e" * 64,
                "rate_state_after_browser": {
                    "configured_window_ms": 300000,
                    "minimum_elapsed_ms": 900000,
                    "snapshot_completed_monotonic_ms": 20100,
                    "snapshot": {
                        write_key: {"value": 3, "ttl_ms": 6000},
                    },
                },
            }
        artifacts[f"{stage}.json"] = (
            json.dumps(manifest, sort_keys=True).encode() + b"\n"
        )
    destination.mkdir(parents=True)
    for name, body in artifacts.items():
        (destination / name).write_bytes(body)
    _write_acceptance_checksums(destination)
    return state


def _write_acceptance_checksums(destination: Path) -> None:
    artifacts = {
        path.name: path.read_bytes()
        for path in destination.iterdir()
        if path.name not in {"SHA256SUMS", "OUTER-SHA256SUMS"}
    }
    (destination / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256(body).hexdigest()}  {name}\n"
            for name, body in sorted(artifacts.items())
        ),
        encoding="utf-8",
    )


def test_finalize_evidence_collection_requires_complete_checksum_bound_10_of_10(
    tmp_path,
):
    destination = tmp_path / "evidence"
    state = _write_complete_acceptance_evidence(destination)

    assert orchestrate.finalize_evidence_collection(destination) == state
    outer = (destination / "OUTER-SHA256SUMS").read_text().splitlines()
    assert outer == [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(destination.iterdir())
        if path.name != "OUTER-SHA256SUMS"
    ]

    (destination / "LOCAL-WRITE-UI-1.json").write_text("tampered\n")
    with pytest.raises(
        orchestrate.OrchestrationError, match="evidence_checksum_mismatch"
    ):
        orchestrate.finalize_evidence_collection(destination)


def test_finalize_evidence_collection_rejects_unindexed_artifacts(tmp_path):
    destination = tmp_path / "evidence"
    _write_complete_acceptance_evidence(destination)
    (destination / "untrusted.log").write_text("not indexed\n")

    with pytest.raises(
        orchestrate.OrchestrationError, match="evidence_inventory_invalid"
    ):
        orchestrate.finalize_evidence_collection(destination)


def test_finalize_evidence_collection_rejects_partial_harness_identity(tmp_path):
    destination = tmp_path / "evidence"
    state = _write_complete_acceptance_evidence(destination)
    state["harness_hashes"].pop(next(iter(state["harness_hashes"])))
    (destination / "stage-state.json").write_text(
        json.dumps(state, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_acceptance_checksums(destination)

    with pytest.raises(orchestrate.OrchestrationError, match="evidence_state_invalid"):
        orchestrate.finalize_evidence_collection(destination)


def _write_complete_rehearsal_evidence(destination: Path) -> dict:
    release_sha = "a" * 40
    frontend_sha = "b" * 40
    state = {
        "release_sha": release_sha,
        "frontend_sha": frontend_sha,
        "harness_hashes": {
            name: "c" * 64 for name in orchestrate.EVIDENCE_HARNESS_ARTIFACTS
        },
        "completed": list(orchestrate.REHEARSAL_STAGE_ORDER),
        "execution_kind": "rehearsal",
        "machine": "munbon-control-plan-rehearsal",
        "acceptance_evidence": False,
        "dependency_sha256": "d" * 64,
        "as_of_date": "2026-08-16",
    }
    artifacts = {
        "stage-state.json": json.dumps(state, sort_keys=True).encode() + b"\n",
        **{
            f"{stage}.json": (
                json.dumps(
                    {
                        "stage": stage,
                        "verdict": "PASS",
                        "release_sha": release_sha,
                        "frontend_sha": frontend_sha,
                    },
                    sort_keys=True,
                ).encode()
                + b"\n"
            )
            for stage in orchestrate.REHEARSAL_STAGE_ORDER
        },
    }
    destination.mkdir(parents=True)
    for name, body in artifacts.items():
        (destination / name).write_bytes(body)
    _write_acceptance_checksums(destination)
    return state


def test_finalize_rehearsal_collection_is_checksum_bound_and_non_authoritative(
    tmp_path,
):
    destination = tmp_path / "rehearsal"
    state = _write_complete_rehearsal_evidence(destination)

    assert orchestrate.finalize_rehearsal_collection(destination) == {
        "schema_version": 1,
        "evidence_kind": "non_authoritative_rehearsal",
        "execution_kind": "rehearsal",
        "acceptance_evidence": False,
        "release_sha": state["release_sha"],
        "frontend_sha": state["frontend_sha"],
        "harness_hashes": state["harness_hashes"],
        "machine": "munbon-control-plan-rehearsal",
        "dependency_sha256": "d" * 64,
        "as_of_date": "2026-08-16",
        "passed": list(orchestrate.REHEARSAL_STAGE_ORDER),
        "failed": [],
        "unreached": list(orchestrate.STAGE_ORDER[3:]),
    }
    assert not (destination / "OUTER-SHA256SUMS").exists()
    assert not (destination / "SHA256SUMS").exists()
    assert (destination / "REHEARSAL-SHA256SUMS").is_file()
    assert (destination / "REHEARSAL-SUMMARY.json").is_file()
    outer = (destination / "REHEARSAL-OUTER-SHA256SUMS").read_text().splitlines()
    assert outer == [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(destination.iterdir())
        if path.name != "REHEARSAL-OUTER-SHA256SUMS"
    ]

    (destination / "LOCAL-AC-1.json").write_text("tampered\n")
    with pytest.raises(
        orchestrate.OrchestrationError,
        match="rehearsal_evidence_checksum_mismatch",
    ):
        orchestrate.finalize_rehearsal_collection(destination)


@pytest.mark.parametrize(
    "completed",
    [
        ["LOCAL-BASE-0", "LOCAL-RTA-1"],
        ["LOCAL-BASE-0", "LOCAL-RTA-1", "LOCAL-AC-1", "LOCAL-READ-ACT-1"],
    ],
)
def test_finalize_rehearsal_collection_requires_exact_three_stage_prefix(
    tmp_path, completed
):
    destination = tmp_path / "rehearsal"
    _write_complete_rehearsal_evidence(destination)
    state_path = destination / "stage-state.json"
    state = json.loads(state_path.read_text())
    state["completed"] = completed
    state_path.write_text(json.dumps(state, sort_keys=True) + "\n")
    _write_acceptance_checksums(destination)

    with pytest.raises(
        orchestrate.OrchestrationError, match="rehearsal_evidence_state_invalid"
    ):
        orchestrate.finalize_rehearsal_collection(destination)


def test_collect_evidence_extracts_then_validates_exact_inventory(
    tmp_path, monkeypatch
):
    destination = tmp_path / "evidence"
    source = tmp_path / "guest-evidence"
    expected_state = _write_complete_acceptance_evidence(source)
    streamed_archive = tmp_path / "streamed-evidence.tar.gz"
    with tarfile.open(streamed_archive, "w:gz") as bundle:
        for path in sorted(source.iterdir()):
            bundle.add(path, arcname=path.name)

    def stream_archive(_argv, *, stdout, **_kwargs):
        stdout.write(streamed_archive.read_bytes())
        return subprocess.CompletedProcess(_argv, 0, b"", b"")

    def extract_archive(code, argv, **_kwargs):
        assert code == "evidence_extract"
        with tarfile.open(argv[2], "r:gz") as bundle:
            bundle.extractall(argv[4], filter="data")
        return ""

    monkeypatch.setattr(orchestrate.subprocess, "run", stream_archive)
    monkeypatch.setattr(orchestrate, "_run_checked", extract_archive)

    orchestrate.collect_evidence(destination)

    assert not (destination / "local-acceptance-evidence.tar.gz").exists()
    assert json.loads((destination / "stage-state.json").read_text()) == expected_state
    assert (destination / "OUTER-SHA256SUMS").is_file()


def test_collect_evidence_removes_temporary_output_when_extraction_fails(
    tmp_path, monkeypatch
):
    destination = tmp_path / "evidence"

    def stream_archive(argv, *, stdout, **_kwargs):
        stdout.write(b"truncated archive")
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    def fail_extraction(code, _argv, **_kwargs):
        assert code == "evidence_extract"
        raise orchestrate.OrchestrationError("evidence_extract_failed")

    monkeypatch.setattr(orchestrate.subprocess, "run", stream_archive)
    monkeypatch.setattr(orchestrate, "_run_checked", fail_extraction)

    with pytest.raises(orchestrate.OrchestrationError, match="evidence_extract_failed"):
        orchestrate.collect_evidence(destination)

    assert not destination.exists()
    assert list(tmp_path.glob(".evidence-*")) == []


def test_collect_rehearsal_targets_fixed_guest_and_writes_only_rehearsal_outer_index(
    tmp_path, monkeypatch
):
    destination = tmp_path / "rehearsal"
    source = tmp_path / "guest-rehearsal"
    _write_complete_rehearsal_evidence(source)
    streamed_archive = tmp_path / "streamed-rehearsal.tar.gz"
    with tarfile.open(streamed_archive, "w:gz") as bundle:
        for path in sorted(source.iterdir()):
            bundle.add(path, arcname=path.name)

    def stream_archive(argv, *, stdout, **_kwargs):
        assert argv[argv.index("-m") + 1] == "munbon-control-plan-rehearsal"
        stdout.write(streamed_archive.read_bytes())
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    def extract_archive(code, argv, **_kwargs):
        if code == "rehearsal_collection_provision_state":
            return json.dumps(
                {
                    "state": "ready",
                    "dependency_sha256": "d" * 64,
                    "release_sha": "a" * 40,
                    "frontend_sha": "b" * 40,
                    "phase": "complete",
                    "recorded_at": "2026-08-16T00:00:00Z",
                    "substep": "ready-state",
                }
            )
        if code == "rehearsal_collection_owner":
            return json.dumps(
                {
                    "machine": "munbon-control-plan-rehearsal",
                    "architecture": "arm64",
                    "state": "ready",
                    "release_sha": "a" * 40,
                    "frontend_sha": "b" * 40,
                    "dependency_sha256": "d" * 64,
                    "execution_kind": "rehearsal",
                    "acceptance_evidence": False,
                }
            )
        assert code == "rehearsal_evidence_extract"
        with tarfile.open(argv[2], "r:gz") as bundle:
            bundle.extractall(argv[4], filter="data")
        return ""

    monkeypatch.setattr(orchestrate.subprocess, "run", stream_archive)
    monkeypatch.setattr(orchestrate, "_run_checked", extract_archive)
    monkeypatch.setattr(orchestrate, "_rehearsal_machine_state", lambda: "ready")

    summary = orchestrate.collect_rehearsal(
        destination, "a" * 40, "b" * 40, "2026-08-16"
    )

    assert summary["acceptance_evidence"] is False
    assert not (destination / "local-rehearsal-evidence.tar.gz").exists()
    assert not (destination / "OUTER-SHA256SUMS").exists()
    assert (destination / "REHEARSAL-OUTER-SHA256SUMS").is_file()


def test_collect_rehearsal_rechecks_owner_before_atomic_publish(tmp_path, monkeypatch):
    destination = tmp_path / "rehearsal"
    owner = {
        "machine": "munbon-control-plan-rehearsal",
        "architecture": "arm64",
        "state": "ready",
        "release_sha": "a" * 40,
        "frontend_sha": "b" * 40,
        "dependency_sha256": "d" * 64,
        "execution_kind": "rehearsal",
        "acceptance_evidence": False,
    }
    owners = iter((owner, {**owner, "dependency_sha256": "e" * 64}))
    monkeypatch.setattr(
        orchestrate,
        "_validated_rehearsal_owner",
        lambda _release_sha, _frontend_sha: next(owners),
    )
    monkeypatch.setattr(
        orchestrate,
        "finalize_rehearsal_collection",
        lambda _temporary: {
            "machine": owner["machine"],
            "release_sha": owner["release_sha"],
            "frontend_sha": owner["frontend_sha"],
            "dependency_sha256": owner["dependency_sha256"],
            "execution_kind": "rehearsal",
            "acceptance_evidence": False,
        },
    )

    def finalize_only(_destination, *, finalizer, **_kwargs):
        temporary = tmp_path / "temporary"
        temporary.mkdir()
        return finalizer(temporary)

    monkeypatch.setattr(orchestrate, "_collect_guest_evidence", finalize_only)

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="rehearsal_evidence_owner_mismatch",
    ):
        orchestrate.collect_rehearsal(destination, "a" * 40, "b" * 40, "2026-08-16")

    assert not destination.exists()


def test_collect_rehearsal_requires_a_new_destination(tmp_path, monkeypatch):
    destination = tmp_path / "existing"
    destination.mkdir()
    (destination / "stale.json").write_text("{}\n")
    monkeypatch.setattr(
        orchestrate.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("must reject before streaming"),
    )

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="rehearsal_evidence_destination_exists",
    ):
        orchestrate.collect_rehearsal(destination, "a" * 40, "b" * 40, "2026-08-16")


def _write_partial_failure_evidence(
    destination: Path,
    *,
    completed_count: int = 2,
    acceptance_evidence: bool | None = None,
) -> dict:
    release_sha = "a" * 40
    frontend_sha = "b" * 40
    completed = list(orchestrate.STAGE_ORDER[:completed_count])
    failed_stage = orchestrate.STAGE_ORDER[completed_count]
    state = {
        "release_sha": release_sha,
        "frontend_sha": frontend_sha,
        "harness_hashes": {
            name: "c" * 64 for name in orchestrate.EVIDENCE_HARNESS_ARTIFACTS
        },
        "completed": completed,
    }
    if acceptance_evidence is not None:
        state.update(
            {
                "execution_kind": "rehearsal",
                "machine": "munbon-control-plan-rehearsal",
                "acceptance_evidence": False,
                "dependency_sha256": "d" * 64,
                "as_of_date": "2026-08-16",
            }
        )
    failure = {
        "stage": failed_stage,
        "verdict": "FAIL",
        "release_sha": release_sha,
        "frontend_sha": frontend_sha,
        "failed_gate": "manual_requirement_run_not_accepted",
        "failed_at": "2026-08-12T00:00:00Z",
    }
    if acceptance_evidence is not None:
        failure["acceptance_evidence"] = acceptance_evidence
        failure["as_of_date"] = "2026-08-16"
    artifacts = {
        "stage-state.json": json.dumps(state, sort_keys=True).encode() + b"\n",
        f"{failed_stage}-failure.json": (
            json.dumps(failure, sort_keys=True).encode() + b"\n"
        ),
    }
    artifacts.update(
        {
            f"{stage}.json": (
                json.dumps(
                    {
                        "stage": stage,
                        "verdict": "PASS",
                        "release_sha": release_sha,
                        "frontend_sha": frontend_sha,
                    },
                    sort_keys=True,
                ).encode()
                + b"\n"
            )
            for stage in completed
        }
    )
    destination.mkdir(parents=True)
    for name, body in artifacts.items():
        (destination / name).write_bytes(body)
    _write_acceptance_checksums(destination)
    return state


def test_finalize_partial_failure_collection_requires_ordered_prefix_and_identity(
    tmp_path,
):
    destination = tmp_path / "partial-evidence"
    state = _write_partial_failure_evidence(destination)

    assert orchestrate.finalize_partial_failure_collection(destination) == {
        "acceptance_evidence": False,
        "release_sha": state["release_sha"],
        "frontend_sha": state["frontend_sha"],
        "harness_hashes": state["harness_hashes"],
        "completed": list(orchestrate.STAGE_ORDER[:2]),
        "failed_stage": "LOCAL-AC-1",
        "failed_gate": "manual_requirement_run_not_accepted",
        "passed": 2,
        "failed": 1,
        "unreached": 7,
    }
    outer = (destination / "PARTIAL-OUTER-SHA256SUMS").read_text().splitlines()
    summary = json.loads((destination / "PARTIAL-SUMMARY.json").read_text())
    assert summary["acceptance_evidence"] is False
    assert summary["failed_stage"] == "LOCAL-AC-1"
    assert outer == [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(destination.iterdir())
        if path.name != "PARTIAL-OUTER-SHA256SUMS"
    ]
    assert any(line.endswith("  PARTIAL-SUMMARY.json") for line in outer)

    with pytest.raises(
        orchestrate.OrchestrationError, match="evidence_inventory_invalid"
    ):
        orchestrate.finalize_evidence_collection(destination)


@pytest.mark.parametrize("completed_count", [0, 1, 2])
def test_finalize_rehearsal_partial_failure_accepts_each_rehearsal_failure_boundary(
    tmp_path, completed_count
):
    destination = tmp_path / "rehearsal-partial"
    _write_partial_failure_evidence(
        destination,
        completed_count=completed_count,
        acceptance_evidence=False,
    )

    summary = orchestrate.finalize_rehearsal_partial_failure_collection(destination)

    assert summary["acceptance_evidence"] is False
    assert summary["evidence_kind"] == "non_authoritative_rehearsal"
    assert summary["passed"] == completed_count
    assert summary["failed_stage"] == orchestrate.STAGE_ORDER[completed_count]
    assert not (destination / "PARTIAL-OUTER-SHA256SUMS").exists()
    assert not (destination / "SHA256SUMS").exists()
    assert (destination / "REHEARSAL-SHA256SUMS").is_file()
    assert (destination / "REHEARSAL-PARTIAL-OUTER-SHA256SUMS").is_file()


@pytest.mark.parametrize(
    ("completed_count", "acceptance_evidence"),
    [(3, False), (2, None), (2, True)],
)
def test_finalize_rehearsal_partial_failure_rejects_later_or_unmarked_failure(
    tmp_path, completed_count, acceptance_evidence
):
    destination = tmp_path / "rehearsal-partial"
    _write_partial_failure_evidence(
        destination,
        completed_count=completed_count,
        acceptance_evidence=acceptance_evidence,
    )

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="rehearsal_partial_evidence_not_accepted",
    ):
        orchestrate.finalize_rehearsal_partial_failure_collection(destination)


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("gap", "partial_evidence_stage_sequence_invalid"),
        ("identity", "partial_evidence_manifest_invalid"),
        ("missing_frontend", "partial_evidence_manifest_invalid"),
        ("missing_pass_frontend", "partial_evidence_manifest_invalid"),
        ("indexed_later_stage", "partial_evidence_stage_sequence_invalid"),
        ("unindexed", "partial_evidence_inventory_invalid"),
    ],
)
def test_finalize_partial_failure_collection_rejects_invalid_evidence(
    tmp_path, mutation, error
):
    destination = tmp_path / mutation
    _write_partial_failure_evidence(destination)
    if mutation == "gap":
        source = destination / "LOCAL-AC-1-failure.json"
        manifest = json.loads(source.read_text())
        manifest["stage"] = "LOCAL-READ-ACT-1"
        source.unlink()
        (destination / "LOCAL-READ-ACT-1-failure.json").write_text(
            json.dumps(manifest, sort_keys=True) + "\n"
        )
        _write_acceptance_checksums(destination)
    elif mutation in {"identity", "missing_frontend"}:
        path = destination / "LOCAL-AC-1-failure.json"
        manifest = json.loads(path.read_text())
        if mutation == "identity":
            manifest["frontend_sha"] = "d" * 40
        else:
            del manifest["frontend_sha"]
        path.write_text(json.dumps(manifest, sort_keys=True) + "\n")
        _write_acceptance_checksums(destination)
    elif mutation == "missing_pass_frontend":
        path = destination / "LOCAL-RTA-1.json"
        manifest = json.loads(path.read_text())
        del manifest["frontend_sha"]
        path.write_text(json.dumps(manifest, sort_keys=True) + "\n")
        _write_acceptance_checksums(destination)
    elif mutation == "indexed_later_stage":
        (destination / "LOCAL-WRITE-UI-1-browser-result.json").write_text(
            '{"browser":"unreached"}\n'
        )
        _write_acceptance_checksums(destination)
    else:
        (destination / "untrusted.log").write_text("not indexed\n")

    with pytest.raises(orchestrate.OrchestrationError, match=error):
        orchestrate.finalize_partial_failure_collection(destination)


def test_collect_partial_failure_extracts_then_validates(tmp_path, monkeypatch):
    destination = tmp_path / "partial-evidence"
    source = tmp_path / "guest-partial-evidence"
    expected_state = _write_partial_failure_evidence(source)
    streamed_archive = tmp_path / "streamed-partial-evidence.tar.gz"
    with tarfile.open(streamed_archive, "w:gz") as bundle:
        for path in sorted(source.iterdir()):
            bundle.add(path, arcname=path.name)

    def stream_archive(_argv, *, stdout, **_kwargs):
        stdout.write(streamed_archive.read_bytes())
        return subprocess.CompletedProcess(_argv, 0, b"", b"")

    def extract_archive(code, argv, **_kwargs):
        assert code == "partial_evidence_extract"
        with tarfile.open(argv[2], "r:gz") as bundle:
            bundle.extractall(argv[4], filter="data")
        return ""

    monkeypatch.setattr(orchestrate.subprocess, "run", stream_archive)
    monkeypatch.setattr(orchestrate, "_run_checked", extract_archive)

    summary = orchestrate.collect_partial_failure(destination)

    assert summary["release_sha"] == expected_state["release_sha"]
    assert not (destination / "local-partial-failure-evidence.tar.gz").exists()
    assert (destination / "PARTIAL-OUTER-SHA256SUMS").is_file()


def test_parser_accepts_partial_failure_collection_action():
    args = orchestrate._parse_args(
        ["collect-partial-failure", "--evidence-dir", "/tmp/partial-evidence"]
    )

    assert args.action == "collect-partial-failure"


@pytest.mark.parametrize(
    "frontend_sha_args",
    [[], ["--frontend-sha", "not-a-full-sha"]],
)
def test_main_requires_explicit_frontend_sha_before_repo_inspection(
    frontend_sha_args, monkeypatch, capsys
):
    monkeypatch.setattr(
        orchestrate,
        "_origin_main_sha",
        lambda _path: pytest.fail("repository inspection must not run"),
    )

    assert orchestrate.main(["plan", *frontend_sha_args]) == 1
    assert capsys.readouterr().out == (
        "FAIL orchestration: frontend_sha_not_accepted\n"
    )


def test_partial_failure_cli_prints_machine_readable_non_acceptance_summary(
    tmp_path, monkeypatch, capsys
):
    backend_sha = orchestrate.ACCEPTED_BASE_SHA
    frontend_sha = "fbd4ce4df0bb0476b7cd402ac1a4e180a91a7792"
    origin_shas = iter((backend_sha, frontend_sha))
    summary = {
        "acceptance_evidence": False,
        "failed_stage": "LOCAL-AC-1",
        "passed": 2,
        "failed": 1,
        "unreached": 6,
    }
    monkeypatch.setattr(
        orchestrate, "_origin_main_sha", lambda _path: next(origin_shas)
    )
    monkeypatch.setattr(
        orchestrate, "collect_partial_failure", lambda _destination: summary
    )

    assert (
        orchestrate.main(
            [
                "collect-partial-failure",
                "--repo",
                str(tmp_path / "backend"),
                "--frontend-repo",
                str(tmp_path / "frontend"),
                "--frontend-sha",
                frontend_sha,
                "--evidence-dir",
                str(tmp_path / "evidence"),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == summary


def _campaign_ledger_entry(
    campaign_id: str,
    *,
    previous_entry_sha256: str | None,
    outcome: dict | None = None,
    authorization: dict | None = None,
    evidence_index_name: str = "OUTER-SHA256SUMS",
) -> dict:
    entry = {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "recorded_at": "2026-08-12T00:00:00Z",
        "candidate": {
            "backend_sha": "a" * 40,
            "frontend_sha": "b" * 40,
            "dependency_sha256": "c" * 64,
            "harness_hashes": {
                name: "d" * 64 for name in orchestrate.EVIDENCE_HARNESS_ARTIFACTS
            },
        },
        "guest": {
            "name": "munbon-control-plan-local",
            "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
            "architecture": "arm64",
        },
        "evidence": {
            "ref": "external-evidence/campaign",
            "index_name": evidence_index_name,
            "index_sha256": "e" * 64,
        },
        "outcome": (
            outcome
            if outcome is not None
            else {
                "acceptance": False,
                "passed": list(orchestrate.CAMPAIGN_LEDGER_V1_STAGE_ORDER[:2]),
                "failed": [orchestrate.CAMPAIGN_LEDGER_V1_STAGE_ORDER[2]],
                "unreached": list(orchestrate.CAMPAIGN_LEDGER_V1_STAGE_ORDER[3:]),
            }
        ),
        "authorization": (
            authorization
            if authorization is not None
            else {
                "state": "exhausted",
                "attempt": 3,
                "ceiling": 3,
            }
        ),
        "previous_entry_sha256": previous_entry_sha256,
    }
    canonical = json.dumps(entry, sort_keys=True, separators=(",", ":")).encode()
    return {
        **entry,
        "entry_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _successful_campaign_ledger_entry(
    campaign_id: str, *, previous_entry_sha256: str | None
) -> dict:
    return _campaign_ledger_entry(
        campaign_id,
        previous_entry_sha256=previous_entry_sha256,
        outcome={
            "acceptance": True,
            "passed": list(EXPECTED_SUCCESSFUL_STAGE_ORDER),
            "failed": [],
            "unreached": [],
        },
        authorization={
            "state": "successful_closed",
            "attempt": 1,
            "ceiling": 3,
        },
    )


def test_validate_campaign_ledger_accepts_complete_successful_closed_entry(tmp_path):
    entry = _successful_campaign_ledger_entry(
        "campaign-success", previous_entry_sha256=None
    )
    path = tmp_path / "campaign-ledger.jsonl"
    path.write_text(json.dumps(entry, sort_keys=True) + "\n")

    assert orchestrate.CAMPAIGN_LEDGER_V1_STAGE_ORDER == (
        EXPECTED_SUCCESSFUL_STAGE_ORDER
    )
    assert orchestrate.validate_campaign_ledger(path) == [entry]


@pytest.mark.parametrize(
    ("outcome", "authorization", "evidence_index_name"),
    [
        (
            {
                "acceptance": False,
                "passed": list(orchestrate.STAGE_ORDER),
                "failed": [],
                "unreached": [],
            },
            {"state": "successful_closed", "attempt": 1, "ceiling": 3},
            "OUTER-SHA256SUMS",
        ),
        (
            {
                "acceptance": False,
                "passed": list(orchestrate.STAGE_ORDER[:2]),
                "failed": [orchestrate.STAGE_ORDER[2]],
                "unreached": list(orchestrate.STAGE_ORDER[3:]),
            },
            {"state": "successful_closed", "attempt": 1, "ceiling": 3},
            "OUTER-SHA256SUMS",
        ),
        (
            {
                "acceptance": True,
                "passed": list(orchestrate.STAGE_ORDER[:-1]),
                "failed": [],
                "unreached": [orchestrate.STAGE_ORDER[-1]],
            },
            {"state": "successful_closed", "attempt": 1, "ceiling": 3},
            "OUTER-SHA256SUMS",
        ),
        (
            {
                "acceptance": True,
                "passed": list(orchestrate.STAGE_ORDER[:-1]),
                "failed": [orchestrate.STAGE_ORDER[-1]],
                "unreached": [],
            },
            {"state": "successful_closed", "attempt": 1, "ceiling": 3},
            "OUTER-SHA256SUMS",
        ),
        (
            {
                "acceptance": True,
                "passed": [
                    orchestrate.STAGE_ORDER[1],
                    orchestrate.STAGE_ORDER[0],
                    *orchestrate.STAGE_ORDER[2:],
                ],
                "failed": [],
                "unreached": [],
            },
            {"state": "successful_closed", "attempt": 1, "ceiling": 3},
            "OUTER-SHA256SUMS",
        ),
        (
            {
                "acceptance": True,
                "passed": [
                    *orchestrate.STAGE_ORDER[:-1],
                    orchestrate.STAGE_ORDER[-2],
                ],
                "failed": [],
                "unreached": [],
            },
            {"state": "successful_closed", "attempt": 1, "ceiling": 3},
            "OUTER-SHA256SUMS",
        ),
        (
            {
                "acceptance": True,
                "passed": list(orchestrate.STAGE_ORDER),
                "failed": [],
                "unreached": [],
            },
            {"state": "exhausted", "attempt": 3, "ceiling": 3},
            "OUTER-SHA256SUMS",
        ),
        (
            {
                "acceptance": True,
                "passed": list(orchestrate.STAGE_ORDER),
                "failed": [],
                "unreached": [],
            },
            {"state": "successful_closed", "attempt": None, "ceiling": None},
            "OUTER-SHA256SUMS",
        ),
        (
            {
                "acceptance": True,
                "passed": list(orchestrate.STAGE_ORDER),
                "failed": [],
                "unreached": [],
            },
            {"state": "successful_closed", "attempt": True, "ceiling": 3},
            "OUTER-SHA256SUMS",
        ),
        (
            {
                "acceptance": True,
                "passed": list(orchestrate.STAGE_ORDER),
                "failed": [],
                "unreached": [],
            },
            {"state": "successful_closed", "attempt": 0, "ceiling": 3},
            "OUTER-SHA256SUMS",
        ),
        (
            {
                "acceptance": True,
                "passed": list(orchestrate.STAGE_ORDER),
                "failed": [],
                "unreached": [],
            },
            {"state": "successful_closed", "attempt": -1, "ceiling": 3},
            "OUTER-SHA256SUMS",
        ),
        (
            {
                "acceptance": True,
                "passed": list(orchestrate.STAGE_ORDER),
                "failed": [],
                "unreached": [],
            },
            {"state": "successful_closed", "attempt": 4, "ceiling": 3},
            "OUTER-SHA256SUMS",
        ),
        (
            {
                "acceptance": True,
                "passed": list(orchestrate.STAGE_ORDER),
                "failed": [],
                "unreached": [],
            },
            {"state": "successful_closed", "attempt": 1, "ceiling": 3},
            "PARTIAL-OUTER-SHA256SUMS",
        ),
        (
            {
                "acceptance": True,
                "passed": list(orchestrate.STAGE_ORDER),
                "failed": [],
                "unreached": [],
            },
            {"state": "successful_closed", "attempt": 1, "ceiling": 3},
            "SHA256SUMS",
        ),
        (
            {
                "acceptance": True,
                "passed": list(EXPECTED_SUCCESSFUL_STAGE_ORDER),
                "failed": [],
                "unreached": [],
            },
            {"state": "successful_closed", "attempt": 1, "ceiling": 3},
            "REHEARSAL-OUTER-SHA256SUMS",
        ),
        (
            {
                "acceptance": False,
                "passed": list(EXPECTED_SUCCESSFUL_STAGE_ORDER[:2]),
                "failed": [EXPECTED_SUCCESSFUL_STAGE_ORDER[2]],
                "unreached": list(EXPECTED_SUCCESSFUL_STAGE_ORDER[3:]),
            },
            {"state": "exhausted", "attempt": 3, "ceiling": 3},
            "REHEARSAL-PARTIAL-OUTER-SHA256SUMS",
        ),
        (
            {
                "acceptance": False,
                "passed": [],
                "failed": [EXPECTED_SUCCESSFUL_STAGE_ORDER[0]],
                "unreached": list(EXPECTED_SUCCESSFUL_STAGE_ORDER[1:]),
            },
            {"state": "exhausted", "attempt": 1, "ceiling": 1},
            "REHEARSAL-BOOTSTRAP-OUTER-SHA256SUMS",
        ),
        (
            {
                "acceptance": False,
                "passed": [],
                "failed": [EXPECTED_SUCCESSFUL_STAGE_ORDER[0]],
                "unreached": list(EXPECTED_SUCCESSFUL_STAGE_ORDER[1:]),
            },
            {"state": "exhausted", "attempt": 1, "ceiling": 1},
            "REHEARSAL-SHA256SUMS",
        ),
    ],
)
def test_validate_campaign_ledger_rejects_invalid_successful_closed_entry(
    tmp_path, outcome, authorization, evidence_index_name
):
    entry = _campaign_ledger_entry(
        "campaign-success",
        previous_entry_sha256=None,
        outcome=outcome,
        authorization=authorization,
        evidence_index_name=evidence_index_name,
    )
    path = tmp_path / "campaign-ledger.jsonl"
    path.write_text(json.dumps(entry, sort_keys=True) + "\n")

    with pytest.raises(
        orchestrate.OrchestrationError, match="campaign_ledger_schema_invalid"
    ):
        orchestrate.validate_campaign_ledger(path)


def test_validate_campaign_ledger_append_only_accepts_success_after_failure_history(
    tmp_path,
):
    first = _campaign_ledger_entry("campaign-1", previous_entry_sha256=None)
    second = _campaign_ledger_entry(
        "campaign-2", previous_entry_sha256=first["entry_sha256"]
    )
    success = _successful_campaign_ledger_entry(
        "campaign-success", previous_entry_sha256=second["entry_sha256"]
    )
    base = tmp_path / "base.jsonl"
    current = tmp_path / "current.jsonl"
    base_text = "".join(
        json.dumps(entry, sort_keys=True) + "\n" for entry in (first, second)
    )
    base.write_text(base_text)
    current.write_text(base_text + json.dumps(success, sort_keys=True) + "\n")

    assert orchestrate.validate_campaign_ledger_append_only(base, current) == [
        first,
        second,
        success,
    ]


def test_validate_campaign_ledger_cli_does_not_require_frontend_repo(
    tmp_path, monkeypatch, capsys
):
    entry = _campaign_ledger_entry("campaign-1", previous_entry_sha256=None)
    path = tmp_path / "campaign-ledger.jsonl"
    path.write_text(json.dumps(entry, sort_keys=True) + "\n")
    monkeypatch.setattr(
        orchestrate,
        "_origin_main_sha",
        lambda _path: pytest.fail("repository inspection must not run"),
    )

    assert (
        orchestrate.main(
            [
                "validate-campaign-ledger",
                "--campaign-ledger",
                str(path),
            ]
        )
        == 0
    )
    assert capsys.readouterr().out == "PASS campaign_ledger\n"


def test_validate_campaign_ledger_requires_canonical_hash_chain_and_stage_partition(
    tmp_path,
):
    first = _campaign_ledger_entry("campaign-1", previous_entry_sha256=None)
    second = _campaign_ledger_entry(
        "campaign-2", previous_entry_sha256=first["entry_sha256"]
    )
    path = tmp_path / "campaign-ledger.jsonl"
    path.write_text(
        "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in (first, second))
    )

    assert orchestrate.validate_campaign_ledger(path) == [first, second]

    second["evidence"]["ref"] = "external-evidence/tampered"
    path.write_text(
        "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in (first, second))
    )
    with pytest.raises(
        orchestrate.OrchestrationError, match="campaign_ledger_entry_hash_invalid"
    ):
        orchestrate.validate_campaign_ledger(path)

    invalid_partition = _campaign_ledger_entry(
        "campaign-2", previous_entry_sha256=first["entry_sha256"]
    )
    invalid_partition["outcome"]["passed"] = list(orchestrate.STAGE_ORDER[:3])
    canonical = {
        key: value for key, value in invalid_partition.items() if key != "entry_sha256"
    }
    invalid_partition["entry_sha256"] = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path.write_text(
        "".join(
            json.dumps(entry, sort_keys=True) + "\n"
            for entry in (first, invalid_partition)
        )
    )
    with pytest.raises(
        orchestrate.OrchestrationError, match="campaign_ledger_schema_invalid"
    ):
        orchestrate.validate_campaign_ledger(path)


def test_validate_campaign_ledger_rejects_broken_previous_hash(tmp_path):
    first = _campaign_ledger_entry("campaign-1", previous_entry_sha256=None)
    second = _campaign_ledger_entry("campaign-2", previous_entry_sha256="f" * 64)
    path = tmp_path / "campaign-ledger.jsonl"
    path.write_text(
        "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in (first, second))
    )

    with pytest.raises(
        orchestrate.OrchestrationError, match="campaign_ledger_chain_invalid"
    ):
        orchestrate.validate_campaign_ledger(path)


@pytest.mark.parametrize(
    ("container", "field"),
    [
        ("candidate", "backend_sha"),
        ("candidate", "frontend_sha"),
        ("candidate", "dependency_sha256"),
        ("evidence", "index_sha256"),
    ],
)
def test_validate_campaign_ledger_bounds_malformed_identity_types(
    tmp_path, container, field
):
    entry = _campaign_ledger_entry("campaign-1", previous_entry_sha256=None)
    entry[container][field] = 123
    canonical = {key: value for key, value in entry.items() if key != "entry_sha256"}
    entry["entry_sha256"] = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = tmp_path / "campaign-ledger.jsonl"
    path.write_text(json.dumps(entry, sort_keys=True) + "\n")

    with pytest.raises(
        orchestrate.OrchestrationError, match="campaign_ledger_schema_invalid"
    ):
        orchestrate.validate_campaign_ledger(path)


def test_validate_campaign_ledger_rejects_boolean_schema_version(tmp_path):
    entry = _campaign_ledger_entry("campaign-1", previous_entry_sha256=None)
    entry["schema_version"] = True
    canonical = {key: value for key, value in entry.items() if key != "entry_sha256"}
    entry["entry_sha256"] = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = tmp_path / "campaign-ledger.jsonl"
    path.write_text(json.dumps(entry, sort_keys=True) + "\n")

    with pytest.raises(
        orchestrate.OrchestrationError, match="campaign_ledger_schema_invalid"
    ):
        orchestrate.validate_campaign_ledger(path)


@pytest.mark.parametrize("duplicate_key", ["campaign_id", "backend_sha"])
def test_validate_campaign_ledger_rejects_duplicate_keys_recursively(
    tmp_path, duplicate_key
):
    entry = _campaign_ledger_entry("campaign-1", previous_entry_sha256=None)
    line = json.dumps(entry, sort_keys=True)
    value = (
        entry[duplicate_key]
        if duplicate_key in entry
        else entry["candidate"][duplicate_key]
    )
    fragment = f"{json.dumps(duplicate_key)}: {json.dumps(value)}"
    line = line.replace(fragment, f"{fragment}, {fragment}", 1)
    path = tmp_path / "campaign-ledger.jsonl"
    path.write_text(line + "\n")

    with pytest.raises(
        orchestrate.OrchestrationError, match="campaign_ledger_schema_invalid"
    ):
        orchestrate.validate_campaign_ledger(path)


@pytest.mark.parametrize(
    "recorded_at",
    [
        "2026-99-12T00:00:00Z",
        "2026-08-99T00:00:00Z",
        "2026-08-12T24:00:00Z",
        "2026-08-12T00:00:60Z",
    ],
)
def test_validate_campaign_ledger_rejects_impossible_utc_timestamp(
    tmp_path, recorded_at
):
    entry = _campaign_ledger_entry("campaign-1", previous_entry_sha256=None)
    entry["recorded_at"] = recorded_at
    canonical = {key: value for key, value in entry.items() if key != "entry_sha256"}
    entry["entry_sha256"] = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = tmp_path / "campaign-ledger.jsonl"
    path.write_text(json.dumps(entry, sort_keys=True) + "\n")

    with pytest.raises(
        orchestrate.OrchestrationError, match="campaign_ledger_schema_invalid"
    ):
        orchestrate.validate_campaign_ledger(path)


def test_validate_campaign_ledger_append_only_requires_byte_prefix(tmp_path):
    first = _campaign_ledger_entry("campaign-1", previous_entry_sha256=None)
    second = _campaign_ledger_entry(
        "campaign-2", previous_entry_sha256=first["entry_sha256"]
    )
    base = tmp_path / "base.jsonl"
    current = tmp_path / "current.jsonl"
    first_line = json.dumps(first, sort_keys=True) + "\n"
    base.write_text(first_line)
    current.write_text(first_line + json.dumps(second, sort_keys=True) + "\n")

    assert orchestrate.validate_campaign_ledger_append_only(base, current) == [
        first,
        second,
    ]

    rewritten = {**first, "recorded_at": "2026-08-12T00:00:01Z"}
    canonical = {
        key: value for key, value in rewritten.items() if key != "entry_sha256"
    }
    rewritten["entry_sha256"] = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    current.write_text(json.dumps(rewritten, sort_keys=True) + "\n")
    with pytest.raises(
        orchestrate.OrchestrationError, match="campaign_ledger_history_rewritten"
    ):
        orchestrate.validate_campaign_ledger_append_only(base, current)


@pytest.mark.parametrize(
    ("state", "attempt", "ceiling"),
    [("exhausted", None, None), ("historical_closed", 1, 1)],
)
def test_validate_campaign_ledger_rejects_contradictory_authorization(
    tmp_path, state, attempt, ceiling
):
    entry = _campaign_ledger_entry("campaign-1", previous_entry_sha256=None)
    entry["authorization"] = {
        "state": state,
        "attempt": attempt,
        "ceiling": ceiling,
    }
    canonical = {key: value for key, value in entry.items() if key != "entry_sha256"}
    entry["entry_sha256"] = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = tmp_path / "campaign-ledger.jsonl"
    path.write_text(json.dumps(entry, sort_keys=True) + "\n")

    with pytest.raises(
        orchestrate.OrchestrationError, match="campaign_ledger_schema_invalid"
    ):
        orchestrate.validate_campaign_ledger(path)


def test_checked_in_campaign_ledger_is_valid():
    ledger = (
        MODULE_PATH.parents[2] / "docs/operations/control-plan-campaign-ledger.jsonl"
    )
    historical_prefix = b"\n".join(ledger.read_bytes().splitlines()[:2]) + b"\n"

    assert hashlib.sha256(historical_prefix).hexdigest() == (
        "45970d9a2240eb2090a7958d9add373fb5ec4ef6068b38d04ae4ac22ce4f4261"
    )

    assert hashlib.sha256(ledger.read_bytes()).hexdigest() == (
        "18c2b4a6168b2f547ea873bcc8dee0a88450416d0998b75752ffc7196eb2d741"
    )

    entries = orchestrate.validate_campaign_ledger(ledger)

    assert [
        {
            "campaign_id": entry["campaign_id"],
            "candidate_sha256": hashlib.sha256(
                json.dumps(
                    entry["candidate"], sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest(),
            "guest": entry["guest"],
            "evidence": entry["evidence"],
            "entry_sha256": entry["entry_sha256"],
        }
        for entry in entries
    ] == [
        {
            "campaign_id": "2026-08-09-nine-stage-orbstack-0228f495",
            "candidate_sha256": "a061dcf5a9568d0779648a98f35746ed02e1399ed4d2289307f5e686ffd8a424",
            "guest": {
                "architecture": "arm64",
                "id": None,
                "name": "munbon-control-plan-local",
            },
            "evidence": {
                "index_name": "SHA256SUMS",
                "index_sha256": "25924dd828c416a1199cc178a3d31e28a2032b18216eb87a74f9ca3b59892632",
                "ref": "coding-logs/evidence/2026-08-09-nine-stage-orbstack-0228f495",
            },
            "entry_sha256": "1ebd77862cc20fedec0c3e8e381e5915541ceae06a495514b8a2e753724293b2",
        },
        {
            "campaign_id": "2026-08-12-nine-stage-orbstack-5cfdb2a0-attempt-3",
            "candidate_sha256": "88854daa52e4786125f36ae96d037681447014b3fa71ec39a92c178bae57cbdc",
            "guest": {
                "architecture": "arm64",
                "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
                "name": "munbon-control-plan-local",
            },
            "evidence": {
                "index_name": "OUTER-SHA256SUMS",
                "index_sha256": "34b952b660ec230ab2d9049b60f6dd8496561ce6e2860b377124c8ae48947ecd",
                "ref": "../munbon2-backend-external-evidence/2026-08-12-nine-stage-orbstack-5cfdb2a0-attempt-3",
            },
            "entry_sha256": "fe2cb916578a1c6ded0c4087f99be832639b3f72af74fcf35ae5f98c9b03f810",
        },
        {
            "campaign_id": "2026-08-20-nine-stage-orbstack-7f032c4c-attempt-1",
            "candidate_sha256": "7d2cb9a50b1c80896a4c5892deeb3b612227c5aa32e5e7f8c6934e98a29eee11",
            "guest": {
                "architecture": "arm64",
                "id": "01M0F27Z1GZQ7SQF07XH9M3VQT",
                "name": "munbon-control-plan-local",
            },
            "evidence": {
                "index_name": "OUTER-SHA256SUMS",
                "index_sha256": "903602d8ae622c5de72ffa31c705782ae663dfd6dc9a53d4450c6aa5e0c1bbef",
                "ref": "../munbon-control-plan-9of9-evidence/2026-08-20-nine-stage-orbstack-7f032c4c-attempt-1",
            },
            "entry_sha256": "585467a896065b42a40982eb08c1f3447e1b5439928bcca50fc471a7595e51aa",
        },
    ]

    assert [entry["outcome"] for entry in entries] == [
        {
            "acceptance": False,
            "passed": list(orchestrate.CAMPAIGN_LEDGER_V1_STAGE_ORDER[:7]),
            "failed": [orchestrate.CAMPAIGN_LEDGER_V1_STAGE_ORDER[7]],
            "unreached": [orchestrate.CAMPAIGN_LEDGER_V1_STAGE_ORDER[8]],
        },
        {
            "acceptance": False,
            "passed": list(orchestrate.CAMPAIGN_LEDGER_V1_STAGE_ORDER[:2]),
            "failed": [orchestrate.CAMPAIGN_LEDGER_V1_STAGE_ORDER[2]],
            "unreached": list(orchestrate.CAMPAIGN_LEDGER_V1_STAGE_ORDER[3:]),
        },
        {
            "acceptance": True,
            "passed": list(orchestrate.CAMPAIGN_LEDGER_V1_STAGE_ORDER),
            "failed": [],
            "unreached": [],
        },
    ]
    assert [entry["authorization"] for entry in entries] == [
        {"state": "historical_closed", "attempt": None, "ceiling": None},
        {"state": "exhausted", "attempt": 3, "ceiling": 3},
        {"state": "successful_closed", "attempt": 1, "ceiling": 1},
    ]


def test_host_accepts_pre_python_failure_bundle_and_state(tmp_path):
    local_dir = Path(__file__).resolve().parents[1]
    helper = local_dir / "bootstrap-provisioning-state.sh"
    state_root = tmp_path / "guest-provisioning"
    destination = tmp_path / "host-failure"
    release_sha = "a" * 40
    frontend_sha = "b" * 40
    dependency_sha = "c" * 64

    subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; '
            'write_bootstrap_state "$2" created "$3" "$4" "$5" bootstrap arguments; '
            'write_pre_python_failure "$2" "$3" "$4" "$5" '
            "base_packages offline-debian-packages 1 false",
            "bootstrap-state-test",
            str(helper),
            str(state_root),
            release_sha,
            frontend_sha,
            dependency_sha,
        ],
        check=True,
    )
    shutil.copytree(state_root / "failure", destination / "bundle")

    state = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
    metadata = orchestrate.finalize_bootstrap_failure_bundle(destination)

    assert metadata["classification"] == "nonretryable-bootstrap"
    assert orchestrate.validate_failure_state_matches_metadata(state, metadata) is None


def test_failed_executable_contract_writer_falls_back_to_collectable_shell_bundle(
    tmp_path,
):
    local_dir = Path(__file__).resolve().parents[1]
    helper = local_dir / "bootstrap-provisioning-state.sh"
    state_root = tmp_path / "guest-provisioning"
    destination = tmp_path / "host-failure"
    log_path = tmp_path / "bootstrap.log"
    release_sha = "a" * 40
    frontend_sha = "b" * 40
    dependency_sha = "c" * 64
    log_path.write_text("untrusted raw output\n", encoding="utf-8")

    subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; '
            'write_bootstrap_state "$2" created "$3" "$4" "$5" bootstrap arguments; '
            'write_bootstrap_failure "$2" "$3" "$4" "$5" '
            'base_packages offline-debian-packages 1 false "$6" /usr/bin/false "$1" /usr',
            "bootstrap-state-test",
            str(helper),
            str(state_root),
            release_sha,
            frontend_sha,
            dependency_sha,
            str(log_path),
        ],
        check=True,
    )
    shutil.copytree(state_root / "failure", destination / "bundle")

    state = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
    metadata = orchestrate.finalize_bootstrap_failure_bundle(destination)

    assert (state["state"], metadata["state"]) == ("failed", "failed")
    assert (destination / "bundle" / "bootstrap-sanitized.log").read_text() == (
        "FAIL bootstrap_base_packages\n"
    )
    assert orchestrate.validate_failure_state_matches_metadata(state, metadata) is None


def test_working_contract_writer_is_preferred_and_sanitizes_raw_log(tmp_path):
    local_dir = Path(__file__).resolve().parents[1]
    helper = local_dir / "bootstrap-provisioning-state.sh"
    contract = local_dir / "provisioning_contract.py"
    state_root = tmp_path / "guest-provisioning"
    log_path = tmp_path / "bootstrap.log"
    release_sha = "a" * 40
    frontend_sha = "b" * 40
    dependency_sha = "c" * 64
    log_path.write_text("password=must-not-survive\n", encoding="utf-8")

    subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; '
            'write_bootstrap_state "$2" created "$3" "$4" "$5" bootstrap arguments; '
            'write_bootstrap_failure "$2" "$3" "$4" "$5" '
            'node_runtime node-archive 1 false "$6" "$7" "$8" /usr',
            "bootstrap-state-test",
            str(helper),
            str(state_root),
            release_sha,
            frontend_sha,
            dependency_sha,
            str(log_path),
            sys.executable,
            str(contract),
        ],
        check=True,
    )

    assert (state_root / "failure" / "bootstrap-sanitized.log").read_text() == (
        "[REDACTED SECRET-SHAPED LOG LINE]\n"
    )


def test_validate_failure_state_matches_preserved_metadata():
    recorded_at = "2026-08-10T10:00:00Z"
    state = {
        "state": "failed",
        "dependency_sha256": "c" * 64,
        "release_sha": "a" * 40,
        "frontend_sha": "b" * 40,
        "phase": "dependency-staging",
        "recorded_at": recorded_at,
        "substep": "auth-npm-ci",
    }
    metadata = {
        **state,
        "classification": "retryable-transport",
        "exit_code": 1,
        "tool_versions": {"node": "v22.23.1", "npm": "10.9.8"},
    }

    assert orchestrate.validate_failure_state_matches_metadata(state, metadata) is None

    metadata["release_sha"] = "d" * 40
    with pytest.raises(
        orchestrate.OrchestrationError,
        match="bootstrap_failure_state_metadata_mismatch",
    ):
        orchestrate.validate_failure_state_matches_metadata(state, metadata)


def test_validate_dependency_archive_accepts_only_exact_content_bound_archive(
    tmp_path,
):
    repo = tmp_path / "repo"
    frontend = tmp_path / "frontend"
    bundle_root = tmp_path / "payload" / "bundle"
    bundle_root.mkdir(parents=True)
    provisioning = sys.modules["provisioning_contract"]
    for relative_name in provisioning.BACKEND_DEPENDENCY_INPUTS:
        path = repo / relative_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative_name)
    frontend.mkdir()
    (frontend / "package-lock.json").write_text("frontend-lock")
    deb_body = b"deb"
    packages = (
        "Package: example\n"
        "Version: 1.0\n"
        "Architecture: arm64\n"
        "Filename: ./example_1.0_arm64.deb\n"
        f"Size: {len(deb_body)}\n"
        f"SHA256: {hashlib.sha256(deb_body).hexdigest()}\n"
    ).encode()
    bundle_artifacts = {
        "debian/Packages": packages,
        "debian/Packages.gz": gzip.compress(packages, mtime=0),
        "debian/example_1.0_arm64.deb": deb_body,
        "debian/package-names.txt": b"example\n",
        "debian/package-specs.txt": b"example=1.0\n",
        "install-debian-closure-linux.sh": b"#!/usr/bin/env bash\n",
    }
    for relative_name, body in bundle_artifacts.items():
        path = bundle_root / relative_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    release_sha = "a" * 40
    frontend_sha = "b" * 40
    provisioning.create_dependency_manifest(
        bundle_root,
        repo_root=repo,
        frontend_root=frontend,
        release_sha=release_sha,
        frontend_sha=frontend_sha,
    )
    archive = tmp_path / "dependencies.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        stream.add(bundle_root, arcname="bundle")
    archive_sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()

    assert (
        orchestrate.validate_dependency_archive(
            archive,
            archive_sha256,
            repo=repo,
            release_sha=release_sha,
            frontend_repo=frontend,
            frontend_sha=frontend_sha,
        )
        is None
    )

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="dependency_archive_checksum_mismatch",
    ):
        orchestrate.validate_dependency_archive(
            archive,
            "0" * 64,
            repo=repo,
            release_sha=release_sha,
            frontend_repo=frontend,
            frontend_sha=frontend_sha,
        )


def test_provision_collects_failure_bundle_and_returns_only_safe_classification(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    frontend = tmp_path / "frontend"
    dependency_archive = tmp_path / "dependencies.tar.gz"
    failure_directory = tmp_path / "failure"
    verifier = repo / "ops/control-plan-read-runtime/verify_bearer.py"
    verifier.parent.mkdir(parents=True)
    verifier.write_text("pass\n")
    dependency_archive.write_bytes(b"bundle")
    machine_states = iter(("missing", "ready"))
    collected = []

    monkeypatch.setattr(orchestrate, "_validate_commit", lambda *_a: None)
    monkeypatch.setattr(
        orchestrate, "validate_dependency_archive", lambda *_a, **_k: None
    )
    monkeypatch.setattr(orchestrate, "_machine_state", lambda: next(machine_states))

    def fake_run_checked(code, _argv, **_kwargs):
        if code == "bootstrap_linux":
            raise orchestrate.CommandExecutionError(code, 1)
        return ""

    def fake_create_bundle(_repo, _sha, target):
        target.write_bytes(b"git-bundle")

    monkeypatch.setattr(orchestrate, "_run_checked", fake_run_checked)
    monkeypatch.setattr(orchestrate, "_create_bundle", fake_create_bundle)
    monkeypatch.setattr(orchestrate, "_push_isolated_file", lambda *_a: None)
    monkeypatch.setattr(
        orchestrate,
        "collect_bootstrap_failure",
        lambda destination: collected.append(destination)
        or {"classification": "retryable-transport"},
    )

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="^bootstrap_linux_failed_retryable_transport$",
    ):
        orchestrate.provision(
            repo,
            "a" * 40,
            frontend,
            "b" * 40,
            dependency_archive,
            "c" * 64,
            failure_directory,
        )

    assert collected == [failure_directory]


def test_provision_rehearsal_automatically_finalizes_failure_bundle(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    frontend = tmp_path / "frontend"
    dependency_archive = tmp_path / "dependencies.tar.gz"
    failure_directory = tmp_path / "rehearsal-failure"
    verifier = repo / "ops/control-plan-read-runtime/verify_bearer.py"
    verifier.parent.mkdir(parents=True)
    verifier.write_text("pass\n")
    dependency_archive.write_bytes(b"bundle")
    machine_states = iter(("missing", "ready"))
    collected = []

    monkeypatch.setattr(orchestrate, "_validate_commit", lambda *_args: None)
    monkeypatch.setattr(
        orchestrate, "validate_dependency_archive", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        orchestrate, "_rehearsal_machine_state", lambda: next(machine_states)
    )

    def fail_bootstrap(code, _argv, **_kwargs):
        if code == "bootstrap_linux":
            raise orchestrate.CommandExecutionError(code, 1)
        return ""

    monkeypatch.setattr(orchestrate, "_run_checked", fail_bootstrap)
    monkeypatch.setattr(
        orchestrate,
        "_create_bundle",
        lambda _repo, _sha, target: target.write_bytes(b"git-bundle"),
    )
    monkeypatch.setattr(
        orchestrate, "_push_rehearsal_isolated_file", lambda *_args: None
    )
    monkeypatch.setattr(
        orchestrate,
        "collect_bootstrap_failure",
        lambda destination, *, execution_kind="canonical": collected.append(
            (destination, execution_kind)
        )
        or {"classification": "retryable-transport"},
    )

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="^bootstrap_linux_failed_retryable_transport$",
    ):
        orchestrate.provision_rehearsal(
            repo,
            "a" * 40,
            frontend,
            "b" * 40,
            dependency_archive,
            "c" * 64,
            failure_directory,
        )

    assert collected == [(failure_directory, "rehearsal")]


def test_provision_rehearsal_targets_only_fixed_guest_and_marks_bootstrap_kind(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    frontend = tmp_path / "frontend"
    dependency_archive = tmp_path / "dependencies.tar.gz"
    failure_directory = tmp_path / "failure"
    verifier = repo / "ops/control-plan-read-runtime/verify_bearer.py"
    verifier.parent.mkdir(parents=True)
    verifier.write_text("pass\n")
    dependency_archive.write_bytes(b"bundle")
    machine_states = iter(("missing", "ready"))
    commands = []
    pushed = []
    monkeypatch.setattr(orchestrate, "_validate_commit", lambda *_args: None)
    monkeypatch.setattr(
        orchestrate, "validate_dependency_archive", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        orchestrate, "_rehearsal_machine_state", lambda: next(machine_states)
    )
    monkeypatch.setattr(
        orchestrate,
        "_run_checked",
        lambda code, argv, **_kwargs: commands.append((code, argv)) or "",
    )
    monkeypatch.setattr(
        orchestrate,
        "_create_bundle",
        lambda _repo, _sha, target: target.write_bytes(b"git-bundle"),
    )
    monkeypatch.setattr(
        orchestrate,
        "_push_rehearsal_isolated_file",
        lambda source, destination: pushed.append((source.name, destination)),
    )

    orchestrate.provision_rehearsal(
        repo,
        "a" * 40,
        frontend,
        "b" * 40,
        dependency_archive,
        "c" * 64,
        failure_directory,
    )

    assert commands[0] == (
        "orb_create",
        orchestrate.build_rehearsal_machine_command(),
    )
    for code, argv in commands[1:]:
        if code in {"guest_input_directory", "bootstrap_linux"}:
            assert argv[argv.index("-m") + 1] == "munbon-control-plan-rehearsal"
    bootstrap = next(argv for code, argv in commands if code == "bootstrap_linux")
    assert bootstrap[-1] == "rehearsal"
    assert pushed and all(
        destination == f"/opt/munbon/input/{name}" for name, destination in pushed
    )


def test_push_rehearsal_isolated_file_targets_only_fixed_guest(tmp_path, monkeypatch):
    source = tmp_path / "source.bundle"
    source.write_bytes(b"bundle")
    commands = []

    def capture_upload(argv, **_kwargs):
        commands.append(argv)
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(orchestrate.subprocess, "run", capture_upload)

    orchestrate._push_rehearsal_isolated_file(source, "/opt/munbon/input/source.bundle")

    assert commands == [
        orchestrate.build_rehearsal_isolated_write_command(
            "/opt/munbon/input/source.bundle"
        )
    ]
    assert commands[0][commands[0].index("-m") + 1] == ("munbon-control-plan-rehearsal")


def test_run_checked_classifies_host_timeout_for_failure_collection(monkeypatch):
    def raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["orb"], 3600)

    monkeypatch.setattr(orchestrate.subprocess, "run", raise_timeout)

    with pytest.raises(orchestrate.CommandExecutionError) as failure:
        orchestrate._run_checked("bootstrap_linux", ["orb"], timeout=3600)

    assert (failure.value.code, failure.value.returncode) == (
        "bootstrap_linux",
        124,
    )


def test_build_isolated_write_command_targets_only_fixed_guest_directory():
    assert orchestrate.build_isolated_write_command(
        "/opt/munbon/input/source.bundle"
    ) == [
        "orb",
        "-m",
        "munbon-control-plan-local",
        "-u",
        "root",
        "tee",
        "/opt/munbon/input/source.bundle",
    ]

    with pytest.raises(
        orchestrate.OrchestrationError, match="isolated_destination_invalid"
    ):
        orchestrate.build_isolated_write_command("/home/munbonlocal/source.bundle")


def test_parser_and_stage_runner_accept_completed_local_gates():
    for stage in (
        "LOCAL-AC-1",
        "LOCAL-READ-ACT-1",
        "LOCAL-EVIDENCE-1",
        "LOCAL-GO-READ-1",
    ):
        args = orchestrate._parse_args(
            [
                "run-stage",
                "--stage",
                stage,
                "--release-sha",
                orchestrate.ACCEPTED_BASE_SHA,
            ]
        )
        assert args.stage == stage


def test_run_all_executes_every_progressive_stage(monkeypatch):
    calls = []
    monkeypatch.setattr(
        orchestrate,
        "run_stage",
        lambda stage, release_sha, frontend_sha, as_of_date=None: calls.append(
            (stage, release_sha, frontend_sha)
        ),
    )

    orchestrate.run_all_stages("a" * 40, "b" * 40)

    assert calls == [(stage, "a" * 40, "b" * 40) for stage in orchestrate.STAGE_ORDER]


def test_run_rehearsal_stage_allows_only_the_fixed_three_stage_prefix(monkeypatch):
    calls = []
    monkeypatch.setattr(
        orchestrate,
        "_run_stage",
        lambda stage, release_sha, frontend_sha, **kwargs: calls.append(
            (stage, release_sha, frontend_sha, kwargs)
        ),
    )

    orchestrate.run_rehearsal_stage(
        "LOCAL-AC-1", "a" * 40, "b" * 40, as_of_date="2026-08-16"
    )

    assert calls == [
        (
            "LOCAL-AC-1",
            "a" * 40,
            "b" * 40,
            {"as_of_date": "2026-08-16", "execution_kind": "rehearsal"},
        )
    ]
    with pytest.raises(orchestrate.OrchestrationError, match="stage_not_supported"):
        orchestrate.run_rehearsal_stage("LOCAL-READ-ACT-1", "a" * 40, "b" * 40)


def test_parser_exposes_only_explicit_rehearsal_actions():
    for action in (
        "provision-rehearsal",
        "run-rehearsal-stage",
        "collect-rehearsal",
        "collect-rehearsal-partial-failure",
        "collect-rehearsal-bootstrap-failure",
    ):
        args = orchestrate._parse_args([action])
        assert args.action == action


def _capture_ready_stage_command(code, argv, captured):
    if code == "stage_provision_state":
        return json.dumps(
            {
                "dependency_sha256": "c" * 64,
                "frontend_sha": "b" * 40,
                "phase": "complete",
                "recorded_at": "2026-08-10T10:00:00Z",
                "release_sha": "a" * 40,
                "state": "ready",
                "substep": "ready-state",
            }
        )
    if code == "stage_machine_owner":
        return json.dumps(
            {
                "architecture": "arm64",
                "dependency_sha256": "c" * 64,
                "frontend_sha": "b" * 40,
                "machine": "munbon-control-plan-local",
                "release_sha": "a" * 40,
                "state": "ready",
            }
        )
    captured["argv"] = argv
    return ""


def test_run_stage_forwards_as_of_date_to_the_guest_cli(monkeypatch):
    captured = {}
    monkeypatch.setattr(orchestrate, "_machine_state", lambda: "ready")
    monkeypatch.setattr(
        orchestrate,
        "_run_checked",
        lambda code, argv, **kwargs: _capture_ready_stage_command(code, argv, captured),
    )

    orchestrate.run_stage(
        "LOCAL-PERSIST-ONLY-1", "a" * 40, "b" * 40, as_of_date="2026-11-02"
    )

    argv = captured["argv"]
    assert "--as-of-date" in argv
    assert argv[argv.index("--as-of-date") + 1] == "2026-11-02"


def test_run_stage_omits_as_of_date_when_not_pinned(monkeypatch):
    captured = {}
    monkeypatch.setattr(orchestrate, "_machine_state", lambda: "ready")
    monkeypatch.setattr(
        orchestrate,
        "_run_checked",
        lambda code, argv, **kwargs: _capture_ready_stage_command(code, argv, captured),
    )

    orchestrate.run_stage("LOCAL-PERSIST-ONLY-1", "a" * 40, "b" * 40)

    assert "--as-of-date" not in captured["argv"]


def test_run_stage_uses_extended_timeout_only_for_write_activation(monkeypatch):
    captured = {}
    monkeypatch.setattr(orchestrate, "_machine_state", lambda: "ready")

    def record(code, argv, **kwargs):
        if code in {"stage_provision_state", "stage_machine_owner"}:
            return _capture_ready_stage_command(code, argv, captured)
        if code == "stage_terminal_failure":
            return ""
        captured["stage_code"] = code
        captured["timeout"] = kwargs["timeout"]
        return ""

    monkeypatch.setattr(orchestrate, "_run_checked", record)

    orchestrate.run_stage("LOCAL-WRITE-ACT-1", "a" * 40, "b" * 40)

    assert captured == {
        "stage_code": "local_write_act_1",
        "timeout": 7200,
    }


def test_run_stage_surfaces_failure_manifest_publication_exit(monkeypatch):
    captured = {}
    monkeypatch.setattr(orchestrate, "_machine_state", lambda: "ready")

    def fail_stage_publication(code, argv, **kwargs):
        if code in {"stage_provision_state", "stage_machine_owner"}:
            return _capture_ready_stage_command(code, argv, captured)
        if code == "stage_terminal_failure":
            return ""
        raise orchestrate.CommandExecutionError(
            code, orchestrate.FAILURE_MANIFEST_EXIT_CODE
        )

    monkeypatch.setattr(orchestrate, "_run_checked", fail_stage_publication)

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="stage_failure_manifest_publication_failed",
    ):
        orchestrate.run_stage("LOCAL-WRITE-UI-1", "a" * 40, "b" * 40)


def test_run_rehearsal_stage_refuses_any_existing_failure_before_execution(monkeypatch):
    captured = {}
    monkeypatch.setattr(orchestrate, "_rehearsal_machine_state", lambda: "ready")

    def terminal_failure(code, argv, **kwargs):
        if code in {"stage_provision_state", "stage_machine_owner"}:
            state_or_owner = _capture_ready_stage_command(code, argv, captured)
            if code == "stage_machine_owner":
                owner = json.loads(state_or_owner)
                owner.update(
                    {
                        "machine": "munbon-control-plan-rehearsal",
                        "execution_kind": "rehearsal",
                        "acceptance_evidence": False,
                    }
                )
                return json.dumps(owner)
            return state_or_owner
        if code == "stage_terminal_failure":
            return "LOCAL-RTA-1-failure.json\n"
        pytest.fail("stage command must not run")

    monkeypatch.setattr(orchestrate, "_run_checked", terminal_failure)

    with pytest.raises(orchestrate.OrchestrationError, match="stage_failure_terminal"):
        orchestrate.run_rehearsal_stage("LOCAL-RTA-1", "a" * 40, "b" * 40)


def test_run_all_forwards_as_of_date_to_every_stage(monkeypatch):
    calls = []
    monkeypatch.setattr(
        orchestrate,
        "run_stage",
        lambda stage, release_sha, frontend_sha, as_of_date=None: calls.append(
            (stage, as_of_date)
        ),
    )

    orchestrate.run_all_stages("a" * 40, "b" * 40, as_of_date="2026-11-02")

    assert calls == [(stage, "2026-11-02") for stage in orchestrate.STAGE_ORDER]


def test_parse_args_accepts_as_of_date():
    args = orchestrate._parse_args(
        [
            "run-all",
            "--release-sha",
            orchestrate.ACCEPTED_BASE_SHA,
            "--as-of-date",
            "2026-11-02",
        ]
    )
    assert args.as_of_date == "2026-11-02"


@pytest.mark.parametrize("as_of_date", ["2026-13-99", "20260816"])
def test_main_rejects_noncanonical_as_of_date(as_of_date, monkeypatch, capsys):
    monkeypatch.setattr(orchestrate, "_origin_main_sha", lambda path: "a" * 40)
    monkeypatch.setattr(
        orchestrate, "run_all_stages", lambda *a, **k: pytest.fail("must not run")
    )

    exit_code = orchestrate.main(
        [
            "run-all",
            "--release-sha",
            "a" * 40,
            "--frontend-sha",
            "a" * 40,
            "--accept-later-origin-main",
            "--as-of-date",
            as_of_date,
        ]
    )

    assert exit_code == 1
    assert "as_of_date_not_accepted" in capsys.readouterr().out


def test_orchestrator_stage_order_matches_suite_stage_order():
    suite_path = Path(__file__).resolve().parents[1] / "run-stage-suite.py"
    suite_source = suite_path.read_text(encoding="utf-8")
    match = re.search(
        r"^STAGE_ORDER\s*=\s*\((.*?)\)",
        suite_source,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None
    suite_stages = tuple(
        line.strip().strip(",").strip().strip('"').strip("'")
        for line in match.group(1).splitlines()
        if line.strip() and not line.strip().startswith("#")
    )

    assert orchestrate.STAGE_ORDER == suite_stages


def test_parser_accepts_persist_only_stage():
    args = orchestrate._parse_args(
        [
            "run-stage",
            "--stage",
            "LOCAL-PERSIST-ONLY-1",
            "--release-sha",
            orchestrate.ACCEPTED_BASE_SHA,
        ]
    )
    assert args.stage == "LOCAL-PERSIST-ONLY-1"


def test_parser_accepts_write_ui_stage():
    args = orchestrate._parse_args(
        [
            "run-stage",
            "--stage",
            "LOCAL-WRITE-UI-1",
            "--release-sha",
            orchestrate.ACCEPTED_BASE_SHA,
        ]
    )
    assert args.stage == "LOCAL-WRITE-UI-1"


def test_documented_candidate_commands_validate_the_same_exact_shas(
    tmp_path, monkeypatch
):
    backend_repo = tmp_path / "backend"
    frontend_repo = tmp_path / "frontend"
    evidence_dir = tmp_path / "evidence"
    dependency_bundle = tmp_path / "dependencies.tar.gz"
    failure_dir = tmp_path / "bootstrap-failure"
    backend_sha = "a" * 40
    frontend_sha = "b" * 40
    calls = []
    monkeypatch.setattr(
        orchestrate,
        "_origin_main_sha",
        lambda path: backend_sha if path == backend_repo else frontend_sha,
    )
    monkeypatch.setattr(
        orchestrate,
        "provision",
        lambda repo, release_sha, frontend, accepted_frontend_sha, bundle, bundle_sha256, bootstrap_failure_dir: calls.append(
            (
                "provision",
                repo,
                release_sha,
                frontend,
                accepted_frontend_sha,
                bundle,
                bundle_sha256,
                bootstrap_failure_dir,
            )
        ),
    )
    monkeypatch.setattr(
        orchestrate,
        "run_stage",
        lambda stage, release_sha, accepted_frontend_sha, as_of_date=None: calls.append(
            (stage, release_sha, accepted_frontend_sha)
        ),
    )
    monkeypatch.setattr(
        orchestrate,
        "collect_evidence",
        lambda destination: calls.append(("collect", destination)),
    )
    common = [
        "--repo",
        str(backend_repo),
        "--frontend-repo",
        str(frontend_repo),
        "--release-sha",
        backend_sha,
        "--frontend-sha",
        frontend_sha,
        "--accept-later-origin-main",
    ]
    commands = (
        [
            "provision",
            "--dependency-bundle",
            str(dependency_bundle),
            "--dependency-bundle-sha256",
            "c" * 64,
            "--bootstrap-failure-dir",
            str(failure_dir),
        ],
        *(["run-stage", "--stage", stage] for stage in orchestrate.STAGE_ORDER),
        ["collect", "--evidence-dir", str(evidence_dir)],
    )

    assert [orchestrate.main([*command, *common]) for command in commands] == [0] * len(
        commands
    )
    assert calls == [
        (
            "provision",
            backend_repo,
            backend_sha,
            frontend_repo,
            frontend_sha,
            dependency_bundle,
            "c" * 64,
            failure_dir,
        ),
        *((stage, backend_sha, frontend_sha) for stage in orchestrate.STAGE_ORDER),
        ("collect", evidence_dir),
    ]


def test_failure_collection_does_not_depend_on_current_origin_main(
    tmp_path, monkeypatch
):
    destination = tmp_path / "bootstrap-failure"
    collected = []

    monkeypatch.setattr(
        orchestrate,
        "_origin_main_sha",
        lambda _path: (_ for _ in ()).throw(AssertionError("origin must not be read")),
    )
    monkeypatch.setattr(
        orchestrate,
        "collect_bootstrap_failure",
        lambda target: collected.append(target),
    )

    assert (
        orchestrate.main(
            [
                "collect-bootstrap-failure",
                "--bootstrap-failure-dir",
                str(destination),
            ]
        )
        == 0
    )
    assert collected == [destination]


def test_rehearsal_bootstrap_failure_collection_does_not_inspect_repositories(
    tmp_path, monkeypatch
):
    destination = tmp_path / "rehearsal-bootstrap-failure"
    collected = []
    monkeypatch.setattr(
        orchestrate,
        "_origin_main_sha",
        lambda _path: (_ for _ in ()).throw(AssertionError("origin must not be read")),
    )
    monkeypatch.setattr(
        orchestrate,
        "collect_rehearsal_bootstrap_failure",
        lambda target: collected.append(target),
    )

    assert (
        orchestrate.main(
            [
                "collect-rehearsal-bootstrap-failure",
                "--bootstrap-failure-dir",
                str(destination),
            ]
        )
        == 0
    )
    assert collected == [destination]


def test_documented_rehearsal_actions_bind_exact_candidates_and_fixed_handlers(
    tmp_path, monkeypatch
):
    backend_repo = tmp_path / "backend"
    frontend_repo = tmp_path / "frontend"
    dependency_bundle = tmp_path / "dependencies.tar.gz"
    failure_dir = tmp_path / "bootstrap-failure"
    evidence_dir = tmp_path / "evidence"
    backend_sha = "a" * 40
    frontend_sha = "b" * 40
    calls = []
    monkeypatch.setattr(
        orchestrate,
        "_origin_main_sha",
        lambda path: backend_sha if path == backend_repo else frontend_sha,
    )
    monkeypatch.setattr(
        orchestrate,
        "provision_rehearsal",
        lambda repo, release_sha, frontend, accepted_frontend_sha, bundle, bundle_sha256, bootstrap_failure_dir: calls.append(
            (
                "provision",
                repo,
                release_sha,
                frontend,
                accepted_frontend_sha,
                bundle,
                bundle_sha256,
                bootstrap_failure_dir,
            )
        ),
    )
    monkeypatch.setattr(
        orchestrate,
        "run_rehearsal_stage",
        lambda stage, release_sha, accepted_frontend_sha, as_of_date=None: calls.append(
            (stage, release_sha, accepted_frontend_sha, as_of_date)
        ),
    )
    monkeypatch.setattr(
        orchestrate,
        "collect_rehearsal",
        lambda destination, _release_sha, _frontend_sha, as_of_date: calls.append(
            ("collect", destination, as_of_date)
        )
        or {"acceptance_evidence": False},
    )
    monkeypatch.setattr(
        orchestrate,
        "collect_rehearsal_partial_failure",
        lambda destination, _release_sha, _frontend_sha, as_of_date: calls.append(
            ("partial", destination, as_of_date)
        )
        or {"acceptance_evidence": False},
    )
    common = [
        "--repo",
        str(backend_repo),
        "--frontend-repo",
        str(frontend_repo),
        "--release-sha",
        backend_sha,
        "--frontend-sha",
        frontend_sha,
        "--accept-later-origin-main",
    ]
    commands = (
        [
            "provision-rehearsal",
            "--dependency-bundle",
            str(dependency_bundle),
            "--dependency-bundle-sha256",
            "c" * 64,
            "--bootstrap-failure-dir",
            str(failure_dir),
        ],
        [
            "run-rehearsal-stage",
            "--stage",
            "LOCAL-AC-1",
            "--as-of-date",
            "2026-08-16",
        ],
        [
            "collect-rehearsal",
            "--evidence-dir",
            str(evidence_dir),
            "--as-of-date",
            "2026-08-16",
        ],
        [
            "collect-rehearsal-partial-failure",
            "--evidence-dir",
            str(evidence_dir),
            "--as-of-date",
            "2026-08-16",
        ],
    )

    assert [orchestrate.main([*command, *common]) for command in commands] == [
        0,
        0,
        0,
        0,
    ]
    assert calls == [
        (
            "provision",
            backend_repo,
            backend_sha,
            frontend_repo,
            frontend_sha,
            dependency_bundle,
            "c" * 64,
            failure_dir,
        ),
        ("LOCAL-AC-1", backend_sha, frontend_sha, "2026-08-16"),
        ("collect", evidence_dir, "2026-08-16"),
        ("partial", evidence_dir, "2026-08-16"),
    ]


@pytest.mark.parametrize(
    "action", ["collect-rehearsal", "collect-rehearsal-partial-failure"]
)
def test_rehearsal_collection_requires_authorized_operational_date(
    action, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(orchestrate, "_origin_main_sha", lambda _path: "a" * 40)

    assert (
        orchestrate.main(
            [
                action,
                "--release-sha",
                "a" * 40,
                "--frontend-sha",
                "a" * 40,
                "--accept-later-origin-main",
                "--evidence-dir",
                str(tmp_path / "evidence"),
            ]
        )
        == 1
    )
    assert "as_of_date_required" in capsys.readouterr().out


def _rc_machine(guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS"):
    return {
        "id": guest_id,
        "name": "munbon-control-plan-local",
        "image": {"distro": "debian", "version": "bookworm", "arch": "arm64"},
        "config": {
            "isolated": True,
            "isolate_network": True,
            "default_username": "munbonlocal",
            "memory_limit_mib": 8192,
            "cpu_limit": 4,
            "disk_limit_bytes": 40 * 1024**3,
        },
        "state": "running",
    }


def test_validate_rc_guest_identity_accepts_only_the_expected_immutable_guest():
    guest_id = "01KZSKQ6FY4EVCCY94XGWZ9NDS"
    unrelated = {**_rc_machine("01KZSKQ6FY4EVCCY94XGWZ9NDT"), "name": "unrelated"}

    assert orchestrate.validate_rc_guest_identity(
        json.dumps([unrelated, _rc_machine()]), guest_id
    ) == {
        "name": "munbon-control-plan-local",
        "id": guest_id,
        "architecture": "arm64",
    }


@pytest.mark.parametrize(
    "inventory",
    [
        [_rc_machine("01KZSKQ6FY4EVCCY94XGWZ9NDT")],
        [_rc_machine(), _rc_machine()],
        [{**_rc_machine(), "state": "stopped"}],
        [
            {
                **_rc_machine(),
                "image": {"distro": "ubuntu", "version": "24.04", "arch": "arm64"},
            }
        ],
        [
            {
                **_rc_machine(),
                "image": {"distro": "debian", "version": "bookworm", "arch": "amd64"},
            }
        ],
    ],
)
def test_validate_rc_guest_identity_rejects_identity_or_shape_drift(inventory):
    with pytest.raises(
        orchestrate.OrchestrationError, match="rc_guest_identity_not_accepted"
    ):
        orchestrate.validate_rc_guest_identity(
            json.dumps(inventory), "01KZSKQ6FY4EVCCY94XGWZ9NDS"
        )


def test_validated_rc_guest_binds_inventory_owner_and_dependency_archive(monkeypatch):
    responses = {
        "rc_orb_inventory": json.dumps([_rc_machine()]),
        "rc_provision_state": json.dumps(
            {
                "dependency_sha256": "c" * 64,
                "frontend_sha": "b" * 40,
                "phase": "complete",
                "recorded_at": "2026-11-02T00:00:00Z",
                "release_sha": "a" * 40,
                "state": "ready",
                "substep": "ready-state",
            }
        ),
        "rc_machine_owner": json.dumps(
            {
                "architecture": "arm64",
                "dependency_sha256": "c" * 64,
                "frontend_sha": "b" * 40,
                "machine": "munbon-control-plan-local",
                "release_sha": "a" * 40,
                "state": "ready",
            }
        ),
        "rc_guest_machine_id": "f" * 32 + "\n",
    }
    inventory_reads = []

    def checked(code, _argv, **_kwargs):
        if code == "rc_orb_inventory":
            inventory_reads.append(code)
        return responses[code]

    monkeypatch.setattr(
        orchestrate,
        "_run_checked",
        checked,
    )

    assert orchestrate._validated_rc_guest(
        "a" * 40,
        "b" * 40,
        "c" * 64,
        "01KZSKQ6FY4EVCCY94XGWZ9NDS",
    ) == {
        "name": "munbon-control-plan-local",
        "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
        "architecture": "arm64",
        "dependency_sha256": "c" * 64,
        "machine_id": "f" * 32,
    }
    assert inventory_reads == ["rc_orb_inventory", "rc_orb_inventory"]

    with pytest.raises(
        orchestrate.OrchestrationError, match="rc_dependency_identity_mismatch"
    ):
        orchestrate._validated_rc_guest(
            "a" * 40,
            "b" * 40,
            "d" * 64,
            "01KZSKQ6FY4EVCCY94XGWZ9NDS",
        )


def test_run_rc_revalidates_identity_around_every_no_retry_phase(monkeypatch, tmp_path):
    events = []
    guest = {
        "name": "munbon-control-plan-local",
        "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
        "architecture": "arm64",
        "dependency_sha256": "c" * 64,
        "machine_id": "f" * 32,
    }

    def validate(*_args, **_kwargs):
        events.append("identity")
        return guest

    def phase(name, *_args, **_kwargs):
        events.append(name)

    monkeypatch.setattr(orchestrate, "_validated_rc_guest", validate, raising=False)
    monkeypatch.setattr(orchestrate, "_run_rc_phase", phase, raising=False)
    monkeypatch.setattr(
        orchestrate,
        "run_stage",
        lambda stage, *_args, **_kwargs: events.append(stage),
    )
    monkeypatch.setattr(
        orchestrate,
        "collect_rc",
        lambda *_args, **_kwargs: events.append("collect") or {"verdict": "PASS"},
        raising=False,
    )

    assert orchestrate.run_rc(
        release_sha="a" * 40,
        frontend_sha="b" * 40,
        dependency_sha256="c" * 64,
        guest_id=guest["id"],
        destination=tmp_path / "rc-evidence",
        as_of_date="2026-11-02",
    ) == {"verdict": "PASS"}
    assert events == [
        "identity",
        "preflight",
        "identity",
        *[
            event
            for stage in orchestrate.STAGE_ORDER
            for event in ("identity", stage, "identity")
        ],
        "identity",
        "finalize",
        "identity",
        "identity",
        "collect",
        "identity",
    ]


@pytest.mark.parametrize(
    "replacement",
    (
        {"machine_id": "e" * 32},
        {"id": "01KZSKQ6FY4EVCCY94XGWZ9NDT"},
    ),
)
def test_run_rc_pins_the_first_guest_identity_for_the_entire_lifecycle(
    monkeypatch, tmp_path, replacement
):
    accepted = {
        "name": "munbon-control-plan-local",
        "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
        "architecture": "arm64",
        "dependency_sha256": "c" * 64,
        "machine_id": "f" * 32,
    }
    changed = {**accepted, **replacement}
    validation_count = [0]

    def validate(*_args):
        validation_count[0] += 1
        return accepted if validation_count[0] == 1 else changed

    monkeypatch.setattr(orchestrate, "_validated_rc_guest", validate)
    monkeypatch.setattr(orchestrate, "_run_rc_phase", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        orchestrate,
        "run_stage",
        lambda *_args, **_kwargs: pytest.fail("replacement must block dispatch"),
    )
    monkeypatch.setattr(
        orchestrate,
        "collect_rc",
        lambda *_args, **_kwargs: pytest.fail("replacement must block collection"),
    )

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="rc_guest_machine_identity_mismatch",
    ):
        orchestrate.run_rc(
            "a" * 40,
            "b" * 40,
            "c" * 64,
            accepted["id"],
            tmp_path / "rc",
            "2026-11-02",
        )

    assert validation_count == [2]


def test_run_rc_rejects_noncanonical_date_before_guest_inspection(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        orchestrate,
        "_validated_rc_guest",
        lambda *_args, **_kwargs: pytest.fail("guest inspection must not run"),
    )

    with pytest.raises(
        orchestrate.OrchestrationError, match="rc_arguments_not_accepted"
    ):
        orchestrate.run_rc(
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="c" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            destination=tmp_path / "rc-evidence",
            as_of_date="2026-99-99",
        )


def test_run_rc_phase_uses_explicit_canonical_guest_execution(monkeypatch):
    captured = {}

    def record(code, argv, **kwargs):
        captured.update({"code": code, "argv": argv, "timeout": kwargs["timeout"]})
        return ""

    monkeypatch.setattr(orchestrate, "_run_checked", record)

    orchestrate._run_rc_phase(
        "preflight",
        "a" * 40,
        "b" * 40,
        "c" * 64,
        "01KZSKQ6FY4EVCCY94XGWZ9NDS",
        "2026-11-02",
        expected_machine_id="f" * 32,
    )

    assert captured["code"] == "rc_preflight"
    assert captured["timeout"] == 2400
    assert captured["argv"][captured["argv"].index("--execution-kind") + 1] == (
        "canonical"
    )
    assert captured["argv"][captured["argv"].index("--expected-machine-id") + 1] == (
        "f" * 32
    )


@pytest.mark.parametrize("phase", ("preflight", "finalize"))
def test_run_rc_phase_surfaces_failure_manifest_publication_exit(monkeypatch, phase):
    monkeypatch.setattr(
        orchestrate,
        "_run_checked",
        lambda code, _argv, **_kwargs: (_ for _ in ()).throw(
            orchestrate.CommandExecutionError(
                code, orchestrate.FAILURE_MANIFEST_EXIT_CODE
            )
        ),
    )

    with pytest.raises(
        orchestrate.OrchestrationError,
        match=f"rc_{phase}_failure_manifest_publication_failed",
    ):
        orchestrate._run_rc_phase(
            phase,
            "a" * 40,
            "b" * 40,
            "c" * 64,
            "01KZSKQ6FY4EVCCY94XGWZ9NDS",
            "2026-11-02",
            expected_machine_id="f" * 32,
        )


def test_run_rc_passes_the_revalidated_machine_id_to_every_guest_dispatch(
    monkeypatch, tmp_path
):
    phase_machine_ids = []
    stage_machine_ids = []
    collection_machine_ids = []
    guest = {
        "name": "munbon-control-plan-local",
        "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
        "architecture": "arm64",
        "dependency_sha256": "c" * 64,
        "machine_id": "f" * 32,
    }
    monkeypatch.setattr(orchestrate, "_validated_rc_guest", lambda *_args: guest)
    monkeypatch.setattr(
        orchestrate,
        "_run_rc_phase",
        lambda _phase, *_args, expected_machine_id: phase_machine_ids.append(
            expected_machine_id
        ),
    )
    monkeypatch.setattr(
        orchestrate,
        "run_stage",
        lambda _stage, *_args, expected_machine_id, **_kwargs: stage_machine_ids.append(
            expected_machine_id
        ),
    )
    monkeypatch.setattr(
        orchestrate,
        "collect_rc",
        lambda *_args, expected_machine_id: collection_machine_ids.append(
            expected_machine_id
        )
        or {"verdict": "PASS"},
    )

    orchestrate.run_rc(
        "a" * 40,
        "b" * 40,
        "c" * 64,
        guest["id"],
        tmp_path / "rc",
        "2026-11-02",
    )

    assert phase_machine_ids == ["f" * 32, "f" * 32]
    assert stage_machine_ids == ["f" * 32] * len(orchestrate.STAGE_ORDER)
    assert collection_machine_ids == ["f" * 32]


def test_run_rc_rejects_existing_destination_before_guest_inspection(
    monkeypatch, tmp_path
):
    destination = tmp_path / "existing"
    destination.mkdir()
    monkeypatch.setattr(
        orchestrate,
        "_validated_rc_guest",
        lambda *_args, **_kwargs: pytest.fail("guest inspection must not run"),
        raising=False,
    )

    with pytest.raises(
        orchestrate.OrchestrationError, match="rc_evidence_destination_exists"
    ):
        orchestrate.run_rc(
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="c" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            destination=destination,
            as_of_date="2026-11-02",
        )


def test_run_rc_stops_on_first_failure_without_retry_finalize_or_collect(
    monkeypatch, tmp_path
):
    events = []
    failure = orchestrate.OrchestrationError("stage_failed")
    monkeypatch.setattr(
        orchestrate,
        "_validated_rc_guest",
        lambda *_args, **_kwargs: events.append("identity") or {"machine_id": "f" * 32},
        raising=False,
    )
    monkeypatch.setattr(
        orchestrate,
        "_run_rc_phase",
        lambda phase, *_args, **_kwargs: events.append(phase),
        raising=False,
    )

    def run_stage(stage, *_args, **_kwargs):
        events.append(stage)
        if stage == "LOCAL-AC-1":
            raise failure

    monkeypatch.setattr(orchestrate, "run_stage", run_stage)
    monkeypatch.setattr(
        orchestrate,
        "collect_rc",
        lambda *_args, **_kwargs: pytest.fail("collection must not run"),
        raising=False,
    )

    with pytest.raises(orchestrate.OrchestrationError) as caught:
        orchestrate.run_rc(
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="c" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            destination=tmp_path / "rc-evidence",
            as_of_date="2026-11-02",
        )

    assert caught.value is failure
    assert events == [
        "identity",
        "preflight",
        "identity",
        "identity",
        "LOCAL-BASE-0",
        "identity",
        "identity",
        "LOCAL-RTA-1",
        "identity",
        "identity",
        "LOCAL-AC-1",
        "identity",
    ]


def test_run_rc_preserves_the_primary_failure_when_identity_postcheck_also_fails(
    monkeypatch, tmp_path
):
    primary = orchestrate.OrchestrationError("base_probe_failed")
    accepted = {
        "name": "munbon-control-plan-local",
        "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
        "architecture": "arm64",
        "dependency_sha256": "c" * 64,
        "machine_id": "f" * 32,
    }
    changed = {**accepted, "machine_id": "e" * 32}
    validations = []

    def validate(*_args):
        validations.append("identity")
        return changed if len(validations) == 4 else accepted

    monkeypatch.setattr(orchestrate, "_validated_rc_guest", validate)
    monkeypatch.setattr(orchestrate, "_run_rc_phase", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        orchestrate,
        "run_stage",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(primary),
    )
    monkeypatch.setattr(
        orchestrate,
        "collect_rc",
        lambda *_args, **_kwargs: pytest.fail("collection must not run"),
    )

    with pytest.raises(orchestrate.OrchestrationError) as caught:
        orchestrate.run_rc(
            "a" * 40,
            "b" * 40,
            "c" * 64,
            accepted["id"],
            tmp_path / "rc",
            "2026-11-02",
        )

    assert caught.value is primary
    assert caught.value.identity_postcheck_error == (
        "rc_guest_machine_identity_mismatch"
    )
    assert validations == ["identity"] * 4


@pytest.mark.parametrize("interrupt", (KeyboardInterrupt(), SystemExit(23)))
def test_run_rc_propagates_a_postcheck_interrupt_after_an_ordinary_failure(
    monkeypatch, tmp_path, interrupt
):
    primary = orchestrate.OrchestrationError("base_probe_failed")
    guest = {
        "name": "munbon-control-plan-local",
        "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
        "architecture": "arm64",
        "dependency_sha256": "c" * 64,
        "machine_id": "f" * 32,
    }
    validations = []
    stages = []

    def validate(*_args):
        validations.append("identity")
        if len(validations) == 4:
            raise interrupt
        return guest

    monkeypatch.setattr(orchestrate, "_validated_rc_guest", validate)
    monkeypatch.setattr(orchestrate, "_run_rc_phase", lambda *_args, **_kwargs: None)

    def fail_stage(stage, *_args, **_kwargs):
        stages.append(stage)
        raise primary

    monkeypatch.setattr(orchestrate, "run_stage", fail_stage)
    monkeypatch.setattr(
        orchestrate,
        "collect_rc",
        lambda *_args, **_kwargs: pytest.fail("collection must not run"),
    )

    with pytest.raises(BaseException) as caught:
        orchestrate.run_rc(
            "a" * 40,
            "b" * 40,
            "c" * 64,
            guest["id"],
            tmp_path / "rc",
            "2026-11-02",
        )

    assert caught.value is interrupt
    assert caught.value.__cause__ is primary
    assert validations == ["identity"] * 4
    assert stages == ["LOCAL-BASE-0"]


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt(), SystemExit(17)])
def test_run_rc_preserves_interrupt_identity_without_follow_on_actions(
    monkeypatch, tmp_path, interrupt
):
    events = []
    monkeypatch.setattr(
        orchestrate,
        "_validated_rc_guest",
        lambda *_args, **_kwargs: events.append("identity") or {"machine_id": "f" * 32},
        raising=False,
    )
    monkeypatch.setattr(
        orchestrate,
        "_run_rc_phase",
        lambda phase, *_args, **_kwargs: events.append(phase),
        raising=False,
    )

    def run_stage(stage, *_args, **_kwargs):
        events.append(stage)
        raise interrupt

    monkeypatch.setattr(orchestrate, "run_stage", run_stage)
    monkeypatch.setattr(
        orchestrate,
        "collect_rc",
        lambda *_args, **_kwargs: pytest.fail("collection must not run"),
        raising=False,
    )

    with pytest.raises(BaseException) as caught:
        orchestrate.run_rc(
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="c" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            destination=tmp_path / "rc-evidence",
            as_of_date="2026-11-02",
        )

    assert caught.value is interrupt
    assert events == [
        "identity",
        "preflight",
        "identity",
        "identity",
        "LOCAL-BASE-0",
        "identity",
    ]


def _write_complete_rc_evidence(destination: Path) -> dict:
    state = _write_complete_acceptance_evidence(destination)
    state["harness_hashes"] = _authorized_rc_harness_hashes()
    (destination / "stage-state.json").write_text(
        json.dumps(state, sort_keys=True) + "\n", encoding="utf-8"
    )
    guest = {
        "name": "munbon-control-plan-local",
        "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
        "architecture": "arm64",
        "machine_id": "f" * 32,
    }
    preflight_record = _rc_preflight_record()
    (destination / "RC-PREFLIGHT.json").write_text(
        json.dumps(preflight_record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _bind_rc_stage_evidence(destination)
    preflight_bytes = (
        json.dumps(preflight_record, indent=2, sort_keys=True) + "\n"
    ).encode()
    runtime = _rc_test_runtime_proof()
    write_activation_sha256 = hashlib.sha256(
        (destination / "LOCAL-WRITE-ACT-1.json").read_bytes()
    ).hexdigest()
    manifest = {
        "schema_version": 1,
        "stage": "LOCAL-RC-1",
        "verdict": "PASS",
        "release_sha": state["release_sha"],
        "frontend_sha": state["frontend_sha"],
        "dependency_sha256": "d" * 64,
        "guest": guest,
        "as_of_date": "2026-11-02",
        "preflight": {
            "verdict": "PASS",
            "evidence_root_empty": True,
            "database_clean": True,
            "rate_state_clean": True,
            "actionable_commands": 0,
            "sources_clean": True,
            "runtime_dark": True,
            "record": preflight_record,
            "record_sha256": hashlib.sha256(preflight_bytes).hexdigest(),
        },
        "final": {
            "verdict": "PASS",
            "completed": list(orchestrate.STAGE_ORDER),
            "runtime_dark": True,
            "processes_stable": True,
            "readiness_green": True,
            "listeners_accepted": True,
            "immutable_history": True,
            "proof": {
                "processes": runtime["processes"],
                "dark_contract": runtime["dark_contract_after"],
                "frontend_activation_gates": runtime["final_activation_gates"],
                "readiness": runtime["readiness"],
                "listeners": runtime["listeners"],
                "persist_snapshot_sha256": "e" * 64,
                "rate_state": {},
                "rate_minimum_elapsed_ms": 900000,
                "rate_snapshot_started_monotonic_ms": 920000,
                "rate_snapshot_completed_monotonic_ms": 921000,
                "write_activation_manifest_sha256": write_activation_sha256,
            },
        },
    }
    summary = {
        "schema_version": 1,
        "evidence_kind": "local_release_candidate",
        "acceptance": "LOCAL-RC-1",
        "acceptance_evidence": True,
        "campaign_ledger_eligible": False,
        "aws_actions_authorized": False,
        "release_sha": state["release_sha"],
        "frontend_sha": state["frontend_sha"],
        "dependency_sha256": "d" * 64,
        "guest": guest,
        "as_of_date": "2026-11-02",
        "passed": [*orchestrate.STAGE_ORDER, "LOCAL-RC-1"],
        "failed": [],
        "unreached": [],
        "verdict": "PASS",
    }
    (destination / "LOCAL-RC-1.json").write_text(
        json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
    )
    (destination / "RC-SUMMARY.json").write_text(
        json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_acceptance_checksums(destination)
    return summary


def test_finalize_rc_collection_binds_exact_identity_and_writes_only_rc_indexes(
    tmp_path,
):
    destination = tmp_path / "rc-evidence"
    expected = _write_complete_rc_evidence(destination)

    assert (
        orchestrate.finalize_rc_collection(
            destination,
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="d" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            as_of_date="2026-11-02",
        )
        == expected
    )
    assert not (destination / "OUTER-SHA256SUMS").exists()
    assert (destination / "RC-SHA256SUMS").is_file()
    rc_index = (destination / "RC-SHA256SUMS").read_text().splitlines()
    assert rc_index == [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(destination.iterdir())
        if path.name not in {"RC-SHA256SUMS", "RC-OUTER-SHA256SUMS"}
    ]
    outer = (destination / "RC-OUTER-SHA256SUMS").read_text().splitlines()
    assert outer == [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(destination.iterdir())
        if path.name != "RC-OUTER-SHA256SUMS"
    ]


@pytest.mark.parametrize("mutation", ["record", "digest"])
def test_finalize_rc_collection_rejects_preflight_record_or_digest_substitution(
    tmp_path, mutation
):
    destination = tmp_path / mutation
    _write_complete_rc_evidence(destination)
    manifest_path = destination / "LOCAL-RC-1.json"
    manifest = json.loads(manifest_path.read_text())
    if mutation == "record":
        manifest["preflight"]["record"]["guest"]["id"] = "01KZSKQ6FY4EVCCY94XGWZ9NDT"
    else:
        manifest["preflight"]["record_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")
    _write_acceptance_checksums(destination)

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="rc_evidence_identity_mismatch",
    ):
        orchestrate.finalize_rc_collection(
            destination,
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="d" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            as_of_date="2026-11-02",
        )


@pytest.mark.parametrize("mutation", ("missing", "date"))
def test_finalize_rc_collection_rejects_stage_attempt_lineage_drift(tmp_path, mutation):
    destination = tmp_path / f"stage-lineage-{mutation}"
    _write_complete_rc_evidence(destination)
    stage_path = destination / "LOCAL-BASE-0.json"
    manifest = json.loads(stage_path.read_text())
    if mutation == "missing":
        manifest.pop("rc_attempt")
    else:
        manifest["rc_attempt"]["as_of_date"] = "2026-11-03"
    stage_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")
    _write_acceptance_checksums(destination)

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="rc_evidence_identity_mismatch",
    ):
        orchestrate.finalize_rc_collection(
            destination,
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="d" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            as_of_date="2026-11-02",
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "process",
        "dark",
        "readiness",
        "listener",
        "persist",
        "rate",
        "rate_elapsed",
        "rate_elapsed_high",
        "rate_timing",
        "write_digest",
    ),
)
def test_finalize_rc_collection_rejects_unproved_final_runtime_or_history(
    tmp_path, mutation
):
    destination = tmp_path / mutation
    _write_complete_rc_evidence(destination)
    manifest_path = destination / "LOCAL-RC-1.json"
    manifest = json.loads(manifest_path.read_text())
    proof = manifest["final"]["proof"]
    if mutation == "process":
        proof["processes"][0]["pid"] += 1
    elif mutation == "dark":
        proof["dark_contract"]["planning_depth_writes"] = True
    elif mutation == "readiness":
        proof["readiness"].pop("scheduler")
    elif mutation == "listener":
        proof["listeners"][0]["address"] = "0.0.0.0"
    elif mutation == "persist":
        proof["persist_snapshot_sha256"] = "f" * 64
    elif mutation == "rate":
        proof["rate_state"] = {
            "bff-water-planning:rate:planning_depth.submit:"
            + "f"
            * 64: {
                "value": 1,
                "ttl_ms": 1000,
            }
        }
    elif mutation == "rate_elapsed":
        proof["rate_minimum_elapsed_ms"] = 899999
    elif mutation == "rate_elapsed_high":
        proof["rate_minimum_elapsed_ms"] = 900001
    elif mutation == "rate_timing":
        proof["rate_snapshot_started_monotonic_ms"] = 920101
    else:
        proof["write_activation_manifest_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")
    _write_acceptance_checksums(destination)

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="rc_evidence_identity_mismatch",
    ):
        orchestrate.finalize_rc_collection(
            destination,
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="d" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            as_of_date="2026-11-02",
        )


@pytest.mark.parametrize(
    "rate_row",
    (
        {"value": 4, "ttl_ms": 1000},
        {"value": 3, "ttl_ms": 1},
        {"value": 3, "ttl_ms": 300001},
    ),
)
def test_finalize_rc_collection_rejects_counter_or_ttl_drift_from_write_act(
    tmp_path, rate_row
):
    destination = tmp_path / f"rate-{rate_row['value']}-{rate_row['ttl_ms']}"
    _write_complete_rc_evidence(destination)
    manifest_path = destination / "LOCAL-RC-1.json"
    manifest = json.loads(manifest_path.read_text())
    write_key = (
        "bff-water-planning:rate:planning_depth.submit:"
        + hashlib.sha256(b"operator-write").hexdigest()
    )
    manifest["final"]["proof"]["rate_state"] = {write_key: rate_row}
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")
    _write_acceptance_checksums(destination)

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="rc_evidence_identity_mismatch",
    ):
        orchestrate.finalize_rc_collection(
            destination,
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="d" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            as_of_date="2026-11-02",
        )


def test_finalize_rc_collection_accepts_a_surviving_key_at_the_decay_bound(tmp_path):
    destination = tmp_path / "rate-decay-bound"
    _write_complete_rc_evidence(destination)
    write_path = destination / "LOCAL-WRITE-ACT-1.json"
    write_manifest = json.loads(write_path.read_text())
    write_manifest["steps"]["rate_state_after_browser"]["minimum_elapsed_ms"] = 1000
    write_manifest["steps"]["rate_state_after_browser"][
        "snapshot_completed_monotonic_ms"
    ] = 20000
    write_path.write_text(json.dumps(write_manifest, sort_keys=True) + "\n")
    rc_path = destination / "LOCAL-RC-1.json"
    rc_manifest = json.loads(rc_path.read_text())
    write_key = (
        "bff-water-planning:rate:planning_depth.submit:"
        + hashlib.sha256(b"operator-write").hexdigest()
    )
    rc_manifest["final"]["proof"]["rate_state"] = {
        write_key: {"value": 3, "ttl_ms": 5000}
    }
    rc_manifest["final"]["proof"]["rate_minimum_elapsed_ms"] = 1000
    rc_manifest["final"]["proof"]["rate_snapshot_started_monotonic_ms"] = 21000
    rc_manifest["final"]["proof"]["rate_snapshot_completed_monotonic_ms"] = 22000
    rc_manifest["final"]["proof"]["write_activation_manifest_sha256"] = hashlib.sha256(
        write_path.read_bytes()
    ).hexdigest()
    rc_path.write_text(json.dumps(rc_manifest, sort_keys=True) + "\n")
    _write_acceptance_checksums(destination)

    summary = orchestrate.finalize_rc_collection(
        destination,
        release_sha="a" * 40,
        frontend_sha="b" * 40,
        dependency_sha256="d" * 64,
        guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
        as_of_date="2026-11-02",
    )

    assert summary["verdict"] == "PASS"


def test_finalize_rc_collection_rejects_ttl_above_the_guest_final_elapsed_bound(
    tmp_path,
):
    destination = tmp_path / "rate-final-decay"
    _write_complete_rc_evidence(destination)
    write_path = destination / "LOCAL-WRITE-ACT-1.json"
    write_manifest = json.loads(write_path.read_text())
    rate_reference = write_manifest["steps"]["rate_state_after_browser"]
    rate_reference["minimum_elapsed_ms"] = 1000
    rate_reference["snapshot_completed_monotonic_ms"] = 20000
    write_path.write_text(json.dumps(write_manifest, sort_keys=True) + "\n")
    rc_path = destination / "LOCAL-RC-1.json"
    rc_manifest = json.loads(rc_path.read_text())
    write_key = (
        "bff-water-planning:rate:planning_depth.submit:"
        + hashlib.sha256(b"operator-write").hexdigest()
    )
    rc_manifest["final"]["proof"]["rate_state"] = {
        write_key: {"value": 3, "ttl_ms": 4000}
    }
    rc_manifest["final"]["proof"]["rate_minimum_elapsed_ms"] = 3000
    rc_manifest["final"]["proof"]["rate_snapshot_started_monotonic_ms"] = 23000
    rc_manifest["final"]["proof"]["rate_snapshot_completed_monotonic_ms"] = 24000
    rc_manifest["final"]["proof"]["write_activation_manifest_sha256"] = hashlib.sha256(
        write_path.read_bytes()
    ).hexdigest()
    rc_path.write_text(json.dumps(rc_manifest, sort_keys=True) + "\n")
    _write_acceptance_checksums(destination)

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="rc_evidence_identity_mismatch",
    ):
        orchestrate.finalize_rc_collection(
            destination,
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="d" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            as_of_date="2026-11-02",
        )


@pytest.mark.parametrize(
    ("snapshot_started_ms", "snapshot_completed_ms", "accepted"),
    (
        (21000, 22000, False),
        (25000, 27000, False),
        (26000, 27000, True),
        (27000, 28000, True),
    ),
)
def test_finalize_rc_collection_accepts_a_missing_rate_key_only_after_expiry(
    tmp_path, snapshot_started_ms, snapshot_completed_ms, accepted
):
    destination = tmp_path / f"missing-rate-{snapshot_started_ms}"
    _write_complete_rc_evidence(destination)
    write_path = destination / "LOCAL-WRITE-ACT-1.json"
    write_manifest = json.loads(write_path.read_text())
    rate_reference = write_manifest["steps"]["rate_state_after_browser"]
    rate_reference["minimum_elapsed_ms"] = 1000
    rate_reference["snapshot_completed_monotonic_ms"] = 20000
    write_path.write_text(json.dumps(write_manifest, sort_keys=True) + "\n")
    rc_path = destination / "LOCAL-RC-1.json"
    rc_manifest = json.loads(rc_path.read_text())
    proof = rc_manifest["final"]["proof"]
    proof["rate_state"] = {}
    proof["rate_minimum_elapsed_ms"] = max(1000, snapshot_started_ms - 20000)
    proof["rate_snapshot_started_monotonic_ms"] = snapshot_started_ms
    proof["rate_snapshot_completed_monotonic_ms"] = snapshot_completed_ms
    proof["write_activation_manifest_sha256"] = hashlib.sha256(
        write_path.read_bytes()
    ).hexdigest()
    rc_path.write_text(json.dumps(rc_manifest, sort_keys=True) + "\n")
    _write_acceptance_checksums(destination)

    if not accepted:
        with pytest.raises(
            orchestrate.OrchestrationError,
            match="rc_evidence_identity_mismatch",
        ):
            orchestrate.finalize_rc_collection(
                destination,
                release_sha="a" * 40,
                frontend_sha="b" * 40,
                dependency_sha256="d" * 64,
                guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
                as_of_date="2026-11-02",
            )
        return

    summary = orchestrate.finalize_rc_collection(
        destination,
        release_sha="a" * 40,
        frontend_sha="b" * 40,
        dependency_sha256="d" * 64,
        guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
        as_of_date="2026-11-02",
    )

    assert summary["verdict"] == "PASS"


def _write_rc_partial_failure_evidence(destination: Path, phase: str):
    if phase == "preflight":
        destination.mkdir(parents=True)
        completed = []
        failure = {
            "stage": "LOCAL-RC-1",
            "rc_phase": "preflight",
            "verdict": "FAIL",
            "release_sha": "a" * 40,
            "frontend_sha": "b" * 40,
            "dependency_sha256": "d" * 64,
            "guest": _rc_preflight_record()["guest"],
            "harness_hashes": _authorized_rc_harness_hashes(),
            "as_of_date": "2026-11-02",
            "failed_gate": "rc_database_not_clean",
            "failed_at": "2026-11-02T01:02:03Z",
        }
        (destination / "LOCAL-RC-1-failure.json").write_text(
            json.dumps(failure, sort_keys=True) + "\n"
        )
    elif phase == "stage":
        completed = list(orchestrate.STAGE_ORDER[:2])
        state = _write_partial_failure_evidence(destination, completed_count=2)
        state["harness_hashes"] = _authorized_rc_harness_hashes()
        (destination / "stage-state.json").write_text(
            json.dumps(state, sort_keys=True) + "\n"
        )
        (destination / "RC-PREFLIGHT.json").write_text(
            json.dumps(_rc_preflight_record(), indent=2, sort_keys=True) + "\n"
        )
        _bind_rc_stage_evidence(destination)
    elif phase == "finalize":
        completed = list(orchestrate.STAGE_ORDER)
        state = _write_complete_acceptance_evidence(destination)
        state["harness_hashes"] = _authorized_rc_harness_hashes()
        (destination / "stage-state.json").write_text(
            json.dumps(state, sort_keys=True) + "\n"
        )
        (destination / "RC-PREFLIGHT.json").write_text(
            json.dumps(_rc_preflight_record(), indent=2, sort_keys=True) + "\n"
        )
        _bind_rc_stage_evidence(destination)
        failure = {
            "stage": "LOCAL-RC-1",
            "rc_phase": "finalize",
            "verdict": "FAIL",
            "release_sha": "a" * 40,
            "frontend_sha": "b" * 40,
            "dependency_sha256": "d" * 64,
            "guest": _rc_preflight_record()["guest"],
            "as_of_date": "2026-11-02",
            "failed_gate": "rc_finalize_runtime_dark_invalid",
            "failed_at": "2026-11-02T01:02:03Z",
        }
        (destination / "LOCAL-RC-1-failure.json").write_text(
            json.dumps(failure, sort_keys=True) + "\n"
        )
    else:
        raise AssertionError(phase)
    _write_acceptance_checksums(destination)
    return completed


@pytest.mark.parametrize("phase", ("preflight", "stage", "finalize"))
def test_finalize_rc_partial_failure_collection_covers_each_failure_boundary(
    tmp_path, phase
):
    destination = tmp_path / phase
    completed = _write_rc_partial_failure_evidence(destination, phase)

    summary = orchestrate.finalize_rc_partial_failure_collection(
        destination,
        release_sha="a" * 40,
        frontend_sha="b" * 40,
        dependency_sha256="d" * 64,
        guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
        as_of_date="2026-11-02",
    )

    failed_stage = "LOCAL-AC-1" if phase == "stage" else "LOCAL-RC-1"
    expected_unreached = (
        list(orchestrate.STAGE_ORDER)
        if phase == "preflight"
        else (
            [*orchestrate.STAGE_ORDER[len(completed) + 1 :], "LOCAL-RC-1"]
            if phase == "stage"
            else []
        )
    )
    assert summary == {
        "schema_version": 1,
        "evidence_kind": "local_release_candidate_partial_failure",
        "acceptance": "LOCAL-RC-1",
        "acceptance_evidence": False,
        "campaign_ledger_eligible": False,
        "aws_actions_authorized": False,
        "release_sha": "a" * 40,
        "frontend_sha": "b" * 40,
        "dependency_sha256": "d" * 64,
        "guest": {
            "name": "munbon-control-plan-local",
            "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
            "architecture": "arm64",
            "machine_id": "f" * 32,
        },
        "as_of_date": "2026-11-02",
        "phase": phase,
        "passed": completed,
        "failed": [failed_stage],
        "failed_gate": (
            "manual_requirement_run_not_accepted"
            if phase == "stage"
            else (
                "rc_database_not_clean"
                if phase == "preflight"
                else "rc_finalize_runtime_dark_invalid"
            )
        ),
        "unreached": expected_unreached,
        "verdict": "FAIL",
    }
    assert not (destination / "SHA256SUMS").exists()
    assert not (destination / "OUTER-SHA256SUMS").exists()
    assert not (destination / "PARTIAL-OUTER-SHA256SUMS").exists()
    assert (destination / "RC-PARTIAL-SHA256SUMS").is_file()
    assert (destination / "RC-PARTIAL-OUTER-SHA256SUMS").is_file()
    outer = (destination / "RC-PARTIAL-OUTER-SHA256SUMS").read_text().splitlines()
    assert outer == [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(destination.iterdir())
        if path.name != "RC-PARTIAL-OUTER-SHA256SUMS"
    ]


@pytest.mark.parametrize("mutation", ("missing", "incomplete", "mismatch"))
def test_rc_preflight_partial_requires_the_exact_host_harness_inventory(
    monkeypatch, tmp_path, mutation
):
    destination = tmp_path / mutation
    _write_rc_partial_failure_evidence(destination, "preflight")
    failure_path = destination / "LOCAL-RC-1-failure.json"
    failure = json.loads(failure_path.read_text(encoding="utf-8"))
    if mutation == "missing":
        failure.pop("harness_hashes")
    elif mutation == "incomplete":
        failure["harness_hashes"].pop(next(iter(failure["harness_hashes"])))
    else:
        first = next(iter(failure["harness_hashes"]))
        failure["harness_hashes"][first] = "f" * 64
    failure_path.write_text(json.dumps(failure, sort_keys=True) + "\n")
    _write_acceptance_checksums(destination)
    monkeypatch.setattr(
        orchestrate,
        "_host_harness_hashes",
        _authorized_rc_harness_hashes,
    )

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="rc_partial_evidence_identity_mismatch",
    ):
        orchestrate.finalize_rc_partial_failure_collection(
            destination,
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="d" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            as_of_date="2026-11-02",
        )


@pytest.mark.parametrize(
    ("mutation", "error"),
    (
        ("campaign_index", "rc_partial_evidence_inventory_invalid"),
        ("identity", "rc_partial_evidence_identity_mismatch"),
        ("gap", "rc_partial_evidence_stage_sequence_invalid"),
    ),
)
def test_finalize_rc_partial_failure_collection_rejects_drift(
    tmp_path, mutation, error
):
    destination = tmp_path / mutation
    if mutation == "gap":
        _write_rc_partial_failure_evidence(destination, "stage")
        source = destination / "LOCAL-AC-1-failure.json"
        failure = json.loads(source.read_text())
        failure["stage"] = "LOCAL-READ-ACT-1"
        source.unlink()
        (destination / "LOCAL-READ-ACT-1-failure.json").write_text(
            json.dumps(failure, sort_keys=True) + "\n"
        )
    else:
        _write_rc_partial_failure_evidence(destination, "preflight")
        if mutation == "campaign_index":
            (destination / "OUTER-SHA256SUMS").write_text("campaign-shaped\n")
        else:
            failure_path = destination / "LOCAL-RC-1-failure.json"
            failure = json.loads(failure_path.read_text())
            failure["release_sha"] = "f" * 40
            failure_path.write_text(json.dumps(failure, sort_keys=True) + "\n")
    _write_acceptance_checksums(destination)

    with pytest.raises(orchestrate.OrchestrationError, match=error):
        orchestrate.finalize_rc_partial_failure_collection(
            destination,
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="d" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            as_of_date="2026-11-02",
        )


def test_rc_partial_rejects_an_ordinary_campaign_failure_without_rc_preflight(
    tmp_path,
):
    destination = tmp_path / "ordinary"
    state = _write_partial_failure_evidence(destination, completed_count=2)
    state["harness_hashes"] = _authorized_rc_harness_hashes()
    (destination / "stage-state.json").write_text(
        json.dumps(state, sort_keys=True) + "\n"
    )
    _write_acceptance_checksums(destination)

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="rc_partial_evidence_identity_mismatch",
    ):
        orchestrate.finalize_rc_partial_failure_collection(
            destination,
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="d" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            as_of_date="2026-11-02",
        )


def test_rc_preflight_partial_rejects_collector_supplied_date_drift(tmp_path):
    destination = tmp_path / "preflight-date-drift"
    _write_rc_partial_failure_evidence(destination, "preflight")

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="rc_partial_evidence_identity_mismatch",
    ):
        orchestrate.finalize_rc_partial_failure_collection(
            destination,
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="d" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            as_of_date="2026-11-03",
        )


def test_rc_partial_rejects_a_stage_failure_from_another_operational_date(tmp_path):
    destination = tmp_path / "stage-date-drift"
    _write_rc_partial_failure_evidence(destination, "stage")
    failure_path = destination / "LOCAL-AC-1-failure.json"
    failure = json.loads(failure_path.read_text())
    failure["rc_attempt"]["as_of_date"] = "2026-11-03"
    failure_path.write_text(json.dumps(failure, sort_keys=True) + "\n")
    _write_acceptance_checksums(destination)

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="rc_partial_evidence_identity_mismatch",
    ):
        orchestrate.finalize_rc_partial_failure_collection(
            destination,
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="d" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            as_of_date="2026-11-02",
        )


@pytest.mark.parametrize(
    ("failed_stage", "failed_artifacts"),
    (
        ("LOCAL-GO-READ-1", ()),
        ("LOCAL-GO-READ-1", ("LOCAL-GO-READ-1-live.png",)),
        (
            "LOCAL-GO-READ-1",
            ("LOCAL-GO-READ-1-live.png", "LOCAL-GO-READ-1-outage.png"),
        ),
        ("LOCAL-WRITE-UI-1", ("LOCAL-WRITE-UI-1-browser-result.json",)),
        ("LOCAL-WRITE-ACT-1", ("LOCAL-WRITE-ACT-1-browser-result.json",)),
    ),
)
def test_rc_partial_accepts_bounded_auxiliary_evidence_from_the_failed_stage(
    tmp_path, failed_stage, failed_artifacts
):
    destination = tmp_path / failed_stage
    completed_count = orchestrate.STAGE_ORDER.index(failed_stage)
    state = _write_partial_failure_evidence(
        destination, completed_count=completed_count
    )
    state["harness_hashes"] = _authorized_rc_harness_hashes()
    (destination / "stage-state.json").write_text(
        json.dumps(state, sort_keys=True) + "\n"
    )
    (destination / "RC-PREFLIGHT.json").write_text(
        json.dumps(_rc_preflight_record(), indent=2, sort_keys=True) + "\n"
    )
    _bind_rc_stage_evidence(destination)
    if "LOCAL-GO-READ-1" in state["completed"]:
        (destination / "LOCAL-GO-READ-1-live.png").write_bytes(b"live")
        (destination / "LOCAL-GO-READ-1-outage.png").write_bytes(b"outage")
    if "LOCAL-WRITE-UI-1" in state["completed"]:
        (destination / "LOCAL-WRITE-UI-1-browser-result.json").write_text(
            '{"browser":"accepted"}\n'
        )
    for name in failed_artifacts:
        path = destination / name
        if path.suffix == ".png":
            path.write_bytes(b"bounded-failure")
        else:
            path.write_text('{"browser":"bounded-failure"}\n')
    _write_acceptance_checksums(destination)

    summary = orchestrate.finalize_rc_partial_failure_collection(
        destination,
        release_sha="a" * 40,
        frontend_sha="b" * 40,
        dependency_sha256="d" * 64,
        guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
        as_of_date="2026-11-02",
    )

    assert summary["failed"] == [failed_stage]


def test_rc_partial_rejects_outage_only_evidence_from_failed_go_read(tmp_path):
    destination = tmp_path / "go-outage-only"
    failed_stage = "LOCAL-GO-READ-1"
    state = _write_partial_failure_evidence(
        destination,
        completed_count=orchestrate.STAGE_ORDER.index(failed_stage),
    )
    state["harness_hashes"] = _authorized_rc_harness_hashes()
    (destination / "stage-state.json").write_text(
        json.dumps(state, sort_keys=True) + "\n"
    )
    (destination / "RC-PREFLIGHT.json").write_text(
        json.dumps(_rc_preflight_record(), indent=2, sort_keys=True) + "\n"
    )
    _bind_rc_stage_evidence(destination)
    (destination / "LOCAL-GO-READ-1-outage.png").write_bytes(b"unreachable")
    _write_acceptance_checksums(destination)

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="rc_partial_evidence_stage_sequence_invalid",
    ):
        orchestrate.finalize_rc_partial_failure_collection(
            destination,
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="d" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            as_of_date="2026-11-02",
        )


def test_rc_success_rejects_a_guest_harness_map_not_authorized_by_the_host(
    tmp_path, monkeypatch
):
    destination = tmp_path / "harness-drift"
    _write_complete_rc_evidence(destination)
    monkeypatch.setattr(
        orchestrate,
        "_host_harness_hashes",
        lambda: {name: "f" * 64 for name in orchestrate.EVIDENCE_HARNESS_ARTIFACTS},
        raising=False,
    )

    with pytest.raises(
        orchestrate.OrchestrationError,
        match="rc_evidence_identity_mismatch",
    ):
        orchestrate.finalize_rc_collection(
            destination,
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="d" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            as_of_date="2026-11-02",
        )


def test_collect_rc_partial_failure_revalidates_guest_around_atomic_collection(
    monkeypatch, tmp_path
):
    source = tmp_path / "source"
    _write_rc_partial_failure_evidence(source, "preflight")
    events = []
    monkeypatch.setattr(
        orchestrate,
        "_validated_rc_guest",
        lambda *_args: events.append("identity")
        or {"guest": "accepted", "machine_id": "f" * 32},
    )

    def collect(destination, *, finalizer, **kwargs):
        assert destination == tmp_path / "collected"
        assert kwargs["archive_name"] == "local-rc-partial-failure-evidence.tar.gz"
        events.append("collect")
        return finalizer(source)

    monkeypatch.setattr(orchestrate, "_collect_guest_evidence", collect)

    summary = orchestrate.collect_rc_partial_failure(
        tmp_path / "collected",
        "a" * 40,
        "b" * 40,
        "d" * 64,
        "01KZSKQ6FY4EVCCY94XGWZ9NDS",
        "2026-11-02",
    )

    assert summary["acceptance_evidence"] is False
    assert events == ["identity", "collect", "identity"]


@pytest.mark.parametrize(
    ("collector_name", "finalizer_name"),
    (
        ("collect_rc", "finalize_rc_collection"),
        ("collect_rc_partial_failure", "finalize_rc_partial_failure_collection"),
    ),
)
def test_rc_collection_threads_the_current_machine_into_durable_validation(
    monkeypatch, tmp_path, collector_name, finalizer_name
):
    machine_id = "f" * 32
    guest = {
        "name": "munbon-control-plan-local",
        "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
        "architecture": "arm64",
        "dependency_sha256": "d" * 64,
        "machine_id": machine_id,
    }
    captured = []
    archive_machine_ids = []
    monkeypatch.setattr(orchestrate, "_validated_rc_guest", lambda *_args: guest)

    def finalize(_destination, *, expected_machine_id, **_kwargs):
        captured.append(expected_machine_id)
        return {"verdict": "PASS"}

    def collect(_destination, *, finalizer, expected_machine_id, **_kwargs):
        archive_machine_ids.append(expected_machine_id)
        return finalizer(tmp_path / "source")

    monkeypatch.setattr(orchestrate, finalizer_name, finalize)
    monkeypatch.setattr(orchestrate, "_collect_guest_evidence", collect)

    result = getattr(orchestrate, collector_name)(
        tmp_path / "collected",
        "a" * 40,
        "b" * 40,
        "d" * 64,
        guest["id"],
        "2026-11-02",
    )

    assert result == {"verdict": "PASS"}
    assert captured == [machine_id]
    assert archive_machine_ids == [machine_id]


@pytest.mark.parametrize(
    ("stream_code", "archive_name"),
    (
        ("rc_evidence_stream", "local-rc-evidence.tar.gz"),
        (
            "rc_partial_evidence_stream",
            "local-rc-partial-failure-evidence.tar.gz",
        ),
    ),
)
def test_rc_archive_stream_checks_machine_id_in_the_same_guest_command(
    monkeypatch, tmp_path, stream_code, archive_name
):
    machine_id = "f" * 32
    captured = {}

    def guest_command(argv, *, user):
        captured["argv"] = argv
        captured["user"] = user
        return ["orb", "-m", "munbon-control-plan-local", "run", "--", *argv]

    def run(argv, **_kwargs):
        captured["command"] = argv
        return subprocess.CompletedProcess(argv, 1)

    monkeypatch.setattr(orchestrate.subprocess, "run", run)
    destination = tmp_path / "collected"

    with pytest.raises(
        orchestrate.OrchestrationError,
        match=f"{stream_code}_failed",
    ):
        orchestrate._collect_guest_evidence(
            destination,
            guest_command=guest_command,
            archive_name=archive_name,
            stream_code=stream_code,
            extract_code="unused_extract",
            destination_error="destination_exists",
            finalizer=lambda _temporary: pytest.fail("finalizer must not run"),
            expected_machine_id=machine_id,
        )

    assert captured == {
        "argv": [
            "sh",
            "-ceu",
            'test "$(cat /etc/machine-id)" = "$1"; shift; exec "$@"',
            "rc-archive-guard",
            machine_id,
            "tar",
            "-C",
            "/var/lib/munbon-local-acceptance/evidence",
            "-czf",
            "-",
            ".",
        ],
        "user": "root",
        "command": [
            "orb",
            "-m",
            "munbon-control-plan-local",
            "run",
            "--",
            "sh",
            "-ceu",
            'test "$(cat /etc/machine-id)" = "$1"; shift; exec "$@"',
            "rc-archive-guard",
            machine_id,
            "tar",
            "-C",
            "/var/lib/munbon-local-acceptance/evidence",
            "-czf",
            "-",
            ".",
        ],
    }
    assert machine_id not in captured["argv"][2]
    assert not destination.exists()


@pytest.mark.parametrize(
    ("collector_name", "evidence_kind"),
    (
        ("collect_rc", "complete"),
        ("collect_rc_partial_failure", "partial"),
    ),
)
def test_standalone_rc_collection_rejects_machine_drift_from_durable_lineage(
    monkeypatch, tmp_path, collector_name, evidence_kind
):
    source = tmp_path / "source"
    if evidence_kind == "complete":
        _write_complete_rc_evidence(source)
    else:
        _write_rc_partial_failure_evidence(source, "preflight")
    current_guest = {
        "name": "munbon-control-plan-local",
        "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
        "architecture": "arm64",
        "dependency_sha256": "d" * 64,
        "machine_id": "e" * 32,
    }
    monkeypatch.setattr(
        orchestrate, "_validated_rc_guest", lambda *_args: current_guest
    )
    monkeypatch.setattr(
        orchestrate,
        "_collect_guest_evidence",
        lambda _destination, *, finalizer, **_kwargs: finalizer(source),
    )

    with pytest.raises(
        orchestrate.OrchestrationError,
        match=(
            "rc_evidence_identity_mismatch"
            if evidence_kind == "complete"
            else "rc_partial_evidence_identity_mismatch"
        ),
    ):
        getattr(orchestrate, collector_name)(
            tmp_path / "collected",
            "a" * 40,
            "b" * 40,
            "d" * 64,
            current_guest["id"],
            "2026-11-02",
        )


def test_rc_partial_failure_cli_dispatches_instead_of_placeholder(
    monkeypatch, tmp_path, capsys
):
    summary = {
        "evidence_kind": "local_release_candidate_partial_failure",
        "acceptance_evidence": False,
        "verdict": "FAIL",
    }
    origin_shas = iter(("a" * 40, "b" * 40))
    monkeypatch.setattr(
        orchestrate, "_origin_main_sha", lambda *_args: next(origin_shas)
    )
    monkeypatch.setattr(
        orchestrate,
        "collect_rc_partial_failure",
        lambda *args: summary,
        raising=False,
    )

    assert (
        orchestrate.main(
            [
                "collect-rc-partial-failure",
                "--release-sha",
                "a" * 40,
                "--frontend-sha",
                "b" * 40,
                "--accept-later-origin-main",
                "--dependency-bundle-sha256",
                "d" * 64,
                "--guest-id",
                "01KZSKQ6FY4EVCCY94XGWZ9NDS",
                "--as-of-date",
                "2026-11-02",
                "--evidence-dir",
                str(tmp_path / "collected"),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == summary


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("identity", "rc_evidence_identity_mismatch"),
        ("tamper", "rc_evidence_checksum_mismatch"),
        ("campaign_outer", "rc_evidence_inventory_invalid"),
    ],
)
def test_finalize_rc_collection_rejects_identity_checksum_or_campaign_index_drift(
    tmp_path, mutation, error
):
    destination = tmp_path / mutation
    _write_complete_rc_evidence(destination)
    kwargs = {
        "release_sha": "a" * 40,
        "frontend_sha": "b" * 40,
        "dependency_sha256": "d" * 64,
        "guest_id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
        "as_of_date": "2026-11-02",
    }
    if mutation == "identity":
        kwargs["guest_id"] = "01KZSKQ6FY4EVCCY94XGWZ9NDT"
    elif mutation == "tamper":
        (destination / "LOCAL-RC-1.json").write_text("tampered\n")
    else:
        (destination / "OUTER-SHA256SUMS").write_text("campaign-shaped\n")

    with pytest.raises(orchestrate.OrchestrationError, match=error):
        orchestrate.finalize_rc_collection(destination, **kwargs)


def test_parser_exposes_rc_actions_and_exact_identity_arguments():
    for action in ("run-rc", "collect-rc", "collect-rc-partial-failure"):
        args = orchestrate._parse_args(
            [
                action,
                "--guest-id",
                "01KZSKQ6FY4EVCCY94XGWZ9NDS",
                "--dependency-bundle-sha256",
                "d" * 64,
                "--as-of-date",
                "2026-11-02",
            ]
        )
        assert (
            args.action,
            args.guest_id,
            args.dependency_bundle_sha256,
            args.as_of_date,
        ) == (
            action,
            "01KZSKQ6FY4EVCCY94XGWZ9NDS",
            "d" * 64,
            "2026-11-02",
        )


def test_campaign_ledger_rejects_rc_outer_index_as_historical_acceptance(tmp_path):
    entry = _campaign_ledger_entry(
        "rc-not-campaign",
        previous_entry_sha256=None,
        outcome={
            "acceptance": True,
            "passed": list(EXPECTED_SUCCESSFUL_STAGE_ORDER),
            "failed": [],
            "unreached": [],
        },
        authorization={"state": "successful_closed", "attempt": 1, "ceiling": 3},
        evidence_index_name="RC-OUTER-SHA256SUMS",
    )
    path = tmp_path / "campaign-ledger.jsonl"
    path.write_text(json.dumps(entry, sort_keys=True) + "\n")

    with pytest.raises(
        orchestrate.OrchestrationError, match="campaign_ledger_schema_invalid"
    ):
        orchestrate.validate_campaign_ledger(path)
