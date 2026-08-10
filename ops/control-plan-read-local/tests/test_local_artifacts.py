import json
import re
import subprocess
import sys
from pathlib import Path

LOCAL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = LOCAL_DIR.parents[1]


def test_bootstrap_is_valid_bash_and_provisions_only_isolated_manifests():
    path = LOCAL_DIR / "bootstrap-linux.sh"
    body = path.read_text(encoding="utf-8")
    state_helper_body = (LOCAL_DIR / "bootstrap-provisioning-state.sh").read_text(
        encoding="utf-8"
    )
    provisioning_body = body + state_helper_body

    subprocess.run(["bash", "-n", str(path)], check=True)
    assert "\ncd /\n" in body
    for required in (
        "postgresql",
        "postgis",
        "redis-server",
        "prometheus",
        "python3 -m venv",
        "requirements.txt",
        "--no-index",
        "--find-links",
        "DEPENDENCY_ROOT=/opt/munbon/dependencies",
        "provisioning_contract.py",
        '--tool-version "bash=',
        '--tool-version "node=',
        '--tool-version "npm=',
        '--tool-version "python=',
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
        "playwright-browsers",
        "frontend.bundle",
        '"frontend_sha":"${FRONTEND_SHA}"',
        'mv -- "${OWNER_TEMP}" "${STATE_ROOT}/owner.json"',
        "run-read-browser.js",
        "run-evidence-browser.js",
        "run-go-read-browser.js",
        "services/scada-gate-control",
        "services/scada-gate-control-web",
        "node-modules/${name}.tar.gz",
        "validate-node-archive",
        "checkout --force --quiet",
        "evidence-archive",
        "pg_terminate_backend",
        "dropdb --if-exists munbon_local",
        "redis-cli FLUSHALL",
        '"${BROWSER_ROOT}/node_modules/pm2/bin/pm2"',
    ):
        assert required in provisioning_body
    assert "pip install --user" not in body
    assert "sudo pip" not in body
    assert "apt-get update" not in body
    assert "npm install --global" not in body
    assert "npm_offline_ci" not in body
    assert "prisma generate" not in body
    assert "https://nodejs.org" not in body
    assert "https://repos.influxdata.com" not in body
    assert "--no-download --no-install-recommends" in body
    assert body.index("--state ready") < body.index(
        'mv -- "${OWNER_TEMP}" "${STATE_ROOT}/owner.json"'
    )
    for match in re.finditer(r"postgres(?:ql)?://[^\s]+:[^\s]+@", body):
        assert "${" in match.group()


def test_orchestrator_provisions_every_local_ac_harness_artifact():
    body = (LOCAL_DIR / "orchestrate.py").read_text(encoding="utf-8")

    for required in (
        "bootstrap-provisioning-state.sh",
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
        "ExecStart=/opt/node-v22.23.1-linux-arm64/bin/node src/index.js",
        "NoNewPrivileges=true",
    ):
        assert required in body
    assert "password" not in body.lower()


def test_dependency_roots_lock_exact_pm2_and_playwright_versions():
    root = LOCAL_DIR / "dependency-roots"
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))

    assert package["dependencies"] == {"playwright": "1.54.2", "pm2": "5.4.3"}
    assert lock["packages"][""]["dependencies"] == package["dependencies"]
    assert lock["packages"]["node_modules/playwright"]["version"] == "1.54.2"
    assert lock["packages"]["node_modules/pm2"]["version"] == "5.4.3"


def test_dependency_builder_produces_content_addressed_arm64_closure():
    path = LOCAL_DIR / "build-dependency-bundle-linux.sh"
    body = path.read_text(encoding="utf-8")

    subprocess.run(["bash", "-n", str(path)], check=True)
    for required in (
        "aarch64",
        "debian",
        "22.23.1",
        "10.9.8",
        "pip wheel",
        "node-modules",
        "package-lock.json",
        "requirements.txt",
        "python-closures.lock",
        "dependency_bundle_python_closure",
        "prisma generate",
        "VALIDATOR_SCRIPT",
        "validate-node-archive",
        "unshare -n",
        "playwright-browsers",
        "sha256sum",
        "manifest.json",
        "SHA256SUMS",
    ):
        assert required in body
    assert "--no-install-recommends" in body


