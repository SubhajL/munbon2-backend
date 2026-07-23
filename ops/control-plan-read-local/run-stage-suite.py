#!/usr/bin/env python3
"""Run LOCAL-BASE-0 and LOCAL-RTA-1 inside the isolated Linux guest."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class StageGateError(RuntimeError):
    """A local stage gate failed with a fixed safe code."""


PROCESS_NAMES = (
    "flow-monitoring",
    "scheduler",
    "ros-gis-integration",
    "bff-water-planning",
)
READINESS_URLS = {
    "flow-monitoring": "http://127.0.0.1:3011/ready",
    "scheduler": "http://127.0.0.1:3021/ready",
    "ros-gis-integration": "http://127.0.0.1:3047/ready",
    "bff-water-planning": "http://127.0.0.1:3022/ready",
}
EXPECTED_FRONTEND_SHA = "3a16498a60927996ac38e741b276150968d0cadc"
GATE_ENV_NAMES = {
    "ALLOW_MACHINE_COMMANDS",
    "CONTROL_EXECUTION_MODE",
    "CONTROL_READBACK_RECONCILIATION_MODE",
    "DAILY_REQUIREMENT_ENABLED",
    "DAILY_REQUIREMENT_SCHEDULE_ENABLED",
    "DAILY_REQUIREMENT_STARTUP_CATCHUP_ENABLED",
    "GATES_API_ENABLED",
    "PLANNING_DEPTH_WRITES_ENABLED",
    "REQUIREMENT_SOURCE_POSTGRES_URL",
    "SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH",
    "SCHEDULER_SCADA_BASE_URL",
    "SCHEDULER_SERVICE_JWT_SECRET",
}


@dataclass(frozen=True)
class StageContext:
    release_sha: str
    frontend_sha: str
    repo_root: Path
    harness_root: Path
    evidence_root: Path
    runtime_env_dir: Path
    stability_duration: int = 300


def validate_runtime_urls(urls: dict[str, str]) -> dict[str, str]:
    for value in urls.values():
        parsed = urlsplit(value)
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.port is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise StageGateError("runtime_url_not_loopback")
    return urls


def validate_stage_transition(completed: tuple[str, ...], requested: str) -> None:
    order = ("LOCAL-BASE-0", "LOCAL-RTA-1")
    expected_index = len(completed)
    if (
        completed != order[:expected_index]
        or expected_index >= len(order)
        or requested != order[expected_index]
    ):
        raise StageGateError("stage_transition_invalid")


def rta_step_order() -> tuple[str, ...]:
    return (
        "capture_baseline",
        "verify_source_sha",
        "capacity_gate",
        "capacity_stop_rule",
        "install_manifests",
        "migration_parity",
        "monitoring_preflight",
        "start_four_processes",
        "verify_dark_flags",
        "five_minute_stability",
        "bearer_lifecycle",
        "pm2_save_and_evidence",
    )


def validate_evidence_payload(payload: object) -> None:
    forbidden_keys = (
        "password",
        "authorization",
        "token",
        "cookie",
        "secret",
        "dsn",
        "database_url",
        "postgres_url",
        "redis_url",
    )
    credential_url = re.compile(r"\b(?:postgres(?:ql)?|redis)://[^\s/@:]+:[^\s/@]+@")

    def inspect(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = str(key).lower()
                if any(forbidden in normalized for forbidden in forbidden_keys):
                    raise StageGateError("evidence_contains_secret")
                inspect(item)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                inspect(item)
            return
        if isinstance(value, str) and (
            value.lower().startswith("bearer ") or credential_url.search(value)
        ):
            raise StageGateError("evidence_contains_secret")

    inspect(payload)


def project_pm2_state(pm2_json: str) -> list[dict]:
    try:
        raw = json.loads(pm2_json)
        if not isinstance(raw, list):
            raise ValueError
        projection = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError
            env = item.get("pm2_env")
            monitor = item.get("monit", {})
            if not isinstance(env, dict) or not isinstance(monitor, dict):
                raise ValueError
            values = {
                "name": item.get("name"),
                "status": env.get("status"),
                "restarts": env.get("restart_time"),
                "pid": item.get("pid"),
                "memory_bytes": monitor.get("memory", 0),
                "cpu_percent": monitor.get("cpu", 0),
            }
            if (
                not isinstance(values["name"], str)
                or not isinstance(values["status"], str)
                or not isinstance(values["restarts"], int)
                or not isinstance(values["pid"], int)
                or not isinstance(values["memory_bytes"], int)
                or not isinstance(values["cpu_percent"], (int, float))
            ):
                raise ValueError
            projection.append(values)
        return sorted(projection, key=lambda item: item["name"])
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise StageGateError("pm2_state_invalid") from exc


def collect_dark_runtime_contract(pm2_json: str, model_release: dict) -> dict:
    try:
        raw = json.loads(pm2_json)
        if not isinstance(raw, list) or not isinstance(model_release, dict):
            raise ValueError
        environments = {}
        for item in raw:
            name = item.get("name")
            pm2_env = item.get("pm2_env")
            if not isinstance(name, str) or not isinstance(pm2_env, dict):
                raise ValueError
            nested = pm2_env.get("env", {})
            if not isinstance(nested, dict):
                raise ValueError
            environments[name] = {**nested, **pm2_env}
        required_names = {
            "flow-monitoring",
            "scheduler",
            "ros-gis-integration",
            "bff-water-planning",
        }
        if not required_names.issubset(environments):
            raise ValueError
        flow = environments["flow-monitoring"]
        scheduler = environments["scheduler"]
        ros = environments["ros-gis-integration"]
        bff = environments["bff-water-planning"]
        contract = {
            "flow_gates_api": flow.get("GATES_API_ENABLED") == "true",
            "scheduler_execution": scheduler.get("CONTROL_EXECUTION_MODE"),
            "scheduler_readback": scheduler.get("CONTROL_READBACK_RECONCILIATION_MODE"),
            "scheduler_scada_configured": any(
                scheduler.get(name)
                for name in (
                    "SCHEDULER_SCADA_BASE_URL",
                    "SCHEDULER_SERVICE_JWT_SECRET",
                    "SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH",
                )
            ),
            "ros_manual_producer": ros.get("DAILY_REQUIREMENT_ENABLED") == "true",
            "ros_startup_producer": ros.get("DAILY_REQUIREMENT_STARTUP_CATCHUP_ENABLED")
            == "true",
            "ros_recurring_producer": ros.get("DAILY_REQUIREMENT_SCHEDULE_ENABLED")
            == "true",
            "ros_source_configured": bool(ros.get("REQUIREMENT_SOURCE_POSTGRES_URL")),
            "planning_depth_writes": bff.get("PLANNING_DEPTH_WRITES_ENABLED") == "true",
            "machine_commands_configured": any(
                env.get("ALLOW_MACHINE_COMMANDS") not in (None, "false")
                for env in environments.values()
            ),
            "model_release_commandable": model_release.get("commandable"),
            "control_plan_reads_visible": False,
            "planning_depth_writes_visible": False,
        }
        expected = {
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
        if contract != expected:
            raise ValueError
        return contract
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise StageGateError("dark_runtime_contract_failed") from exc


def write_stage_manifest(path, payload: dict) -> None:
    target = Path(path)
    validate_evidence_payload(payload)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        os.chmod(target, 0o600)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def parse_listening_sockets(ss_output: str) -> list[dict]:
    listeners = []
    for line in ss_output.splitlines():
        fields = line.split()
        if len(fields) < 5 or fields[0] != "LISTEN":
            continue
        endpoint = fields[3]
        if endpoint.startswith("["):
            match = re.fullmatch(r"\[([^]]+)]:(\d+)", endpoint)
        else:
            match = re.fullmatch(r"(.+):(\d+)", endpoint)
        if match is None:
            continue
        listeners.append({"address": match.group(1), "port": int(match.group(2))})
    return listeners


def application_port_conflicts(listeners: list[dict]) -> list[int]:
    application_ports = {3011, 3021, 3022, 3047}
    return sorted(
        {
            listener["port"]
            for listener in listeners
            if listener.get("port") in application_ports
        }
    )


def unexpected_non_loopback_listeners(listeners: list[dict]) -> list[int]:
    loopback_addresses = {"127.0.0.1", "::1"}
    return sorted(
        {
            listener["port"]
            for listener in listeners
            if listener.get("address") not in loopback_addresses
            and isinstance(listener.get("port"), int)
        }
    )


def validate_migration_parity(
    scheduler_ids: list[str], ros_ids: list[str], bff_009_present: bool
) -> dict:
    expected_ros = [
        "0001_dataset_version_parent",
        "0002_water_requirement_publication",
        "0003_daily_requirement_producer",
    ]
    if (
        len(scheduler_ids) != 13
        or scheduler_ids[-1:] != ["0013_operator_approved_execution"]
        or ros_ids != expected_ros
        or not bff_009_present
    ):
        raise StageGateError("migration_parity_failed")
    return {
        "scheduler_latest": scheduler_ids[-1],
        "scheduler_count": len(scheduler_ids),
        "ros_latest": ros_ids[-1],
        "ros_count": len(ros_ids),
        "bff_latest": "009_crop_registry",
    }


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run_checked(
    code: str,
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 600,
) -> str:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StageGateError(f"{code}_failed") from exc
    if result.returncode != 0:
        raise StageGateError(f"{code}_failed")
    print(f"PASS {code}")
    return result.stdout


def _load_env_file(path: Path) -> dict[str, str]:
    try:
        result = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
                raise ValueError
            result[key] = value
        return result
    except (OSError, ValueError) as exc:
        raise StageGateError("runtime_env_invalid") from exc


def _service_environment(context: StageContext, service: str) -> dict[str, str]:
    return {
        **os.environ,
        **_load_env_file(context.runtime_env_dir / f"{service}.env"),
    }


def _postgres_process_env(postgres_url: str) -> dict[str, str]:
    parsed = urlsplit(postgres_url)
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or parsed.hostname != "127.0.0.1"
        or not parsed.username
        or parsed.password is None
        or not parsed.path.lstrip("/")
    ):
        raise StageGateError("postgres_url_invalid")
    from urllib.parse import unquote

    return {
        **os.environ,
        "PGHOST": parsed.hostname,
        "PGPORT": str(parsed.port or 5432),
        "PGUSER": unquote(parsed.username),
        "PGPASSWORD": unquote(parsed.password),
        "PGDATABASE": unquote(parsed.path.lstrip("/")),
        "PGOPTIONS": "-c statement_timeout=10000",
    }


def _psql(context: StageContext, query: str) -> str:
    postgres_url = _load_env_file(context.runtime_env_dir / "bff.env")["POSTGRES_URL"]
    return _run_checked(
        "postgres_probe",
        ["psql", "--no-psqlrc", "-X", "-At", "-F", "\t", "-c", query],
        env=_postgres_process_env(postgres_url),
        timeout=30,
    )


def _pm2_json() -> str:
    return _run_checked("pm2_snapshot", ["pm2", "jlist"], timeout=30)


def _capacity_snapshot() -> dict[str, int]:
    values = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            name, separator, remainder = line.partition(":")
            if separator and name in {"MemAvailable", "SwapTotal", "SwapFree"}:
                amount, unit = remainder.split()
                if unit != "kB":
                    raise ValueError
                values[name] = int(amount) // 1024
        if set(values) != {"MemAvailable", "SwapTotal", "SwapFree"}:
            raise ValueError
    except (OSError, ValueError) as exc:
        raise StageGateError("capacity_probe_failed") from exc
    return {
        "mem_available_mib": values["MemAvailable"],
        "swap_used_mib": values["SwapTotal"] - values["SwapFree"],
    }


def _listener_snapshot() -> list[dict]:
    output = _run_checked("listener_probe", ["ss", "-H", "-ltn"], timeout=30)
    return parse_listening_sockets(output)


def _read_json(path: Path) -> dict:
    try:
        if path.stat().st_size > 1024 * 1024:
            raise ValueError
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise StageGateError("json_artifact_invalid") from exc


def _load_state(context: StageContext) -> dict:
    path = context.evidence_root / "stage-state.json"
    if not path.exists():
        return {"release_sha": context.release_sha, "completed": []}
    state = _read_json(path)
    if state.get("release_sha") != context.release_sha or not isinstance(
        state.get("completed"), list
    ):
        raise StageGateError("stage_state_stale")
    return state


def _save_state(context: StageContext, completed: list[str]) -> None:
    write_stage_manifest(
        context.evidence_root / "stage-state.json",
        {"release_sha": context.release_sha, "completed": completed},
    )


def run_local_base(context: StageContext) -> dict:
    state = _load_state(context)
    validate_stage_transition(tuple(state["completed"]), "LOCAL-BASE-0")
    if context.frontend_sha != EXPECTED_FRONTEND_SHA:
        raise StageGateError("frontend_sha_not_accepted")
    actual_sha = _run_checked(
        "backend_sha", ["git", "rev-parse", "HEAD"], cwd=context.repo_root
    ).strip()
    tracked_status = _run_checked(
        "tracked_tree",
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=context.repo_root,
    ).strip()
    owner = _read_json(Path("/var/lib/munbon-local-acceptance/owner.json"))
    if (
        actual_sha != context.release_sha
        or tracked_status
        or os.uname().machine != "aarch64"
        or owner.get("machine") != "munbon-control-plan-local"
        or owner.get("architecture") != "arm64"
        or owner.get("release_sha") != context.release_sha
    ):
        raise StageGateError("local_baseline_invalid")
    manifest = {
        "stage": "LOCAL-BASE-0",
        "verdict": "PASS",
        "captured_at": _utc_timestamp(),
        "backend_sha": actual_sha,
        "frontend_sha": context.frontend_sha,
        "frontend_status": {
            "FE-0": "complete",
            "FE-1": "complete",
            "FE-2": "complete",
            "FE-3": "complete",
            "FE-4": "complete",
        },
        "pending_starts": ["ME-1", "W1"],
        "activation_flags": {
            "scheduler_execution": False,
            "machine_commands": False,
            "ros_manual_production": False,
            "ros_startup_production": False,
            "ros_recurring_production": False,
            "control_plan_reads": False,
            "control_plan_evidence_reads": False,
            "planning_depth_writes": False,
            "planning_depth_writes_visible": False,
        },
    }
    write_stage_manifest(context.evidence_root / "LOCAL-BASE-0.json", manifest)
    _save_state(context, ["LOCAL-BASE-0"])
    print("PASS LOCAL-BASE-0")
    return manifest


def _install_manifests(context: StageContext) -> dict:
    results = {}
    for service in PROCESS_NAMES:
        root = context.repo_root / "services" / service
        python = root / ".venv" / "bin" / "python"
        pip = root / ".venv" / "bin" / "pip"
        _run_checked(
            f"{service}_venv",
            ["python3", "-m", "venv", str(root / ".venv")],
            timeout=120,
        )
        _run_checked(
            f"{service}_manifest",
            [
                str(pip),
                "install",
                "--disable-pip-version-check",
                "--quiet",
                "--requirement",
                str(root / "requirements.txt"),
            ],
            timeout=1200,
        )
        _run_checked(f"{service}_pip_check", [str(python), "-m", "pip", "check"])
        results[service] = "manifest-installed-pip-check-pass"
    return results


def _apply_migrations(context: StageContext) -> dict:
    for service in ("flow-monitoring", "scheduler"):
        root = context.repo_root / "services" / service
        env = _service_environment(
            context, "flow" if service == "flow-monitoring" else service
        )
        _run_checked(
            f"{service}_migrations",
            [str(root / ".venv/bin/python"), "migrations/migrate.py", "apply-all"],
            cwd=root,
            env=env,
            timeout=180,
        )
    ros_root = context.repo_root / "services/ros-gis-integration"
    ros_env = _service_environment(context, "ros")
    for migration_id in (
        "0001_dataset_version_parent",
        "0002_water_requirement_publication",
        "0003_daily_requirement_producer",
    ):
        _run_checked(
            f"ros_{migration_id}",
            [
                str(ros_root / ".venv/bin/python"),
                "migrations/migrate.py",
                "apply",
                migration_id,
            ],
            cwd=ros_root,
            env=ros_env,
            timeout=180,
        )
    bff_root = context.repo_root / "services/bff-water-planning"
    _run_checked(
        "bff_009_migration",
        [
            str(bff_root / ".venv/bin/python"),
            str(
                context.repo_root
                / "ops/control-plan-read-runtime/apply_bff_migration.py"
            ),
        ],
        cwd=context.repo_root,
        env=_service_environment(context, "bff"),
        timeout=180,
    )
    scheduler_rows = _psql(
        context,
        "SELECT migration_id, checksum FROM scheduler.schema_migrations ORDER BY migration_id",
    ).splitlines()
    ros_rows = _psql(
        context,
        "SELECT migration_id, checksum FROM ros_gis.schema_migrations ORDER BY migration_id",
    ).splitlines()
    bff_present = (
        _psql(context, "SELECT to_regclass('gis.crop_registry') IS NOT NULL").strip()
        == "t"
    )
    scheduler_ids = [row.split("\t", 1)[0] for row in scheduler_rows]
    ros_ids = [row.split("\t", 1)[0] for row in ros_rows]
    parity = validate_migration_parity(scheduler_ids, ros_ids, bff_present)
    parity["scheduler_migrations"] = scheduler_ids
    parity["ros_migrations"] = ros_ids
    parity["bff_009_sha256"] = hashlib.sha256(
        (bff_root / "migrations/009_crop_registry.sql").read_bytes()
    ).hexdigest()
    return parity


def _monitoring_preflight(context: StageContext) -> dict:
    _run_checked(
        "prometheus_rules",
        ["promtool", "check", "rules", "/etc/prometheus/control-plane-alerts.yml"],
    )
    _run_checked(
        "prometheus_config",
        ["promtool", "check", "config", "/etc/prometheus/control-plane-prometheus.yml"],
    )
    infra = context.repo_root / "infra/pm2"
    _run_checked("infra_verify", ["npm", "run", "verify"], cwd=infra, timeout=900)
    _run_checked("infra_build", ["npm", "run", "build"], cwd=infra, timeout=300)
    scheduler_env = _service_environment(context, "scheduler")
    bff_env = _service_environment(context, "bff")
    flow_env = _service_environment(context, "flow")
    secrets = _load_env_file(context.runtime_env_dir / "local-secrets.env")
    preflight_env = {
        **os.environ,
        **scheduler_env,
        "GIS_DATABASE_URL": bff_env["POSTGRES_URL"],
        "TIMESCALE_URL": flow_env["TIMESCALE_URL"],
        "POSTGRES_PASSWORD": secrets["DB_PASSWORD"],
        "TIMESCALE_PASSWORD": secrets["DB_PASSWORD"],
    }
    output = _run_checked(
        "repository_preflight",
        [
            "node",
            "dist/deploy-preflight-cli.js",
            "--role",
            "central",
            "--expected-commit",
            context.release_sha,
        ],
        cwd=infra,
        env=preflight_env,
        timeout=120,
    )
    try:
        report = json.loads(output)
        return {
            "approved": report["approved"],
            "commit": report["commit"],
            "latest_migration": report["latestMigration"],
            "process_names": report["processNames"],
            "command_gates": report["commandGates"],
            "promtool": "PASS",
        }
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise StageGateError("repository_preflight_output_invalid") from exc


def _actual_gate_environment(pm2_json: str) -> str:
    try:
        raw = json.loads(pm2_json)
        projected = []
        for item in raw:
            if item.get("name") not in PROCESS_NAMES or not isinstance(
                item.get("pid"), int
            ):
                continue
            environ = Path(f"/proc/{item['pid']}/environ").read_bytes().split(b"\0")
            selected = {}
            for entry in environ:
                key, separator, value = entry.partition(b"=")
                decoded_key = key.decode("utf-8", errors="strict")
                if separator and decoded_key in GATE_ENV_NAMES:
                    selected[decoded_key] = value.decode("utf-8", errors="strict")
            projected.append(
                {"name": item["name"], "pm2_env": {"env": selected, **selected}}
            )
        return json.dumps(projected)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise StageGateError("process_gate_environment_invalid") from exc


def _readiness_snapshot() -> dict[str, dict]:
    results = {}
    for name, url in READINESS_URLS.items():
        try:
            request = Request(url, headers={"Accept": "application/json"})
            with urlopen(request, timeout=5) as response:
                body = json.loads(response.read(64 * 1024))
            if response.status != 200 or body.get("status") != "ready":
                raise ValueError
            checks = body.get("checks", {})
            if not isinstance(checks, dict):
                raise ValueError
            results[name] = {
                "status_code": response.status,
                "status": "ready",
                "checks": checks,
            }
        except Exception as exc:
            raise StageGateError(f"{name}_readiness_evidence_failed") from exc
    validate_evidence_payload(results)
    return results


@contextmanager
def _temporary_environment(values: dict[str, str]):
    previous = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _run_bearer(context: StageContext) -> dict:
    path = context.harness_root / "verify_bearer.py"
    spec = importlib.util.spec_from_file_location("local_verify_bearer", path)
    if spec is None or spec.loader is None:
        raise StageGateError("bearer_verifier_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    operator_env = _load_env_file(context.runtime_env_dir / "operator.env")
    try:
        with _temporary_environment(operator_env):
            config = module.Config.from_environment()
            evidence = module.run_verification(config, module.SafeReporter())
    except module.VerificationError as exc:
        raise StageGateError(f"bearer_{exc}") from exc
    validate_evidence_payload(evidence)
    return evidence


def _stop_runtime() -> None:
    subprocess.run(
        ["pm2", "stop", *PROCESS_NAMES],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )


def _checksum_manifest(path: Path) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    index = path.parent / "SHA256SUMS"
    descriptor = os.open(index, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(f"{digest}  {path.name}\n")


def run_local_rta(context: StageContext) -> dict:
    state = _load_state(context)
    validate_stage_transition(tuple(state["completed"]), "LOCAL-RTA-1")
    steps = {}
    before_pm2_json = _pm2_json()
    steps["capture_baseline"] = {
        "captured_at": _utc_timestamp(),
        "hostname": os.uname().nodename,
        "kernel_machine": os.uname().machine,
        "release_sha": context.release_sha,
        "pm2": project_pm2_state(before_pm2_json),
        "capacity": _capacity_snapshot(),
        "listeners": _listener_snapshot(),
    }
    actual_sha = _run_checked(
        "release_sha", ["git", "rev-parse", "HEAD"], cwd=context.repo_root
    ).strip()
    if actual_sha != context.release_sha:
        raise StageGateError("release_sha_mismatch")
    steps["verify_source_sha"] = {"actual_sha": actual_sha}
    capacity = _capacity_snapshot()
    conflicts = application_port_conflicts(steps["capture_baseline"]["listeners"])
    exposed_ports = unexpected_non_loopback_listeners(
        steps["capture_baseline"]["listeners"]
    )
    if capacity["mem_available_mib"] < 512:
        raise StageGateError("mem_available_below_512_mib")
    if capacity["swap_used_mib"] > 1024:
        raise StageGateError("swap_used_above_1024_mib")
    if conflicts:
        raise StageGateError("application_port_conflict")
    if exposed_ports:
        raise StageGateError("unexpected_non_loopback_listener")
    _run_checked(
        "capacity_gate",
        ["python3", "ops/control-plan-read-runtime/runtime_gate.py", "capacity"],
        cwd=context.repo_root,
    )
    steps["capacity_gate"] = {
        **capacity,
        "port_conflicts": conflicts,
        "non_loopback_ports": exposed_ports,
    }
    steps["capacity_stop_rule"] = {"triggered": False, "gate_lowered": False}
    steps["install_manifests"] = _install_manifests(context)
    steps["migration_parity"] = _apply_migrations(context)
    steps["monitoring_preflight"] = _monitoring_preflight(context)
    runtime_env = {**os.environ, "MUNBON_RUNTIME_ENV_DIR": str(context.runtime_env_dir)}
    _run_checked(
        "start_four_processes",
        ["pm2", "start", "ecosystem.config.cjs", "--update-env"],
        cwd=context.repo_root / "ops/control-plan-read-runtime",
        env=runtime_env,
        timeout=120,
    )
    baseline_output = _run_checked(
        "restart_baseline",
        ["python3", "runtime_gate.py", "snapshot"],
        cwd=context.repo_root / "ops/control-plan-read-runtime",
        env=runtime_env,
    )
    try:
        restart_baseline = json.loads(baseline_output)
    except json.JSONDecodeError as exc:
        raise StageGateError("restart_baseline_invalid") from exc
    steps["start_four_processes"] = {"restart_baseline": restart_baseline}
    running_pm2_json = _pm2_json()
    model_release = _read_json(
        context.repo_root
        / "services/flow-monitoring/data/model-releases/engineering-prior-v3-v1.json"
    )
    steps["verify_dark_flags"] = collect_dark_runtime_contract(
        _actual_gate_environment(running_pm2_json), model_release
    )
    baseline_path = context.evidence_root / ".restart-baseline.json"
    write_stage_manifest(baseline_path, restart_baseline)
    _run_checked(
        "five_minute_stability",
        [
            "python3",
            "runtime_gate.py",
            "stability",
            "--baseline",
            str(baseline_path),
            "--startup-timeout",
            "120",
            "--duration",
            str(context.stability_duration),
            "--interval",
            "5",
        ],
        cwd=context.repo_root / "ops/control-plan-read-runtime",
        env=runtime_env,
        timeout=context.stability_duration + 180,
    )
    baseline_path.unlink(missing_ok=True)
    stable_pm2_json = _pm2_json()
    stable_state = project_pm2_state(stable_pm2_json)
    steps["five_minute_stability"] = {
        "duration_seconds": context.stability_duration,
        "readiness": _readiness_snapshot(),
        "pm2": stable_state,
        "restart_counts_unchanged": all(
            item["restarts"] == restart_baseline[item["name"]]
            for item in stable_state
            if item["name"] in restart_baseline
        ),
    }
    if not steps["five_minute_stability"]["restart_counts_unchanged"]:
        raise StageGateError("restart_counts_changed")
    steps["bearer_lifecycle"] = _run_bearer(context)
    after_capacity = _capacity_snapshot()
    after_listeners = _listener_snapshot()
    if unexpected_non_loopback_listeners(after_listeners):
        raise StageGateError("unexpected_non_loopback_listener")
    expected_listeners = {
        ("127.0.0.1", 3011),
        ("127.0.0.1", 3021),
        ("127.0.0.1", 3022),
        ("127.0.0.1", 3047),
    }
    actual_application_listeners = {
        (item["address"], item["port"])
        for item in after_listeners
        if item["port"] in {3011, 3021, 3022, 3047}
    }
    if actual_application_listeners != expected_listeners:
        raise StageGateError("loopback_listener_contract_failed")
    steps["pm2_save_and_evidence"] = {
        "saved": True,
        "capacity_after_startup": after_capacity,
        "application_listeners": after_listeners,
    }
    manifest = {
        "stage": "LOCAL-RTA-1",
        "verdict": "PASS",
        "release_sha": context.release_sha,
        "completed_at": _utc_timestamp(),
        "step_order": list(rta_step_order()),
        "steps": steps,
    }
    validate_evidence_payload(manifest)
    _run_checked("pm2_save", ["pm2", "save"], timeout=60)
    target = context.evidence_root / "LOCAL-RTA-1.json"
    write_stage_manifest(target, manifest)
    _checksum_manifest(target)
    _save_state(context, ["LOCAL-BASE-0", "LOCAL-RTA-1"])
    print("PASS LOCAL-RTA-1")
    return manifest


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("LOCAL-BASE-0", "LOCAL-RTA-1"))
    parser.add_argument("--release-sha", required=True)
    parser.add_argument("--frontend-sha", default=EXPECTED_FRONTEND_SHA)
    parser.add_argument("--repo-root", type=Path, default=Path("/opt/munbon/repo"))
    parser.add_argument(
        "--harness-root", type=Path, default=Path("/opt/munbon/harness")
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path("/var/lib/munbon-local-acceptance/evidence"),
    )
    parser.add_argument(
        "--runtime-env-dir",
        type=Path,
        default=Path("/etc/munbon/control-plan-read-runtime"),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    context = StageContext(
        release_sha=args.release_sha,
        frontend_sha=args.frontend_sha,
        repo_root=args.repo_root,
        harness_root=args.harness_root,
        evidence_root=args.evidence_root,
        runtime_env_dir=args.runtime_env_dir,
    )
    try:
        if args.stage == "LOCAL-BASE-0":
            run_local_base(context)
        else:
            run_local_rta(context)
    except Exception as exc:
        safe_error = (
            exc
            if isinstance(exc, StageGateError)
            else StageGateError(f"unexpected_{type(exc).__name__}")
        )
        if args.stage == "LOCAL-RTA-1":
            _stop_runtime()
        failure = {
            "stage": args.stage,
            "verdict": "FAIL",
            "release_sha": args.release_sha,
            "failed_gate": str(safe_error),
            "failed_at": _utc_timestamp(),
        }
        try:
            write_stage_manifest(
                args.evidence_root / f"{args.stage}-failure.json", failure
            )
        except Exception:
            pass
        print(f"FAIL {args.stage}: {safe_error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
