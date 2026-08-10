#!/usr/bin/env python3
"""Host-side orchestration for isolated local control-plan acceptance."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provisioning_contract import (  # noqa: E402
    ProvisioningContractError,
    dependency_input_digests,
    validate_dependency_bundle,
)

ACCEPTED_BASE_SHA = "8095bfe37550200da00ecb554edc646febf8aff9"
MACHINE_NAME = "munbon-control-plan-local"
DIAGNOSTIC_MACHINE_NAME = "munbon-control-plan-write-ui-diagnostic"
STAGE_ORDER = (
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


class OrchestrationError(RuntimeError):
    """A local orchestration invariant failed with a safe error code."""


class CommandExecutionError(OrchestrationError):
    """A child command failed without exposing its captured output."""

    def __init__(self, code: str, returncode: int):
        super().__init__(f"{code}_failed")
        self.code = code
        self.returncode = returncode


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class MachineSpec:
    name: str = MACHINE_NAME
    user: str = "munbonlocal"
    architecture: str = "arm64"
    memory: str = "8G"
    cpus: str = "4"
    disk: str = "40G"
    distribution: str = "debian:12"


def build_machine_command(spec: MachineSpec) -> list[str]:
    if spec != MachineSpec():
        raise OrchestrationError("machine_spec_not_accepted")
    return [
        "orb",
        "create",
        "--arch",
        spec.architecture,
        "--memory",
        spec.memory,
        "--cpus",
        spec.cpus,
        "--disk",
        spec.disk,
        "--user",
        spec.user,
        "--isolated",
        "--isolate-network",
        spec.distribution,
        spec.name,
    ]


def validate_release_sha(
    requested_sha: str,
    *,
    accepted_base_sha: str = ACCEPTED_BASE_SHA,
    origin_main_sha: str | None = None,
    accept_later_origin_main: bool = False,
) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", requested_sha):
        raise OrchestrationError("release_sha_not_accepted")
    if requested_sha == accepted_base_sha:
        return requested_sha
    if (
        accept_later_origin_main
        and origin_main_sha is not None
        and requested_sha == origin_main_sha
    ):
        return requested_sha
    raise OrchestrationError("release_sha_not_accepted")


def build_guest_command(
    argv: list[str], *, user: str = "munbon", workdir: str | None = None
) -> list[str]:
    if not argv or user not in {"root", "munbon"}:
        raise OrchestrationError("guest_command_invalid")
    command = ["orb", "-m", MACHINE_NAME, "-u", user]
    if workdir is not None:
        command.extend(["--workdir", workdir])
    return [*command, *argv]


def build_diagnostic_command(argv: list[str], *, user: str = "root") -> list[str]:
    if not argv or user not in {"root", "munbon"}:
        raise OrchestrationError("diagnostic_command_invalid")
    return [
        "orb",
        "-m",
        DIAGNOSTIC_MACHINE_NAME,
        "-u",
        user,
        *argv,
    ]


def _classify_machine_inventory(inventory_json: str, machine_name: str) -> str:
    try:
        inventory = json.loads(inventory_json)
        if not isinstance(inventory, list):
            raise ValueError
        matches = [item for item in inventory if item.get("name") == machine_name]
        if not matches:
            return "missing"
        if len(matches) != 1:
            raise ValueError
        machine = matches[0]
        image = machine.get("image")
        config = machine.get("config")
        if (
            not isinstance(image, dict)
            or not isinstance(config, dict)
            or image.get("distro") != "debian"
            or image.get("version") not in {"bookworm", "12"}
            or image.get("arch") != "arm64"
            or config.get("isolated") is not True
            or config.get("isolate_network") is not True
            or config.get("default_username") != "munbonlocal"
            or config.get("memory_limit_mib") != 8192
            or config.get("cpu_limit") != 4
            or config.get("disk_limit_bytes") != 40 * 1024**3
            or machine.get("state") != "running"
        ):
            raise ValueError
        return "ready"
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise OrchestrationError("machine_shape_not_accepted") from exc


def classify_machine_inventory(inventory_json: str) -> str:
    return _classify_machine_inventory(inventory_json, MACHINE_NAME)


def classify_diagnostic_machine_inventory(inventory_json: str) -> str:
    return _classify_machine_inventory(inventory_json, DIAGNOSTIC_MACHINE_NAME)


def validate_diagnostic_owner(marker_json: str) -> None:
    expected = {
        "architecture": "arm64",
        "canonical": False,
        "machine": DIAGNOSTIC_MACHINE_NAME,
        "purpose": "dependency-build",
    }
    try:
        marker = json.loads(marker_json)
    except json.JSONDecodeError as exc:
        raise OrchestrationError("diagnostic_owner_not_accepted") from exc
    if marker != expected:
        raise OrchestrationError("diagnostic_owner_not_accepted")


def validate_machine_owner(marker_json: str) -> None:
    try:
        marker = json.loads(marker_json)
        if (
            not isinstance(marker, dict)
            or marker.get("machine") != MACHINE_NAME
            or marker.get("architecture") != "arm64"
            or marker.get("state") != "ready"
            or not isinstance(marker.get("release_sha"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", marker["release_sha"])
            or not re.fullmatch(r"[0-9a-f]{40}", marker.get("frontend_sha", ""))
            or not re.fullmatch(r"[0-9a-f]{64}", marker.get("dependency_sha256", ""))
        ):
            raise ValueError
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise OrchestrationError("machine_owner_not_accepted") from exc


def validate_existing_guest(provision_state_json: str, owner_json: str) -> None:
    if not provision_state_json:
        raise OrchestrationError("machine_provision_state_missing")
    try:
        state = json.loads(provision_state_json)
        if (
            not isinstance(state, dict)
            or state.get("state")
            not in {
                "created",
                "dependency-staged",
                "runtime-reset",
                "ready",
                "failed",
                "interrupted",
            }
            or not re.fullmatch(r"[0-9a-f]{40}", state.get("release_sha", ""))
            or not re.fullmatch(r"[0-9a-f]{40}", state.get("frontend_sha", ""))
            or not re.fullmatch(r"[0-9a-f]{64}", state.get("dependency_sha256", ""))
            or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", state.get("phase", ""))
            or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", state.get("substep", ""))
            or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", state.get("recorded_at", "")
            )
        ):
            raise ValueError
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise OrchestrationError("machine_provision_state_invalid") from exc
    if state["state"] in {"failed", "interrupted"}:
        raise OrchestrationError("machine_failed_evidence_only")
    if state["state"] != "ready":
        raise OrchestrationError("machine_provision_incomplete")
    validate_machine_owner(owner_json)
    owner = json.loads(owner_json)
    if (
        owner["release_sha"] != state["release_sha"]
        or owner["frontend_sha"] != state["frontend_sha"]
        or owner["dependency_sha256"] != state["dependency_sha256"]
    ):
        raise OrchestrationError("machine_owner_state_mismatch")


def validate_stage_guest(
    provision_state_json: str,
    owner_json: str,
    release_sha: str,
    frontend_sha: str,
) -> None:
    validate_existing_guest(provision_state_json, owner_json)
    state = json.loads(provision_state_json)
    if state["release_sha"] != release_sha or state["frontend_sha"] != frontend_sha:
        raise OrchestrationError("machine_stage_sha_mismatch")


def finalize_bootstrap_failure_bundle(destination: Path) -> dict:
    bundle = destination / "bundle"
    checksum_path = bundle / "SHA256SUMS"
    try:
        checksum_lines = checksum_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise OrchestrationError("bootstrap_failure_inner_index_missing") from exc
    expected_names = {"bootstrap-sanitized.log", "metadata.json"}
    if len(checksum_lines) != len(expected_names):
        raise OrchestrationError("bootstrap_failure_inner_index_invalid")
    indexed_names = set()
    for line in checksum_lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([a-z0-9.-]+)", line)
        if match is None or match.group(2) not in expected_names:
            raise OrchestrationError("bootstrap_failure_inner_index_invalid")
        digest, name = match.groups()
        indexed_names.add(name)
        artifact = bundle / name
        if (
            not artifact.is_file()
            or artifact.is_symlink()
            or _sha256_file(artifact) != digest
        ):
            raise OrchestrationError("bootstrap_failure_inner_checksum_mismatch")
    if indexed_names != expected_names:
        raise OrchestrationError("bootstrap_failure_inner_inventory_invalid")
    try:
        metadata = json.loads((bundle / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OrchestrationError("bootstrap_failure_metadata_invalid") from exc
    if (
        not isinstance(metadata, dict)
        or set(metadata)
        != {
            "classification",
            "dependency_sha256",
            "exit_code",
            "frontend_sha",
            "phase",
            "recorded_at",
            "release_sha",
            "state",
            "substep",
            "tool_versions",
        }
        or metadata["classification"]
        not in {
            "retryable-transport",
            "nonretryable-integrity",
            "nonretryable-bootstrap",
            "interrupted",
        }
        or metadata["state"] not in {"failed", "interrupted"}
        or not isinstance(metadata["exit_code"], int)
        or not 0 < metadata["exit_code"] <= 255
        or not re.fullmatch(r"[0-9a-f]{40}", metadata["release_sha"])
        or not re.fullmatch(r"[0-9a-f]{40}", metadata["frontend_sha"])
        or not re.fullmatch(r"[0-9a-f]{64}", metadata["dependency_sha256"])
        or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", metadata["phase"])
        or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", metadata["substep"])
        or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", metadata["recorded_at"]
        )
        or not isinstance(metadata["tool_versions"], dict)
    ):
        raise OrchestrationError("bootstrap_failure_metadata_not_accepted")
    actual_names = {path.name for path in bundle.iterdir() if path.is_file()}
    if actual_names != {*expected_names, "SHA256SUMS"}:
        raise OrchestrationError("bootstrap_failure_inner_inventory_invalid")
    outer_path = destination / "OUTER-SHA256SUMS"
    outer_path.write_text(
        "".join(
            f"{_sha256_file(path)}  bundle/{path.name}\n"
            for path in sorted(bundle.iterdir())
        ),
        encoding="utf-8",
    )
    outer_path.chmod(0o600)
    return metadata


def validate_failure_state_matches_metadata(state: dict, metadata: dict) -> None:
    bound_fields = {
        "dependency_sha256",
        "frontend_sha",
        "phase",
        "release_sha",
        "state",
        "substep",
    }
    if any(state.get(field) != metadata.get(field) for field in bound_fields):
        raise OrchestrationError("bootstrap_failure_state_metadata_mismatch")


def validate_dependency_archive(
    archive: Path,
    archive_sha256: str,
    *,
    repo: Path,
    release_sha: str,
    frontend_repo: Path,
    frontend_sha: str,
) -> None:
    if (
        not archive.is_file()
        or not re.fullmatch(r"[0-9a-f]{64}", archive_sha256)
        or _sha256_file(archive) != archive_sha256
    ):
        raise OrchestrationError("dependency_archive_checksum_mismatch")
    with tempfile.TemporaryDirectory(prefix="munbon-dependency-verify-") as temporary:
        extracted = Path(temporary)
        try:
            with tarfile.open(archive, "r:gz") as bundle:
                members = bundle.getmembers()
                if not members or any(
                    member.name == "bundle"
                    and not member.isdir()
                    or member.name != "bundle"
                    and not member.name.startswith("bundle/")
                    or member.issym()
                    or member.islnk()
                    or not (member.isdir() or member.isfile())
                    for member in members
                ):
                    raise OrchestrationError("dependency_archive_inventory_invalid")
                bundle.extractall(extracted, filter="data")
            validate_dependency_bundle(
                extracted / "bundle",
                release_sha=release_sha,
                frontend_sha=frontend_sha,
                expected_inputs=dependency_input_digests(repo, frontend_repo),
            )
        except (OSError, tarfile.TarError, ProvisioningContractError) as exc:
            if isinstance(exc, OrchestrationError):
                raise
            raise OrchestrationError("dependency_archive_not_accepted") from exc


def build_isolated_write_command(destination: str) -> list[str]:
    if not destination.startswith("/opt/munbon/input/") or destination.endswith("/"):
        raise OrchestrationError("isolated_destination_invalid")
    return [
        "orb",
        "-m",
        MACHINE_NAME,
        "-u",
        "root",
        "tee",
        destination,
    ]


def _run_checked(
    code: str,
    argv: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 1800,
) -> str:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise CommandExecutionError(code, 124) from exc
    except OSError as exc:
        raise OrchestrationError(f"{code}_failed") from exc
    if result.returncode != 0:
        raise CommandExecutionError(code, result.returncode)
    print(f"PASS {code}")
    return result.stdout


def _origin_main_sha(repo: Path) -> str:
    return _run_checked(
        "origin_main_sha", ["git", "rev-parse", "origin/main"], cwd=repo, timeout=30
    ).strip()


def _validate_commit(repo: Path, release_sha: str) -> None:
    actual = _run_checked(
        "release_commit",
        ["git", "cat-file", "-t", release_sha],
        cwd=repo,
        timeout=30,
    ).strip()
    if actual != "commit":
        raise OrchestrationError("release_commit_invalid")


def _machine_state() -> str:
    inventory = _run_checked(
        "orb_inventory", ["orb", "list", "--format", "json"], timeout=30
    )
    return classify_machine_inventory(inventory)


def _prepare_diagnostic_machine(*, confirmed: bool) -> None:
    if not confirmed:
        raise OrchestrationError("diagnostic_build_not_authorized")
    inventory = _run_checked(
        "diagnostic_orb_inventory", ["orb", "list", "--format", "json"], timeout=30
    )
    if classify_diagnostic_machine_inventory(inventory) != "ready":
        raise OrchestrationError("diagnostic_machine_missing")
    marker_path = "/var/lib/munbon-local-acceptance/diagnostic-owner.json"
    marker = _run_checked(
        "diagnostic_owner",
        build_diagnostic_command(
            ["sh", "-c", f"test ! -f {marker_path} || cat {marker_path}"]
        ),
        timeout=30,
    )
    if not marker:
        marker_body = json.dumps(
            {
                "architecture": "arm64",
                "canonical": False,
                "machine": DIAGNOSTIC_MACHINE_NAME,
                "purpose": "dependency-build",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        _run_checked(
            "diagnostic_owner_create",
            build_diagnostic_command(
                [
                    "sh",
                    "-c",
                    f"install -d -m 0700 /var/lib/munbon-local-acceptance && printf '%s\\n' '{marker_body}' > {marker_path}.tmp && chmod 600 {marker_path}.tmp && mv {marker_path}.tmp {marker_path}",
                ]
            ),
            timeout=30,
        )
        marker = _run_checked(
            "diagnostic_owner_verify",
            build_diagnostic_command(["cat", marker_path]),
            timeout=30,
        )
    validate_diagnostic_owner(marker)


def _create_bundle(repo: Path, release_sha: str, target: Path) -> None:
    origin_main = _origin_main_sha(repo)
    local_main = _run_checked(
        "local_main_sha", ["git", "rev-parse", "main"], cwd=repo, timeout=30
    ).strip()
    if origin_main != release_sha or local_main != release_sha:
        raise OrchestrationError("bundle_source_not_origin_main")
    _run_checked(
        "source_bundle",
        ["git", "bundle", "create", str(target), "main"],
        cwd=repo,
        timeout=120,
    )
    _run_checked(
        "source_bundle_verify",
        ["git", "bundle", "verify", str(target)],
        cwd=repo,
        timeout=30,
    )


def _push_isolated_file(source: Path, destination: str) -> None:
    try:
        with source.open("rb") as stream:
            result = subprocess.run(
                build_isolated_write_command(destination),
                stdin=stream,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                timeout=600,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OrchestrationError("guest_input_push_failed") from exc
    if result.returncode != 0:
        raise OrchestrationError("guest_input_push_failed")
    print(f"PASS guest_input_{source.name}")


def _push_diagnostic_file(source: Path, destination: str) -> None:
    if not destination.startswith("/opt/munbon/dependency-build/"):
        raise OrchestrationError("diagnostic_destination_invalid")
    try:
        with source.open("rb") as stream:
            result = subprocess.run(
                build_diagnostic_command(["tee", destination]),
                stdin=stream,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                timeout=600,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OrchestrationError("diagnostic_input_push_failed") from exc
    if result.returncode != 0:
        raise OrchestrationError("diagnostic_input_push_failed")
    print(f"PASS diagnostic_input_{source.name}")


def build_dependency_bundle(
    repo: Path,
    release_sha: str,
    frontend_repo: Path,
    frontend_sha: str,
    destination: Path,
    *,
    confirm_diagnostic_build: bool = False,
) -> str:
    _validate_commit(repo, release_sha)
    _validate_commit(frontend_repo, frontend_sha)
    if destination.exists():
        raise OrchestrationError("dependency_bundle_destination_exists")
    _prepare_diagnostic_machine(confirmed=confirm_diagnostic_build)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    local_dir = Path(__file__).resolve().parent
    remote_root = (
        f"/opt/munbon/dependency-build/{release_sha[:12]}-"
        f"{frontend_sha[:12]}-{os.getpid()}"
    )
    with tempfile.TemporaryDirectory(prefix="munbon-dependency-source-") as temporary:
        bundle = Path(temporary) / "source.bundle"
        frontend_bundle = Path(temporary) / "frontend.bundle"
        _create_bundle(repo, release_sha, bundle)
        _create_bundle(frontend_repo, frontend_sha, frontend_bundle)
        sources = (
            bundle,
            frontend_bundle,
            local_dir / "build-dependency-bundle-linux.sh",
            local_dir / "provisioning_contract.py",
            local_dir / "validate-dependency-bundle-linux.sh",
        )
        _run_checked(
            "diagnostic_build_directory",
            build_diagnostic_command(["install", "-d", "-m", "0700", remote_root]),
            timeout=30,
        )
        for source in sources:
            _push_diagnostic_file(source, f"{remote_root}/{source.name}")
    remote_archive = f"{remote_root}/dependencies.tar.gz"
    _run_checked(
        "diagnostic_dependency_build",
        build_diagnostic_command(
            [
                "bash",
                f"{remote_root}/build-dependency-bundle-linux.sh",
                f"{remote_root}/source.bundle",
                release_sha,
                f"{remote_root}/frontend.bundle",
                frontend_sha,
                f"{remote_root}/provisioning_contract.py",
                f"{remote_root}/validate-dependency-bundle-linux.sh",
                remote_archive,
            ]
        ),
        timeout=7200,
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".dependencies-", suffix=".tar.gz", dir=destination.parent
    )
    temporary_archive = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            result = subprocess.run(
                build_diagnostic_command(["cat", remote_archive]),
                stdout=stream,
                stderr=subprocess.PIPE,
                check=False,
                timeout=1800,
            )
        if result.returncode != 0:
            raise OrchestrationError("diagnostic_dependency_stream_failed")
        archive_sha256 = _sha256_file(temporary_archive)
        validate_dependency_archive(
            temporary_archive,
            archive_sha256,
            repo=repo,
            release_sha=release_sha,
            frontend_repo=frontend_repo,
            frontend_sha=frontend_sha,
        )
        temporary_archive.chmod(0o600)
        temporary_archive.replace(destination)
    finally:
        temporary_archive.unlink(missing_ok=True)
    _run_checked(
        "diagnostic_build_cleanup",
        build_diagnostic_command(["rm", "-rf", "--", remote_root]),
        timeout=120,
    )
    print(f"PASS dependency_bundle {archive_sha256}")
    return archive_sha256


def provision(
    repo: Path,
    release_sha: str,
    frontend_repo: Path,
    frontend_sha: str,
    dependency_archive: Path,
    dependency_archive_sha256: str,
    failure_directory: Path,
) -> None:
    _validate_commit(repo, release_sha)
    _validate_commit(frontend_repo, frontend_sha)
    validate_dependency_archive(
        dependency_archive,
        dependency_archive_sha256,
        repo=repo,
        release_sha=release_sha,
        frontend_repo=frontend_repo,
        frontend_sha=frontend_sha,
    )
    state = _machine_state()
    created_now = state == "missing"
    if state == "missing":
        _run_checked("orb_create", build_machine_command(MachineSpec()), timeout=600)
        if _machine_state() != "ready":
            raise OrchestrationError("machine_create_not_ready")
    if not created_now:
        provision_state = _run_checked(
            "machine_provision_state",
            build_guest_command(
                [
                    "sh",
                    "-c",
                    "test ! -f /var/lib/munbon-local-acceptance/provisioning/state.json || cat /var/lib/munbon-local-acceptance/provisioning/state.json",
                ],
                user="root",
            ),
            timeout=30,
        )
        owner = _run_checked(
            "machine_owner",
            build_guest_command(
                [
                    "sh",
                    "-c",
                    "test ! -f /var/lib/munbon-local-acceptance/owner.json || cat /var/lib/munbon-local-acceptance/owner.json",
                ],
                user="root",
            ),
            timeout=30,
        )
        validate_existing_guest(provision_state, owner)
        raise OrchestrationError("machine_reprovision_not_authorized")
    local_dir = Path(__file__).resolve().parent
    runtime_verifier = repo / "ops/control-plan-read-runtime/verify_bearer.py"
    sources = [
        local_dir / "bootstrap-linux.sh",
        local_dir / "bootstrap-provisioning-state.sh",
        local_dir / "provisioning_contract.py",
        local_dir / "validate-dependency-bundle-linux.sh",
        local_dir / "run-stage-suite.py",
        local_dir / "local-ac1.py",
        local_dir / "seed-approved-sources.py",
        local_dir / "run-ros-manual-producer.sh",
        local_dir / "run-read-browser.js",
        local_dir / "run-evidence-browser.js",
        local_dir / "run-go-read-browser.js",
        local_dir / "run-write-browser.js",
        local_dir / "seed-local-operators.js",
        local_dir / "systemd/munbon-local-auth.service",
        runtime_verifier,
    ]
    if any(not path.is_file() for path in sources):
        raise OrchestrationError("harness_artifact_missing")
    with tempfile.TemporaryDirectory(prefix="munbon-local-acceptance-") as temporary:
        bundle = Path(temporary) / "source.bundle"
        frontend_bundle = Path(temporary) / "frontend.bundle"
        _create_bundle(repo, release_sha, bundle)
        _create_bundle(frontend_repo, frontend_sha, frontend_bundle)
        _run_checked(
            "guest_input_directory",
            build_guest_command(
                ["install", "-d", "-m", "0700", "/opt/munbon/input"],
                user="root",
            ),
            timeout=30,
        )
        for source in (bundle, frontend_bundle, dependency_archive, *sources):
            _push_isolated_file(source, f"/opt/munbon/input/{source.name}")
    try:
        _run_checked(
            "bootstrap_linux",
            build_guest_command(
                [
                    "timeout",
                    "--signal=TERM",
                    "--kill-after=10s",
                    "3500s",
                    "bash",
                    "/opt/munbon/input/bootstrap-linux.sh",
                    "/opt/munbon/input/source.bundle",
                    release_sha,
                    "/opt/munbon/input/frontend.bundle",
                    frontend_sha,
                    f"/opt/munbon/input/{dependency_archive.name}",
                    dependency_archive_sha256,
                ],
                user="root",
            ),
            timeout=3600,
        )
    except CommandExecutionError as exc:
        try:
            metadata = collect_bootstrap_failure(failure_directory)
        except OrchestrationError as collection_exc:
            raise OrchestrationError(
                "bootstrap_linux_failed_and_failure_collection_failed"
            ) from collection_exc
        classification = metadata["classification"].replace("-", "_")
        raise OrchestrationError(f"bootstrap_linux_failed_{classification}") from exc


def run_stage(
    stage: str,
    release_sha: str,
    frontend_sha: str,
    as_of_date: str | None = None,
) -> None:
    if stage not in STAGE_ORDER:
        raise OrchestrationError("stage_not_supported")
    if _machine_state() != "ready":
        raise OrchestrationError("machine_not_ready")
    provision_state = _run_checked(
        "stage_provision_state",
        build_guest_command(
            ["cat", "/var/lib/munbon-local-acceptance/provisioning/state.json"],
            user="root",
        ),
        timeout=30,
    )
    owner = _run_checked(
        "stage_machine_owner",
        build_guest_command(
            ["cat", "/var/lib/munbon-local-acceptance/owner.json"], user="root"
        ),
        timeout=30,
    )
    validate_stage_guest(provision_state, owner, release_sha, frontend_sha)
    stage_argv = [
        "python3",
        "/opt/munbon/harness/run-stage-suite.py",
        stage,
        "--release-sha",
        release_sha,
        "--frontend-sha",
        frontend_sha,
    ]
    if as_of_date is not None:
        stage_argv.extend(["--as-of-date", as_of_date])
    _run_checked(
        stage.lower().replace("-", "_"),
        build_guest_command(stage_argv, workdir="/opt/munbon/repo"),
        timeout=2400,
    )


def run_all_stages(
    release_sha: str, frontend_sha: str, as_of_date: str | None = None
) -> None:
    for stage in STAGE_ORDER:
        run_stage(stage, release_sha, frontend_sha, as_of_date=as_of_date)


def collect_evidence(destination: Path) -> None:
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    archive_name = "local-acceptance-evidence.tar.gz"
    archive = destination / archive_name
    try:
        with archive.open("wb") as stream:
            result = subprocess.run(
                build_guest_command(
                    [
                        "tar",
                        "-C",
                        "/var/lib/munbon-local-acceptance/evidence",
                        "-czf",
                        "-",
                        ".",
                    ],
                    user="root",
                ),
                stdout=stream,
                stderr=subprocess.PIPE,
                check=False,
                timeout=120,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OrchestrationError("evidence_stream_failed") from exc
    if result.returncode != 0:
        raise OrchestrationError("evidence_stream_failed")
    print("PASS evidence_stream")
    _run_checked(
        "evidence_extract",
        ["tar", "-xzf", str(archive), "-C", str(destination)],
        timeout=120,
    )
    archive.unlink()


def collect_bootstrap_failure(destination: Path) -> dict:
    if destination.exists():
        raise OrchestrationError("bootstrap_failure_destination_exists")
    state_json = _run_checked(
        "bootstrap_failure_state",
        build_guest_command(
            ["cat", "/var/lib/munbon-local-acceptance/provisioning/state.json"],
            user="root",
        ),
        timeout=30,
    )
    try:
        state = json.loads(state_json)
    except json.JSONDecodeError as exc:
        raise OrchestrationError("bootstrap_failure_state_invalid") from exc
    if state.get("state") not in {"failed", "interrupted"}:
        raise OrchestrationError("bootstrap_failure_state_not_terminal")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".bootstrap-failure-", dir=destination.parent)
    )
    try:
        bundle_directory = temporary / "bundle"
        bundle_directory.mkdir(mode=0o700)
        archive = temporary / "failure.tar.gz"
        try:
            with archive.open("wb") as stream:
                result = subprocess.run(
                    build_guest_command(
                        [
                            "tar",
                            "-C",
                            "/var/lib/munbon-local-acceptance/provisioning/failure",
                            "-czf",
                            "-",
                            ".",
                        ],
                        user="root",
                    ),
                    stdout=stream,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=120,
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OrchestrationError("bootstrap_failure_stream_failed") from exc
        if result.returncode != 0:
            raise OrchestrationError("bootstrap_failure_stream_failed")
        try:
            with tarfile.open(archive, "r:gz") as failure_archive:
                members = failure_archive.getmembers()
                if any(
                    member.issym()
                    or member.islnk()
                    or not (member.isdir() or member.isfile())
                    for member in members
                ):
                    raise OrchestrationError("bootstrap_failure_archive_invalid")
                failure_archive.extractall(bundle_directory, filter="data")
        except (OSError, tarfile.TarError) as exc:
            raise OrchestrationError("bootstrap_failure_archive_invalid") from exc
        archive.unlink()
        metadata = finalize_bootstrap_failure_bundle(temporary)
        validate_failure_state_matches_metadata(state, metadata)
        temporary.rename(destination)
        print("PASS bootstrap_failure_bundle")
        return metadata
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "plan",
            "build-dependencies",
            "provision",
            "run-stage",
            "run-all",
            "collect",
            "collect-bootstrap-failure",
        ),
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--frontend-repo",
        type=Path,
        default=Path.cwd().parent / "smart-cms-app",
    )
    parser.add_argument("--release-sha", default=ACCEPTED_BASE_SHA)
    parser.add_argument(
        "--frontend-sha", default="fbd4ce4df0bb0476b7cd402ac1a4e180a91a7792"
    )
    parser.add_argument("--stage", choices=STAGE_ORDER)
    parser.add_argument("--accept-later-origin-main", action="store_true")
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--dependency-bundle", type=Path)
    parser.add_argument("--dependency-bundle-sha256")
    parser.add_argument("--bootstrap-failure-dir", type=Path)
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--confirm-diagnostic-build", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.action == "collect-bootstrap-failure":
            if args.bootstrap_failure_dir is None:
                raise OrchestrationError("bootstrap_failure_dir_required")
            collect_bootstrap_failure(args.bootstrap_failure_dir)
            return 0
        origin_main = _origin_main_sha(args.repo)
        frontend_origin_main = _origin_main_sha(args.frontend_repo)
        release_sha = validate_release_sha(
            args.release_sha,
            origin_main_sha=origin_main,
            accept_later_origin_main=args.accept_later_origin_main,
        )
        if (
            not re.fullmatch(r"[0-9a-f]{40}", args.frontend_sha)
            or args.frontend_sha != frontend_origin_main
        ):
            raise OrchestrationError("frontend_sha_not_accepted")
        if args.as_of_date is not None:
            try:
                date.fromisoformat(args.as_of_date)
            except ValueError as exc:
                raise OrchestrationError("as_of_date_not_accepted") from exc
        if args.action == "plan":
            print(
                json.dumps(
                    {
                        "machine": MACHINE_NAME,
                        "architecture": "arm64",
                        "isolation": True,
                        "network_isolation": True,
                        "release_sha": release_sha,
                        "frontend_sha": args.frontend_sha,
                        "aws_actions": False,
                    },
                    sort_keys=True,
                )
            )
        elif args.action == "build-dependencies":
            if args.dependency_bundle is None:
                raise OrchestrationError("dependency_bundle_destination_required")
            build_dependency_bundle(
                args.repo,
                release_sha,
                args.frontend_repo,
                args.frontend_sha,
                args.dependency_bundle,
                confirm_diagnostic_build=args.confirm_diagnostic_build,
            )
        elif args.action == "provision":
            if (
                args.dependency_bundle is None
                or args.dependency_bundle_sha256 is None
                or args.bootstrap_failure_dir is None
            ):
                raise OrchestrationError("provision_dependency_arguments_required")
            provision(
                args.repo,
                release_sha,
                args.frontend_repo,
                args.frontend_sha,
                args.dependency_bundle,
                args.dependency_bundle_sha256,
                args.bootstrap_failure_dir,
            )
        elif args.action == "run-stage":
            if args.stage is None:
                raise OrchestrationError("stage_required")
            run_stage(
                args.stage, release_sha, args.frontend_sha, as_of_date=args.as_of_date
            )
        elif args.action == "run-all":
            run_all_stages(release_sha, args.frontend_sha, as_of_date=args.as_of_date)
        elif args.action == "collect":
            if args.evidence_dir is None:
                raise OrchestrationError("evidence_dir_required")
            collect_evidence(args.evidence_dir)
        else:
            raise OrchestrationError("action_not_accepted")
    except OrchestrationError as exc:
        print(f"FAIL orchestration: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