def test_dependency_builder_uses_apt_resolver_for_pristine_debian_closure():
    body = (LOCAL_DIR / "build-dependency-bundle-linux.sh").read_text(encoding="utf-8")

    assert "Dir::State::status=${APT_STATUS}" in body
    assert "Dir::Cache::archives=${BUNDLE_ROOT}/debian" in body
    assert "--download-only" in body
    assert "apt-cache depends --recurse" not in body


def test_dependency_validator_exercises_every_closure_without_network():
    path = LOCAL_DIR / "validate-dependency-bundle-linux.sh"
    body = path.read_text(encoding="utf-8")

    subprocess.run(["bash", "-n", str(path)], check=True)
    for required in (
        "npm_config_offline=true",
        "--no-index",
        "--find-links",
        "python",
        "playwright-browsers",
        "dpkg-deb --info",
        "pip check",
        'NODE_ROOT="${SCRATCH_ROOT}/node"',
        " ls --all",
        "node-modules",
        "validate-node-archive",
        "require('bcrypt')",
        "require('@prisma/client')",
    ):
        assert required in body
    assert '"${NODE_ROOT}/bin/npm" --prefix "${target_root}" ci' not in body


def test_dependency_validator_simulates_complete_offline_debian_install():
    body = (LOCAL_DIR / "validate-dependency-bundle-linux.sh").read_text(
        encoding="utf-8"
    )

    assert "apt-get --simulate" in body
    assert "--no-download" in body
    assert 'install "${BUNDLE_ROOT}"/debian/*.deb' in body


def test_python_closure_lock_content_addresses_all_arm64_wheel_sets():
    lock_path = LOCAL_DIR / "python-closures.lock"
    lines = lock_path.read_text(encoding="utf-8").splitlines()

    assert [line.split()[0] for line in lines] == [
        "flow-monitoring",
        "scheduler",
        "ros-gis-integration",
        "bff-water-planning",
    ]
    for line in lines:
        service, digest, count = line.split()
        assert service
        assert re.fullmatch(r"[0-9a-f]{64}", digest)
        assert int(count) > 0


def test_bootstrap_validates_and_stages_dependencies_before_runtime_reset():
    body = (LOCAL_DIR / "bootstrap-linux.sh").read_text(encoding="utf-8")

    staged = body.index("phase dependency_staged")
    reset = body.index("phase postgres_redis")
    assert staged < reset


def test_bootstrap_records_state_before_dependencies_and_installs_python_before_transition():
    body = (LOCAL_DIR / "bootstrap-linux.sh").read_text(encoding="utf-8")

    initial_state = body.index("write_bootstrap_state")
    outer_checksum = body.index("phase dependency_archive")
    inner_checksum = body.index("substep inner-checksum")
    offline_packages = body.index(
        "apt-get install -y -qq --no-download --no-install-recommends"
    )
    dependency_staged = body.index("phase dependency_staged")

    assert (
        initial_state
        < outer_checksum
        < inner_checksum
        < offline_packages
        < dependency_staged
    )
    assert "write_bootstrap_failure" in body
    assert "write_pre_python_failure" in (
        LOCAL_DIR / "bootstrap-provisioning-state.sh"
    ).read_text(encoding="utf-8")


def test_pre_python_failure_writer_emits_collectable_checksum_bound_state(tmp_path):
    helper = LOCAL_DIR / "bootstrap-provisioning-state.sh"
    state_root = tmp_path / "provisioning"
    release_sha = "1" * 40
    frontend_sha = "2" * 40
    dependency_sha = "3" * 64

    subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; '
            'write_bootstrap_state "$2" created "$3" "$4" "$5" bootstrap arguments; '
            'write_pre_python_failure "$2" "$3" "$4" "$5" '
            "base_packages offline-debian-packages 1 false",
            "bootstrap-state-test",
            str(helper),
            str(state_root),
            release_sha,
            frontend_sha,
            dependency_sha,
        ],
        check=True,
    )

    state = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
    metadata = json.loads(
        (state_root / "failure" / "metadata.json").read_text(encoding="utf-8")
    )
    assert state | {"recorded_at": "ignored"} == {
        "dependency_sha256": dependency_sha,
        "frontend_sha": frontend_sha,
        "phase": "base_packages",
        "recorded_at": "ignored",
        "release_sha": release_sha,
        "state": "failed",
        "substep": "offline-debian-packages",
    }
    assert metadata | {"recorded_at": "ignored"} == {
        "classification": "nonretryable-bootstrap",
        "dependency_sha256": dependency_sha,
        "exit_code": 1,
        "frontend_sha": frontend_sha,
        "phase": "base_packages",
        "recorded_at": "ignored",
        "release_sha": release_sha,
        "state": "failed",
        "substep": "offline-debian-packages",
        "tool_versions": metadata["tool_versions"],
    }
    assert re.fullmatch(r"[0-9.]+", metadata["tool_versions"]["bash"])
    checksum_result = subprocess.run(
        ["sha256sum", "--check", "--strict", "SHA256SUMS"],
        cwd=state_root / "failure",
        check=True,
        capture_output=True,
        text=True,
    )
    assert checksum_result.stdout.splitlines() == [
        "bootstrap-sanitized.log: OK",
        "metadata.json: OK",
    ]
    assert (state_root / "failure" / "bootstrap-sanitized.log").read_text() == (
        "FAIL bootstrap_base_packages\n"
    )
    helper_body = helper.read_text(encoding="utf-8")
    assert "python3" not in helper_body
    assert "/usr/bin/python" not in helper_body


