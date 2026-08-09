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
        "run-go-read-browser.js",
        "services/scada-gate-control",
        "services/scada-gate-control-web",
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
        "run-go-read-browser.js",
        "run-write-browser.js",
        "--frontend-repo",
    ):
        assert required in body


def test_every_completed_stage_is_added_to_the_checksum_index():
    body = (LOCAL_DIR / "run-stage-suite.py").read_text(encoding="utf-8")

    # Nine PASS manifests plus the pre-validation browser result and any
    # failure manifest are all checksum-bound.
    assert body.count("_checksum_manifest(target)") == 11
    assert "_checksum_manifest(path)" in body
    assert "_verify_checksum_entry" in body
    assert "_save_state(context, list(STAGE_ORDER[:5]))" in body
    assert "_save_state(context, list(STAGE_ORDER[:6]))" in body
    assert "_save_state(context, list(STAGE_ORDER[:7]))" in body
    assert "_save_state(context, list(STAGE_ORDER[:8]))" in body
    assert "_save_state(context, list(STAGE_ORDER[:9]))" in body


def test_stage_suite_uses_the_v5_hydraulic_release():
    body = (LOCAL_DIR / "run-stage-suite.py").read_text(encoding="utf-8")

    assert body.count("engineering-prior-v5-v1.json") == 5
    assert "engineering-prior-v3-v1.json" not in body


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
        "request_inventory_scope",
        "evidence_request_paths",
        "forbidden_product_requests",
        "product_mutation_requests",
        "classifyProductRequest",
        "unexpectedApi",
        "unexpected_api_request_observed",
        "forbidden_control_path_observed",
        "evidenceInventoryActive",
        "bootstrap_refresh_not_settled",
        "redirectAfterLogin",
        "No command intents are recorded.",
        "Empty intent history does not claim execution.",
    ):
        assert required in body


def test_go_read_browser_runner_covers_real_status_outage_and_request_inventory():
    path = LOCAL_DIR / "run-go-read-browser.js"
    body = path.read_text(encoding="utf-8")

    subprocess.run(["node", "--check", str(path)], check=True)
    subprocess.run(
        [
            "node",
            "--test",
            str(LOCAL_DIR / "tests" / "test_go_read_browser_inventory.js"),
        ],
        check=True,
    )
    for required in (
        "signed_out_status_requests",
        "live_status_responses",
        "unknown_gate_status",
        "outage_status",
        "outage_alert_visible",
        "stale_status_hidden",
        "action_controls",
        "direct_scada_browser_requests",
        "forbidden_product_requests",
        "product_mutation_requests",
        "full-signed-out-through-outage",
        "LOCAL_GO_READ_READY_PATH",
        "LOCAL_GO_READ_OUTAGE_RELEASE_PATH",
        'route.abort("blockedbyclient")',
        "FAIL go_read_browser:",
        "LOCAL-GO-READ-1-live.png",
        "LOCAL-GO-READ-1-outage.png",
    ):
        assert required in body
    assert body.count('main [role="alert"]') == 2


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


def test_write_browser_runner_covers_create_conflict_retry_and_outage():
    path = LOCAL_DIR / "run-write-browser.js"
    body = path.read_text(encoding="utf-8")

    subprocess.run(["node", "--check", str(path)], check=True)
    for required in (
        "create_result",
        "active_readback",
        "correct_result",
        "conflict_result",
        "field_team_result",
        "logout_result",
        "outage_result",
        "request_inventory",
        "forbiddenWrites.push",
        "writeExpected",
        "FAIL write_browser:",
        "conflict_reconciliation",
        "reload_result",
        "classifyProductRequest",
        "isForbiddenWrite",
        "authorizedRequestInit",
        "validateControlPath",
        "installResponseBoundary",
        # The body must be read BEFORE the read is recorded -- a pure test cannot
        # reach call ordering, so this is the declared fallback for it.
        "await response.clone().arrayBuffer()",
        "recordPlanningRead",
        "makePlanningFetchWrapper",
        # #160 HIGH-1: each context's OWN pre-logout refresh cookie must be the
        # revocation probe's input, and only integer statuses may be recorded.
        "smart_cms_refresh",
        "refresh_reuse_status",
        "contextRefreshCookie",
        "proveContextLogout",
        "assertRefreshShaped",
        "AbortSignal.timeout",
        # Credentials must be the bootstrap's canonical names, and the outage
        # must be coordinated rather than asserted.
        "MUNBON_OPERATOR_EMAIL",
        "MUNBON_FIELD_TEAM_EMAIL",
        "LOCAL_WRITE_UI_OUTAGE_RELEASE_FILE",
    ):
        assert required in body

    # The reload BEHAVIOUR is pinned behaviourally by
    # tests/test_write_browser_inventory.js::navigationSteps -- a substring check
    # here would survive a revert that left the surrounding comment intact.

    # The fabrications R2 removed must not creep back in. A source-string check
    # is weak evidence for behaviour, but it is exact evidence for absence --
    # provided it is asserted against the file the string actually lived in.
    for forbidden in (
        "reads_preserved",
        "LOCAL_OPERATOR_EMAIL",
        "LOCAL_OPERATOR_PASSWORD",
    ):
        assert forbidden not in body

    # The runbook is part of the deliverable and previously documented a
    # readiness model the code had already removed. Pin the corrected one, and
    # the absence of the claim that readiness comes from the container.
    runbook = (
        REPO_ROOT / "docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md"
    ).read_text(encoding="utf-8")
    assert (
        "Readiness is **neither** network quiescence **nor** any DOM element" in runbook
    )
    assert "readiness is taken from the product's own" not in runbook
    assert "the app's own roster and\nactive reads completing" in runbook

    # `safe_redirect` was only ever emitted by the PYTHON validator, so asserting
    # its absence from the browser source would be vacuous. Target the emitted
    # dict KEY, not the name -- the validator's docstring names it deliberately
    # to record what was removed and why.
    stage_suite_body = (
        REPO_ROOT / "ops/control-plan-read-local/run-stage-suite.py"
    ).read_text(encoding="utf-8")
    assert '"safe_redirect":' not in stage_suite_body


def test_all_stages_runbook_locks_local_before_aws_and_documents_current_commands():
    body = (
        REPO_ROOT / "docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md"
    ).read_text(encoding="utf-8")
    documented_candidate_commands = 11

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
        "orchestrate.py run-stage --stage LOCAL-GO-READ-1",
        "orchestrate.py run-stage --stage LOCAL-WRITE-FOUNDATION-1",
        "orchestrate.py run-stage --stage LOCAL-WRITE-UI-1",
        "orchestrate.py run-stage --stage LOCAL-PERSIST-ONLY-1",
        "orchestrate.py collect",
        "false → true → false",
        "bearer verification before `pm2 save`",
        "evidence-with-wildcard",
        "run-write-browser.js",
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
