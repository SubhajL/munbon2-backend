import importlib.util
import json
from pathlib import Path
import sys

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "orchestrate.py"
SPEC = importlib.util.spec_from_file_location(
    "control_plan_local_orchestrate", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
orchestrate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = orchestrate
SPEC.loader.exec_module(orchestrate)


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
                "release_sha": orchestrate.ACCEPTED_BASE_SHA,
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