def test_shell_created_state_transitions_with_installed_python_contract(tmp_path):
    helper = LOCAL_DIR / "bootstrap-provisioning-state.sh"
    contract = LOCAL_DIR / "provisioning_contract.py"
    state_root = tmp_path / "provisioning"
    release_sha = "1" * 40
    frontend_sha = "2" * 40
    dependency_sha = "3" * 64

    subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; '
            'write_bootstrap_state "$2" created "$3" "$4" "$5" bootstrap arguments',
            "bootstrap-state-test",
            str(helper),
            str(state_root),
            release_sha,
            frontend_sha,
            dependency_sha,
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(contract),
            "state",
            "--state-root",
            str(state_root),
            "--state",
            "dependency-staged",
            "--release-sha",
            release_sha,
            "--frontend-sha",
            frontend_sha,
            "--dependency-sha256",
            dependency_sha,
            "--phase",
            "dependency-staged",
            "--substep",
            "complete",
        ],
        check=True,
    )

    state = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
    assert (state["state"], state["phase"], state["substep"]) == (
        "dependency-staged",
        "dependency-staged",
        "complete",
    )


def test_stage_baseline_uses_nonsecret_owner_attestation_not_private_failure_state():
    body = (LOCAL_DIR / "run-stage-suite.py").read_text(encoding="utf-8")

    assert 'Path("/var/lib/munbon-local-acceptance/owner.json")' in body
    assert (
        'Path("/var/lib/munbon-local-acceptance/provisioning/state.json")' not in body
    )
    assert 'owner.get("state") != "ready"' in body
    assert "--no-index" in body
    assert "--find-links" in body
    assert "npm install --global" not in body
    assert "/usr/bin/node" not in body
    assert "playwright install --with-deps chromium" not in body


def test_stage_suite_revalidates_manifests_offline_with_pinned_node():
    body = (LOCAL_DIR / "run-stage-suite.py").read_text(encoding="utf-8")

    install_start = body.index("def _install_manifests")
    install_end = body.index("\ndef _apply_migrations", install_start)
    install_body = body[install_start:install_end]
    preflight_start = body.index("def _monitoring_preflight")
    preflight_end = body.index("\ndef _actual_gate_environment", preflight_start)
    preflight_body = body[preflight_start:preflight_end]
    assert "--no-index" in install_body
    assert "--find-links" in install_body
    assert 'str(NODE_ROOT / "bin/npm")' in preflight_body
    assert 'str(NODE_ROOT / "bin/node")' in preflight_body
    assert '["npm"' not in preflight_body
    assert '["node"' not in preflight_body


def test_local_base_binds_ready_state_and_dependency_environment_digest():
    body = (LOCAL_DIR / "run-stage-suite.py").read_text(encoding="utf-8")
    start = body.index("def run_local_base")
    end = body.index("\ndef _install_manifests", start)
    base_body = body[start:end]

    assert "/var/lib/munbon-local-acceptance/owner.json" in base_body
    assert 'owner.get("state") != "ready"' in base_body
    assert 'owner.get("dependency_sha256", "")' in base_body
    assert '"dependency_bundle_sha256"' in base_body


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
        "provePageOriginLogout",
        "pageOriginLogout",
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
    documented_candidate_commands = 12

    for required in (
        "LOCAL-BASE-0",
        "LOCAL-RTA-1",
        "LOCAL-RC-1",
        "native `arm64`",
        "No AWS action",
        "orchestrate.py provision",
        "orchestrate.py build-dependencies",
        "orchestrate.py collect-bootstrap-failure",
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
