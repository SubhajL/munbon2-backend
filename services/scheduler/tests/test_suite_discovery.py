"""Roadmap-named lock: the FULL scheduler suite collects cleanly (PR 4.2)."""

import os
import subprocess
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]


def test_full_scheduler_suite_collects_cleanly():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=SERVICE_ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # pytest reports collection failures via exit code 2 plus these markers;
    # a plain substring "error" also matches pydantic deprecation URLs.
    assert "errors during collection" not in result.stdout, result.stdout
    assert "\nERROR" not in result.stdout, result.stdout
    # The operational probes must never be discoverable as tests.
    collected = [
        line for line in result.stdout.splitlines() if "::" in line
    ]
    assert collected, result.stdout
    banned = ("ec2_connection_probe", "ec2_scheduler_api_probe",
              "test_ec2_connection", "test_scheduler_ec2_api")
    assert not any(
        any(name in line for name in banned) for line in collected
    ), collected
