import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

LOCAL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = LOCAL_DIR.parents[1]


def _workflow_job(workflow: str, job_name: str, next_job_name: str) -> str:
    return workflow.split(f"  {job_name}:\n", 1)[1].split(f"\n  {next_job_name}:\n", 1)[
        0
    ]


def _workflow_step(job: str, step_name: str) -> str:
    return job.split(f"      - name: {step_name}\n", 1)[1].split("\n      - name: ", 1)[
        0
    ]


def _workflow_step_env(step: str) -> dict[str, str]:
    env_block = step.split("        env:\n", 1)[1].split("\n        run:", 1)[0]
    return {
        key: value
        for line in env_block.splitlines()
        if (match := re.fullmatch(r"          ([A-Z][A-Z0-9_]*): (.+)", line))
        for key, value in [match.groups()]
    }


def _workflow_rollback_ids(step: str) -> list[str]:
    return re.findall(
        r"^          python migrations/migrate\.py rollback ([a-z0-9_]+)$",
        step,
        flags=re.MULTILINE,
    )


def test_scheduler_bare_pytest_job_provides_required_postgres_url():
    workflow = (
        REPO_ROOT / ".github/workflows/control-plane-hardening-tests.yml"
    ).read_text(encoding="utf-8")
    scheduler_job = _workflow_job(workflow, "scheduler-tests", "bff-tests")
    pytest_step = _workflow_step(
        scheduler_job, "Bare pytest (the gate); integration suites skip without a DB"
    )

    assert _workflow_step_env(pytest_step)["POSTGRES_URL"] == (
        "postgresql://ci-dummy:ci-dummy@ci-dummy:5432/ci_dummy"
    )


def test_scheduler_postgres_integration_provides_runtime_postgres_url():
    workflow = (
        REPO_ROOT / ".github/workflows/control-plane-hardening-tests.yml"
    ).read_text(encoding="utf-8")
    scheduler_job = _workflow_job(
        workflow, "scheduler-postgres-integration", "scada-gate-control-tests"
    )
    integration_step = _workflow_step(
        scheduler_job, "Env-gated control-plan integration suites (real Postgres)"
    )

    assert _workflow_step_env(integration_step)["POSTGRES_URL"] == (
        "postgresql://postgres:postgres@127.0.0.1:5432/scheduler_test"
    )


def test_scheduler_postgres_workflow_rolls_back_every_migration_in_reverse_order():
    workflow = (
        REPO_ROOT / ".github/workflows/control-plane-hardening-tests.yml"
    ).read_text(encoding="utf-8")
    scheduler_job = _workflow_job(
        workflow, "scheduler-postgres-integration", "scada-gate-control-tests"
    )
    migration_round_trip = scheduler_job.split(
        "python migrations/migrate.py apply-all", 1
    )[1].split("python migrations/migrate.py apply-all", 1)[0]
    rollback_ids = _workflow_rollback_ids(migration_round_trip)
    migration_ids = [
        path.name.removesuffix(".up.sql")
        for path in sorted(
            (REPO_ROOT / "services/scheduler/migrations").glob("*.up.sql")
        )
    ]

    assert rollback_ids == list(reversed(migration_ids))


def test_workflow_contract_ignores_commented_or_mis_scoped_values():
    assert _workflow_step_env(
        "        env:\n"
        "          # POSTGRES_URL: postgresql://comment-only\n"
        "          SCHEDULER_TEST_POSTGRES_URL: postgresql://test-only\n"
        "        run: python -m pytest -q\n"
    ) == {"SCHEDULER_TEST_POSTGRES_URL": "postgresql://test-only"}
    assert (
        _workflow_rollback_ids(
            "          # python migrations/migrate.py rollback 0013_comment_only\n"
            "        python migrations/migrate.py rollback 0012_wrong_indent\n"
        )
        == []
    )


