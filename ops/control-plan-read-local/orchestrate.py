#!/usr/bin/env python3
"""Host-side orchestration for isolated local control-plan acceptance."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provisioning_contract import (  # noqa: E402
    ProvisioningContractError,
    dependency_input_digests,
    validate_dependency_bundle,
)

ACCEPTED_BASE_SHA = "8095bfe37550200da00ecb554edc646febf8aff9"
MACHINE_NAME = "munbon-control-plan-local"
REHEARSAL_MACHINE_NAME = "munbon-control-plan-rehearsal"
DIAGNOSTIC_MACHINE_NAME = "munbon-control-plan-write-ui-diagnostic"
CAMPAIGN_LEDGER_V1_STAGE_ORDER = (
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
STAGE_ORDER = (*CAMPAIGN_LEDGER_V1_STAGE_ORDER, "LOCAL-WRITE-ACT-1")
REHEARSAL_STAGE_ORDER = CAMPAIGN_LEDGER_V1_STAGE_ORDER[:3]
EVIDENCE_HARNESS_ARTIFACTS = (
    "local-ac1.py",
    "run-evidence-browser.js",
    "run-go-read-browser.js",
    "run-read-browser.js",
    "run-ros-manual-producer.sh",
    "run-stage-suite.py",
    "run-write-browser.js",
    "seed-approved-sources.py",
    "seed-local-operators.js",
    "provisioning_contract.py",
    "validate-dependency-bundle-linux.sh",
    "verify_bearer.py",
)
RC_PROCESS_NAMES = (
    "flow-monitoring",
    "scheduler",
    "ros-gis-integration",
    "bff-water-planning",
)
FAILURE_MANIFEST_EXIT_CODE = 70


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


def _host_harness_hashes() -> dict[str, str]:
    harness_root = Path(__file__).resolve().parent
    hashes: dict[str, str] = {}
    try:
        for name in EVIDENCE_HARNESS_ARTIFACTS:
            path = (
                harness_root.parent / "control-plan-read-runtime" / name
                if name == "verify_bearer.py"
                else harness_root / name
            )
            hashes[name] = _sha256_file(path)
    except OSError as exc:
        raise OrchestrationError("rc_evidence_identity_mismatch") from exc
    return hashes


def _is_canonical_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def validate_campaign_ledger(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise OrchestrationError("campaign_ledger_invalid") from exc
    if not lines or any(not line for line in lines):
        raise OrchestrationError("campaign_ledger_invalid")

    entries: list[dict] = []
    previous_entry_sha256: str | None = None
    campaign_ids: set[str] = set()
    for line in lines:
        try:
            entry = json.loads(line, object_pairs_hook=_strict_ledger_object)
        except json.JSONDecodeError as exc:
            raise OrchestrationError("campaign_ledger_invalid") from exc
        if not isinstance(entry, dict) or set(entry) != {
            "schema_version",
            "campaign_id",
            "recorded_at",
            "candidate",
            "guest",
            "evidence",
            "outcome",
            "authorization",
            "previous_entry_sha256",
            "entry_sha256",
        }:
            raise OrchestrationError("campaign_ledger_schema_invalid")

        candidate = entry["candidate"]
        guest = entry["guest"]
        evidence = entry["evidence"]
        outcome = entry["outcome"]
        authorization = entry["authorization"]
        outcome_lists_are_valid = (
            isinstance(outcome, dict)
            and set(outcome) == {"acceptance", "passed", "failed", "unreached"}
            and all(
                isinstance(outcome.get(name), list)
                for name in ("passed", "failed", "unreached")
            )
        )
        failure_outcome_is_valid = (
            outcome_lists_are_valid
            and outcome.get("acceptance") is False
            and len(outcome["failed"]) == 1
            and [*outcome["passed"], *outcome["failed"], *outcome["unreached"]]
            == list(CAMPAIGN_LEDGER_V1_STAGE_ORDER)
        )
        successful_outcome_is_valid = (
            outcome_lists_are_valid
            and outcome.get("acceptance") is True
            and outcome["passed"] == list(CAMPAIGN_LEDGER_V1_STAGE_ORDER)
            and outcome["failed"] == []
            and outcome["unreached"] == []
            and isinstance(evidence, dict)
            and evidence.get("index_name") == "OUTER-SHA256SUMS"
        )
        authorization_shape_is_valid = isinstance(authorization, dict) and set(
            authorization
        ) == {"state", "attempt", "ceiling"}
        authorization_attempt = (
            authorization.get("attempt") if authorization_shape_is_valid else None
        )
        authorization_ceiling = (
            authorization.get("ceiling") if authorization_shape_is_valid else None
        )
        authorization_attempts_are_valid = (
            type(authorization_attempt) is int
            and type(authorization_ceiling) is int
            and 0 < authorization_attempt <= authorization_ceiling
        )
        historical_authorization_is_valid = (
            authorization_shape_is_valid
            and authorization.get("state") == "historical_closed"
            and authorization_attempt is None
            and authorization_ceiling is None
        )
        exhausted_authorization_is_valid = (
            authorization_shape_is_valid
            and authorization.get("state") == "exhausted"
            and authorization_attempts_are_valid
            and authorization_attempt == authorization_ceiling
        )
        successful_authorization_is_valid = (
            authorization_shape_is_valid
            and authorization.get("state") == "successful_closed"
            and authorization_attempts_are_valid
        )
        ledger_variant_is_valid = (
            failure_outcome_is_valid
            and (historical_authorization_is_valid or exhausted_authorization_is_valid)
        ) or (successful_outcome_is_valid and successful_authorization_is_valid)
        if (
            type(entry["schema_version"]) is not int
            or entry["schema_version"] != 1
            or not isinstance(entry["campaign_id"], str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", entry["campaign_id"])
            or entry["campaign_id"] in campaign_ids
            or not isinstance(entry["recorded_at"], str)
            or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", entry["recorded_at"]
            )
            or not _is_canonical_utc_timestamp(entry["recorded_at"])
            or not isinstance(candidate, dict)
            or set(candidate)
            != {
                "backend_sha",
                "frontend_sha",
                "dependency_sha256",
                "harness_hashes",
            }
            or not isinstance(candidate.get("backend_sha"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", candidate["backend_sha"])
            or not isinstance(candidate.get("frontend_sha"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", candidate["frontend_sha"])
            or (
                candidate.get("dependency_sha256") is not None
                and (
                    not isinstance(candidate["dependency_sha256"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", candidate["dependency_sha256"])
                )
            )
            or not isinstance(candidate.get("harness_hashes"), dict)
            or not candidate["harness_hashes"]
            or not all(
                isinstance(name, str)
                and re.fullmatch(r"[A-Za-z0-9_.-]+", name)
                and isinstance(digest, str)
                and re.fullmatch(r"[0-9a-f]{64}", digest)
                for name, digest in candidate["harness_hashes"].items()
            )
            or not isinstance(guest, dict)
            or set(guest) != {"name", "id", "architecture"}
            or guest.get("name") != MACHINE_NAME
            or guest.get("architecture") != "arm64"
            or (
                guest.get("id") is not None
                and (
                    not isinstance(guest["id"], str)
                    or not re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", guest["id"])
                )
            )
            or not isinstance(evidence, dict)
            or set(evidence) != {"ref", "index_name", "index_sha256"}
            or not isinstance(evidence.get("ref"), str)
            or not evidence["ref"]
            or evidence.get("index_name")
            not in {"SHA256SUMS", "OUTER-SHA256SUMS", "PARTIAL-OUTER-SHA256SUMS"}
            or not isinstance(evidence.get("index_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", evidence["index_sha256"])
            or not ledger_variant_is_valid
        ):
            raise OrchestrationError("campaign_ledger_schema_invalid")
        if entry["previous_entry_sha256"] != previous_entry_sha256:
            raise OrchestrationError("campaign_ledger_chain_invalid")

        claimed_entry_sha256 = entry["entry_sha256"]
        canonical_entry = {
            key: value for key, value in entry.items() if key != "entry_sha256"
        }
        actual_entry_sha256 = hashlib.sha256(
            json.dumps(canonical_entry, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
        if claimed_entry_sha256 != actual_entry_sha256:
            raise OrchestrationError("campaign_ledger_entry_hash_invalid")
        campaign_ids.add(entry["campaign_id"])
        previous_entry_sha256 = claimed_entry_sha256
        entries.append(entry)
    return entries


def _is_canonical_utc_timestamp(value: str) -> bool:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ") == value


def _strict_ledger_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise OrchestrationError("campaign_ledger_schema_invalid")
        result[key] = value
    return result


def validate_campaign_ledger_append_only(base_path: Path, path: Path) -> list[dict]:
    entries = validate_campaign_ledger(path)
    try:
        base = base_path.read_bytes()
        current = path.read_bytes()
    except OSError as exc:
        raise OrchestrationError("campaign_ledger_invalid") from exc
    if not base:
        return entries
    validate_campaign_ledger(base_path)
    if not base.endswith(b"\n") or not current.startswith(base):
        raise OrchestrationError("campaign_ledger_history_rewritten")
    return entries


@dataclass(frozen=True)
class MachineSpec:
    name: str = MACHINE_NAME
    user: str = "munbonlocal"
    architecture: str = "arm64"
    memory: str = "8G"
    cpus: str = "4"
    disk: str = "40G"
    distribution: str = "debian:12"


def _build_machine_command(spec: MachineSpec, expected_name: str) -> list[str]:
    if spec != MachineSpec(name=expected_name):
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


def build_machine_command(spec: MachineSpec) -> list[str]:
    return _build_machine_command(spec, MACHINE_NAME)


def build_rehearsal_machine_command() -> list[str]:
    return _build_machine_command(
        MachineSpec(name=REHEARSAL_MACHINE_NAME), REHEARSAL_MACHINE_NAME
    )


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


def _build_guest_command(
    machine_name: str,
    argv: list[str],
    *,
    user: str = "munbon",
    workdir: str | None = None,
) -> list[str]:
    if not argv or user not in {"root", "munbon"}:
        raise OrchestrationError("guest_command_invalid")
    command = ["orb", "-m", machine_name, "-u", user]
    if workdir is not None:
        command.extend(["--workdir", workdir])
    return [*command, *argv]


def build_guest_command(
    argv: list[str], *, user: str = "munbon", workdir: str | None = None
) -> list[str]:
    return _build_guest_command(MACHINE_NAME, argv, user=user, workdir=workdir)


def build_rehearsal_guest_command(
    argv: list[str], *, user: str = "munbon", workdir: str | None = None
) -> list[str]:
    return _build_guest_command(
        REHEARSAL_MACHINE_NAME, argv, user=user, workdir=workdir
    )


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


def classify_rehearsal_machine_inventory(inventory_json: str) -> str:
    return _classify_machine_inventory(inventory_json, REHEARSAL_MACHINE_NAME)


def classify_diagnostic_machine_inventory(inventory_json: str) -> str:
    return _classify_machine_inventory(inventory_json, DIAGNOSTIC_MACHINE_NAME)


def validate_rc_guest_identity(
    inventory_json: str, expected_guest_id: str
) -> dict[str, str]:
    try:
        if not isinstance(expected_guest_id, str) or not re.fullmatch(
            r"[0-9A-HJKMNP-TV-Z]{26}", expected_guest_id
        ):
            raise ValueError
        inventory = json.loads(inventory_json)
        if not isinstance(inventory, list):
            raise ValueError
        matches = [
            item
            for item in inventory
            if isinstance(item, dict) and item.get("name") == MACHINE_NAME
        ]
        if len(matches) != 1:
            raise ValueError
        machine = matches[0]
        image = machine.get("image")
        config = machine.get("config")
        if (
            machine.get("id") != expected_guest_id
            or not isinstance(image, dict)
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
        return {"name": MACHINE_NAME, "id": expected_guest_id, "architecture": "arm64"}
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise OrchestrationError("rc_guest_identity_not_accepted") from exc


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


def validate_rehearsal_owner(marker_json: str) -> None:
    try:
        marker = json.loads(marker_json)
        if (
            not isinstance(marker, dict)
            or set(marker)
            != {
                "machine",
                "architecture",
                "state",
                "release_sha",
                "frontend_sha",
                "dependency_sha256",
                "execution_kind",
                "acceptance_evidence",
            }
            or marker.get("machine") != REHEARSAL_MACHINE_NAME
            or marker.get("architecture") != "arm64"
            or marker.get("state") != "ready"
            or marker.get("execution_kind") != "rehearsal"
            or marker.get("acceptance_evidence") is not False
            or not re.fullmatch(r"[0-9a-f]{40}", marker.get("release_sha", ""))
            or not re.fullmatch(r"[0-9a-f]{40}", marker.get("frontend_sha", ""))
            or not re.fullmatch(r"[0-9a-f]{64}", marker.get("dependency_sha256", ""))
        ):
            raise ValueError
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise OrchestrationError("rehearsal_owner_not_accepted") from exc


def validate_existing_guest(
    provision_state_json: str, owner_json: str, *, execution_kind: str = "canonical"
) -> None:
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
    if execution_kind == "canonical":
        validate_machine_owner(owner_json)
    elif execution_kind == "rehearsal":
        validate_rehearsal_owner(owner_json)
    else:
        raise OrchestrationError("execution_kind_not_accepted")
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
    *,
    execution_kind: str = "canonical",
) -> None:
    validate_existing_guest(
        provision_state_json, owner_json, execution_kind=execution_kind
    )
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


def finalize_rehearsal_bootstrap_failure_bundle(destination: Path) -> dict:
    metadata = finalize_bootstrap_failure_bundle(destination)
    (destination / "OUTER-SHA256SUMS").unlink()
    bundle = destination / "bundle"
    (bundle / "SHA256SUMS").rename(bundle / "REHEARSAL-SHA256SUMS")
    summary = {
        **metadata,
        "schema_version": 1,
        "evidence_kind": "non_authoritative_rehearsal",
        "execution_kind": "rehearsal",
        "acceptance_evidence": False,
    }
    summary_path = destination / "REHEARSAL-BOOTSTRAP-SUMMARY.json"
    summary_path.write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    summary_path.chmod(0o600)
    outer_path = destination / "REHEARSAL-BOOTSTRAP-OUTER-SHA256SUMS"
    outer_path.write_text(
        "".join(
            [
                *(
                    f"{_sha256_file(path)}  bundle/{path.name}\n"
                    for path in sorted(bundle.iterdir())
                ),
                f"{_sha256_file(summary_path)}  {summary_path.name}\n",
            ]
        ),
        encoding="utf-8",
    )
    outer_path.chmod(0o600)
    return summary


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


def _build_isolated_write_command(machine_name: str, destination: str) -> list[str]:
    if not destination.startswith("/opt/munbon/input/") or destination.endswith("/"):
        raise OrchestrationError("isolated_destination_invalid")
    return [
        "orb",
        "-m",
        machine_name,
        "-u",
        "root",
        "tee",
        destination,
    ]


def build_isolated_write_command(destination: str) -> list[str]:
    return _build_isolated_write_command(MACHINE_NAME, destination)


def build_rehearsal_isolated_write_command(destination: str) -> list[str]:
    return _build_isolated_write_command(REHEARSAL_MACHINE_NAME, destination)


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


def _rehearsal_machine_state() -> str:
    inventory = _run_checked(
        "rehearsal_orb_inventory", ["orb", "list", "--format", "json"], timeout=30
    )
    return classify_rehearsal_machine_inventory(inventory)


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
    _run_checked(
        "diagnostic_dpkg_scanpackages",
        build_diagnostic_command(["dpkg-scanpackages", "--version"]),
        timeout=30,
    )


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


def _push_isolated_file_with_command(
    source: Path, destination: str, command: list[str]
) -> None:
    try:
        with source.open("rb") as stream:
            result = subprocess.run(
                command,
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


def _push_isolated_file(source: Path, destination: str) -> None:
    _push_isolated_file_with_command(
        source, destination, build_isolated_write_command(destination)
    )


def _push_rehearsal_isolated_file(source: Path, destination: str) -> None:
    _push_isolated_file_with_command(
        source, destination, build_rehearsal_isolated_write_command(destination)
    )


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
            local_dir / "install-debian-closure-linux.sh",
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
                f"{remote_root}/install-debian-closure-linux.sh",
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


def _provision(
    repo: Path,
    release_sha: str,
    frontend_repo: Path,
    frontend_sha: str,
    dependency_archive: Path,
    dependency_archive_sha256: str,
    failure_directory: Path,
    *,
    execution_kind: str,
) -> None:
    if execution_kind == "canonical":
        machine_state = _machine_state
        machine_command = build_machine_command(MachineSpec())
        guest_command = build_guest_command
        push_isolated_file = _push_isolated_file
    elif execution_kind == "rehearsal":
        machine_state = _rehearsal_machine_state
        machine_command = build_rehearsal_machine_command()
        guest_command = build_rehearsal_guest_command
        push_isolated_file = _push_rehearsal_isolated_file
    else:
        raise OrchestrationError("execution_kind_not_accepted")
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
    state = machine_state()
    created_now = state == "missing"
    if state == "missing":
        _run_checked("orb_create", machine_command, timeout=600)
        if machine_state() != "ready":
            raise OrchestrationError("machine_create_not_ready")
    if not created_now:
        provision_state = _run_checked(
            "machine_provision_state",
            guest_command(
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
            guest_command(
                [
                    "sh",
                    "-c",
                    "test ! -f /var/lib/munbon-local-acceptance/owner.json || cat /var/lib/munbon-local-acceptance/owner.json",
                ],
                user="root",
            ),
            timeout=30,
        )
        validate_existing_guest(provision_state, owner, execution_kind=execution_kind)
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
            guest_command(
                ["install", "-d", "-m", "0700", "/opt/munbon/input"],
                user="root",
            ),
            timeout=30,
        )
        for source in (bundle, frontend_bundle, dependency_archive, *sources):
            push_isolated_file(source, f"/opt/munbon/input/{source.name}")
    try:
        _run_checked(
            "bootstrap_linux",
            guest_command(
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
                    execution_kind,
                ],
                user="root",
            ),
            timeout=3600,
        )
    except CommandExecutionError as exc:
        try:
            if execution_kind == "canonical":
                metadata = collect_bootstrap_failure(failure_directory)
            else:
                metadata = collect_bootstrap_failure(
                    failure_directory, execution_kind="rehearsal"
                )
        except OrchestrationError as collection_exc:
            raise OrchestrationError(
                "bootstrap_linux_failed_and_failure_collection_failed"
            ) from collection_exc
        classification = metadata["classification"].replace("-", "_")
        raise OrchestrationError(f"bootstrap_linux_failed_{classification}") from exc


def provision(
    repo: Path,
    release_sha: str,
    frontend_repo: Path,
    frontend_sha: str,
    dependency_archive: Path,
    dependency_archive_sha256: str,
    failure_directory: Path,
) -> None:
    _provision(
        repo,
        release_sha,
        frontend_repo,
        frontend_sha,
        dependency_archive,
        dependency_archive_sha256,
        failure_directory,
        execution_kind="canonical",
    )


def provision_rehearsal(
    repo: Path,
    release_sha: str,
    frontend_repo: Path,
    frontend_sha: str,
    dependency_archive: Path,
    dependency_archive_sha256: str,
    failure_directory: Path,
) -> None:
    _provision(
        repo,
        release_sha,
        frontend_repo,
        frontend_sha,
        dependency_archive,
        dependency_archive_sha256,
        failure_directory,
        execution_kind="rehearsal",
    )


def _run_stage(
    stage: str,
    release_sha: str,
    frontend_sha: str,
    as_of_date: str | None = None,
    *,
    execution_kind: str,
    expected_machine_id: str | None = None,
) -> None:
    if execution_kind == "canonical":
        accepted_stages = STAGE_ORDER
        machine_state = _machine_state
        guest_command = build_guest_command
    elif execution_kind == "rehearsal":
        accepted_stages = REHEARSAL_STAGE_ORDER
        machine_state = _rehearsal_machine_state
        guest_command = build_rehearsal_guest_command
    else:
        raise OrchestrationError("execution_kind_not_accepted")
    if stage not in accepted_stages:
        raise OrchestrationError("stage_not_supported")
    if expected_machine_id is not None:
        if (
            execution_kind != "canonical"
            or not isinstance(expected_machine_id, str)
            or not re.fullmatch(r"[0-9a-f]{32}", expected_machine_id)
        ):
            raise OrchestrationError("rc_guest_machine_identity_mismatch")
    if machine_state() != "ready":
        raise OrchestrationError("machine_not_ready")
    provision_state = _run_checked(
        "stage_provision_state",
        guest_command(
            ["cat", "/var/lib/munbon-local-acceptance/provisioning/state.json"],
            user="root",
        ),
        timeout=30,
    )
    owner = _run_checked(
        "stage_machine_owner",
        guest_command(
            ["cat", "/var/lib/munbon-local-acceptance/owner.json"], user="root"
        ),
        timeout=30,
    )
    validate_stage_guest(
        provision_state,
        owner,
        release_sha,
        frontend_sha,
        execution_kind=execution_kind,
    )
    terminal_failure = _run_checked(
        "stage_terminal_failure",
        guest_command(
            [
                "sh",
                "-c",
                "find /var/lib/munbon-local-acceptance/evidence -maxdepth 1 -type f -name '*-failure.json' -print -quit",
            ],
            user="root",
        ),
        timeout=30,
    )
    if terminal_failure.strip():
        raise OrchestrationError("stage_failure_terminal")
    stage_argv = [
        "python3",
        "/opt/munbon/harness/run-stage-suite.py",
        stage,
        "--release-sha",
        release_sha,
        "--frontend-sha",
        frontend_sha,
    ]
    stage_argv.extend(["--execution-kind", execution_kind])
    if as_of_date is not None:
        stage_argv.extend(["--as-of-date", as_of_date])
    if expected_machine_id is not None:
        stage_argv.extend(["--expected-machine-id", expected_machine_id])
    try:
        _run_checked(
            stage.lower().replace("-", "_"),
            guest_command(stage_argv, workdir="/opt/munbon/repo"),
            timeout=7200 if stage == "LOCAL-WRITE-ACT-1" else 2400,
        )
    except CommandExecutionError as exc:
        if exc.returncode == FAILURE_MANIFEST_EXIT_CODE:
            raise OrchestrationError(
                "stage_failure_manifest_publication_failed"
            ) from exc
        raise


def run_stage(
    stage: str,
    release_sha: str,
    frontend_sha: str,
    as_of_date: str | None = None,
    *,
    expected_machine_id: str | None = None,
) -> None:
    _run_stage(
        stage,
        release_sha,
        frontend_sha,
        as_of_date=as_of_date,
        execution_kind="canonical",
        expected_machine_id=expected_machine_id,
    )


def run_rehearsal_stage(
    stage: str,
    release_sha: str,
    frontend_sha: str,
    as_of_date: str | None = None,
) -> None:
    if stage not in REHEARSAL_STAGE_ORDER:
        raise OrchestrationError("stage_not_supported")
    _run_stage(
        stage,
        release_sha,
        frontend_sha,
        as_of_date=as_of_date,
        execution_kind="rehearsal",
    )


def run_all_stages(
    release_sha: str, frontend_sha: str, as_of_date: str | None = None
) -> None:
    for stage in STAGE_ORDER:
        run_stage(stage, release_sha, frontend_sha, as_of_date=as_of_date)


def _run_rc_phase(
    phase: str,
    release_sha: str,
    frontend_sha: str,
    dependency_sha256: str,
    guest_id: str,
    as_of_date: str,
    *,
    expected_machine_id: str,
) -> None:
    if phase not in {"preflight", "finalize"}:
        raise OrchestrationError("rc_phase_not_supported")
    if (
        not re.fullmatch(r"[0-9a-f]{40}", release_sha)
        or not re.fullmatch(r"[0-9a-f]{40}", frontend_sha)
        or not re.fullmatch(r"[0-9a-f]{64}", dependency_sha256)
        or not re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", guest_id)
        or not isinstance(expected_machine_id, str)
        or not re.fullmatch(r"[0-9a-f]{32}", expected_machine_id)
        or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", as_of_date)
    ):
        raise OrchestrationError("rc_phase_arguments_not_accepted")
    phase_argv = [
        "python3",
        "/opt/munbon/harness/run-stage-suite.py",
        "LOCAL-RC-1",
        "--rc-phase",
        phase,
        "--release-sha",
        release_sha,
        "--frontend-sha",
        frontend_sha,
        "--execution-kind",
        "canonical",
        "--dependency-sha256",
        dependency_sha256,
        "--guest-id",
        guest_id,
        "--expected-machine-id",
        expected_machine_id,
        "--as-of-date",
        as_of_date,
    ]
    try:
        _run_checked(
            f"rc_{phase}",
            build_guest_command(phase_argv, workdir="/opt/munbon/repo"),
            timeout=2400,
        )
    except CommandExecutionError as exc:
        if exc.returncode == FAILURE_MANIFEST_EXIT_CODE:
            raise OrchestrationError(
                f"rc_{phase}_failure_manifest_publication_failed"
            ) from exc
        raise


def _validated_rc_guest(
    release_sha: str,
    frontend_sha: str,
    dependency_sha256: str,
    guest_id: str,
) -> dict[str, str]:
    inventory = _run_checked(
        "rc_orb_inventory", ["orb", "list", "--format", "json"], timeout=30
    )
    identity = validate_rc_guest_identity(inventory, guest_id)
    provision_state_json = _run_checked(
        "rc_provision_state",
        build_guest_command(
            ["cat", "/var/lib/munbon-local-acceptance/provisioning/state.json"],
            user="root",
        ),
        timeout=30,
    )
    owner_json = _run_checked(
        "rc_machine_owner",
        build_guest_command(
            ["cat", "/var/lib/munbon-local-acceptance/owner.json"], user="root"
        ),
        timeout=30,
    )
    try:
        provision_state = json.loads(provision_state_json)
        owner = json.loads(owner_json)
        if not isinstance(provision_state, dict) or not isinstance(owner, dict):
            raise ValueError
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise OrchestrationError("rc_guest_identity_not_accepted") from exc
    if (
        provision_state.get("dependency_sha256") != dependency_sha256
        or owner.get("dependency_sha256") != dependency_sha256
    ):
        raise OrchestrationError("rc_dependency_identity_mismatch")
    validate_existing_guest(provision_state_json, owner_json)
    if (
        provision_state.get("release_sha") != release_sha
        or provision_state.get("frontend_sha") != frontend_sha
        or owner.get("release_sha") != release_sha
        or owner.get("frontend_sha") != frontend_sha
    ):
        raise OrchestrationError("rc_guest_identity_not_accepted")
    try:
        machine_id = _run_checked(
            "rc_guest_machine_id",
            build_guest_command(["cat", "/etc/machine-id"], user="root"),
            timeout=30,
        ).strip()
    except Exception as exc:
        raise OrchestrationError("rc_guest_machine_identity_mismatch") from exc
    if not re.fullmatch(r"[0-9a-f]{32}", machine_id):
        raise OrchestrationError("rc_guest_machine_identity_mismatch")
    second_inventory = _run_checked(
        "rc_orb_inventory", ["orb", "list", "--format", "json"], timeout=30
    )
    second_identity = validate_rc_guest_identity(second_inventory, guest_id)
    if second_identity != identity:
        raise OrchestrationError("rc_guest_machine_identity_mismatch")
    return {
        **identity,
        "dependency_sha256": dependency_sha256,
        "machine_id": machine_id,
    }


def _validate_rc_final_proof(
    destination: Path,
    final: object,
    stage_manifests: dict[str, dict],
) -> dict:
    expected_final = {
        "verdict": "PASS",
        "completed": list(STAGE_ORDER),
        "runtime_dark": True,
        "processes_stable": True,
        "readiness_green": True,
        "listeners_accepted": True,
        "immutable_history": True,
    }
    expected_proof_keys = {
        "processes",
        "dark_contract",
        "frontend_activation_gates",
        "readiness",
        "listeners",
        "persist_snapshot_sha256",
        "rate_state",
        "rate_minimum_elapsed_ms",
        "rate_snapshot_started_monotonic_ms",
        "rate_snapshot_completed_monotonic_ms",
        "write_activation_manifest_sha256",
    }
    dark_contract = {
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
    frontend_gates = {
        "control_plan_reads": False,
        "control_plan_evidence_reads": False,
        "water_planning_v2": False,
        "water_planning_submit": False,
    }
    application_ports = {3011, 3021, 3022, 3047}

    def invalid() -> None:
        raise OrchestrationError("rc_evidence_identity_mismatch")

    def process_identity(processes: object) -> list[tuple[str, str, int, int]]:
        if type(processes) is not list or len(processes) != len(RC_PROCESS_NAMES):
            invalid()
        identity = []
        for item in processes:
            if (
                type(item) is not dict
                or set(item)
                != {
                    "name",
                    "status",
                    "restarts",
                    "pid",
                    "memory_bytes",
                    "cpu_percent",
                }
                or type(item.get("name")) is not str
                or type(item.get("status")) is not str
                or item.get("status") != "online"
                or type(item.get("restarts")) is not int
                or item.get("restarts") < 0
                or type(item.get("pid")) is not int
                or item.get("pid") <= 0
                or type(item.get("memory_bytes")) is not int
                or item.get("memory_bytes") < 0
                or type(item.get("cpu_percent")) not in {int, float}
                or isinstance(item.get("cpu_percent"), bool)
                or not math.isfinite(item.get("cpu_percent"))
                or item.get("cpu_percent") < 0
                or item.get("name") not in RC_PROCESS_NAMES
            ):
                invalid()
            identity.append(
                (
                    item["name"],
                    item["status"],
                    item["restarts"],
                    item["pid"],
                )
            )
        if sorted(name for name, *_rest in identity) != sorted(RC_PROCESS_NAMES):
            invalid()
        return sorted(identity)

    def readiness_shape(readiness: object) -> None:
        if type(readiness) is not dict or set(readiness) != set(RC_PROCESS_NAMES):
            invalid()
        for value in readiness.values():
            if (
                type(value) is not dict
                or set(value) != {"status_code", "status", "checks"}
                or type(value.get("status_code")) is not int
                or value.get("status_code") != 200
                or value.get("status") != "ready"
                or type(value.get("checks")) is not dict
            ):
                invalid()

    def listener_shape(listeners: object) -> None:
        if type(listeners) is not list:
            invalid()
        seen: set[tuple[str, int]] = set()
        ports: list[int] = []
        for item in listeners:
            if (
                type(item) is not dict
                or set(item) != {"address", "port"}
                or item.get("address") not in {"127.0.0.1", "::1"}
                or type(item.get("port")) is not int
                or item.get("port") <= 0
            ):
                invalid()
            pair = (item["address"], item["port"])
            if pair in seen:
                invalid()
            seen.add(pair)
            ports.append(item["port"])
        if any(ports.count(port) != 1 for port in application_ports):
            invalid()

    try:
        if (
            type(final) is not dict
            or set(final) != {*expected_final, "proof"}
            or {key: final.get(key) for key in expected_final} != expected_final
            or type(final["proof"]) is not dict
            or set(final["proof"]) != expected_proof_keys
        ):
            invalid()
        proof = final["proof"]
        write_manifest = stage_manifests["LOCAL-WRITE-ACT-1"]
        persist_manifest = stage_manifests["LOCAL-PERSIST-ONLY-1"]
        write_steps = write_manifest["steps"]
        persist_steps = persist_manifest["steps"]
        write_principal = write_steps["operator_principal"]["subject"]
        persist_principal = persist_steps["operator_principal"]["subject"]
        baseline = write_steps["runtime_restoration"]
        persisted_digest = write_steps["persist_snapshot_sha256"]
        if (
            type(write_principal) is not str
            or not write_principal
            or type(persist_principal) is not str
            or not persist_principal
            or type(baseline) is not dict
            or type(persisted_digest) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", persisted_digest)
        ):
            invalid()
        baseline_processes = baseline["processes"]
        baseline_dark = baseline["dark_contract_after"]
        baseline_frontend = baseline["final_activation_gates"]
        baseline_readiness = baseline["readiness"]
        baseline_listeners = baseline["listeners"]
        baseline_identity = process_identity(baseline_processes)
        proof_identity = process_identity(proof["processes"])
        if proof_identity != baseline_identity:
            invalid()
        if (
            baseline_dark != dark_contract
            or proof["dark_contract"] != dark_contract
            or proof["dark_contract"] != baseline_dark
        ):
            invalid()
        if (
            baseline_frontend != frontend_gates
            or proof["frontend_activation_gates"] != frontend_gates
            or proof["frontend_activation_gates"] != baseline_frontend
        ):
            invalid()
        readiness_shape(baseline_readiness)
        readiness_shape(proof["readiness"])
        if proof["readiness"] != baseline_readiness:
            invalid()
        listener_shape(baseline_listeners)
        listener_shape(proof["listeners"])
        if proof["listeners"] != baseline_listeners:
            invalid()
        if (
            type(proof["persist_snapshot_sha256"]) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", proof["persist_snapshot_sha256"])
            or proof["persist_snapshot_sha256"] != persisted_digest
        ):
            invalid()
        allowed_rate_keys = {
            "bff-water-planning:rate:planning_depth.submit:"
            + hashlib.sha256(subject.encode("utf-8")).hexdigest()
            for subject in (persist_principal, write_principal)
        }
        write_rate_key = (
            "bff-water-planning:rate:planning_depth.submit:"
            + hashlib.sha256(write_principal.encode("utf-8")).hexdigest()
        )
        rate_reference = write_steps["rate_state_after_browser"]
        if (
            type(rate_reference) is not dict
            or set(rate_reference)
            != {
                "configured_window_ms",
                "minimum_elapsed_ms",
                "snapshot_completed_monotonic_ms",
                "snapshot",
            }
            or type(rate_reference["configured_window_ms"]) is not int
            or isinstance(rate_reference["configured_window_ms"], bool)
            or rate_reference["configured_window_ms"] <= 0
            or type(rate_reference["minimum_elapsed_ms"]) is not int
            or isinstance(rate_reference["minimum_elapsed_ms"], bool)
            or rate_reference["minimum_elapsed_ms"] < 0
            or type(rate_reference["snapshot_completed_monotonic_ms"]) is not int
            or isinstance(rate_reference["snapshot_completed_monotonic_ms"], bool)
            or rate_reference["snapshot_completed_monotonic_ms"] < 0
            or type(rate_reference["snapshot"]) is not dict
            or not set(rate_reference["snapshot"]).issubset(allowed_rate_keys)
            or write_rate_key not in rate_reference["snapshot"]
        ):
            invalid()
        configured_window_ms = rate_reference["configured_window_ms"]
        minimum_elapsed_ms = rate_reference["minimum_elapsed_ms"]
        snapshot_completed_monotonic_ms = rate_reference[
            "snapshot_completed_monotonic_ms"
        ]
        reference_rate_state = rate_reference["snapshot"]
        for key, row in reference_rate_state.items():
            if (
                type(key) is not str
                or key not in allowed_rate_keys
                or type(row) is not dict
                or set(row) != {"value", "ttl_ms"}
                or type(row["value"]) is not int
                or row["value"] <= 0
                or type(row["ttl_ms"]) is not int
                or row["ttl_ms"] <= 0
                or row["ttl_ms"] > configured_window_ms
            ):
                invalid()
        rate_minimum_elapsed_ms = proof["rate_minimum_elapsed_ms"]
        rate_snapshot_started_ms = proof["rate_snapshot_started_monotonic_ms"]
        rate_snapshot_completed_ms = proof["rate_snapshot_completed_monotonic_ms"]
        if (
            type(rate_minimum_elapsed_ms) is not int
            or isinstance(rate_minimum_elapsed_ms, bool)
            or rate_minimum_elapsed_ms < 0
            or type(rate_snapshot_started_ms) is not int
            or isinstance(rate_snapshot_started_ms, bool)
            or rate_snapshot_started_ms < snapshot_completed_monotonic_ms
            or type(rate_snapshot_completed_ms) is not int
            or isinstance(rate_snapshot_completed_ms, bool)
            or rate_snapshot_completed_ms < rate_snapshot_started_ms
        ):
            invalid()
        expected_rate_minimum_elapsed_ms = max(
            minimum_elapsed_ms,
            rate_snapshot_started_ms - snapshot_completed_monotonic_ms,
        )
        if rate_minimum_elapsed_ms != expected_rate_minimum_elapsed_ms:
            invalid()
        rate_state = proof["rate_state"]
        if type(rate_state) is not dict:
            invalid()
        for key, reference_row in reference_rate_state.items():
            if (
                key not in rate_state
                and reference_row["ttl_ms"] > rate_minimum_elapsed_ms
            ):
                invalid()
        for key, row in rate_state.items():
            if (
                type(key) is not str
                or key not in allowed_rate_keys
                or type(row) is not dict
                or set(row) != {"value", "ttl_ms"}
                or type(row["value"]) is not int
                or row["value"] <= 0
                or type(row["ttl_ms"]) is not int
                or row["ttl_ms"] <= 0
                or key not in reference_rate_state
                or row["value"] != reference_rate_state[key]["value"]
                or row["ttl_ms"] > configured_window_ms
                or row["ttl_ms"]
                > max(
                    0,
                    reference_rate_state[key]["ttl_ms"] - rate_minimum_elapsed_ms,
                )
            ):
                invalid()
        write_manifest_sha256 = _sha256_file(destination / "LOCAL-WRITE-ACT-1.json")
        if (
            type(proof["write_activation_manifest_sha256"]) is not str
            or not re.fullmatch(
                r"[0-9a-f]{64}", proof["write_activation_manifest_sha256"]
            )
            or proof["write_activation_manifest_sha256"] != write_manifest_sha256
        ):
            invalid()
        return proof
    except OrchestrationError:
        raise
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise OrchestrationError("rc_evidence_identity_mismatch") from exc


def finalize_rc_collection(
    destination: Path,
    *,
    release_sha: str,
    frontend_sha: str,
    dependency_sha256: str,
    guest_id: str,
    as_of_date: str,
    expected_machine_id: str | None = None,
) -> dict:
    stage_names = {f"{stage}.json" for stage in STAGE_ORDER}
    inner_names = {
        *stage_names,
        "stage-state.json",
        "RC-PREFLIGHT.json",
        "LOCAL-WRITE-UI-1-browser-result.json",
        "LOCAL-WRITE-ACT-1-browser-result.json",
        "LOCAL-GO-READ-1-live.png",
        "LOCAL-GO-READ-1-outage.png",
        "SHA256SUMS",
    }
    base_names = {*inner_names, "LOCAL-RC-1.json", "RC-SUMMARY.json"}
    final_names = {*base_names, "RC-SHA256SUMS", "RC-OUTER-SHA256SUMS"}
    if (
        not re.fullmatch(r"[0-9a-f]{40}", release_sha)
        or not re.fullmatch(r"[0-9a-f]{40}", frontend_sha)
        or not re.fullmatch(r"[0-9a-f]{64}", dependency_sha256)
        or not re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", guest_id)
        or not _is_canonical_date(as_of_date)
        or (
            expected_machine_id is not None
            and (
                not isinstance(expected_machine_id, str)
                or not re.fullmatch(r"[0-9a-f]{32}", expected_machine_id)
            )
        )
    ):
        raise OrchestrationError("rc_evidence_identity_mismatch")
    try:
        artifacts = tuple(destination.iterdir())
    except OSError as exc:
        raise OrchestrationError("rc_evidence_inventory_invalid") from exc
    if any(path.is_symlink() or not path.is_file() for path in artifacts):
        raise OrchestrationError("rc_evidence_inventory_invalid")
    artifact_names = {path.name for path in artifacts}
    if "OUTER-SHA256SUMS" in artifact_names:
        raise OrchestrationError("rc_evidence_inventory_invalid")
    if artifact_names != base_names and artifact_names != final_names:
        raise OrchestrationError("rc_evidence_inventory_invalid")

    def read_index(path: Path, expected_names: set[str]) -> tuple[str, dict[str, str]]:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise OrchestrationError("rc_evidence_inventory_invalid") from exc
        checksums: dict[str, str] = {}
        for line in text.splitlines():
            match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
            if match is None or match.group(2) in checksums:
                raise OrchestrationError("rc_evidence_inventory_invalid")
            checksums[match.group(2)] = match.group(1)
        if set(checksums) != expected_names:
            raise OrchestrationError("rc_evidence_inventory_invalid")
        for name, digest in checksums.items():
            if _sha256_file(destination / name) != digest:
                raise OrchestrationError("rc_evidence_checksum_mismatch")
        return text, checksums

    read_index(destination / "SHA256SUMS", base_names - {"SHA256SUMS"})
    try:
        state = json.loads(
            (destination / "stage-state.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise OrchestrationError("rc_evidence_inventory_invalid") from exc
    if (
        not isinstance(state, dict)
        or set(state) != {"release_sha", "frontend_sha", "harness_hashes", "completed"}
        or state.get("release_sha") != release_sha
        or state.get("frontend_sha") != frontend_sha
        or state.get("completed") != list(STAGE_ORDER)
        or not isinstance(state.get("harness_hashes"), dict)
        or set(state["harness_hashes"]) != set(EVIDENCE_HARNESS_ARTIFACTS)
        or not all(
            isinstance(name, str)
            and isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest)
            for name, digest in state["harness_hashes"].items()
        )
    ):
        raise OrchestrationError("rc_evidence_inventory_invalid")
    try:
        if state["harness_hashes"] != _host_harness_hashes():
            raise OrchestrationError("rc_evidence_identity_mismatch")
    except OrchestrationError:
        raise
    except OSError as exc:
        raise OrchestrationError("rc_evidence_identity_mismatch") from exc

    stage_manifests: dict[str, dict] = {}
    for stage in STAGE_ORDER:
        try:
            manifest = json.loads(
                (destination / f"{stage}.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise OrchestrationError("rc_evidence_inventory_invalid") from exc
        stage_release = (
            manifest.get("release_sha", manifest.get("backend_sha"))
            if isinstance(manifest, dict)
            else None
        )
        if (
            not isinstance(manifest, dict)
            or manifest.get("stage") != stage
            or manifest.get("verdict") != "PASS"
            or stage_release != release_sha
            or manifest.get("frontend_sha") != frontend_sha
        ):
            raise OrchestrationError("rc_evidence_inventory_invalid")
        stage_manifests[stage] = manifest

    expected_guest = {
        "name": MACHINE_NAME,
        "id": guest_id,
        "architecture": "arm64",
    }
    expected_preflight_checks = {
        "evidence_root_empty": True,
        "database_clean": True,
        "rate_state_clean": True,
        "actionable_commands": 0,
        "sources_clean": True,
        "runtime_dark": True,
    }
    expected_manifest = {
        "schema_version": 1,
        "stage": "LOCAL-RC-1",
        "verdict": "PASS",
        "release_sha": release_sha,
        "frontend_sha": frontend_sha,
        "dependency_sha256": dependency_sha256,
        "guest": expected_guest,
        "as_of_date": as_of_date,
        "preflight": {
            "verdict": "PASS",
            **expected_preflight_checks,
        },
        "final": {
            "verdict": "PASS",
            "completed": list(STAGE_ORDER),
            "runtime_dark": True,
            "processes_stable": True,
            "readiness_green": True,
            "listeners_accepted": True,
            "immutable_history": True,
        },
    }
    try:
        manifest = json.loads(
            (destination / "LOCAL-RC-1.json").read_text(encoding="utf-8")
        )
        summary = json.loads(
            (destination / "RC-SUMMARY.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise OrchestrationError("rc_evidence_inventory_invalid") from exc
    if not isinstance(manifest, dict):
        raise OrchestrationError("rc_evidence_identity_mismatch")
    preflight = manifest.get("preflight")
    record = preflight.get("record") if isinstance(preflight, dict) else None
    record_sha256 = (
        preflight.get("record_sha256") if isinstance(preflight, dict) else None
    )
    record_guest = record.get("guest") if isinstance(record, dict) else None
    if (
        not isinstance(record_guest, dict)
        or set(record_guest) != {"name", "id", "architecture", "machine_id"}
        or record_guest.get("name") != MACHINE_NAME
        or record_guest.get("id") != guest_id
        or record_guest.get("architecture") != "arm64"
        or not isinstance(record_guest.get("machine_id"), str)
        or not re.fullmatch(r"[0-9a-f]{32}", record_guest["machine_id"])
        or (
            expected_machine_id is not None
            and record_guest["machine_id"] != expected_machine_id
        )
    ):
        raise OrchestrationError("rc_evidence_identity_mismatch")
    expected_guest["machine_id"] = record_guest["machine_id"]
    expected_preflight_record = {
        "schema_version": 1,
        "phase": "preflight",
        "verdict": "PASS",
        "release_sha": release_sha,
        "frontend_sha": frontend_sha,
        "dependency_sha256": dependency_sha256,
        "guest": expected_guest,
        "as_of_date": as_of_date,
        "checks": expected_preflight_checks,
    }
    if (
        not isinstance(record, dict)
        or set(record) != {*expected_preflight_record, "captured_at"}
        or not isinstance(record.get("captured_at"), str)
        or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
            record["captured_at"],
        )
    ):
        raise OrchestrationError("rc_evidence_identity_mismatch")
    try:
        captured_at = datetime.strptime(
            record["captured_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise OrchestrationError("rc_evidence_identity_mismatch") from exc
    if captured_at != record["captured_at"]:
        raise OrchestrationError("rc_evidence_identity_mismatch")
    expected_preflight_record["captured_at"] = record["captured_at"]
    if record != expected_preflight_record:
        raise OrchestrationError("rc_evidence_identity_mismatch")
    try:
        record_bytes = (json.dumps(record, indent=2, sort_keys=True) + "\n").encode()
    except (TypeError, ValueError) as exc:
        raise OrchestrationError("rc_evidence_identity_mismatch") from exc
    if record_sha256 != hashlib.sha256(record_bytes).hexdigest():
        raise OrchestrationError("rc_evidence_identity_mismatch")
    try:
        preflight_bytes = (destination / "RC-PREFLIGHT.json").read_bytes()
        internal_record = json.loads(preflight_bytes.decode("utf-8"))
        internal_canonical = (
            json.dumps(internal_record, indent=2, sort_keys=True) + "\n"
        ).encode()
    except (
        OSError,
        UnicodeDecodeError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise OrchestrationError("rc_evidence_identity_mismatch") from exc
    if (
        internal_record != expected_preflight_record
        or preflight_bytes != internal_canonical
        or hashlib.sha256(preflight_bytes).hexdigest() != record_sha256
    ):
        raise OrchestrationError("rc_evidence_identity_mismatch")
    expected_rc_attempt = {
        "preflight_sha256": record_sha256,
        "dependency_sha256": dependency_sha256,
        "guest": expected_guest,
        "as_of_date": as_of_date,
    }
    for stage in STAGE_ORDER:
        if stage_manifests[stage].get("rc_attempt") != expected_rc_attempt:
            raise OrchestrationError("rc_evidence_identity_mismatch")
    expected_manifest["preflight"]["record"] = expected_preflight_record
    expected_manifest["preflight"]["record_sha256"] = record_sha256
    final_proof = _validate_rc_final_proof(
        destination,
        manifest.get("final"),
        stage_manifests,
    )
    expected_manifest["final"]["proof"] = final_proof
    expected_summary = {
        "schema_version": 1,
        "evidence_kind": "local_release_candidate",
        "acceptance": "LOCAL-RC-1",
        "acceptance_evidence": True,
        "campaign_ledger_eligible": False,
        "aws_actions_authorized": False,
        "release_sha": release_sha,
        "frontend_sha": frontend_sha,
        "dependency_sha256": dependency_sha256,
        "guest": expected_guest,
        "as_of_date": as_of_date,
        "passed": [*STAGE_ORDER, "LOCAL-RC-1"],
        "failed": [],
        "unreached": [],
        "verdict": "PASS",
    }
    if manifest != expected_manifest or summary != expected_summary:
        raise OrchestrationError("rc_evidence_identity_mismatch")

    if artifact_names == final_names:
        read_index(destination / "RC-SHA256SUMS", base_names)
        read_index(
            destination / "RC-OUTER-SHA256SUMS",
            final_names - {"RC-OUTER-SHA256SUMS"},
        )
        return summary

    rc_checksum_path = destination / "RC-SHA256SUMS"
    rc_checksum_path.write_text(
        "".join(
            f"{_sha256_file(path)}  {path.name}\n"
            for path in sorted(destination.iterdir())
            if path.name not in {"RC-SHA256SUMS", "RC-OUTER-SHA256SUMS"}
        ),
        encoding="utf-8",
    )
    rc_checksum_path.chmod(0o600)
    outer_path = destination / "RC-OUTER-SHA256SUMS"
    outer_path.write_text(
        "".join(
            f"{_sha256_file(path)}  {path.name}\n"
            for path in sorted(destination.iterdir())
            if path.name != outer_path.name
        ),
        encoding="utf-8",
    )
    outer_path.chmod(0o600)
    return summary


def finalize_rc_partial_failure_collection(
    destination: Path,
    *,
    release_sha: str,
    frontend_sha: str,
    dependency_sha256: str,
    guest_id: str,
    as_of_date: str,
    expected_machine_id: str | None = None,
) -> dict:
    """Finalize a bounded, non-authoritative RC failure bundle."""

    if (
        not isinstance(destination, Path)
        or not re.fullmatch(r"[0-9a-f]{40}", release_sha)
        or not re.fullmatch(r"[0-9a-f]{40}", frontend_sha)
        or not re.fullmatch(r"[0-9a-f]{64}", dependency_sha256)
        or not re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", guest_id)
        or not _is_canonical_date(as_of_date)
        or (
            expected_machine_id is not None
            and (
                not isinstance(expected_machine_id, str)
                or not re.fullmatch(r"[0-9a-f]{32}", expected_machine_id)
            )
        )
    ):
        raise OrchestrationError("rc_partial_evidence_identity_mismatch")

    try:
        artifacts = tuple(destination.iterdir())
    except OSError as exc:
        raise OrchestrationError("rc_partial_evidence_inventory_invalid") from exc
    if any(path.is_symlink() or not path.is_file() for path in artifacts):
        raise OrchestrationError("rc_partial_evidence_inventory_invalid")
    artifact_names = {path.name for path in artifacts}
    forbidden_names = {
        "OUTER-SHA256SUMS",
        "PARTIAL-OUTER-SHA256SUMS",
        "PARTIAL-SUMMARY.json",
        "REHEARSAL-SHA256SUMS",
        "REHEARSAL-SUMMARY.json",
        "REHEARSAL-OUTER-SHA256SUMS",
        "RC-SHA256SUMS",
        "RC-OUTER-SHA256SUMS",
        "RC-SUMMARY.json",
        "LOCAL-RC-1.json",
        "RC-PARTIAL-SHA256SUMS",
        "RC-PARTIAL-SUMMARY.json",
        "RC-PARTIAL-OUTER-SHA256SUMS",
    }
    if "SHA256SUMS" not in artifact_names or artifact_names & forbidden_names:
        raise OrchestrationError("rc_partial_evidence_inventory_invalid")

    try:
        checksum_lines = (
            (destination / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        )
    except OSError as exc:
        raise OrchestrationError("rc_partial_evidence_checksum_index_invalid") from exc
    checksums: dict[str, str] = {}
    for line in checksum_lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if match is None or match.group(2) in checksums:
            raise OrchestrationError("rc_partial_evidence_checksum_index_invalid")
        checksums[match.group(2)] = match.group(1)
    if set(checksums) != artifact_names - {"SHA256SUMS"}:
        raise OrchestrationError("rc_partial_evidence_inventory_invalid")
    for name, digest in checksums.items():
        try:
            actual_digest = _sha256_file(destination / name)
        except OSError as exc:
            raise OrchestrationError("rc_partial_evidence_checksum_mismatch") from exc
        if actual_digest != digest:
            raise OrchestrationError("rc_partial_evidence_checksum_mismatch")

    def read_json(name: str, code: str) -> dict:
        try:
            value = json.loads((destination / name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OrchestrationError(code) from exc
        if not isinstance(value, dict):
            raise OrchestrationError(code)
        return value

    expected_state_keys = {
        "release_sha",
        "frontend_sha",
        "harness_hashes",
        "completed",
    }
    state: dict | None = None
    completed: list[str]
    phase: str
    if "stage-state.json" not in artifact_names:
        phase = "preflight"
        completed = []
        expected_names = {"SHA256SUMS", "LOCAL-RC-1-failure.json"}
        if artifact_names != expected_names:
            if any(
                name == "stage-state.json"
                or any(
                    name == f"{stage}.json"
                    or name == f"{stage}-failure.json"
                    or name.startswith(f"{stage}-")
                    for stage in STAGE_ORDER
                )
                for name in artifact_names
            ):
                raise OrchestrationError("rc_partial_evidence_stage_sequence_invalid")
            raise OrchestrationError("rc_partial_evidence_inventory_invalid")
    else:
        state = read_json("stage-state.json", "rc_partial_evidence_state_invalid")
        if set(state) != expected_state_keys:
            raise OrchestrationError("rc_partial_evidence_state_invalid")
        if (
            state.get("release_sha") != release_sha
            or state.get("frontend_sha") != frontend_sha
        ):
            raise OrchestrationError("rc_partial_evidence_identity_mismatch")
        harness_hashes = state.get("harness_hashes")
        if (
            type(harness_hashes) is not dict
            or set(harness_hashes) != set(EVIDENCE_HARNESS_ARTIFACTS)
            or not all(
                type(name) is str
                and type(digest) is str
                and re.fullmatch(r"[0-9a-f]{64}", digest)
                for name, digest in harness_hashes.items()
            )
            or type(state.get("completed")) is not list
            or any(type(stage) is not str for stage in state["completed"])
        ):
            raise OrchestrationError("rc_partial_evidence_state_invalid")
        completed = state["completed"]
        if completed != list(STAGE_ORDER[: len(completed)]):
            raise OrchestrationError("rc_partial_evidence_stage_sequence_invalid")
        if len(completed) == len(STAGE_ORDER):
            phase = "finalize"
        elif len(completed) < len(STAGE_ORDER):
            phase = "stage"
        else:
            raise OrchestrationError("rc_partial_evidence_stage_sequence_invalid")
        if "RC-PREFLIGHT.json" not in artifact_names:
            raise OrchestrationError("rc_partial_evidence_identity_mismatch")
        try:
            if state["harness_hashes"] != _host_harness_hashes():
                raise OrchestrationError("rc_partial_evidence_identity_mismatch")
        except OrchestrationError:
            raise
        except OSError as exc:
            raise OrchestrationError("rc_partial_evidence_identity_mismatch") from exc

    def read_rc_preflight() -> dict[str, Any]:
        try:
            raw = (destination / "RC-PREFLIGHT.json").read_bytes()
            record = json.loads(raw.decode("utf-8"))
            canonical = (json.dumps(record, indent=2, sort_keys=True) + "\n").encode(
                "utf-8"
            )
        except (
            OSError,
            UnicodeDecodeError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise OrchestrationError("rc_partial_evidence_identity_mismatch") from exc
        record_guest = record.get("guest") if isinstance(record, dict) else None
        if (
            not isinstance(record_guest, dict)
            or set(record_guest) != {"name", "id", "architecture", "machine_id"}
            or record_guest.get("name") != MACHINE_NAME
            or record_guest.get("id") != guest_id
            or record_guest.get("architecture") != "arm64"
            or not isinstance(record_guest.get("machine_id"), str)
            or not re.fullmatch(r"[0-9a-f]{32}", record_guest["machine_id"])
            or (
                expected_machine_id is not None
                and record_guest["machine_id"] != expected_machine_id
            )
        ):
            raise OrchestrationError("rc_partial_evidence_identity_mismatch")
        expected = {
            "schema_version": 1,
            "phase": "preflight",
            "verdict": "PASS",
            "release_sha": release_sha,
            "frontend_sha": frontend_sha,
            "dependency_sha256": dependency_sha256,
            "guest": record_guest,
            "as_of_date": as_of_date,
            "checks": {
                "evidence_root_empty": True,
                "database_clean": True,
                "rate_state_clean": True,
                "actionable_commands": 0,
                "sources_clean": True,
                "runtime_dark": True,
            },
        }
        captured_at = record.get("captured_at") if isinstance(record, dict) else None
        if (
            not isinstance(record, dict)
            or set(record) != {*expected, "captured_at"}
            or not isinstance(captured_at, str)
            or not re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
                captured_at,
            )
            or record != {**expected, "captured_at": captured_at}
            or raw != canonical
            or len(raw) > 1024 * 1024
        ):
            raise OrchestrationError("rc_partial_evidence_identity_mismatch")
        try:
            if (
                datetime.strptime(captured_at, "%Y-%m-%dT%H:%M:%SZ").strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                != captured_at
            ):
                raise ValueError
        except ValueError as exc:
            raise OrchestrationError("rc_partial_evidence_identity_mismatch") from exc
        return record

    preflight_record: dict[str, Any] | None = None
    durable_guest: dict[str, str] | None = None
    expected_rc_attempt: dict[str, Any] | None = None
    if phase != "preflight":
        preflight_record = read_rc_preflight()
        durable_guest = preflight_record["guest"]
        preflight_bytes = (
            json.dumps(preflight_record, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        expected_rc_attempt = {
            "preflight_sha256": hashlib.sha256(preflight_bytes).hexdigest(),
            "dependency_sha256": dependency_sha256,
            "guest": durable_guest,
            "as_of_date": as_of_date,
        }

    failed_stage = (
        "LOCAL-RC-1"
        if phase == "preflight"
        else ("LOCAL-RC-1" if phase == "finalize" else STAGE_ORDER[len(completed)])
    )
    failure_name = f"{failed_stage}-failure.json"
    if failure_name not in artifact_names:
        raise OrchestrationError("rc_partial_evidence_stage_sequence_invalid")

    stage_manifest_names = {f"{stage}.json" for stage in STAGE_ORDER}
    stage_failure_names = {f"{stage}-failure.json" for stage in STAGE_ORDER}
    auxiliary_names = {
        "LOCAL-WRITE-UI-1-browser-result.json",
        "LOCAL-WRITE-ACT-1-browser-result.json",
        "LOCAL-GO-READ-1-live.png",
        "LOCAL-GO-READ-1-outage.png",
    }
    if phase == "preflight":
        expected_names = {"SHA256SUMS", failure_name}
        if artifact_names != expected_names:
            raise OrchestrationError("rc_partial_evidence_stage_sequence_invalid")
    else:
        allowed_auxiliary = set()
        if "LOCAL-WRITE-UI-1" in completed:
            allowed_auxiliary.add("LOCAL-WRITE-UI-1-browser-result.json")
        if "LOCAL-WRITE-ACT-1" in completed:
            allowed_auxiliary.add("LOCAL-WRITE-ACT-1-browser-result.json")
        if "LOCAL-GO-READ-1" in completed:
            allowed_auxiliary.update(
                {"LOCAL-GO-READ-1-live.png", "LOCAL-GO-READ-1-outage.png"}
            )
        failed_auxiliary = set()
        if phase == "stage":
            if failed_stage == "LOCAL-GO-READ-1":
                failed_auxiliary = {
                    name
                    for name in {
                        "LOCAL-GO-READ-1-live.png",
                        "LOCAL-GO-READ-1-outage.png",
                    }
                    if name in artifact_names
                }
                if failed_auxiliary not in (
                    set(),
                    {"LOCAL-GO-READ-1-live.png"},
                    {"LOCAL-GO-READ-1-live.png", "LOCAL-GO-READ-1-outage.png"},
                ):
                    raise OrchestrationError(
                        "rc_partial_evidence_stage_sequence_invalid"
                    )
            elif failed_stage == "LOCAL-WRITE-UI-1":
                name = "LOCAL-WRITE-UI-1-browser-result.json"
                if name in artifact_names:
                    failed_auxiliary.add(name)
            elif failed_stage == "LOCAL-WRITE-ACT-1":
                name = "LOCAL-WRITE-ACT-1-browser-result.json"
                if name in artifact_names:
                    failed_auxiliary.add(name)
        expected_names = {
            "SHA256SUMS",
            "stage-state.json",
            "RC-PREFLIGHT.json",
            failure_name,
            *(f"{stage}.json" for stage in completed),
            *allowed_auxiliary,
            *failed_auxiliary,
        }
        if phase == "finalize":
            expected_names.update(
                {f"{stage}.json" for stage in STAGE_ORDER[len(completed) :]}
            )
            expected_names.update(auxiliary_names)
        if artifact_names != expected_names:
            known_stage_artifact = any(
                name in stage_manifest_names
                or name in stage_failure_names
                or any(name.startswith(f"{stage}-") for stage in STAGE_ORDER)
                for name in artifact_names
            )
            if known_stage_artifact:
                raise OrchestrationError("rc_partial_evidence_stage_sequence_invalid")
            raise OrchestrationError("rc_partial_evidence_inventory_invalid")

    for stage in completed:
        manifest = read_json(f"{stage}.json", "rc_partial_evidence_manifest_invalid")
        manifest_release = manifest.get("release_sha", manifest.get("backend_sha"))
        if (
            manifest.get("stage") != stage
            or manifest.get("verdict") != "PASS"
            or manifest_release != release_sha
            or manifest.get("frontend_sha") != frontend_sha
        ):
            raise OrchestrationError("rc_partial_evidence_identity_mismatch")
        if (
            expected_rc_attempt is not None
            and manifest.get("rc_attempt") != expected_rc_attempt
        ):
            raise OrchestrationError("rc_partial_evidence_identity_mismatch")
    if phase == "finalize":
        for stage in STAGE_ORDER:
            if stage in completed:
                continue
            manifest = read_json(
                f"{stage}.json", "rc_partial_evidence_manifest_invalid"
            )
            manifest_release = manifest.get("release_sha", manifest.get("backend_sha"))
            if (
                manifest.get("stage") != stage
                or manifest.get("verdict") != "PASS"
                or manifest_release != release_sha
                or manifest.get("frontend_sha") != frontend_sha
            ):
                raise OrchestrationError("rc_partial_evidence_identity_mismatch")
            if (
                expected_rc_attempt is not None
                and manifest.get("rc_attempt") != expected_rc_attempt
            ):
                raise OrchestrationError("rc_partial_evidence_identity_mismatch")

    failure = read_json(failure_name, "rc_partial_evidence_manifest_invalid")
    if (
        failure.get("stage") != failed_stage
        or failure.get("verdict") != "FAIL"
        or failure.get("release_sha") != release_sha
        or failure.get("frontend_sha") != frontend_sha
        or not isinstance(failure.get("failed_gate"), str)
        or not failure["failed_gate"]
    ):
        if (
            failure.get("release_sha") != release_sha
            or failure.get("frontend_sha") != frontend_sha
        ):
            raise OrchestrationError("rc_partial_evidence_identity_mismatch")
        if failure.get("stage") != failed_stage:
            raise OrchestrationError("rc_partial_evidence_stage_sequence_invalid")
        raise OrchestrationError("rc_partial_evidence_manifest_invalid")
    if phase in {"preflight", "finalize"}:
        expected_phase = phase
        failure_guest = failure.get("guest")
        if phase == "preflight":
            if (
                not isinstance(failure_guest, dict)
                or set(failure_guest) != {"name", "id", "architecture", "machine_id"}
                or failure_guest.get("name") != MACHINE_NAME
                or failure_guest.get("id") != guest_id
                or failure_guest.get("architecture") != "arm64"
                or not isinstance(failure_guest.get("machine_id"), str)
                or not re.fullmatch(r"[0-9a-f]{32}", failure_guest["machine_id"])
                or (
                    expected_machine_id is not None
                    and failure_guest["machine_id"] != expected_machine_id
                )
            ):
                raise OrchestrationError("rc_partial_evidence_identity_mismatch")
            durable_guest = failure_guest
        if durable_guest is None:
            raise OrchestrationError("rc_partial_evidence_identity_mismatch")
        expected_guest = durable_guest
        if (
            failure.get("rc_phase") != expected_phase
            or failure.get("dependency_sha256") != dependency_sha256
            or failure.get("guest") != expected_guest
            or failure.get("as_of_date") != as_of_date
        ):
            raise OrchestrationError("rc_partial_evidence_identity_mismatch")
        if phase == "preflight":
            harness_hashes = failure.get("harness_hashes")
            if (
                type(harness_hashes) is not dict
                or set(harness_hashes) != set(EVIDENCE_HARNESS_ARTIFACTS)
                or not all(
                    type(name) is str
                    and type(digest) is str
                    and re.fullmatch(r"[0-9a-f]{64}", digest)
                    for name, digest in harness_hashes.items()
                )
            ):
                raise OrchestrationError("rc_partial_evidence_identity_mismatch")
            try:
                if harness_hashes != _host_harness_hashes():
                    raise OrchestrationError("rc_partial_evidence_identity_mismatch")
            except OrchestrationError:
                raise
            except OSError as exc:
                raise OrchestrationError(
                    "rc_partial_evidence_identity_mismatch"
                ) from exc
    if phase == "stage" and (
        expected_rc_attempt is None or failure.get("rc_attempt") != expected_rc_attempt
    ):
        raise OrchestrationError("rc_partial_evidence_identity_mismatch")

    summary = {
        "schema_version": 1,
        "evidence_kind": "local_release_candidate_partial_failure",
        "acceptance": "LOCAL-RC-1",
        "acceptance_evidence": False,
        "campaign_ledger_eligible": False,
        "aws_actions_authorized": False,
        "release_sha": release_sha,
        "frontend_sha": frontend_sha,
        "dependency_sha256": dependency_sha256,
        "guest": durable_guest,
        "as_of_date": as_of_date,
        "phase": phase,
        "passed": list(completed),
        "failed": [failed_stage],
        "failed_gate": failure["failed_gate"],
        "unreached": (
            list(STAGE_ORDER)
            if phase == "preflight"
            else (
                [*STAGE_ORDER[len(completed) + 1 :], "LOCAL-RC-1"]
                if phase == "stage"
                else []
            )
        ),
        "verdict": "FAIL",
    }
    checksum_path = destination / "SHA256SUMS"
    partial_checksum_path = destination / "RC-PARTIAL-SHA256SUMS"
    checksum_path.rename(partial_checksum_path)
    partial_checksum_path.chmod(0o600)
    summary_path = destination / "RC-PARTIAL-SUMMARY.json"
    summary_path.write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    summary_path.chmod(0o600)
    outer_path = destination / "RC-PARTIAL-OUTER-SHA256SUMS"
    outer_path.write_text(
        "".join(
            f"{_sha256_file(path)}  {path.name}\n"
            for path in sorted(destination.iterdir())
            if path.name != outer_path.name
        ),
        encoding="utf-8",
    )
    outer_path.chmod(0o600)
    return summary


def finalize_evidence_collection(destination: Path) -> dict:
    stage_names = {f"{stage}.json" for stage in STAGE_ORDER}
    inner_names = {
        *stage_names,
        "stage-state.json",
        "LOCAL-WRITE-UI-1-browser-result.json",
        "LOCAL-WRITE-ACT-1-browser-result.json",
        "LOCAL-GO-READ-1-live.png",
        "LOCAL-GO-READ-1-outage.png",
        "SHA256SUMS",
    }
    outer_name = "OUTER-SHA256SUMS"
    try:
        artifacts = tuple(destination.iterdir())
    except OSError as exc:
        raise OrchestrationError("evidence_inventory_invalid") from exc
    if any(path.is_symlink() or not path.is_file() for path in artifacts):
        raise OrchestrationError("evidence_inventory_invalid")
    artifact_names = {path.name for path in artifacts}
    if artifact_names != inner_names and artifact_names != {
        *inner_names,
        outer_name,
    }:
        raise OrchestrationError("evidence_inventory_invalid")

    try:
        checksum_lines = (
            (destination / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        )
    except OSError as exc:
        raise OrchestrationError("evidence_checksum_index_invalid") from exc
    expected_index_names = inner_names - {"SHA256SUMS"}
    checksums: dict[str, str] = {}
    for line in checksum_lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if match is None or match.group(2) in checksums:
            raise OrchestrationError("evidence_checksum_index_invalid")
        digest, name = match.groups()
        checksums[name] = digest
    if set(checksums) != expected_index_names:
        raise OrchestrationError("evidence_inventory_invalid")
    for name, digest in checksums.items():
        if _sha256_file(destination / name) != digest:
            raise OrchestrationError("evidence_checksum_mismatch")

    try:
        state = json.loads(
            (destination / "stage-state.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise OrchestrationError("evidence_state_invalid") from exc
    if (
        not isinstance(state, dict)
        or set(state) != {"release_sha", "frontend_sha", "harness_hashes", "completed"}
        or not re.fullmatch(r"[0-9a-f]{40}", state.get("release_sha", ""))
        or not re.fullmatch(r"[0-9a-f]{40}", state.get("frontend_sha", ""))
        or state.get("completed") != list(STAGE_ORDER)
        or not isinstance(state.get("harness_hashes"), dict)
        or set(state["harness_hashes"]) != set(EVIDENCE_HARNESS_ARTIFACTS)
        or not all(
            isinstance(name, str)
            and isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest)
            for name, digest in state["harness_hashes"].items()
        )
    ):
        raise OrchestrationError("evidence_state_invalid")

    for stage in STAGE_ORDER:
        try:
            manifest = json.loads(
                (destination / f"{stage}.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise OrchestrationError("evidence_manifest_invalid") from exc
        release_sha = (
            manifest.get("release_sha", manifest.get("backend_sha"))
            if isinstance(manifest, dict)
            else None
        )
        frontend_sha = (
            manifest.get("frontend_sha") if isinstance(manifest, dict) else None
        )
        if (
            not isinstance(manifest, dict)
            or manifest.get("stage") != stage
            or manifest.get("verdict") != "PASS"
            or release_sha != state["release_sha"]
            or frontend_sha != state["frontend_sha"]
        ):
            raise OrchestrationError("evidence_manifest_invalid")

    outer_path = destination / outer_name
    outer_path.write_text(
        "".join(
            f"{_sha256_file(path)}  {path.name}\n"
            for path in sorted(destination.iterdir())
            if path.name != outer_name
        ),
        encoding="utf-8",
    )
    outer_path.chmod(0o600)
    return state


def finalize_rehearsal_collection(destination: Path) -> dict:
    stage_names = {f"{stage}.json" for stage in REHEARSAL_STAGE_ORDER}
    indexed_names = {*stage_names, "stage-state.json"}
    raw_index_name = "SHA256SUMS"
    rehearsal_index_name = "REHEARSAL-SHA256SUMS"
    summary_name = "REHEARSAL-SUMMARY.json"
    outer_name = "REHEARSAL-OUTER-SHA256SUMS"
    try:
        artifacts = tuple(destination.iterdir())
    except OSError as exc:
        raise OrchestrationError("rehearsal_evidence_inventory_invalid") from exc
    if any(path.is_symlink() or not path.is_file() for path in artifacts):
        raise OrchestrationError("rehearsal_evidence_inventory_invalid")
    artifact_names = {path.name for path in artifacts}
    initial_names = {*indexed_names, raw_index_name}
    finalized_names = {
        *indexed_names,
        rehearsal_index_name,
        summary_name,
        outer_name,
    }
    if artifact_names == initial_names:
        checksum_path = destination / raw_index_name
    elif artifact_names == finalized_names:
        checksum_path = destination / rehearsal_index_name
    else:
        raise OrchestrationError("rehearsal_evidence_inventory_invalid")

    try:
        checksum_lines = checksum_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise OrchestrationError("rehearsal_evidence_checksum_index_invalid") from exc
    checksums: dict[str, str] = {}
    for line in checksum_lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if match is None or match.group(2) in checksums:
            raise OrchestrationError("rehearsal_evidence_checksum_index_invalid")
        digest, name = match.groups()
        checksums[name] = digest
    if set(checksums) != indexed_names:
        raise OrchestrationError("rehearsal_evidence_inventory_invalid")
    for name, digest in checksums.items():
        if _sha256_file(destination / name) != digest:
            raise OrchestrationError("rehearsal_evidence_checksum_mismatch")

    try:
        state = json.loads(
            (destination / "stage-state.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise OrchestrationError("rehearsal_evidence_state_invalid") from exc
    if (
        not isinstance(state, dict)
        or set(state)
        != {
            "release_sha",
            "frontend_sha",
            "harness_hashes",
            "completed",
            "execution_kind",
            "machine",
            "acceptance_evidence",
            "dependency_sha256",
            "as_of_date",
        }
        or not re.fullmatch(r"[0-9a-f]{40}", state.get("release_sha", ""))
        or not re.fullmatch(r"[0-9a-f]{40}", state.get("frontend_sha", ""))
        or state.get("completed") != list(REHEARSAL_STAGE_ORDER)
        or state.get("execution_kind") != "rehearsal"
        or state.get("machine") != REHEARSAL_MACHINE_NAME
        or state.get("acceptance_evidence") is not False
        or not re.fullmatch(r"[0-9a-f]{64}", state.get("dependency_sha256", ""))
        or not _is_canonical_date(state.get("as_of_date"))
        or not isinstance(state.get("harness_hashes"), dict)
        or set(state["harness_hashes"]) != set(EVIDENCE_HARNESS_ARTIFACTS)
        or not all(
            isinstance(name, str)
            and isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest)
            for name, digest in state["harness_hashes"].items()
        )
    ):
        raise OrchestrationError("rehearsal_evidence_state_invalid")

    for stage in REHEARSAL_STAGE_ORDER:
        try:
            manifest = json.loads(
                (destination / f"{stage}.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise OrchestrationError("rehearsal_evidence_manifest_invalid") from exc
        release_sha = (
            manifest.get("release_sha", manifest.get("backend_sha"))
            if isinstance(manifest, dict)
            else None
        )
        if (
            not isinstance(manifest, dict)
            or manifest.get("stage") != stage
            or manifest.get("verdict") != "PASS"
            or release_sha != state["release_sha"]
            or manifest.get("frontend_sha") != state["frontend_sha"]
        ):
            raise OrchestrationError("rehearsal_evidence_manifest_invalid")

    summary = {
        "schema_version": 1,
        "evidence_kind": "non_authoritative_rehearsal",
        "execution_kind": "rehearsal",
        "acceptance_evidence": False,
        "release_sha": state["release_sha"],
        "frontend_sha": state["frontend_sha"],
        "harness_hashes": state["harness_hashes"],
        "machine": REHEARSAL_MACHINE_NAME,
        "dependency_sha256": state["dependency_sha256"],
        "as_of_date": state["as_of_date"],
        "passed": list(REHEARSAL_STAGE_ORDER),
        "failed": [],
        "unreached": list(STAGE_ORDER[len(REHEARSAL_STAGE_ORDER) :]),
    }
    if checksum_path.name == raw_index_name:
        checksum_path.rename(destination / rehearsal_index_name)
    summary_path = destination / summary_name
    summary_path.write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    summary_path.chmod(0o600)
    outer_path = destination / outer_name
    outer_path.write_text(
        "".join(
            f"{_sha256_file(path)}  {path.name}\n"
            for path in sorted(destination.iterdir())
            if path.name != outer_name
        ),
        encoding="utf-8",
    )
    outer_path.chmod(0o600)
    return summary


def finalize_partial_failure_collection(
    destination: Path, *, execution_kind: str = "canonical"
) -> dict:
    if execution_kind not in {"canonical", "rehearsal"}:
        raise OrchestrationError("execution_kind_not_accepted")
    outer_name = "PARTIAL-OUTER-SHA256SUMS"
    summary_name = "PARTIAL-SUMMARY.json"
    try:
        artifacts = tuple(destination.iterdir())
    except OSError as exc:
        raise OrchestrationError("partial_evidence_inventory_invalid") from exc
    if any(path.is_symlink() or not path.is_file() for path in artifacts):
        raise OrchestrationError("partial_evidence_inventory_invalid")
    artifact_names = {path.name for path in artifacts}
    if (
        "SHA256SUMS" not in artifact_names
        or "stage-state.json" not in artifact_names
        or outer_name in artifact_names
        or summary_name in artifact_names
    ):
        raise OrchestrationError("partial_evidence_inventory_invalid")

    try:
        checksum_lines = (
            (destination / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        )
    except OSError as exc:
        raise OrchestrationError("partial_evidence_checksum_index_invalid") from exc
    checksums: dict[str, str] = {}
    for line in checksum_lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if match is None or match.group(2) in checksums:
            raise OrchestrationError("partial_evidence_checksum_index_invalid")
        digest, name = match.groups()
        checksums[name] = digest
    expected_index_names = artifact_names - {"SHA256SUMS", outer_name}
    if set(checksums) != expected_index_names:
        raise OrchestrationError("partial_evidence_inventory_invalid")
    for name, digest in checksums.items():
        if _sha256_file(destination / name) != digest:
            raise OrchestrationError("partial_evidence_checksum_mismatch")

    try:
        state = json.loads(
            (destination / "stage-state.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise OrchestrationError("partial_evidence_state_invalid") from exc
    state_names = {"release_sha", "frontend_sha", "harness_hashes", "completed"}
    if execution_kind == "rehearsal":
        state_names.update(
            {
                "execution_kind",
                "machine",
                "acceptance_evidence",
                "dependency_sha256",
                "as_of_date",
            }
        )
    if (
        not isinstance(state, dict)
        or set(state) != state_names
        or not re.fullmatch(r"[0-9a-f]{40}", state.get("release_sha", ""))
        or not re.fullmatch(r"[0-9a-f]{40}", state.get("frontend_sha", ""))
        or not isinstance(state.get("completed"), list)
        or len(state["completed"]) >= len(STAGE_ORDER)
        or state["completed"] != list(STAGE_ORDER[: len(state["completed"])])
        or not isinstance(state.get("harness_hashes"), dict)
        or set(state["harness_hashes"]) != set(EVIDENCE_HARNESS_ARTIFACTS)
        or not all(
            isinstance(name, str)
            and isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest)
            for name, digest in state["harness_hashes"].items()
        )
        or (
            execution_kind == "rehearsal"
            and (
                state.get("execution_kind") != "rehearsal"
                or state.get("machine") != REHEARSAL_MACHINE_NAME
                or state.get("acceptance_evidence") is not False
                or not re.fullmatch(r"[0-9a-f]{64}", state.get("dependency_sha256", ""))
                or not _is_canonical_date(state.get("as_of_date"))
            )
        )
    ):
        raise OrchestrationError("partial_evidence_state_invalid")

    completed = state["completed"]
    failed_stage = STAGE_ORDER[len(completed)]
    unreached_stages = STAGE_ORDER[len(completed) + 1 :]
    if any(
        name == f"{stage}.json" or name.startswith(f"{stage}-")
        for name in artifact_names
        for stage in unreached_stages
    ):
        raise OrchestrationError("partial_evidence_stage_sequence_invalid")
    expected_manifests = {
        *(f"{stage}.json" for stage in completed),
        f"{failed_stage}-failure.json",
    }
    actual_manifests = {
        name
        for name in artifact_names
        if any(
            name in {f"{stage}.json", f"{stage}-failure.json"} for stage in STAGE_ORDER
        )
    }
    if actual_manifests != expected_manifests:
        raise OrchestrationError("partial_evidence_stage_sequence_invalid")

    for stage in completed:
        try:
            manifest = json.loads(
                (destination / f"{stage}.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise OrchestrationError("partial_evidence_manifest_invalid") from exc
        release_sha = (
            manifest.get("release_sha", manifest.get("backend_sha"))
            if isinstance(manifest, dict)
            else None
        )
        frontend_sha = (
            manifest.get("frontend_sha") if isinstance(manifest, dict) else None
        )
        if (
            not isinstance(manifest, dict)
            or manifest.get("stage") != stage
            or manifest.get("verdict") != "PASS"
            or release_sha != state["release_sha"]
            or frontend_sha != state["frontend_sha"]
        ):
            raise OrchestrationError("partial_evidence_manifest_invalid")

    try:
        failure = json.loads(
            (destination / f"{failed_stage}-failure.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise OrchestrationError("partial_evidence_manifest_invalid") from exc
    if (
        not isinstance(failure, dict)
        or failure.get("stage") != failed_stage
        or failure.get("verdict") != "FAIL"
        or failure.get("release_sha") != state["release_sha"]
        or failure.get("frontend_sha") != state["frontend_sha"]
        or not isinstance(failure.get("failed_gate"), str)
        or not failure["failed_gate"]
        or (
            execution_kind == "rehearsal"
            and failure.get("as_of_date") != state["as_of_date"]
        )
    ):
        raise OrchestrationError("partial_evidence_manifest_invalid")

    summary = {
        "acceptance_evidence": False,
        "release_sha": state["release_sha"],
        "frontend_sha": state["frontend_sha"],
        "harness_hashes": state["harness_hashes"],
        "completed": completed,
        "failed_stage": failed_stage,
        "failed_gate": failure["failed_gate"],
        "passed": len(completed),
        "failed": 1,
        "unreached": len(STAGE_ORDER) - len(completed) - 1,
    }
    if execution_kind == "rehearsal":
        summary.update(
            {
                "execution_kind": "rehearsal",
                "machine": REHEARSAL_MACHINE_NAME,
                "dependency_sha256": state["dependency_sha256"],
                "as_of_date": state["as_of_date"],
            }
        )
    summary_path = destination / summary_name
    summary_path.write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    summary_path.chmod(0o600)
    outer_path = destination / outer_name
    outer_path.write_text(
        "".join(
            f"{_sha256_file(path)}  {path.name}\n"
            for path in sorted(destination.iterdir())
            if path.name != outer_name
        ),
        encoding="utf-8",
    )
    outer_path.chmod(0o600)
    return summary


def finalize_rehearsal_partial_failure_collection(destination: Path) -> dict:
    try:
        state = json.loads(
            (destination / "stage-state.json").read_text(encoding="utf-8")
        )
        completed = state["completed"]
        if (
            not isinstance(completed, list)
            or len(completed) >= len(REHEARSAL_STAGE_ORDER)
            or completed != list(REHEARSAL_STAGE_ORDER[: len(completed)])
        ):
            raise ValueError
        failed_stage = REHEARSAL_STAGE_ORDER[len(completed)]
        failure = json.loads(
            (destination / f"{failed_stage}-failure.json").read_text(encoding="utf-8")
        )
        if failure.get("acceptance_evidence") is not False:
            raise ValueError
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise OrchestrationError("rehearsal_partial_evidence_not_accepted") from exc
    summary = finalize_partial_failure_collection(
        destination, execution_kind="rehearsal"
    )
    (destination / "PARTIAL-OUTER-SHA256SUMS").unlink()
    (destination / "SHA256SUMS").rename(destination / "REHEARSAL-SHA256SUMS")
    summary["evidence_kind"] = "non_authoritative_rehearsal"
    summary_path = destination / "PARTIAL-SUMMARY.json"
    summary_path.write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    summary_path.chmod(0o600)
    outer_path = destination / "REHEARSAL-PARTIAL-OUTER-SHA256SUMS"
    outer_path.write_text(
        "".join(
            f"{_sha256_file(path)}  {path.name}\n"
            for path in sorted(destination.iterdir())
            if path.name != outer_path.name
        ),
        encoding="utf-8",
    )
    outer_path.chmod(0o600)
    return summary


def _collect_guest_evidence(
    destination: Path,
    *,
    guest_command: Callable[..., list[str]],
    archive_name: str,
    stream_code: str,
    extract_code: str,
    destination_error: str,
    finalizer: Callable[[Path], dict | None],
    expected_machine_id: str | None = None,
) -> dict | None:
    if destination.exists():
        raise OrchestrationError(destination_error)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent)
    )
    try:
        archive = temporary / archive_name
        if expected_machine_id is None:
            archive_argv = [
                "tar",
                "-C",
                "/var/lib/munbon-local-acceptance/evidence",
                "-czf",
                "-",
                ".",
            ]
        elif isinstance(expected_machine_id, str) and re.fullmatch(
            r"[0-9a-f]{32}", expected_machine_id
        ):
            archive_argv = [
                "sh",
                "-ceu",
                'test "$(cat /etc/machine-id)" = "$1"; shift; exec "$@"',
                "rc-archive-guard",
                expected_machine_id,
                "tar",
                "-C",
                "/var/lib/munbon-local-acceptance/evidence",
                "-czf",
                "-",
                ".",
            ]
        else:
            raise OrchestrationError(f"{stream_code}_failed")
        try:
            with archive.open("wb") as stream:
                result = subprocess.run(
                    guest_command(archive_argv, user="root"),
                    stdout=stream,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=120,
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OrchestrationError(f"{stream_code}_failed") from exc
        if result.returncode != 0:
            raise OrchestrationError(f"{stream_code}_failed")
        print(f"PASS {stream_code}")
        _run_checked(
            extract_code,
            ["tar", "-xzf", str(archive), "-C", str(temporary)],
            timeout=120,
        )
        archive.unlink()
        result_summary = finalizer(temporary)
        temporary.rename(destination)
        return result_summary
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def collect_evidence(destination: Path) -> None:
    _collect_guest_evidence(
        destination,
        guest_command=build_guest_command,
        archive_name="local-acceptance-evidence.tar.gz",
        stream_code="evidence_stream",
        extract_code="evidence_extract",
        destination_error="evidence_destination_exists",
        finalizer=finalize_evidence_collection,
    )


def collect_rc(
    destination: Path,
    release_sha: str,
    frontend_sha: str,
    dependency_sha256: str,
    guest_id: str,
    as_of_date: str,
    *,
    expected_machine_id: str | None = None,
) -> dict:
    if destination.exists():
        raise OrchestrationError("rc_evidence_destination_exists")
    owner = _validated_rc_guest(release_sha, frontend_sha, dependency_sha256, guest_id)
    if expected_machine_id is not None and (
        not isinstance(expected_machine_id, str)
        or not re.fullmatch(r"[0-9a-f]{32}", expected_machine_id)
        or owner.get("machine_id") != expected_machine_id
    ):
        raise OrchestrationError("rc_evidence_identity_mismatch")
    archive_machine_id = expected_machine_id or owner["machine_id"]

    def finalize_bound_rc(temporary: Path) -> dict:
        summary = finalize_rc_collection(
            temporary,
            release_sha=release_sha,
            frontend_sha=frontend_sha,
            dependency_sha256=dependency_sha256,
            guest_id=guest_id,
            as_of_date=as_of_date,
            expected_machine_id=archive_machine_id,
        )
        current_owner = _validated_rc_guest(
            release_sha, frontend_sha, dependency_sha256, guest_id
        )
        if current_owner != owner:
            raise OrchestrationError("rc_evidence_identity_mismatch")
        return summary

    summary = _collect_guest_evidence(
        destination,
        guest_command=build_guest_command,
        archive_name="local-rc-evidence.tar.gz",
        stream_code="rc_evidence_stream",
        extract_code="rc_evidence_extract",
        destination_error="rc_evidence_destination_exists",
        finalizer=finalize_bound_rc,
        expected_machine_id=archive_machine_id,
    )
    assert isinstance(summary, dict)
    return summary


def collect_rc_partial_failure(
    destination: Path,
    release_sha: str,
    frontend_sha: str,
    dependency_sha256: str,
    guest_id: str,
    as_of_date: str,
) -> dict:
    if destination.exists():
        raise OrchestrationError("rc_partial_evidence_destination_exists")
    owner = _validated_rc_guest(release_sha, frontend_sha, dependency_sha256, guest_id)

    def finalize_bound_rc_partial(temporary: Path) -> dict:
        summary = finalize_rc_partial_failure_collection(
            temporary,
            release_sha=release_sha,
            frontend_sha=frontend_sha,
            dependency_sha256=dependency_sha256,
            guest_id=guest_id,
            as_of_date=as_of_date,
            expected_machine_id=owner["machine_id"],
        )
        current_owner = _validated_rc_guest(
            release_sha, frontend_sha, dependency_sha256, guest_id
        )
        if current_owner != owner:
            raise OrchestrationError("rc_partial_evidence_identity_mismatch")
        return summary

    summary = _collect_guest_evidence(
        destination,
        guest_command=build_guest_command,
        archive_name="local-rc-partial-failure-evidence.tar.gz",
        stream_code="rc_partial_evidence_stream",
        extract_code="rc_partial_evidence_extract",
        destination_error="rc_partial_evidence_destination_exists",
        finalizer=finalize_bound_rc_partial,
        expected_machine_id=owner["machine_id"],
    )
    assert isinstance(summary, dict)
    return summary


def run_rc(
    release_sha: str,
    frontend_sha: str,
    dependency_sha256: str,
    guest_id: str,
    destination: Path,
    as_of_date: str,
) -> dict:
    if (
        not isinstance(destination, Path)
        or not isinstance(release_sha, str)
        or not re.fullmatch(r"[0-9a-f]{40}", release_sha)
        or not isinstance(frontend_sha, str)
        or not re.fullmatch(r"[0-9a-f]{40}", frontend_sha)
        or not isinstance(dependency_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", dependency_sha256)
        or not isinstance(guest_id, str)
        or not re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", guest_id)
        or not _is_canonical_date(as_of_date)
    ):
        raise OrchestrationError("rc_arguments_not_accepted")
    if destination.exists():
        raise OrchestrationError("rc_evidence_destination_exists")
    pinned_guest = _validated_rc_guest(
        release_sha, frontend_sha, dependency_sha256, guest_id
    )
    if (
        type(pinned_guest) is not dict
        or not isinstance(pinned_guest.get("machine_id"), str)
        or not re.fullmatch(r"[0-9a-f]{32}", pinned_guest["machine_id"])
    ):
        raise OrchestrationError("rc_guest_machine_identity_mismatch")

    def assert_pinned_guest() -> None:
        try:
            current_guest = _validated_rc_guest(
                release_sha, frontend_sha, dependency_sha256, guest_id
            )
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:
            raise OrchestrationError("rc_guest_machine_identity_mismatch") from exc
        if current_guest != pinned_guest:
            raise OrchestrationError("rc_guest_machine_identity_mismatch")

    def run_pinned(operation: Callable[[], Any], *, prechecked: bool = False) -> Any:
        if not prechecked:
            assert_pinned_guest()
        try:
            result = operation()
        except BaseException as primary:
            try:
                assert_pinned_guest()
            except BaseException as postcheck_error:
                if isinstance(primary, (KeyboardInterrupt, SystemExit)):
                    raise primary
                if isinstance(postcheck_error, (KeyboardInterrupt, SystemExit)):
                    raise postcheck_error from primary
                try:
                    postcheck_code = str(postcheck_error)
                    if not re.fullmatch(r"[a-z][a-z0-9_]{0,127}", postcheck_code):
                        postcheck_code = "rc_guest_machine_identity_mismatch"
                    primary.identity_postcheck_error = postcheck_code
                except BaseException:
                    pass
                raise primary
            raise
        assert_pinned_guest()
        return result

    run_pinned(
        lambda: _run_rc_phase(
            "preflight",
            release_sha,
            frontend_sha,
            dependency_sha256,
            guest_id,
            as_of_date,
            expected_machine_id=pinned_guest["machine_id"],
        ),
        prechecked=True,
    )
    for stage in STAGE_ORDER:
        run_pinned(
            lambda stage=stage: run_stage(
                stage,
                release_sha,
                frontend_sha,
                as_of_date=as_of_date,
                expected_machine_id=pinned_guest["machine_id"],
            )
        )
    run_pinned(
        lambda: _run_rc_phase(
            "finalize",
            release_sha,
            frontend_sha,
            dependency_sha256,
            guest_id,
            as_of_date,
            expected_machine_id=pinned_guest["machine_id"],
        )
    )
    return run_pinned(
        lambda: collect_rc(
            destination,
            release_sha,
            frontend_sha,
            dependency_sha256,
            guest_id,
            as_of_date,
            expected_machine_id=pinned_guest["machine_id"],
        )
    )


def _validated_rehearsal_owner(release_sha: str, frontend_sha: str) -> dict:
    if _rehearsal_machine_state() != "ready":
        raise OrchestrationError("machine_not_ready")
    provision_state = _run_checked(
        "rehearsal_collection_provision_state",
        build_rehearsal_guest_command(
            ["cat", "/var/lib/munbon-local-acceptance/provisioning/state.json"],
            user="root",
        ),
        timeout=30,
    )
    owner_json = _run_checked(
        "rehearsal_collection_owner",
        build_rehearsal_guest_command(
            ["cat", "/var/lib/munbon-local-acceptance/owner.json"], user="root"
        ),
        timeout=30,
    )
    validate_stage_guest(
        provision_state,
        owner_json,
        release_sha,
        frontend_sha,
        execution_kind="rehearsal",
    )
    return json.loads(owner_json)


def _validate_rehearsal_summary_owner(
    summary: dict, owner: dict, as_of_date: str
) -> None:
    if (
        summary.get("machine") != owner["machine"]
        or summary.get("release_sha") != owner["release_sha"]
        or summary.get("frontend_sha") != owner["frontend_sha"]
        or summary.get("dependency_sha256") != owner["dependency_sha256"]
        or summary.get("as_of_date") != as_of_date
        or summary.get("execution_kind") != "rehearsal"
        or summary.get("acceptance_evidence") is not False
    ):
        raise OrchestrationError("rehearsal_evidence_owner_mismatch")


def collect_rehearsal(
    destination: Path, release_sha: str, frontend_sha: str, as_of_date: str
) -> dict:
    if destination.exists():
        raise OrchestrationError("rehearsal_evidence_destination_exists")
    owner = _validated_rehearsal_owner(release_sha, frontend_sha)

    def finalize_bound_rehearsal(temporary: Path) -> dict:
        summary = finalize_rehearsal_collection(temporary)
        current_owner = _validated_rehearsal_owner(release_sha, frontend_sha)
        if current_owner != owner:
            raise OrchestrationError("rehearsal_evidence_owner_mismatch")
        _validate_rehearsal_summary_owner(summary, current_owner, as_of_date)
        return summary

    summary = _collect_guest_evidence(
        destination,
        guest_command=build_rehearsal_guest_command,
        archive_name="local-rehearsal-evidence.tar.gz",
        stream_code="rehearsal_evidence_stream",
        extract_code="rehearsal_evidence_extract",
        destination_error="rehearsal_evidence_destination_exists",
        finalizer=finalize_bound_rehearsal,
    )
    assert isinstance(summary, dict)
    return summary


def collect_partial_failure(destination: Path) -> dict:
    summary = _collect_guest_evidence(
        destination,
        guest_command=build_guest_command,
        archive_name="local-partial-failure-evidence.tar.gz",
        stream_code="partial_evidence_stream",
        extract_code="partial_evidence_extract",
        destination_error="partial_evidence_destination_exists",
        finalizer=finalize_partial_failure_collection,
    )
    assert isinstance(summary, dict)
    return summary


def collect_rehearsal_partial_failure(
    destination: Path, release_sha: str, frontend_sha: str, as_of_date: str
) -> dict:
    if destination.exists():
        raise OrchestrationError("rehearsal_partial_evidence_destination_exists")
    owner = _validated_rehearsal_owner(release_sha, frontend_sha)

    def finalize_bound_rehearsal_partial(temporary: Path) -> dict:
        summary = finalize_rehearsal_partial_failure_collection(temporary)
        current_owner = _validated_rehearsal_owner(release_sha, frontend_sha)
        if current_owner != owner:
            raise OrchestrationError("rehearsal_evidence_owner_mismatch")
        _validate_rehearsal_summary_owner(summary, current_owner, as_of_date)
        return summary

    summary = _collect_guest_evidence(
        destination,
        guest_command=build_rehearsal_guest_command,
        archive_name="local-rehearsal-partial-failure-evidence.tar.gz",
        stream_code="rehearsal_partial_evidence_stream",
        extract_code="rehearsal_partial_evidence_extract",
        destination_error="rehearsal_partial_evidence_destination_exists",
        finalizer=finalize_bound_rehearsal_partial,
    )
    assert isinstance(summary, dict)
    return summary


def collect_bootstrap_failure(
    destination: Path, *, execution_kind: str = "canonical"
) -> dict:
    if execution_kind == "canonical":
        guest_command = build_guest_command
    elif execution_kind == "rehearsal":
        guest_command = build_rehearsal_guest_command
    else:
        raise OrchestrationError("execution_kind_not_accepted")
    if destination.exists():
        raise OrchestrationError("bootstrap_failure_destination_exists")
    state_json = _run_checked(
        "bootstrap_failure_state",
        guest_command(
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
                    guest_command(
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
        if execution_kind == "canonical":
            metadata = finalize_bootstrap_failure_bundle(temporary)
        else:
            metadata = finalize_rehearsal_bootstrap_failure_bundle(temporary)
        validate_failure_state_matches_metadata(state, metadata)
        temporary.rename(destination)
        print("PASS bootstrap_failure_bundle")
        return metadata
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def collect_rehearsal_bootstrap_failure(destination: Path) -> dict:
    return collect_bootstrap_failure(destination, execution_kind="rehearsal")


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
            "collect-partial-failure",
            "collect-bootstrap-failure",
            "provision-rehearsal",
            "run-rehearsal-stage",
            "collect-rehearsal",
            "collect-rehearsal-partial-failure",
            "collect-rehearsal-bootstrap-failure",
            "run-rc",
            "collect-rc",
            "collect-rc-partial-failure",
            "validate-campaign-ledger",
        ),
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--frontend-repo",
        type=Path,
        default=Path.cwd().parent / "smart-cms-app",
    )
    parser.add_argument("--release-sha", default=ACCEPTED_BASE_SHA)
    parser.add_argument("--frontend-sha")
    parser.add_argument("--stage", choices=STAGE_ORDER)
    parser.add_argument("--accept-later-origin-main", action="store_true")
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--dependency-bundle", type=Path)
    parser.add_argument("--dependency-bundle-sha256")
    parser.add_argument("--guest-id")
    parser.add_argument("--bootstrap-failure-dir", type=Path)
    parser.add_argument("--campaign-ledger", type=Path)
    parser.add_argument("--base-campaign-ledger", type=Path)
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
        if args.action == "collect-rehearsal-bootstrap-failure":
            if args.bootstrap_failure_dir is None:
                raise OrchestrationError("bootstrap_failure_dir_required")
            collect_rehearsal_bootstrap_failure(args.bootstrap_failure_dir)
            return 0
        if args.action == "validate-campaign-ledger":
            if args.campaign_ledger is None:
                raise OrchestrationError("campaign_ledger_path_required")
            if args.base_campaign_ledger is None:
                validate_campaign_ledger(args.campaign_ledger)
            else:
                validate_campaign_ledger_append_only(
                    args.base_campaign_ledger, args.campaign_ledger
                )
            print("PASS campaign_ledger")
            return 0
        if not isinstance(args.frontend_sha, str) or not re.fullmatch(
            r"[0-9a-f]{40}", args.frontend_sha
        ):
            raise OrchestrationError("frontend_sha_not_accepted")
        origin_main = _origin_main_sha(args.repo)
        frontend_origin_main = _origin_main_sha(args.frontend_repo)
        release_sha = validate_release_sha(
            args.release_sha,
            origin_main_sha=origin_main,
            accept_later_origin_main=args.accept_later_origin_main,
        )
        if args.frontend_sha != frontend_origin_main:
            raise OrchestrationError("frontend_sha_not_accepted")
        if args.as_of_date is not None and not _is_canonical_date(args.as_of_date):
            raise OrchestrationError("as_of_date_not_accepted")
        if args.action in {"run-rc", "collect-rc", "collect-rc-partial-failure"}:
            if args.evidence_dir is None:
                raise OrchestrationError("rc_evidence_destination_required")
            if args.guest_id is None:
                raise OrchestrationError("rc_guest_id_required")
            if not re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", args.guest_id):
                raise OrchestrationError("rc_guest_identity_not_accepted")
            if args.dependency_bundle_sha256 is None:
                raise OrchestrationError("rc_dependency_sha256_required")
            if not re.fullmatch(r"[0-9a-f]{64}", args.dependency_bundle_sha256):
                raise OrchestrationError("rc_dependency_identity_mismatch")
            if args.as_of_date is None:
                raise OrchestrationError("as_of_date_required")
            if args.evidence_dir.exists():
                raise OrchestrationError("rc_evidence_destination_exists")
            if args.action == "run-rc":
                print(
                    json.dumps(
                        run_rc(
                            release_sha=release_sha,
                            frontend_sha=args.frontend_sha,
                            dependency_sha256=args.dependency_bundle_sha256,
                            guest_id=args.guest_id,
                            destination=args.evidence_dir,
                            as_of_date=args.as_of_date,
                        ),
                        sort_keys=True,
                    )
                )
            elif args.action == "collect-rc":
                print(
                    json.dumps(
                        collect_rc(
                            destination=args.evidence_dir,
                            release_sha=release_sha,
                            frontend_sha=args.frontend_sha,
                            dependency_sha256=args.dependency_bundle_sha256,
                            guest_id=args.guest_id,
                            as_of_date=args.as_of_date,
                        ),
                        sort_keys=True,
                    )
                )
            else:
                print(
                    json.dumps(
                        collect_rc_partial_failure(
                            args.evidence_dir,
                            release_sha,
                            args.frontend_sha,
                            args.dependency_bundle_sha256,
                            args.guest_id,
                            args.as_of_date,
                        ),
                        sort_keys=True,
                    )
                )
        elif args.action == "plan":
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
        elif args.action in {"provision", "provision-rehearsal"}:
            if (
                args.dependency_bundle is None
                or args.dependency_bundle_sha256 is None
                or args.bootstrap_failure_dir is None
            ):
                raise OrchestrationError("provision_dependency_arguments_required")
            provision_action = (
                provision if args.action == "provision" else provision_rehearsal
            )
            provision_action(
                args.repo,
                release_sha,
                args.frontend_repo,
                args.frontend_sha,
                args.dependency_bundle,
                args.dependency_bundle_sha256,
                args.bootstrap_failure_dir,
            )
        elif args.action in {"run-stage", "run-rehearsal-stage"}:
            if args.stage is None:
                raise OrchestrationError("stage_required")
            if args.action == "run-rehearsal-stage" and args.as_of_date is None:
                raise OrchestrationError("as_of_date_required")
            stage_action = (
                run_stage if args.action == "run-stage" else run_rehearsal_stage
            )
            stage_action(
                args.stage, release_sha, args.frontend_sha, as_of_date=args.as_of_date
            )
        elif args.action == "run-all":
            run_all_stages(release_sha, args.frontend_sha, as_of_date=args.as_of_date)
        elif args.action == "collect":
            if args.evidence_dir is None:
                raise OrchestrationError("evidence_dir_required")
            collect_evidence(args.evidence_dir)
        elif args.action == "collect-rehearsal":
            if args.evidence_dir is None:
                raise OrchestrationError("evidence_dir_required")
            if args.as_of_date is None:
                raise OrchestrationError("as_of_date_required")
            print(
                json.dumps(
                    collect_rehearsal(
                        args.evidence_dir,
                        release_sha,
                        args.frontend_sha,
                        args.as_of_date,
                    ),
                    sort_keys=True,
                )
            )
        elif args.action == "collect-partial-failure":
            if args.evidence_dir is None:
                raise OrchestrationError("evidence_dir_required")
            print(
                json.dumps(collect_partial_failure(args.evidence_dir), sort_keys=True)
            )
        elif args.action == "collect-rehearsal-partial-failure":
            if args.evidence_dir is None:
                raise OrchestrationError("evidence_dir_required")
            if args.as_of_date is None:
                raise OrchestrationError("as_of_date_required")
            print(
                json.dumps(
                    collect_rehearsal_partial_failure(
                        args.evidence_dir,
                        release_sha,
                        args.frontend_sha,
                        args.as_of_date,
                    ),
                    sort_keys=True,
                )
            )
        else:
            raise OrchestrationError("action_not_accepted")
    except OrchestrationError as exc:
        print(f"FAIL orchestration: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
