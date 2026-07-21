#!/usr/bin/env python3
"""Fail-closed capacity, PM2 restart, and readiness gates for OPS-1."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen


MIB = 1024 * 1024
MIN_MEM_AVAILABLE_BYTES = 512 * MIB
MAX_SWAP_USED_BYTES = 1024 * MIB
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


class GateError(RuntimeError):
    """A gate input is missing or malformed; messages are fixed safe codes."""


@dataclass(frozen=True)
class Capacity:
    mem_available_bytes: int
    swap_total_bytes: int
    swap_free_bytes: int

    @property
    def swap_used_bytes(self) -> int:
        return self.swap_total_bytes - self.swap_free_bytes


def parse_meminfo(text: str) -> Capacity:
    try:
        values: dict[str, int] = {}
        for line in text.splitlines():
            name, separator, remainder = line.partition(":")
            if not separator or name not in {
                "MemAvailable",
                "SwapTotal",
                "SwapFree",
            }:
                continue
            parts = remainder.split()
            if len(parts) != 2 or parts[1] != "kB":
                raise ValueError
            values[name] = int(parts[0]) * 1024
        if set(values) != {"MemAvailable", "SwapTotal", "SwapFree"}:
            raise ValueError
        if any(value < 0 for value in values.values()):
            raise ValueError
        if values["SwapFree"] > values["SwapTotal"]:
            raise ValueError
        return Capacity(
            mem_available_bytes=values["MemAvailable"],
            swap_total_bytes=values["SwapTotal"],
            swap_free_bytes=values["SwapFree"],
        )
    except (TypeError, ValueError) as exc:
        raise GateError("invalid_meminfo") from exc


def read_capacity(path: Path = Path("/proc/meminfo")) -> Capacity:
    try:
        return parse_meminfo(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise GateError("meminfo_unavailable") from exc


def capacity_errors(capacity: Capacity) -> list[str]:
    errors = []
    if capacity.mem_available_bytes < MIN_MEM_AVAILABLE_BYTES:
        errors.append("mem_available_below_512_mib")
    if capacity.swap_used_bytes > MAX_SWAP_USED_BYTES:
        errors.append("swap_used_above_1024_mib")
    return errors


def _project_pm2(pm2_json: str) -> dict[str, tuple[str, int]]:
    try:
        raw = json.loads(pm2_json)
        if not isinstance(raw, list):
            raise ValueError
        projected: dict[str, tuple[str, int]] = {}
        for item in raw:
            if not isinstance(item, dict) or item.get("name") not in PROCESS_NAMES:
                continue
            name = item["name"]
            if name in projected:
                raise ValueError
            env = item.get("pm2_env")
            if not isinstance(env, dict):
                raise ValueError
            status = env.get("status")
            restart_count = env.get("restart_time")
            if not isinstance(status, str) or not isinstance(restart_count, int):
                raise ValueError
            if restart_count < 0:
                raise ValueError
            projected[name] = (status, restart_count)
        return projected
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise GateError("invalid_pm2_state") from exc


def restart_snapshot(pm2_json: str) -> dict[str, int]:
    projected = _project_pm2(pm2_json)
    return {name: projected.get(name, ("missing", 0))[1] for name in PROCESS_NAMES}


def run_pm2_jlist() -> str:
    try:
        result = subprocess.run(
            ["pm2", "jlist"], capture_output=True, text=True, check=False
        )
    except OSError as exc:
        raise GateError("pm2_unavailable") from exc
    if result.returncode != 0:
        raise GateError("pm2_jlist_failed")
    return result.stdout


def probe_readiness(
    url: str,
    opener: Callable = urlopen,
    timeout_seconds: float = 3.0,
) -> bool:
    try:
        request = Request(url, headers={"Accept": "application/json"})
        with opener(request, timeout=timeout_seconds) as response:
            if response.status != 200:
                return False
            body = json.loads(response.read())
        return isinstance(body, dict) and body.get("status") == "ready"
    except Exception:
        return False


def stability_errors(
    pm2_json: str,
    baseline: dict[str, int],
    readiness: dict[str, bool],
    capacity: Capacity,
) -> list[str]:
    errors = capacity_errors(capacity)
    try:
        projected = _project_pm2(pm2_json)
    except GateError:
        return [*errors, "pm2_state_invalid"]
    for name in PROCESS_NAMES:
        current = projected.get(name)
        if current is None:
            errors.append(f"{name}_missing")
        else:
            status, restart_count = current
            if status != "online":
                errors.append(f"{name}_not_online")
            if restart_count != baseline.get(name, 0):
                errors.append(f"{name}_restarted")
        if readiness.get(name) is not True:
            errors.append(f"{name}_not_ready")
    return errors


def monitor_stability(
    duration_seconds: float,
    interval_seconds: float,
    sample: Callable[[], list[str]],
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> list[str]:
    if duration_seconds < 0 or interval_seconds <= 0:
        return ["invalid_monitor_window"]
    started = monotonic()
    while True:
        errors = sample()
        if errors:
            return errors
        elapsed = monotonic() - started
        if elapsed >= duration_seconds:
            return []
        sleep(min(interval_seconds, duration_seconds - elapsed))


def monitor_startup(
    timeout_seconds: float,
    interval_seconds: float,
    sample: Callable[[], list[str]],
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> list[str]:
    if timeout_seconds < 0 or interval_seconds <= 0:
        return ["invalid_startup_window"]
    started = monotonic()
    transient_suffixes = ("_missing", "_not_online", "_not_ready")
    while True:
        errors = sample()
        if not errors:
            return []
        fatal = [error for error in errors if not error.endswith(transient_suffixes)]
        if fatal:
            return fatal
        elapsed = monotonic() - started
        if elapsed >= timeout_seconds:
            return ["startup_timeout", *errors]
        sleep(min(interval_seconds, timeout_seconds - elapsed))


def _load_baseline(path: Path) -> dict[str, int]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or set(value) != set(PROCESS_NAMES):
            raise ValueError
        if not all(isinstance(item, int) and item >= 0 for item in value.values()):
            raise ValueError
        return value
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise GateError("invalid_restart_baseline") from exc


def _capacity_command() -> int:
    try:
        capacity = read_capacity()
        errors = capacity_errors(capacity)
    except GateError as exc:
        print(f"FAIL capacity: {exc}")
        return 1
    if errors:
        print(f"FAIL capacity: {','.join(errors)}")
        return 1
    print(
        "PASS capacity: "
        f"mem_available_mib={capacity.mem_available_bytes // MIB} "
        f"swap_used_mib={capacity.swap_used_bytes // MIB}"
    )
    return 0


def _snapshot_command() -> int:
    try:
        print(json.dumps(restart_snapshot(run_pm2_jlist()), sort_keys=True))
    except GateError as exc:
        print(f"FAIL snapshot: {exc}")
        return 1
    return 0


def _stability_command(
    baseline_path: Path, startup_timeout: int, duration: int, interval: int
) -> int:
    try:
        baseline = _load_baseline(baseline_path)
    except GateError as exc:
        print(f"FAIL stability: {exc}")
        return 1

    def sample() -> list[str]:
        try:
            capacity = read_capacity()
            pm2_json = run_pm2_jlist()
        except GateError as exc:
            return [str(exc)]
        readiness = {
            name: probe_readiness(READINESS_URLS[name]) for name in PROCESS_NAMES
        }
        return stability_errors(pm2_json, baseline, readiness, capacity)

    errors = monitor_startup(startup_timeout, interval, sample)
    if errors:
        print(f"FAIL startup: {','.join(errors)}")
        return 1
    errors = monitor_stability(duration, interval, sample)
    if errors:
        print(f"FAIL stability: {','.join(errors)}")
        return 1
    print(f"PASS stability: duration_seconds={duration} unexpected_restarts=0")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("capacity")
    subparsers.add_parser("snapshot")
    stability = subparsers.add_parser("stability")
    stability.add_argument("--baseline", type=Path, required=True)
    stability.add_argument("--startup-timeout", type=int, default=120)
    stability.add_argument("--duration", type=int, default=300)
    stability.add_argument("--interval", type=int, default=5)
    args = parser.parse_args(argv)
    if args.command == "capacity":
        return _capacity_command()
    if args.command == "snapshot":
        return _snapshot_command()
    return _stability_command(
        args.baseline, args.startup_timeout, args.duration, args.interval
    )


if __name__ == "__main__":
    raise SystemExit(main())
