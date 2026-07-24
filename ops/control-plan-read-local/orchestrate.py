#!/usr/bin/env python3
"""Host-side orchestration for isolated local control-plan acceptance."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import tempfile

ACCEPTED_BASE_SHA = "8095bfe37550200da00ecb554edc646febf8aff9"
MACHINE_NAME = "munbon-control-plan-local"
STAGE_ORDER = (
    "LOCAL-BASE-0",
    "LOCAL-RTA-1",
    "LOCAL-AC-1",
    "LOCAL-READ-ACT-1",
    "LOCAL-EVIDENCE-1",
    "LOCAL-GO-READ-1",
)


class OrchestrationError(RuntimeError):
    """A local orchestration invariant failed with a safe error code."""


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


def classify_machine_inventory(inventory_json: str) -> str:
    try:
        inventory = json.loads(inventory_json)
        if not isinstance(inventory, list):
            raise ValueError
        matches = [item for item in inventory if item.get("name") == MACHINE_NAME]
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


def validate_machine_owner(marker_json: str) -> None:
    try:
        marker = json.loads(marker_json)
        if (
            not isinstance(marker, dict)
            or marker.get("machine") != MACHINE_NAME
            or marker.get("architecture") != "arm64"
            or not isinstance(marker.get("release_sha"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", marker["release_sha"])
        ):
            raise ValueError
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise OrchestrationError("machine_owner_not_accepted") from exc


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
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OrchestrationError(f"{code}_failed") from exc
    if result.returncode != 0:
        raise OrchestrationError(f"{code}_failed")
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


def provision(
    repo: Path,
    release_sha: str,
    frontend_repo: Path,
    frontend_sha: str,
) -> None:
    _validate_commit(repo, release_sha)
    _validate_commit(frontend_repo, frontend_sha)
    state = _machine_state()
    created_now = state == "missing"
    if state == "missing":
        _run_checked("orb_create", build_machine_command(MachineSpec()), timeout=600)
        if _machine_state() != "ready":
            raise OrchestrationError("machine_create_not_ready")
    if not created_now:
        owner = _run_checked(
            "machine_owner",
            build_guest_command(
                ["cat", "/var/lib/munbon-local-acceptance/owner.json"], user="root"
            ),
            timeout=30,
        )
        validate_machine_owner(owner)
    local_dir = Path(__file__).resolve().parent
    runtime_verifier = repo / "ops/control-plan-read-runtime/verify_bearer.py"
    sources = [
        local_dir / "bootstrap-linux.sh",
        local_dir / "run-stage-suite.py",
        local_dir / "local-ac1.py",
        local_dir / "seed-approved-sources.py",
        local_dir / "run-ros-manual-producer.sh",
        local_dir / "run-read-browser.js",
        local_dir / "run-evidence-browser.js",
        local_dir / "run-go-read-browser.js",
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
        for source in (bundle, frontend_bundle, *sources):
            _push_isolated_file(source, f"/opt/munbon/input/{source.name}")
    _run_checked(
        "bootstrap_linux",
        build_guest_command(
            [
                "bash",
                "/opt/munbon/input/bootstrap-linux.sh",
                "/opt/munbon/input/source.bundle",
                release_sha,
                "/opt/munbon/input/frontend.bundle",
                frontend_sha,
            ],
            user="root",
        ),
        timeout=3600,
    )


def run_stage(stage: str, release_sha: str, frontend_sha: str) -> None:
    if stage not in STAGE_ORDER:
        raise OrchestrationError("stage_not_supported")
    if _machine_state() != "ready":
        raise OrchestrationError("machine_not_ready")
    _run_checked(
        stage.lower().replace("-", "_"),
        build_guest_command(
            [
                "python3",
                "/opt/munbon/harness/run-stage-suite.py",
                stage,
                "--release-sha",
                release_sha,
                "--frontend-sha",
                frontend_sha,
            ],
            workdir="/opt/munbon/repo",
        ),
        timeout=2400,
    )


def run_all_stages(release_sha: str, frontend_sha: str) -> None:
    for stage in STAGE_ORDER:
        run_stage(stage, release_sha, frontend_sha)


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


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("plan", "provision", "run-stage", "run-all", "collect")
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
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
        elif args.action == "provision":
            provision(
                args.repo,
                release_sha,
                args.frontend_repo,
                args.frontend_sha,
            )
        elif args.action == "run-stage":
            if args.stage is None:
                raise OrchestrationError("stage_required")
            run_stage(args.stage, release_sha, args.frontend_sha)
        elif args.action == "run-all":
            run_all_stages(release_sha, args.frontend_sha)
        else:
            if args.evidence_dir is None:
                raise OrchestrationError("evidence_dir_required")
            collect_evidence(args.evidence_dir)
    except OrchestrationError as exc:
        print(f"FAIL orchestration: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
