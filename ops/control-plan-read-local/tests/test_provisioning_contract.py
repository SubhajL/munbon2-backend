import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tarfile

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "provisioning_contract.py"
SPEC = importlib.util.spec_from_file_location("provisioning_contract", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
provisioning = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = provisioning
SPEC.loader.exec_module(provisioning)


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def test_transition_provision_state_accepts_only_canonical_sequence_and_terminals():
    assert provisioning.transition_provision_state("created", "dependency-staged") == (
        "dependency-staged"
    )
    assert provisioning.transition_provision_state(
        "dependency-staged", "runtime-reset"
    ) == ("runtime-reset")
    assert provisioning.transition_provision_state("runtime-reset", "ready") == "ready"
    assert provisioning.transition_provision_state("ready", "failed") == "failed"
    assert provisioning.transition_provision_state("created", "failed") == "failed"
    assert provisioning.transition_provision_state(
        "dependency-staged", "interrupted"
    ) == ("interrupted")

    for current, target in (
        ("created", "runtime-reset"),
        ("dependency-staged", "ready"),
        ("failed", "created"),
        ("ready", "dependency-staged"),
    ):
        with pytest.raises(
            provisioning.ProvisioningContractError,
            match="provision_state_transition_invalid",
        ):
            provisioning.transition_provision_state(current, target)


@pytest.mark.parametrize(
    ("log_text", "interrupted", "expected"),
    [
        ("npm error code ERR_SOCKET_TIMEOUT", False, "retryable-transport"),
        ("npm error code EINTEGRITY", False, "nonretryable-integrity"),
        ("sha256sum: checksum did NOT match", False, "nonretryable-integrity"),
        ("command exited unexpectedly", False, "nonretryable-bootstrap"),
        ("npm error code ERR_SOCKET_TIMEOUT", True, "interrupted"),
    ],
)
def test_classify_bootstrap_failure_returns_only_stable_safe_codes(
    log_text, interrupted, expected
):
    assert (
        provisioning.classify_bootstrap_failure(log_text, interrupted=interrupted)
        == expected
    )


def test_sanitize_bootstrap_log_removes_secret_lines_and_credential_urls():
    raw = "\n".join(
        (
            "17 http fetch GET 200 https://registry.npmjs.org/left-pad",
            "18 config authToken=top-secret",
            "19 fetch https://user:password@example.invalid/package.tgz",
            "20 npm error code ERR_SOCKET_TIMEOUT",
            "21 postgresql://dbuser:dbpass@127.0.0.1:5432/munbon",
            "22 redis://:redispass@127.0.0.1:6379/1",
            "23 Authorization: Bearer bearer-value",
            "24 DATABASE_URL=postgresql://dbuser:dbpass@localhost/db",
        )
    )

    sanitized = provisioning.sanitize_bootstrap_log(raw)

    assert sanitized == "\n".join(
        (
            "17 http fetch GET 200 https://registry.npmjs.org/left-pad",
            "[REDACTED SECRET-SHAPED LOG LINE]",
            "19 fetch https://[REDACTED]@example.invalid/package.tgz",
            "20 npm error code ERR_SOCKET_TIMEOUT",
            "21 postgresql://[REDACTED]@127.0.0.1:5432/munbon",
            "22 redis://[REDACTED]@127.0.0.1:6379/1",
            "[REDACTED SECRET-SHAPED LOG LINE]",
            "[REDACTED SECRET-SHAPED LOG LINE]",
            "",
        )
    )
    assert "top-secret" not in sanitized
    assert "password" not in sanitized
    for secret in ("dbpass", "redispass", "bearer-value"):
        assert secret not in sanitized


def test_write_provision_state_is_mode_600_and_rejects_skipped_transition(tmp_path):
    state_root = tmp_path / "provisioning"
    release_sha = "a" * 40
    frontend_sha = "b" * 40
    dependency_sha256 = "c" * 64

    state_path = provisioning.write_provision_state(
        state_root,
        state="created",
        release_sha=release_sha,
        frontend_sha=frontend_sha,
        dependency_sha256=dependency_sha256,
        phase="bootstrap",
        substep="arguments",
    )
    state = json.loads(state_path.read_text())
    recorded_at = state.pop("recorded_at")

    assert state == {
        "frontend_sha": frontend_sha,
        "dependency_sha256": dependency_sha256,
        "phase": "bootstrap",
        "release_sha": release_sha,
        "state": "created",
        "substep": "arguments",
    }
    assert recorded_at.endswith("Z")
    assert state_path.stat().st_mode & 0o777 == 0o600

    with pytest.raises(
        provisioning.ProvisioningContractError,
        match="provision_state_transition_invalid",
    ):
        provisioning.write_provision_state(
            state_root,
            state="ready",
            release_sha=release_sha,
            frontend_sha=frontend_sha,
            dependency_sha256=dependency_sha256,
            phase="ownership",
            substep="owner-marker",
        )


def test_write_failure_bundle_sanitizes_log_and_checksum_indexes_metadata(tmp_path):
    state_root = tmp_path / "provisioning"
    release_sha = "a" * 40
    frontend_sha = "b" * 40
    dependency_sha256 = "c" * 64
    provisioning.write_provision_state(
        state_root,
        state="created",
        release_sha=release_sha,
        frontend_sha=frontend_sha,
        dependency_sha256=dependency_sha256,
        phase="bootstrap",
        substep="arguments",
    )

    failure_root = provisioning.write_failure_bundle(
        state_root,
        release_sha=release_sha,
        frontend_sha=frontend_sha,
        dependency_sha256=dependency_sha256,
        phase="dependency-staging",
        substep="auth-npm-ci",
        exit_code=1,
        log_text="authToken=secret\nnpm error code ERR_SOCKET_TIMEOUT\n",
        tool_versions={"node": "v22.23.1", "npm": "10.9.8"},
    )

    metadata = json.loads((failure_root / "metadata.json").read_text())
    recorded_at = metadata.pop("recorded_at")
    sanitized_log = (failure_root / "bootstrap-sanitized.log").read_text()
    checksum_lines = (failure_root / "SHA256SUMS").read_text().splitlines()

    assert metadata == {
        "classification": "retryable-transport",
        "dependency_sha256": dependency_sha256,
        "exit_code": 1,
        "frontend_sha": frontend_sha,
        "phase": "dependency-staging",
        "release_sha": release_sha,
        "state": "failed",
        "substep": "auth-npm-ci",
        "tool_versions": {"node": "v22.23.1", "npm": "10.9.8"},
    }
    assert recorded_at.endswith("Z")
    assert sanitized_log == (
        "[REDACTED SECRET-SHAPED LOG LINE]\n" "npm error code ERR_SOCKET_TIMEOUT\n"
    )
    assert checksum_lines == [
        f"{_sha256(sanitized_log.encode())}  bootstrap-sanitized.log",
        f"{_sha256((failure_root / 'metadata.json').read_bytes())}  metadata.json",
    ]
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in failure_root.iterdir())


