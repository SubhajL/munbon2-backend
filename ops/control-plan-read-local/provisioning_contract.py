#!/usr/bin/env python3
"""Provisioning state, dependency, and failure-evidence contracts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import tarfile
import tempfile


class ProvisioningContractError(RuntimeError):
    """A provisioning contract invariant failed."""


BACKEND_DEPENDENCY_INPUTS = (
    "services/auth/package-lock.json",
    "infra/pm2/package-lock.json",
    "services/scada-gate-control/package-lock.json",
    "services/scada-gate-control-web/package-lock.json",
    "services/flow-monitoring/requirements.txt",
    "services/scheduler/requirements.txt",
    "services/ros-gis-integration/requirements.txt",
    "services/bff-water-planning/requirements.txt",
    "ops/control-plan-read-local/dependency-roots/package-lock.json",
    "ops/control-plan-read-local/python-closures.lock",
)

NODE_ARCHIVE_NAMES = (
    "auth",
    "pm2",
    "scada",
    "gate-web",
    "frontend",
    "dependency-roots",
)

DEBIAN_REPOSITORY_ARTIFACTS = {
    "debian/Packages",
    "debian/Packages.gz",
    "debian/package-names.txt",
    "debian/package-specs.txt",
    "install-debian-closure-linux.sh",
}


def transition_provision_state(current: str, target: str) -> str:
    transitions = {
        "created": {"dependency-staged", "failed", "interrupted"},
        "dependency-staged": {"runtime-reset", "failed", "interrupted"},
        "runtime-reset": {"ready", "failed", "interrupted"},
        "ready": {"failed", "interrupted"},
        "failed": set(),
        "interrupted": set(),
    }
    if target not in transitions.get(current, set()):
        raise ProvisioningContractError("provision_state_transition_invalid")
    return target


def classify_bootstrap_failure(log_text: str, *, interrupted: bool = False) -> str:
    if interrupted:
        return "interrupted"
    normalized = log_text.upper()
    if any(
        marker in normalized
        for marker in ("EINTEGRITY", "CHECKSUM MISMATCH", "DID NOT MATCH")
    ):
        return "nonretryable-integrity"
    if any(
        marker in normalized
        for marker in (
            "ERR_SOCKET_TIMEOUT",
            "ETIMEDOUT",
            "ECONNRESET",
            "EAI_AGAIN",
            "TEMPORARY FAILURE IN NAME RESOLUTION",
        )
    ):
        return "retryable-transport"
    return "nonretryable-bootstrap"


def sanitize_bootstrap_log(log_text: str) -> str:
    credential_url = re.compile(
        r"(\b[a-z][a-z0-9+.-]*://)([^/\s@]*:[^/\s@]+)@", re.IGNORECASE
    )
    connection_assignment = re.compile(r"(?i)\b[A-Z0-9_]*(?:URL|URI|DSN)\s*=")
    secret_key = re.compile(
        r"(?i)(auth|authorization|cookie|password|passwd|secret|token)"
    )
    lines = []
    for line in log_text.splitlines():
        clean = credential_url.sub(r"\1[REDACTED]@", line)
        if connection_assignment.search(clean) or secret_key.search(clean):
            clean = "[REDACTED SECRET-SHAPED LOG LINE]"
        lines.append(clean)
    return "\n".join(lines) + "\n"


def _validate_sha(value: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ProvisioningContractError("provision_sha_invalid")


def _validate_dependency_sha(value: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ProvisioningContractError("dependency_sha_invalid")


def _validate_label(value: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", value):
        raise ProvisioningContractError("provision_label_invalid")


def dependency_input_digests(repo_root: Path, frontend_root: Path) -> dict[str, str]:
    inputs = {
        relative_name: _sha256_file(repo_root / relative_name)
        for relative_name in BACKEND_DEPENDENCY_INPUTS
    }
    inputs["frontend/package-lock.json"] = _sha256_file(
        frontend_root / "package-lock.json"
    )
    return dict(sorted(inputs.items()))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_debian_repository_artifacts(artifact_names: set[str]) -> None:
    has_debian_package = any(
        Path(name).parent == Path("debian") and Path(name).suffix == ".deb"
        for name in artifact_names
    )
    if (
        not DEBIAN_REPOSITORY_ARTIFACTS.issubset(artifact_names)
        or not has_debian_package
    ):
        raise ProvisioningContractError("dependency_debian_repository_not_accepted")


def _validate_debian_repository_contents(
    bundle_root: Path, artifact_names: set[str]
) -> None:
    try:
        packages_body = (bundle_root / "debian/Packages").read_bytes()
        if (
            gzip.decompress((bundle_root / "debian/Packages.gz").read_bytes())
            != packages_body
        ):
            raise ValueError
        package_names = (
            (bundle_root / "debian/package-names.txt")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        package_specs = (
            (bundle_root / "debian/package-specs.txt")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        packages_text = packages_body.decode("utf-8")
    except (EOFError, OSError, UnicodeDecodeError, ValueError) as exc:
        raise ProvisioningContractError(
            "dependency_debian_repository_not_accepted"
        ) from exc

    indexed_names = []
    indexed_specs = []
    indexed_artifacts = set()
    for paragraph in re.split(r"\n\s*\n", packages_text.strip()):
        fields = {}
        for line in paragraph.splitlines():
            if line[:1].isspace():
                continue
            key, separator, value = line.partition(":")
            if not separator or key in fields:
                raise ProvisioningContractError(
                    "dependency_debian_repository_not_accepted"
                )
            fields[key] = value.strip()
        package_name = fields.get("Package", "")
        package_version = fields.get("Version", "")
        filename = fields.get("Filename", "")
        size = fields.get("Size", "")
        sha256 = fields.get("SHA256", "")
        relative_filename = Path(filename.removeprefix("./"))
        artifact_name = f"debian/{relative_filename.as_posix()}"
        if (
            not re.fullmatch(r"[a-z0-9][a-z0-9+.-]*", package_name)
            or not package_version
            or any(character.isspace() for character in package_version)
            or not filename.startswith("./")
            or relative_filename.is_absolute()
            or ".." in relative_filename.parts
            or relative_filename.parent != Path(".")
            or relative_filename.suffix != ".deb"
            or artifact_name not in artifact_names
            or not size.isdigit()
            or not re.fullmatch(r"[0-9a-f]{64}", sha256)
        ):
            raise ProvisioningContractError("dependency_debian_repository_not_accepted")
        artifact = bundle_root / artifact_name
        if artifact.stat().st_size != int(size) or _sha256_file(artifact) != sha256:
            raise ProvisioningContractError("dependency_debian_repository_not_accepted")
        indexed_names.append(package_name)
        indexed_specs.append(f"{package_name}={package_version}")
        indexed_artifacts.add(artifact_name)

    debian_artifacts = {
        name
        for name in artifact_names
        if Path(name).parent == Path("debian") and Path(name).suffix == ".deb"
    }
    if (
        not indexed_names
        or len(indexed_names) != len(set(indexed_names))
        or package_names != sorted(indexed_names)
        or package_specs != sorted(indexed_specs)
        or indexed_artifacts != debian_artifacts
    ):
        raise ProvisioningContractError("dependency_debian_repository_not_accepted")


def _write_json_atomic(path: Path, body: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(body, stream, indent=2, sort_keys=True)
            stream.write("\n")
        temporary.chmod(0o600)
        temporary.replace(path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def validate_node_modules_archive(archive_path: Path, *, archive_name: str) -> None:
    if archive_name not in NODE_ARCHIVE_NAMES:
        raise ProvisioningContractError("node_modules_archive_name_invalid")
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
    except (OSError, tarfile.TarError) as exc:
        raise ProvisioningContractError("node_modules_archive_invalid") from exc
    if not members:
        raise ProvisioningContractError("node_modules_archive_invalid")
    symlink_names = set()
    for member in members:
        normalized = posixpath.normpath(member.name)
        if (
            member.name.startswith("/")
            or normalized == ".."
            or normalized.startswith("../")
            or not (
                normalized == "node_modules" or normalized.startswith("node_modules/")
            )
            or not (
                member.isfile() or member.isdir() or member.issym() or member.islnk()
            )
        ):
            raise ProvisioningContractError("node_modules_archive_invalid")
        if member.issym():
            symlink_names.add(normalized)
            if member.linkname.startswith("/"):
                raise ProvisioningContractError("node_modules_archive_invalid")
            resolved_link = posixpath.normpath(
                posixpath.join(posixpath.dirname(normalized), member.linkname)
            )
            allowed_local_shared = (
                archive_name == "auth"
                and normalized == "node_modules/@munbon/shared"
                and member.linkname == "../../../../shared/nodejs"
            )
            if not allowed_local_shared and not (
                resolved_link == "node_modules"
                or resolved_link.startswith("node_modules/")
            ):
                raise ProvisioningContractError("node_modules_archive_invalid")
        if member.islnk():
            hardlink_target = posixpath.normpath(member.linkname)
            if not hardlink_target.startswith("node_modules/"):
                raise ProvisioningContractError("node_modules_archive_invalid")
    if any(
        member_name.startswith(f"{symlink_name}/")
        for symlink_name in symlink_names
        for member_name in (posixpath.normpath(member.name) for member in members)
    ):
        raise ProvisioningContractError("node_modules_archive_invalid")


def _recorded_at() -> str:
    return (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


def write_provision_state(
    state_root: Path,
    *,
    state: str,
    release_sha: str,
    frontend_sha: str,
    dependency_sha256: str,
    phase: str,
    substep: str,
) -> Path:
    _validate_sha(release_sha)
    _validate_sha(frontend_sha)
    _validate_dependency_sha(dependency_sha256)
    _validate_label(phase)
    _validate_label(substep)
    state_path = state_root / "state.json"
    if state_path.exists():
        try:
            current = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProvisioningContractError("provision_state_invalid") from exc
        if (
            current.get("release_sha") != release_sha
            or current.get("frontend_sha") != frontend_sha
            or current.get("dependency_sha256") != dependency_sha256
        ):
            raise ProvisioningContractError("provision_state_sha_mismatch")
        transition_provision_state(current.get("state", ""), state)
    elif state != "created":
        raise ProvisioningContractError("provision_state_transition_invalid")
    body = {
        "dependency_sha256": dependency_sha256,
        "frontend_sha": frontend_sha,
        "phase": phase,
        "recorded_at": _recorded_at(),
        "release_sha": release_sha,
        "state": state,
        "substep": substep,
    }
    _write_json_atomic(state_path, body)
    return state_path


def write_failure_bundle(
    state_root: Path,
    *,
    release_sha: str,
    frontend_sha: str,
    dependency_sha256: str,
    phase: str,
    substep: str,
    exit_code: int,
    log_text: str,
    tool_versions: dict[str, str],
    interrupted: bool = False,
) -> Path:
    _validate_label(phase)
    _validate_label(substep)
    if not isinstance(exit_code, int) or not 0 < exit_code <= 255:
        raise ProvisioningContractError("failure_exit_code_invalid")
    if not tool_versions or any(
        not re.fullmatch(r"[a-z0-9-]{1,32}", key)
        or not isinstance(value, str)
        or not re.fullmatch(r"[A-Za-z0-9.+_-]{1,64}", value)
        for key, value in tool_versions.items()
    ):
        raise ProvisioningContractError("failure_tool_versions_invalid")
    terminal_state = "interrupted" if interrupted else "failed"
    write_provision_state(
        state_root,
        state=terminal_state,
        release_sha=release_sha,
        frontend_sha=frontend_sha,
        dependency_sha256=dependency_sha256,
        phase=phase,
        substep=substep,
    )
    failure_root = state_root / "failure"
    if failure_root.exists():
        raise ProvisioningContractError("failure_bundle_exists")
    temporary = Path(tempfile.mkdtemp(prefix=".failure-", dir=state_root))
    temporary.chmod(0o700)
    try:
        sanitized = sanitize_bootstrap_log(log_text)
        metadata = {
            "classification": classify_bootstrap_failure(
                log_text, interrupted=interrupted
            ),
            "dependency_sha256": dependency_sha256,
            "exit_code": exit_code,
            "frontend_sha": frontend_sha,
            "phase": phase,
            "recorded_at": _recorded_at(),
            "release_sha": release_sha,
            "state": terminal_state,
            "substep": substep,
            "tool_versions": dict(sorted(tool_versions.items())),
        }
        log_path = temporary / "bootstrap-sanitized.log"
        metadata_path = temporary / "metadata.json"
        log_path.write_text(sanitized, encoding="utf-8")
        metadata_path.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        for path in (log_path, metadata_path):
            path.chmod(0o600)
        checksum_path = temporary / "SHA256SUMS"
        checksum_path.write_text(
            "".join(
                f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
                for path in (log_path, metadata_path)
            ),
            encoding="utf-8",
        )
        checksum_path.chmod(0o600)
        temporary.replace(failure_root)
    finally:
        if temporary.exists():
            for path in temporary.iterdir():
                path.unlink()
            temporary.rmdir()
    return failure_root


def validate_dependency_bundle(
    bundle_root: Path,
    *,
    release_sha: str,
    frontend_sha: str,
    expected_inputs: dict[str, str],
) -> dict:
    manifest_path = bundle_root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProvisioningContractError("dependency_manifest_invalid") from exc
    expected_platform = {
        "architecture": "aarch64",
        "distribution": "debian",
        "distribution_version": "12",
        "node": "22.23.1",
        "npm": "10.9.8",
        "python": "3.11",
    }
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != 2
        or manifest.get("platform") != expected_platform
        or manifest.get("release_sha") != release_sha
        or manifest.get("frontend_sha") != frontend_sha
        or manifest.get("inputs") != expected_inputs
        or not isinstance(manifest.get("artifacts"), dict)
        or not manifest["artifacts"]
    ):
        raise ProvisioningContractError("dependency_manifest_not_accepted")
    _validate_debian_repository_artifacts(set(manifest["artifacts"]))
    for relative_name, expected_sha in sorted(manifest["artifacts"].items()):
        if (
            not isinstance(relative_name, str)
            or Path(relative_name).is_absolute()
            or ".." in Path(relative_name).parts
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha or "")
        ):
            raise ProvisioningContractError("dependency_artifact_invalid")
        artifact = bundle_root / relative_name
        if not artifact.is_file() or artifact.is_symlink():
            raise ProvisioningContractError("dependency_artifact_missing")
        if _sha256_file(artifact) != expected_sha:
            raise ProvisioningContractError("dependency_artifact_checksum_mismatch")
    _validate_debian_repository_contents(bundle_root, set(manifest["artifacts"]))
    actual_artifacts = {
        path.relative_to(bundle_root).as_posix()
        for path in bundle_root.rglob("*")
        if path.is_file()
        and path != manifest_path
        and path != bundle_root / "SHA256SUMS"
    }
    if actual_artifacts != set(manifest["artifacts"]):
        raise ProvisioningContractError("dependency_artifact_inventory_mismatch")
    return manifest


def create_dependency_manifest(
    bundle_root: Path,
    *,
    repo_root: Path,
    frontend_root: Path,
    release_sha: str,
    frontend_sha: str,
) -> dict:
    _validate_sha(release_sha)
    _validate_sha(frontend_sha)
    manifest_path = bundle_root / "manifest.json"
    checksum_path = bundle_root / "SHA256SUMS"
    if manifest_path.exists() or checksum_path.exists():
        raise ProvisioningContractError("dependency_manifest_exists")
    artifacts = {
        path.relative_to(bundle_root).as_posix(): _sha256_file(path)
        for path in sorted(bundle_root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }
    if not artifacts:
        raise ProvisioningContractError("dependency_artifact_inventory_empty")
    _validate_debian_repository_artifacts(set(artifacts))
    _validate_debian_repository_contents(bundle_root, set(artifacts))
    manifest = {
        "schema": 2,
        "platform": {
            "architecture": "aarch64",
            "distribution": "debian",
            "distribution_version": "12",
            "node": "22.23.1",
            "npm": "10.9.8",
            "python": "3.11",
        },
        "release_sha": release_sha,
        "frontend_sha": frontend_sha,
        "inputs": dependency_input_digests(repo_root, frontend_root),
        "artifacts": artifacts,
    }
    _write_json_atomic(manifest_path, manifest)
    checksum_path.write_text(
        "".join(f"{digest}  {name}\n" for name, digest in artifacts.items()),
        encoding="utf-8",
    )
    checksum_path.chmod(0o600)
    return manifest


def _parse_tool_versions(values: list[str]) -> dict[str, str]:
    versions = {}
    for value in values:
        key, separator, version = value.partition("=")
        if not separator:
            raise ProvisioningContractError("failure_tool_versions_invalid")
        versions[key] = version
    return versions


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    state = subparsers.add_parser("state")
    failure = subparsers.add_parser("failure")
    create = subparsers.add_parser("create-manifest")
    validate = subparsers.add_parser("validate-bundle")
    node_archive = subparsers.add_parser("validate-node-archive")
    node_archive.add_argument("--archive", type=Path, required=True)
    node_archive.add_argument("--name", choices=NODE_ARCHIVE_NAMES, required=True)
    for command in (state, failure):
        command.add_argument("--state-root", type=Path, required=True)
        command.add_argument("--release-sha", required=True)
        command.add_argument("--frontend-sha", required=True)
        command.add_argument("--dependency-sha256", required=True)
        command.add_argument("--phase", required=True)
        command.add_argument("--substep", required=True)
    state.add_argument(
        "--state",
        choices=(
            "created",
            "dependency-staged",
            "runtime-reset",
            "ready",
        ),
        required=True,
    )
    failure.add_argument("--exit-code", type=int, required=True)
    failure.add_argument("--log", type=Path, required=True)
    failure.add_argument("--tool-version", action="append", default=[])
    failure.add_argument("--interrupted", action="store_true")
    for command in (create, validate):
        command.add_argument("--bundle-root", type=Path, required=True)
        command.add_argument("--repo-root", type=Path, required=True)
        command.add_argument("--frontend-root", type=Path, required=True)
        command.add_argument("--release-sha", required=True)
        command.add_argument("--frontend-sha", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.action == "state":
            write_provision_state(
                args.state_root,
                state=args.state,
                release_sha=args.release_sha,
                frontend_sha=args.frontend_sha,
                dependency_sha256=args.dependency_sha256,
                phase=args.phase,
                substep=args.substep,
            )
        elif args.action == "failure":
            write_failure_bundle(
                args.state_root,
                release_sha=args.release_sha,
                frontend_sha=args.frontend_sha,
                dependency_sha256=args.dependency_sha256,
                phase=args.phase,
                substep=args.substep,
                exit_code=args.exit_code,
                log_text=args.log.read_text(encoding="utf-8", errors="replace"),
                tool_versions=_parse_tool_versions(args.tool_version),
                interrupted=args.interrupted,
            )
        elif args.action == "create-manifest":
            create_dependency_manifest(
                args.bundle_root,
                repo_root=args.repo_root,
                frontend_root=args.frontend_root,
                release_sha=args.release_sha,
                frontend_sha=args.frontend_sha,
            )
        elif args.action == "validate-bundle":
            manifest = validate_dependency_bundle(
                args.bundle_root,
                release_sha=args.release_sha,
                frontend_sha=args.frontend_sha,
                expected_inputs=dependency_input_digests(
                    args.repo_root, args.frontend_root
                ),
            )
            checksum_lines = (
                (args.bundle_root / "SHA256SUMS")
                .read_text(encoding="utf-8")
                .splitlines()
            )
            expected_checksum_lines = [
                f"{digest}  {name}" for name, digest in manifest["artifacts"].items()
            ]
            if len(checksum_lines) != len(expected_checksum_lines) or set(
                checksum_lines
            ) != set(expected_checksum_lines):
                raise ProvisioningContractError("dependency_checksum_index_invalid")
        else:
            validate_node_modules_archive(args.archive, archive_name=args.name)
        return 0
    except (OSError, ProvisioningContractError) as exc:
        print(f"FAIL {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
