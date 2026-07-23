import re
import subprocess
from pathlib import Path

LOCAL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = LOCAL_DIR.parents[1]


def test_bootstrap_is_valid_bash_and_provisions_only_isolated_manifests():
    path = LOCAL_DIR / "bootstrap-linux.sh"
    body = path.read_text(encoding="utf-8")

    subprocess.run(["bash", "-n", str(path)], check=True)
    for required in (
        "influxdb2",
        "postgresql",
        "postgis",
        "libgdal-dev",
        "redis-server",
        "prometheus",
        "python3 -m venv",
        "requirements.txt",
        "npm --prefix",
        "pm2@",
        "127.0.0.1:8086",
        "Type=simple",
        "PIDFile=",
        "chmod 600",
        "seed-local-operators.js",
    ):
        assert required in body
    assert "pip install --user" not in body
    assert "sudo pip" not in body
    for match in re.finditer(r"postgres(?:ql)?://[^\s]+:[^\s]+@", body):
        assert "${" in match.group()


def test_auth_systemd_unit_is_loopback_local_and_uses_mode_600_env():
    body = (LOCAL_DIR / "systemd" / "munbon-local-auth.service").read_text(
        encoding="utf-8"
    )

    for required in (
        "User=munbon",
        "EnvironmentFile=/etc/munbon/control-plan-read-runtime/auth.env",
        "WorkingDirectory=/opt/munbon/repo/services/auth",
        "ExecStart=/usr/bin/node src/index.js",
        "NoNewPrivileges=true",
    ):
        assert required in body
    assert "password" not in body.lower()


def test_all_stages_runbook_locks_local_before_aws_and_documents_current_commands():
    body = (
        REPO_ROOT / "docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md"
    ).read_text(encoding="utf-8")

    for required in (
        "LOCAL-BASE-0",
        "LOCAL-RTA-1",
        "LOCAL-RC-1",
        "native `arm64`",
        "No AWS action",
        "orchestrate.py provision",
        "orchestrate.py run-stage --stage LOCAL-BASE-0",
        "orchestrate.py run-stage --stage LOCAL-RTA-1",
        "bearer verification before `pm2 save`",
        "evidence-with-wildcard",
    ):
        assert required in body