@pytest.mark.parametrize(
    ("interrupted", "expected_state"),
    ((False, "failed"), (True, "interrupted")),
)
def test_owner_publication_failure_after_private_ready_remains_collectable(
    tmp_path, interrupted, expected_state
):
    state_root = tmp_path / "provisioning"
    release_sha = "a" * 40
    frontend_sha = "b" * 40
    dependency_sha256 = "c" * 64
    for state, phase, substep in (
        ("created", "bootstrap", "arguments"),
        ("dependency-staged", "dependencies", "verified"),
        ("runtime-reset", "runtime", "reset"),
        ("ready", "ownership", "ready-state"),
    ):
        provisioning.write_provision_state(
            state_root,
            state=state,
            release_sha=release_sha,
            frontend_sha=frontend_sha,
            dependency_sha256=dependency_sha256,
            phase=phase,
            substep=substep,
        )

    failure_root = provisioning.write_failure_bundle(
        state_root,
        release_sha=release_sha,
        frontend_sha=frontend_sha,
        dependency_sha256=dependency_sha256,
        phase="complete",
        substep="owner-marker",
        exit_code=143 if interrupted else 1,
        log_text="owner publication did not complete\n",
        tool_versions={"bash": "5.2.15"},
        interrupted=interrupted,
    )

    assert json.loads((state_root / "state.json").read_text())["state"] == (
        expected_state
    )
    assert json.loads((failure_root / "metadata.json").read_text())["state"] == (
        expected_state
    )
    assert (failure_root / "SHA256SUMS").is_file()


