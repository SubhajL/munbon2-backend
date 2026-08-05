import importlib.util
import json
from pathlib import Path
import re
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
        lambda stage, release_sha, frontend_sha: calls.append(
            (stage, release_sha, frontend_sha)
        ),
    )

    orchestrate.run_all_stages("a" * 40, "b" * 40)

    assert calls == [(stage, "a" * 40, "b" * 40) for stage in orchestrate.STAGE_ORDER]


def test_orchestrator_stage_order_matches_suite_stage_order():
    suite_path = Path(__file__).resolve().parents[1] / "run-stage-suite.py"
    suite_source = suite_path.read_text(encoding="utf-8")
    match = re.search(
        r'^STAGE_ORDER\s*=\s*\((.*?)\)',
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
        lambda repo, release_sha, frontend, accepted_frontend_sha: calls.append(
            ("provision", repo, release_sha, frontend, accepted_frontend_sha)
        ),
    )
    monkeypatch.setattr(
        orchestrate,
        "run_stage",
        lambda stage, release_sha, accepted_frontend_sha: calls.append(
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
        ["provision"],
        *(["run-stage", "--stage", stage] for stage in orchestrate.STAGE_ORDER),
        ["collect", "--evidence-dir", str(evidence_dir)],
    )

    assert [orchestrate.main([*command, *common]) for command in commands] == [0] * len(
        commands
    )
    assert calls == [
        ("provision", backend_repo, backend_sha, frontend_repo, frontend_sha),
        *((stage, backend_sha, frontend_sha) for stage in orchestrate.STAGE_ORDER),
        ("collect", evidence_dir),
    ]