def test_full_tree_baseline_lists_scheduler_legacy_ip_carrier():
    legacy_ip = "43.208." "201.191"
    carrier_path = (
        "services/scheduler/coding-logs/"
        "2026-07-18 Impl (pr-4-4a-2-runtime-readiness).md"
    )
    baseline = {
        line
        for line in (REPO_ROOT / ".security/full-tree-baseline.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line and not line.startswith("#")
    }

    if legacy_ip in (REPO_ROOT / carrier_path).read_text(encoding="utf-8"):
        assert carrier_path in baseline


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
        '"$#" != "7"',
        "MACHINE_NAME=munbon-control-plan-local",
        "MACHINE_NAME=munbon-control-plan-rehearsal",
        '"execution_kind":"rehearsal"',
        '"acceptance_evidence":false',
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
    assert "install-debian-closure-linux.sh" in body
    assert "--no-download" not in body
    assert body.index("--state ready") < body.index(
        'mv -- "${OWNER_TEMP}" "${STATE_ROOT}/owner.json"'
    )
    for match in re.finditer(r"postgres(?:ql)?://[^\s]+:[^\s]+@", body):
        assert "${" in match.group()


def test_bootstrap_keeps_secrets_private_and_prometheus_targets_readable():
    body = (LOCAL_DIR / "bootstrap-linux.sh").read_text(encoding="utf-8")
    target_paths = {
        "/etc/prometheus/control-plane-central-targets.json",
        "/etc/prometheus/control-plane-field-targets.json",
        "/etc/prometheus/control-plane-readiness-targets.json",
    }
    readable_mode = re.search(
        r"chmod 0644 \\\n(?P<paths>(?:  /etc/prometheus/control-plane-[^\n]+\\?\n?)+)",
        body,
    )

    assert 'chmod 600 "${SECRETS_FILE}"' in body
    assert 'chmod 600 "${RUNTIME_ENV_DIR}"/*.env' in body
    assert readable_mode is not None
    assert set(readable_mode.group("paths").replace("\\", "").split()) == target_paths
    assert (
        max(body.index(f"cat > {path}") for path in target_paths)
        < readable_mode.start()
    )


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


def test_campaign_ledger_ci_fetches_and_requires_the_base_commit():
    workflow = (
        REPO_ROOT / ".github/workflows/control-plane-hardening-tests.yml"
    ).read_text(encoding="utf-8")
    harness_job = workflow.split("  control-plan-local-harness-tests:", 1)[1].split(
        "\n  ros-postgis-integration:", 1
    )[0]

    assert "fetch-depth: 0" in harness_job
    assert 'git cat-file -e "${BASE_SHA}^{commit}"' in harness_job
    assert "campaign_ledger_base_commit_unavailable" in harness_job
    assert "ops/control-plan-read-local/tests/test_local_artifacts.py" in harness_job


def test_every_completed_stage_is_added_to_the_checksum_index():
    body = (LOCAL_DIR / "run-stage-suite.py").read_text(encoding="utf-8")

    # Ten PASS manifests plus the pre-validation browser result and any
    # failure manifest are all checksum-bound.
    assert body.count("_checksum_manifest(target)") == 12
    assert "_checksum_manifest(path)" in body
    assert "_verify_checksum_entry" in body
    assert "_save_state(context, list(STAGE_ORDER[:5]))" in body
    assert "_save_state(context, list(STAGE_ORDER[:6]))" in body
    assert "_save_state(context, list(STAGE_ORDER[:7]))" in body
    assert "_save_state(context, list(STAGE_ORDER[:8]))" in body
    assert "_save_state(context, list(STAGE_ORDER[:9]))" in body
    assert "_save_state(context, list(STAGE_ORDER))" in body


def test_stage_suite_uses_the_v5_hydraulic_release():
    body = (LOCAL_DIR / "run-stage-suite.py").read_text(encoding="utf-8")

    assert set(re.findall(r"engineering-prior-v\d+-v1\.json", body)) == {
        "engineering-prior-v5-v1.json"
    }


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


@pytest.mark.parametrize(
    "script_name",
    (
        "build-dependency-bundle-linux.sh",
        "validate-dependency-bundle-linux.sh",
        "bootstrap-linux.sh",
    ),
)
def test_node_runtime_version_checks_resolve_bundled_npm_without_ambient_node(
    script_name,
):
    body = (LOCAL_DIR / script_name).read_text(encoding="utf-8")

    assert re.search(
        r'env PATH="\$\{NODE_ROOT\}/bin:/usr/bin:/bin" \\\n'
        r'\s+"\$\{NODE_ROOT\}/bin/npm" --version',
        body,
    )


def test_bootstrap_failure_metadata_resolves_bundled_npm_without_ambient_node():
    body = (LOCAL_DIR / "bootstrap-provisioning-state.sh").read_text(encoding="utf-8")

    assert re.search(
        r'--tool-version "npm=\$\(env PATH="\$\{node_root\}/bin:/usr/bin:/bin" \\\n'
        r'\s+"\$\{node_root\}/bin/npm" --version',
        body,
    )


def test_dependency_builder_uses_apt_resolver_for_pristine_debian_closure():
    body = (LOCAL_DIR / "build-dependency-bundle-linux.sh").read_text(encoding="utf-8")

    assert "Dir::State::status=${APT_STATUS}" in body
    assert "Dir::Cache::archives=${BUNDLE_ROOT}/debian" in body
    assert "--download-only" in body
    assert "dpkg-scanpackages --multiversion" in body
    assert "package-specs.txt" in body
    assert "install-debian-closure-linux.sh" in body
    assert "apt-cache depends --recurse" not in body


def test_dependency_builder_requests_postgresql_15_postgis_extension_package():
    body = (LOCAL_DIR / "build-dependency-bundle-linux.sh").read_text(encoding="utf-8")
    apt_roots = re.search(r"APT_ROOTS=\(\n(?P<roots>.*?)\n\)", body, re.DOTALL)

    assert apt_roots is not None
    root_packages = apt_roots.group("roots").split()
    assert "postgresql-15-postgis-3" in root_packages
    assert "postgis" not in root_packages


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

    assert (
        'bash "${BUNDLE_ROOT}/install-debian-closure-linux.sh" '
        '--simulate "${BUNDLE_ROOT}/debian"' in body
    )
    assert "apt-get --simulate" not in body
    assert 'install "${BUNDLE_ROOT}"/debian/*.deb' not in body


def test_offline_debian_installer_uses_only_local_repo_and_exact_versions(tmp_path):
    installer = LOCAL_DIR / "install-debian-closure-linux.sh"
    repository = tmp_path / "debian"
    repository.mkdir()
    (repository / "Packages").write_text("Package: placeholder\n", encoding="utf-8")
    (repository / "Packages.gz").write_bytes(b"packages")
    (repository / "package-specs.txt").write_text(
        "perl-modules-5.36=5.36.0-7+deb12u3\npython3=3.11.2-1+b1\n",
        encoding="utf-8",
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture = tmp_path / "apt-calls.log"
    fake_apt_get = fake_bin / "apt-get"
    fake_apt_get.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf 'CALL' >> \"${APT_CAPTURE}\"\n"
        "source_list=\n"
        'for argument in "$@"; do\n'
        '  printf \' <%s>\' "${argument}" >> "${APT_CAPTURE}"\n'
        '  case "${argument}" in\n'
        '    Dir::Etc::sourcelist=*) source_list="${argument#*=}" ;;\n'
        "  esac\n"
        "done\n"
        "printf '\\n' >> \"${APT_CAPTURE}\"\n"
        'if [[ -n "${source_list}" ]]; then\n'
        "  printf 'SOURCE ' >> \"${APT_CAPTURE}\"\n"
        '  cat "${source_list}" >> "${APT_CAPTURE}"\n'
        "fi\n",
        encoding="utf-8",
    )
    fake_apt_get.chmod(0o755)

    subprocess.run(
        ["bash", str(installer), "--simulate", str(repository)],
        check=True,
        env={
            **os.environ,
            "APT_CAPTURE": str(capture),
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
        },
    )

    calls = capture.read_text(encoding="utf-8")
    assert f"SOURCE deb [trusted=yes] file:{repository} ./\n" in calls
    assert "<Dir::Etc::main=/dev/null>" in calls
    assert "<Dir::Etc::parts=->" in calls
    assert "<update> <-qq>" in calls
    assert "<install> <--simulate> <--no-install-recommends>" in calls
    assert "<perl-modules-5.36=5.36.0-7+deb12u3>" in calls
    assert "<python3=3.11.2-1+b1>" in calls
    assert "--no-download" not in calls
    assert ".deb>" not in calls


def test_offline_debian_installer_rejects_option_shaped_package_specs(tmp_path):
    installer = LOCAL_DIR / "install-debian-closure-linux.sh"
    repository = tmp_path / "debian"
    repository.mkdir()
    (repository / "Packages").write_text("Package: placeholder\n", encoding="utf-8")
    (repository / "Packages.gz").write_bytes(b"packages")
    (repository / "package-specs.txt").write_text(
        "--allow-unauthenticated=true\n", encoding="utf-8"
    )

    result = subprocess.run(
        ["bash", str(installer), "--simulate", str(repository)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert (result.returncode, result.stdout, result.stderr) == (
        1,
        "",
        "FAIL offline_debian_installer_package_specs\n",
    )


def test_offline_debian_installer_allows_only_exact_local_downgrades(tmp_path):
    installer = LOCAL_DIR / "install-debian-closure-linux.sh"
    repository = tmp_path / "debian"
    repository.mkdir()
    (repository / "Packages").write_text("Package: example\n", encoding="utf-8")
    (repository / "Packages.gz").write_bytes(b"packages")
    (repository / "package-specs.txt").write_text("example=1.0\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture = tmp_path / "apt-calls.log"
    fake_apt_get = fake_bin / "apt-get"
    fake_apt_get.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf 'CALL' >> \"${APT_CAPTURE}\"\n"
        'for argument in "$@"; do\n'
        '  printf \' <%s>\' "${argument}" >> "${APT_CAPTURE}"\n'
        "done\n"
        "printf '\\n' >> \"${APT_CAPTURE}\"\n",
        encoding="utf-8",
    )
    fake_apt_get.chmod(0o755)
    fake_id = fake_bin / "id"
    fake_id.write_text("#!/usr/bin/env bash\nprintf '0\\n'\n", encoding="utf-8")
    fake_id.chmod(0o755)

    subprocess.run(
        ["bash", str(installer), "--install", str(repository)],
        check=True,
        env={
            **os.environ,
            "APT_CAPTURE": str(capture),
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
        },
    )

    calls = capture.read_text(encoding="utf-8")
    assert (
        "<install> <-y> <-qq> <--allow-downgrades> "
        "<--no-install-recommends> <example=1.0>" in calls
    )


def test_python_closure_lock_content_addresses_all_arm64_wheel_sets():
    lock_path = LOCAL_DIR / "python-closures.lock"
    locked_closures = [
        tuple(line.split())
        for line in lock_path.read_text(encoding="utf-8").splitlines()
    ]
    service_order = (
        "flow-monitoring",
        "scheduler",
        "ros-gis-integration",
        "bff-water-planning",
    )
    measured_closures = []

    assert tuple(service for service, _, _ in locked_closures) == service_order
    for service, _, _ in locked_closures:
        receipt_lines = (
            (LOCAL_DIR / "python-closure-receipts" / f"{service}.sha256")
            .read_bytes()
            .splitlines(keepends=True)
        )
        assert all(
            re.fullmatch(rb"[0-9a-f]{64}  \./[A-Za-z0-9_.+-]+\.whl\n", receipt_line)
            for receipt_line in receipt_lines
        )
        assert receipt_lines == sorted(
            receipt_lines, key=lambda line: line.split(b"  ", 1)[1]
        )
        measured_closures.append(
            (
                service,
                hashlib.sha256(b"".join(receipt_lines)).hexdigest(),
                str(len(receipt_lines)),
            )
        )

    assert locked_closures == measured_closures


def test_bootstrap_validates_and_stages_dependencies_before_runtime_reset():
    body = (LOCAL_DIR / "bootstrap-linux.sh").read_text(encoding="utf-8")

    staged = body.index("phase dependency_staged")
    reset = body.index("phase postgres_redis")
    assert staged < reset


def test_bootstrap_writes_scheduler_dark_preflight_contract():
    body = (LOCAL_DIR / "bootstrap-linux.sh").read_text(encoding="utf-8")
    scheduler_environment = body.split(
        'cat > "${RUNTIME_ENV_DIR}/scheduler.env" <<EOF\n', 1
    )[1].split("\nEOF", 1)[0]
    values = dict(line.split("=", 1) for line in scheduler_environment.splitlines())

    assert {
        "CONTROL_EXECUTION_MODE": values.get("CONTROL_EXECUTION_MODE"),
        "CONTROL_READBACK_RECONCILIATION_MODE": values.get(
            "CONTROL_READBACK_RECONCILIATION_MODE"
        ),
    } == {
        "CONTROL_EXECUTION_MODE": "disabled",
        "CONTROL_READBACK_RECONCILIATION_MODE": "off",
    }


def test_bootstrap_budgets_every_rate_counted_rc_write_request():
    body = (LOCAL_DIR / "bootstrap-linux.sh").read_text(encoding="utf-8")
    bff_environment = body.split('cat > "${RUNTIME_ENV_DIR}/bff.env" <<EOF\n', 1)[
        1
    ].split("\nEOF", 1)[0]
    values = dict(line.split("=", 1) for line in bff_environment.splitlines())
    stage_request_counts = {
        "write_foundation": 3,
        "write_ui": 3,
        "persist_only": 2,
        "write_activation": 3,
    }

    assert values.get("PLANNING_DEPTH_WRITE_LIMIT") == str(
        sum(stage_request_counts.values())
    )


def test_bootstrap_records_state_before_dependencies_and_installs_python_before_transition():
    body = (LOCAL_DIR / "bootstrap-linux.sh").read_text(encoding="utf-8")

    initial_state = body.index("write_bootstrap_state")
    outer_checksum = body.index("phase dependency_archive")
    inner_checksum = body.index("substep inner-checksum")
    offline_packages = body.index(
        'bash "${DEPENDENCY_ROOT}/install-debian-closure-linux.sh" '
        '--install "${DEPENDENCY_ROOT}/debian"'
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


def test_bootstrap_delegates_offline_debian_install_to_bundle_installer():
    body = (LOCAL_DIR / "bootstrap-linux.sh").read_text(encoding="utf-8")

    assert (
        'bash "${DEPENDENCY_ROOT}/install-debian-closure-linux.sh" '
        '--install "${DEPENDENCY_ROOT}/debian"' in body
    )
    assert '"${DEPENDENCY_ROOT}"/debian/*.deb' not in body
    assert "--no-download" not in body


@pytest.mark.parametrize(
    ("sql_statement", "expected_substep"),
    (
        (
            "ALTER ROLE munbon_local PASSWORD :'database_password';",
            "substep postgres-role",
        ),
        (
            "CREATE EXTENSION IF NOT EXISTS postgis;",
            "substep postgis-extension",
        ),
    ),
)
def test_bootstrap_postgres_setup_fails_closed_on_sql_errors(
    sql_statement, expected_substep
):
    body = (LOCAL_DIR / "bootstrap-linux.sh").read_text(encoding="utf-8")
    statement_offset = body.index(sql_statement)
    invocation_offset = body.rfind("runuser -u postgres -- psql", 0, statement_offset)
    assert invocation_offset != -1

    invocation = body[invocation_offset : body.index("<<'SQL'", invocation_offset)]
    substep_offset = body.rfind(expected_substep, 0, invocation_offset)
    assert substep_offset != -1
    assert body.rfind("substep ", substep_offset, invocation_offset) == substep_offset
    assert "--set=ON_ERROR_STOP=1" in invocation


def test_orchestrator_embeds_offline_debian_installer_in_dependency_bundle():
    body = (LOCAL_DIR / "orchestrate.py").read_text(encoding="utf-8")

    assert 'local_dir / "install-debian-closure-linux.sh"' in body
    assert 'f"{remote_root}/install-debian-closure-linux.sh"' in body


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
    assert 'owner.get("state") == "ready"' in body
    assert "_validate_execution_owner(context, owner)" in body
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
    assert "_validate_execution_owner(context, owner)" in base_body
    owner_start = body.index("def _validate_execution_owner")
    owner_end = body.index("\ndef _verify_source_checkouts", owner_start)
    owner_body = body[owner_start:owner_end]
    assert 'owner.get("state") == "ready"' in owner_body
    assert 'owner.get("dependency_sha256", "")' in owner_body
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
    level_two_headings = [
        (line_number, match.group(1).strip())
        for line_number, line in enumerate(body.splitlines())
        if (
            match := re.fullmatch(
                r" {0,3}##\s+(.+?)(?:\s+#+)?\s*",
                line,
            )
        )
    ]
    promotion_headings = [
        line_number
        for line_number, title in level_two_headings
        if title == "Promotion sequence"
    ]
    provision_headings = [
        line_number for line_number, title in level_two_headings if title == "Provision"
    ]
    assert len(promotion_headings) == 1
    assert len(provision_headings) == 1
    assert promotion_headings[0] < provision_headings[0]
    promotion_table = body.splitlines()[
        promotion_headings[0] + 1 : provision_headings[0]
    ]
    promotion_rows = []
    for line in promotion_table:
        if not line.lstrip().startswith("|") or "LOCAL-" not in line:
            continue
        match = re.fullmatch(
            r" {0,3}\|\s*[^|]+?\s*\|\s*`(?P<stage>LOCAL-[A-Z0-9-]+)`\s*"
            r"\|\s*(?P<status>[^|]+?)\s*\|\s*",
            line,
        )
        assert match is not None
        promotion_rows.append((match.group("stage"), match.group("status")))
    current_result = body.split("## Current local result\n", maxsplit=1)[1].split(
        "\n### Historical three-stage result", maxsplit=1
    )[0]

    assert promotion_rows == [
        ("LOCAL-BASE-0", "Implemented and passed"),
        ("LOCAL-RTA-1", "Implemented and passed"),
        ("LOCAL-AC-1", "Implemented and passed"),
        ("LOCAL-READ-ACT-1", "Implemented and passed"),
        ("LOCAL-EVIDENCE-1", "Implemented and passed"),
        ("LOCAL-GO-READ-1", "Implemented and passed"),
        ("LOCAL-WRITE-FOUNDATION-1", "Implemented; prior SHA passed"),
        ("LOCAL-WRITE-UI-1", "Implemented; latest campaign passed"),
        ("LOCAL-PERSIST-ONLY-1", "Implemented; latest campaign passed"),
        ("LOCAL-WRITE-ACT-1", "Implemented in source; not yet accepted"),
        ("LOCAL-RC-1", "Implemented in source; not yet accepted"),
    ]

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
        "orchestrate.py run-stage --stage LOCAL-WRITE-ACT-1",
        "orchestrate.py collect",
        "orchestrate.py run-rc",
        "orchestrate.py collect-rc",
        "orchestrate.py collect-rc-partial-failure",
        "RC-SHA256SUMS",
        "RC-OUTER-SHA256SUMS",
        "RC-PARTIAL-SHA256SUMS",
        "RC-PARTIAL-OUTER-SHA256SUMS",
        "acceptance_evidence=false",
        "campaign_ledger_eligible=false",
        "does not authorize guest creation, replacement, repair, deployment, activation, or AWS action",
        "munbon-control-plan-rehearsal",
        "orchestrate.py provision-rehearsal",
        "orchestrate.py run-rehearsal-stage --stage LOCAL-BASE-0",
        "orchestrate.py run-rehearsal-stage --stage LOCAL-RTA-1",
        "orchestrate.py run-rehearsal-stage --stage LOCAL-AC-1",
        "orchestrate.py collect-rehearsal",
        "orchestrate.py collect-rehearsal-partial-failure",
        "orchestrate.py collect-rehearsal-bootstrap-failure",
        "REHEARSAL-OUTER-SHA256SUMS",
        "REHEARSAL-PARTIAL-OUTER-SHA256SUMS",
        "REHEARSAL-BOOTSTRAP-OUTER-SHA256SUMS",
        "REHEARSAL-SHA256SUMS",
        "REHEARSAL-SUMMARY.json",
        "acceptance_evidence=false",
        "false → true → false",
        "bearer verification before `pm2 save`",
        "evidence-with-wildcard",
        "run-write-browser.js",
    ):
        assert required in body
    assert Counter(
        re.findall(
            r"^python3 ops/control-plan-read-local/orchestrate\.py ([a-z-]+)\b",
            body,
            flags=re.MULTILINE,
        )
    ) == Counter(
        {
            "build-dependencies": 1,
            "provision-rehearsal": 1,
            "run-rehearsal-stage": 3,
            "collect-rehearsal": 1,
            "collect-rehearsal-partial-failure": 1,
            "collect-rehearsal-bootstrap-failure": 1,
            "provision": 1,
            "collect-bootstrap-failure": 1,
            "run-stage": 10,
            "run-rc": 1,
            "collect-rc": 1,
            "collect-rc-partial-failure": 1,
            "collect": 1,
        }
    )
    assert body.count('--as-of-date "$rehearsal_as_of_date"') == 5
    for required in (
        "accepted_frontend_sha=REPLACE_WITH_ACCEPTED_40_CHARACTER_FRONTEND_SHA",
        "Historical frontend SHAs below are evidence identities, not reusable defaults.",
        "All ten current local acceptance stages are implemented in source",
        "Neither `LOCAL-WRITE-ACT-1` nor `LOCAL-RC-1` has been run or accepted",
        "The current candidate has genuine 9/9 local acceptance evidence",
        "2026-08-20-nine-stage-orbstack-7f032c4c-attempt-1",
        "7f032c4c20e7f9cdd443d64f7adbeb37342ff190",
        "01M0F27Z1GZQ7SQF07XH9M3VQT",
        "903602d8ae622c5de72ffa31c705782ae663dfd6dc9a53d4450c6aa5e0c1bbef",
        "585467a896065b42a40982eb08c1f3447e1b5439928bcca50fc471a7595e51aa",
        "successful_closed",
        "Another rehearsal or canonical campaign requires a new separate authorization.",
        "A rehearsal grant does not authorize canonical guest replacement",
        "Provisioning already collects and finalizes this bundle automatically",
        "only the ordered `LOCAL-BASE-0 → LOCAL-RTA-1 → LOCAL-AC-1` prefix",
        "cannot satisfy `successful_closed`",
        "Guest replacement, deployment, and activation remain separately authorized actions.",
        "Every authorized campaign outcome, success or failure, must extend the campaign",
        "This 9/9 result grants no",
        "still requires a separately authorized passing `LOCAL-RC-1`",
        "promotion and AWS authorization.",
    ):
        assert required in body
    assert "accepted_frontend_sha=fbd4ce4df0bb0476b7cd402ac1a4e180a91a7792" not in body
    assert "No current candidate has genuine 9/9 acceptance evidence." not in body
    assert "before implementing `LOCAL-WRITE-UI-1`" not in body
    assert (
        "Only genuine 9/9 evidence from one pristine authorized guest may extend"
        not in body
    )
    assert "2ee640c5eed939b68035c7695a4c129570e9ca5a" not in body
    for required in (
        "**9 passed / 0 failed /\n0 unreached**",
        "2026-08-20-nine-stage-orbstack-7f032c4c-attempt-1",
        "7f032c4c20e7f9cdd443d64f7adbeb37342ff190",
        "067b3e22401854f8c6d6db42dc0c5c1872fca6f8",
        "89a26cbd783b21037acd3ce2f1e116f0e69ba8ea0d1667be8b6fda22a1aef7ab",
        "01M0F27Z1GZQ7SQF07XH9M3VQT",
        "attempt 1 of 1",
        "failed and unreached stages: none",
        "final visibility, submit, execution, authority, and write flags: false",
        "../munbon-control-plan-9of9-evidence/2026-08-20-nine-stage-orbstack-7f032c4c-attempt-1/",
        "903602d8ae622c5de72ffa31c705782ae663dfd6dc9a53d4450c6aa5e0c1bbef",
        "585467a896065b42a40982eb08c1f3447e1b5439928bcca50fc471a7595e51aa",
    ):
        assert required in current_result


def test_all_stages_runbook_records_source_delivery_without_runtime_acceptance():
    body = (
        REPO_ROOT / "docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md"
    ).read_text(encoding="utf-8")
    source_delivery = body.split("## Source delivery status\n", maxsplit=1)[1].split(
        "\n## ", maxsplit=1
    )[0]

    for required in (
        "PR #193",
        "86f7bc293277277010a64a2751d56fbeeb9e4172",
        "3e038caec2909665266905aa00beff5e78299dc0",
        "661 Python tests and 51 Node tests passed in each of three consecutive rounds",
        "formal g-check snapshot `2026-08-20/2218` was clean",
        "PR #194",
        "75408f8f8c83c48bccc5b9e64c67b8124281cdd3",
        "fa588d285932569147038ff8209961b8cf965dd4",
        "818 Python tests and 51 Node tests passed in each of three consecutive rounds",
        "formal g-check snapshot `2026-08-21/0339` was clean",
        "No guest command or fresh exact-SHA acceptance run was performed",
        "No authoritative `LOCAL-WRITE-ACT-1` or `LOCAL-RC-1` acceptance is claimed",
        "does not authorize or perform guest creation, guest replacement, live guest operations",
        "AWS inventory or action, promotion, deployment, activation, post-deployment verification, or rollback execution",
        "The historical campaign ledger remains frozen at nine stages",
        "Its existing 9/9 rows are not redefined by the ten-stage live order or by the `LOCAL-RC-1` wrapper",
    ):
        assert required in source_delivery