def test_write_failure_bundle_records_interruption_as_terminal_without_retry(tmp_path):
    state_root = tmp_path / "provisioning"
    provisioning.write_provision_state(
        state_root,
        state="created",
        release_sha="a" * 40,
        frontend_sha="b" * 40,
        dependency_sha256="c" * 64,
        phase="bootstrap",
        substep="arguments",
    )

    failure_root = provisioning.write_failure_bundle(
        state_root,
        release_sha="a" * 40,
        frontend_sha="b" * 40,
        dependency_sha256="c" * 64,
        phase="service-manifests",
        substep="auth-npm-ci",
        exit_code=143,
        log_text="terminated\n",
        tool_versions={"node": "v22.23.1", "npm": "10.9.8"},
        interrupted=True,
    )

    state = json.loads((state_root / "state.json").read_text())
    metadata = json.loads((failure_root / "metadata.json").read_text())
    assert (state["state"], metadata["state"], metadata["classification"]) == (
        "interrupted",
        "interrupted",
        "interrupted",
    )
    with pytest.raises(
        provisioning.ProvisioningContractError,
        match="provision_state_transition_invalid",
    ):
        provisioning.write_provision_state(
            state_root,
            state="created",
            release_sha="a" * 40,
            frontend_sha="b" * 40,
            dependency_sha256="c" * 64,
            phase="bootstrap",
            substep="arguments",
        )


def test_validate_dependency_bundle_binds_shas_inputs_platform_and_artifacts(tmp_path):
    release_sha = "a" * 40
    frontend_sha = "b" * 40
    bundle_root = tmp_path / "bundle"
    wheel = bundle_root / "python" / "scheduler" / "example.whl"
    npm_cache = bundle_root / "npm-cache" / "content"
    wheel.parent.mkdir(parents=True)
    npm_cache.parent.mkdir(parents=True)
    wheel.write_bytes(b"wheel")
    npm_cache.write_bytes(b"npm")
    input_digests = {
        "services/scheduler/requirements.txt": "c" * 64,
        "frontend/package-lock.json": "d" * 64,
    }
    manifest = {
        "schema": 1,
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
        "inputs": input_digests,
        "artifacts": {
            "npm-cache/content": _sha256(b"npm"),
            "python/scheduler/example.whl": _sha256(b"wheel"),
        },
    }
    (bundle_root / "manifest.json").write_text(json.dumps(manifest))

    assert (
        provisioning.validate_dependency_bundle(
            bundle_root,
            release_sha=release_sha,
            frontend_sha=frontend_sha,
            expected_inputs=input_digests,
        )
        == manifest
    )

    wheel.write_bytes(b"tampered")
    with pytest.raises(
        provisioning.ProvisioningContractError,
        match="dependency_artifact_checksum_mismatch",
    ):
        provisioning.validate_dependency_bundle(
            bundle_root,
            release_sha=release_sha,
            frontend_sha=frontend_sha,
            expected_inputs=input_digests,
        )


