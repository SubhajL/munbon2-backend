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
    (bundle_root / "artifact").write_bytes(b"content")
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


def test_main_rejects_malformed_as_of_date(monkeypatch, capsys):
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
            "2026-13-99",
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
