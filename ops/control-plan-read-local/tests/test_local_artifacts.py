import re
import subprocess
from pathlib import Path

LOCAL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = LOCAL_DIR.parents[1]


def test_bootstrap_is_valid_bash_and_provisions_only_isolated_manifests():
    path = LOCAL_DIR / "bootstrap-linux.sh"
    body = path.read_text(encoding="utf-8")

    subprocess.run(["bash", "-n", str(path)], check=True)
    assert "\ncd /\n" in body
    assert 'cd "${FRONTEND_ROOT}"' in body
    for required in (
        "influxdb2",
        "coinor-cbc",
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
        "local-ac1.py",
        "seed-approved-sources.py",
        "run-ros-manual-producer.sh",
        "NODE_VERSION=22.23.1",
        "linux-arm64",
        "playwright@1.54.2",
        "playwright install --with-deps chromium",
        "frontend.bundle",
        "run-read-browser.js",
        "run-evidence-browser.js",
        "prisma generate",
        "checkout --force --quiet",
        "evidence-archive",
        "pg_terminate_backend",
        "dropdb --if-exists munbon_local",
        "redis-cli FLUSHALL",
        "pm2 delete all",
    ):
        assert required in body
    assert "pip install --user" not in body
    assert "sudo pip" not in body
    for match in re.finditer(r"postgres(?:ql)?://[^\s]+:[^\s]+@", body):
        assert "${" in match.group()


def test_orchestrator_provisions_every_local_ac_harness_artifact():
    body = (LOCAL_DIR / "orchestrate.py").read_text(encoding="utf-8")

    for required in (
        "local-ac1.py",
        "seed-approved-sources.py",
        "run-ros-manual-producer.sh",
        "frontend.bundle",
        "run-read-browser.js",
        "run-evidence-browser.js",
        "--frontend-repo",
    ):
        assert required in body


def test_every_completed_stage_is_added_to_the_checksum_index():
    body = (LOCAL_DIR / "run-stage-suite.py").read_text(encoding="utf-8")

    assert body.count("_checksum_manifest(target)") == 5
    assert "_checksum_manifest(path)" in body
    assert "_verify_checksum_entry" in body


def test_read_browser_runner_covers_dark_visible_and_panel_failure_scenarios():
    body = (LOCAL_DIR / "run-read-browser.js").read_text(encoding="utf-8")

    for required in (
        "navigation_link_count",
        "signed_out_redirect",
        "list_plan_found",
        "refresh_preserved_detail",
        "deep_link_loaded",
        "missing_plan_alerts",
        "ledger-only",
        "action_controls",
        "unexpected_control_plan_mutations",
        "mutation_route_denial_count",
        "mutationRoutePaths",
        'route.abort("blockedbyclient")',
        "browser_${checkpoint}_failed",
        "serverProxyAllowed",
        "projectionPanel",
    ):
        assert required in body


def test_evidence_browser_runner_covers_machine_evidence_and_gate_boundary():
    path = LOCAL_DIR / "run-evidence-browser.js"
    body = path.read_text(encoding="utf-8")

    subprocess.run(["node", "--check", str(path)], check=True)
    for required in (
        "projection_statuses",
        "projection_no_store_count",
        "evidence_panel_count",
        "absent_projection_alerts",
        "unavailable_projection",
        "malformed_projection",
        "intent_timeline_state",
        "held_state",
        "gate_link",
        "gate_operations_navigation_requests",
        "evidence_request_paths",
        "forbidden_product_requests",
        "product_mutation_requests",
        "classifyProductRequest",
        "unexpectedApi",
        "No command intents are recorded.",
        "Empty intent history does not claim execution.",
    ):
        assert required in body


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


def test_manual_ros_wrapper_enables_only_manual_production_on_loopback():
    wrapper = (LOCAL_DIR / "run-ros-manual-producer.sh").read_text(encoding="utf-8")

    assert (
        "DAILY_REQUIREMENT_ENABLED=true" in wrapper
        and "DAILY_REQUIREMENT_STARTUP_CATCHUP_ENABLED=false" in wrapper
        and "DAILY_REQUIREMENT_SCHEDULE_ENABLED=false" in wrapper
        and 'REQUIREMENT_SOURCE_POSTGRES_URL="${POSTGRES_URL}"' in wrapper
        and "FLOW_MONITORING_URL=http://127.0.0.1:3011" in wrapper
        and "--host 127.0.0.1" in wrapper
        and "--port 3047" in wrapper
        and "ALLOW_MACHINE_COMMANDS=false" in wrapper
        and "DAILY_REQUIREMENT_MANUAL_TOKEN" in wrapper
        and "local-secrets.env" in wrapper
        and 'PYTHONPATH="${SERVICE_ROOT}/src"' in wrapper
        and "src.main:app" in wrapper
    )


def test_all_stages_runbook_locks_local_before_aws_and_documents_current_commands():
    body = (
        REPO_ROOT / "docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md"
    ).read_text(encoding="utf-8")
    documented_candidate_commands = 7

    for required in (
        "LOCAL-BASE-0",
        "LOCAL-RTA-1",
        "LOCAL-RC-1",
        "native `arm64`",
        "No AWS action",
        "orchestrate.py provision",
        "orchestrate.py run-stage --stage LOCAL-BASE-0",
        "orchestrate.py run-stage --stage LOCAL-RTA-1",
        "orchestrate.py run-stage --stage LOCAL-AC-1",
        "orchestrate.py run-stage --stage LOCAL-READ-ACT-1",
        "orchestrate.py run-stage --stage LOCAL-EVIDENCE-1",
        "orchestrate.py collect",
        "false → true → false",
        "bearer verification before `pm2 save`",
        "evidence-with-wildcard",
    ):
        assert required in body
    assert (
        body.count('--release-sha "$accepted_backend_sha"')
        == documented_candidate_commands
    )
    assert (
        body.count('--frontend-sha "$accepted_frontend_sha"')
        == documented_candidate_commands
    )
    assert "2ee640c5eed939b68035c7695a4c129570e9ca5a" not in body