def test_validate_bundle_cli_accepts_checksum_index_in_any_order(tmp_path):
    repo = tmp_path / "repo"
    frontend = tmp_path / "frontend"
    bundle = tmp_path / "bundle"
    for relative_name in provisioning.BACKEND_DEPENDENCY_INPUTS:
        path = repo / relative_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative_name)
    frontend.mkdir()
    (frontend / "package-lock.json").write_text("frontend")
    for relative_name in ("z-last", "a-first"):
        path = bundle / relative_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative_name)
    provisioning.create_dependency_manifest(
        bundle,
        repo_root=repo,
        frontend_root=frontend,
        release_sha="a" * 40,
        frontend_sha="b" * 40,
    )
    checksum_path = bundle / "SHA256SUMS"
    checksum_path.write_text(
        "\n".join(reversed(checksum_path.read_text().splitlines())) + "\n"
    )

    assert (
        provisioning.main(
            [
                "validate-bundle",
                "--bundle-root",
                str(bundle),
                "--repo-root",
                str(repo),
                "--frontend-root",
                str(frontend),
                "--release-sha",
                "a" * 40,
                "--frontend-sha",
                "b" * 40,
            ]
        )
        == 0
    )


def test_validate_node_modules_archive_rejects_traversal_and_escaping_links(tmp_path):
    safe = tmp_path / "safe.tar.gz"
    with tarfile.open(safe, "w:gz") as archive:
        directory = tarfile.TarInfo("node_modules/package")
        directory.type = tarfile.DIRTYPE
        archive.addfile(directory)
        link = tarfile.TarInfo("node_modules/.bin/package")
        link.type = tarfile.SYMTYPE
        link.linkname = "../package/bin.js"
        archive.addfile(link)

    assert provisioning.validate_node_modules_archive(safe, archive_name="pm2") is None

    for name, linkname in (
        ("../outside", None),
        ("node_modules/.bin/escape", "../../../outside"),
    ):
        malicious = tmp_path / f"malicious-{len(name)}-{len(linkname or '')}.tar.gz"
        with tarfile.open(malicious, "w:gz") as archive:
            member = tarfile.TarInfo(name)
            if linkname is None:
                member.type = tarfile.REGTYPE
                member.size = 0
            else:
                member.type = tarfile.SYMTYPE
                member.linkname = linkname
            archive.addfile(member)
        with pytest.raises(
            provisioning.ProvisioningContractError,
            match="node_modules_archive_invalid",
        ):
            provisioning.validate_node_modules_archive(malicious, archive_name="pm2")

    symlink_prefix = tmp_path / "symlink-prefix.tar.gz"
    with tarfile.open(symlink_prefix, "w:gz") as archive:
        shared = tarfile.TarInfo("node_modules/@munbon/shared")
        shared.type = tarfile.SYMTYPE
        shared.linkname = "../../../../shared/nodejs"
        archive.addfile(shared)
        nested = tarfile.TarInfo("node_modules/@munbon/shared/escape")
        nested.type = tarfile.REGTYPE
        nested.size = 0
        archive.addfile(nested)
    with pytest.raises(
        provisioning.ProvisioningContractError,
        match="node_modules_archive_invalid",
    ):
        provisioning.validate_node_modules_archive(symlink_prefix, archive_name="auth")


@pytest.mark.parametrize(
    "archive_name",
    ("pm2", "scada", "gate-web", "frontend", "dependency-roots"),
)
def test_validate_node_modules_archive_allows_workspace_link_only_for_auth(
    tmp_path, archive_name
):
    archive_path = tmp_path / f"{archive_name}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        shared = tarfile.TarInfo("node_modules/@munbon/shared")
        shared.type = tarfile.SYMTYPE
        shared.linkname = "../../../../shared/nodejs"
        archive.addfile(shared)

    with pytest.raises(
        provisioning.ProvisioningContractError,
        match="node_modules_archive_invalid",
    ):
        provisioning.validate_node_modules_archive(
            archive_path, archive_name=archive_name
        )

    assert (
        provisioning.validate_node_modules_archive(archive_path, archive_name="auth")
        is None
    )
