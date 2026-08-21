import ast
from contextlib import contextmanager
import dataclasses
from datetime import date, timedelta
import importlib.util
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "run-stage-suite.py"
SPEC = importlib.util.spec_from_file_location(
    "control_plan_local_stage_suite", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
stage_suite = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = stage_suite
SPEC.loader.exec_module(stage_suite)

SEED_MODULE_PATH = Path(__file__).resolve().parents[1] / "seed-approved-sources.py"
SEED_SPEC = importlib.util.spec_from_file_location(
    "local_approved_sources_for_stage_suite", SEED_MODULE_PATH
)
assert SEED_SPEC is not None and SEED_SPEC.loader is not None
approved_sources = importlib.util.module_from_spec(SEED_SPEC)
SEED_SPEC.loader.exec_module(approved_sources)

# Sections 3..43 is the roster size the BFF hard-requires
# (planning_depth_submission.validate_canonical_roster). The section range and
# the 01-NN area-id format are restated here -- the seed module does not export
# either -- so this pins the section->zone MAPPING only. A change to the roster
# size or to the area-id format is NOT caught here.
SEEDED_SECTION_NUMBERS = range(3, 44)


def test_validate_runtime_urls_accepts_only_exact_loopback_http_endpoints():
    urls = {
        "flow": "http://127.0.0.1:3011",
        "scheduler": "http://127.0.0.1:3021",
        "ros": "http://127.0.0.1:3047",
        "bff": "http://127.0.0.1:3022",
        "auth": "http://127.0.0.1:3005",
    }

    assert stage_suite.validate_runtime_urls(urls) == urls


def test_safe_subprocess_failure_code_accepts_one_code_only_line():
    assert (
        stage_suite.safe_subprocess_failure_code(
            "browser noise\nFAIL evidence_browser: forbidden_product_request_observed\n",
            "FAIL evidence_browser: ",
        )
        == "forbidden_product_request_observed"
    )
    assert (
        stage_suite.safe_subprocess_failure_code(
            "FAIL evidence_browser: invalid code with spaces\n",
            "FAIL evidence_browser: ",
        )
        is None
    )
    assert (
        stage_suite.safe_subprocess_failure_code(
            "FAIL evidence_browser: first_failure\n"
            "FAIL evidence_browser: second_failure\n",
            "FAIL evidence_browser: ",
        )
        is None
    )


def test_only_evidence_browser_propagates_validated_child_failure_codes():
    evidence_source = inspect.getsource(stage_suite._run_evidence_browser)
    read_source = inspect.getsource(stage_suite._run_read_browser)

    assert 'safe_error_prefix="FAIL evidence_browser: "' in evidence_source
    assert "safe_error_prefix" not in read_source


def test_run_checked_propagates_one_validated_child_failure_code(monkeypatch):
    monkeypatch.setattr(
        stage_suite.subprocess,
        "run",
        lambda *_args, **_kwargs: stage_suite.subprocess.CompletedProcess(
            args=["node"],
            returncode=1,
            stdout="",
            stderr="FAIL evidence_browser: forbidden_product_request_observed\n",
        ),
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="^forbidden_product_request_observed$",
    ):
        stage_suite._run_checked(
            "evidence_browser_visible",
            ["node"],
            safe_error_prefix="FAIL evidence_browser: ",
        )


@pytest.mark.parametrize(
    "stderr",
    [
        "FAIL evidence_browser: invalid code\n",
        (
            "FAIL evidence_browser: first_failure\n"
            "FAIL evidence_browser: second_failure\n"
        ),
        "secret=value\n",
    ],
)
def test_run_checked_falls_back_for_unaccepted_child_stderr(monkeypatch, stderr):
    monkeypatch.setattr(
        stage_suite.subprocess,
        "run",
        lambda *_args, **_kwargs: stage_suite.subprocess.CompletedProcess(
            args=["node"],
            returncode=1,
            stdout="",
            stderr=stderr,
        ),
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="^evidence_browser_visible_failed$",
    ):
        stage_suite._run_checked(
            "evidence_browser_visible",
            ["node"],
            safe_error_prefix="FAIL evidence_browser: ",
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:3011",
        "http://localhost:3011",
        "http://192.168.1.1:3011",
        "http://127.0.0.1:3011/path",
        "http://user:password@127.0.0.1:3011",
    ],
)
def test_validate_runtime_urls_rejects_noncanonical_or_credentialed_urls(url):
    with pytest.raises(stage_suite.StageGateError, match="runtime_url_not_loopback"):
        stage_suite.validate_runtime_urls({"service": url})


def test_stage_transition_requires_each_progressive_local_gate():
    stage_suite.validate_stage_transition((), "LOCAL-BASE-0")
    stage_suite.validate_stage_transition(("LOCAL-BASE-0",), "LOCAL-RTA-1")
    stage_suite.validate_stage_transition(("LOCAL-BASE-0", "LOCAL-RTA-1"), "LOCAL-AC-1")
    stage_suite.validate_stage_transition(
        ("LOCAL-BASE-0", "LOCAL-RTA-1", "LOCAL-AC-1"),
        "LOCAL-READ-ACT-1",
    )
    stage_suite.validate_stage_transition(
        (
            "LOCAL-BASE-0",
            "LOCAL-RTA-1",
            "LOCAL-AC-1",
            "LOCAL-READ-ACT-1",
        ),
        "LOCAL-EVIDENCE-1",
    )
    stage_suite.validate_stage_transition(
        (
            "LOCAL-BASE-0",
            "LOCAL-RTA-1",
            "LOCAL-AC-1",
            "LOCAL-READ-ACT-1",
            "LOCAL-EVIDENCE-1",
        ),
        "LOCAL-GO-READ-1",
    )

    with pytest.raises(stage_suite.StageGateError, match="stage_transition_invalid"):
        stage_suite.validate_stage_transition((), "LOCAL-RTA-1")


def test_rta_order_saves_pm2_only_after_stability_and_bearer():
    order = stage_suite.rta_step_order()

    assert order == (
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
    assert order.index("pm2_save_and_evidence") > order.index("bearer_lifecycle")


def test_rta_runtime_environment_resolves_checksum_bound_pm2_without_ambient_cli(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("PATH", "/untrusted/bin")
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "evidence",
        runtime_env_dir=tmp_path / "runtime",
    )

    environment = stage_suite._pm2_runtime_environment(context)

    assert environment["MUNBON_RUNTIME_ENV_DIR"] == str(context.runtime_env_dir)
    assert environment["PATH"].split(os.pathsep) == [
        str(stage_suite.PM2_CLI.parent),
        str(stage_suite.NODE_ROOT / "bin"),
        "/usr/bin",
        "/bin",
    ]
    assert "runtime_env = _pm2_runtime_environment(context)" in inspect.getsource(
        stage_suite.run_local_rta
    )


def test_read_activation_build_sequence_is_false_true_false():
    assert stage_suite.read_activation_flag_sequence() == (False, True, False)


def test_evidence_activation_sequence_ends_fully_dark():
    assert stage_suite.evidence_activation_flag_sequence() == (
        (True, False),
        (True, True),
        (False, False),
    )


def test_frontend_process_environment_keeps_other_activation_gates_dark(tmp_path):
    (tmp_path / "auth.env").write_text(
        "\n".join(
            (
                "JWT_SECRET=local-signing-value",
                "JWT_ISSUER=munbon-auth",
                "JWT_AUDIENCE=munbon-services",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    environment = stage_suite.frontend_process_environment(
        tmp_path,
        control_plan_reads=True,
    )

    assert {
        key: environment[key]
        for key in (
            "NEXT_PUBLIC_CONTROL_PLAN_READS",
            "NEXT_PUBLIC_CONTROL_PLAN_EVIDENCE_READS",
            "NEXT_PUBLIC_WATER_PLANNING_V2",
            "NEXT_PUBLIC_WATER_PLANNING_SUBMIT_ENABLED",
            "CENTRAL_AUTH_URL",
            "WATER_PLANNING_BFF_URL",
            "JWT_SECRET",
            "JWT_ISSUER",
            "JWT_AUDIENCE",
        )
    } == {
        "NEXT_PUBLIC_CONTROL_PLAN_READS": "true",
        "NEXT_PUBLIC_CONTROL_PLAN_EVIDENCE_READS": "false",
        "NEXT_PUBLIC_WATER_PLANNING_V2": "false",
        "NEXT_PUBLIC_WATER_PLANNING_SUBMIT_ENABLED": "false",
        "CENTRAL_AUTH_URL": "http://127.0.0.1:3005",
        "WATER_PLANNING_BFF_URL": "http://127.0.0.1:3022",
        "JWT_SECRET": "local-signing-value",
        "JWT_ISSUER": "munbon-auth",
        "JWT_AUDIENCE": "munbon-services",
    }
    assert stage_suite.project_frontend_activation_gates(environment) == {
        "control_plan_reads": True,
        "control_plan_evidence_reads": False,
        "water_planning_v2": False,
        "water_planning_submit": False,
    }


def test_frontend_evidence_environment_requires_exact_loopback_read_only_gate_url(
    tmp_path,
):
    (tmp_path / "auth.env").write_text(
        "\n".join(
            (
                "JWT_SECRET=local-signing-value",
                "JWT_ISSUER=munbon-auth",
                "JWT_AUDIENCE=munbon-services",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    environment = stage_suite.frontend_process_environment(
        tmp_path,
        control_plan_reads=True,
        control_plan_evidence_reads=True,
        gate_operations_base_url="http://127.0.0.1:9998/read-only/gates",
    )

    assert environment["NEXT_PUBLIC_CONTROL_PLAN_EVIDENCE_READS"] == "true"
    assert (
        environment["NEXT_PUBLIC_GATE_OPERATIONS_URL"]
        == "http://127.0.0.1:9998/read-only/gates"
    )
    assert stage_suite.project_frontend_activation_gates(environment) == {
        "control_plan_reads": True,
        "control_plan_evidence_reads": True,
        "water_planning_v2": False,
        "water_planning_submit": False,
    }

    with pytest.raises(
        stage_suite.StageGateError,
        match="gate_operations_url_invalid",
    ):
        stage_suite.frontend_process_environment(
            tmp_path,
            control_plan_reads=True,
            control_plan_evidence_reads=True,
            gate_operations_base_url="http://127.0.0.1:9998/gates",
        )


def test_verify_evidence_contract_parity_requires_exact_roster_hashes_and_bytes(
    tmp_path,
):
    backend = tmp_path / "backend"
    frontend = tmp_path / "frontend"
    backend.mkdir()
    frontend.mkdir()
    schema = '{"type":"object"}\n'
    schema_sha = hashlib.sha256(schema.encode()).hexdigest()
    records = [{"relative_path": "projection.schema.json", "sha256": schema_sha}]
    aggregate = hashlib.sha256(
        json.dumps(records, separators=(",", ":")).encode()
    ).hexdigest()
    manifest = {
        "contract_family": "control-plan-evidence",
        "contract_version": 1,
        "contract_set_sha256": aggregate,
        "schemas": records,
        "fixtures": [],
    }
    for root in (backend, frontend):
        (root / "projection.schema.json").write_text(schema, encoding="utf-8")
        (root / "manifest.json").write_text(
            json.dumps(manifest, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    assert stage_suite.verify_evidence_contract_parity(backend, frontend) == {
        "contract_version": 1,
        "file_count": 2,
        "contract_set_sha256": aggregate,
        "exact_bytes": True,
    }

    (frontend / "projection.schema.json").write_text(
        '{"type":"array"}\n',
        encoding="utf-8",
    )
    with pytest.raises(
        stage_suite.StageGateError,
        match="evidence_contract_parity_failed",
    ):
        stage_suite.verify_evidence_contract_parity(backend, frontend)


def test_evidence_seed_sql_adds_only_append_only_held_and_unavailable_readback():
    plan_id = str(uuid4())

    sql = stage_suite.build_evidence_seed_sql(plan_id, 3)

    for required in (
        "INSERT INTO scheduler.control_command_execution_events",
        "'held'",
        "INSERT INTO scheduler.control_gate_readback_observations",
        "'waste-way'",
        "'unavailable'",
        f"'{plan_id}'::uuid",
    ):
        assert required in sql
    assert "UPDATE " not in sql
    assert "DELETE " not in sql


def test_restore_evidence_safety_attempts_dark_build_when_resume_fails(
    monkeypatch,
):
    calls = []

    def fail_resume(*_args, **_kwargs):
        calls.append("resume")
        raise stage_suite.StageGateError("postgres_probe_failed")

    def record_dark_build(*_args, **kwargs):
        calls.append(
            (
                kwargs["control_plan_reads"],
                kwargs["control_plan_evidence_reads"],
                kwargs["build_label"],
            )
        )

    monkeypatch.setattr(stage_suite, "_psql", fail_resume)
    monkeypatch.setattr(stage_suite, "_build_frontend", record_dark_build)

    with pytest.raises(stage_suite.StageGateError, match="evidence_resume_failed"):
        stage_suite.restore_evidence_safety(
            object(),
            plan_id=str(uuid4()),
            plan_version=3,
            resume_required=True,
            dark_build_required=True,
        )

    assert calls == ["resume", (False, False, "evidence-emergency-dark")]


def test_validate_evidence_browser_result_locks_all_read_only_proofs():
    plan_id = str(uuid4())
    projection_paths = [
        f"/api/smart-water-backend/control-plans/{plan_id}/versions/3/{name}"
        for name in (
            "execution-state",
            "intent-timeline",
            "readback-observations",
        )
    ]
    body = {
        "mode": "evidence-visible",
        "projection_statuses": {
            "execution-state": 200,
            "intent-timeline": 200,
            "readback-observations": 200,
        },
        "projection_no_store_count": 3,
        "evidence_panel_count": 3,
        "absent_projection_alerts": 3,
        "unavailable_projection": "readback-observations",
        "malformed_projection": "intent-timeline",
        "intent_timeline_state": "empty-not-execution",
        "held_state": True,
        "gate_link": "http://127.0.0.1:9998/read-only/gates/waste-way",
        "gate_operations_navigation_requests": 0,
        "request_inventory_scope": "post-auth-plan-detail",
        "evidence_request_paths": projection_paths,
        "forbidden_product_requests": [],
        "product_mutation_requests": 0,
    }

    assert (
        stage_suite.validate_evidence_browser_result(
            body,
            plan_id=plan_id,
            plan_version=3,
            gate_id="waste-way",
        )
        == body
    )

    body["product_mutation_requests"] = 1
    with pytest.raises(
        stage_suite.StageGateError,
        match="evidence_browser_result_not_accepted",
    ):
        stage_suite.validate_evidence_browser_result(
            body,
            plan_id=plan_id,
            plan_version=3,
            gate_id="waste-way",
        )


def test_validate_evidence_projection_results_requires_real_held_and_unavailable_data():
    plan_id = str(uuid4())
    headers = {"cache-control": "private, no-store"}
    results = {
        "intent-timeline": stage_suite.HttpResult(
            200,
            {"plan_id": plan_id, "plan_version": 3, "intents": []},
            headers,
        ),
        "readback-observations": stage_suite.HttpResult(
            200,
            {
                "plan_id": plan_id,
                "plan_version": 3,
                "observations": [
                    {
                        "canonical_gate_id": "waste-way",
                        "observed_level": None,
                        "verdict": "unavailable",
                    }
                ],
            },
            headers,
        ),
        "execution-state": stage_suite.HttpResult(
            200,
            {
                "plan_id": plan_id,
                "plan_version": 3,
                "is_held": True,
                "hold_events": [{"event_type": "held"}],
            },
            headers,
        ),
    }
    absent = {name: 404 for name in results}

    assert stage_suite.validate_evidence_projection_results(
        results,
        absent_statuses=absent,
        plan_id=plan_id,
        plan_version=3,
    ) == {
        "statuses": {name: 200 for name in results},
        "no_store_count": 3,
        "intent_count": 0,
        "observation_count": 1,
        "unavailable_observation_count": 1,
        "is_held": True,
        "hold_event_count": 1,
        "absent_statuses": absent,
    }

    results["execution-state"] = stage_suite.HttpResult(
        200,
        {
            "plan_id": plan_id,
            "plan_version": 3,
            "is_held": False,
            "hold_events": [],
        },
        headers,
    )
    with pytest.raises(
        stage_suite.StageGateError,
        match="evidence_projection_result_not_accepted",
    ):
        stage_suite.validate_evidence_projection_results(
            results,
            absent_statuses=absent,
            plan_id=plan_id,
            plan_version=3,
        )


def test_verify_read_only_gate_source_rejects_command_capable_imports(tmp_path):
    service = tmp_path / "services/scada-gate-control-web"
    route = service / "src/app/read-only/gates/[id]"
    library = service / "src/lib"
    route.mkdir(parents=True)
    library.mkdir(parents=True)
    (route / "page.tsx").write_text(
        "\n".join(
            (
                'import { RequireAuth } from "@/components/RequireAuth";',
                'import { createReadOnlyGateStatusClient } from "@/lib/read-only-gate-status";',
                "export default function Page() { return <RequireAuth>read only</RequireAuth>; }",
            )
        ),
        encoding="utf-8",
    )
    (library / "read-only-gate-status.ts").write_text(
        "export const getGateStatus = () => fetch('/api/read-only/gates/id/status');\n",
        encoding="utf-8",
    )

    assert stage_suite.verify_read_only_gate_source(tmp_path) == {
        "route": "/read-only/gates/[id]",
        "command_capable_imports": 0,
        "mutation_methods": 0,
    }

    (route / "page.tsx").write_text(
        'import { ConfirmCommandModal } from "@/components/ConfirmCommandModal";\n',
        encoding="utf-8",
    )
    with pytest.raises(
        stage_suite.StageGateError,
        match="read_only_gate_source_invalid",
    ):
        stage_suite.verify_read_only_gate_source(tmp_path)

    (library / "read-only-gate-status.ts").write_text(
        "export const getGateStatus = () => fetch('/api/read-only/gates/id/status');\n",
        encoding="utf-8",
    )
    (route / "page.tsx").write_text(
        "\n".join(
            (
                'import { RequireAuth } from "@/components/RequireAuth";',
                'import { createReadOnlyGateStatusClient } from "@/lib/read-only-gate-status";',
            )
        ),
        encoding="utf-8",
    )
    (library / "read-only-gate-status.ts").write_text(
        "\n".join(
            (
                'import { GateStatus } from "./api";',
                "fetch('/api/read-only/gates/id/status');",
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        stage_suite.StageGateError,
        match="read_only_gate_source_invalid",
    ):
        stage_suite.verify_read_only_gate_source(tmp_path)

    (library / "read-only-gate-status.ts").write_text(
        "export const getGateStatus = () => fetch('/api/read-only/gates/id/status');\n",
        encoding="utf-8",
    )
    (route / "page.tsx").write_text(
        "\n".join(
            (
                'import { RequireAuth } from "@/components/RequireAuth";',
                'import { createReadOnlyGateStatusClient } from "@/lib/read-only-gate-status";',
                'import { helper } from "@/lib/command-helper";',
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        stage_suite.StageGateError,
        match="read_only_gate_source_invalid",
    ):
        stage_suite.verify_read_only_gate_source(tmp_path)

    (library / "read-only-gate-status.ts").write_text(
        "export const getGateStatus = () => fetch('/api/gates/id/status');\n",
        encoding="utf-8",
    )
    (route / "page.tsx").write_text(
        "\n".join(
            (
                'import { RequireAuth } from "@/components/RequireAuth";',
                'import { createReadOnlyGateStatusClient } from "@/lib/read-only-gate-status";',
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        stage_suite.StageGateError,
        match="read_only_gate_source_invalid",
    ):
        stage_suite.verify_read_only_gate_source(tmp_path)

    (library / "read-only-gate-status.ts").write_text(
        "\n".join(
            (
                "fetch('/api/read-only/gates/id/status');",
                "fetch('/api/gates/id/status');",
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        stage_suite.StageGateError,
        match="read_only_gate_source_invalid",
    ):
        stage_suite.verify_read_only_gate_source(tmp_path)

    (route / "page.tsx").write_text(
        "\n".join(
            (
                'import { RequireAuth } from "@/components/RequireAuth";',
                'import { createReadOnlyGateStatusClient } from "@/lib/read-only-gate-status";',
            )
        ),
        encoding="utf-8",
    )
    (library / "read-only-gate-status.ts").write_text(
        "\n".join(
            (
                'import type { GateStatus } from "./api";',
                "fetch('/api/read-only/gates/id/status', { method: 'PATCH' });",
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        stage_suite.StageGateError,
        match="read_only_gate_source_invalid",
    ):
        stage_suite.verify_read_only_gate_source(tmp_path)


@pytest.mark.parametrize(
    "payload",
    [
        {"password": "not-allowed"},
        {"authorization": "Bearer not-allowed"},
        {"safe": "postgresql://user:secret@127.0.0.1/db"},
        {"nested": [{"refresh_token": "not-allowed"}]},
    ],
)
def test_evidence_payload_rejects_secret_shaped_fields_and_values(payload):
    with pytest.raises(stage_suite.StageGateError, match="evidence_contains_secret"):
        stage_suite.validate_evidence_payload(payload)


def test_evidence_payload_accepts_only_sanitized_operational_facts():
    stage_suite.validate_evidence_payload(
        {
            "stage": "LOCAL-RTA-1",
            "sha": "8" * 40,
            "capacity": {"mem_available_mib": 4096, "swap_used_mib": 0},
            "statuses": [200, 403, 404, 401],
            "cache_control": "no-store",
        }
    )


def test_project_pm2_state_keeps_only_safe_process_fields():
    raw = json.dumps(
        [
            {
                "name": "scheduler",
                "pid": 123,
                "monit": {"memory": 456, "cpu": 1.5},
                "pm2_env": {
                    "status": "online",
                    "restart_time": 2,
                    "POSTGRES_URL": "postgresql://user:secret@127.0.0.1/db",
                },
            }
        ]
    )

    projection = stage_suite.project_pm2_state(raw)

    assert projection == [
        {
            "name": "scheduler",
            "status": "online",
            "restarts": 2,
            "pid": 123,
            "memory_bytes": 456,
            "cpu_percent": 1.5,
        }
    ]
    assert "secret" not in json.dumps(projection)


def test_collect_dark_runtime_contract_requires_every_gate_false_or_absent():
    process_envs = {
        "flow-monitoring": {"GATES_API_ENABLED": "false"},
        "scheduler": {
            "CONTROL_EXECUTION_MODE": "disabled",
            "CONTROL_READBACK_RECONCILIATION_MODE": "off",
        },
        "ros-gis-integration": {
            "DAILY_REQUIREMENT_ENABLED": "false",
            "DAILY_REQUIREMENT_STARTUP_CATCHUP_ENABLED": "false",
            "DAILY_REQUIREMENT_SCHEDULE_ENABLED": "false",
        },
        "bff-water-planning": {},
    }
    raw = json.dumps(
        [
            {"name": name, "pm2_env": {"env": values, **values}}
            for name, values in process_envs.items()
        ]
    )

    assert stage_suite.collect_dark_runtime_contract(raw, {"commandable": False}) == {
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


def test_collect_dark_runtime_contract_fails_when_any_gate_is_armed():
    raw = json.dumps(
        [
            {
                "name": "scheduler",
                "pm2_env": {"CONTROL_EXECUTION_MODE": "enabled"},
            }
        ]
    )

    with pytest.raises(
        stage_suite.StageGateError, match="dark_runtime_contract_failed"
    ):
        stage_suite.collect_dark_runtime_contract(raw, {"commandable": False})


def test_validate_go_read_runtime_environment_requires_loopback_and_dark_commands():
    scada = {
        "NODE_ENV": "production",
        "HTTP_HOST": "127.0.0.1",
        "PORT": "3030",
        "MODBUS_HOST": "127.0.0.1",
        "MODBUS_PORT": "65534",
        "ALLOW_IN_MEMORY_AUDIT": "false",
        "ALLOW_MACHINE_COMMANDS": "false",
        "DATABASE_URL": "postgresql://local:redacted@127.0.0.1/munbon_local",
        "JWT_SECRET": "not-for-evidence",
    }
    gate_web = {
        "NODE_ENV": "production",
        "AUTH_SERVICE_URL": "http://127.0.0.1:3005",
        "SCADA_GATE_CONTROL_URL": "http://127.0.0.1:3030",
        "NEXT_PUBLIC_DEV_TOKEN": "",
        "NEXT_PUBLIC_API_BASE_URL": "",
    }

    assert stage_suite.validate_go_read_runtime_environment(scada, gate_web) == {
        "scada_bind": "127.0.0.1:3030",
        "modbus_target": "127.0.0.1:65534",
        "machine_commands": False,
        "durable_audit": True,
        "service_auth": "dark",
        "gate_web_bind": "127.0.0.1:9998",
        "auth_origin": "http://127.0.0.1:3005",
        "scada_origin": "http://127.0.0.1:3030",
        "dev_bypass": False,
        "legacy_direct_scada": False,
    }

    with pytest.raises(
        stage_suite.StageGateError, match="go_read_runtime_environment_invalid"
    ):
        stage_suite.validate_go_read_runtime_environment(
            {**scada, "ALLOW_MACHINE_COMMANDS": "true"},
            gate_web,
        )

    for forbidden_name in (
        "SCHEDULER_SERVICE_JWT_SECRET",
        "SCADA_SITE_CANONICAL_GATE_ID",
        "SCADA_APPROVED_FIELD_BUNDLE_PATH",
        "SCADA_DEVICE_REGISTRY_PATH",
        "SCADA_APPROVED_LINEAGE_ANCHOR_PATH",
    ):
        with pytest.raises(
            stage_suite.StageGateError,
            match="go_read_runtime_environment_invalid",
        ):
            stage_suite.validate_go_read_runtime_environment(
                {**scada, forbidden_name: ""},
                gate_web,
            )


def test_go_read_runtime_environment_removes_inherited_authority_configuration(
    tmp_path,
    monkeypatch,
):
    forbidden_names = (
        "SCHEDULER_SERVICE_JWT_SECRET",
        "SCADA_SITE_CANONICAL_GATE_ID",
        "SCADA_APPROVED_FIELD_BUNDLE_PATH",
        "SCADA_DEVICE_REGISTRY_PATH",
        "SCADA_APPROVED_LINEAGE_ANCHOR_PATH",
    )
    for name in forbidden_names:
        monkeypatch.setenv(name, "inherited-value")
    runtime_env_dir = tmp_path / "runtime"
    runtime_env_dir.mkdir()
    (runtime_env_dir / "auth.env").write_text(
        "\n".join(
            (
                "JWT_SECRET=local-test-value",
                "JWT_ISSUER=munbon-local",
                "JWT_AUDIENCE=munbon-local-services",
            )
        ),
        encoding="utf-8",
    )
    (runtime_env_dir / "bff.env").write_text(
        "POSTGRES_URL=postgresql://local:test@127.0.0.1/munbon_local\n",
        encoding="utf-8",
    )
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "evidence",
        runtime_env_dir=runtime_env_dir,
    )

    scada, _gate_web, projection = stage_suite._go_read_runtime_environments(context)

    assert all(name not in scada for name in forbidden_names)
    assert projection["service_auth"] == "dark"


def test_go_read_restoration_guard_preserves_primary_failure_and_records_cleanup(
    monkeypatch,
):
    calls = []

    def verify(*_args):
        calls.append("verify")
        return {"verified": True, "temporary_processes": 0}

    monkeypatch.setattr(stage_suite, "_verify_go_read_restoration", verify)

    with pytest.raises(stage_suite.StageGateError, match="browser_failed") as error:
        with stage_suite._go_read_restoration_guard(
            object(),
            before_pm2={},
            before_dark={},
            model_release={},
        ):
            raise stage_suite.StageGateError("browser_failed")

    assert calls == ["verify"]
    assert error.value.restoration == {
        "verified": True,
        "temporary_processes": 0,
    }


def test_go_read_failure_manifest_preserves_primary_gate_and_restoration_proof(
    tmp_path,
    monkeypatch,
):
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    args = stage_suite.argparse.Namespace(
        stage="LOCAL-GO-READ-1",
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=evidence_root,
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 7, 24),
    )

    def fail_with_restoration(_context):
        error = stage_suite.StageGateError("browser_failed")
        error.restoration = {
            "verified": True,
            "reserved_listeners": [],
            "temporary_processes": 0,
        }
        raise error

    monkeypatch.setattr(stage_suite, "_parse_args", lambda _argv: args)
    monkeypatch.setattr(stage_suite, "run_local_go_read", fail_with_restoration)

    assert stage_suite.main([]) == 1
    failure = json.loads(
        (evidence_root / "LOCAL-GO-READ-1-failure.json").read_text(encoding="utf-8")
    )
    assert failure.pop("failed_at").endswith("Z")
    assert failure == {
        "stage": "LOCAL-GO-READ-1",
        "verdict": "FAIL",
        "release_sha": "8" * 40,
        "frontend_sha": "9" * 40,
        "failed_gate": "browser_failed",
        "restoration": {
            "verified": True,
            "reserved_listeners": [],
            "temporary_processes": 0,
        },
    }


def test_go_read_listener_projection_requires_exact_loopback_bindings():
    listeners = [
        {"address": "127.0.0.1", "port": 3030},
        {"address": "127.0.0.1", "port": 9998},
        {"address": "127.0.0.1", "port": 5432},
    ]

    assert stage_suite.go_read_listener_projection(listeners) == {
        "3030": ["127.0.0.1"],
        "9998": ["127.0.0.1"],
    }

    with pytest.raises(
        stage_suite.StageGateError, match="go_read_listener_binding_invalid"
    ):
        stage_suite.go_read_listener_projection(
            [*listeners, {"address": "0.0.0.0", "port": 3030}]
        )


def test_validate_go_read_status_results_requires_exact_offline_gate_and_no_store():
    point = {
        "raw": None,
        "value": None,
        "quality": "offline",
        "lastUpdated": None,
        "lastError": "connect ECONNREFUSED",
    }
    known = stage_suite.HttpResult(
        status=200,
        headers={"cache-control": "no-store"},
        body={
            "id": "waste-way",
            "name": "Waste Way",
            "endpoint": {"host": "127.0.0.1", "port": 65534, "unitId": 1},
            "connection": "offline",
            "markerColor": "red",
            "lastUpdated": None,
            "lastError": "connect ECONNREFUSED",
            "gateLevel": point,
            "doorSw": point,
            "horn": point,
            "gateCf": point,
        },
    )
    unknown = stage_suite.HttpResult(
        status=404,
        headers={"cache-control": "no-store"},
        body={"error": "unknown gate"},
    )

    assert stage_suite.validate_go_read_status_results(known, unknown) == {
        "known_gate_status": 200,
        "known_gate_no_store": True,
        "gate_id": "waste-way",
        "gate_name": "Waste Way",
        "connection": "offline",
        "endpoint": {"host": "127.0.0.1", "port": 65534, "unit_id": 1},
        "null_observations": 4,
        "unknown_gate_status": 404,
        "unknown_gate_no_store": True,
        "http_methods": ["GET", "GET"],
        "product_mutations": 0,
    }

    for field, value in (
        ("markerColor", "green"),
        ("lastUpdated", "2026-07-24T00:00:00.000Z"),
        ("lastError", None),
    ):
        with pytest.raises(
            stage_suite.StageGateError,
            match="go_read_status_result_not_accepted",
        ):
            stage_suite.validate_go_read_status_results(
                stage_suite.HttpResult(
                    status=known.status,
                    headers=known.headers,
                    body={**known.body, field: value},
                ),
                unknown,
            )

    with pytest.raises(
        stage_suite.StageGateError,
        match="go_read_status_result_not_accepted",
    ):
        stage_suite.validate_go_read_status_results(
            stage_suite.HttpResult(
                status=known.status,
                headers=known.headers,
                body={
                    **known.body,
                    "gateLevel": {**point, "raw": 0},
                },
            ),
            unknown,
        )


def test_validate_ros_lifecycle_accepts_manual_only_and_restored_dark_states():
    manual = {
        "daily_requirement": {
            "enabled": True,
            "startup_catchup_enabled": False,
            "schedule_enabled": False,
            "schedule_running": False,
        }
    }
    restored = {
        "daily_requirement": {
            "enabled": False,
            "startup_catchup_enabled": False,
            "schedule_enabled": False,
            "schedule_running": False,
        }
    }

    assert stage_suite.validate_ros_lifecycle(manual, manual_enabled=True) == {
        "enabled": True,
        "startup_catchup_enabled": False,
        "schedule_enabled": False,
        "schedule_running": False,
    }
    assert stage_suite.validate_ros_lifecycle(restored, manual_enabled=False) == {
        "enabled": False,
        "startup_catchup_enabled": False,
        "schedule_enabled": False,
        "schedule_running": False,
    }


@pytest.mark.parametrize("status", ["published", "deduplicated"])
def test_validate_manual_requirement_run_accepts_exact_complete_success(status):
    run_id = str(uuid4())

    assert stage_suite.validate_manual_requirement_run(
        200,
        {
            "status": status,
            "runId": run_id,
            "asOfDate": "2026-07-23",
            "requirementCount": 287,
        },
        as_of_date="2026-07-23",
    ) == {
        "status": status,
        "run_id": run_id,
        "as_of_date": "2026-07-23",
        "requirement_count": 287,
    }


@pytest.mark.parametrize(
    ("http_status", "run_status", "run_id", "as_of_date", "count"),
    [
        (500, "published", str(uuid4()), "2026-07-23", 287),
        (200, "unknown", str(uuid4()), "2026-07-23", 287),
        (200, "published", "invalid", "2026-07-23", 287),
        (200, "published", str(uuid4()), "2026-07-22", 287),
        (200, "published", str(uuid4()), "2026-07-23", 286),
    ],
)
def test_validate_manual_requirement_run_rejects_inexact_success(
    http_status, run_status, run_id, as_of_date, count
):
    with pytest.raises(
        stage_suite.StageGateError, match="manual_requirement_run_not_accepted"
    ):
        stage_suite.validate_manual_requirement_run(
            http_status,
            {
                "status": run_status,
                "runId": run_id,
                "asOfDate": as_of_date,
                "requirementCount": count,
            },
            as_of_date="2026-07-23",
        )


@pytest.mark.parametrize(
    "body",
    [
        {
            "status": "published",
            "runId": str(uuid4()),
            "asOfDate": "2026-07-23",
            "requirementCount": 287,
            "extra": True,
        },
        {
            "status": "published",
            "runId": str(uuid4()),
            "asOfDate": "2026-07-23",
            "requirementCount": 287.0,
        },
        {
            "status": "published",
            "runId": str(uuid4()),
            "asOfDate": "2026-07-23",
            "requirementCount": True,
        },
        {
            "status": "published",
            "runId": 12345678123456781234567812345678,
            "asOfDate": "2026-07-23",
            "requirementCount": 287,
        },
        {
            "status": "published",
            "runId": str(uuid4()).upper(),
            "asOfDate": "2026-07-23",
            "requirementCount": 287,
        },
    ],
)
def test_validate_manual_requirement_run_rejects_extra_keys_and_non_integer_count(
    body,
):
    with pytest.raises(
        stage_suite.StageGateError, match="manual_requirement_run_not_accepted"
    ):
        stage_suite.validate_manual_requirement_run(200, body, as_of_date="2026-07-23")


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (
            500,
            {
                "detail": {
                    "status": "failed_incomplete_source",
                    "reason": "requirement_inputs_incomplete",
                    "asOfDate": "2026-08-12",
                }
            },
        ),
        (
            409,
            {
                "detail": {
                    "status": "failed_incomplete_source",
                    "reason": "unknown",
                    "asOfDate": "2026-08-12",
                }
            },
        ),
        (
            409,
            {
                "detail": {
                    "status": "failed_incomplete_source",
                    "reason": "requirement_inputs_incomplete",
                    "asOfDate": "2026-08-11",
                }
            },
        ),
    ],
)
def test_validate_manual_requirement_failure_rejects_unbounded_response(status, body):
    with pytest.raises(
        stage_suite.StageGateError, match="manual_requirement_run_not_accepted"
    ):
        stage_suite.validate_manual_requirement_failure(
            status, body, as_of_date="2026-08-12"
        )


@pytest.mark.parametrize(
    ("reason", "expected_gate"),
    [
        ("requirement_source_invalid", "manual_requirement_source_invalid"),
        ("requirement_inputs_incomplete", "manual_requirement_inputs_incomplete"),
        ("superseded_lineage", "manual_requirement_superseded_lineage"),
    ],
)
def test_validate_manual_requirement_failure_preserves_sanitized_classification(
    reason, expected_gate
):
    with pytest.raises(stage_suite.StageGateError, match=expected_gate):
        status = (
            "failed_incomplete_source"
            if reason.startswith("requirement_")
            else "rejected"
        )
        stage_suite.validate_manual_requirement_failure(
            409,
            {
                "detail": {
                    "status": status,
                    "reason": reason,
                    "asOfDate": "2026-08-12",
                }
            },
            as_of_date="2026-08-12",
        )


def test_validate_manual_requirement_failure_preserves_operational_date_mismatch():
    with pytest.raises(
        stage_suite.StageGateError, match="manual_requirement_operational_date_mismatch"
    ):
        stage_suite.validate_manual_requirement_failure(
            409,
            {
                "detail": {
                    "status": "rejected",
                    "reason": "operational_date_mismatch",
                    "asOfDate": "2026-08-13",
                    "expectedAsOfDate": "2026-08-12",
                }
            },
            as_of_date="2026-08-13",
        )


def test_validate_requirement_run_lineage_requires_exact_database_identity_and_hashes():
    run_id = str(uuid4())
    run_content_sha256 = "a" * 64
    approved_source_sha256 = "b" * 64
    section_source_sha256 = "c" * 64
    gate_mapping_source_sha256 = "d" * 64
    row = "\t".join(
        (
            run_id,
            run_content_sha256,
            "17",
            section_source_sha256,
            "23",
            gate_mapping_source_sha256,
            "crop-register-v1",
            "weather-v1",
            "ros-daily-v1",
        )
    )

    assert stage_suite.validate_requirement_run_lineage(
        row,
        run_id=run_id,
        approved_source_sha256=approved_source_sha256,
    ) == {
        "run_id": run_id,
        "run_content_sha256": run_content_sha256,
        "approved_source_content_sha256": approved_source_sha256,
        "section_dataset": {
            "version_id": 17,
            "source_sha256": section_source_sha256,
        },
        "gate_mapping_dataset": {
            "version_id": 23,
            "source_sha256": gate_mapping_source_sha256,
        },
        "crop_register_version": "crop-register-v1",
        "weather_version": "weather-v1",
        "method_version": "ros-daily-v1",
    }

    invalid_rows = (
        row.replace(run_id, str(uuid4()), 1),
        row.replace(run_content_sha256, "invalid", 1),
        row.replace("\t17\t", "\t0\t", 1),
        row.replace("crop-register-v1", "", 1),
    )
    for invalid_row in invalid_rows:
        with pytest.raises(
            stage_suite.StageGateError,
            match="requirement_run_lineage_not_accepted",
        ):
            stage_suite.validate_requirement_run_lineage(
                invalid_row,
                run_id=run_id,
                approved_source_sha256=approved_source_sha256,
            )


def test_collect_requirement_run_lineage_queries_published_dataset_parents(
    tmp_path, monkeypatch
):
    run_id = str(uuid4())
    run_content_sha256 = "a" * 64
    approved_source_sha256 = "b" * 64
    section_source_sha256 = "c" * 64
    gate_mapping_source_sha256 = "d" * 64
    row = "\t".join(
        (
            run_id,
            run_content_sha256,
            "17",
            section_source_sha256,
            "23",
            gate_mapping_source_sha256,
            "crop-register-v1",
            "weather-v1",
            "ros-daily-v1",
        )
    )
    queries = []
    monkeypatch.setattr(
        stage_suite,
        "_psql",
        lambda context, query: queries.append(query) or row,
    )
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "evidence",
        runtime_env_dir=tmp_path / "runtime",
    )

    assert stage_suite.collect_requirement_run_lineage(
        context,
        run_id=run_id,
        approved_source_sha256=approved_source_sha256,
    ) == {
        "run_id": run_id,
        "run_content_sha256": run_content_sha256,
        "approved_source_content_sha256": approved_source_sha256,
        "section_dataset": {
            "version_id": 17,
            "source_sha256": section_source_sha256,
        },
        "gate_mapping_dataset": {
            "version_id": 23,
            "source_sha256": gate_mapping_source_sha256,
        },
        "crop_register_version": "crop-register-v1",
        "weather_version": "weather-v1",
        "method_version": "ros-daily-v1",
    }
    query = " ".join(queries[0].split())
    for required in (
        "FROM ros_gis.water_requirement_runs AS run",
        "JOIN ros_gis.dataset_versions AS section_dataset",
        "section_dataset.dataset_kind = 'section_master'",
        "JOIN ros_gis.dataset_versions AS gate_mapping_dataset",
        "gate_mapping_dataset.dataset_kind = 'gate_crosswalk'",
        f"WHERE run.run_id = '{run_id}'::uuid",
        "run.status = 'published'",
    ):
        assert required in query


def test_validate_zone_requirements_requires_nine_current_zone_six_sections():
    run_id = str(uuid4())
    requirement_ids = [str(uuid4()) for _ in range(9)]
    requirements = [
        {
            "requirementId": requirement_id,
            "runId": run_id,
            "version": 1,
            "serviceDate": "2026-07-23",
            "sectionId": f"01-06-01-{number:02d}",
            "zone": 6,
            "requiredVolumeM3": 0 if number == 35 else 1_000.0 + number,
            "dataStatus": "published",
            "deliveryWindow": {
                "start": "2026-07-22T19:00:00+00:00",
                "end": "2026-07-23T19:00:00+00:00",
            },
        }
        for requirement_id, number in zip(requirement_ids, range(35, 44))
    ]

    summary = stage_suite.validate_zone_requirements(
        200,
        {
            "serviceDate": "2026-07-23",
            "zone": 6,
            "dataStatus": "published",
            "requirements": requirements,
        },
        as_of_date="2026-07-23",
        run_id=run_id,
    )

    assert summary == {
        "service_date": "2026-07-23",
        "zone": 6,
        "data_status": "published",
        "requirement_count": 9,
        "run_id": run_id,
        "version": 1,
        "positive_requirement_count": 8,
    }


def test_validate_draft_and_projection_results_keep_only_safe_structural_evidence():
    plan_id = str(uuid4())
    run_id = str(uuid4())
    draft_body = {
        "plan_id": plan_id,
        "plan_version": 1,
        "requirement_run_id": run_id,
        "requirement_version": 1,
        "lifecycle_state": "draft",
        "optimizer_status": "feasible",
        "prediction_status": "completed",
        "requirements": [{"requirement_id": str(uuid4())}],
        "events": [{"event_sequence": 1}],
        "transitions": [{"transition_sequence": 1}],
    }

    summary = stage_suite.validate_draft_result(
        201, draft_body, requirement_run_id=run_id
    )
    projection = stage_suite.validate_projection_result(
        f"/api/v1/control-plans/{plan_id}/versions/1",
        200,
        {"cache-control": "private, no-store"},
        draft_body,
        plan_id=plan_id,
        plan_version=1,
    )

    assert summary == {
        "status": 201,
        "plan_id": plan_id,
        "plan_version": 1,
        "lifecycle_state": "draft",
        "optimizer_status": "feasible",
        "prediction_status": "completed",
        "requirement_count": 1,
        "event_count": 1,
        "transition_count": 1,
    }
    assert projection == {
        "status": 200,
        "no_store": True,
        "plan_id": plan_id,
        "plan_version": 1,
        "top_level_keys": sorted(draft_body),
    }


def test_validate_read_browser_result_accepts_dark_and_visible_proofs():
    plan_id = str(uuid4())

    assert stage_suite.validate_read_browser_result(
        {
            "mode": "dark",
            "signed_in": True,
            "navigation_link_count": 0,
            "route_status": 404,
        },
        mode="dark",
        plan_id=plan_id,
        plan_version=1,
    ) == {
        "mode": "dark",
        "signed_in": True,
        "navigation_link_count": 0,
        "route_status": 404,
    }
    assert (
        stage_suite.validate_read_browser_result(
            {
                "mode": "visible",
                "signed_out_redirect": "/login",
                "navigation_link_count": 1,
                "list_plan_found": True,
                "detail_plan_id": plan_id,
                "detail_plan_version": 1,
                "refresh_preserved_detail": True,
                "deep_link_loaded": True,
                "missing_plan_alerts": 4,
                "independent_panel_failure": "ledger-only",
                "action_controls": 0,
                "unexpected_control_plan_mutations": 0,
                "mutation_route_denial_count": 5,
            },
            mode="visible",
            plan_id=plan_id,
            plan_version=1,
        )["independent_panel_failure"]
        == "ledger-only"
    )


def test_validate_read_browser_result_rejects_partial_or_wrong_plan_evidence():
    plan_id = str(uuid4())

    with pytest.raises(
        stage_suite.StageGateError,
        match="read_browser_result_not_accepted",
    ):
        stage_suite.validate_read_browser_result(
            {
                "mode": "visible",
                "signed_out_redirect": "/login",
                "navigation_link_count": 1,
                "list_plan_found": True,
                "detail_plan_id": str(uuid4()),
                "detail_plan_version": 1,
                "refresh_preserved_detail": True,
                "deep_link_loaded": True,
                "missing_plan_alerts": 4,
                "independent_panel_failure": "ledger-only",
                "action_controls": 0,
                "unexpected_control_plan_mutations": 0,
                "mutation_route_denial_count": 5,
            },
            mode="visible",
            plan_id=plan_id,
            plan_version=1,
        )


def test_validate_go_read_browser_result_requires_live_outage_and_zero_mutations():
    body = {
        "mode": "go-read",
        "signed_out_redirect": "/login",
        "signed_out_status_requests": 0,
        "login_status": 200,
        "gate_id": "waste-way",
        "gate_name": "Waste Way",
        "connection": "offline",
        "read_status": 200,
        "read_no_store": True,
        "live_status_responses": 3,
        "unknown_gate_status": 404,
        "unknown_gate_no_store": True,
        "outage_status": 503,
        "outage_no_store": True,
        "outage_alert_visible": True,
        "stale_status_hidden": True,
        "action_controls": 0,
        "same_origin_status_path": "/api/read-only/gates/waste-way/status",
        "direct_scada_browser_requests": 0,
        "forbidden_product_requests": [],
        "product_mutation_requests": 0,
        "request_inventory_scope": "full-signed-out-through-outage",
        "screenshots": [
            "LOCAL-GO-READ-1-live.png",
            "LOCAL-GO-READ-1-outage.png",
        ],
    }

    assert (
        stage_suite.validate_go_read_browser_result(body, gate_id="waste-way") == body
    )

    with pytest.raises(
        stage_suite.StageGateError, match="go_read_browser_result_not_accepted"
    ):
        stage_suite.validate_go_read_browser_result(
            {**body, "product_mutation_requests": 1},
            gate_id="waste-way",
        )


def test_write_stage_manifest_is_mode_600_atomic_and_secret_safe(tmp_path):
    target = tmp_path / "LOCAL-BASE-0.json"
    payload = {"stage": "LOCAL-BASE-0", "sha": "8" * 40, "verdict": "PASS"}

    stage_suite.write_stage_manifest(target, payload)

    assert json.loads(target.read_text()) == payload
    assert os.stat(target).st_mode & 0o777 == 0o600
    assert not target.with_suffix(".json.tmp").exists()

    with pytest.raises(stage_suite.StageGateError, match="evidence_contains_secret"):
        stage_suite.write_stage_manifest(target, {"password": "no"})


def test_checksum_manifest_preserves_and_updates_every_stage_entry(tmp_path):
    first = tmp_path / "LOCAL-RTA-1.json"
    second = tmp_path / "LOCAL-AC-1.json"
    first.write_text('{"verdict":"PASS"}\n', encoding="utf-8")
    second.write_text('{"verdict":"PASS"}\n', encoding="utf-8")

    stage_suite._checksum_manifest(first)
    stage_suite._checksum_manifest(second)
    first.write_text('{"verdict":"PASS","rerun":true}\n', encoding="utf-8")
    stage_suite._checksum_manifest(first)

    lines = (tmp_path / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert lines == [
        f"{stage_suite.hashlib.sha256(second.read_bytes()).hexdigest()}  {second.name}",
        f"{stage_suite.hashlib.sha256(first.read_bytes()).hexdigest()}  {first.name}",
    ]
    stage_suite._verify_checksum_entry(first)
    first.write_text('{"verdict":"FAIL"}\n', encoding="utf-8")
    with pytest.raises(stage_suite.StageGateError, match="evidence_checksum_mismatch"):
        stage_suite._verify_checksum_entry(first)


def test_stage_state_binds_source_and_harness_and_verifies_prior_manifest(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    harness_root = tmp_path / "harness"
    frontend_root = tmp_path / "frontend"
    evidence_root = tmp_path / "evidence"
    runtime_env_dir = tmp_path / "runtime"
    for path in (
        repo_root,
        harness_root,
        frontend_root,
        evidence_root,
        runtime_env_dir,
    ):
        path.mkdir()
    for name in stage_suite.HARNESS_ARTIFACTS:
        (harness_root / name).write_text(f"{name}\n", encoding="utf-8")
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=repo_root,
        harness_root=harness_root,
        evidence_root=evidence_root,
        runtime_env_dir=runtime_env_dir,
        frontend_root=frontend_root,
    )
    monkeypatch.setattr(stage_suite, "_verify_source_checkouts", lambda context: None)
    manifest = evidence_root / "LOCAL-BASE-0.json"
    manifest.write_text('{"verdict":"PASS"}\n', encoding="utf-8")
    stage_suite._checksum_manifest(manifest)

    stage_suite._save_state(context, ["LOCAL-BASE-0"])

    assert stage_suite._load_state(context) == {
        "release_sha": "8" * 40,
        "frontend_sha": "9" * 40,
        "harness_hashes": {
            name: stage_suite.hashlib.sha256(
                (harness_root / name).read_bytes()
            ).hexdigest()
            for name in stage_suite.HARNESS_ARTIFACTS
        },
        "completed": ["LOCAL-BASE-0"],
    }
    manifest.write_text('{"verdict":"FAIL"}\n', encoding="utf-8")
    with pytest.raises(stage_suite.StageGateError, match="evidence_checksum_mismatch"):
        stage_suite._load_state(context)


def test_stage_state_fails_closed_if_index_survives_without_state(
    tmp_path, monkeypatch
):
    harness_root = tmp_path / "harness"
    evidence_root = tmp_path / "evidence"
    harness_root.mkdir()
    evidence_root.mkdir()
    for name in stage_suite.HARNESS_ARTIFACTS:
        (harness_root / name).write_text(f"{name}\n", encoding="utf-8")
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        harness_root=harness_root,
        evidence_root=evidence_root,
        runtime_env_dir=tmp_path / "runtime",
        frontend_root=tmp_path / "frontend",
    )
    monkeypatch.setattr(stage_suite, "_verify_source_checkouts", lambda context: None)
    (evidence_root / "SHA256SUMS").write_text("", encoding="utf-8")

    with pytest.raises(stage_suite.StageGateError, match="stage_state_missing"):
        stage_suite._load_state(context)


def test_rehearsal_context_accepts_only_the_first_three_stages_and_fixed_owner():
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=Path("/opt/munbon/repo"),
        harness_root=Path("/opt/munbon/harness"),
        evidence_root=Path("/var/lib/munbon-local-acceptance/evidence"),
        runtime_env_dir=Path("/etc/munbon/control-plan-read-runtime"),
        execution_kind="rehearsal",
    )
    owner = {
        "machine": "munbon-control-plan-rehearsal",
        "architecture": "arm64",
        "state": "ready",
        "release_sha": context.release_sha,
        "frontend_sha": context.frontend_sha,
        "dependency_sha256": "c" * 64,
        "execution_kind": "rehearsal",
        "acceptance_evidence": False,
    }

    assert stage_suite._validate_execution_owner(context, owner) is None
    assert stage_suite._execution_stages(context) == stage_suite.STAGE_ORDER[:3]
    with pytest.raises(stage_suite.StageGateError, match="local_baseline_invalid"):
        stage_suite._validate_execution_owner(
            context, {**owner, "acceptance_evidence": True}
        )


def test_rehearsal_stage_state_binds_profile_machine_and_dependency(
    tmp_path, monkeypatch
):
    harness_root = tmp_path / "harness"
    evidence_root = tmp_path / "evidence"
    harness_root.mkdir()
    evidence_root.mkdir()
    for name in stage_suite.HARNESS_ARTIFACTS:
        (harness_root / name).write_text(f"{name}\n", encoding="utf-8")
    owner_path = tmp_path / "owner.json"
    owner_path.write_text(
        json.dumps(
            {
                "machine": "munbon-control-plan-rehearsal",
                "architecture": "arm64",
                "state": "ready",
                "release_sha": "8" * 40,
                "frontend_sha": "9" * 40,
                "dependency_sha256": "c" * 64,
                "execution_kind": "rehearsal",
                "acceptance_evidence": False,
            }
        ),
        encoding="utf-8",
    )
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        harness_root=harness_root,
        evidence_root=evidence_root,
        runtime_env_dir=tmp_path / "runtime",
        frontend_root=tmp_path / "frontend",
        as_of_date=stage_suite.date(2026, 8, 16),
        execution_kind="rehearsal",
        owner_path=owner_path,
    )
    monkeypatch.setattr(stage_suite, "_verify_source_checkouts", lambda _context: None)
    for stage in stage_suite.STAGE_ORDER[:3]:
        manifest = evidence_root / f"{stage}.json"
        manifest.write_text('{"verdict":"PASS"}\n', encoding="utf-8")
        stage_suite._checksum_manifest(manifest)

    stage_suite._save_state(context, list(stage_suite.STAGE_ORDER[:3]))
    state = stage_suite._load_state(context)

    assert {
        key: state[key]
        for key in (
            "execution_kind",
            "machine",
            "acceptance_evidence",
            "dependency_sha256",
            "as_of_date",
        )
    } == {
        "execution_kind": "rehearsal",
        "machine": "munbon-control-plan-rehearsal",
        "acceptance_evidence": False,
        "dependency_sha256": "c" * 64,
        "as_of_date": "2026-08-16",
    }
    changed_date_context = dataclasses.replace(
        context, as_of_date=stage_suite.date(2026, 8, 17)
    )
    with pytest.raises(stage_suite.StageGateError, match="stage_state_stale"):
        stage_suite._load_state(changed_date_context)
    canonical_context = stage_suite.StageContext(
        release_sha=context.release_sha,
        frontend_sha=context.frontend_sha,
        repo_root=context.repo_root,
        harness_root=context.harness_root,
        evidence_root=context.evidence_root,
        runtime_env_dir=context.runtime_env_dir,
        frontend_root=context.frontend_root,
        execution_kind="canonical",
    )
    with pytest.raises(stage_suite.StageGateError, match="stage_state_stale"):
        stage_suite._load_state(canonical_context)


def test_parse_args_rejects_later_stage_for_rehearsal_execution():
    with pytest.raises(SystemExit):
        stage_suite._parse_args(
            [
                "LOCAL-READ-ACT-1",
                "--release-sha",
                "8" * 40,
                "--frontend-sha",
                "9" * 40,
                "--execution-kind",
                "rehearsal",
            ]
        )


def test_parse_args_requires_explicit_execution_kind_and_rehearsal_date():
    common = ["--release-sha", "8" * 40, "--frontend-sha", "9" * 40]

    with pytest.raises(SystemExit):
        stage_suite._parse_args(["LOCAL-BASE-0", *common])
    with pytest.raises(SystemExit):
        stage_suite._parse_args(
            ["LOCAL-BASE-0", *common, "--execution-kind", "rehearsal"]
        )


def test_rehearsal_failure_manifest_is_explicitly_non_authoritative(
    tmp_path, monkeypatch
):
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    args = stage_suite.argparse.Namespace(
        stage="LOCAL-AC-1",
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=evidence_root,
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 8, 16),
        execution_kind="rehearsal",
        diagnostic=False,
    )
    monkeypatch.setattr(stage_suite, "_parse_args", lambda _argv: args)
    monkeypatch.setattr(
        stage_suite,
        "run_local_ac",
        lambda _context: (_ for _ in ()).throw(
            stage_suite.StageGateError("rehearsal_ac_failed")
        ),
    )

    assert stage_suite.main([]) == 1
    failure = json.loads(
        (evidence_root / "LOCAL-AC-1-failure.json").read_text(encoding="utf-8")
    )
    assert failure == {
        "stage": "LOCAL-AC-1",
        "verdict": "FAIL",
        "release_sha": "8" * 40,
        "frontend_sha": "9" * 40,
        "failed_gate": "rehearsal_ac_failed",
        "failed_at": failure["failed_at"],
        "acceptance_evidence": False,
        "as_of_date": "2026-08-16",
    }


def test_existing_rehearsal_failure_is_terminal_without_manifest_rewrite(
    tmp_path, monkeypatch
):
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    failure_path = evidence_root / "LOCAL-AC-1-failure.json"
    failure_body = b'{"failed_gate":"first_failure","verdict":"FAIL"}\n'
    failure_path.write_bytes(failure_body)
    args = stage_suite.argparse.Namespace(
        stage="LOCAL-AC-1",
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=evidence_root,
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 8, 16),
        execution_kind="rehearsal",
        diagnostic=False,
    )
    calls = []
    monkeypatch.setattr(stage_suite, "_parse_args", lambda _argv: args)
    monkeypatch.setattr(
        stage_suite, "run_local_ac", lambda _context: calls.append("stage")
    )

    assert stage_suite.main([]) == 1
    assert calls == []
    assert failure_path.read_bytes() == failure_body


def test_clear_failure_manifest_removes_only_the_completed_stage(tmp_path):
    current = tmp_path / "LOCAL-AC-1-failure.json"
    other = tmp_path / "LOCAL-RTA-1-failure.json"
    current.write_text("{}")
    other.write_text("{}")
    stage_suite._checksum_manifest(current)
    stage_suite._checksum_manifest(other)

    stage_suite.clear_failure_manifest(tmp_path, "LOCAL-AC-1")

    assert not current.exists()
    assert other.exists()
    assert stage_suite._read_checksum_index(tmp_path / "SHA256SUMS") == {
        other.name: stage_suite._hash_file(other)
    }


def test_parse_listening_sockets_projects_addresses_and_ports_without_processes():
    output = "\n".join(
        [
            "LISTEN 0 244 127.0.0.1:5432 0.0.0.0:*",
            "LISTEN 0 511 [::1]:6379 [::]:*",
            "LISTEN 0 4096 127.0.0.1:8086 0.0.0.0:*",
        ]
    )

    assert stage_suite.parse_listening_sockets(output) == [
        {"address": "127.0.0.1", "port": 5432},
        {"address": "::1", "port": 6379},
        {"address": "127.0.0.1", "port": 8086},
    ]


def test_application_port_conflicts_returns_only_runtime_ports():
    listeners = [
        {"address": "127.0.0.1", "port": 5432},
        {"address": "127.0.0.1", "port": 3011},
        {"address": "0.0.0.0", "port": 3022},
    ]

    assert stage_suite.application_port_conflicts(listeners) == [3011, 3022]


def test_unexpected_non_loopback_listeners_rejects_wildcard_services():
    listeners = [
        {"address": "127.0.0.1", "port": 5432},
        {"address": "::1", "port": 6379},
        {"address": "*", "port": 9090},
        {"address": "0.0.0.0", "port": 9100},
    ]

    assert stage_suite.unexpected_non_loopback_listeners(listeners) == [9090, 9100]


def test_validate_migration_parity_requires_scheduler_0013_ros_0004_and_bff_012():
    scheduler = [f"{index:04d}_migration" for index in range(1, 13)] + [
        "0013_operator_approved_execution"
    ]
    ros = [
        "0001_dataset_version_parent",
        "0002_water_requirement_publication",
        "0003_daily_requirement_producer",
        "0004_dataset_version_identity_immutable",
    ]
    bff = [
        "009_crop_registry",
        "010_planning_depth_submissions",
        "011_planning_depth_rid_calendar_v2",
        "012_planning_depth_roster_provenance",
    ]

    assert stage_suite.validate_migration_parity(scheduler, ros, bff) == {
        "scheduler_latest": "0013_operator_approved_execution",
        "scheduler_count": 13,
        "ros_latest": "0004_dataset_version_identity_immutable",
        "ros_count": 4,
        "bff_latest": "012_planning_depth_roster_provenance",
        "bff_count": 4,
    }


@pytest.mark.parametrize(
    "scheduler,ros,bff",
    [
        (
            [f"{index:04d}_migration" for index in range(1, 13)],
            [
                "0001_dataset_version_parent",
                "0002_water_requirement_publication",
                "0003_daily_requirement_producer",
                "0004_dataset_version_identity_immutable",
            ],
            [
                "009_crop_registry",
                "010_planning_depth_submissions",
                "011_planning_depth_rid_calendar_v2",
                "012_planning_depth_roster_provenance",
            ],
        ),
        (
            [f"{index:04d}_migration" for index in range(1, 13)]
            + ["0013_operator_approved_execution"],
            [
                "0001_dataset_version_parent",
                "0002_water_requirement_publication",
                "0003_daily_requirement_producer",
            ],
            [
                "009_crop_registry",
                "010_planning_depth_submissions",
                "011_planning_depth_rid_calendar_v2",
                "012_planning_depth_roster_provenance",
            ],
        ),
        (
            [f"{index:04d}_migration" for index in range(1, 13)]
            + ["0013_operator_approved_execution"],
            [
                "0001_dataset_version_parent",
                "0002_water_requirement_publication",
                "0003_daily_requirement_producer",
                "0004_dataset_version_identity_immutable",
            ],
            [
                "009_crop_registry",
                "010_planning_depth_submissions",
                "011_planning_depth_rid_calendar_v2",
            ],
        ),
    ],
)
def test_validate_migration_parity_fails_closed_on_any_missing_tail(
    scheduler, ros, bff
):
    with pytest.raises(stage_suite.StageGateError, match="migration_parity_failed"):
        stage_suite.validate_migration_parity(scheduler, ros, bff)


ROS_DATASET_VERSION_TRIGGER_ROWS = [
    (
        "dataset_versions_identity_is_immutable\tO\t27\t\ttrue\t"
        "ros_gis.reject_dataset_version_identity_change()"
    ),
    (
        "dataset_versions_no_truncate\tO\t34\t\ttrue\t"
        "ros_gis.reject_dataset_version_identity_change()"
    ),
]


def test_validate_ros_dataset_version_triggers_requires_enabled_exact_definitions():
    assert stage_suite.validate_ros_dataset_version_triggers(
        ROS_DATASET_VERSION_TRIGGER_ROWS
    ) == {
        "dataset_version_triggers": [
            {
                "name": "dataset_versions_identity_is_immutable",
                "enabled": "O",
                "type_mask": 27,
                "column_filter": None,
                "unconditional": True,
                "function": "ros_gis.reject_dataset_version_identity_change()",
            },
            {
                "name": "dataset_versions_no_truncate",
                "enabled": "O",
                "type_mask": 34,
                "column_filter": None,
                "unconditional": True,
                "function": "ros_gis.reject_dataset_version_identity_change()",
            },
        ]
    }


@pytest.mark.parametrize(
    "trigger_rows",
    [
        [],
        [
            ROS_DATASET_VERSION_TRIGGER_ROWS[0].replace("\tO\t", "\tD\t"),
            ROS_DATASET_VERSION_TRIGGER_ROWS[1],
        ],
        [
            ROS_DATASET_VERSION_TRIGGER_ROWS[0].replace("\t27\t", "\t11\t"),
            ROS_DATASET_VERSION_TRIGGER_ROWS[1],
        ],
        [
            ROS_DATASET_VERSION_TRIGGER_ROWS[0].replace("\t\ttrue\t", "\t1 2\ttrue\t"),
            ROS_DATASET_VERSION_TRIGGER_ROWS[1],
        ],
        [
            ROS_DATASET_VERSION_TRIGGER_ROWS[0].replace("\t\ttrue\t", "\t\tfalse\t"),
            ROS_DATASET_VERSION_TRIGGER_ROWS[1],
        ],
        [
            ROS_DATASET_VERSION_TRIGGER_ROWS[0].replace(
                "ros_gis.reject_dataset_version_identity_change()",
                "ros_gis.unexpected_function()",
            ),
            ROS_DATASET_VERSION_TRIGGER_ROWS[1],
        ],
        ROS_DATASET_VERSION_TRIGGER_ROWS[:1],
        [
            *ROS_DATASET_VERSION_TRIGGER_ROWS,
            "unexpected_trigger\tO\t27\t\ttrue\tfn()",
        ],
    ],
)
def test_validate_ros_dataset_version_triggers_fails_closed_on_any_mismatch(
    trigger_rows,
):
    with pytest.raises(
        stage_suite.StageGateError,
        match="^ros_dataset_version_trigger_parity_failed$",
    ):
        stage_suite.validate_ros_dataset_version_triggers(trigger_rows)


def test_apply_migrations_applies_ros_0004_and_queries_exact_triggers(
    tmp_path, monkeypatch
):
    context = stage_suite.StageContext(
        release_sha="a" * 40,
        frontend_sha="b" * 40,
        repo_root=tmp_path,
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "evidence",
        runtime_env_dir=tmp_path / "runtime-env",
    )
    commands = []
    sql_queries = []
    scheduler_ids = [f"{index:04d}_migration" for index in range(1, 13)] + [
        "0013_operator_approved_execution"
    ]
    ros_ids = [
        "0001_dataset_version_parent",
        "0002_water_requirement_publication",
        "0003_daily_requirement_producer",
        "0004_dataset_version_identity_immutable",
    ]
    bff_ids = [
        "009_crop_registry",
        "010_planning_depth_submissions",
        "011_planning_depth_rid_calendar_v2",
        "012_planning_depth_roster_provenance",
    ]

    def fake_run_checked(label, argv, **_kwargs):
        commands.append((label, argv))
        return ""

    def rows(values):
        return "\n".join(f"{value}\tchecksum" for value in values)

    def fake_psql(_context, sql):
        sql_queries.append(sql)
        if "scheduler.schema_migrations" in sql:
            return rows(scheduler_ids)
        if "ros_gis.schema_migrations" in sql:
            return rows(ros_ids)
        if "water_planning.schema_migrations" in sql:
            return rows(bff_ids)
        if "to_regclass" in sql:
            return "t"
        if sql == stage_suite.ROS_DATASET_VERSION_TRIGGER_QUERY:
            return "\n".join(ROS_DATASET_VERSION_TRIGGER_ROWS)
        raise AssertionError(f"unexpected SQL: {sql}")

    monkeypatch.setattr(stage_suite, "_run_checked", fake_run_checked)
    monkeypatch.setattr(stage_suite, "_psql", fake_psql)
    monkeypatch.setattr(stage_suite, "_service_environment", lambda *_args: {})

    result = stage_suite._apply_migrations(context)

    ros_apply_ids = [
        argv[-1] for label, argv in commands if label.startswith("ros_000")
    ]
    assert ros_apply_ids == ros_ids
    assert stage_suite.ROS_DATASET_VERSION_TRIGGER_QUERY == (
        "SELECT t.tgname, t.tgenabled, t.tgtype::integer, t.tgattr::text, "
        "(t.tgqual IS NULL)::text, t.tgfoid::regprocedure::text "
        "FROM pg_trigger AS t "
        "WHERE t.tgrelid = 'ros_gis.dataset_versions'::regclass "
        "AND NOT t.tgisinternal ORDER BY t.tgname"
    )
    assert stage_suite.ROS_DATASET_VERSION_TRIGGER_QUERY in sql_queries
    assert [item["name"] for item in result["dataset_version_triggers"]] == [
        "dataset_versions_identity_is_immutable",
        "dataset_versions_no_truncate",
    ]


# --- LOCAL-WRITE-FOUNDATION-1 tests ---


def test_stage_order_includes_local_write_foundation_after_go_read():
    idx = stage_suite.STAGE_ORDER.index("LOCAL-WRITE-FOUNDATION-1")
    assert stage_suite.STAGE_ORDER[idx - 1] == "LOCAL-GO-READ-1"


def test_stage_transition_accepts_write_foundation_after_all_six_prior_stages():
    stage_suite.validate_stage_transition(
        (
            "LOCAL-BASE-0",
            "LOCAL-RTA-1",
            "LOCAL-AC-1",
            "LOCAL-READ-ACT-1",
            "LOCAL-EVIDENCE-1",
            "LOCAL-GO-READ-1",
        ),
        "LOCAL-WRITE-FOUNDATION-1",
    )


def test_validate_w1_principal_result_accepts_valid_operator():
    body = {"subject": "op1", "effective_roles": ["operator"]}
    headers = {"cache-control": "no-store"}

    result = stage_suite.validate_w1_principal_result(200, body, headers)

    assert result["subject"] == "op1"
    assert result["effective_roles"] == ["operator"]


def test_validate_w1_principal_result_rejects_missing_operator_role():
    body = {"subject": "ft1", "effective_roles": ["field_team"]}
    headers = {"cache-control": "no-store"}

    with pytest.raises(
        stage_suite.StageGateError,
        match="w1_principal_result_not_accepted",
    ):
        stage_suite.validate_w1_principal_result(200, body, headers)


def test_validate_w1_principal_result_rejects_missing_no_store():
    body = {"subject": "op1", "effective_roles": ["operator"]}
    headers = {"cache-control": "max-age=60"}

    with pytest.raises(
        stage_suite.StageGateError,
        match="w1_principal_result_not_accepted",
    ):
        stage_suite.validate_w1_principal_result(200, body, headers)


def test_validate_w2_write_disabled_result_accepts_503_disabled():
    body = {"detail": "planning_depth_writes_disabled"}
    headers = {"cache-control": "no-store"}

    result = stage_suite.validate_w2_write_disabled_result(503, body, headers)

    assert result["status"] == 503
    assert result["detail"] == "planning_depth_writes_disabled"


def test_validate_w2_submission_result_accepts_201_create():
    body = {
        "submission_id": "sid-1",
        "client_submission_id": "csid-1",
        "request_sha256": "a" * 64,
        "replayed": False,
        "week_key": "2026-R31",
        "project_key": "mun-bon",
        "calendar_system": "rid-irrigation-v1",
        "week_date": "2026-05-30",
        "submitted_at": "2026-07-28T12:00:00+07:00",
        "submitted_by": "op1",
        "supersedes_submission_id": None,
    }
    headers = {"cache-control": "no-store"}

    result = stage_suite.validate_w2_submission_result(
        201, body, headers, expected_status=201
    )

    assert result["submission_id"] == "sid-1"
    assert result["replayed"] is False
    assert result["calendar_system"] == "rid-irrigation-v1"
    assert result["week_date"] == "2026-05-30"
    assert result["supersedes_submission_id"] is None


def _expanded_levels(depths: dict[str, float]) -> list[dict]:
    levels = []
    for zone in range(1, 7):
        zone_id = f"01-{zone:02d}"
        for section in range(zone, 43, 6):
            levels.append(
                {
                    "section_id": f"01-{zone:02d}-01-{section + 2:02d}",
                    "zone_id": zone_id,
                    "planning_depth_mm": depths[zone_id],
                    "source_kind": "zone_default",
                    "source_area_id": zone_id,
                }
            )
    return levels[:41]


ZONE_DEPTHS = {f"01-{zone:02d}": 240.0 + 10.0 * zone for zone in range(1, 7)}


def test_validate_w2_active_result_accepts_200_with_41_expanded_values():
    body = {
        "submission_id": "sid-1",
        "levels": _expanded_levels(ZONE_DEPTHS),
    }
    headers = {"cache-control": "no-store"}

    result = stage_suite.validate_w2_active_result(
        200,
        body,
        headers,
        submission_id="sid-1",
        expected_count=41,
        expected_zone_depths=ZONE_DEPTHS,
    )

    assert result["levels_count"] == 41


def test_validate_w2_active_result_rejects_collapsed_zone_expansion():
    # Every section served one zone's default: the count is still 41, so only a
    # per-zone depth check can catch a broken zone->section fan-out.
    collapsed = _expanded_levels({zone: 250.0 for zone in ZONE_DEPTHS})
    headers = {"cache-control": "no-store"}

    with pytest.raises(stage_suite.StageGateError, match="w2_active"):
        stage_suite.validate_w2_active_result(
            200,
            {"submission_id": "sid-1", "levels": collapsed},
            headers,
            submission_id="sid-1",
            expected_count=41,
            expected_zone_depths=ZONE_DEPTHS,
        )


def test_validate_w2_active_result_rejects_a_relabelled_collapsed_expansion():
    # 41 self-consistent rows all claiming one zone: every row passes a per-row
    # check, so only a whole-set coverage check catches this.
    collapsed = [
        {
            "section_id": f"01-01-01-{index + 3:02d}",
            "zone_id": "01-01",
            "planning_depth_mm": ZONE_DEPTHS["01-01"],
            "source_kind": "zone_default",
            "source_area_id": "01-01",
        }
        for index in range(41)
    ]

    with pytest.raises(stage_suite.StageGateError, match="w2_active"):
        stage_suite.validate_w2_active_result(
            200,
            {"submission_id": "sid-1", "levels": collapsed},
            {"cache-control": "no-store"},
            submission_id="sid-1",
            expected_count=41,
            expected_zone_depths=ZONE_DEPTHS,
        )


def test_validate_w2_active_result_rejects_a_section_id_from_another_zone():
    levels = _expanded_levels(ZONE_DEPTHS)
    # section_id encodes its own zone; a row whose section belongs elsewhere is
    # a broken mapping even though the row is internally consistent.
    levels[0] = {**levels[0], "section_id": "01-04-01-09"}

    with pytest.raises(stage_suite.StageGateError, match="w2_active"):
        stage_suite.validate_w2_active_result(
            200,
            {"submission_id": "sid-1", "levels": levels},
            {"cache-control": "no-store"},
            submission_id="sid-1",
            expected_count=41,
            expected_zone_depths=ZONE_DEPTHS,
        )


def test_validate_w2_week_is_clean_rejects_a_404_with_an_unexpected_detail():
    with pytest.raises(
        stage_suite.StageGateError,
        match="write_foundation_week_precheck_failed",
    ):
        stage_suite.validate_w2_week_is_clean(
            404, {"detail": "something_else"}, {"cache-control": "no-store"}
        )


def test_dark_probe_request_can_never_be_persisted():
    # The write-flag gate precedes roster validation, so a roster-invalid body
    # yields 503 when dark and 422 (no write) if the runtime is unexpectedly
    # armed. A fully valid body would be inserted instead.
    probe = stage_suite._build_dark_probe_request(
        week_date="2026-07-27",
        week_key="2026-W31",
        client_submission_id="id-dark-gate",
    )
    canonical_zones = {f"01-{zone:02d}" for zone in range(1, 7)}

    assert probe["levels"]
    assert not {level["area_id"] for level in probe["levels"]} <= canonical_zones
    assert probe["schema_version"] == 1
    assert probe["week_key"] == "2026-W31"


def test_validate_w2_active_result_rejects_section_override_source_kind():
    levels = _expanded_levels(ZONE_DEPTHS)
    levels[0] = {**levels[0], "source_kind": "section_override"}
    headers = {"cache-control": "no-store"}

    with pytest.raises(stage_suite.StageGateError, match="w2_active"):
        stage_suite.validate_w2_active_result(
            200,
            {"submission_id": "sid-1", "levels": levels},
            headers,
            submission_id="sid-1",
            expected_count=41,
            expected_zone_depths=ZONE_DEPTHS,
        )


def test_validate_w2_conflict_result_accepts_only_the_stale_active_conflict():
    headers = {"cache-control": "no-store"}

    result = stage_suite.validate_w2_conflict_result(
        409, {"detail": "stale_active_submission"}, headers
    )

    assert result["detail"] == "stale_active_submission"


def test_validate_w2_conflict_result_rejects_a_client_id_collision_409():
    # The uuid5 derivation exists to prevent this 409; accepting it here would
    # make the drill green for the very failure it is meant to detect.
    headers = {"cache-control": "no-store"}

    with pytest.raises(stage_suite.StageGateError, match="w2_conflict"):
        stage_suite.validate_w2_conflict_result(
            409, {"detail": "client_submission_id_conflict"}, headers
        )


def test_validate_w2_not_found_result_accepts_404():
    body = {"detail": "planning_depth_submission_not_found"}
    headers = {"cache-control": "no-store"}

    result = stage_suite.validate_w2_not_found_result(404, body, headers)

    assert result["status"] == 404


def test_build_planning_depth_request_produces_distinct_canonical_payloads():
    req_a = stage_suite._build_planning_depth_request(
        week_date="2026-07-27",
        week_key="2026-W31",
        client_submission_id="csid-a",
        active_submission_id=None,
        depth_offset="0.100",
    )
    req_b = stage_suite._build_planning_depth_request(
        week_date="2026-07-27",
        week_key="2026-W31",
        client_submission_id="csid-b",
        active_submission_id=None,
        depth_offset="0.200",
    )

    assert req_a["project_key"] == "mun-bon"
    assert req_a["week_date"] == "2026-07-27"
    assert len(req_a["levels"]) == 6
    assert req_a["levels"] != req_b["levels"]


def test_build_planning_depth_request_uses_the_supplied_week_key():
    # The week key must come from the single derivation in
    # _write_foundation_week, not a second formula inside the builder.
    request = stage_suite._build_planning_depth_request(
        week_date="2026-07-27",
        week_key="2026-W99",
        client_submission_id="csid-a",
        active_submission_id=None,
        depth_offset="0.100",
    )

    assert request["week_key"] == "2026-W99"


def test_build_planning_depth_request_zone_depths_match_the_active_oracle():
    request = stage_suite._build_planning_depth_request(
        week_date="2026-07-27",
        week_key="2026-W31",
        client_submission_id="csid-a",
        active_submission_id=None,
        depth_offset="0.100",
    )

    assert {
        level["area_id"]: level["planning_depth_mm"] for level in request["levels"]
    } == ZONE_DEPTHS


def test_validate_write_flag_is_dark_accepts_a_disabled_flag():
    assert stage_suite.validate_write_flag_is_dark("false") == {
        "planning_depth_writes_enabled": "false"
    }


def test_validate_write_flag_is_dark_refuses_to_probe_an_armed_runtime():
    # Probing the dark gate while writes are armed inserts a real submission
    # into an append-only table, poisoning that week permanently.
    with pytest.raises(
        stage_suite.StageGateError,
        match="write_foundation_flag_not_dark",
    ):
        stage_suite.validate_write_flag_is_dark("true")


def test_validate_w2_week_is_clean_distinguishes_an_unavailable_precheck():
    body = {"detail": "planning_depth_database_unavailable"}
    headers = {"cache-control": "no-store"}

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_foundation_week_precheck_failed",
    ):
        stage_suite.validate_w2_week_is_clean(503, body, headers)


def test_validate_w2_week_is_clean_rejects_a_404_without_no_store():
    body = {"detail": "planning_depth_submission_not_found"}

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_foundation_week_precheck_failed",
    ):
        stage_suite.validate_w2_week_is_clean(
            404, body, {"cache-control": "max-age=60"}
        )


def test_validate_w2_not_found_result_rejects_a_404_without_no_store():
    body = {"detail": "planning_depth_submission_not_found"}

    with pytest.raises(stage_suite.StageGateError, match="w2_not_found"):
        stage_suite.validate_w2_not_found_result(
            404, body, {"cache-control": "max-age=60"}
        )


def test_validate_w2_active_result_rejects_a_200_without_no_store():
    body = {"submission_id": "sid-1", "levels": _expanded_levels(ZONE_DEPTHS)}

    with pytest.raises(stage_suite.StageGateError, match="w2_active"):
        stage_suite.validate_w2_active_result(
            200,
            body,
            {"cache-control": "max-age=60"},
            submission_id="sid-1",
            expected_count=41,
            expected_zone_depths=ZONE_DEPTHS,
        )


def test_validate_w2_conflict_result_rejects_a_409_without_no_store():
    body = {"detail": "stale_active_submission"}

    with pytest.raises(stage_suite.StageGateError, match="w2_conflict"):
        stage_suite.validate_w2_conflict_result(
            409, body, {"cache-control": "max-age=60"}
        )


def test_validate_w2_write_disabled_result_rejects_wrong_status():
    body = {"detail": "planning_depth_writes_disabled"}
    headers = {"cache-control": "no-store"}

    with pytest.raises(stage_suite.StageGateError, match="w2_write_disabled"):
        stage_suite.validate_w2_write_disabled_result(200, body, headers)


def test_validate_w2_submission_result_rejects_wrong_status():
    body = {
        "submission_id": "sid-1",
        "client_submission_id": "csid-1",
        "request_sha256": "a" * 64,
        "replayed": False,
        "week_key": "2026-W31",
        "project_key": "mun-bon",
        "submitted_at": "2026-07-28T12:00:00+07:00",
        "submitted_by": "op1",
    }
    headers = {"cache-control": "no-store"}

    with pytest.raises(stage_suite.StageGateError, match="w2_submission"):
        stage_suite.validate_w2_submission_result(
            500, body, headers, expected_status=201
        )


def test_validate_w2_active_result_rejects_wrong_count():
    body = {
        "submission_id": "sid-1",
        "levels": _expanded_levels(ZONE_DEPTHS)[:1],
    }
    headers = {"cache-control": "no-store"}

    with pytest.raises(stage_suite.StageGateError, match="w2_active"):
        stage_suite.validate_w2_active_result(
            200,
            body,
            headers,
            submission_id="sid-1",
            expected_count=41,
            expected_zone_depths=ZONE_DEPTHS,
        )


def test_validate_w2_conflict_result_rejects_wrong_status():
    body = {"detail": "stale_active_submission"}
    headers = {"cache-control": "no-store"}

    with pytest.raises(stage_suite.StageGateError, match="w2_conflict"):
        stage_suite.validate_w2_conflict_result(200, body, headers)


def test_validate_w2_not_found_result_rejects_wrong_status():
    body = {"detail": "planning_depth_submission_not_found"}
    headers = {"cache-control": "no-store"}

    with pytest.raises(stage_suite.StageGateError, match="w2_not_found"):
        stage_suite.validate_w2_not_found_result(200, body, headers)


# --- runtime correctness + re-runnability ---


def test_planning_depth_request_zone_ids_match_the_seeded_canonical_roster():
    seeded_zones = {
        approved_sources._zone_for_section(number) for number in SEEDED_SECTION_NUMBERS
    }
    expected_area_ids = {f"01-{zone:02d}" for zone in seeded_zones}

    request = stage_suite._build_planning_depth_request(
        week_date="2026-07-27",
        week_key="2026-W31",
        client_submission_id="00000000-0000-4000-a000-000000000002",
        active_submission_id=None,
        depth_offset="0.100",
    )

    assert {level["area_id"] for level in request["levels"]} == expected_area_ids
    assert {level["area_type"] for level in request["levels"]} == {"zone"}
    assert not any("zone_id" in level for level in request["levels"])


def test_write_foundation_week_is_the_monday_of_the_as_of_week():
    assert stage_suite._write_foundation_week(date(2026, 7, 29)) == (
        "2026-07-27",
        "2026-W31",
    )


def test_write_foundation_week_is_stable_for_every_day_of_that_week():
    monday = date(2026, 7, 27)
    resolved = {
        stage_suite._write_foundation_week(monday + timedelta(days=offset))
        for offset in range(7)
    }

    assert resolved == {("2026-07-27", "2026-W31")}


def test_write_foundation_week_snaps_back_across_a_calendar_year_boundary():
    # 2027-01-01 is a Friday whose Monday falls in the previous calendar year.
    # NOTE: this does NOT pin ISO-vs-calendar year -- that Monday's calendar and
    # ISO years both read 2026. The ISO property is pinned by the test below.
    assert stage_suite._write_foundation_week(date(2027, 1, 1)) == (
        "2026-12-28",
        "2026-W53",
    )


def test_write_foundation_week_handles_iso_year_ahead_of_calendar_year():
    # 2025-12-29 is a Monday that already belongs to ISO week 2026-W01 — the
    # mirror of the 2026-W53 case, and the direction a calendar-year
    # implementation gets wrong in the opposite way.
    assert stage_suite._write_foundation_week(date(2025, 12, 29)) == (
        "2025-12-29",
        "2026-W01",
    )
    assert stage_suite._write_foundation_week(date(2026, 1, 1)) == (
        "2025-12-29",
        "2026-W01",
    )


def test_client_submission_id_is_deterministic_for_the_same_run():
    first = stage_suite._write_foundation_client_submission_id(
        "7f8b8a84", "2026-W31", "create"
    )
    second = stage_suite._write_foundation_client_submission_id(
        "7f8b8a84", "2026-W31", "create"
    )

    assert first == second
    assert UUID(first).version == 5


def test_client_submission_id_covaries_with_the_week_key():
    week_31 = stage_suite._write_foundation_client_submission_id(
        "7f8b8a84", "2026-W31", "create"
    )
    week_32 = stage_suite._write_foundation_client_submission_id(
        "7f8b8a84", "2026-W32", "create"
    )

    assert week_31 != week_32


def test_client_submission_id_differs_per_drill_and_per_release():
    create = stage_suite._write_foundation_client_submission_id(
        "7f8b8a84", "2026-W31", "create"
    )
    conflict = stage_suite._write_foundation_client_submission_id(
        "7f8b8a84", "2026-W31", "conflict"
    )
    other_release = stage_suite._write_foundation_client_submission_id(
        "469553cc", "2026-W31", "create"
    )

    assert len({create, conflict, other_release}) == 3


def test_validate_w2_week_is_clean_accepts_absent_active_submission():
    body = {"detail": "planning_depth_submission_not_found"}
    headers = {"cache-control": "no-store"}

    assert stage_suite.validate_w2_week_is_clean(404, body, headers) == {
        "status": 404,
        "clean": True,
    }


def test_write_foundation_stage_derives_week_and_ids_instead_of_hardcoding():
    tree = ast.parse(inspect.getsource(stage_suite.run_local_write_foundation))
    called = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]

    assert called.count("_write_foundation_week") == 1
    assert called.count("_write_foundation_client_submission_id") == 1
    assert "2026-07-27" not in inspect.getsource(stage_suite.run_local_write_foundation)


class _FakeResponse:
    def __init__(self, status, body=None, headers=None):
        self.status = status
        self.body = {} if body is None else body
        self.headers = {"cache-control": "no-store"} if headers is None else headers


class _ScriptedClient:
    """Replays queued responses and records the calls it received."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.bearers = []

    def request(self, method, url, *, payload=None, bearer=None, **kwargs):
        self.calls.append((method, url, payload))
        self.bearers.append(bearer)
        if not self._responses:
            raise AssertionError(f"unscripted request: {method} {url}")
        return self._responses.pop(0)


def test_scripted_client_pins_the_real_http_client_signature():
    # A fake encoding a wrong interface assumption makes every test above it
    # false assurance, so pin it against the client the stage actually uses.
    real = inspect.signature(stage_suite.LocalHttpClient.request)
    fake = inspect.signature(_ScriptedClient.request)
    accepts_kwargs = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in fake.parameters.values()
    )

    assert accepts_kwargs
    for name, parameter in real.parameters.items():
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY:
            continue
        assert name in fake.parameters, f"fake is missing {name}"
    assert [f.name for f in dataclasses.fields(stage_suite.HttpResult)] == [
        "status",
        "body",
        "headers",
    ]


def _drill_kwargs(*, flag="false", arming=None):
    return dict(
        token="t",
        week_date="2026-07-27",
        week_key="2026-W31",
        drill_submission_id=lambda drill: f"id-{drill}",
        arm_writes=(arming if arming is not None else []).append,
        read_write_flag=lambda: flag,
    )


def _receipt(submission_id, *, replayed):
    return {
        "submission_id": submission_id,
        "client_submission_id": "id-create",
        "request_sha256": "a" * 64,
        "replayed": replayed,
        "week_key": "2026-W31",
        "project_key": "mun-bon",
        "submitted_at": "2026-07-27T12:00:00+07:00",
        "submitted_by": "op1",
    }


def _happy_path_responses():
    return [
        _FakeResponse(200, {"subject": "op1", "effective_roles": ["operator"]}),
        _FakeResponse(404, {"detail": "planning_depth_submission_not_found"}),
        _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
        _FakeResponse(201, _receipt("sid-1", replayed=False)),
        _FakeResponse(200, _receipt("sid-1", replayed=True)),
        _FakeResponse(409, {"detail": "stale_active_submission"}),
        _FakeResponse(
            200, {"submission_id": "sid-1", "levels": _expanded_levels(ZONE_DEPTHS)}
        ),
        _FakeResponse(404, {"detail": "planning_depth_submission_not_found"}),
        _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
    ]


def test_write_foundation_drills_complete_every_drill_on_the_happy_path():
    arming = []
    client = _ScriptedClient(_happy_path_responses())

    steps = stage_suite.run_write_foundation_drills(
        client, **_drill_kwargs(arming=arming)
    )

    assert set(steps) == {
        "w1_principal",
        "w2_week_clean",
        "migration_011",
        "w2_dark_flag_gate",
        "w2_create",
        "w2_replay",
        "w2_conflict",
        "w2_active",
        "w2_not_found",
        "w2_restored_gate",
    }
    assert arming == [True, False]
    assert steps["w2_create"]["replayed"] is False
    assert steps["w2_replay"]["replayed"] is True
    assert steps["w2_active"]["levels_count"] == 41


def test_write_foundation_drills_prove_the_gate_is_dark_again_after_disarming():
    arming = []
    client = _ScriptedClient(_happy_path_responses())

    stage_suite.run_write_foundation_drills(client, **_drill_kwargs(arming=arming))

    # the restored-gate POST must be the last request, i.e. after arm_writes(False)
    assert client.calls[-1][0] == "POST"
    assert not client._responses, "every scripted response must be consumed"


def test_write_foundation_drills_reject_a_replay_where_a_fresh_create_is_required():
    # The whole point of the derived week/ids: the create drill must see 201.
    responses = _happy_path_responses()
    responses[3] = _FakeResponse(200, _receipt("sid-1", replayed=True))
    client = _ScriptedClient(responses)

    with pytest.raises(stage_suite.StageGateError, match="w2_submission"):
        stage_suite.run_write_foundation_drills(client, **_drill_kwargs(arming=[]))


def test_write_foundation_drills_reject_a_replay_of_a_different_submission():
    responses = _happy_path_responses()
    responses[4] = _FakeResponse(200, _receipt("sid-other", replayed=True))
    client = _ScriptedClient(responses)

    with pytest.raises(
        stage_suite.StageGateError,
        match="w2_replay_submission_id_mismatch",
    ):
        stage_suite.run_write_foundation_drills(client, **_drill_kwargs(arming=[]))


def test_write_foundation_drills_restore_the_dark_flag_when_a_drill_fails():
    arming = []
    # clean precheck -> dark gate 503 -> create returns an unexpected 500
    client = _ScriptedClient(
        [
            _FakeResponse(200, {"subject": "op1", "effective_roles": ["operator"]}),
            _FakeResponse(404, {"detail": "planning_depth_submission_not_found"}),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
            _FakeResponse(500, {"detail": "boom"}),
        ]
    )

    with pytest.raises(stage_suite.StageGateError):
        stage_suite.run_write_foundation_drills(client, **_drill_kwargs(arming=arming))

    assert arming == [True, False], "writes must be disarmed on the failure path"


def test_write_foundation_drills_never_arm_writes_when_the_week_is_dirty():
    arming = []
    client = _ScriptedClient(
        [
            _FakeResponse(200, {"subject": "op1", "effective_roles": ["operator"]}),
            _FakeResponse(200, {"submission_id": "existing", "levels": []}),
        ]
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_foundation_week_not_clean",
    ):
        stage_suite.run_write_foundation_drills(client, **_drill_kwargs(arming=arming))

    assert arming == [], "a dirty week must never arm the write flag"


def test_write_foundation_drills_refuse_to_probe_an_already_armed_runtime():
    arming = []
    client = _ScriptedClient(
        [
            _FakeResponse(200, {"subject": "op1", "effective_roles": ["operator"]}),
            _FakeResponse(404, {"detail": "planning_depth_submission_not_found"}),
        ]
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_foundation_flag_not_dark",
    ):
        stage_suite.run_write_foundation_drills(
            client, **_drill_kwargs(arming=arming, flag="true")
        )

    # The dark-gate POST would have been persisted against an armed runtime.
    assert arming == []
    assert [method for method, _, _ in client.calls] == ["GET", "GET"]


def test_write_foundation_drills_check_the_week_before_arming_writes():
    arming = []
    client = _ScriptedClient(
        [
            _FakeResponse(200, {"subject": "op1", "effective_roles": ["operator"]}),
            _FakeResponse(404, {"detail": "planning_depth_submission_not_found"}),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
            _FakeResponse(500, {"detail": "stop here"}),
        ]
    )

    recorded = []

    def arm(enabled):
        recorded.append(("arm", enabled, len(client.calls)))
        arming.append(enabled)

    kwargs = _drill_kwargs(arming=arming)
    kwargs["arm_writes"] = arm
    with pytest.raises(stage_suite.StageGateError):
        stage_suite.run_write_foundation_drills(client, **kwargs)

    # the clean-week GET and the dark-gate POST both complete before writes arm
    methods = [method for method, _, _ in client.calls]
    assert methods[:3] == ["GET", "GET", "POST"]
    first_arm = next(entry for entry in recorded if entry[1] is True)
    assert first_arm[2] == 3, "writes armed before the dark-gate drill finished"


def test_validate_w2_week_is_clean_rejects_an_existing_active_submission():
    body = {"submission_id": "sid-1", "levels": []}
    headers = {"cache-control": "no-store"}

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_foundation_week_not_clean",
    ):
        stage_suite.validate_w2_week_is_clean(200, body, headers)


# --- LOCAL-WRITE-UI-1 ---


def test_stage_order_includes_local_write_ui_after_write_foundation():
    idx = stage_suite.STAGE_ORDER.index("LOCAL-WRITE-UI-1")
    assert stage_suite.STAGE_ORDER[idx - 1] == "LOCAL-WRITE-FOUNDATION-1"


def test_stage_transition_accepts_write_ui_after_all_seven_prior_stages():
    stage_suite.validate_stage_transition(
        (
            "LOCAL-BASE-0",
            "LOCAL-RTA-1",
            "LOCAL-AC-1",
            "LOCAL-READ-ACT-1",
            "LOCAL-EVIDENCE-1",
            "LOCAL-GO-READ-1",
            "LOCAL-WRITE-FOUNDATION-1",
        ),
        "LOCAL-WRITE-UI-1",
    )


def test_frontend_process_environment_accepts_water_planning_submit_enabled(tmp_path):
    auth = tmp_path / "auth.env"
    auth.write_text("JWT_SECRET=s\nJWT_ISSUER=i\nJWT_AUDIENCE=a\n")

    result = stage_suite.frontend_process_environment(
        tmp_path,
        control_plan_reads=False,
        water_planning_v2=True,
        water_planning_submit=True,
    )

    assert result["NEXT_PUBLIC_WATER_PLANNING_V2"] == "true"
    assert result["NEXT_PUBLIC_WATER_PLANNING_SUBMIT_ENABLED"] == "true"


def test_frontend_process_environment_rejects_submit_without_v2(tmp_path):
    auth = tmp_path / "auth.env"
    auth.write_text("JWT_SECRET=s\nJWT_ISSUER=i\nJWT_AUDIENCE=a\n")

    with pytest.raises(stage_suite.StageGateError):
        stage_suite.frontend_process_environment(
            tmp_path,
            control_plan_reads=False,
            water_planning_submit=True,
            water_planning_v2=False,
        )


def test_frontend_process_environment_defaults_preserve_existing_dark_behavior(
    tmp_path,
):
    auth = tmp_path / "auth.env"
    auth.write_text("JWT_SECRET=s\nJWT_ISSUER=i\nJWT_AUDIENCE=a\n")

    result = stage_suite.frontend_process_environment(
        tmp_path, control_plan_reads=False
    )

    assert result["NEXT_PUBLIC_WATER_PLANNING_V2"] == "false"
    assert result["NEXT_PUBLIC_WATER_PLANNING_SUBMIT_ENABLED"] == "false"


def test_frontend_env_sets_v2_write_paths_when_armed_and_removes_when_dark(
    tmp_path, monkeypatch
):
    # Real consumer: the frontend's Next.js proxy routes read API_SERVER +
    # PLANNING_DEPTH_{SUBMIT,ACTIVE,ROSTER}_PATH (smart-cms-app
    # app/api/smart-water-backend/water-planning/*/route.ts). An armed frontend
    # must get the exact real BFF paths; a dark frontend must NOT inherit them
    # from a polluted parent env (defence-in-depth beyond the SUBMIT flag).
    auth = tmp_path / "auth.env"
    auth.write_text("JWT_SECRET=s\nJWT_ISSUER=i\nJWT_AUDIENCE=a\n")
    write_path_vars = (
        "API_SERVER",
        "PLANNING_DEPTH_SUBMIT_PATH",
        "PLANNING_DEPTH_ACTIVE_PATH",
        "PLANNING_DEPTH_ROSTER_PATH",
    )
    for name in write_path_vars:
        monkeypatch.setenv(name, "polluted")

    armed = stage_suite.frontend_process_environment(
        tmp_path,
        control_plan_reads=False,
        water_planning_v2=True,
        water_planning_submit=True,
    )
    assert armed["API_SERVER"] == "http://127.0.0.1:3022"
    assert armed["PLANNING_DEPTH_SUBMIT_PATH"] == (
        "/api/v2/water-planning/planning-depth-submissions"
    )
    assert armed["PLANNING_DEPTH_ACTIVE_PATH"] == (
        "/api/v2/water-planning/planning-depth-submissions/active"
    )
    assert armed["PLANNING_DEPTH_ROSTER_PATH"] == (
        "/api/v1/water-planning/planning-depth-roster/v1"
    )

    dark = stage_suite.frontend_process_environment(tmp_path, control_plan_reads=False)
    for name in write_path_vars:
        assert name not in dark, name


def test_accepted_frontend_sha_accepts_any_validated_40_hex():
    # No pin to one historical SHA: the identity binding is orchestrate
    # (== frontend origin/main) and _verify_frontend_source (== guest checkout
    # HEAD), so LOCAL-BASE-0 needs only a format gate. Two DISTINCT valid SHAs
    # are accepted, which a hard pin to one constant could not do.
    assert stage_suite._accepted_frontend_sha("a" * 40) == "a" * 40
    other = "0123456789abcdef" * 2 + "0" * 8
    assert len(other) == 40
    assert stage_suite._accepted_frontend_sha(other) == other


def test_accepted_frontend_sha_rejects_malformed():
    for bad in ("", "a" * 39, "a" * 41, "A" * 40, "g" * 40, " " + "a" * 39):
        with pytest.raises(
            stage_suite.StageGateError, match="frontend_sha_not_accepted"
        ):
            stage_suite._accepted_frontend_sha(bad)


def test_stage_transition_rejects_write_ui_without_write_foundation():
    with pytest.raises(stage_suite.StageGateError, match="stage_transition_invalid"):
        stage_suite.validate_stage_transition(
            (
                "LOCAL-BASE-0",
                "LOCAL-RTA-1",
                "LOCAL-AC-1",
                "LOCAL-READ-ACT-1",
                "LOCAL-EVIDENCE-1",
                "LOCAL-GO-READ-1",
            ),
            "LOCAL-WRITE-UI-1",
        )


def _write_browser_evidence():
    """Truthful write-UI evidence.

    Every status here is what the real stack actually returns, verified at
    source: the submit receipt is reduced camelCase with no client id
    (submissions/route.ts:186-193); the active readback is the BFF body verbatim
    (active/route.ts:158); a denied read is 403 passthrough
    (planning-depth-roster/route.ts:79-80); and ANY upstream failure collapses to
    502, never 503 (upstream-guard.ts:48-58).
    """
    create_submission_id = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
    correct_submission_id = "d4c3b2a1-f6e5-4b7a-9d8c-1e0f2a3b4c5d"
    create_request = {
        "schema_version": 2,
        "project_key": "mun-bon",
        "calendar_system": "rid-irrigation-v1",
        "week_key": "2027-R02",
        "week_date": "2026-11-08",
        "client_submission_id": "33333333-3333-4333-8333-333333333333",
        "expected_active_submission_id": None,
        "levels": [
            {
                "area_type": "zone",
                "area_id": f"01-{zone:02d}",
                "planning_depth_mm": 250.0 + 10.0 * (zone - 1),
            }
            for zone in range(1, 7)
        ],
    }
    correct_request = {
        **create_request,
        "client_submission_id": "44444444-4444-4444-8444-444444444444",
        "expected_active_submission_id": create_submission_id,
        "levels": [
            {
                "area_type": "zone",
                "area_id": f"01-{zone:02d}",
                "planning_depth_mm": 260.0 + 10.0 * (zone - 1),
            }
            for zone in range(1, 7)
        ],
    }
    return {
        "create_result": {
            "status": 201,
            "submission_id": create_submission_id,
            "replayed": False,
        },
        "active_readback": {
            "status": 200,
            "submission_id": create_submission_id,
            "levels_count": 41,
            "distinct_depths": [250.0, 260.0, 270.0, 280.0, 290.0, 300.0],
        },
        "correct_result": {
            "status": 201,
            "submission_id": correct_submission_id,
        },
        "conflict_result": {"status": 409},
        "conflict_reconciliation": {
            "status": 200,
            "submission_id": correct_submission_id,
        },
        "request_identity": {
            "create": create_request,
            "correct": correct_request,
        },
        "roster_provenance": {
            "dataset_version_id": 7,
            "source_hash": "a" * 64,
        },
        "field_team_result": {
            "roster_status": 403,
            "active_status": 403,
            "observed_roster_status": 403,
            "panel_roster_status": 403,
            "panel_active_status": 403,
            "submit_absent": True,
            "denied_banner": True,
            "unavailable_banner": False,
            "submit_status": 403,
            "logout_status": 200,
            "refresh_reuse_status": 401,
        },
        "outage_result": {
            "roster_status": 502,
            "active_status": 502,
            "observed_roster_status": 502,
            "panel_roster_status": 502,
            "panel_active_status": 502,
            "submit_absent": True,
            "unavailable_banner": True,
            "denied_banner": False,
            "submit_status": 502,
        },
        "logout_result": {
            "status": 200,
            "second_context_status": 200,
            "refresh_reuse_status": 401,
            "second_context_refresh_reuse_status": 401,
            "redirect_url": "/login",
        },
        "reload_result": {
            "redirect_url": "/login",
            "reloaded_from": "/smart-water/dashboard",
        },
        "request_inventory": {
            "forbidden_write_count": 0,
            "forbidden_writes": [],
            "total_mutations": 5,
        },
    }


def test_validate_write_browser_result_accepts_truthful_write_evidence():
    result = stage_suite.validate_write_browser_result(_write_browser_evidence())

    assert result["create_result"]["submission_id"] is not None
    assert result["active_readback"]["levels_count"] == 41
    assert result["conflict_result"]["status"] == 409
    assert result["request_identity"]["correct"]["expected_active_submission_id"] == (
        result["create_result"]["submission_id"]
    )
    assert result["roster_provenance"] == {
        "dataset_version_id": 7,
        "source_hash": "a" * 64,
    }
    assert result["request_inventory"]["forbidden_write_count"] == 0
    assert result["field_team_result"]["roster_status"] == 403
    assert result["outage_result"]["roster_status"] == 502
    assert result["logout_result"]["redirect_to_login"] is True
    # The two fabricated claims the merged stage emitted must be GONE, not merely
    # false: an absent key cannot be misread as a proven property.
    assert "reads_preserved" not in result["outage_result"]
    assert "safe_redirect" not in result["logout_result"]


def test_validate_write_browser_result_rejects_missing_create_proof():
    evidence = _write_browser_evidence()
    del evidence["create_result"]

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_reports_every_failed_predicate():
    evidence = _write_browser_evidence()
    evidence["create_result"]["status"] = 500
    evidence["outage_result"]["submit_status"] = 503

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ) as exc_info:
        stage_suite.validate_write_browser_result(evidence)

    assert exc_info.value.predicate_codes == (
        "create_status_not_201",
        "outage_submit_status_not_502",
    )


def test_persist_write_browser_result_checksums_sanitized_result(tmp_path):
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "evidence",
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 8, 9),
    )
    evidence = _write_browser_evidence()

    target = stage_suite._persist_write_browser_result(context, evidence)

    assert json.loads(target.read_text(encoding="utf-8")) == evidence
    assert stage_suite._read_checksum_index(target.parent / "SHA256SUMS") == {
        target.name: stage_suite._hash_file(target)
    }


def test_persist_write_browser_result_rejects_unsafe_result_without_artifact(tmp_path):
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "evidence",
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 8, 9),
    )
    evidence = _write_browser_evidence()
    evidence["authorization"] = "Bearer secret"

    with pytest.raises(
        stage_suite.StageGateError,
        match="evidence_contains_secret",
    ):
        stage_suite._persist_write_browser_result(context, evidence)

    assert not context.evidence_root.exists()


def test_accept_write_browser_output_persists_before_predicate_rejection(tmp_path):
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "evidence",
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 8, 9),
    )
    evidence = _write_browser_evidence()
    evidence["create_result"]["status"] = 500

    with pytest.raises(stage_suite.StageGateError) as exc_info:
        stage_suite._accept_write_browser_output(context, json.dumps(evidence))

    target = context.evidence_root / "LOCAL-WRITE-UI-1-browser-result.json"
    assert exc_info.value.predicate_codes == ("create_status_not_201",)
    assert json.loads(target.read_text(encoding="utf-8")) == evidence
    stage_suite._verify_checksum_entry(target)


def test_run_local_write_ui_clears_stale_browser_result_before_new_drill(
    tmp_path, monkeypatch
):
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "evidence",
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 8, 9),
    )
    target = stage_suite._persist_write_browser_result(
        context, _write_browser_evidence()
    )
    monkeypatch.setattr(
        stage_suite,
        "_load_state",
        lambda _context: {"completed": list(stage_suite.STAGE_ORDER[:7])},
    )

    def stop_before_drill(_context):
        raise stage_suite.StageGateError("frontend_source_identity_stale")

    monkeypatch.setattr(stage_suite, "_verify_frontend_source", stop_before_drill)

    with pytest.raises(
        stage_suite.StageGateError,
        match="frontend_source_identity_stale",
    ):
        stage_suite.run_local_write_ui(context)

    assert not target.exists()
    assert target.name not in stage_suite._read_checksum_index(
        context.evidence_root / "SHA256SUMS"
    )


REFRESH_REUSE_FIELDS = (
    ("field_team_result", "refresh_reuse_status"),
    ("logout_result", "refresh_reuse_status"),
    ("logout_result", "second_context_refresh_reuse_status"),
)


@pytest.mark.parametrize(("section", "field"), REFRESH_REUSE_FIELDS)
def test_validate_write_browser_result_rejects_missing_refresh_reuse(section, field):
    evidence = _write_browser_evidence()
    del evidence[section][field]

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


@pytest.mark.parametrize(
    ("section", "field", "float_value"),
    [
        ("field_team_result", "panel_roster_status", 403.0),
        ("field_team_result", "panel_active_status", 403.0),
        ("field_team_result", "observed_roster_status", 403.0),
        ("outage_result", "panel_roster_status", 502.0),
        ("outage_result", "panel_active_status", 502.0),
        ("outage_result", "observed_roster_status", 502.0),
    ],
)
def test_validate_write_browser_result_rejects_float_passive_statuses(
    section, field, float_value
):
    # The passive/panel cross-checks are int-strict too: a float that == the
    # probe status must not be read as agreement (#160 round-3 review).
    evidence = _write_browser_evidence()
    evidence[section][field] = float_value

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


@pytest.mark.parametrize(
    ("section", "field", "float_value"),
    [
        ("create_result", "status", 201.0),
        ("field_team_result", "roster_status", 403.0),
        ("outage_result", "roster_status", 502.0),
        ("conflict_result", "status", 409.0),
    ],
)
def test_validate_write_browser_result_rejects_float_status_lookalikes(
    section, field, float_value
):
    # Every status gate is int-strict, not just the 401 ones: a re-serialization
    # emitting 403.0/502.0/201.0 must not sail through on == equality.
    evidence = _write_browser_evidence()
    evidence[section][field] = float_value

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


@pytest.mark.parametrize(("section", "field"), REFRESH_REUSE_FIELDS)
@pytest.mark.parametrize("unrevoked_status", [200, 403, None, 401.0, "401", True])
def test_validate_write_browser_result_rejects_unrevoked_refresh_reuse(
    section, field, unrevoked_status
):
    # The suppression scenario: logout status, redirect, and reload can all look
    # perfect while the SAME context's refresh token still works (200) or fails
    # for the wrong reason (403/None). Only an observed 401 proves revocation.
    evidence = _write_browser_evidence()
    evidence[section][field] = unrevoked_status

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_restore_scheduler_guarded_retries_then_reports_success(monkeypatch):
    calls = {"restore": 0}

    def restore_fail_once():
        calls["restore"] += 1
        if calls["restore"] == 1:
            raise stage_suite.StageGateError("write_ui_scheduler_restart")

    monkeypatch.setattr(stage_suite, "_restore_scheduler", restore_fail_once)
    monkeypatch.setattr(stage_suite, "_verify_scheduler_restoration", lambda: None)
    monkeypatch.setattr(stage_suite.time, "sleep", lambda _s: None)

    report = stage_suite._restore_scheduler_guarded()

    assert report == {"attempts": 2, "restored": True, "failed_gate": None}


def test_restore_scheduler_guarded_reports_failure_after_bounded_attempts(
    monkeypatch,
):
    calls = {"restore": 0}

    def restore_always_fails():
        calls["restore"] += 1
        raise stage_suite.StageGateError("write_ui_scheduler_restart")

    def verify_fails():
        raise stage_suite.StageGateError("write_ui_scheduler_not_online_after_restore")

    monkeypatch.setattr(stage_suite, "_restore_scheduler", restore_always_fails)
    monkeypatch.setattr(stage_suite, "_verify_scheduler_restoration", verify_fails)
    monkeypatch.setattr(stage_suite.time, "sleep", lambda _s: None)

    report = stage_suite._restore_scheduler_guarded()

    assert calls["restore"] == 3
    # The final-state verification is authoritative on failure: it names the
    # unmet condition, superseding the earlier restart error.
    assert report == {
        "attempts": 3,
        "restored": False,
        "failed_gate": "write_ui_scheduler_not_online_after_restore",
    }


def test_restore_scheduler_guarded_never_persists_raw_exception_text(
    monkeypatch,
):
    # Raw str(exc) can carry credential context the sanitizer cannot recognize,
    # and a sanitizer trip while writing the manifest silently discards it.
    # Non-StageGateError failures must be reduced to a safe type code.
    def restore_raises_with_secret():
        raise RuntimeError("postgres://operator:hunter2@10.0.0.5/db unreachable")

    monkeypatch.setattr(stage_suite, "_restore_scheduler", restore_raises_with_secret)

    def verify_fails():
        raise RuntimeError("also-secret: Bearer abc.def")

    monkeypatch.setattr(stage_suite, "_verify_scheduler_restoration", verify_fails)
    monkeypatch.setattr(stage_suite.time, "sleep", lambda _s: None)

    report = stage_suite._restore_scheduler_guarded()

    assert report == {
        "attempts": 3,
        "restored": False,
        "failed_gate": "unexpected_RuntimeError",
    }


def test_safe_subprocess_failure_code_extracts_a_named_browser_code():
    # The browser now prints a clean code token so a named diagnostic
    # (refresh_cookie_ambiguous, …) reaches the failure manifest instead of
    # collapsing to the generic write_browser_failed.
    stderr = (
        "FAIL write_browser: refresh_cookie_ambiguous\n"
        "write_browser detail: two smart_cms_refresh cookies\n"
    )
    assert (
        stage_suite.safe_subprocess_failure_code(stderr, "FAIL write_browser: ")
        == "refresh_cookie_ambiguous"
    )


def test_safe_subprocess_failure_code_ignores_the_human_detail_line():
    # The non-prefixed detail line must never be mistaken for a second code
    # (which would collapse the extraction to None).
    stderr = (
        "FAIL write_browser: browser_logout_failed\n"
        "write_browser detail: ECONNRESET 127.0.0.1:9999\n"
    )
    assert (
        stage_suite.safe_subprocess_failure_code(stderr, "FAIL write_browser: ")
        == "browser_logout_failed"
    )


def test_write_browser_environment_scrubs_node_preload_injection(tmp_path, monkeypatch):
    # A parent NODE_OPTIONS=--require preload can replace globalThis.fetch and
    # fabricate a 401 the validator would accept, without ever contacting
    # central auth. The launcher env must not inherit it (#160 review).
    monkeypatch.setenv("NODE_OPTIONS", "--require /tmp/evil-preload.js")
    monkeypatch.setenv("NODE_REPL_EXTERNAL_MODULE", "/tmp/evil.js")
    context = _write_ui_context(tmp_path)
    runtime = context.runtime_env_dir
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "operator.env").write_text(
        "MUNBON_OPERATOR_EMAIL=op@example.test\n" "MUNBON_OPERATOR_PASSWORD=pw\n",
        encoding="utf-8",
    )
    (runtime / "field-team.env").write_text(
        "MUNBON_FIELD_TEAM_EMAIL=ft@example.test\n" "MUNBON_FIELD_TEAM_PASSWORD=pw\n",
        encoding="utf-8",
    )

    environment = stage_suite._write_browser_environment(
        context,
        week_key="2027-R01",
        week_date="2026-11-02",
        ready_path=tmp_path / ".ready",
        release_path=tmp_path / ".release",
    )

    assert "NODE_OPTIONS" not in environment
    assert "NODE_REPL_EXTERNAL_MODULE" not in environment


def test_restore_scheduler_guarded_propagates_interrupt_class_exits(monkeypatch):
    # An operator Ctrl-C must NOT be absorbed into a scheduler_restore_failed
    # verdict: the guard lets interrupt-class exits propagate so the caller can
    # route them to a manifest-then-propagate exit with their own semantics.
    def restore_interrupted():
        raise KeyboardInterrupt

    monkeypatch.setattr(stage_suite, "_restore_scheduler", restore_interrupted)
    monkeypatch.setattr(stage_suite, "_verify_scheduler_restoration", lambda: None)
    monkeypatch.setattr(stage_suite.time, "sleep", lambda _s: None)

    with pytest.raises(KeyboardInterrupt):
        stage_suite._restore_scheduler_guarded()


def test_restore_scheduler_guarded_backs_off_between_attempts(monkeypatch):
    sleeps = []

    def restore_always_fails():
        raise stage_suite.StageGateError("write_ui_scheduler_restart")

    monkeypatch.setattr(stage_suite, "_restore_scheduler", restore_always_fails)
    monkeypatch.setattr(stage_suite, "_verify_scheduler_restoration", lambda: None)
    monkeypatch.setattr(stage_suite.time, "sleep", sleeps.append)

    stage_suite._restore_scheduler_guarded(attempts=3, backoff_seconds=2.5)

    assert sleeps == [2.5, 2.5]


def test_verify_scheduler_restoration_checks_state_and_readiness_without_restart(
    monkeypatch,
):
    # ONE ordered log: readiness must be polled BEFORE the pm2 snapshot, or a
    # restart still respawning is snapshotted as not-online and false-fails —
    # the exact #160 HIGH-2 race. Separate lists cannot pin that order.
    events = []

    def recording_run_checked(label, argv, **_kwargs):
        assert argv == stage_suite._pm2_command("jlist")
        events.append("pm2_jlist")
        return _scheduler_jlist("online")

    monkeypatch.setattr(stage_suite, "_run_checked", recording_run_checked)
    monkeypatch.setattr(
        stage_suite,
        "_wait_json",
        lambda _c, _url: events.append("readiness"),
    )
    monkeypatch.setattr(stage_suite, "LocalHttpClient", lambda *_a, **_k: object())

    stage_suite._verify_scheduler_restoration()

    assert events == ["readiness", "pm2_jlist"]


def test_verify_scheduler_restoration_tolerates_a_stale_stopped_duplicate(
    monkeypatch,
):
    # pm2 can retain a stale errored/stopped duplicate entry beside the healthy
    # one; a stage whose scheduler is genuinely online (and serving readiness)
    # must not FAIL because a leftover duplicate is not online (#160 round-5).
    monkeypatch.setattr(
        stage_suite,
        "_run_checked",
        lambda *_a, **_k: _scheduler_jlist_entries("stopped", "online"),
    )
    monkeypatch.setattr(
        stage_suite, "_wait_json", lambda *_a, **_k: {"status": "ready"}
    )
    monkeypatch.setattr(stage_suite, "LocalHttpClient", lambda *_a, **_k: object())

    stage_suite._verify_scheduler_restoration()  # must not raise


def test_verify_scheduler_restoration_rejects_a_stopped_scheduler(monkeypatch):
    # Readiness is polled first; a process that answers readiness but whose pm2
    # entry is not 'online' (a stale/errored duplicate) is still rejected.
    monkeypatch.setattr(
        stage_suite,
        "_run_checked",
        lambda *_a, **_k: _scheduler_jlist("stopped"),
    )
    monkeypatch.setattr(
        stage_suite, "_wait_json", lambda *_a, **_k: {"status": "ready"}
    )
    monkeypatch.setattr(stage_suite, "LocalHttpClient", lambda *_a, **_k: object())

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_ui_scheduler_not_online_after_restore",
    ):
        stage_suite._verify_scheduler_restoration()


def test_restore_scheduler_guarded_records_restored_despite_command_error(
    monkeypatch,
):
    # `pm2 restart` can time out while still taking effect. The INDEPENDENT
    # final-state check decides `restored`; the command error stays on record.
    def restore_always_fails():
        raise stage_suite.StageGateError("write_ui_scheduler_restart")

    monkeypatch.setattr(stage_suite, "_restore_scheduler", restore_always_fails)
    monkeypatch.setattr(stage_suite, "_verify_scheduler_restoration", lambda: None)
    monkeypatch.setattr(stage_suite.time, "sleep", lambda _s: None)

    report = stage_suite._restore_scheduler_guarded()

    assert report == {
        "attempts": 3,
        "restored": True,
        "failed_gate": "write_ui_scheduler_restart",
    }


def test_run_write_browser_restores_scheduler_then_propagates_a_primary_interrupt(
    tmp_path, monkeypatch
):
    # An operator Ctrl-C aborting the drill is not a stage verdict: the guarded
    # restore still runs (never leave the scheduler down), but the interrupt
    # propagates with its exit semantics rather than being converted or recorded.
    context = _write_ui_context(tmp_path)
    events = []
    _install_write_browser_fakes(monkeypatch, tmp_path, events)

    def drive_interrupted(_context, _environment, _ready, _release, state):
        state["scheduler_stopped"] = True
        raise KeyboardInterrupt

    monkeypatch.setattr(stage_suite, "_drive_write_browser", drive_interrupted)

    with pytest.raises(KeyboardInterrupt):
        stage_suite._run_write_browser(
            context, week_key="2027-R01", week_date="2026-11-02"
        )

    assert "restart:scheduler" in events


def test_run_write_browser_success_path_fails_closed_when_restore_fails(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(stage_suite, "_write_browser_environment", lambda *a, **k: {})
    monkeypatch.setattr(
        stage_suite,
        "_drive_write_browser",
        lambda *_a, **_k: {"browser": "evidence"},
    )
    failed_report = {"attempts": 3, "restored": False, "failed_gate": "dead"}
    monkeypatch.setattr(
        stage_suite, "_restore_scheduler_guarded", lambda: failed_report
    )

    class _Context:
        evidence_root = tmp_path
        harness_root = tmp_path

    with pytest.raises(
        stage_suite.StageGateError, match="write_ui_scheduler_restore_failed"
    ) as excinfo:
        stage_suite._run_write_browser(
            _Context(), week_key="2026-W32", week_date="2026-08-03"
        )

    assert excinfo.value.restoration is failed_report


def test_run_write_browser_success_records_restoration_after_retry(
    tmp_path, monkeypatch
):
    # The #160 combined scenario: browser evidence succeeds, the FIRST restore
    # attempt fails, the retry succeeds — the stage passes and the evidence
    # carries the real restoration report.
    calls = {"restore": 0}

    def restore_fail_once():
        calls["restore"] += 1
        if calls["restore"] == 1:
            raise stage_suite.StageGateError("write_ui_scheduler_restart")

    monkeypatch.setattr(stage_suite, "_write_browser_environment", lambda *a, **k: {})
    monkeypatch.setattr(
        stage_suite,
        "_drive_write_browser",
        lambda *_a, **_k: {"browser": "evidence"},
    )
    monkeypatch.setattr(stage_suite, "_restore_scheduler", restore_fail_once)
    monkeypatch.setattr(stage_suite, "_verify_scheduler_restoration", lambda: None)
    monkeypatch.setattr(stage_suite.time, "sleep", lambda _s: None)

    class _Context:
        evidence_root = tmp_path
        harness_root = tmp_path

    result = stage_suite._run_write_browser(
        _Context(), week_key="2026-W32", week_date="2026-08-03"
    )

    assert result["browser"] == "evidence"
    assert result["scheduler_restoration"] == {
        "attempts": 2,
        "restored": True,
        "failed_gate": None,
    }


def test_run_write_browser_failure_path_attaches_restoration_report(
    tmp_path, monkeypatch
):
    report = {"attempts": 1, "restored": True, "failed_gate": None}

    def drive_and_fail(_context, _environment, _ready, _release, state):
        state["scheduler_stopped"] = True
        raise stage_suite.StageGateError("write_browser_result_not_accepted")

    monkeypatch.setattr(stage_suite, "_write_browser_environment", lambda *a, **k: {})
    monkeypatch.setattr(stage_suite, "_drive_write_browser", drive_and_fail)
    monkeypatch.setattr(stage_suite, "_restore_scheduler_guarded", lambda: report)

    class _Context:
        evidence_root = tmp_path
        harness_root = tmp_path

    with pytest.raises(
        stage_suite.StageGateError, match="write_browser_result_not_accepted"
    ) as excinfo:
        stage_suite._run_write_browser(
            _Context(), week_key="2026-W32", week_date="2026-08-03"
        )

    assert excinfo.value.restoration is report


def test_main_propagates_a_primary_interrupt_without_writing_a_manifest(
    tmp_path, monkeypatch
):
    # An operator interrupt is not a stage verdict: it propagates with its own
    # process semantics and writes NO manifest — a FAIL manifest here would
    # stamp a contradiction beside an already-written PASS if the abort landed
    # just after a stage completed.
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    args = stage_suite.argparse.Namespace(
        stage="LOCAL-WRITE-UI-1",
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=evidence_root,
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 8, 9),
    )

    def interrupt(_context):
        raise KeyboardInterrupt

    monkeypatch.setattr(stage_suite, "_parse_args", lambda _argv: args)
    monkeypatch.setattr(stage_suite, "run_local_write_ui", interrupt)

    with pytest.raises(KeyboardInterrupt):
        stage_suite.main([])

    assert not (evidence_root / "LOCAL-WRITE-UI-1-failure.json").exists()


def test_rta1_manifest_records_a_swallowed_teardown_error(tmp_path, monkeypatch):
    # Containing a _stop_runtime() failure must not make it INVISIBLE: the
    # teardown error is recorded on the manifest so orphaned processes are
    # explained, while the primary gate still leads (#160 round-4).
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    args = stage_suite.argparse.Namespace(
        stage="LOCAL-RTA-1",
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=evidence_root,
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 8, 9),
    )

    def gate_fails(_context):
        raise stage_suite.StageGateError("rta1_bearer_rejected")

    def teardown_times_out():
        raise stage_suite.subprocess.TimeoutExpired(cmd="pm2", timeout=30)

    monkeypatch.setattr(stage_suite, "_parse_args", lambda _argv: args)
    monkeypatch.setattr(stage_suite, "run_local_rta", gate_fails)
    monkeypatch.setattr(stage_suite, "_stop_runtime", teardown_times_out)

    assert stage_suite.main([]) == 1

    failure = json.loads(
        (evidence_root / "LOCAL-RTA-1-failure.json").read_text(encoding="utf-8")
    )
    assert failure["failed_gate"] == "rta1_bearer_rejected"
    assert failure["teardown_error"] == "unexpected_TimeoutExpired"


@pytest.mark.parametrize(
    "teardown_error",
    ("frontend_process_cleanup_failed", "frontend_log_cleanup_failed"),
)
def test_write_activation_manifest_records_frontend_cleanup_failure(
    tmp_path, monkeypatch, teardown_error
):
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    args = stage_suite.argparse.Namespace(
        stage="LOCAL-WRITE-ACT-1",
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=evidence_root,
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 8, 9),
    )

    def browser_and_cleanup_fail(_context):
        error = stage_suite.StageGateError("browser_failed")
        error.teardown_error = teardown_error
        raise error

    monkeypatch.setattr(stage_suite, "_parse_args", lambda _argv: args)
    monkeypatch.setattr(
        stage_suite,
        "run_local_write_activation",
        browser_and_cleanup_fail,
    )

    assert stage_suite.main([]) == 1

    failure = json.loads(
        (evidence_root / "LOCAL-WRITE-ACT-1-failure.json").read_text(encoding="utf-8")
    )
    assert {
        "failed_gate": failure["failed_gate"],
        "teardown_error": failure["teardown_error"],
    } == {
        "failed_gate": "browser_failed",
        "teardown_error": teardown_error,
    }


def test_write_ui_failure_manifest_preserves_restoration_for_unexpected_errors(
    tmp_path, monkeypatch
):
    # main() wraps a non-StageGateError primary in unexpected_<Type>; the
    # restoration report must survive that wrapping into the failure manifest.
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    args = stage_suite.argparse.Namespace(
        stage="LOCAL-WRITE-UI-1",
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=evidence_root,
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 8, 9),
    )

    def fail_with_restoration(_context):
        error = RuntimeError("browser exploded")
        error.restoration = {"attempts": 2, "restored": True, "failed_gate": None}
        raise error

    monkeypatch.setattr(stage_suite, "_parse_args", lambda _argv: args)
    monkeypatch.setattr(stage_suite, "run_local_write_ui", fail_with_restoration)

    assert stage_suite.main([]) == 1
    failure = json.loads(
        (evidence_root / "LOCAL-WRITE-UI-1-failure.json").read_text(encoding="utf-8")
    )
    assert failure.pop("failed_at").endswith("Z")
    assert failure == {
        "stage": "LOCAL-WRITE-UI-1",
        "verdict": "FAIL",
        "release_sha": "8" * 40,
        "frontend_sha": "9" * 40,
        "failed_gate": "unexpected_RuntimeError",
        "restoration": {"attempts": 2, "restored": True, "failed_gate": None},
    }


def test_write_ui_failure_manifest_is_checksummed_with_predicate_codes(
    tmp_path, monkeypatch
):
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    args = stage_suite.argparse.Namespace(
        stage="LOCAL-WRITE-UI-1",
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=evidence_root,
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 8, 9),
        diagnostic=False,
    )

    def fail_with_predicates(_context):
        error = stage_suite.StageGateError("write_browser_result_not_accepted")
        error.predicate_codes = (
            "create_status_not_201",
            "outage_submit_status_not_502",
        )
        raise error

    monkeypatch.setattr(stage_suite, "_parse_args", lambda _argv: args)
    monkeypatch.setattr(stage_suite, "run_local_write_ui", fail_with_predicates)

    assert stage_suite.main([]) == 1
    target = evidence_root / "LOCAL-WRITE-UI-1-failure.json"
    failure = json.loads(target.read_text(encoding="utf-8"))
    assert failure["predicate_codes"] == [
        "create_status_not_201",
        "outage_submit_status_not_502",
    ]
    assert stage_suite._read_checksum_index(evidence_root / "SHA256SUMS") == {
        target.name: stage_suite._hash_file(target)
    }


@pytest.mark.parametrize(
    ("failed_operation", "expected_code"),
    [
        ("write", "failure_manifest_write_failed"),
        ("checksum", "failure_manifest_checksum_failed"),
    ],
)
def test_main_surfaces_failure_manifest_publication_errors(
    tmp_path, monkeypatch, capsys, failed_operation, expected_code
):
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    args = stage_suite.argparse.Namespace(
        stage="LOCAL-WRITE-UI-1",
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=evidence_root,
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 8, 9),
        diagnostic=False,
    )

    def primary_failure(_context):
        raise stage_suite.StageGateError("injected_primary_failure")

    monkeypatch.setattr(stage_suite, "_parse_args", lambda _argv: args)
    monkeypatch.setattr(stage_suite, "run_local_write_ui", primary_failure)
    if failed_operation == "write":
        monkeypatch.setattr(
            stage_suite,
            "write_stage_manifest",
            lambda *_args: (_ for _ in ()).throw(OSError("write failed")),
        )
    else:
        monkeypatch.setattr(
            stage_suite,
            "_checksum_manifest",
            lambda *_args: (_ for _ in ()).throw(OSError("checksum failed")),
        )

    assert stage_suite.main([]) == stage_suite.FAILURE_MANIFEST_EXIT_CODE
    assert capsys.readouterr().err.splitlines() == [f"FAIL {expected_code}"]


def test_parse_args_rejects_diagnostic_mode_for_acceptance_evidence_root():
    with pytest.raises(SystemExit):
        stage_suite._parse_args(
            [
                "LOCAL-WRITE-UI-1",
                "--release-sha",
                "8" * 40,
                "--frontend-sha",
                "9" * 40,
                "--execution-kind",
                "canonical",
                "--diagnostic",
            ]
        )


def test_parse_args_accepts_write_ui_diagnostic_with_separate_evidence_root(
    tmp_path,
):
    args = stage_suite._parse_args(
        [
            "LOCAL-WRITE-UI-1",
            "--release-sha",
            "8" * 40,
            "--frontend-sha",
            "9" * 40,
            "--execution-kind",
            "canonical",
            "--diagnostic",
            "--evidence-root",
            str(tmp_path / "diagnostic-evidence"),
        ]
    )

    assert args.diagnostic is True


def test_write_ui_diagnostic_manifest_never_advances_acceptance_state(
    tmp_path, monkeypatch
):
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "diagnostic-evidence",
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 8, 16),
    )

    def reject_state_write(*_args, **_kwargs):
        raise AssertionError("diagnostic mode must not write stage state")

    monkeypatch.setattr(stage_suite, "_save_state", reject_state_write)

    manifest = stage_suite._write_local_write_ui_manifest(
        context,
        {"write_browser": {"create_result": {"status": 201}}},
        diagnostic=True,
    )

    assert manifest["stage"] == "LOCAL-WRITE-UI-DIAGNOSTIC"
    assert manifest["verdict"] == "DIAGNOSTIC_PASS"
    assert manifest["acceptance_evidence"] is False
    assert not (context.evidence_root / "stage-state.json").exists()
    assert (context.evidence_root / "LOCAL-WRITE-UI-DIAGNOSTIC.json").exists()


def test_write_ui_diagnostic_clears_prior_pass_before_new_attempt(
    tmp_path, monkeypatch
):
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "diagnostic-evidence",
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 8, 16),
    )
    target = context.evidence_root / "LOCAL-WRITE-UI-DIAGNOSTIC.json"
    stage_suite._write_local_write_ui_manifest(
        context,
        {"write_browser": {"create_result": {"status": 201}}},
        diagnostic=True,
    )
    monkeypatch.setattr(stage_suite, "_verify_source_checkouts", lambda _context: None)

    def stop_before_drill(_context):
        raise stage_suite.StageGateError("frontend_source_identity_stale")

    monkeypatch.setattr(stage_suite, "_verify_frontend_source", stop_before_drill)

    with pytest.raises(
        stage_suite.StageGateError,
        match="frontend_source_identity_stale",
    ):
        stage_suite.run_local_write_ui(context, diagnostic=True)

    assert not target.exists()
    assert target.name not in stage_suite._read_checksum_index(
        context.evidence_root / "SHA256SUMS"
    )


def test_write_ui_diagnostic_rejects_canonical_acceptance_machine(
    tmp_path, monkeypatch
):
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "diagnostic-evidence",
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 8, 16),
    )
    monkeypatch.setattr(
        stage_suite.os,
        "uname",
        lambda: SimpleNamespace(nodename="munbon-control-plan-local"),
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_ui_diagnostic_machine_not_isolated",
    ):
        stage_suite._verify_write_ui_diagnostic_isolation(context)


def test_validate_write_browser_result_projects_refresh_reuse_statuses():
    # The projection must ECHO the observed 401s; checked-then-dropped evidence
    # is the capture-then-discard pattern this stage exists to delete.
    result = stage_suite.validate_write_browser_result(_write_browser_evidence())

    assert result["field_team_result"]["refresh_reuse_status"] == 401
    assert result["logout_result"]["refresh_reuse_status"] == 401
    assert result["logout_result"]["second_context_refresh_reuse_status"] == 401


def test_validate_write_browser_result_rejects_forbidden_write_count():
    evidence = _write_browser_evidence()
    evidence["request_inventory"]["forbidden_write_count"] = 1
    evidence["request_inventory"]["forbidden_writes"] = ["POST /x 201"]

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_forbidden_writes_when_count_claims_zero():
    """The merged stage's defect in miniature: `forbiddenMutations` was declared
    but never appended to, so the count read 0 no matter what the browser did.
    The recorded list -- not the self-reported count -- is the evidence, so a
    non-empty list must reject even when the count claims zero."""
    evidence = _write_browser_evidence()
    evidence["request_inventory"]["forbidden_writes"] = [
        "POST /api/smart-water-backend/water-planning/planning-depth-submissions 201"
    ]
    evidence["request_inventory"]["forbidden_write_count"] = 0

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_nonuuid_submission_id():
    evidence = _write_browser_evidence()
    evidence["create_result"]["submission_id"] = "not-a-uuid"

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_lingering_reads_preserved_claim():
    """The exact fabrication R2 exists to delete: a residual `reads_preserved`
    key must reject rather than ride along unread."""
    evidence = _write_browser_evidence()
    evidence["outage_result"]["reads_preserved"] = True

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_outage_read_that_succeeded():
    evidence = _write_browser_evidence()
    evidence["outage_result"]["roster_status"] = 200
    evidence["outage_result"]["observed_roster_status"] = 200
    evidence["outage_result"]["panel_roster_status"] = 200

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_outage_with_submit_present():
    evidence = _write_browser_evidence()
    evidence["outage_result"]["submit_absent"] = False

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_outage_write_that_succeeded():
    evidence = _write_browser_evidence()
    evidence["outage_result"]["submit_status"] = 201

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_field_team_that_saw_reads():
    evidence = _write_browser_evidence()
    # Move the passive observation too, so the contradiction check cannot reject
    # this for a different reason than the one the test names.
    evidence["field_team_result"]["roster_status"] = 200
    evidence["field_team_result"]["observed_roster_status"] = 200
    evidence["field_team_result"]["panel_roster_status"] = 200

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_field_team_successful_submit():
    evidence = _write_browser_evidence()
    evidence["field_team_result"]["submit_status"] = 201

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_field_team_with_submit_present():
    evidence = _write_browser_evidence()
    evidence["field_team_result"]["submit_absent"] = False

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_outage_mistaken_for_denial():
    """Outage and denial must stay distinguishable: the product renders a
    different banner for each (PlanningRhsPanel.tsx:517 vs :522). Accepting an
    outage whose banner says 'denied' would let a permission bug pass as an
    outage drill."""
    evidence = _write_browser_evidence()
    evidence["outage_result"]["unavailable_banner"] = False

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_logout_redirect_to_dashboard():
    """The merged validator accepted ANY string here and then emitted
    `safe_redirect: True` regardless -- this input is what it wrongly passed."""
    evidence = _write_browser_evidence()
    evidence["logout_result"]["redirect_url"] = "/smart-water/dashboard/water-planning"

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_failed_logout_status():
    evidence = _write_browser_evidence()
    evidence["logout_result"]["status"] = 500

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_missing_outage_proof():
    evidence = _write_browser_evidence()
    del evidence["outage_result"]

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_field_team_submit_that_only_conflicted():
    """A 409 means the field team got PAST authorization to the concurrency
    check -- i.e. it was wrongly authorized. Accepting any non-2xx as 'denied'
    would let exactly the regression R7 exists to detect slip through."""
    evidence = _write_browser_evidence()
    evidence["field_team_result"]["submit_status"] = 409

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_field_team_submit_that_never_left_browser():
    """A transport failure is not a denial. The browser reports `None` rather
    than a fake 0 so this can never be read as a status."""
    evidence = _write_browser_evidence()
    evidence["field_team_result"]["submit_status"] = None

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_field_team_submit_rejected_as_unauthenticated():
    """401 means the bearer was not attached -- a C1 regression masquerading as
    a denial. Only a real 403 proves the principal was identified and refused."""
    evidence = _write_browser_evidence()
    evidence["field_team_result"]["submit_status"] = 401

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_outage_submit_that_never_left_browser():
    evidence = _write_browser_evidence()
    evidence["outage_result"]["submit_status"] = None

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_missing_field_team_logout():
    evidence = _write_browser_evidence()
    evidence["field_team_result"]["logout_status"] = 500

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_echoes_observed_banners_not_literals():
    """The runbook claims the manifest distinguishes denial from outage, so the
    banner facts must actually appear in the emitted evidence."""
    result = stage_suite.validate_write_browser_result(_write_browser_evidence())

    assert result["field_team_result"]["denied_banner"] is True
    assert result["outage_result"]["unavailable_banner"] is True
    assert result["field_team_result"]["logout_status"] == 200


def test_validate_write_browser_result_rejects_outage_showing_the_denial_banner():
    """The runbook claims the two banners keep an outage from being recorded as a
    permission denial. That is only true if the validator asserts the ABSENCE of
    the other banner -- asserting presence alone leaves the claim unenforced."""
    evidence = _write_browser_evidence()
    evidence["outage_result"]["denied_banner"] = True

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_field_team_showing_the_unavailable_banner():
    """`resolvePlanningMutationPolicy` collapses not-requested/loading/
    unauthenticated/unavailable into one `unavailable` state, so an expired
    session would render the outage banner. A denial must not show it."""
    evidence = _write_browser_evidence()
    evidence["field_team_result"]["unavailable_banner"] = True

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_uniform_zone_fanout():
    """41 rows is not proof of a correct expansion: a regression that served every
    section one zone's depth still returns exactly 41. The repo's own
    `validate_w2_active_result` docstring says so -- but that strong check covers
    the DIRECT API path, against a different submission, so the UI-path readback
    needs its own."""
    evidence = _write_browser_evidence()
    evidence["active_readback"]["distinct_depths"] = [250.0]

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_outage_whose_passive_read_succeeded():
    """The app's own query 200-ing while the explicit probe 502s means a stale
    cache is being served as live data. Capturing that contradiction and then
    discarding it unread is the defect class rounds 1-2 removed."""
    evidence = _write_browser_evidence()
    evidence["outage_result"]["observed_roster_status"] = 200

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_accepts_absent_passive_observation():
    """A drill where the app never issued its own roster GET is legitimate -- the
    explicit probe is the primary evidence. Only a CONTRADICTION is fatal."""
    evidence = _write_browser_evidence()
    evidence["field_team_result"]["observed_roster_status"] = None

    result = stage_suite.validate_write_browser_result(evidence)

    assert result["field_team_result"]["roster_status"] == 403


def test_validate_write_browser_result_rejects_banner_rendered_before_the_reads_settled():
    """The panel renders its `unavailable` banner from the `not-requested`
    placeholder, BEFORE the roster/active queries are issued. Without pinning the
    status the app's own read actually returned, the outage drill would pass
    having asked nothing -- self-fulfilling evidence."""
    evidence = _write_browser_evidence()
    evidence["outage_result"]["panel_roster_status"] = None

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_panel_read_disagreeing_with_probe():
    evidence = _write_browser_evidence()
    evidence["field_team_result"]["panel_roster_status"] = 200

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_reload_that_only_reloaded_login():
    """If hydration beats `commit`, the reload re-requests /login and proves
    nothing. Capturing that and not reading it is the 'capture then discard'
    pattern this stage's own checks condemn."""
    evidence = _write_browser_evidence()
    evidence["reload_result"]["reloaded_from"] = "/login"

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_inventory_that_observed_no_mutations():
    """`forbidden_writes == []` is also what an inventory that saw NOTHING
    produces -- the merged stage's defect in a new costume. The harness issues
    exactly five W2 POSTs, so a live boundary must have seen at least that many."""
    evidence = _write_browser_evidence()
    evidence["request_inventory"]["total_mutations"] = 0

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_absent_passive_observation_key():
    """An ABSENT key must not be indistinguishable from an observed None: a
    browser regression that stops emitting the field would degrade silently."""
    evidence = _write_browser_evidence()
    del evidence["field_team_result"]["observed_roster_status"]

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def test_validate_write_browser_result_rejects_missing_field_team_proof():
    evidence = _write_browser_evidence()
    del evidence["field_team_result"]

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite.validate_write_browser_result(evidence)


def _write_ui_context(tmp_path):
    runtime_env_dir = tmp_path / "runtime-env"
    runtime_env_dir.mkdir(parents=True, exist_ok=True)
    (runtime_env_dir / "operator.env").write_text(
        "MUNBON_OPERATOR_EMAIL=operator@local.invalid\n"
        "MUNBON_OPERATOR_PASSWORD=disposable-operator-secret\n",
        encoding="utf-8",
    )
    (runtime_env_dir / "field-team.env").write_text(
        "MUNBON_FIELD_TEAM_EMAIL=field-team@local.invalid\n"
        "MUNBON_FIELD_TEAM_PASSWORD=disposable-field-team-secret\n",
        encoding="utf-8",
    )
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)
    return stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        harness_root=MODULE_PATH.parent,
        evidence_root=evidence_root,
        runtime_env_dir=runtime_env_dir,
    )


def test_write_browser_environment_supplies_every_required_env_name(tmp_path):
    """C2 in test form: the browser aborts before login if any `required(...)`
    name is absent from the launcher env. The merged stage asked for
    LOCAL_OPERATOR_* while bootstrap writes MUNBON_OPERATOR_*, so it could never
    have logged in. Parse the names out of the JS rather than restating them,
    so adding a new `required(...)` cannot silently go unprovisioned."""
    context = _write_ui_context(tmp_path)
    environment = stage_suite._write_browser_environment(
        context,
        week_key="2027-R01",
        week_date="2026-11-02",
        ready_path=context.evidence_root / ".write-ui-ready",
        release_path=context.evidence_root / ".write-ui-outage-release",
    )

    source = (MODULE_PATH.parent / "run-write-browser.js").read_text(encoding="utf-8")
    required_names = set(re.findall(r'required\("([A-Z0-9_]+)"\)', source))

    assert required_names, "parsed no required() names -- the parse itself is broken"
    assert sorted(n for n in required_names if not environment.get(n)) == []


def test_write_browser_environment_binds_coordination_to_the_resolved_evidence_root(
    tmp_path,
):
    context = _write_ui_context(tmp_path)
    environment = stage_suite._write_browser_environment(
        context,
        week_key="2027-R01",
        week_date="2026-11-02",
        ready_path=context.evidence_root / ".write-ui-ready",
        release_path=context.evidence_root / ".write-ui-outage-release",
    )

    assert environment["LOCAL_WRITE_UI_EVIDENCE_ROOT"] == str(
        context.evidence_root.resolve()
    )


def test_write_browser_environment_rejects_removed_transport_comparison_switch(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("LOCAL_WRITE_UI_DIAGNOSTIC", "1")
    context = _write_ui_context(tmp_path)
    kwargs = {
        "week_key": "2027-R01",
        "week_date": "2026-11-02",
        "ready_path": context.evidence_root / ".write-ui-ready",
        "release_path": context.evidence_root / ".write-ui-outage-release",
    }

    environment = stage_suite._write_browser_environment(context, **kwargs)

    assert environment.get("LOCAL_WRITE_UI_DIAGNOSTIC") is None
    with pytest.raises(TypeError):
        stage_suite._write_browser_environment(context, diagnostic=True, **kwargs)


def test_run_write_browser_does_not_forward_removed_transport_comparison_switch(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("LOCAL_WRITE_UI_DIAGNOSTIC", "1")
    context = _write_ui_context(tmp_path)
    observed = {}

    def capture_environment(_context, environment, *_args):
        observed.update(environment)
        return {"write_browser": "evidence"}

    monkeypatch.setattr(stage_suite, "_drive_write_browser", capture_environment)
    monkeypatch.setattr(
        stage_suite,
        "_restore_scheduler_guarded",
        lambda: {"attempts": 1, "restored": True, "failed_gate": None},
    )

    result = stage_suite._run_write_browser(
        context,
        week_key="2027-R01",
        week_date="2026-11-02",
    )

    assert observed.get("LOCAL_WRITE_UI_DIAGNOSTIC") is None
    assert result["write_browser"] == "evidence"


def test_run_write_browser_resolves_a_symlinked_evidence_root(tmp_path, monkeypatch):
    context = _write_ui_context(tmp_path)
    resolved_root = tmp_path / "resolved-evidence"
    resolved_root.mkdir()
    alias_root = tmp_path / "diagnostic-alias"
    alias_root.symlink_to(resolved_root, target_is_directory=True)
    context = dataclasses.replace(context, evidence_root=alias_root)
    observed = {}

    def capture_environment(_context, *, ready_path, release_path, **_kwargs):
        observed["ready_path"] = ready_path
        observed["release_path"] = release_path
        raise stage_suite.StageGateError("captured_coordination_paths")

    monkeypatch.setattr(stage_suite, "_write_browser_environment", capture_environment)

    with pytest.raises(
        stage_suite.StageGateError, match="^captured_coordination_paths$"
    ):
        stage_suite._run_write_browser(
            context, week_key="2027-R01", week_date="2026-11-02"
        )

    assert observed == {
        "ready_path": resolved_root.resolve() / ".write-ui-ready",
        "release_path": resolved_root.resolve() / ".write-ui-outage-release",
    }


def test_write_coordination_file_refuses_an_existing_symlink(tmp_path):
    victim = tmp_path / "victim"
    victim.write_text("unchanged\n", encoding="utf-8")
    target = tmp_path / ".write-ui-outage-release"
    target.symlink_to(victim)

    with pytest.raises(
        stage_suite.StageGateError, match="^coordination_file_not_private$"
    ):
        stage_suite._write_coordination_file(target, "released\n")

    assert victim.read_text(encoding="utf-8") == "unchanged\n"


def test_write_browser_environment_fails_closed_without_field_team_credentials(
    tmp_path,
):
    context = _write_ui_context(tmp_path)
    (context.runtime_env_dir / "field-team.env").write_text("", encoding="utf-8")

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_credentials_missing",
    ):
        stage_suite._write_browser_environment(
            context,
            week_key="2027-R01",
            week_date="2026-11-02",
            ready_path=context.evidence_root / ".write-ui-ready",
            release_path=context.evidence_root / ".write-ui-outage-release",
        )


class _FakeWriteBrowserProcess:
    """Stands in for the Playwright browser: signals ready on the second poll,
    then writes truthful evidence to the stdout spill file once released.

    It writes to the SINK rather than returning from communicate(), because the
    real runner spills both pipes to temp files -- piping them would let a chatty
    browser fill the buffer during the healthy phase and deadlock before the
    ready file is written.
    """

    def __init__(self, ready_path, events, payload, stdout_sink):
        self._ready_path = ready_path
        self._events = events
        self._payload = payload
        self._stdout_sink = stdout_sink
        self._polls = 0
        self.returncode = 0

    def poll(self):
        self._polls += 1
        if self._polls >= 2 and not self._ready_path.exists():
            self._ready_path.write_text("ready\n", encoding="utf-8")
            self._events.append("browser_ready")
        return None

    def communicate(self, timeout=None):
        self._events.append("browser_exit")
        if self._stdout_sink is not None:
            self._stdout_sink.write(json.dumps(self._payload))
        return None, None

    def wait(self, timeout=None):
        return 0

    def kill(self):
        return None

    def terminate(self):
        return None


def _scheduler_jlist_entries(*statuses):
    return json.dumps(
        [
            {
                "name": "scheduler",
                "pid": 4242 + i,
                "pm2_env": {"status": s, "restart_time": 0},
                "monit": {"memory": 1024, "cpu": 0},
            }
            for i, s in enumerate(statuses)
        ]
    )


def _scheduler_jlist(status):
    """A minimal pm2 jlist body that project_pm2_state accepts."""
    return json.dumps(
        [
            {
                "name": "scheduler",
                "pid": 4242,
                "pm2_env": {"status": status, "restart_time": 0},
                "monit": {"memory": 1024, "cpu": 0},
            }
        ]
    )


def _install_write_browser_fakes(monkeypatch, tmp_path, events, payload=None):
    ready_path = tmp_path / "evidence" / ".write-ui-ready"
    body = payload if payload is not None else _write_browser_evidence()

    def fake_popen(*_args, **kwargs):
        events.append("browser_spawned")
        return _FakeWriteBrowserProcess(ready_path, events, body, kwargs.get("stdout"))

    def fake_run_checked(label, argv, **_kwargs):
        if argv == stage_suite._pm2_command("jlist"):
            events.append("jlist:scheduler")
            return _scheduler_jlist("online")
        events.append(f"{argv[2]}:{argv[3]}")
        return ""

    def fake_write_coordination_file(path, value):
        events.append("release_written")
        path.write_text(value, encoding="utf-8")

    monkeypatch.setattr(stage_suite.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(stage_suite, "_run_checked", fake_run_checked)
    monkeypatch.setattr(
        stage_suite, "_write_coordination_file", fake_write_coordination_file
    )
    monkeypatch.setattr(stage_suite, "_stop_temporary_process", lambda _p: None)
    monkeypatch.setattr(
        stage_suite, "_wait_json", lambda *_a, **_k: {"status": "ready"}
    )
    monkeypatch.setattr(stage_suite, "LocalHttpClient", lambda *_a, **_k: object())
    monkeypatch.setattr(stage_suite.time, "sleep", lambda _s: None)


def test_run_write_browser_stops_scheduler_only_after_ready_and_restores_after(
    tmp_path, monkeypatch
):
    """The outage must be REAL and correctly ordered: the scheduler may only go
    down once the browser has finished its healthy-path work and signalled
    ready, and must be back up before the stage continues."""
    context = _write_ui_context(tmp_path)
    events = []
    _install_write_browser_fakes(monkeypatch, tmp_path, events)

    result = stage_suite._run_write_browser(
        context, week_key="2027-R01", week_date="2026-11-02"
    )

    assert result["outage_result"]["roster_status"] == 502
    assert events.index("browser_ready") < events.index("stop:scheduler")
    assert events.index("stop:scheduler") < events.index("release_written")
    assert events.index("release_written") < events.index("browser_exit")
    assert events.index("browser_exit") < events.index("restart:scheduler")


def test_run_write_browser_fails_closed_when_scheduler_restore_fails(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    events = []
    _install_write_browser_fakes(monkeypatch, tmp_path, events)

    def failing_run_checked(label, argv, **_kwargs):
        if argv == stage_suite._pm2_command("jlist"):
            # The restart genuinely never took: pm2 still reports it stopped.
            return _scheduler_jlist("stopped")
        events.append(f"{argv[2]}:{argv[3]}")
        if argv[2] == "restart":
            raise stage_suite.StageGateError("pm2_restart_failed")
        return ""

    monkeypatch.setattr(stage_suite, "_run_checked", failing_run_checked)

    with pytest.raises(stage_suite.StageGateError, match="scheduler_restore_failed"):
        stage_suite._run_write_browser(
            context, week_key="2027-R01", week_date="2026-11-02"
        )

    assert "restart:scheduler" in events


def test_run_write_browser_restores_scheduler_when_the_stop_itself_times_out(
    tmp_path, monkeypatch
):
    """`pm2 stop` frequently still takes effect after the CLI call times out. If
    the 'stopped' flag were only set once the call RETURNED, a timeout would skip
    the restore and leave every later stage running against a dead scheduler."""
    context = _write_ui_context(tmp_path)
    events = []
    _install_write_browser_fakes(monkeypatch, tmp_path, events)

    def stop_times_out(label, argv, **_kwargs):
        if argv == stage_suite._pm2_command("jlist"):
            return _scheduler_jlist("online")
        events.append(f"{argv[2]}:{argv[3]}")
        if argv[2] == "stop":
            raise stage_suite.StageGateError("write_ui_scheduler_stop_failed")
        return ""

    monkeypatch.setattr(stage_suite, "_run_checked", stop_times_out)

    with pytest.raises(stage_suite.StageGateError):
        stage_suite._run_write_browser(
            context, week_key="2027-R01", week_date="2026-11-02"
        )

    assert "restart:scheduler" in events


def test_run_write_browser_keeps_the_primary_diagnosis_when_restore_also_fails(
    tmp_path, monkeypatch
):
    """The manifest persists only the error CODE, so if the restore's exception
    replaced the primary one the operator would read 'pm2 hiccuped' when the real
    finding was 'the evidence was untruthful'."""
    context = _write_ui_context(tmp_path)
    events = []
    untruthful = _write_browser_evidence()
    untruthful["outage_result"]["roster_status"] = 200
    _install_write_browser_fakes(monkeypatch, tmp_path, events, payload=untruthful)

    def restart_fails(label, argv, **_kwargs):
        if argv == stage_suite._pm2_command("jlist"):
            # Dead for real: the primary diagnosis must still lead the code.
            return _scheduler_jlist("stopped")
        events.append(f"{argv[2]}:{argv[3]}")
        if argv[2] == "restart":
            raise stage_suite.StageGateError("pm2_restart_failed")
        return ""

    monkeypatch.setattr(stage_suite, "_run_checked", restart_fails)

    with pytest.raises(stage_suite.StageGateError) as excinfo:
        stage_suite._run_write_browser(
            context, week_key="2027-R01", week_date="2026-11-02"
        )

    # Full-code pin: a regression to the bare primary code would still satisfy
    # a substring match — the combined "name BOTH" code is the behavior.
    assert (
        str(excinfo.value)
        == "write_browser_result_not_accepted_and_scheduler_restore_failed"
    )
    assert excinfo.value.predicate_codes == (
        "outage_roster_status_not_502",
        "outage_panel_roster_status_mismatch",
        "outage_observed_roster_status_mismatch",
    )
    assert "restart:scheduler" in events


def test_run_write_browser_restores_scheduler_when_evidence_is_rejected(
    tmp_path, monkeypatch
):
    """A failed drill must not leave the scheduler down for every later stage."""
    context = _write_ui_context(tmp_path)
    events = []
    untruthful = _write_browser_evidence()
    untruthful["outage_result"]["roster_status"] = 200
    _install_write_browser_fakes(monkeypatch, tmp_path, events, payload=untruthful)

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_browser_result_not_accepted",
    ):
        stage_suite._run_write_browser(
            context, week_key="2027-R01", week_date="2026-11-02"
        )

    assert "restart:scheduler" in events


class _RefreshClient:
    def __init__(self, status):
        self._status = status
        self.calls = []

    def request(self, method, url, *, payload=None, bearer=None, **_kwargs):
        self.calls.append((method, url))
        return stage_suite.HttpResult(status=self._status, body={}, headers={})


def test_operator_refresh_reuse_after_logout_is_rejected():
    client = _RefreshClient(401)

    evidence = stage_suite._assert_operator_refresh_reuse_rejected(
        client, "refresh-token"
    )

    assert evidence == {"refresh_reuse_status": 401, "revoked": True}
    assert client.calls == [("POST", "http://127.0.0.1:3005/api/v1/auth/refresh")]


def test_operator_refresh_reuse_that_still_works_fails_the_stage():
    """Logout revokes rather than deletes the refresh token, so the only proof
    that the session is really gone is that reusing it now fails."""
    client = _RefreshClient(200)

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_ui_refresh_reuse_not_rejected",
    ):
        stage_suite._assert_operator_refresh_reuse_rejected(client, "refresh-token")


def test_build_planning_depth_request_v2_uses_rid_calendar():
    request = stage_suite._build_planning_depth_request_v2(
        week_date="2026-11-02",
        week_key="2027-R01",
        client_submission_id="00000000-0000-4000-a000-000000000001",
        active_submission_id=None,
        depth_offset="0.100",
    )

    assert request["schema_version"] == 2
    assert request["calendar_system"] == "rid-irrigation-v1"
    assert request["week_key"] == "2027-R01"
    assert request["project_key"] == "mun-bon"
    assert len(request["levels"]) == 6
    assert all(level["area_type"] == "zone" for level in request["levels"])


def test_write_ui_rid_week_matches_canonical_rid_calendar():
    assert stage_suite._write_ui_rid_week(date(2026, 11, 1)) == (
        "2026-11-01",
        "2027-R01",
    )
    assert stage_suite._write_ui_rid_week(date(2026, 11, 2)) == (
        "2026-11-01",
        "2027-R01",
    )
    assert stage_suite._write_ui_rid_week(date(2026, 11, 7)) == (
        "2026-11-01",
        "2027-R01",
    )
    assert stage_suite._write_ui_rid_week(date(2026, 11, 8)) == (
        "2026-11-08",
        "2027-R02",
    )
    assert stage_suite._write_ui_rid_week(date(2026, 10, 31)) == (
        "2026-10-31",
        "2026-R53",
    )
    assert stage_suite._write_ui_rid_week(date(2026, 8, 6)) == (
        "2026-08-01",
        "2026-R40",
    )
    assert stage_suite._write_ui_rid_week(date(2025, 11, 1)) == (
        "2025-11-01",
        "2026-R01",
    )


def test_write_ui_namespace_differs_from_write_foundation():
    assert stage_suite.WRITE_UI_NAMESPACE != stage_suite.WRITE_FOUNDATION_NAMESPACE


# --- LOCAL-PERSIST-ONLY-1 ---


def test_stage_order_includes_persist_only_after_write_ui():
    assert stage_suite.STAGE_ORDER[-3:-1] == (
        "LOCAL-WRITE-UI-1",
        "LOCAL-PERSIST-ONLY-1",
    )


def test_stage_transition_accepts_persist_only_after_all_eight_prior_stages():
    stage_suite.validate_stage_transition(
        (
            "LOCAL-BASE-0",
            "LOCAL-RTA-1",
            "LOCAL-AC-1",
            "LOCAL-READ-ACT-1",
            "LOCAL-EVIDENCE-1",
            "LOCAL-GO-READ-1",
            "LOCAL-WRITE-FOUNDATION-1",
            "LOCAL-WRITE-UI-1",
        ),
        "LOCAL-PERSIST-ONLY-1",
    )


def test_stage_transition_rejects_persist_only_without_write_ui():
    with pytest.raises(stage_suite.StageGateError, match="stage_transition_invalid"):
        stage_suite.validate_stage_transition(
            (
                "LOCAL-BASE-0",
                "LOCAL-RTA-1",
                "LOCAL-AC-1",
                "LOCAL-READ-ACT-1",
                "LOCAL-EVIDENCE-1",
                "LOCAL-GO-READ-1",
                "LOCAL-WRITE-FOUNDATION-1",
            ),
            "LOCAL-PERSIST-ONLY-1",
        )


# --- LOCAL-WRITE-ACT-1 ---


def test_stage_order_includes_write_activation_after_persist_only():
    assert stage_suite.STAGE_ORDER[-2:] == (
        "LOCAL-PERSIST-ONLY-1",
        "LOCAL-WRITE-ACT-1",
    )


def test_stage_transition_requires_all_nine_predecessors_for_write_activation():
    stage_suite.validate_stage_transition(
        tuple(stage_suite.STAGE_ORDER[:9]), "LOCAL-WRITE-ACT-1"
    )

    with pytest.raises(stage_suite.StageGateError, match="stage_transition_invalid"):
        stage_suite.validate_stage_transition(
            tuple(stage_suite.STAGE_ORDER[:8]), "LOCAL-WRITE-ACT-1"
        )


def test_write_activation_rid_week_is_distinct_from_ui_and_persist_scopes():
    start = date(2026, 1, 1)

    for day_offset in range(366):
        operational_date = start + timedelta(days=day_offset)
        scopes = {
            stage_suite._write_ui_rid_week(operational_date),
            stage_suite._persist_only_rid_week(operational_date),
            stage_suite._write_activation_rid_week(operational_date),
        }
        assert len(scopes) == 3


def test_write_ui_and_write_activation_browser_results_use_separate_artifacts(tmp_path):
    context = _write_ui_context(tmp_path)
    evidence = _write_browser_evidence()

    write_ui = stage_suite._persist_write_browser_result(context, evidence)
    write_act = stage_suite._persist_write_browser_result(
        context,
        evidence,
        stage="LOCAL-WRITE-ACT-1",
    )

    assert write_ui.name == "LOCAL-WRITE-UI-1-browser-result.json"
    assert write_act.name == "LOCAL-WRITE-ACT-1-browser-result.json"
    assert write_ui.read_bytes() == write_act.read_bytes()


def test_write_activation_stability_requires_31_ordered_samples_over_900_seconds():
    now = [0.0]
    pm2 = [
        {
            "name": name,
            "status": "online",
            "restarts": 1,
            "pid": index + 10,
            "memory_bytes": 1024,
            "cpu_percent": 0,
        }
        for index, name in enumerate(stage_suite.PROCESS_NAMES)
    ]
    listeners = [{"address": "127.0.0.1", "port": 3022}]

    def monotonic():
        return now[0]

    def sleep(seconds):
        now[0] += seconds

    result = stage_suite._observe_write_activation_stability(
        duration_seconds=900,
        interval_seconds=30,
        readiness_probe=lambda: {
            name: {"status_code": 200, "status": "ready", "checks": {}}
            for name in stage_suite.PROCESS_NAMES
        },
        pm2_probe=lambda: pm2,
        listener_probe=lambda: listeners,
        frontend_probe=lambda: {
            "status_code": 200,
            "path": "/smart-water/dashboard",
        },
        monotonic=monotonic,
        sleep=sleep,
    )

    assert result == {
        "duration_seconds": 900,
        "observed_duration_seconds": 900.0,
        "interval_seconds": 30,
        "sample_count": 31,
        "samples": [
            {
                "scheduled_elapsed_seconds": elapsed,
                "observed_elapsed_seconds": float(elapsed),
                "readiness": {
                    name: {"status_code": 200, "status": "ready", "checks": {}}
                    for name in stage_suite.PROCESS_NAMES
                },
                "pm2": pm2,
                "listeners": listeners,
                "frontend": {
                    "status_code": 200,
                    "path": "/smart-water/dashboard",
                },
            }
            for elapsed in range(0, 901, 30)
        ],
    }


def test_write_activation_stability_rejects_frontend_probe_failure():
    pm2 = [
        {
            "name": name,
            "status": "online",
            "restarts": 1,
            "pid": index + 10,
        }
        for index, name in enumerate(stage_suite.PROCESS_NAMES)
    ]

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_frontend_drift",
    ):
        stage_suite._observe_write_activation_stability(
            duration_seconds=0,
            interval_seconds=30,
            readiness_probe=lambda: {
                name: {"status_code": 200, "status": "ready", "checks": {}}
                for name in stage_suite.PROCESS_NAMES
            },
            pm2_probe=lambda: pm2,
            listener_probe=lambda: [],
            frontend_probe=lambda: {
                "status_code": 503,
                "path": "/smart-water/dashboard",
            },
            monotonic=lambda: 0.0,
            sleep=lambda _seconds: None,
        )


def test_write_activation_stability_anchors_window_after_slow_baseline_probe():
    now = [0.0]
    frontend_calls = [0]
    pm2 = [
        {
            "name": name,
            "status": "online",
            "restarts": 1,
            "pid": index + 10,
        }
        for index, name in enumerate(stage_suite.PROCESS_NAMES)
    ]

    def frontend_probe():
        if frontend_calls[0] == 0:
            now[0] += 120.0
        frontend_calls[0] += 1
        return {"status_code": 200, "path": "/smart-water/dashboard"}

    result = stage_suite._observe_write_activation_stability(
        duration_seconds=900,
        interval_seconds=30,
        readiness_probe=lambda: {
            name: {"status_code": 200, "status": "ready", "checks": {}}
            for name in stage_suite.PROCESS_NAMES
        },
        pm2_probe=lambda: pm2,
        listener_probe=lambda: [],
        frontend_probe=frontend_probe,
        monotonic=lambda: now[0],
        sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
    )

    assert result["observed_duration_seconds"] == 900.0
    assert now[0] == 1020.0


def test_write_activation_stability_rejects_unexpected_pm2_process():
    pm2 = [
        {
            "name": name,
            "status": "online",
            "restarts": 1,
            "pid": index + 10,
        }
        for index, name in enumerate(stage_suite.PROCESS_NAMES)
    ]
    pm2.append(
        {"name": "unexpected-worker", "status": "online", "restarts": 0, "pid": 99}
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_process_inventory_unexpected",
    ):
        stage_suite._observe_write_activation_stability(
            duration_seconds=0,
            interval_seconds=30,
            readiness_probe=lambda: {
                name: {"status_code": 200, "status": "ready", "checks": {}}
                for name in stage_suite.PROCESS_NAMES
            },
            pm2_probe=lambda: pm2,
            listener_probe=lambda: [],
            frontend_probe=lambda: {
                "status_code": 200,
                "path": "/smart-water/dashboard",
            },
            monotonic=lambda: 0.0,
            sleep=lambda _seconds: None,
        )


def test_validate_write_dark_browser_result_requires_rendered_dark_affordance():
    result = stage_suite.validate_write_dark_browser_result(
        {
            "path": "/smart-water/dashboard",
            "submit_absent": True,
            "forbidden_write_count": 0,
            "forbidden_writes": [],
            "mutation_attempt_count": 0,
            "mutation_attempts": [],
            "total_mutations": 0,
            "logout_status": 200,
            "refresh_reuse_status": 401,
        }
    )

    assert result == {
        "path": "/smart-water/dashboard",
        "submit_absent": True,
        "forbidden_write_count": 0,
        "mutation_attempt_count": 0,
        "total_mutations": 0,
        "logout_status": 200,
        "refresh_reuse_status": 401,
    }


def test_validate_write_dark_browser_result_rejects_rendered_submit():
    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_frontend_not_dark",
    ):
        stage_suite.validate_write_dark_browser_result(
            {
                "path": "/smart-water/dashboard",
                "submit_absent": False,
                "forbidden_write_count": 0,
                "forbidden_writes": [],
                "mutation_attempt_count": 0,
                "mutation_attempts": [],
                "total_mutations": 0,
                "logout_status": 200,
                "refresh_reuse_status": 401,
            }
        )


def test_write_activation_stability_rejects_unready_sample():
    pm2 = [
        {
            "name": name,
            "status": "online",
            "restarts": 1,
            "pid": index + 10,
            "memory_bytes": 1024,
            "cpu_percent": 0,
        }
        for index, name in enumerate(stage_suite.PROCESS_NAMES)
    ]
    readiness = {
        name: {"status_code": 200, "status": "ready", "checks": {}}
        for name in stage_suite.PROCESS_NAMES
    }
    readiness["scheduler"] = {
        "status_code": 503,
        "status": "not_ready",
        "checks": {},
    }

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_readiness_drift",
    ):
        stage_suite._observe_write_activation_stability(
            duration_seconds=0,
            interval_seconds=30,
            readiness_probe=lambda: readiness,
            pm2_probe=lambda: pm2,
            listener_probe=lambda: [],
            monotonic=lambda: 0.0,
            sleep=lambda _seconds: None,
        )


def test_write_activation_stability_rejects_duplicate_required_process():
    pm2 = [
        {
            "name": name,
            "status": "online",
            "restarts": 1,
            "pid": index + 10,
            "memory_bytes": 1024,
            "cpu_percent": 0,
        }
        for index, name in enumerate(stage_suite.PROCESS_NAMES)
    ]
    pm2.append({**pm2[0], "pid": 999})

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_process_not_online",
    ):
        stage_suite._observe_write_activation_stability(
            duration_seconds=0,
            interval_seconds=30,
            readiness_probe=lambda: {
                name: {"status_code": 200, "status": "ready", "checks": {}}
                for name in stage_suite.PROCESS_NAMES
            },
            pm2_probe=lambda: pm2,
            listener_probe=lambda: [],
            monotonic=lambda: 0.0,
            sleep=lambda _seconds: None,
        )


def _patch_write_activation_body(monkeypatch, context, events, client):
    before_snapshot = {
        "non_w2_digests": {},
        "w2_submissions": [],
        "w2_values": [],
    }
    snapshots = iter((before_snapshot, before_snapshot))
    rate_call_count = [0]

    def snapshot_rate(_ctx):
        label = "before" if rate_call_count[0] == 0 else "after"
        rate_call_count[0] += 1
        events.append(f"rate:{label}")
        return {}

    monkeypatch.setattr(
        stage_suite,
        "_write_activation_rid_week",
        lambda _date: ("2026-11-15", "2027-R03"),
    )
    monkeypatch.setattr(
        stage_suite,
        "_load_env_file",
        lambda _path: {"PLANNING_DEPTH_WRITES_ENABLED": "false"},
    )
    monkeypatch.setattr(
        stage_suite, "_take_persist_snapshot", lambda _ctx: next(snapshots)
    )
    monkeypatch.setattr(
        stage_suite,
        "_snapshot_planning_depth_rate_keys",
        snapshot_rate,
    )
    monkeypatch.setattr(stage_suite, "_read_json", lambda _path: {"commandable": False})
    monkeypatch.setattr(stage_suite, "_pm2_json", lambda: "[]")
    monkeypatch.setattr(
        stage_suite,
        "collect_dark_runtime_contract",
        lambda _pm2, _release: {"dark": True},
    )
    monkeypatch.setattr(stage_suite, "_listener_snapshot", lambda: [])
    monkeypatch.setattr(
        stage_suite,
        "_restart_bff_with_flag",
        lambda _ctx, *, enabled: events.append(f"bff:{enabled}"),
    )

    def disarm_bff(_ctx, *, behavioral_dark_probe):
        events.append("bff:False")
        behavioral_dark_probe()
        return {
            "attempts": 1,
            "dark": True,
            "stopped": False,
            "failed_gate": None,
        }

    monkeypatch.setattr(
        stage_suite,
        "_disarm_bff_guarded",
        disarm_bff,
        raising=False,
    )
    monkeypatch.setattr(
        stage_suite,
        "_restore_scheduler_guarded",
        lambda: events.append("scheduler:restore")
        or {"attempts": 1, "restored": True, "failed_gate": None},
    )
    monkeypatch.setattr(
        stage_suite,
        "_build_frontend",
        lambda _ctx, **kwargs: events.append(
            "frontend:armed" if kwargs["water_planning_submit"] else "frontend:dark"
        )
        or {"build": "PASS"},
    )

    class FrontendServer:
        def __init__(self, dark):
            self.dark = dark

        def __enter__(self):
            events.append("frontend:dark-enter" if self.dark else "frontend:enter")

        def __exit__(self, *_args):
            events.append("frontend:dark-exit" if self.dark else "frontend:exit")

    monkeypatch.setattr(
        stage_suite,
        "_frontend_server",
        lambda *_args, **kwargs: FrontendServer(
            kwargs.get("server_label") == "write-activation-restored"
        ),
    )
    monkeypatch.setattr(
        stage_suite,
        "_run_write_dark_browser",
        lambda _ctx: events.append("frontend:dark-browser") or {"submit_absent": True},
    )
    monkeypatch.setattr(
        stage_suite,
        "_observe_write_activation_stability",
        lambda **_kwargs: events.append("stability") or {"sample_count": 31},
    )
    monkeypatch.setattr(
        stage_suite,
        "validate_write_activation_diff",
        lambda *_args, **_kwargs: {"diff": "accepted"},
    )

    def validate_rate(*_args, expected_increment=2, expected_operator_key, **_kwargs):
        expected_key = (
            "bff-water-planning:rate:planning_depth.submit:"
            + hashlib.sha256(b"operator-1").hexdigest()
        )
        assert expected_operator_key == expected_key
        events.append("rate-key-bound")
        return {"increment": expected_increment}

    monkeypatch.setattr(
        stage_suite,
        "validate_persist_only_rate_accounting",
        validate_rate,
    )
    monkeypatch.setattr(
        stage_suite,
        "_verify_write_activation_restoration",
        lambda *_args, **_kwargs: {"verified": True},
    )
    monkeypatch.setattr(stage_suite, "_verify_frontend_source", lambda _ctx: {})

    session_count = [0]

    @contextmanager
    def fresh_session(_context, _verifier, *, expected_subject):
        session_count[0] += 1
        session_number = session_count[0]
        evidence = {
            "login": {"status": 200, "claims": "valid"},
            "principal": {"subject": expected_subject},
        }
        events.append(f"reauth:{session_number}")
        try:
            yield client, f"fresh-token-{session_number}", evidence
        finally:
            evidence["logout"] = {"accepted": True}
            evidence["refresh_revoked"] = {"revoked": True}
            events.append(f"revoke:{session_number}")

    monkeypatch.setattr(
        stage_suite,
        "_fresh_write_activation_operator_session",
        fresh_session,
        raising=False,
    )
    return before_snapshot


def test_write_activation_body_arms_backend_before_frontend_and_rolls_back_frontend_first(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    events = []
    client = _ScriptedClient(
        [
            _FakeResponse(
                200,
                {"subject": "operator-1", "effective_roles": ["operator"]},
            ),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
            _FakeResponse(
                200,
                {
                    "submission_id": "d4c3b2a1-f6e5-4b7a-9d8c-1e0f2a3b4c5d",
                    "levels": _expanded_levels(
                        {
                            f"01-{zone:02d}": 260.0 + 10.0 * (zone - 1)
                            for zone in range(1, 7)
                        }
                    ),
                },
            ),
        ]
    )
    _patch_write_activation_body(monkeypatch, context, events, client)
    browser = _write_browser_evidence()

    def run_browser(*_args, healthy_boundary_probe=None, **_kwargs):
        events.append("browser")
        if healthy_boundary_probe is not None:
            healthy_boundary_probe()
        return browser

    monkeypatch.setattr(stage_suite, "_run_write_browser", run_browser)
    monotonic_values = iter((10.0, 20.0, 20.1, 920.1))
    monkeypatch.setattr(stage_suite.time, "monotonic", monotonic_values.__next__)

    steps = stage_suite._run_local_write_activation_authenticated(
        context,
        client,
        "token",
        {"login": "accepted"},
        verifier=object(),
    )

    assert events == [
        "rate:before",
        "bff:True",
        "frontend:armed",
        "frontend:enter",
        "browser",
        "rate:after",
        "stability",
        "frontend:exit",
        "frontend:dark",
        "frontend:dark-enter",
        "frontend:dark-browser",
        "frontend:dark-exit",
        "bff:False",
        "reauth:1",
        "revoke:1",
        "scheduler:restore",
        "reauth:2",
        "revoke:2",
        "rate-key-bound",
    ]
    assert steps["persisted_diff"] == {"diff": "accepted"}
    expected_snapshot = {
        "non_w2_digests": {},
        "w2_submissions": [],
        "w2_values": [],
    }
    assert (
        steps["persist_snapshot_sha256"]
        == hashlib.sha256(
            (
                json.dumps(expected_snapshot, separators=(",", ":"), sort_keys=True)
                + "\n"
            ).encode()
        ).hexdigest()
    )
    assert steps["rate_accounting"] == {"increment": 3}
    assert steps["rate_state_after_browser"] == {
        "configured_window_ms": 300000,
        "minimum_elapsed_ms": 900000,
        "snapshot_completed_monotonic_ms": 20100,
        "snapshot": {},
    }
    assert steps["active_after_rollback"] == {
        "submission_id": "d4c3b2a1-f6e5-4b7a-9d8c-1e0f2a3b4c5d",
        "levels_count": 41,
        "zones_covered": [f"01-{zone:02d}" for zone in range(1, 7)],
    }
    assert client.calls[-1] == (
        "GET",
        (
            f"{stage_suite.W2_V2_BASE}/active?project_key=mun-bon&"
            "calendar_system=rid-irrigation-v1&week_key=2027-R03"
        ),
        None,
    )
    assert steps["aws_actions"] is False
    assert steps["rollback_operator_session"]["logout"] == {"accepted": True}
    assert steps["rollback_operator_session"]["refresh_revoked"] == {"revoked": True}
    assert steps["readback_operator_session"]["refresh_revoked"] == {"revoked": True}
    assert client.bearers == [
        "token",
        "token",
        "fresh-token-1",
        "fresh-token-2",
    ]


def test_write_activation_rollback_reauthenticates_each_disarm_attempt(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    events = []
    client = _ScriptedClient(
        [
            _FakeResponse(
                200,
                {"subject": "operator-1", "effective_roles": ["operator"]},
            ),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
            _FakeResponse(401, {"detail": "access_token_expired"}),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
            _FakeResponse(
                200,
                {
                    "submission_id": "d4c3b2a1-f6e5-4b7a-9d8c-1e0f2a3b4c5d",
                    "levels": _expanded_levels(
                        {
                            f"01-{zone:02d}": 260.0 + 10.0 * (zone - 1)
                            for zone in range(1, 7)
                        }
                    ),
                },
            ),
        ]
    )
    _patch_write_activation_body(monkeypatch, context, events, client)

    def retry_disarm(_context, *, behavioral_dark_probe):
        try:
            behavioral_dark_probe()
        except stage_suite.StageGateError:
            pass
        behavioral_dark_probe()
        return {
            "attempts": 2,
            "dark": True,
            "stopped": False,
            "failed_gate": None,
        }

    monkeypatch.setattr(stage_suite, "_disarm_bff_guarded", retry_disarm)

    def run_browser(*_args, healthy_boundary_probe=None, **_kwargs):
        if healthy_boundary_probe is not None:
            healthy_boundary_probe()
        return _write_browser_evidence()

    monkeypatch.setattr(stage_suite, "_run_write_browser", run_browser)

    steps = stage_suite._run_local_write_activation_authenticated(
        context,
        client,
        "token",
        {"login": "accepted"},
        verifier=object(),
    )

    assert client.bearers == [
        "token",
        "token",
        "fresh-token-1",
        "fresh-token-2",
        "fresh-token-3",
    ]
    assert [
        {
            "probe_outcome": session["probe_outcome"],
            "failed_gate": session.get("failed_gate"),
            "subject": session["principal"]["subject"],
            "logout": session["logout"],
            "refresh_revoked": session["refresh_revoked"],
        }
        for session in steps["rollback_operator_sessions"]
    ] == [
        {
            "probe_outcome": "failed",
            "failed_gate": "w2_write_disabled_result_not_accepted",
            "subject": "operator-1",
            "logout": {"accepted": True},
            "refresh_revoked": {"revoked": True},
        },
        {
            "probe_outcome": "accepted",
            "failed_gate": None,
            "subject": "operator-1",
            "logout": {"accepted": True},
            "refresh_revoked": {"revoked": True},
        },
    ]


@pytest.mark.parametrize("failure_phase", ("login", "principal"))
def test_write_activation_rollback_retains_proved_preyield_session_before_retry(
    tmp_path, monkeypatch, failure_phase
):
    context = _write_ui_context(tmp_path)
    events = []
    client = _ScriptedClient(
        [
            _FakeResponse(
                200,
                {"subject": "operator-1", "effective_roles": ["operator"]},
            ),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
            _FakeResponse(
                200,
                {
                    "submission_id": "d4c3b2a1-f6e5-4b7a-9d8c-1e0f2a3b4c5d",
                    "levels": _expanded_levels(
                        {
                            f"01-{zone:02d}": 260.0 + 10.0 * (zone - 1)
                            for zone in range(1, 7)
                        }
                    ),
                },
            ),
        ]
    )
    _patch_write_activation_body(monkeypatch, context, events, client)
    session_count = [0]
    failed_gate = (
        "operator_login_not_accepted"
        if failure_phase == "login"
        else "write_activation_operator_subject_changed"
    )
    preyield_record = {
        "phase": failure_phase,
        "probe_outcome": "not_started",
        "failed_gate": failed_gate,
        "logout": {"accepted": True},
        "refresh_revoked": {"refresh_reuse_status": 401, "revoked": True},
    }
    if failure_phase == "principal":
        preyield_record.update(
            {
                "login": {"status": 200, "claims": "valid"},
                "principal": {
                    "subject": "different-operator",
                    "effective_roles": ["operator"],
                },
            }
        )

    @contextmanager
    def preyield_failure_then_session(_context, _verifier, *, expected_subject):
        session_count[0] += 1
        if session_count[0] == 1:
            error = stage_suite.StageGateError(failed_gate)
            error.rollback_session_record = dict(preyield_record)
            raise error
        evidence = {
            "login": {"status": 200, "claims": "valid"},
            "principal": {"subject": expected_subject},
        }
        try:
            yield client, f"fresh-token-{session_count[0]}", evidence
        finally:
            evidence["logout"] = {"accepted": True}
            evidence["refresh_revoked"] = {"revoked": True}

    def retry_disarm(_context, *, behavioral_dark_probe):
        with pytest.raises(stage_suite.StageGateError, match=failed_gate):
            behavioral_dark_probe()
        behavioral_dark_probe()
        return {
            "attempts": 2,
            "dark": True,
            "stopped": False,
            "failed_gate": None,
        }

    def run_browser(*_args, healthy_boundary_probe=None, **_kwargs):
        if healthy_boundary_probe is not None:
            healthy_boundary_probe()
        return _write_browser_evidence()

    monkeypatch.setattr(
        stage_suite,
        "_fresh_write_activation_operator_session",
        preyield_failure_then_session,
    )
    monkeypatch.setattr(stage_suite, "_disarm_bff_guarded", retry_disarm)
    monkeypatch.setattr(stage_suite, "_run_write_browser", run_browser)

    steps = stage_suite._run_local_write_activation_authenticated(
        context,
        client,
        "token",
        {"login": "accepted"},
        verifier=object(),
    )

    assert steps["rollback_operator_sessions"][0] == preyield_record
    assert steps["rollback_operator_sessions"][1]["probe_outcome"] == "accepted"
    assert steps["rollback_operator_sessions"][1]["principal"] == {
        "subject": "operator-1"
    }
    assert session_count == [3]


def test_write_activation_failure_retains_every_rollback_session_in_restoration(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    events = []
    client = _ScriptedClient(
        [
            _FakeResponse(
                200,
                {"subject": "operator-1", "effective_roles": ["operator"]},
            ),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
            _FakeResponse(401, {"detail": "access_token_expired"}),
            _FakeResponse(401, {"detail": "access_token_expired"}),
        ]
    )
    _patch_write_activation_body(monkeypatch, context, events, client)

    def failed_disarm(_context, *, behavioral_dark_probe):
        failures = []
        for _attempt in range(2):
            try:
                behavioral_dark_probe()
            except stage_suite.StageGateError as exc:
                failures.append(str(exc))
        assert failures == [
            "w2_write_disabled_result_not_accepted",
            "w2_write_disabled_result_not_accepted",
        ]
        return {
            "attempts": 2,
            "dark": False,
            "stopped": True,
            "failed_gate": failures[0],
        }

    monkeypatch.setattr(stage_suite, "_disarm_bff_guarded", failed_disarm)
    monkeypatch.setattr(
        stage_suite,
        "_run_write_browser",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            stage_suite.StageGateError("injected_browser_failure")
        ),
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="injected_browser_failure_and_write_activation_restore_failed",
    ) as exc_info:
        stage_suite._run_local_write_activation_authenticated(
            context,
            client,
            "token",
            {"login": "accepted"},
            verifier=object(),
        )

    assert [
        {
            "probe_outcome": session["probe_outcome"],
            "failed_gate": session["failed_gate"],
            "subject": session["principal"]["subject"],
            "logout": session["logout"],
            "refresh_revoked": session["refresh_revoked"],
        }
        for session in exc_info.value.restoration["rollback_operator_sessions"]
    ] == [
        {
            "probe_outcome": "failed",
            "failed_gate": "w2_write_disabled_result_not_accepted",
            "subject": "operator-1",
            "logout": {"accepted": True},
            "refresh_revoked": {"revoked": True},
        },
        {
            "probe_outcome": "failed",
            "failed_gate": "w2_write_disabled_result_not_accepted",
            "subject": "operator-1",
            "logout": {"accepted": True},
            "refresh_revoked": {"revoked": True},
        },
    ]


@pytest.mark.parametrize("invalid_evidence", ("missing_logout", "unexpected_field"))
def test_write_activation_rejects_incomplete_or_unsafe_rollback_session_evidence(
    tmp_path, monkeypatch, invalid_evidence
):
    context = _write_ui_context(tmp_path)
    events = []
    client = _ScriptedClient(
        [
            _FakeResponse(
                200,
                {"subject": "operator-1", "effective_roles": ["operator"]},
            ),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
            _FakeResponse(
                200,
                {
                    "submission_id": "d4c3b2a1-f6e5-4b7a-9d8c-1e0f2a3b4c5d",
                    "levels": _expanded_levels(
                        {
                            f"01-{zone:02d}": 260.0 + 10.0 * (zone - 1)
                            for zone in range(1, 7)
                        }
                    ),
                },
            ),
        ]
    )
    _patch_write_activation_body(monkeypatch, context, events, client)
    session_count = [0]

    @contextmanager
    def incomplete_first_session(_context, _verifier, *, expected_subject):
        session_count[0] += 1
        evidence = {
            "login": {"status": 200, "claims": "valid"},
            "principal": {"subject": expected_subject},
        }
        yield client, f"fresh-token-{session_count[0]}", evidence
        if session_count[0] > 1 or invalid_evidence == "unexpected_field":
            evidence["logout"] = {"accepted": True}
        if session_count[0] == 1 and invalid_evidence == "unexpected_field":
            evidence["access_token"] = "must-not-enter-evidence"
        evidence["refresh_revoked"] = {"revoked": True}

    def run_browser(*_args, healthy_boundary_probe=None, **_kwargs):
        if healthy_boundary_probe is not None:
            healthy_boundary_probe()
        return _write_browser_evidence()

    monkeypatch.setattr(
        stage_suite,
        "_fresh_write_activation_operator_session",
        incomplete_first_session,
    )
    monkeypatch.setattr(stage_suite, "_run_write_browser", run_browser)

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_restoration_failed",
    ) as exc_info:
        stage_suite._run_local_write_activation_authenticated(
            context,
            client,
            "token",
            {"login": "accepted"},
            verifier=object(),
        )

    assert (
        exc_info.value.restoration["failed_gate"]
        == "write_activation_rollback_session_evidence_incomplete"
    )
    assert exc_info.value.restoration["rollback_operator_sessions"] == []


def test_write_activation_rejects_preyield_principal_record_without_principal(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    events = []
    client = _ScriptedClient(
        [
            _FakeResponse(
                200,
                {"subject": "operator-1", "effective_roles": ["operator"]},
            ),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
        ]
    )
    _patch_write_activation_body(monkeypatch, context, events, client)

    @contextmanager
    def incomplete_principal_session(*_args, **_kwargs):
        error = stage_suite.StageGateError("w1_principal_result_not_accepted")
        error.rollback_session_record = {
            "phase": "principal",
            "probe_outcome": "not_started",
            "failed_gate": "w1_principal_result_not_accepted",
            "login": {"status": 200, "claims": "valid"},
            "logout": {"accepted": True},
            "refresh_revoked": {"refresh_reuse_status": 401, "revoked": True},
        }
        raise error
        yield

    def run_browser(*_args, healthy_boundary_probe=None, **_kwargs):
        if healthy_boundary_probe is not None:
            healthy_boundary_probe()
        return _write_browser_evidence()

    monkeypatch.setattr(
        stage_suite,
        "_fresh_write_activation_operator_session",
        incomplete_principal_session,
    )
    monkeypatch.setattr(stage_suite, "_run_write_browser", run_browser)

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_restoration_failed",
    ) as exc_info:
        stage_suite._run_local_write_activation_authenticated(
            context,
            client,
            "token",
            {"login": "accepted"},
            verifier=object(),
        )

    assert (
        exc_info.value.restoration["failed_gate"]
        == "write_activation_rollback_session_evidence_incomplete"
    )
    assert exc_info.value.restoration["rollback_operator_sessions"] == []


def test_write_activation_restoration_report_survives_fresh_logout_failure(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    events = []
    client = _ScriptedClient(
        [
            _FakeResponse(
                200,
                {"subject": "operator-1", "effective_roles": ["operator"]},
            ),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
        ]
    )
    _patch_write_activation_body(monkeypatch, context, events, client)

    def build_frontend(_context, **kwargs):
        if kwargs["water_planning_submit"]:
            return {"build": "PASS"}
        raise stage_suite.StageGateError("frontend_restore_failed")

    @contextmanager
    def logout_failing_session(_context, _verifier, *, expected_subject):
        evidence = {"principal": {"subject": expected_subject}}
        yield client, "fresh-token", evidence
        raise stage_suite.StageGateError(
            "write_activation_fresh_operator_logout_failed"
        )

    def contain_logout_failure(_context, *, behavioral_dark_probe):
        try:
            behavioral_dark_probe()
        except stage_suite.StageGateError as exc:
            return {
                "attempts": 1,
                "dark": False,
                "stopped": True,
                "failed_gate": str(exc),
            }
        return {
            "attempts": 1,
            "dark": True,
            "stopped": False,
            "failed_gate": None,
        }

    def run_browser(*_args, healthy_boundary_probe=None, **_kwargs):
        if healthy_boundary_probe is not None:
            healthy_boundary_probe()
        return _write_browser_evidence()

    monkeypatch.setattr(stage_suite, "_build_frontend", build_frontend)
    monkeypatch.setattr(
        stage_suite,
        "_fresh_write_activation_operator_session",
        logout_failing_session,
    )
    monkeypatch.setattr(stage_suite, "_disarm_bff_guarded", contain_logout_failure)
    monkeypatch.setattr(stage_suite, "_run_write_browser", run_browser)

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_restoration_failed",
    ) as exc_info:
        stage_suite._run_local_write_activation_authenticated(
            context,
            client,
            "token",
            {"login": "accepted"},
            verifier=object(),
        )

    assert exc_info.value.restoration["failed_gate"] == "frontend_restore_failed"
    assert exc_info.value.restoration["bff_disarm"]["stopped"] is True
    assert exc_info.value.restoration["scheduler_restored"] is True


def test_write_activation_body_restores_dark_after_browser_failure(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    events = []
    client = _ScriptedClient(
        [
            _FakeResponse(
                200,
                {"subject": "operator-1", "effective_roles": ["operator"]},
            ),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
        ]
    )
    _patch_write_activation_body(monkeypatch, context, events, client)

    def fail_browser(*_args, **_kwargs):
        events.append("browser")
        raise stage_suite.StageGateError("injected_browser_failure")

    monkeypatch.setattr(stage_suite, "_run_write_browser", fail_browser)

    with pytest.raises(
        stage_suite.StageGateError,
        match="injected_browser_failure",
    ) as exc_info:
        stage_suite._run_local_write_activation_authenticated(
            context,
            client,
            "token",
            {"login": "accepted"},
            verifier=object(),
        )

    assert events == [
        "rate:before",
        "bff:True",
        "frontend:armed",
        "frontend:enter",
        "browser",
        "frontend:exit",
        "frontend:dark",
        "frontend:dark-enter",
        "frontend:dark-browser",
        "frontend:dark-exit",
        "bff:False",
        "reauth:1",
        "revoke:1",
        "scheduler:restore",
    ]
    assert exc_info.value.restoration == {
        "frontend_dark_build": True,
        "frontend_dark_rendered": True,
        "frontend_dark_evidence": {"submit_absent": True},
        "bff_disarm": {
            "attempts": 1,
            "dark": True,
            "stopped": False,
            "failed_gate": None,
        },
        "bff_dark": True,
        "scheduler_restored": True,
        "restored": True,
        "failed_gate": None,
        "rollback_operator_sessions": [
            {
                "login": {"status": 200, "claims": "valid"},
                "principal": {"subject": "operator-1"},
                "logout": {"accepted": True},
                "refresh_revoked": {"revoked": True},
                "probe_outcome": "accepted",
            }
        ],
    }


def _patch_fresh_write_activation_session(monkeypatch, *, subject="operator-1"):
    client = _ScriptedClient(
        [
            _FakeResponse(
                200,
                {"subject": subject, "effective_roles": ["operator"]},
            )
        ]
    )
    cleanup = []
    monkeypatch.setattr(stage_suite, "LocalHttpClient", lambda: client)
    monkeypatch.setattr(
        stage_suite,
        "_login_operator",
        lambda *_args: (
            "fresh-access-token",
            "fresh-refresh-token",
            {"status": 200, "claims": "valid"},
        ),
    )
    monkeypatch.setattr(
        stage_suite,
        "_operator_logout",
        lambda _client, refresh, *, strict, error_code: cleanup.append(
            (refresh, strict, error_code)
        ),
    )
    monkeypatch.setattr(
        stage_suite,
        "_assert_operator_refresh_reuse_rejected",
        lambda _client, refresh: cleanup.append(("reuse", refresh))
        or {"refresh_reuse_status": 401, "revoked": True},
    )
    return client, cleanup


def test_fresh_write_activation_operator_session_uses_and_revokes_new_session(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    client, cleanup = _patch_fresh_write_activation_session(monkeypatch)

    with stage_suite._fresh_write_activation_operator_session(
        context,
        object(),
        expected_subject="operator-1",
    ) as (fresh_client, token, evidence):
        assert fresh_client is client
        assert token == "fresh-access-token"

    assert evidence == {
        "login": {"status": 200, "claims": "valid"},
        "principal": {
            "subject": "operator-1",
            "effective_roles": ["operator"],
        },
        "logout": {"accepted": True},
        "refresh_revoked": {"refresh_reuse_status": 401, "revoked": True},
    }
    assert cleanup == [
        (
            "fresh-refresh-token",
            True,
            "write_activation_fresh_operator_logout_failed",
        ),
        ("reuse", "fresh-refresh-token"),
    ]


def test_fresh_write_activation_operator_session_preserves_operation_failure(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    _client, cleanup = _patch_fresh_write_activation_session(monkeypatch)

    evidence = None
    with pytest.raises(stage_suite.StageGateError, match="injected_fresh_operation"):
        with stage_suite._fresh_write_activation_operator_session(
            context,
            object(),
            expected_subject="operator-1",
        ) as (_fresh_client, _token, evidence):
            raise stage_suite.StageGateError("injected_fresh_operation")

    assert evidence["logout"] == {"accepted": True}
    assert evidence["refresh_revoked"] == {
        "refresh_reuse_status": 401,
        "revoked": True,
    }
    assert cleanup == [
        (
            "fresh-refresh-token",
            False,
            "write_activation_fresh_operator_logout_failed",
        ),
        ("reuse", "fresh-refresh-token"),
    ]


def test_fresh_write_activation_operator_session_rejects_subject_drift_and_cleans_up(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    _client, cleanup = _patch_fresh_write_activation_session(
        monkeypatch,
        subject="different-operator",
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_operator_subject_changed",
    ):
        with stage_suite._fresh_write_activation_operator_session(
            context,
            object(),
            expected_subject="operator-1",
        ):
            pytest.fail("session yielded after subject drift")

    assert cleanup == [
        (
            "fresh-refresh-token",
            False,
            "write_activation_fresh_operator_logout_failed",
        ),
        ("reuse", "fresh-refresh-token"),
    ]


@pytest.mark.parametrize("failed_cleanup_leg", ("logout", "reuse"))
def test_fresh_write_activation_operator_session_rejects_unproved_cleanup(
    tmp_path, monkeypatch, failed_cleanup_leg
):
    context = _write_ui_context(tmp_path)
    _client, _cleanup = _patch_fresh_write_activation_session(monkeypatch)
    calls = []
    primary = stage_suite.StageGateError("injected_fresh_operation")

    def logout(_client, refresh, *, strict, error_code):
        calls.append(("logout", refresh, strict, error_code))
        if failed_cleanup_leg == "logout":
            raise stage_suite.StageGateError("logout_not_accepted")

    def prove_reuse(_client, refresh):
        calls.append(("reuse", refresh))
        if failed_cleanup_leg == "reuse":
            raise stage_suite.StageGateError("refresh_reuse_not_rejected")
        return {"refresh_reuse_status": 401, "revoked": True}

    monkeypatch.setattr(stage_suite, "_operator_logout", logout)
    monkeypatch.setattr(
        stage_suite,
        "_assert_operator_refresh_reuse_rejected",
        prove_reuse,
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_fresh_operator_cleanup_unproved",
    ) as exc_info:
        with stage_suite._fresh_write_activation_operator_session(
            context,
            object(),
            expected_subject="operator-1",
        ):
            raise primary

    assert exc_info.value.__cause__ is primary
    assert [call[0] for call in calls] == ["logout", "reuse"]


def test_fresh_write_activation_operator_session_cleans_accepted_login_failure(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    cleanup = []

    class AcceptedLoginClient:
        def refresh_cookie(self):
            return "accepted-refresh-token"

    monkeypatch.setattr(stage_suite, "LocalHttpClient", AcceptedLoginClient)
    monkeypatch.setattr(
        stage_suite,
        "_login_operator",
        lambda *_args: (_ for _ in ()).throw(
            stage_suite.StageGateError("operator_login_not_accepted")
        ),
    )
    monkeypatch.setattr(
        stage_suite,
        "_operator_logout",
        lambda _client, refresh, *, strict, error_code: cleanup.append(
            (refresh, strict, error_code)
        ),
    )
    monkeypatch.setattr(
        stage_suite,
        "_assert_operator_refresh_reuse_rejected",
        lambda _client, refresh: cleanup.append(("reuse", refresh))
        or {"refresh_reuse_status": 401, "revoked": True},
    )

    with pytest.raises(stage_suite.StageGateError, match="operator_login_not_accepted"):
        with stage_suite._fresh_write_activation_operator_session(
            context,
            object(),
            expected_subject="operator-1",
        ):
            pytest.fail("session yielded after invalid login")

    assert cleanup == [
        (
            "accepted-refresh-token",
            False,
            "write_activation_fresh_operator_logout_failed",
        ),
        ("reuse", "accepted-refresh-token"),
    ]


@pytest.mark.parametrize("failure_phase", ("login", "principal"))
def test_fresh_write_activation_operator_session_attaches_proved_preyield_record(
    tmp_path, monkeypatch, failure_phase
):
    context = _write_ui_context(tmp_path)

    class AcceptedSessionClient:
        def request(self, *_args, **_kwargs):
            return _FakeResponse(
                200,
                {"subject": "different-operator", "effective_roles": ["operator"]},
            )

        def refresh_cookie(self):
            return "accepted-refresh-token"

    primary = stage_suite.StageGateError("operator_login_not_accepted")
    monkeypatch.setattr(stage_suite, "LocalHttpClient", AcceptedSessionClient)
    if failure_phase == "login":
        monkeypatch.setattr(
            stage_suite,
            "_login_operator",
            lambda *_args: (_ for _ in ()).throw(primary),
        )
    else:
        monkeypatch.setattr(
            stage_suite,
            "_login_operator",
            lambda *_args: (
                "fresh-access-token",
                "accepted-refresh-token",
                {"status": 200, "claims": "valid"},
            ),
        )
    monkeypatch.setattr(stage_suite, "_operator_logout", lambda *_a, **_k: True)
    monkeypatch.setattr(
        stage_suite,
        "_assert_operator_refresh_reuse_rejected",
        lambda *_args: {"refresh_reuse_status": 401, "revoked": True},
    )

    with pytest.raises(stage_suite.StageGateError) as exc_info:
        with stage_suite._fresh_write_activation_operator_session(
            context,
            object(),
            expected_subject="operator-1",
        ):
            pytest.fail("pre-yield failure reached the operation body")

    expected = {
        "phase": failure_phase,
        "probe_outcome": "not_started",
        "failed_gate": (
            "operator_login_not_accepted"
            if failure_phase == "login"
            else "write_activation_operator_subject_changed"
        ),
        "logout": {"accepted": True},
        "refresh_revoked": {"refresh_reuse_status": 401, "revoked": True},
    }
    if failure_phase == "principal":
        expected.update(
            {
                "login": {"status": 200, "claims": "valid"},
                "principal": {
                    "subject": "different-operator",
                    "effective_roles": ["operator"],
                },
            }
        )
    assert exc_info.value.rollback_session_record == expected


@pytest.mark.parametrize("interrupt_type", (KeyboardInterrupt, SystemExit))
@pytest.mark.parametrize("interrupt_phase", ("operation", "logout", "reuse"))
def test_write_activation_restoration_preserves_interrupt_after_failed_session_cleanup(
    tmp_path, monkeypatch, interrupt_type, interrupt_phase
):
    context = _write_ui_context(tmp_path)
    _client, _cleanup = _patch_fresh_write_activation_session(monkeypatch)
    events = []
    pending_interrupt = interrupt_type(f"injected_{interrupt_phase}_interrupt")

    def logout(_client, _refresh, *, strict, error_code):
        events.append("logout")
        if interrupt_phase == "logout":
            raise pending_interrupt
        return interrupt_phase != "operation"

    def prove_reuse(_client, _refresh):
        events.append("reuse")
        if interrupt_phase == "reuse":
            raise pending_interrupt
        return {"refresh_reuse_status": 401, "revoked": True}

    @contextmanager
    def dark_server(*_args, **_kwargs):
        yield

    def behavioral_probe():
        with stage_suite._fresh_write_activation_operator_session(
            context,
            object(),
            expected_subject="operator-1",
        ):
            if interrupt_phase == "operation":
                raise pending_interrupt

    monkeypatch.setattr(stage_suite, "_operator_logout", logout)
    monkeypatch.setattr(
        stage_suite,
        "_assert_operator_refresh_reuse_rejected",
        prove_reuse,
    )
    monkeypatch.setattr(stage_suite, "_build_frontend", lambda *_a, **_k: {})
    monkeypatch.setattr(stage_suite, "_frontend_server", dark_server)
    monkeypatch.setattr(
        stage_suite,
        "_run_write_dark_browser",
        lambda _context: {"submit_absent": True},
    )
    monkeypatch.setattr(
        stage_suite,
        "_restart_bff_with_flag",
        lambda *_a, **_k: events.append("bff-restart"),
    )
    monkeypatch.setattr(stage_suite, "_verify_bff_write_flag_dark", lambda: None)
    monkeypatch.setattr(
        stage_suite,
        "_run_checked",
        lambda *_a, **_k: events.append("bff-stop") or "",
    )
    monkeypatch.setattr(
        stage_suite,
        "_verify_bff_fail_safe_stopped",
        lambda: events.append("bff-stop-verified"),
    )
    monkeypatch.setattr(
        stage_suite,
        "_restore_scheduler_guarded",
        lambda: events.append("scheduler-restored")
        or {"attempts": 1, "restored": True, "failed_gate": None},
    )

    with pytest.raises(interrupt_type) as exc_info:
        stage_suite._restore_write_activation_dark(
            context,
            bff_dark_probe=behavioral_probe,
        )

    assert exc_info.value is pending_interrupt
    assert exc_info.value.session_cleanup == {
        "logout_attempted": True,
        "refresh_reuse_attempted": True,
        "proved": False,
    }
    assert exc_info.value.restoration["bff_disarm"]["stopped"] is True
    assert exc_info.value.restoration["scheduler_restored"] is True
    assert events.count("logout") == 1
    assert events.count("reuse") == 1
    assert events[-3:] == ["bff-stop", "bff-stop-verified", "scheduler-restored"]


@pytest.mark.parametrize("interrupt_type", (KeyboardInterrupt, SystemExit))
@pytest.mark.parametrize("cleanup_proved", (True, False))
def test_authenticated_write_activation_rollback_never_masks_operation_interrupt(
    tmp_path, monkeypatch, interrupt_type, cleanup_proved
):
    context = _write_ui_context(tmp_path)
    events = []
    pending_interrupt = interrupt_type("injected_behavioral_interrupt")
    initial_client = _ScriptedClient(
        [
            _FakeResponse(
                200,
                {"subject": "operator-1", "effective_roles": ["operator"]},
            ),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
        ]
    )
    real_disarm = stage_suite._disarm_bff_guarded
    real_fresh_session = stage_suite._fresh_write_activation_operator_session
    _patch_write_activation_body(
        monkeypatch,
        context,
        events,
        initial_client,
    )
    monkeypatch.setattr(stage_suite, "_disarm_bff_guarded", real_disarm)
    monkeypatch.setattr(
        stage_suite,
        "_fresh_write_activation_operator_session",
        real_fresh_session,
    )

    class InterruptingFreshClient:
        def __init__(self):
            self.request_count = 0

        def request(self, *_args, **_kwargs):
            self.request_count += 1
            if self.request_count == 1:
                return _FakeResponse(
                    200,
                    {"subject": "operator-1", "effective_roles": ["operator"]},
                )
            raise pending_interrupt

        def refresh_cookie(self):
            return "fresh-refresh-token"

    fresh_login_count = [0]

    def login(*_args):
        fresh_login_count[0] += 1
        return (
            f"fresh-token-{fresh_login_count[0]}",
            "fresh-refresh-token",
            {"status": 200, "claims": "valid"},
        )

    def run_browser(*_args, healthy_boundary_probe=None, **_kwargs):
        if healthy_boundary_probe is not None:
            healthy_boundary_probe()
        return _write_browser_evidence()

    monkeypatch.setattr(stage_suite, "LocalHttpClient", InterruptingFreshClient)
    monkeypatch.setattr(stage_suite, "_login_operator", login)
    monkeypatch.setattr(
        stage_suite,
        "_operator_logout",
        lambda *_args, **_kwargs: events.append("logout") or cleanup_proved,
    )
    monkeypatch.setattr(
        stage_suite,
        "_assert_operator_refresh_reuse_rejected",
        lambda *_args: events.append("reuse")
        or {"refresh_reuse_status": 401, "revoked": True},
    )
    monkeypatch.setattr(stage_suite, "_run_write_browser", run_browser)
    monkeypatch.setattr(stage_suite, "_verify_bff_write_flag_dark", lambda: None)
    monkeypatch.setattr(stage_suite.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        stage_suite,
        "_run_checked",
        lambda *_args, **_kwargs: events.append("bff-stop") or "",
    )
    monkeypatch.setattr(
        stage_suite,
        "_verify_bff_fail_safe_stopped",
        lambda: events.append("bff-stop-verified"),
    )

    with pytest.raises(interrupt_type) as exc_info:
        stage_suite._run_local_write_activation_authenticated(
            context,
            initial_client,
            "token",
            {"login": "accepted"},
            verifier=object(),
        )

    assert exc_info.value is pending_interrupt
    assert fresh_login_count == [1]
    assert exc_info.value.restoration["bff_disarm"]["stopped"] is True
    assert exc_info.value.restoration["scheduler_restored"] is True
    if cleanup_proved:
        assert exc_info.value.restoration["rollback_operator_sessions"] == [
            {
                "login": {"status": 200, "claims": "valid"},
                "principal": {
                    "subject": "operator-1",
                    "effective_roles": ["operator"],
                },
                "logout": {"accepted": True},
                "refresh_revoked": {
                    "refresh_reuse_status": 401,
                    "revoked": True,
                },
                "probe_outcome": "interrupted",
                "failed_gate": f"unexpected_{interrupt_type.__name__}",
            }
        ]
    else:
        assert exc_info.value.session_cleanup["proved"] is False
        assert exc_info.value.restoration["rollback_operator_sessions"] == []
    assert events.count("logout") == 1
    assert events.count("reuse") == 1
    assert events[-3:] == ["bff-stop", "bff-stop-verified", "scheduler:restore"]


def test_write_activation_reauth_failure_still_runs_fail_safe_restoration(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    events = []
    client = _ScriptedClient(
        [
            _FakeResponse(
                200,
                {"subject": "operator-1", "effective_roles": ["operator"]},
            ),
            _FakeResponse(503, {"detail": "planning_depth_writes_disabled"}),
        ]
    )
    _patch_write_activation_body(monkeypatch, context, events, client)

    def run_browser(*_args, healthy_boundary_probe=None, **_kwargs):
        if healthy_boundary_probe is not None:
            healthy_boundary_probe()
        return _write_browser_evidence()

    @contextmanager
    def fail_fresh_session(*_args, **_kwargs):
        raise stage_suite.StageGateError("write_activation_fresh_login_failed")
        yield

    monkeypatch.setattr(stage_suite, "_run_write_browser", run_browser)
    monkeypatch.setattr(
        stage_suite,
        "_fresh_write_activation_operator_session",
        fail_fresh_session,
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_restoration_failed",
    ) as exc_info:
        stage_suite._run_local_write_activation_authenticated(
            context,
            client,
            "token",
            {"login": "accepted"},
            verifier=object(),
        )

    assert "frontend:dark" in events
    assert "bff:False" in events
    assert "scheduler:restore" in events
    assert exc_info.value.restoration["bff_dark"] is False
    assert (
        exc_info.value.restoration["failed_gate"]
        == "write_activation_fresh_login_failed"
    )


def _patch_frontend_server_process(monkeypatch, process=None):
    if process is None:
        process = SimpleNamespace(
            pid=123,
            poll=lambda: None,
            wait=lambda **_kwargs: 0,
        )
    monkeypatch.setattr(
        stage_suite,
        "frontend_process_environment",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        stage_suite.subprocess, "Popen", lambda *_args, **_kwargs: process
    )
    monkeypatch.setattr(stage_suite, "_wait_frontend", lambda _process: None)
    monkeypatch.setattr(stage_suite.os, "killpg", lambda *_args: None)
    return process


def _frontend_process_that_never_stops():
    def wait(*, timeout):
        raise stage_suite.subprocess.TimeoutExpired(cmd="next", timeout=timeout)

    return SimpleNamespace(
        pid=123,
        poll=lambda: None,
        wait=wait,
    )


def test_frontend_server_removes_transient_log_after_body_failure(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    _patch_frontend_server_process(monkeypatch)
    transient_log = context.evidence_root / ".frontend-write-activation-armed.log"

    with pytest.raises(stage_suite.StageGateError, match="browser_failed"):
        with stage_suite._frontend_server(
            context,
            control_plan_reads=False,
            water_planning_v2=True,
            water_planning_submit=True,
            server_label="write-activation-armed",
        ):
            assert transient_log.is_file()
            raise stage_suite.StageGateError("browser_failed")

    assert not transient_log.exists()


@pytest.mark.parametrize(
    "primary",
    (
        stage_suite.StageGateError("browser_failed"),
        KeyboardInterrupt(),
        SystemExit(7),
    ),
    ids=("stage-gate", "keyboard-interrupt", "system-exit"),
)
def test_frontend_server_preserves_primary_when_log_cleanup_fails(
    tmp_path, monkeypatch, primary
):
    context = _write_ui_context(tmp_path)
    _patch_frontend_server_process(monkeypatch)

    def fail_unlink(_path, *, missing_ok):
        raise OSError("simulated unlink failure")

    monkeypatch.setattr(stage_suite.Path, "unlink", fail_unlink)

    with pytest.raises(type(primary)) as exc_info:
        with stage_suite._frontend_server(
            context,
            control_plan_reads=False,
            water_planning_v2=True,
            water_planning_submit=True,
            server_label="write-activation-armed",
        ):
            raise primary

    assert exc_info.value is primary
    assert primary.teardown_error == "frontend_log_cleanup_failed"


def test_frontend_server_reports_log_cleanup_failure_without_a_primary(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    _patch_frontend_server_process(monkeypatch)

    def fail_unlink(_path, *, missing_ok):
        raise OSError("simulated unlink failure")

    monkeypatch.setattr(stage_suite.Path, "unlink", fail_unlink)

    with pytest.raises(
        stage_suite.StageGateError,
        match="^frontend_log_cleanup_failed$",
    ):
        with stage_suite._frontend_server(
            context,
            control_plan_reads=False,
            water_planning_v2=True,
            water_planning_submit=True,
            server_label="write-activation-armed",
        ):
            pass


def test_frontend_server_reports_process_cleanup_failure_without_a_primary(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    process = _frontend_process_that_never_stops()
    _patch_frontend_server_process(monkeypatch, process)
    transient_log = context.evidence_root / ".frontend-write-activation-armed.log"

    with pytest.raises(
        stage_suite.StageGateError,
        match="^frontend_process_cleanup_failed$",
    ):
        with stage_suite._frontend_server(
            context,
            control_plan_reads=False,
            water_planning_v2=True,
            water_planning_submit=True,
            server_label="write-activation-armed",
        ):
            pass

    assert not transient_log.exists()


def test_frontend_server_preserves_primary_when_process_cleanup_fails(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    process = _frontend_process_that_never_stops()
    _patch_frontend_server_process(monkeypatch, process)
    primary = stage_suite.StageGateError("browser_failed")

    with pytest.raises(stage_suite.StageGateError) as exc_info:
        with stage_suite._frontend_server(
            context,
            control_plan_reads=False,
            water_planning_v2=True,
            water_planning_submit=True,
            server_label="write-activation-armed",
        ):
            raise primary

    assert exc_info.value is primary
    assert primary.teardown_error == "frontend_process_cleanup_failed"


def test_frontend_server_prefers_process_cleanup_when_both_cleanups_fail(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    process = _frontend_process_that_never_stops()
    _patch_frontend_server_process(monkeypatch, process)
    primary = stage_suite.StageGateError("browser_failed")

    def fail_unlink(_path, *, missing_ok):
        raise OSError("simulated unlink failure")

    monkeypatch.setattr(stage_suite.Path, "unlink", fail_unlink)

    with pytest.raises(stage_suite.StageGateError) as exc_info:
        with stage_suite._frontend_server(
            context,
            control_plan_reads=False,
            water_planning_v2=True,
            water_planning_submit=True,
            server_label="write-activation-armed",
        ):
            raise primary

    assert exc_info.value is primary
    assert primary.teardown_error == "frontend_process_cleanup_failed"


def test_frontend_server_accepts_final_poll_that_proves_a_late_exit(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    poll_results = iter((None, 0))
    process = SimpleNamespace(
        pid=123,
        poll=lambda: next(poll_results),
        wait=lambda **_kwargs: pytest.fail("wait must follow successful signal"),
    )
    _patch_frontend_server_process(monkeypatch, process)

    def process_already_exited(*_args):
        raise OSError("simulated late exit")

    monkeypatch.setattr(stage_suite.os, "killpg", process_already_exited)

    with stage_suite._frontend_server(
        context,
        control_plan_reads=False,
        water_planning_v2=True,
        water_planning_submit=True,
        server_label="write-activation-armed",
    ):
        pass


def test_frontend_server_reports_poll_failure_after_attempting_log_cleanup(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)

    def fail_poll():
        raise OSError("simulated poll failure")

    def fail_wait(*, timeout):
        raise stage_suite.subprocess.TimeoutExpired(cmd="next", timeout=timeout)

    process = SimpleNamespace(
        pid=123,
        poll=fail_poll,
        wait=fail_wait,
    )
    _patch_frontend_server_process(monkeypatch, process)
    transient_log = context.evidence_root / ".frontend-write-activation-armed.log"

    with pytest.raises(
        stage_suite.StageGateError,
        match="^frontend_process_cleanup_failed$",
    ):
        with stage_suite._frontend_server(
            context,
            control_plan_reads=False,
            water_planning_v2=True,
            water_planning_submit=True,
            server_label="write-activation-armed",
        ):
            pass

    assert not transient_log.exists()


def test_frontend_server_keeps_body_oserror_sanitized_as_process_failure(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    _patch_frontend_server_process(monkeypatch)

    with pytest.raises(
        stage_suite.StageGateError,
        match="^frontend_process_failed$",
    ):
        with stage_suite._frontend_server(
            context,
            control_plan_reads=False,
            water_planning_v2=True,
            water_planning_submit=True,
            server_label="write-activation-armed",
        ):
            raise OSError("unsanitized body detail")


def test_restore_write_activation_dark_attempts_bff_after_frontend_failure(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    calls = []

    def fail_frontend(*_args, **_kwargs):
        calls.append("frontend")
        raise stage_suite.StageGateError("frontend_restore_failed")

    monkeypatch.setattr(stage_suite, "_build_frontend", fail_frontend)
    monkeypatch.setattr(
        stage_suite,
        "_frontend_server",
        lambda *_args, **_kwargs: pytest.fail("dark server after failed build"),
    )
    monkeypatch.setattr(
        stage_suite,
        "_disarm_bff_guarded",
        lambda _context, *, behavioral_dark_probe: calls.append("bff:False")
        or behavioral_dark_probe()
        or {
            "attempts": 1,
            "dark": True,
            "stopped": False,
            "failed_gate": None,
        },
        raising=False,
    )
    monkeypatch.setattr(
        stage_suite,
        "_restore_scheduler_guarded",
        lambda: calls.append("scheduler")
        or {"attempts": 1, "restored": True, "failed_gate": None},
    )

    assert stage_suite._restore_write_activation_dark(
        context,
        bff_dark_probe=lambda: None,
    ) == {
        "frontend_dark_build": False,
        "frontend_dark_rendered": False,
        "bff_disarm": {
            "attempts": 1,
            "dark": True,
            "stopped": False,
            "failed_gate": None,
        },
        "bff_dark": True,
        "scheduler_restored": True,
        "restored": False,
        "failed_gate": "frontend_restore_failed",
    }
    assert calls == ["frontend", "bff:False", "scheduler"]


def test_verify_bff_write_flag_dark_uses_actual_process_environment(monkeypatch):
    calls = []
    monkeypatch.setattr(stage_suite, "_pm2_json", lambda: "pm2-json")
    monkeypatch.setattr(
        stage_suite,
        "_actual_gate_environment",
        lambda pm2_json: calls.append(pm2_json)
        or json.dumps(
            [
                {
                    "name": "bff-water-planning",
                    "pm2_env": {"env": {"PLANNING_DEPTH_WRITES_ENABLED": "false"}},
                }
            ]
        ),
    )

    assert stage_suite._verify_bff_write_flag_dark() is None
    assert calls == ["pm2-json"]


@pytest.mark.parametrize("runtime_value", ("true", None))
def test_verify_bff_write_flag_dark_rejects_armed_or_unverifiable_runtime(
    monkeypatch, runtime_value
):
    environment = {}
    if runtime_value is not None:
        environment["PLANNING_DEPTH_WRITES_ENABLED"] = runtime_value
    monkeypatch.setattr(stage_suite, "_pm2_json", lambda: "pm2-json")
    monkeypatch.setattr(
        stage_suite,
        "_actual_gate_environment",
        lambda _pm2_json: json.dumps(
            [
                {
                    "name": "bff-water-planning",
                    "pm2_env": {"env": environment},
                }
            ]
        ),
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_bff_still_armed",
    ):
        stage_suite._verify_bff_write_flag_dark()


def test_verify_bff_write_flag_dark_rejects_missing_running_bff(monkeypatch):
    monkeypatch.setattr(stage_suite, "_pm2_json", lambda: "pm2-json")
    monkeypatch.setattr(
        stage_suite,
        "_actual_gate_environment",
        lambda _pm2_json: "[]",
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_bff_still_armed",
    ):
        stage_suite._verify_bff_write_flag_dark()


def test_disarm_bff_guarded_marks_dark_only_after_runtime_verification(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    calls = []
    monkeypatch.setattr(
        stage_suite,
        "_restart_bff_with_flag",
        lambda _context, *, enabled: calls.append(f"restart:{enabled}"),
    )
    monkeypatch.setattr(
        stage_suite,
        "_verify_bff_write_flag_dark",
        lambda: calls.append("verify"),
        raising=False,
    )

    assert stage_suite._disarm_bff_guarded(
        context,
        behavioral_dark_probe=lambda: calls.append("behavior"),
    ) == {
        "attempts": 1,
        "dark": True,
        "stopped": False,
        "failed_gate": None,
    }
    assert calls == ["restart:False", "verify", "behavior"]


def test_disarm_bff_guarded_stops_process_when_runtime_flag_stays_armed(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    calls = []
    monkeypatch.setattr(
        stage_suite,
        "_restart_bff_with_flag",
        lambda _context, *, enabled: calls.append(f"restart:{enabled}"),
    )
    monkeypatch.setattr(
        stage_suite,
        "_verify_bff_write_flag_dark",
        lambda: (_ for _ in ()).throw(
            stage_suite.StageGateError("write_activation_bff_still_armed")
        ),
        raising=False,
    )
    monkeypatch.setattr(stage_suite.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        stage_suite,
        "_run_checked",
        lambda label, command, **_kwargs: calls.append((label, command)) or "",
    )
    monkeypatch.setattr(
        stage_suite,
        "_verify_bff_fail_safe_stopped",
        lambda: calls.append("verify-stopped"),
        raising=False,
    )

    result = stage_suite._disarm_bff_guarded(
        context,
        behavioral_dark_probe=lambda: pytest.fail(
            "behavioral probe after failed process verification"
        ),
        attempts=2,
    )

    assert result == {
        "attempts": 2,
        "dark": False,
        "stopped": True,
        "failed_gate": "write_activation_bff_still_armed",
    }
    assert calls[:2] == ["restart:False", "restart:False"]
    assert calls[2] == (
        "write_activation_bff_fail_safe_stop",
        stage_suite._pm2_command("stop", "bff-water-planning"),
    )
    assert calls[3] == "verify-stopped"


def test_disarm_bff_guarded_stops_after_behavioral_darkness_failure(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    calls = []
    monkeypatch.setattr(
        stage_suite,
        "_restart_bff_with_flag",
        lambda _context, *, enabled: calls.append(f"restart:{enabled}"),
    )
    monkeypatch.setattr(
        stage_suite,
        "_verify_bff_write_flag_dark",
        lambda: calls.append("verify-env"),
    )

    def reject_behavioral_darkness():
        calls.append("verify-behavior")
        raise stage_suite.StageGateError("write_activation_bff_behavior_still_armed")

    monkeypatch.setattr(stage_suite.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        stage_suite,
        "_run_checked",
        lambda label, command, **_kwargs: calls.append((label, command)) or "",
    )
    monkeypatch.setattr(
        stage_suite,
        "_verify_bff_fail_safe_stopped",
        lambda: calls.append("verify-stopped"),
        raising=False,
    )

    assert stage_suite._disarm_bff_guarded(
        context,
        behavioral_dark_probe=reject_behavioral_darkness,
        attempts=2,
    ) == {
        "attempts": 2,
        "dark": False,
        "stopped": True,
        "failed_gate": "write_activation_bff_behavior_still_armed",
    }
    assert calls == [
        "restart:False",
        "verify-env",
        "verify-behavior",
        "restart:False",
        "verify-env",
        "verify-behavior",
        (
            "write_activation_bff_fail_safe_stop",
            stage_suite._pm2_command("stop", "bff-water-planning"),
        ),
        "verify-stopped",
    ]


def test_disarm_bff_guarded_does_not_trust_an_unverified_stop(tmp_path, monkeypatch):
    context = _write_ui_context(tmp_path)
    monkeypatch.setattr(
        stage_suite,
        "_restart_bff_with_flag",
        lambda _context, *, enabled: None,
    )
    monkeypatch.setattr(stage_suite, "_verify_bff_write_flag_dark", lambda: None)
    monkeypatch.setattr(stage_suite, "_run_checked", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        stage_suite,
        "_verify_bff_fail_safe_stopped",
        lambda: (_ for _ in ()).throw(
            stage_suite.StageGateError("write_activation_bff_stop_not_verified")
        ),
        raising=False,
    )

    def reject_behavioral_darkness():
        raise stage_suite.StageGateError("write_activation_bff_behavior_still_armed")

    assert stage_suite._disarm_bff_guarded(
        context,
        behavioral_dark_probe=reject_behavioral_darkness,
        attempts=1,
    ) == {
        "attempts": 1,
        "dark": False,
        "stopped": False,
        "failed_gate": "write_activation_bff_behavior_still_armed",
    }


def test_verify_bff_fail_safe_stopped_rejects_a_still_online_process(monkeypatch):
    monkeypatch.setattr(stage_suite, "_pm2_json", lambda: "pm2-json")
    monkeypatch.setattr(
        stage_suite,
        "project_pm2_state",
        lambda _value: [
            {
                "name": "bff-water-planning",
                "status": "online",
                "restarts": 0,
                "pid": 123,
                "memory_bytes": 1,
                "cpu_percent": 0,
            }
        ],
    )
    monkeypatch.setattr(
        stage_suite,
        "_listener_snapshot",
        lambda: [{"address": "127.0.0.1", "port": 3022}],
    )
    monkeypatch.setattr(
        stage_suite,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("readiness after online PM2 verdict"),
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_bff_stop_not_verified",
    ):
        stage_suite._verify_bff_fail_safe_stopped()


def _fail_safe_pm2_inventory(*bff_entries):
    return [
        {
            "name": name,
            "status": "online",
            "restarts": 0,
            "pid": index + 100,
            "memory_bytes": 1,
            "cpu_percent": 0,
        }
        for index, name in enumerate(stage_suite.PROCESS_NAMES)
        if name != "bff-water-planning"
    ] + list(bff_entries)


@pytest.mark.parametrize(
    "bff_entries",
    (
        (),
        ({"name": "bff-water-planning", "status": "launching"},),
        ({"name": "bff-water-planning", "status": "stopping"},),
        ({"name": "bff-water-planning", "status": "errored"},),
        (
            {"name": "bff-water-planning", "status": "stopped"},
            {"name": "bff-water-planning", "status": "stopped"},
        ),
    ),
)
def test_verify_bff_fail_safe_stopped_rejects_nonterminal_or_duplicate_inventory(
    monkeypatch, bff_entries
):
    monkeypatch.setattr(stage_suite, "_pm2_json", lambda: "pm2-json")
    monkeypatch.setattr(
        stage_suite,
        "project_pm2_state",
        lambda _value: _fail_safe_pm2_inventory(*bff_entries),
    )
    monkeypatch.setattr(
        stage_suite,
        "_listener_snapshot",
        lambda: pytest.fail("listener probe after invalid PM2 inventory"),
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_bff_stop_not_verified",
    ):
        stage_suite._verify_bff_fail_safe_stopped()


def test_verify_bff_fail_safe_stopped_rejects_a_restart_during_quiet_period(
    monkeypatch,
):
    pm2_observations = iter(
        (
            _fail_safe_pm2_inventory(
                {"name": "bff-water-planning", "status": "stopped"}
            ),
            _fail_safe_pm2_inventory(
                {"name": "bff-water-planning", "status": "online"}
            ),
        )
    )
    monkeypatch.setattr(stage_suite, "_pm2_json", lambda: "pm2-json")
    monkeypatch.setattr(
        stage_suite,
        "project_pm2_state",
        lambda _value: next(pm2_observations),
    )
    monkeypatch.setattr(stage_suite, "_listener_snapshot", lambda: [])
    monkeypatch.setattr(
        stage_suite,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            stage_suite.URLError(ConnectionRefusedError())
        ),
    )
    monkeypatch.setattr(stage_suite.time, "sleep", lambda _seconds: None)

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_bff_stop_not_verified",
    ):
        stage_suite._verify_bff_fail_safe_stopped()


def test_verify_bff_fail_safe_stopped_requires_three_quiet_terminal_samples(
    monkeypatch,
):
    observations = []
    monkeypatch.setattr(
        stage_suite,
        "_pm2_json",
        lambda: observations.append("pm2") or "pm2-json",
    )
    monkeypatch.setattr(
        stage_suite,
        "project_pm2_state",
        lambda _value: _fail_safe_pm2_inventory(
            {"name": "bff-water-planning", "status": "stopped"}
        ),
    )
    monkeypatch.setattr(
        stage_suite,
        "_listener_snapshot",
        lambda: observations.append("listeners") or [],
    )
    monkeypatch.setattr(
        stage_suite,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            stage_suite.URLError(ConnectionRefusedError())
        ),
    )
    monkeypatch.setattr(
        stage_suite.time,
        "sleep",
        lambda seconds: observations.append(f"sleep:{seconds}"),
    )

    stage_suite._verify_bff_fail_safe_stopped()

    assert observations == [
        "pm2",
        "listeners",
        "sleep:1.0",
        "pm2",
        "listeners",
        "sleep:1.0",
        "pm2",
        "listeners",
    ]


def test_disarm_bff_guarded_accepts_a_later_verified_retry(tmp_path, monkeypatch):
    context = _write_ui_context(tmp_path)
    calls = []
    verdicts = iter((False, True))

    monkeypatch.setattr(
        stage_suite,
        "_restart_bff_with_flag",
        lambda _context, *, enabled: calls.append(f"restart:{enabled}"),
    )

    def verify():
        calls.append("verify")
        if next(verdicts) is False:
            raise stage_suite.StageGateError("write_activation_bff_still_armed")

    monkeypatch.setattr(
        stage_suite,
        "_verify_bff_write_flag_dark",
        verify,
        raising=False,
    )
    monkeypatch.setattr(
        stage_suite.time, "sleep", lambda _seconds: calls.append("sleep")
    )
    monkeypatch.setattr(
        stage_suite,
        "_run_checked",
        lambda *_args, **_kwargs: pytest.fail("fail-safe stop after verified retry"),
    )

    assert stage_suite._disarm_bff_guarded(
        context,
        behavioral_dark_probe=lambda: calls.append("behavior"),
        attempts=2,
    ) == {
        "attempts": 2,
        "dark": True,
        "stopped": False,
        "failed_gate": None,
    }
    assert calls == [
        "restart:False",
        "verify",
        "sleep",
        "restart:False",
        "verify",
        "behavior",
    ]


@pytest.mark.parametrize(
    "sticky_error_code",
    (
        "write_activation_fresh_operator_cleanup_unproved",
        "write_activation_rollback_session_evidence_incomplete",
    ),
)
def test_disarm_bff_guarded_cannot_clear_unproved_session_cleanup(
    tmp_path, monkeypatch, sticky_error_code
):
    context = _write_ui_context(tmp_path)
    calls = []
    probe_attempts = [0]

    monkeypatch.setattr(
        stage_suite,
        "_restart_bff_with_flag",
        lambda _context, *, enabled: calls.append(f"restart:{enabled}"),
    )
    monkeypatch.setattr(stage_suite, "_verify_bff_write_flag_dark", lambda: None)
    monkeypatch.setattr(stage_suite.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        stage_suite,
        "_run_checked",
        lambda *_args, **_kwargs: calls.append("fail-safe-stop") or "",
    )
    monkeypatch.setattr(
        stage_suite,
        "_verify_bff_fail_safe_stopped",
        lambda: calls.append("stop-verified"),
    )

    def behavioral_probe():
        probe_attempts[0] += 1
        if probe_attempts[0] == 1:
            raise stage_suite.StageGateError(sticky_error_code)
        calls.append("later-dark-proof")

    report = stage_suite._disarm_bff_guarded(
        context,
        behavioral_dark_probe=behavioral_probe,
        attempts=3,
        backoff_seconds=0,
    )

    assert report["dark"] is False
    assert report["stopped"] is True
    assert report["failed_gate"] == sticky_error_code
    assert "later-dark-proof" not in calls
    assert calls[-2:] == ["fail-safe-stop", "stop-verified"]


def test_restore_write_activation_dark_reports_fail_safe_stop_and_runs_scheduler(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    calls = []
    disarm_report = {
        "attempts": 3,
        "dark": False,
        "stopped": True,
        "failed_gate": "write_activation_bff_still_armed",
    }
    monkeypatch.setattr(stage_suite, "_build_frontend", lambda *_args, **_kwargs: None)

    class DarkServer:
        def __enter__(self):
            return None

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(
        stage_suite, "_frontend_server", lambda *_args, **_kwargs: DarkServer()
    )
    monkeypatch.setattr(
        stage_suite,
        "_run_write_dark_browser",
        lambda _context: {"submit_absent": True},
    )
    monkeypatch.setattr(
        stage_suite,
        "_disarm_bff_guarded",
        lambda _context, *, behavioral_dark_probe: calls.append("bff")
        or behavioral_dark_probe()
        or disarm_report,
        raising=False,
    )
    monkeypatch.setattr(
        stage_suite,
        "_restore_scheduler_guarded",
        lambda: calls.append("scheduler")
        or {"attempts": 1, "restored": True, "failed_gate": None},
    )

    assert stage_suite._restore_write_activation_dark(
        context,
        bff_dark_probe=lambda: None,
    ) == {
        "frontend_dark_build": True,
        "frontend_dark_rendered": True,
        "frontend_dark_evidence": {"submit_absent": True},
        "bff_disarm": disarm_report,
        "bff_dark": False,
        "scheduler_restored": True,
        "restored": False,
        "failed_gate": "write_activation_bff_still_armed",
    }
    assert calls == ["bff", "scheduler"]


@pytest.mark.parametrize("interrupt_leg", ("frontend", "bff"))
def test_restore_write_activation_dark_defers_interrupt_until_all_legs_attempted(
    tmp_path, monkeypatch, interrupt_leg
):
    context = _write_ui_context(tmp_path)
    calls = []

    def build(*_args, **_kwargs):
        calls.append("frontend")
        if interrupt_leg == "frontend":
            raise KeyboardInterrupt

    def disarm(_context, *, behavioral_dark_probe):
        calls.append("bff:False")
        if interrupt_leg == "bff":
            raise KeyboardInterrupt
        behavioral_dark_probe()
        return {
            "attempts": 1,
            "dark": True,
            "stopped": False,
            "failed_gate": None,
        }

    class DarkServer:
        def __enter__(self):
            return None

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(stage_suite, "_build_frontend", build)
    monkeypatch.setattr(
        stage_suite, "_frontend_server", lambda *_args, **_kwargs: DarkServer()
    )
    monkeypatch.setattr(
        stage_suite,
        "_run_write_dark_browser",
        lambda _context: {"submit_absent": True},
    )
    monkeypatch.setattr(
        stage_suite,
        "_disarm_bff_guarded",
        disarm,
        raising=False,
    )
    monkeypatch.setattr(
        stage_suite,
        "_restore_scheduler_guarded",
        lambda: calls.append("scheduler")
        or {"attempts": 1, "restored": True, "failed_gate": None},
    )

    with pytest.raises(KeyboardInterrupt) as exc_info:
        stage_suite._restore_write_activation_dark(
            context,
            bff_dark_probe=lambda: None,
        )

    assert calls == ["frontend", "bff:False", "scheduler"]
    assert exc_info.value.restoration["scheduler_restored"] is True


def test_verify_write_activation_restoration_rejects_listener_drift(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    monkeypatch.setattr(stage_suite, "_pm2_json", lambda: "pm2")
    monkeypatch.setattr(
        stage_suite,
        "project_pm2_state",
        lambda _value: [
            {"name": name, "status": "online"} for name in stage_suite.PROCESS_NAMES
        ],
    )
    monkeypatch.setattr(
        stage_suite,
        "_actual_gate_environment",
        lambda _value: "environment",
    )
    monkeypatch.setattr(
        stage_suite,
        "collect_dark_runtime_contract",
        lambda _environment, _release: {"dark": True},
    )
    monkeypatch.setattr(
        stage_suite,
        "_listener_snapshot",
        lambda: [{"address": "127.0.0.1", "port": 9999}],
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_listener_restoration_failed",
    ):
        stage_suite._verify_write_activation_restoration(
            context,
            before_dark={"dark": True},
            model_release={"commandable": False},
            before_listeners=[],
        )


@pytest.mark.parametrize(
    "extra_process",
    (
        {"name": "unexpected-water-process", "status": "online"},
        {"name": stage_suite.PROCESS_NAMES[0], "status": "stopped"},
    ),
)
def test_verify_write_activation_restoration_rejects_non_exact_pm2_inventory(
    tmp_path, monkeypatch, extra_process
):
    context = _write_ui_context(tmp_path)
    expected_dark = {"dark": True}
    expected_gates = {
        "control_plan_reads": False,
        "control_plan_evidence_reads": False,
        "water_planning_v2": False,
        "water_planning_submit": False,
    }
    monkeypatch.setattr(stage_suite, "_pm2_json", lambda: "pm2")
    monkeypatch.setattr(
        stage_suite,
        "project_pm2_state",
        lambda _value: [
            {"name": name, "status": "online"} for name in stage_suite.PROCESS_NAMES
        ]
        + [extra_process],
    )
    monkeypatch.setattr(
        stage_suite, "_actual_gate_environment", lambda _value: "environment"
    )
    monkeypatch.setattr(
        stage_suite,
        "collect_dark_runtime_contract",
        lambda _environment, _release: expected_dark,
    )
    monkeypatch.setattr(stage_suite, "_listener_snapshot", lambda: [])
    monkeypatch.setattr(
        stage_suite, "frontend_process_environment", lambda *_args, **_kwargs: {}
    )
    monkeypatch.setattr(
        stage_suite,
        "project_frontend_activation_gates",
        lambda _environment: expected_gates,
    )
    monkeypatch.setattr(stage_suite, "_readiness_snapshot", lambda: {})
    monkeypatch.setattr(stage_suite, "_verify_frontend_source", lambda _context: {})

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_process_restoration_failed",
    ):
        stage_suite._verify_write_activation_restoration(
            context,
            before_dark=expected_dark,
            model_release={"commandable": False},
            before_listeners=[],
        )


@pytest.mark.parametrize(
    "mutate_readiness",
    (
        lambda readiness: readiness.pop(stage_suite.PROCESS_NAMES[0]),
        lambda readiness: readiness.update(
            {"unexpected-water-process": readiness[stage_suite.PROCESS_NAMES[0]]}
        ),
        lambda readiness: readiness[stage_suite.PROCESS_NAMES[0]].update(
            {"status_code": 503}
        ),
        lambda readiness: readiness[stage_suite.PROCESS_NAMES[0]].update(
            {"status": "not_ready"}
        ),
        lambda readiness: readiness[stage_suite.PROCESS_NAMES[0]].update(
            {"checks": "not-a-dict"}
        ),
    ),
)
def test_verify_write_activation_restoration_rejects_invalid_readiness_evidence(
    tmp_path, monkeypatch, mutate_readiness
):
    context = _write_ui_context(tmp_path)
    expected_dark = {"dark": True}
    expected_gates = {
        "control_plan_reads": False,
        "control_plan_evidence_reads": False,
        "water_planning_v2": False,
        "water_planning_submit": False,
    }
    readiness = {
        name: {"status_code": 200, "status": "ready", "checks": {}}
        for name in stage_suite.PROCESS_NAMES
    }
    mutate_readiness(readiness)
    monkeypatch.setattr(stage_suite, "_pm2_json", lambda: "pm2")
    monkeypatch.setattr(
        stage_suite,
        "project_pm2_state",
        lambda _value: [
            {"name": name, "status": "online"} for name in stage_suite.PROCESS_NAMES
        ],
    )
    monkeypatch.setattr(
        stage_suite, "_actual_gate_environment", lambda _value: "environment"
    )
    monkeypatch.setattr(
        stage_suite,
        "collect_dark_runtime_contract",
        lambda _environment, _release: expected_dark,
    )
    monkeypatch.setattr(stage_suite, "_listener_snapshot", lambda: [])
    monkeypatch.setattr(
        stage_suite, "frontend_process_environment", lambda *_args, **_kwargs: {}
    )
    monkeypatch.setattr(
        stage_suite,
        "project_frontend_activation_gates",
        lambda _environment: expected_gates,
    )
    monkeypatch.setattr(stage_suite, "_readiness_snapshot", lambda: readiness)
    monkeypatch.setattr(stage_suite, "_verify_frontend_source", lambda _context: {})

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_readiness_restoration_failed",
    ):
        stage_suite._verify_write_activation_restoration(
            context,
            before_dark=expected_dark,
            model_release={"commandable": False},
            before_listeners=[],
        )


def test_verify_write_activation_restoration_returns_exact_process_baseline(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    expected_dark = {"dark": True}
    expected_gates = {
        "control_plan_reads": False,
        "control_plan_evidence_reads": False,
        "water_planning_v2": False,
        "water_planning_submit": False,
    }
    processes = [
        {
            "name": name,
            "status": "online",
            "restarts": index,
            "pid": 100 + index,
            "memory_bytes": 1024 + index,
            "cpu_percent": index / 10,
        }
        for index, name in enumerate(stage_suite.PROCESS_NAMES)
    ]
    readiness = {
        name: {"status_code": 200, "status": "ready", "checks": {}}
        for name in stage_suite.PROCESS_NAMES
    }
    listeners = [
        {"address": "127.0.0.1", "port": port} for port in (3011, 3021, 3022, 3047)
    ]
    monkeypatch.setattr(stage_suite, "_pm2_json", lambda: "pm2")
    monkeypatch.setattr(stage_suite, "project_pm2_state", lambda _value: processes)
    monkeypatch.setattr(
        stage_suite, "_actual_gate_environment", lambda _value: "environment"
    )
    monkeypatch.setattr(
        stage_suite,
        "collect_dark_runtime_contract",
        lambda _environment, _release: expected_dark,
    )
    monkeypatch.setattr(stage_suite, "_listener_snapshot", lambda: listeners)
    monkeypatch.setattr(
        stage_suite, "frontend_process_environment", lambda *_args, **_kwargs: {}
    )
    monkeypatch.setattr(
        stage_suite,
        "project_frontend_activation_gates",
        lambda _environment: expected_gates,
    )
    monkeypatch.setattr(stage_suite, "_readiness_snapshot", lambda: readiness)
    monkeypatch.setattr(stage_suite, "_verify_frontend_source", lambda _context: None)

    result = stage_suite._verify_write_activation_restoration(
        context,
        before_dark=expected_dark,
        model_release={"commandable": False},
        before_listeners=listeners,
    )

    assert result["processes"] == processes


def test_run_local_write_activation_clears_stale_browser_result_before_source_check(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    target = stage_suite._persist_write_browser_result(
        context,
        _write_browser_evidence(),
        stage="LOCAL-WRITE-ACT-1",
    )
    monkeypatch.setattr(
        stage_suite,
        "_load_state",
        lambda _context: {"completed": list(stage_suite.STAGE_ORDER[:9])},
    )

    def stop_before_login(_context):
        raise stage_suite.StageGateError("frontend_source_identity_stale")

    monkeypatch.setattr(stage_suite, "_verify_frontend_source", stop_before_login)

    with pytest.raises(
        stage_suite.StageGateError,
        match="frontend_source_identity_stale",
    ):
        stage_suite.run_local_write_activation(context)

    assert not target.exists()
    assert target.name not in stage_suite._read_checksum_index(
        context.evidence_root / "SHA256SUMS"
    )


def test_run_local_write_activation_cleans_accepted_initial_login_failure(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    cleanup = []

    class AcceptedLoginClient:
        def refresh_cookie(self):
            return "accepted-initial-refresh-token"

    monkeypatch.setattr(
        stage_suite,
        "_load_state",
        lambda _context: {"completed": list(stage_suite.STAGE_ORDER[:9])},
    )
    monkeypatch.setattr(stage_suite, "_verify_frontend_source", lambda _context: {})
    monkeypatch.setattr(stage_suite, "_load_harness_module", lambda *_args: object())
    monkeypatch.setattr(stage_suite, "LocalHttpClient", AcceptedLoginClient)
    monkeypatch.setattr(
        stage_suite,
        "_login_operator",
        lambda *_args: (_ for _ in ()).throw(
            stage_suite.StageGateError("operator_login_not_accepted")
        ),
    )
    monkeypatch.setattr(
        stage_suite,
        "_operator_logout",
        lambda _client, refresh, *, strict, error_code: cleanup.append(
            (refresh, strict, error_code)
        ),
    )
    monkeypatch.setattr(
        stage_suite,
        "_assert_operator_refresh_reuse_rejected",
        lambda _client, refresh: cleanup.append(("reuse", refresh))
        or {"refresh_reuse_status": 401, "revoked": True},
    )
    monkeypatch.setattr(
        stage_suite,
        "_run_local_write_activation_authenticated",
        lambda *_args, **_kwargs: pytest.fail("authenticated body after failed login"),
    )

    with pytest.raises(stage_suite.StageGateError, match="operator_login_not_accepted"):
        stage_suite.run_local_write_activation(context)

    assert cleanup == [
        (
            "accepted-initial-refresh-token",
            False,
            "write_activation_operator_logout_failed",
        ),
        ("reuse", "accepted-initial-refresh-token"),
    ]


@pytest.mark.parametrize("failure_point", ("accepted_login", "post_login"))
def test_run_local_write_activation_rejects_unproved_initial_session_cleanup(
    tmp_path, monkeypatch, failure_point
):
    context = _write_ui_context(tmp_path)
    cleanup = []
    primary = stage_suite.StageGateError(f"injected_{failure_point}_failure")

    class AcceptedLoginClient:
        def refresh_cookie(self):
            return "accepted-initial-refresh-token"

    monkeypatch.setattr(
        stage_suite,
        "_load_state",
        lambda _context: {"completed": list(stage_suite.STAGE_ORDER[:9])},
    )
    monkeypatch.setattr(stage_suite, "_verify_frontend_source", lambda _context: {})
    monkeypatch.setattr(stage_suite, "_load_harness_module", lambda *_args: object())
    monkeypatch.setattr(stage_suite, "LocalHttpClient", AcceptedLoginClient)
    if failure_point == "accepted_login":
        monkeypatch.setattr(
            stage_suite,
            "_login_operator",
            lambda *_args: (_ for _ in ()).throw(primary),
        )
    else:
        monkeypatch.setattr(
            stage_suite,
            "_login_operator",
            lambda *_args: (
                "access-token",
                "accepted-initial-refresh-token",
                {"login": "accepted"},
            ),
        )
    monkeypatch.setattr(
        stage_suite,
        "_run_local_write_activation_authenticated",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(primary),
    )
    monkeypatch.setattr(
        stage_suite,
        "_operator_logout",
        lambda _client, refresh, *, strict, error_code: cleanup.append(
            ("logout", refresh, strict, error_code)
        )
        or False,
    )

    def reject_reuse(_client, refresh):
        cleanup.append(("reuse", refresh))
        raise stage_suite.StageGateError("operator_refresh_reuse_not_rejected")

    monkeypatch.setattr(
        stage_suite,
        "_assert_operator_refresh_reuse_rejected",
        reject_reuse,
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_initial_operator_cleanup_unproved",
    ) as exc_info:
        stage_suite.run_local_write_activation(context)

    assert exc_info.value.__cause__ is primary
    assert [call[0] for call in cleanup] == ["logout", "reuse"]


def test_run_local_write_activation_preserves_post_login_failure_after_proved_cleanup(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    cleanup = []
    primary = stage_suite.StageGateError("injected_post_login_failure")

    monkeypatch.setattr(
        stage_suite,
        "_load_state",
        lambda _context: {"completed": list(stage_suite.STAGE_ORDER[:9])},
    )
    monkeypatch.setattr(stage_suite, "_verify_frontend_source", lambda _context: {})
    monkeypatch.setattr(stage_suite, "_load_harness_module", lambda *_args: object())
    monkeypatch.setattr(stage_suite, "LocalHttpClient", object)
    monkeypatch.setattr(
        stage_suite,
        "_login_operator",
        lambda *_args: (
            "access-token",
            "accepted-initial-refresh-token",
            {"login": "accepted"},
        ),
    )
    monkeypatch.setattr(
        stage_suite,
        "_run_local_write_activation_authenticated",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(primary),
    )
    monkeypatch.setattr(
        stage_suite,
        "_operator_logout",
        lambda _client, refresh, *, strict, error_code: cleanup.append(
            ("logout", refresh, strict, error_code)
        )
        or True,
    )
    monkeypatch.setattr(
        stage_suite,
        "_assert_operator_refresh_reuse_rejected",
        lambda _client, refresh: cleanup.append(("reuse", refresh))
        or {"refresh_reuse_status": 401, "revoked": True},
    )

    with pytest.raises(stage_suite.StageGateError) as exc_info:
        stage_suite.run_local_write_activation(context)

    assert exc_info.value is primary
    assert [call[0] for call in cleanup] == ["logout", "reuse"]


def test_run_local_write_activation_persists_manifest_and_full_state(
    tmp_path, monkeypatch
):
    context = _write_ui_context(tmp_path)
    client = _RecordingLogoutClient(status=200)
    saved = []
    authenticated_calls = []
    verifier = object()
    monkeypatch.setattr(
        stage_suite,
        "_load_state",
        lambda _context: {"completed": list(stage_suite.STAGE_ORDER[:9])},
    )
    monkeypatch.setattr(stage_suite, "_verify_frontend_source", lambda _context: {})
    monkeypatch.setattr(stage_suite, "_load_harness_module", lambda *_args: verifier)
    monkeypatch.setattr(stage_suite, "LocalHttpClient", lambda: client)
    monkeypatch.setattr(
        stage_suite,
        "_login_operator",
        lambda *_args: ("token", "refresh-cookie", {"login": "accepted"}),
    )
    monkeypatch.setattr(
        stage_suite,
        "_run_local_write_activation_authenticated",
        lambda *args, **kwargs: authenticated_calls.append((args, kwargs))
        or {"activation": "accepted"},
    )
    monkeypatch.setattr(
        stage_suite,
        "_assert_operator_refresh_reuse_rejected",
        lambda *_args: {"revoked": True},
    )
    monkeypatch.setattr(
        stage_suite,
        "_save_state",
        lambda _context, completed: saved.append(completed),
    )

    manifest = stage_suite.run_local_write_activation(context)

    assert manifest["stage"] == "LOCAL-WRITE-ACT-1"
    assert manifest["verdict"] == "PASS"
    assert manifest["steps"] == {
        "activation": "accepted",
        "refresh_revoked": {"revoked": True},
    }
    assert saved == [list(stage_suite.STAGE_ORDER)]
    assert client.logout_calls == [{"refreshToken": "refresh-cookie"}]
    assert authenticated_calls[0][1] == {"verifier": verifier}
    target = context.evidence_root / "LOCAL-WRITE-ACT-1.json"
    assert json.loads(target.read_text(encoding="utf-8")) == manifest
    stage_suite._verify_checksum_entry(target)


def test_main_dispatches_write_activation_distinct_from_persist_only(
    tmp_path, monkeypatch
):
    calls = []
    args = SimpleNamespace(
        stage="LOCAL-WRITE-ACT-1",
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "evidence",
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=date(2026, 8, 20),
        execution_kind="canonical",
        diagnostic=False,
    )
    monkeypatch.setattr(stage_suite, "_parse_args", lambda _argv: args)
    monkeypatch.setattr(
        stage_suite,
        "run_local_write_activation",
        lambda context: calls.append(("activation", context.as_of_date)),
    )
    monkeypatch.setattr(
        stage_suite,
        "run_local_persist_only",
        lambda _context: pytest.fail(
            "persist-only dispatch must not receive WRITE-ACT"
        ),
    )

    assert stage_suite.main([]) == 0
    assert calls == [("activation", date(2026, 8, 20))]


# --- R1: receipt-bound persist-only diff ---

PERSIST_TARGET_WEEK_KEY = "2027-R02"
PERSIST_TARGET_WEEK_DATE = "2026-11-08"  # canonical span start of 2027-R02
PERSIST_CREATE_ID = "11111111-1111-4111-8111-111111111111"
PERSIST_CORRECT_ID = "22222222-2222-4222-8222-222222222222"
PERSIST_CREATE_DEPTHS = {f"01-{z:02d}": 250.0 + 10.0 * (z - 1) for z in range(1, 7)}
PERSIST_CORRECT_DEPTHS = {f"01-{z:02d}": 350.0 + 10.0 * (z - 1) for z in range(1, 7)}
PERSIST_NON_W2_DIGESTS = {
    "ros_gis.water_requirement_runs": "d" * 32,
    "ros_gis.dataset_versions": "e" * 32,
    "scheduler.control_plan_runs": "f" * 32,
    "scheduler.control_command_outbox": "0" * 32,
}


def _persist_submission_row(
    submission_id, *, csid, request_sha256, supersedes, expanded
):
    return {
        "submission_id": submission_id,
        "schema_version": 2,
        "client_submission_id": csid,
        "project_key": "mun-bon",
        "week_key": PERSIST_TARGET_WEEK_KEY,
        "week_date": PERSIST_TARGET_WEEK_DATE,
        "submitted_at": "2026-07-28T00:00:00+00:00",
        "submitted_by": "operator-1",
        "supersedes_submission_id": supersedes,
        "request_document_text": "{}",
        "request_sha256": request_sha256,
        "expanded_sha256": expanded,
        "calendar_system": "rid-irrigation-v1",
        "roster_dataset_version_id": 7,
        "roster_source_hash": "a" * 64,
    }


def _persist_receipt(submission_id, *, csid, request_sha256, supersedes):
    return {
        "submission_id": submission_id,
        "client_submission_id": csid,
        "request_sha256": request_sha256,
        "replayed": False,
        "week_key": PERSIST_TARGET_WEEK_KEY,
        "project_key": "mun-bon",
        "submitted_at": "2026-07-28T00:00:00+00:00",
        "submitted_by": "operator-1",
        "calendar_system": "rid-irrigation-v1",
        "week_date": PERSIST_TARGET_WEEK_DATE,
        "supersedes_submission_id": supersedes,
    }


def _persist_value_rows(submission_id, depths):
    return [
        {"submission_id": submission_id, **level} for level in _expanded_levels(depths)
    ]


def _persist_only_valid_case():
    create_row = _persist_submission_row(
        PERSIST_CREATE_ID,
        csid="c1",
        request_sha256="a" * 64,
        supersedes=None,
        expanded="1" * 64,
    )
    correct_row = _persist_submission_row(
        PERSIST_CORRECT_ID,
        csid="c2",
        request_sha256="b" * 64,
        supersedes=PERSIST_CREATE_ID,
        expanded="2" * 64,
    )
    before = {
        "non_w2_digests": dict(PERSIST_NON_W2_DIGESTS),
        "w2_submissions": [],
        "w2_values": [],
    }
    after = {
        "non_w2_digests": dict(PERSIST_NON_W2_DIGESTS),
        "w2_submissions": [create_row, correct_row],
        "w2_values": (
            _persist_value_rows(PERSIST_CREATE_ID, PERSIST_CREATE_DEPTHS)
            + _persist_value_rows(PERSIST_CORRECT_ID, PERSIST_CORRECT_DEPTHS)
        ),
    }
    kwargs = {
        "create_receipt": _persist_receipt(
            PERSIST_CREATE_ID, csid="c1", request_sha256="a" * 64, supersedes=None
        ),
        "correct_receipt": _persist_receipt(
            PERSIST_CORRECT_ID,
            csid="c2",
            request_sha256="b" * 64,
            supersedes=PERSIST_CREATE_ID,
        ),
        "target_week_key": PERSIST_TARGET_WEEK_KEY,
        "target_week_date": PERSIST_TARGET_WEEK_DATE,
        "create_zone_depths": PERSIST_CREATE_DEPTHS,
        "correct_zone_depths": PERSIST_CORRECT_DEPTHS,
    }
    return before, after, kwargs


def test_validate_persist_only_diff_accepts_exact_two_receipt_bound_submissions():
    before, after, kwargs = _persist_only_valid_case()

    result = stage_suite.validate_persist_only_diff(before, after, **kwargs)

    assert result["w2_submissions_added"] == [PERSIST_CREATE_ID, PERSIST_CORRECT_ID]
    assert result["w2_values_added"] == 82
    assert result["supersedes_chain"] == {
        PERSIST_CREATE_ID: None,
        PERSIST_CORRECT_ID: PERSIST_CREATE_ID,
    }
    assert result["non_w2_tables_unchanged"] == len(PERSIST_NON_W2_DIGESTS)


def _write_activation_valid_case():
    before, after, _kwargs = _persist_only_valid_case()
    browser = _write_browser_evidence()
    create_request = browser["request_identity"]["create"]
    correct_request = browser["request_identity"]["correct"]

    def request_document(request):
        value = {
            "calendar_system": request["calendar_system"],
            "levels": [
                {
                    "area_id": level["area_id"],
                    "area_type": level["area_type"],
                    "planning_depth_mm": f'{level["planning_depth_mm"]:.3f}',
                }
                for level in sorted(
                    request["levels"],
                    key=lambda level: (level["area_type"], level["area_id"]),
                )
            ],
            "project_key": request["project_key"],
            "schema_version": request["schema_version"],
            "week_date": request["week_date"],
            "week_key": request["week_key"],
        }
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def expanded_sha(rows):
        value = [
            {
                "planning_depth_mm": f'{row["planning_depth_mm"]:.3f}',
                "section_id": row["section_id"],
                "source_area_id": row["source_area_id"],
                "source_kind": row["source_kind"],
                "zone_id": row["zone_id"],
            }
            for row in sorted(rows, key=lambda row: row["section_id"])
        ]
        text = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(text.encode()).hexdigest()

    create_document = request_document(create_request)
    correct_document = request_document(correct_request)
    after["w2_submissions"][0].update(
        {
            "client_submission_id": create_request["client_submission_id"],
            "request_document_text": create_document,
            "request_sha256": hashlib.sha256(create_document.encode()).hexdigest(),
        }
    )
    after["w2_submissions"][1].update(
        {
            "client_submission_id": correct_request["client_submission_id"],
            "request_document_text": correct_document,
            "request_sha256": hashlib.sha256(correct_document.encode()).hexdigest(),
        }
    )
    after["w2_values"] = _persist_value_rows(
        PERSIST_CREATE_ID, PERSIST_CREATE_DEPTHS
    ) + _persist_value_rows(
        PERSIST_CORRECT_ID,
        {f"01-{zone:02d}": 260.0 + 10.0 * (zone - 1) for zone in range(1, 7)},
    )
    after["w2_submissions"][0]["expanded_sha256"] = expanded_sha(
        [row for row in after["w2_values"] if row["submission_id"] == PERSIST_CREATE_ID]
    )
    after["w2_submissions"][1]["expanded_sha256"] = expanded_sha(
        [
            row
            for row in after["w2_values"]
            if row["submission_id"] == PERSIST_CORRECT_ID
        ]
    )
    browser["create_result"]["submission_id"] = PERSIST_CREATE_ID
    browser["active_readback"]["submission_id"] = PERSIST_CREATE_ID
    browser["correct_result"]["submission_id"] = PERSIST_CORRECT_ID
    browser["conflict_reconciliation"]["submission_id"] = PERSIST_CORRECT_ID
    browser["request_identity"]["correct"][
        "expected_active_submission_id"
    ] = PERSIST_CREATE_ID
    return before, after, browser


def test_validate_write_activation_diff_accepts_exact_browser_mutations():
    before, after, browser = _write_activation_valid_case()

    result = stage_suite.validate_write_activation_diff(
        before,
        after,
        browser_result=browser,
        target_week_key=PERSIST_TARGET_WEEK_KEY,
        target_week_date=PERSIST_TARGET_WEEK_DATE,
        expected_submitted_by="operator-1",
    )

    assert result == {
        "non_w2_tables_unchanged": len(PERSIST_NON_W2_DIGESTS),
        "w2_submissions_added": [PERSIST_CREATE_ID, PERSIST_CORRECT_ID],
        "w2_values_added": 82,
        "supersedes_chain": {
            PERSIST_CREATE_ID: None,
            PERSIST_CORRECT_ID: PERSIST_CREATE_ID,
        },
    }


@pytest.mark.parametrize(
    ("field", "substitute"),
    (
        ("client_submission_id", "55555555-5555-4555-8555-555555555555"),
        ("submitted_by", "operator-2"),
        ("roster_dataset_version_id", 8),
        ("roster_source_hash", "b" * 64),
        ("request_sha256", "c" * 64),
        ("expanded_sha256", "d" * 64),
    ),
)
def test_validate_write_activation_diff_rejects_valid_looking_substituted_binding(
    field, substitute
):
    before, after, browser = _write_activation_valid_case()
    after["w2_submissions"][0][field] = substitute

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_w2_shape_unexpected",
    ):
        stage_suite.validate_write_activation_diff(
            before,
            after,
            browser_result=browser,
            target_week_key=PERSIST_TARGET_WEEK_KEY,
            target_week_date=PERSIST_TARGET_WEEK_DATE,
            expected_submitted_by="operator-1",
        )


def test_validate_write_activation_diff_rejects_non_w2_side_effect():
    before, after, browser = _write_activation_valid_case()
    after["non_w2_digests"]["scheduler.control_command_outbox"] = "9" * 32

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_side_effect_detected",
    ):
        stage_suite.validate_write_activation_diff(
            before,
            after,
            browser_result=browser,
            target_week_key=PERSIST_TARGET_WEEK_KEY,
            target_week_date=PERSIST_TARGET_WEEK_DATE,
            expected_submitted_by="operator-1",
        )


def test_validate_write_activation_diff_rejects_broken_supersede_chain():
    before, after, browser = _write_activation_valid_case()
    after["w2_submissions"][1]["supersedes_submission_id"] = None

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_w2_shape_unexpected",
    ):
        stage_suite.validate_write_activation_diff(
            before,
            after,
            browser_result=browser,
            target_week_key=PERSIST_TARGET_WEEK_KEY,
            target_week_date=PERSIST_TARGET_WEEK_DATE,
            expected_submitted_by="operator-1",
        )


def test_validate_write_activation_diff_rejects_non_string_hash_as_stage_error():
    before, after, browser = _write_activation_valid_case()
    after["w2_submissions"][0]["roster_source_hash"] = 7

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_w2_shape_unexpected",
    ):
        stage_suite.validate_write_activation_diff(
            before,
            after,
            browser_result=browser,
            target_week_key=PERSIST_TARGET_WEEK_KEY,
            target_week_date=PERSIST_TARGET_WEEK_DATE,
            expected_submitted_by="operator-1",
        )


def test_validate_write_activation_diff_rejects_corrupt_request_document():
    before, after, browser = _write_activation_valid_case()
    after["w2_submissions"][0]["request_document_text"] = "{}"

    with pytest.raises(
        stage_suite.StageGateError,
        match="write_activation_w2_shape_unexpected",
    ):
        stage_suite.validate_write_activation_diff(
            before,
            after,
            browser_result=browser,
            target_week_key=PERSIST_TARGET_WEEK_KEY,
            target_week_date=PERSIST_TARGET_WEEK_DATE,
            expected_submitted_by="operator-1",
        )


def test_validate_persist_only_diff_rejects_ros_digest_change():
    before, after, kwargs = _persist_only_valid_case()
    after["non_w2_digests"]["ros_gis.water_requirement_runs"] = "9" * 32

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_side_effect_detected"
    ):
        stage_suite.validate_persist_only_diff(before, after, **kwargs)


def test_validate_persist_only_diff_rejects_scheduler_digest_change():
    before, after, kwargs = _persist_only_valid_case()
    after["non_w2_digests"]["scheduler.control_command_outbox"] = "9" * 32

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_side_effect_detected"
    ):
        stage_suite.validate_persist_only_diff(before, after, **kwargs)


def test_validate_persist_only_diff_rejects_new_non_w2_table():
    before, after, kwargs = _persist_only_valid_case()
    after["non_w2_digests"]["scheduler.control_plan_requirements"] = "7" * 32

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_side_effect_detected"
    ):
        stage_suite.validate_persist_only_diff(before, after, **kwargs)


def test_validate_persist_only_diff_rejects_extra_new_submission():
    before, after, kwargs = _persist_only_valid_case()
    after["w2_submissions"].append(
        _persist_submission_row(
            "33333333-3333-4333-8333-333333333333",
            csid="c3",
            request_sha256="c" * 64,
            supersedes=None,
            expanded="3" * 64,
        )
    )

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_w2_shape_unexpected"
    ):
        stage_suite.validate_persist_only_diff(before, after, **kwargs)


def test_validate_persist_only_diff_rejects_broken_supersede_chain():
    before, after, kwargs = _persist_only_valid_case()
    # correct row no longer supersedes the create row
    after["w2_submissions"][1]["supersedes_submission_id"] = None

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_w2_shape_unexpected"
    ):
        stage_suite.validate_persist_only_diff(before, after, **kwargs)


def test_validate_persist_only_diff_rejects_request_sha_not_matching_receipt():
    before, after, kwargs = _persist_only_valid_case()
    after["w2_submissions"][0]["request_sha256"] = "9" * 64

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_w2_shape_unexpected"
    ):
        stage_suite.validate_persist_only_diff(before, after, **kwargs)


def test_validate_persist_only_diff_rejects_missing_roster_provenance():
    before, after, kwargs = _persist_only_valid_case()
    after["w2_submissions"][0]["roster_source_hash"] = None

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_w2_shape_unexpected"
    ):
        stage_suite.validate_persist_only_diff(before, after, **kwargs)


def test_validate_persist_only_diff_rejects_wrong_week_scope():
    before, after, kwargs = _persist_only_valid_case()
    after["w2_submissions"][0]["week_key"] = "2027-R05"

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_w2_shape_unexpected"
    ):
        stage_suite.validate_persist_only_diff(before, after, **kwargs)


def test_validate_persist_only_diff_rejects_identical_expanded_digest():
    before, after, kwargs = _persist_only_valid_case()
    after["w2_submissions"][1]["expanded_sha256"] = after["w2_submissions"][0][
        "expanded_sha256"
    ]

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_w2_shape_unexpected"
    ):
        stage_suite.validate_persist_only_diff(before, after, **kwargs)


def test_validate_persist_only_diff_rejects_wrong_value_count():
    before, after, kwargs = _persist_only_valid_case()
    after["w2_values"].pop()  # 81 instead of 82

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_w2_shape_unexpected"
    ):
        stage_suite.validate_persist_only_diff(before, after, **kwargs)


def test_validate_persist_only_diff_rejects_corrupted_value_content():
    # The Codex "41 wrong values under the correct receipt id" attack: exactly 82
    # rows, correct ids, but one section carries a depth its zone never asked for.
    before, after, kwargs = _persist_only_valid_case()
    after["w2_values"][0]["planning_depth_mm"] = 999.0

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_w2_shape_unexpected"
    ):
        stage_suite.validate_persist_only_diff(before, after, **kwargs)


def test_validate_persist_only_diff_rejects_value_for_unrelated_submission():
    before, after, kwargs = _persist_only_valid_case()
    # swap one create-row value onto an id that is not one of the two new subs
    after["w2_values"][0] = {
        **after["w2_values"][0],
        "submission_id": "99999999-9999-4999-8999-999999999999",
    }

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_w2_shape_unexpected"
    ):
        stage_suite.validate_persist_only_diff(before, after, **kwargs)


def test_validate_persist_only_diff_rejects_mutation_of_existing_submission():
    before, after, kwargs = _persist_only_valid_case()
    existing = _persist_submission_row(
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        csid="c0",
        request_sha256="e" * 64,
        supersedes=None,
        expanded="0" * 64,
    )
    before["w2_submissions"].append(dict(existing))
    mutated = dict(existing)
    mutated["expanded_sha256"] = "f" * 64  # immutable row changed under our feet
    after["w2_submissions"].append(mutated)

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_w2_existing_mutated"
    ):
        stage_suite.validate_persist_only_diff(before, after, **kwargs)


def test_validate_persist_only_diff_rejects_mutation_of_existing_value():
    before, after, kwargs = _persist_only_valid_case()
    existing_value = {
        "submission_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "section_id": "01-01-01-03",
        "zone_id": "01-01",
        "planning_depth_mm": 111.0,
        "source_kind": "zone_default",
        "source_area_id": "01-01",
    }
    before["w2_values"].append(dict(existing_value))
    mutated_value = dict(existing_value)
    mutated_value["planning_depth_mm"] = 222.0
    after["w2_values"].append(mutated_value)

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_w2_existing_mutated"
    ):
        stage_suite.validate_persist_only_diff(before, after, **kwargs)


# --- R1: snapshot SQL builder + fail-closed reads ---

FICTIONAL_PR7_TABLES = (
    "ros_gis.requirement_runs",
    "ros_gis.daily_water_demands",
    "scheduler.control_plan_drafts",
    "scheduler.control_plan_versions",
)


def test_build_persist_snapshot_sql_covers_real_tables_and_is_deterministic():
    tables = sorted(stage_suite.PERSIST_ONLY_EXPECTED_NON_W2_TABLES)
    sql = stage_suite._build_persist_snapshot_sql(tables)

    for table in tables:
        assert table in sql
    # deterministic full-row digest of every column
    assert "to_jsonb(t)" in sql
    assert "ORDER BY to_jsonb(t)::text" in sql
    # the two W2 tables are captured as full ordered rows, not counts
    assert "planning_depth_submissions s" in sql
    assert "planning_depth_values v" in sql
    assert "ORDER BY s.submission_id" in sql
    # the PR-7 fictional names and the invalid s.id join are gone
    for fictional in FICTIONAL_PR7_TABLES:
        assert fictional not in sql
    assert "v.submission_id = s.id" not in sql


def test_persist_snapshot_table_digest_sql_rejects_injection():
    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_table_name_invalid"
    ):
        stage_suite._persist_snapshot_table_digest_sql("ros_gis.x; DROP TABLE y")


def test_enumerate_tables_fails_closed_on_missing_table(monkeypatch):
    monkeypatch.setattr(
        stage_suite, "_psql", lambda ctx, q: "ros_gis.dataset_versions\n"
    )

    with pytest.raises(stage_suite.StageGateError, match="persist_only_table_missing"):
        stage_suite._persist_only_enumerate_tables(object())


def test_enumerate_tables_fails_closed_on_query_error(monkeypatch):
    def boom(ctx, q):
        raise stage_suite.StageGateError("postgres_probe_failed")

    monkeypatch.setattr(stage_suite, "_psql", boom)

    with pytest.raises(stage_suite.StageGateError, match="postgres_probe_failed"):
        stage_suite._persist_only_enumerate_tables(object())


def test_take_persist_snapshot_does_not_swallow_enumerate_failure(monkeypatch):
    def boom(ctx):
        raise stage_suite.StageGateError("persist_only_table_missing")

    monkeypatch.setattr(stage_suite, "_persist_only_enumerate_tables", boom)

    with pytest.raises(stage_suite.StageGateError, match="persist_only_table_missing"):
        stage_suite._take_persist_snapshot(object())


def test_take_persist_snapshot_rejects_malformed_document(monkeypatch):
    monkeypatch.setattr(
        stage_suite,
        "_persist_only_enumerate_tables",
        lambda ctx: ["ros_gis.dataset_versions"],
    )
    monkeypatch.setattr(
        stage_suite,
        "_persist_snapshot_psql",
        lambda ctx, sql: {
            "non_w2_digests": {},
            "w2_submissions": "not-a-list",
            "w2_values": [],
        },
    )

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_snapshot_malformed"
    ):
        stage_suite._take_persist_snapshot(object())


def test_persist_snapshot_psql_fails_closed_on_unparseable(monkeypatch, tmp_path):
    (tmp_path / "bff.env").write_text(
        "POSTGRES_URL=postgresql://u:p@127.0.0.1:5432/munbon_local\n"
    )
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "evidence",
        runtime_env_dir=tmp_path,
    )
    monkeypatch.setattr(stage_suite, "_run_checked", lambda *a, **k: "not json")

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_snapshot_unparseable"
    ):
        stage_suite._persist_snapshot_psql(context, "SELECT 1")


# --- R1: Redis rate-limit side-effect accounting ---


def test_parse_rate_key_snapshot_parses_value_and_ttl_triples():
    raw = (
        "bff-water-planning:rate:planning_depth.submit:"
        + "a" * 64
        + "\t3\t60000\n"
        + "bff-water-planning:rate:planning_depth.submit:"
        + "b" * 64
        + "\t1\t-1"
    )

    parsed = stage_suite._parse_rate_key_snapshot(raw)

    op_a = "bff-water-planning:rate:planning_depth.submit:" + "a" * 64
    assert parsed[op_a] == {"value": 3, "ttl_ms": 60000}


def test_parse_rate_key_snapshot_fails_closed_on_non_integer():
    raw = "bff-water-planning:rate:planning_depth.submit:" + "a" * 64 + "\tNaN\t5"

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_rate_snapshot_unparseable"
    ):
        stage_suite._parse_rate_key_snapshot(raw)


_OP_KEY = "bff-water-planning:rate:planning_depth.submit:" + "a" * 64
_OTHER_OP_KEY = "bff-water-planning:rate:planning_depth.submit:" + "b" * 64


def test_rate_accounting_accepts_operator_increment_by_two():
    before = {_OP_KEY: {"value": 5, "ttl_ms": 60000}}
    after = {_OP_KEY: {"value": 7, "ttl_ms": 55000}}

    result = stage_suite.validate_persist_only_rate_accounting(before, after)

    assert result == {"operator_rate_key": _OP_KEY, "increment": 2}


def test_rate_accounting_accepts_fresh_operator_key():
    result = stage_suite.validate_persist_only_rate_accounting(
        {}, {_OP_KEY: {"value": 2, "ttl_ms": 60000}}
    )
    assert result["operator_rate_key"] == _OP_KEY


def test_rate_accounting_accepts_expired_then_reset_window():
    before = {_OP_KEY: {"value": 9, "ttl_ms": 50}}
    after = {_OP_KEY: {"value": 2, "ttl_ms": 60000}}

    result = stage_suite.validate_persist_only_rate_accounting(
        before,
        after,
        elapsed_ms=50,
    )

    assert result["operator_rate_key"] == _OP_KEY


def test_rate_accounting_rejects_operator_reset_before_prior_ttl_elapsed():
    before = {_OP_KEY: {"value": 9, "ttl_ms": 60000}}
    after = {_OP_KEY: {"value": 2, "ttl_ms": 300000}}

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_rate_side_effect_detected"
    ):
        stage_suite.validate_persist_only_rate_accounting(
            before,
            after,
            elapsed_ms=1000,
        )


def test_rate_accounting_rejects_side_key_disappearance_before_ttl_elapsed():
    before = {
        _OP_KEY: {"value": 5, "ttl_ms": 60000},
        _OTHER_OP_KEY: {"value": 3, "ttl_ms": 60000},
    }
    after = {_OP_KEY: {"value": 7, "ttl_ms": 55000}}

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_rate_side_effect_detected"
    ):
        stage_suite.validate_persist_only_rate_accounting(
            before,
            after,
            elapsed_ms=1000,
        )


def test_rate_accounting_accepts_side_key_disappearance_after_ttl_elapsed():
    before = {
        _OP_KEY: {"value": 5, "ttl_ms": 60000},
        _OTHER_OP_KEY: {"value": 3, "ttl_ms": 50},
    }
    after = {_OP_KEY: {"value": 7, "ttl_ms": 55000}}

    result = stage_suite.validate_persist_only_rate_accounting(
        before,
        after,
        elapsed_ms=50,
    )

    assert result == {"operator_rate_key": _OP_KEY, "increment": 2}


@pytest.mark.parametrize("elapsed_ms", (-1, float("inf"), float("nan"), "1000"))
def test_rate_accounting_rejects_invalid_elapsed_time(elapsed_ms):
    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_rate_elapsed_invalid"
    ):
        stage_suite.validate_persist_only_rate_accounting(
            {},
            {_OP_KEY: {"value": 2, "ttl_ms": 60000}},
            elapsed_ms=elapsed_ms,
        )


@pytest.mark.parametrize("ttl_ms", (-2, -1, 0, 300001))
@pytest.mark.parametrize("before", ({}, {_OP_KEY: {"value": 9, "ttl_ms": 50}}))
def test_rate_accounting_rejects_invalid_current_operator_ttl(before, ttl_ms):
    after = {_OP_KEY: {"value": 2, "ttl_ms": ttl_ms}}

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_rate_side_effect_detected"
    ):
        stage_suite.validate_persist_only_rate_accounting(
            before,
            after,
            configured_window_ms=300000,
        )


@pytest.mark.parametrize("current_ttl_ms", (-1, 61000))
def test_rate_accounting_rejects_persistent_or_renewed_same_window(
    current_ttl_ms,
):
    before = {_OP_KEY: {"value": 5, "ttl_ms": 60000}}
    after = {_OP_KEY: {"value": 7, "ttl_ms": current_ttl_ms}}

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_rate_side_effect_detected"
    ):
        stage_suite.validate_persist_only_rate_accounting(
            before,
            after,
            configured_window_ms=300000,
        )


def test_rate_accounting_rejects_renewed_unchanged_side_key():
    before = {
        _OP_KEY: {"value": 5, "ttl_ms": 60000},
        _OTHER_OP_KEY: {"value": 3, "ttl_ms": 60000},
    }
    after = {
        _OP_KEY: {"value": 7, "ttl_ms": 55000},
        _OTHER_OP_KEY: {"value": 3, "ttl_ms": 61000},
    }

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_rate_side_effect_detected"
    ):
        stage_suite.validate_persist_only_rate_accounting(
            before,
            after,
            configured_window_ms=300000,
        )


@pytest.mark.parametrize(
    ("before", "after"),
    (
        (
            {_OP_KEY: {"value": 5, "ttl_ms": 300000}},
            {_OP_KEY: {"value": 7, "ttl_ms": 250000}},
        ),
        (
            {
                _OP_KEY: {"value": 5, "ttl_ms": 300000},
                _OTHER_OP_KEY: {"value": 3, "ttl_ms": 300000},
            },
            {
                _OP_KEY: {"value": 7, "ttl_ms": 100000},
                _OTHER_OP_KEY: {"value": 3, "ttl_ms": 250000},
            },
        ),
    ),
)
def test_rate_accounting_rejects_surviving_window_ttl_above_elapsed_bound(
    before,
    after,
):
    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_rate_side_effect_detected"
    ):
        stage_suite.validate_persist_only_rate_accounting(
            before,
            after,
            elapsed_ms=200000,
        )


def test_rate_accounting_accepts_surviving_window_ttl_at_elapsed_bound():
    before = {_OP_KEY: {"value": 5, "ttl_ms": 300000}}
    after = {_OP_KEY: {"value": 7, "ttl_ms": 100100}}

    result = stage_suite.validate_persist_only_rate_accounting(
        before,
        after,
        elapsed_ms=200000,
    )

    assert result == {"operator_rate_key": _OP_KEY, "increment": 2}


def test_planning_depth_rate_key_uses_the_principal_subject_hash():
    subject = "operator-1"

    assert stage_suite._planning_depth_rate_key(subject) == (
        "bff-water-planning:rate:planning_depth.submit:"
        + hashlib.sha256(subject.encode("utf-8")).hexdigest()
    )


def test_rate_accounting_rejects_another_operator_increment_after_target_expiry():
    expected_operator_key = stage_suite._planning_depth_rate_key("operator-1")
    other_operator_key = stage_suite._planning_depth_rate_key("operator-2")
    before = {
        expected_operator_key: {"value": 9, "ttl_ms": 50},
        other_operator_key: {"value": 5, "ttl_ms": 60000},
    }
    after = {other_operator_key: {"value": 8, "ttl_ms": 59900}}

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_rate_side_effect_detected"
    ):
        stage_suite.validate_persist_only_rate_accounting(
            before,
            after,
            expected_increment=3,
            elapsed_ms=100,
            expected_operator_key=expected_operator_key,
        )


def test_persist_only_body_binds_rate_accounting_to_verified_principal(
    monkeypatch, tmp_path
):
    context = _write_ui_context(tmp_path)
    subject = "operator-1"
    expected_operator_key = (
        "bff-water-planning:rate:planning_depth.submit:"
        + hashlib.sha256(subject.encode("utf-8")).hexdigest()
    )
    client = _ScriptedClient(
        [
            _FakeResponse(200, {"subject": subject, "effective_roles": ["operator"]}),
            _FakeResponse(201, {"submission_id": "create-id"}),
            _FakeResponse(201, {"submission_id": "correct-id"}),
        ]
    )
    snapshots = iter(
        [
            {"non_w2_digests": {}, "w2_submissions": [], "w2_values": []},
            {"non_w2_digests": {}, "w2_submissions": [], "w2_values": []},
        ]
    )
    rate_snapshots = iter([{}, {expected_operator_key: {"value": 2, "ttl_ms": 1000}}])
    requests = iter(
        [
            {
                "levels": [{"area_id": "01-01", "planning_depth_mm": "260.000"}],
                "client_submission_id": "create-client-id",
            },
            {
                "levels": [{"area_id": "01-01", "planning_depth_mm": "270.000"}],
                "client_submission_id": "correct-client-id",
            },
        ]
    )
    events = []

    monkeypatch.setattr(stage_suite, "_persist_only_rid_week", lambda _date: ("d", "w"))
    monkeypatch.setattr(
        stage_suite,
        "_load_env_file",
        lambda _path: {"PLANNING_DEPTH_WRITES_ENABLED": "false"},
    )
    monkeypatch.setattr(
        stage_suite, "_take_persist_snapshot", lambda _ctx: next(snapshots)
    )
    monkeypatch.setattr(
        stage_suite,
        "assert_persist_target_week_clean",
        lambda *_args: {"clean": True},
    )
    monkeypatch.setattr(
        stage_suite,
        "_snapshot_planning_depth_rate_keys",
        lambda _ctx: next(rate_snapshots),
    )
    monkeypatch.setattr(stage_suite.time, "monotonic", lambda: 1.0)
    monkeypatch.setattr(
        stage_suite, "_restart_bff_with_flag", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        stage_suite,
        "_build_planning_depth_request_v2",
        lambda **_kwargs: next(requests),
    )
    monkeypatch.setattr(
        stage_suite,
        "validate_w1_principal_result",
        lambda status, body, headers: events.append("principal-verified")
        or {"subject": body["subject"]},
    )
    monkeypatch.setattr(
        stage_suite,
        "validate_w2_submission_result",
        lambda _status, body, _headers, **_kwargs: body,
    )
    monkeypatch.setattr(
        stage_suite,
        "validate_persist_only_diff",
        lambda *_args, **_kwargs: {"diff": "accepted"},
    )
    monkeypatch.setattr(
        stage_suite, "_planning_depth_write_window_ms", lambda _ctx: 300000
    )

    def validate_rate(*_args, expected_operator_key, **_kwargs):
        assert expected_operator_key == (
            "bff-water-planning:rate:planning_depth.submit:"
            + hashlib.sha256(subject.encode("utf-8")).hexdigest()
        )
        events.append("rate-key-bound")
        return {"operator_rate_key": expected_operator_key, "increment": 2}

    monkeypatch.setattr(
        stage_suite,
        "validate_persist_only_rate_accounting",
        validate_rate,
    )

    manifest = stage_suite._persist_only_body(
        context,
        client,
        "operator-token",
        {"login": "accepted"},
    )

    assert client.calls[0] == (
        "GET",
        "http://127.0.0.1:3021/api/v1/auth/principal",
        None,
    )
    assert client.bearers[0] == "operator-token"
    assert manifest["steps"]["operator_principal"] == {"subject": subject}
    assert events == ["principal-verified", "rate-key-bound"]


def test_planning_depth_write_window_ms_reads_runtime_configuration(tmp_path):
    context = _write_ui_context(tmp_path)
    (context.runtime_env_dir / "bff.env").write_text(
        "PLANNING_DEPTH_WRITE_WINDOW_SECONDS=45\n"
    )

    assert stage_suite._planning_depth_write_window_ms(context) == 45000


@pytest.mark.parametrize("configured_value", ("0", "-1", "not-an-integer"))
def test_planning_depth_write_window_ms_rejects_invalid_configuration(
    tmp_path, configured_value
):
    context = _write_ui_context(tmp_path)
    (context.runtime_env_dir / "bff.env").write_text(
        f"PLANNING_DEPTH_WRITE_WINDOW_SECONDS={configured_value}\n"
    )

    with pytest.raises(
        stage_suite.StageGateError, match="planning_depth_write_window_invalid"
    ):
        stage_suite._planning_depth_write_window_ms(context)


def test_rate_accounting_rejects_two_changed_keys():
    before = {_OP_KEY: {"value": 5, "ttl_ms": 60000}}
    after = {
        _OP_KEY: {"value": 7, "ttl_ms": 60000},
        _OTHER_OP_KEY: {"value": 2, "ttl_ms": 60000},
    }

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_rate_side_effect_detected"
    ):
        stage_suite.validate_persist_only_rate_accounting(before, after)


def test_rate_accounting_rejects_wrong_increment():
    before = {_OP_KEY: {"value": 5, "ttl_ms": 60000}}
    after = {_OP_KEY: {"value": 8, "ttl_ms": 60000}}

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_rate_side_effect_detected"
    ):
        stage_suite.validate_persist_only_rate_accounting(before, after)


def test_rate_accounting_rejects_malformed_namespace_key():
    after = {
        "bff-water-planning:rate:planning_depth.submit:notahex": {
            "value": 2,
            "ttl_ms": 60000,
        }
    }

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_rate_side_effect_detected"
    ):
        stage_suite.validate_persist_only_rate_accounting({}, after)


def test_rate_accounting_rejects_persistent_key_that_vanished():
    before = {
        _OP_KEY: {"value": 5, "ttl_ms": 60000},
        _OTHER_OP_KEY: {"value": 3, "ttl_ms": -1},  # persistent, no expiry
    }
    after = {_OP_KEY: {"value": 7, "ttl_ms": 60000}}

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_rate_side_effect_detected"
    ):
        stage_suite.validate_persist_only_rate_accounting(before, after)


def test_snapshot_rate_keys_rejects_non_loopback_redis(monkeypatch, tmp_path):
    (tmp_path / "bff.env").write_text("REDIS_URL=redis://10.0.0.5:6379/2\n")
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "evidence",
        runtime_env_dir=tmp_path,
    )

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_rate_url_invalid"
    ):
        stage_suite._snapshot_planning_depth_rate_keys(context)


def test_snapshot_rate_keys_selects_db_and_hides_password(monkeypatch, tmp_path):
    (tmp_path / "bff.env").write_text("REDIS_URL=redis://:s3cret@127.0.0.1:6379/2\n")
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "evidence",
        runtime_env_dir=tmp_path,
    )
    captured = {}

    def fake_run_checked(code, argv, *, env=None, timeout=None, **kwargs):
        captured["argv"] = argv
        captured["env"] = env
        return ""

    monkeypatch.setattr(stage_suite, "_run_checked", fake_run_checked)

    result = stage_suite._snapshot_planning_depth_rate_keys(context)

    assert result == {}
    argv = captured["argv"]
    # db 2 selected explicitly; the password never appears on the argv
    assert argv[argv.index("-n") + 1] == "2"
    assert "s3cret" not in " ".join(argv)
    assert captured["env"]["REDISCLI_AUTH"] == "s3cret"


# --- R1: clean-target-week precheck (re-runnability, no opaque replay failure) ---


def test_assert_persist_target_week_clean_passes_when_scope_empty():
    before = {
        "w2_submissions": [
            _persist_submission_row(
                PERSIST_CREATE_ID,
                csid="c1",
                request_sha256="a" * 64,
                supersedes=None,
                expanded="1" * 64,
            )
        ]
    }
    # the existing row is 2027-R02; a DIFFERENT target week is clean
    result = stage_suite.assert_persist_target_week_clean(before, "2027-R09")
    assert result["clean"] is True


def test_assert_persist_target_week_clean_rejects_existing_root_in_scope():
    before = {
        "w2_submissions": [
            _persist_submission_row(
                PERSIST_CREATE_ID,
                csid="c1",
                request_sha256="a" * 64,
                supersedes=None,
                expanded="1" * 64,
            )
        ]
    }
    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_target_week_not_clean"
    ):
        stage_suite.assert_persist_target_week_clean(before, PERSIST_TARGET_WEEK_KEY)


# --- R1: logout runs in the outer boundary on every post-login path ---


class _StubResponse:
    def __init__(self, status):
        self.status = status
        self.body = {}
        self.headers = {}


class _RecordingLogoutClient:
    def __init__(self, *, status=200, raises=False):
        self._status = status
        self._raises = raises
        self.logout_calls = []

    def request(self, method, url, *, payload=None, bearer=None):
        if url.endswith("/auth/logout"):
            self.logout_calls.append(payload)
            if self._raises:
                raise RuntimeError("network down")
            return _StubResponse(self._status)
        raise AssertionError(f"unexpected request to {url}")


def test_persist_only_logout_best_effort_swallows_errors():
    client = _RecordingLogoutClient(raises=True)
    # must NOT raise on the failure path, so a primary error is never masked
    stage_suite._persist_only_logout(client, "rc", strict=False)
    assert client.logout_calls == [{"refreshToken": "rc"}]


def test_operator_logout_best_effort_swallows_interrupt_class_cleanup_errors():
    class InterruptingLogoutClient:
        def request(self, *_args, **_kwargs):
            raise KeyboardInterrupt

    stage_suite._operator_logout(
        InterruptingLogoutClient(),
        "rc",
        strict=False,
        error_code="write_ui_operator_logout_failed",
    )


def test_persist_only_logout_strict_raises_on_bad_status():
    client = _RecordingLogoutClient(status=500)
    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_operator_logout_failed"
    ):
        stage_suite._persist_only_logout(client, "rc", strict=True)


def test_persist_only_logout_strict_raises_on_exception():
    client = _RecordingLogoutClient(raises=True)
    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_operator_logout_failed"
    ):
        stage_suite._persist_only_logout(client, "rc", strict=True)


def _patch_persist_only_scaffold(monkeypatch, client):
    monkeypatch.setattr(
        stage_suite,
        "_load_state",
        lambda ctx: {"completed": list(stage_suite.STAGE_ORDER[:8])},
    )
    monkeypatch.setattr(stage_suite, "validate_stage_transition", lambda *a, **k: None)
    monkeypatch.setattr(stage_suite, "_load_harness_module", lambda *a, **k: object())
    monkeypatch.setattr(stage_suite, "LocalHttpClient", lambda: client)
    monkeypatch.setattr(
        stage_suite,
        "_login_operator",
        lambda ctx, c, v: ("tok", "refresh-cookie", {"login": "ok"}),
    )


def _persist_only_context(tmp_path):
    return stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "evidence",
        runtime_env_dir=tmp_path,
    )


def test_run_persist_only_logs_out_when_body_fails(monkeypatch, tmp_path):
    client = _RecordingLogoutClient(status=200)
    _patch_persist_only_scaffold(monkeypatch, client)
    cleanup = []

    def failing_body(ctx, c, token, evidence):
        raise stage_suite.StageGateError("injected_body_failure")

    monkeypatch.setattr(stage_suite, "_persist_only_body", failing_body)
    monkeypatch.setattr(
        stage_suite,
        "_assert_operator_refresh_reuse_rejected",
        lambda _client, refresh: cleanup.append(("reuse", refresh))
        or {"refresh_reuse_status": 401, "revoked": True},
    )

    with pytest.raises(stage_suite.StageGateError, match="injected_body_failure"):
        stage_suite.run_local_persist_only(_persist_only_context(tmp_path))

    # the primary error propagated AND the session was still torn down once
    assert client.logout_calls == [{"refreshToken": "refresh-cookie"}]
    assert cleanup == [("reuse", "refresh-cookie")]


def test_run_persist_only_cleans_accepted_initial_login_failure(monkeypatch, tmp_path):
    cleanup = []

    class AcceptedLoginClient:
        def refresh_cookie(self):
            return "accepted-persist-refresh-token"

    monkeypatch.setattr(
        stage_suite,
        "_load_state",
        lambda _context: {"completed": list(stage_suite.STAGE_ORDER[:8])},
    )
    monkeypatch.setattr(stage_suite, "validate_stage_transition", lambda *_args: None)
    monkeypatch.setattr(stage_suite, "_load_harness_module", lambda *_args: object())
    monkeypatch.setattr(stage_suite, "LocalHttpClient", AcceptedLoginClient)
    monkeypatch.setattr(
        stage_suite,
        "_login_operator",
        lambda *_args: (_ for _ in ()).throw(
            stage_suite.StageGateError("operator_login_not_accepted")
        ),
    )
    monkeypatch.setattr(
        stage_suite,
        "_persist_only_logout",
        lambda _client, refresh, *, strict: cleanup.append((refresh, strict)),
    )
    monkeypatch.setattr(
        stage_suite,
        "_assert_operator_refresh_reuse_rejected",
        lambda _client, refresh: cleanup.append(("reuse", refresh))
        or {"refresh_reuse_status": 401, "revoked": True},
    )
    monkeypatch.setattr(
        stage_suite,
        "_persist_only_body",
        lambda *_args: pytest.fail("persist body after failed login"),
    )

    with pytest.raises(stage_suite.StageGateError, match="operator_login_not_accepted"):
        stage_suite.run_local_persist_only(_persist_only_context(tmp_path))

    assert cleanup == [
        ("accepted-persist-refresh-token", False),
        ("reuse", "accepted-persist-refresh-token"),
    ]


@pytest.mark.parametrize("failure_point", ("accepted_login", "post_login"))
def test_run_persist_only_rejects_unproved_initial_session_cleanup(
    monkeypatch, tmp_path, failure_point
):
    context = _persist_only_context(tmp_path)
    cleanup = []
    primary = stage_suite.StageGateError(f"injected_{failure_point}_failure")

    class AcceptedLoginClient:
        def refresh_cookie(self):
            return "accepted-persist-refresh-token"

    client = AcceptedLoginClient()
    _patch_persist_only_scaffold(monkeypatch, client)
    if failure_point == "accepted_login":
        monkeypatch.setattr(
            stage_suite,
            "_login_operator",
            lambda *_args: (_ for _ in ()).throw(primary),
        )
    monkeypatch.setattr(
        stage_suite,
        "_persist_only_body",
        lambda *_args: (_ for _ in ()).throw(primary),
    )
    monkeypatch.setattr(
        stage_suite,
        "_persist_only_logout",
        lambda _client, refresh, *, strict: cleanup.append(("logout", refresh, strict))
        or False,
    )

    def reject_reuse(_client, refresh):
        cleanup.append(("reuse", refresh))
        raise stage_suite.StageGateError("operator_refresh_reuse_not_rejected")

    monkeypatch.setattr(
        stage_suite,
        "_assert_operator_refresh_reuse_rejected",
        reject_reuse,
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="persist_only_initial_operator_cleanup_unproved",
    ) as exc_info:
        stage_suite.run_local_persist_only(context)

    assert exc_info.value.__cause__ is primary
    assert [call[0] for call in cleanup] == ["logout", "reuse"]


def test_run_write_ui_logs_out_when_post_login_body_fails(monkeypatch, tmp_path):
    class FailingWriteUiClient(_RecordingLogoutClient):
        def request(self, method, url, *, payload=None, bearer=None):
            if url.endswith("/auth/logout"):
                return super().request(method, url, payload=payload, bearer=bearer)
            raise stage_suite.StageGateError("injected_post_login_failure")

    client = FailingWriteUiClient(status=200)
    context = stage_suite.StageContext(
        release_sha="8" * 40,
        frontend_sha="9" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=tmp_path / "harness",
        evidence_root=tmp_path / "evidence",
        runtime_env_dir=tmp_path / "runtime",
        as_of_date=stage_suite.date(2026, 8, 9),
    )
    monkeypatch.setattr(
        stage_suite,
        "_load_state",
        lambda _context: {"completed": list(stage_suite.STAGE_ORDER[:7])},
    )
    monkeypatch.setattr(stage_suite, "validate_stage_transition", lambda *a: None)
    monkeypatch.setattr(stage_suite, "_verify_frontend_source", lambda _context: None)
    monkeypatch.setattr(stage_suite, "_load_harness_module", lambda *a: object())
    monkeypatch.setattr(stage_suite, "LocalHttpClient", lambda: client)
    monkeypatch.setattr(
        stage_suite,
        "_login_operator",
        lambda *a: ("token", "refresh-cookie", {"login": "ok"}),
    )
    monkeypatch.setattr(
        stage_suite,
        "_load_env_file",
        lambda _path: {"PLANNING_DEPTH_WRITES_ENABLED": "false"},
    )

    with pytest.raises(stage_suite.StageGateError, match="injected_post_login_failure"):
        stage_suite.run_local_write_ui(context)

    assert client.logout_calls == [{"refreshToken": "refresh-cookie"}]


def test_run_persist_only_fails_when_success_logout_rejected(monkeypatch, tmp_path):
    client = _RecordingLogoutClient(status=500)
    _patch_persist_only_scaffold(monkeypatch, client)
    monkeypatch.setattr(
        stage_suite,
        "_persist_only_body",
        lambda ctx, c, token, evidence: {"stage": "LOCAL-PERSIST-ONLY-1"},
    )

    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_operator_logout_failed"
    ):
        stage_suite.run_local_persist_only(_persist_only_context(tmp_path))


# --- R1: distinct RID week for persist-only ---


def test_persist_only_rid_week_is_the_write_ui_successor_week():
    # persist-only must target a DIFFERENT RID week than write-ui so its
    # active=None create is a fresh root (root-per-scope is per project+calendar+week).
    as_of = date(2026, 11, 2)  # write-ui: 2027-R01
    assert stage_suite._write_ui_rid_week(as_of)[1] == "2027-R01"
    persist_date, persist_key = stage_suite._persist_only_rid_week(as_of)
    assert persist_key == "2027-R02"
    # week_date is the canonical span start of the persist week
    year_start = date(2026, 11, 1)
    assert persist_date == (year_start + timedelta(days=7)).isoformat()


def test_persist_only_rid_week_differs_from_write_ui_for_every_supported_day():
    # Property: across a wide date range, persist week != write-ui week, is 1..53,
    # keeps the same ending-year, and week_date is the canonical span start.
    day = date(1902, 1, 1)
    end = date(2400, 12, 31)
    step = timedelta(days=17)
    while day <= end:
        w_date, w_key = stage_suite._write_ui_rid_week(day)
        p_date, p_key = stage_suite._persist_only_rid_week(day)
        assert p_key != w_key, day
        assert p_key[:4] == w_key[:4], day  # same ending-year
        p_n = int(p_key[6:])
        assert 1 <= p_n <= 53, (day, p_key)
        # canonical span-start check
        ending_year = int(p_key[:4])
        year_start = date(ending_year - 1, 11, 1)
        assert p_date == (year_start + timedelta(days=7 * (p_n - 1))).isoformat()
        day += step


def test_persist_only_rid_week_r53_maps_to_r52():
    # For a write-ui week 53, the successor would overflow the year -> use R52.
    as_of = date(2026, 10, 31)  # write-ui final week of RID year 2026
    _, w_key = stage_suite._write_ui_rid_week(as_of)
    assert w_key == "2026-R53"
    _, p_key = stage_suite._persist_only_rid_week(as_of)
    assert p_key == "2026-R52"


def test_persist_only_rid_week_rejects_out_of_supported_range():
    # ending-year outside 1901..2401 must be rejected, not silently produced.
    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_week_out_of_supported_range"
    ):
        stage_suite._persist_only_rid_week(date(1900, 10, 31))  # ending_year 1900
    with pytest.raises(
        stage_suite.StageGateError, match="persist_only_week_out_of_supported_range"
    ):
        stage_suite._persist_only_rid_week(date(2401, 11, 1))  # ending_year 2402


def _rc_context(tmp_path):
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    runtime_env_dir = tmp_path / "runtime"
    runtime_env_dir.mkdir()
    harness_root = tmp_path / "harness"
    harness_root.mkdir()
    for name in stage_suite.HARNESS_ARTIFACTS:
        (harness_root / name).write_text(f"fixture:{name}\n", encoding="utf-8")
    owner_path = tmp_path / "owner.json"
    owner_path.write_text(
        json.dumps(
            {
                "architecture": "arm64",
                "dependency_sha256": "c" * 64,
                "frontend_sha": "b" * 40,
                "machine": "munbon-control-plan-local",
                "release_sha": "a" * 40,
                "state": "ready",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return stage_suite.StageContext(
        release_sha="a" * 40,
        frontend_sha="b" * 40,
        repo_root=tmp_path / "repo",
        frontend_root=tmp_path / "frontend",
        harness_root=harness_root,
        evidence_root=evidence_root,
        runtime_env_dir=runtime_env_dir,
        as_of_date=date(2026, 11, 2),
        owner_path=owner_path,
    )


def _rc_preflight_checks():
    return {
        "evidence_root_empty": True,
        "database_clean": True,
        "rate_state_clean": True,
        "actionable_commands": 0,
        "sources_clean": True,
        "runtime_dark": True,
    }


def _rc_stage_attempt(*, as_of_date="2026-11-02"):
    preflight = {
        "schema_version": 1,
        "phase": "preflight",
        "verdict": "PASS",
        "release_sha": "a" * 40,
        "frontend_sha": "b" * 40,
        "dependency_sha256": "c" * 64,
        "guest": {
            "name": "munbon-control-plan-local",
            "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
            "architecture": "arm64",
            "machine_id": "f" * 32,
        },
        "as_of_date": "2026-11-02",
        "checks": _rc_preflight_checks(),
        "captured_at": "2026-11-02T01:02:03Z",
    }
    preflight_bytes = (json.dumps(preflight, indent=2, sort_keys=True) + "\n").encode()
    return {
        "preflight_sha256": hashlib.sha256(preflight_bytes).hexdigest(),
        "dependency_sha256": "c" * 64,
        "guest": preflight["guest"],
        "as_of_date": as_of_date,
    }


@pytest.mark.parametrize("clean_result", ["t\n", "true\n"])
def test_rc_database_preflight_accepts_absent_application_schemas(
    monkeypatch, tmp_path, clean_result
):
    context = _rc_context(tmp_path)
    captured = {}

    def psql(_context, query):
        captured["query"] = query
        return clean_result

    monkeypatch.setattr(stage_suite, "_psql", psql)

    assert stage_suite._rc_database_clean(context) is True
    assert all(
        f"to_regnamespace('{schema}') IS NULL" in captured["query"]
        for schema in ("scheduler", "ros_gis", "water_planning", "gis")
    )


@pytest.mark.parametrize("dirty_result", ["f\n", "false\n", "true\ntrue\n", ""])
def test_rc_database_preflight_rejects_present_or_unproven_application_schemas(
    monkeypatch, tmp_path, dirty_result
):
    context = _rc_context(tmp_path)
    monkeypatch.setattr(stage_suite, "_psql", lambda *_args: dirty_result)

    with pytest.raises(stage_suite.StageGateError, match="rc_database_not_clean"):
        stage_suite._rc_database_clean(context)


def test_rc_database_preflight_normalizes_probe_failure(monkeypatch, tmp_path):
    context = _rc_context(tmp_path)

    def fail_probe(*_args):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(stage_suite, "_psql", fail_probe)

    with pytest.raises(stage_suite.StageGateError, match="rc_database_not_clean"):
        stage_suite._rc_database_clean(context)


def test_rc_preflight_snapshot_proves_clean_sources_data_rate_runtime_and_listeners(
    monkeypatch, tmp_path
):
    context = _rc_context(tmp_path)
    events = []
    monkeypatch.setattr(
        stage_suite,
        "_verify_source_checkouts",
        lambda _context: events.append("sources"),
    )
    monkeypatch.setattr(
        stage_suite,
        "_rc_database_clean",
        lambda _context: events.append("database") or True,
        raising=False,
    )
    monkeypatch.setattr(
        stage_suite,
        "_snapshot_planning_depth_rate_keys",
        lambda _context: events.append("rate") or {},
    )
    monkeypatch.setattr(stage_suite, "_pm2_json", lambda: "[]")
    monkeypatch.setattr(
        stage_suite,
        "_listener_snapshot",
        lambda: [{"address": "127.0.0.1", "port": 3005}],
    )
    monkeypatch.setattr(
        stage_suite,
        "_rc_configured_dark",
        lambda _context: events.append("dark") or True,
        raising=False,
    )

    assert stage_suite._rc_preflight_snapshot(context) == _rc_preflight_checks()
    assert events == ["sources", "database", "rate", "dark"]


def _create_bootstrap_runtime_venv_links(repo_root, *, scheduler_target=".venv"):
    for service, target in (
        ("flow-monitoring", ".venv"),
        ("scheduler", scheduler_target),
    ):
        service_root = repo_root / "services" / service
        (service_root / ".venv").mkdir(parents=True)
        (service_root / "venv").symlink_to(target)


def _source_identity_runner(context, backend_status, frontend_status=""):
    def checked(code, argv, **_kwargs):
        if code.endswith("_source_identity"):
            return (
                context.release_sha
                if code.startswith("backend")
                else context.frontend_sha
            )
        if code == "backend_tracked_identity":
            return backend_status
        if code == "frontend_tracked_identity":
            return frontend_status
        raise AssertionError((code, argv))

    return checked


def test_rc_source_preflight_accepts_only_exact_bootstrap_runtime_venv_links(
    monkeypatch, tmp_path
):
    context = _rc_context(tmp_path)
    _create_bootstrap_runtime_venv_links(context.repo_root)
    backend_status = "?? services/flow-monitoring/venv\0" "?? services/scheduler/venv\0"
    status_argv = []

    def checked(code, argv, **kwargs):
        if code.endswith("_tracked_identity"):
            status_argv.append(argv)
        return _source_identity_runner(context, backend_status)(code, argv, **kwargs)

    monkeypatch.setattr(stage_suite, "_run_checked", checked)

    assert stage_suite._verify_source_checkouts(context) is None
    assert status_argv == [
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
    ]


def test_rc_source_preflight_accepts_clean_status_with_exact_runtime_venv_links(
    monkeypatch, tmp_path
):
    context = _rc_context(tmp_path)
    _create_bootstrap_runtime_venv_links(context.repo_root)
    monkeypatch.setattr(
        stage_suite,
        "_run_checked",
        _source_identity_runner(context, ""),
    )

    assert stage_suite._verify_source_checkouts(context) is None


@pytest.mark.parametrize(
    ("backend_status", "scheduler_target"),
    (
        ("?? services/flow-monitoring/venv\0", ".venv"),
        (
            "?? services/flow-monitoring/venv\0"
            "?? services/scheduler/venv\0"
            "?? services/scheduler/src/injected.py\0",
            ".venv",
        ),
        (
            " M services/scheduler/src/main.py\0"
            "?? services/flow-monitoring/venv\0"
            "?? services/scheduler/venv\0",
            ".venv",
        ),
        (
            "?? services/flow-monitoring/venv\0" "?? services/scheduler/venv\0",
            "../unexpected-venv",
        ),
        (
            "?? services/flow-monitoring/venv\0" "?? services/scheduler/venv",
            ".venv",
        ),
    ),
)
def test_rc_source_preflight_rejects_incomplete_extra_tracked_or_wrong_venv_drift(
    monkeypatch, tmp_path, backend_status, scheduler_target
):
    context = _rc_context(tmp_path)
    _create_bootstrap_runtime_venv_links(
        context.repo_root, scheduler_target=scheduler_target
    )
    monkeypatch.setattr(
        stage_suite,
        "_run_checked",
        _source_identity_runner(context, backend_status),
    )

    with pytest.raises(
        stage_suite.StageGateError, match="backend_source_identity_stale"
    ):
        stage_suite._verify_source_checkouts(context)


def test_rc_source_preflight_rejects_regular_file_at_runtime_venv_link(
    monkeypatch, tmp_path
):
    context = _rc_context(tmp_path)
    _create_bootstrap_runtime_venv_links(context.repo_root)
    scheduler_link = context.repo_root / "services/scheduler/venv"
    scheduler_link.unlink()
    scheduler_link.write_text("not a symlink\n", encoding="utf-8")
    backend_status = "?? services/flow-monitoring/venv\0" "?? services/scheduler/venv\0"
    monkeypatch.setattr(
        stage_suite,
        "_run_checked",
        _source_identity_runner(context, backend_status),
    )

    with pytest.raises(
        stage_suite.StageGateError, match="backend_source_identity_stale"
    ):
        stage_suite._verify_source_checkouts(context)


@pytest.mark.parametrize("replacement", ("missing", "directory"))
def test_rc_source_preflight_rejects_missing_or_directory_venv_link_when_git_is_clean(
    monkeypatch, tmp_path, replacement
):
    context = _rc_context(tmp_path)
    _create_bootstrap_runtime_venv_links(context.repo_root)
    scheduler_link = context.repo_root / "services/scheduler/venv"
    scheduler_link.unlink()
    if replacement == "directory":
        scheduler_link.mkdir()
    monkeypatch.setattr(
        stage_suite,
        "_run_checked",
        _source_identity_runner(context, ""),
    )

    with pytest.raises(
        stage_suite.StageGateError, match="backend_source_identity_stale"
    ):
        stage_suite._verify_source_checkouts(context)


def test_rc_source_preflight_keeps_frontend_exception_free(monkeypatch, tmp_path):
    context = _rc_context(tmp_path)
    _create_bootstrap_runtime_venv_links(context.repo_root)
    _create_bootstrap_runtime_venv_links(context.frontend_root)
    runtime_status = "?? services/flow-monitoring/venv\0" "?? services/scheduler/venv\0"
    monkeypatch.setattr(
        stage_suite,
        "_run_checked",
        _source_identity_runner(
            context,
            runtime_status,
            frontend_status=runtime_status,
        ),
    )

    with pytest.raises(
        stage_suite.StageGateError, match="frontend_source_identity_stale"
    ):
        stage_suite._verify_source_checkouts(context)


def test_rc_source_preflight_rejects_untracked_execution_drift(monkeypatch, tmp_path):
    context = _rc_context(tmp_path)
    status_argv = []

    def checked(code, argv, **_kwargs):
        if code.endswith("_source_identity"):
            return (
                context.release_sha
                if code.startswith("backend")
                else context.frontend_sha
            )
        status_argv.append(argv)
        return "?? services/scheduler/src/injected.py\0"

    monkeypatch.setattr(stage_suite, "_run_checked", checked)

    with pytest.raises(
        stage_suite.StageGateError, match="backend_source_identity_stale"
    ):
        stage_suite._verify_source_checkouts(context)

    assert status_argv == [
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]
    ]


@pytest.mark.parametrize(
    ("dirty", "error"),
    [
        (
            {"rate": {"planning-depth:write:subject": {"value": 1, "ttl_ms": 1}}},
            "rc_rate_state_not_clean",
        ),
        ({"pm2": [{"name": "scheduler"}]}, "rc_runtime_not_clean"),
        (
            {"listeners": [{"address": "0.0.0.0", "port": 3022}]},
            "rc_listener_state_not_clean",
        ),
        ({"dark": False}, "rc_runtime_not_dark"),
    ],
)
def test_rc_preflight_snapshot_fails_closed_on_any_dirty_state(
    monkeypatch, tmp_path, dirty, error
):
    context = _rc_context(tmp_path)
    monkeypatch.setattr(stage_suite, "_verify_source_checkouts", lambda _context: None)
    monkeypatch.setattr(
        stage_suite, "_rc_database_clean", lambda _context: True, raising=False
    )
    monkeypatch.setattr(
        stage_suite,
        "_snapshot_planning_depth_rate_keys",
        lambda _context: dirty.get("rate", {}),
    )
    monkeypatch.setattr(
        stage_suite, "_pm2_json", lambda: json.dumps(dirty.get("pm2", []))
    )
    monkeypatch.setattr(
        stage_suite,
        "_listener_snapshot",
        lambda: dirty.get("listeners", [{"address": "127.0.0.1", "port": 3005}]),
    )
    monkeypatch.setattr(
        stage_suite,
        "_rc_configured_dark",
        lambda _context: dirty.get("dark", True),
        raising=False,
    )

    with pytest.raises(stage_suite.StageGateError, match=error):
        stage_suite._rc_preflight_snapshot(context)


def test_run_local_rc_preflight_writes_external_sanitized_state_only(
    monkeypatch, tmp_path
):
    context = _rc_context(tmp_path)
    monkeypatch.setattr(
        stage_suite,
        "_rc_preflight_snapshot",
        lambda _context: _rc_preflight_checks(),
        raising=False,
    )

    manifest = stage_suite.run_local_rc_preflight(
        context,
        dependency_sha256="c" * 64,
        guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
        expected_machine_id="f" * 32,
    )

    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", manifest.pop("captured_at")
    )
    assert manifest == {
        "schema_version": 1,
        "phase": "preflight",
        "verdict": "PASS",
        "release_sha": "a" * 40,
        "frontend_sha": "b" * 40,
        "dependency_sha256": "c" * 64,
        "guest": {
            "name": "munbon-control-plan-local",
            "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
            "architecture": "arm64",
            "machine_id": "f" * 32,
        },
        "as_of_date": "2026-11-02",
        "checks": _rc_preflight_checks(),
    }
    assert {path.name for path in context.evidence_root.iterdir()} == {
        "RC-PREFLIGHT.json",
        "SHA256SUMS",
        "stage-state.json",
    }
    stored = json.loads(stage_suite._rc_preflight_path(context).read_text())
    stored.pop("captured_at")
    assert stored == manifest
    internal = json.loads((context.evidence_root / "RC-PREFLIGHT.json").read_text())
    internal.pop("captured_at")
    assert internal == manifest
    stage_suite._verify_checksum_entry(context.evidence_root / "RC-PREFLIGHT.json")
    monkeypatch.setattr(stage_suite, "_verify_source_checkouts", lambda _context: None)
    assert stage_suite._load_state(context)["completed"] == []


def test_empty_rc_stage_state_rechecks_sources_before_the_first_stage(
    monkeypatch, tmp_path
):
    context = _rc_context(tmp_path)
    monkeypatch.setattr(
        stage_suite,
        "_rc_preflight_snapshot",
        lambda _context: _rc_preflight_checks(),
    )
    stage_suite.run_local_rc_preflight(
        context,
        dependency_sha256="c" * 64,
        guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
        expected_machine_id="f" * 32,
    )
    source_checks = []
    monkeypatch.setattr(
        stage_suite,
        "_verify_source_checkouts",
        lambda checked_context: source_checks.append(checked_context),
    )

    assert stage_suite._load_state(context)["completed"] == []
    assert source_checks == [context]


def test_run_local_rc_preflight_rejects_existing_evidence_before_probes(
    monkeypatch, tmp_path
):
    context = _rc_context(tmp_path)
    (context.evidence_root / "stale.json").write_text("{}\n")
    monkeypatch.setattr(
        stage_suite,
        "_rc_preflight_snapshot",
        lambda _context: pytest.fail("preflight probes must not run"),
        raising=False,
    )

    with pytest.raises(stage_suite.StageGateError, match="rc_evidence_not_clean"):
        stage_suite.run_local_rc_preflight(
            context,
            dependency_sha256="c" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            expected_machine_id="f" * 32,
        )


def test_bootstrap_runtime_environment_satisfies_rc_dark_contract(tmp_path):
    context = _rc_context(tmp_path)
    bootstrap = MODULE_PATH.with_name("bootstrap-linux.sh").read_text(encoding="utf-8")
    for service in ("flow", "scheduler", "ros", "bff"):
        environment = bootstrap.split(
            f'cat > "${{RUNTIME_ENV_DIR}}/{service}.env" <<EOF\n', 1
        )[1].split("\nEOF", 1)[0]
        (context.runtime_env_dir / f"{service}.env").write_text(
            f"{environment}\n", encoding="utf-8"
        )
    model_source = (
        MODULE_PATH.parents[2]
        / "services/flow-monitoring/data/model-releases/engineering-prior-v5-v1.json"
    )
    model_target = (
        context.repo_root
        / "services/flow-monitoring/data/model-releases/engineering-prior-v5-v1.json"
    )
    model_target.parent.mkdir(parents=True)
    model_target.write_bytes(model_source.read_bytes())

    assert stage_suite._rc_configured_dark(context) is True


def test_rc_configured_dark_reads_the_actual_model_release(monkeypatch, tmp_path):
    context = _rc_context(tmp_path)
    model_release = (
        context.repo_root
        / "services/flow-monitoring/data/model-releases/engineering-prior-v5-v1.json"
    )
    model_release.parent.mkdir(parents=True)
    model_release.write_text('{"commandable": true}\n', encoding="utf-8")
    environments = {
        "flow": {"GATES_API_ENABLED": "false", "ALLOW_MACHINE_COMMANDS": "false"},
        "scheduler": {
            "CONTROL_EXECUTION_MODE": "disabled",
            "CONTROL_READBACK_RECONCILIATION_MODE": "off",
            "ALLOW_MACHINE_COMMANDS": "false",
        },
        "ros": {
            "DAILY_REQUIREMENT_ENABLED": "false",
            "DAILY_REQUIREMENT_STARTUP_CATCHUP_ENABLED": "false",
            "DAILY_REQUIREMENT_SCHEDULE_ENABLED": "false",
            "ALLOW_MACHINE_COMMANDS": "false",
        },
        "bff": {
            "PLANNING_DEPTH_WRITES_ENABLED": "false",
            "ALLOW_MACHINE_COMMANDS": "false",
        },
    }
    monkeypatch.setattr(
        stage_suite,
        "_load_env_file",
        lambda path: environments[path.stem],
    )

    with pytest.raises(stage_suite.StageGateError, match="rc_runtime_not_dark"):
        stage_suite._rc_configured_dark(context)


def test_run_local_rc_preflight_never_overwrites_an_existing_external_record(
    monkeypatch, tmp_path
):
    context = _rc_context(tmp_path)
    preflight_path = stage_suite._rc_preflight_path(context)
    preflight_path.write_text('{"prior": true}\n', encoding="utf-8")
    monkeypatch.setattr(
        stage_suite,
        "_rc_preflight_snapshot",
        lambda _context: _rc_preflight_checks(),
    )

    with pytest.raises(
        stage_suite.StageGateError, match="rc_preflight_artifact_exists"
    ):
        stage_suite.run_local_rc_preflight(
            context,
            dependency_sha256="c" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            expected_machine_id="f" * 32,
        )


def _rc_cli_args(tmp_path, phase):
    return [
        "LOCAL-RC-1",
        "--rc-phase",
        phase,
        "--release-sha",
        "a" * 40,
        "--frontend-sha",
        "b" * 40,
        "--dependency-sha256",
        "c" * 64,
        "--guest-id",
        "01KZSKQ6FY4EVCCY94XGWZ9NDS",
        "--expected-machine-id",
        "f" * 32,
        "--execution-kind",
        "canonical",
        "--repo-root",
        str(tmp_path / "repo"),
        "--frontend-root",
        str(tmp_path / "frontend"),
        "--evidence-root",
        str(tmp_path / "evidence"),
        "--runtime-env-dir",
        str(tmp_path / "runtime"),
        "--as-of-date",
        "2026-11-02",
    ]


def _rc_stage_cli_args(tmp_path, stage="LOCAL-BASE-0"):
    args = _rc_cli_args(tmp_path, "preflight")
    args[0] = stage
    del args[1:3]
    for flag in ("--dependency-sha256", "--guest-id"):
        index = args.index(flag)
        del args[index : index + 2]
    return args


def _install_internal_rc_preflight(context):
    record = _write_rc_preflight_record(context)
    internal_path = context.evidence_root / "RC-PREFLIGHT.json"
    stage_suite.write_stage_manifest(internal_path, record)
    stage_suite._checksum_manifest(internal_path)
    return record


@pytest.fixture
def rc_expected_machine(monkeypatch):
    monkeypatch.setattr(stage_suite, "_actual_machine_id", lambda: "f" * 32)


def test_rc_only_options_are_rejected_for_ordinary_stages(tmp_path):
    args = _rc_cli_args(tmp_path, "preflight")
    args[0] = "LOCAL-BASE-0"

    with pytest.raises(SystemExit):
        stage_suite._parse_args(args)


@pytest.mark.parametrize(
    "state_fault", ("missing", "corrupt", "checksum_missing", "noncanonical")
)
def test_rc_dispatched_stage_rejects_an_unproved_post_stage_state(
    monkeypatch, tmp_path, rc_expected_machine, capsys, state_fault
):
    context = _rc_context(tmp_path)
    _install_internal_rc_preflight(context)
    stage_suite._save_state(context, [])

    def pass_base(stage_context):
        manifest = {
            "stage": "LOCAL-BASE-0",
            "verdict": "PASS",
            "release_sha": stage_context.release_sha,
            "frontend_sha": stage_context.frontend_sha,
        }
        target = stage_context.evidence_root / "LOCAL-BASE-0.json"
        stage_suite.write_stage_manifest(target, manifest)
        stage_suite._checksum_manifest(target)
        state_path = stage_context.evidence_root / "stage-state.json"
        if state_fault == "missing":
            stage_suite._clear_checksum_artifact(
                stage_context.evidence_root, state_path.name
            )
        elif state_fault == "corrupt":
            state_path.write_text("{", encoding="utf-8")
        elif state_fault == "checksum_missing":
            entries = stage_suite._read_checksum_index(
                stage_context.evidence_root / "SHA256SUMS"
            )
            entries.pop(state_path.name)
            stage_suite._write_checksum_index(
                stage_context.evidence_root / "SHA256SUMS", entries
            )
        else:
            stage_suite.write_stage_manifest(
                state_path,
                {
                    **stage_suite._stage_identity(stage_context),
                    "completed": ["LOCAL-RTA-1"],
                },
            )
            stage_suite._checksum_manifest(state_path)
        return manifest

    monkeypatch.setattr(stage_suite, "run_local_base", pass_base)

    assert stage_suite.main(_rc_stage_cli_args(tmp_path)) == (
        stage_suite.FAILURE_MANIFEST_EXIT_CODE
    )
    assert capsys.readouterr().err.splitlines() == [
        "FAIL rc_stage_publication_rollback_failed"
    ]
    assert not (context.evidence_root / "LOCAL-BASE-0.json").exists()
    assert not (context.evidence_root / "LOCAL-BASE-0-failure.json").exists()


@pytest.mark.parametrize("binding_step", ("manifest", "checksum"))
def test_rc_stage_binding_failure_keeps_the_prior_state_and_collectable_failure(
    monkeypatch, tmp_path, rc_expected_machine, binding_step
):
    context = _rc_context(tmp_path)
    _install_internal_rc_preflight(context)
    stage_suite._save_state(context, [])

    def pass_base(stage_context):
        manifest = {
            "stage": "LOCAL-BASE-0",
            "verdict": "PASS",
            "release_sha": stage_context.release_sha,
            "frontend_sha": stage_context.frontend_sha,
        }
        target = stage_context.evidence_root / "LOCAL-BASE-0.json"
        stage_suite.write_stage_manifest(target, manifest)
        stage_suite._checksum_manifest(target)
        stage_suite._save_state(stage_context, ["LOCAL-BASE-0"])
        return manifest

    original_write = stage_suite.write_stage_manifest
    original_checksum = stage_suite._checksum_manifest

    def fail_binding_manifest(path, payload):
        if Path(path).name == "LOCAL-BASE-0.json" and "rc_attempt" in payload:
            raise OSError("injected RC binding manifest failure")
        return original_write(path, payload)

    def fail_binding_checksum(path):
        target = Path(path)
        if target.name == "LOCAL-BASE-0.json":
            payload = json.loads(target.read_text(encoding="utf-8"))
            if "rc_attempt" in payload:
                raise OSError("injected RC binding checksum failure")
        return original_checksum(path)

    monkeypatch.setattr(stage_suite, "run_local_base", pass_base)
    monkeypatch.setattr(
        stage_suite,
        "write_stage_manifest",
        fail_binding_manifest if binding_step == "manifest" else original_write,
    )
    monkeypatch.setattr(
        stage_suite,
        "_checksum_manifest",
        fail_binding_checksum if binding_step == "checksum" else original_checksum,
    )

    args = _rc_stage_cli_args(tmp_path)
    args.extend(["--harness-root", str(context.harness_root)])

    assert stage_suite.main(args) == 1
    state = json.loads((context.evidence_root / "stage-state.json").read_text())
    failure = json.loads(
        (context.evidence_root / "LOCAL-BASE-0-failure.json").read_text()
    )
    assert state["completed"] == []
    assert not (context.evidence_root / "LOCAL-BASE-0.json").exists()
    assert failure["stage"] == "LOCAL-BASE-0"
    assert failure["failed_gate"] == "rc_stage_attempt_identity_mismatch"
    assert failure["rc_attempt"] == _rc_stage_attempt()
    stage_suite._verify_checksum_entry(
        context.evidence_root / "LOCAL-BASE-0-failure.json"
    )


@pytest.mark.parametrize("publication_step", ("state_manifest", "state_checksum"))
def test_rc_stage_state_publication_failure_rolls_back_the_bound_pass(
    monkeypatch, tmp_path, rc_expected_machine, publication_step
):
    context = _rc_context(tmp_path)
    _install_internal_rc_preflight(context)
    stage_suite._save_state(context, [])
    state_path = context.evidence_root / "stage-state.json"
    prior_state = state_path.read_bytes()

    def pass_base(stage_context):
        manifest = {
            "stage": "LOCAL-BASE-0",
            "verdict": "PASS",
            "release_sha": stage_context.release_sha,
            "frontend_sha": stage_context.frontend_sha,
        }
        target = stage_context.evidence_root / "LOCAL-BASE-0.json"
        stage_suite.write_stage_manifest(target, manifest)
        stage_suite._checksum_manifest(target)
        stage_suite._save_state(stage_context, ["LOCAL-BASE-0"])
        return manifest

    original_write = stage_suite.write_stage_manifest
    original_checksum = stage_suite._checksum_manifest

    def fail_advanced_state_write(path, payload):
        if Path(path).name == "stage-state.json" and payload.get("completed") == [
            "LOCAL-BASE-0"
        ]:
            raise OSError("injected advanced state write failure")
        return original_write(path, payload)

    def fail_advanced_state_checksum(path):
        target = Path(path)
        if target.name == "stage-state.json":
            payload = json.loads(target.read_text(encoding="utf-8"))
            if payload.get("completed") == ["LOCAL-BASE-0"]:
                raise OSError("injected advanced state checksum failure")
        return original_checksum(path)

    monkeypatch.setattr(stage_suite, "run_local_base", pass_base)
    monkeypatch.setattr(
        stage_suite,
        "write_stage_manifest",
        (
            fail_advanced_state_write
            if publication_step == "state_manifest"
            else original_write
        ),
    )
    monkeypatch.setattr(
        stage_suite,
        "_checksum_manifest",
        (
            fail_advanced_state_checksum
            if publication_step == "state_checksum"
            else original_checksum
        ),
    )

    args = _rc_stage_cli_args(tmp_path)
    args.extend(["--harness-root", str(context.harness_root)])

    assert stage_suite.main(args) == 1
    assert state_path.read_bytes() == prior_state
    assert not (context.evidence_root / "LOCAL-BASE-0.json").exists()
    failure_path = context.evidence_root / "LOCAL-BASE-0-failure.json"
    failure = json.loads(failure_path.read_text(encoding="utf-8"))
    assert failure["rc_attempt"] == _rc_stage_attempt()
    index = stage_suite._read_checksum_index(context.evidence_root / "SHA256SUMS")
    assert index["stage-state.json"] == stage_suite._hash_file(state_path)
    assert "LOCAL-BASE-0.json" not in index
    assert index[failure_path.name] == stage_suite._hash_file(failure_path)


def test_rc_stage_publication_rollback_failure_returns_exit_70(
    monkeypatch, tmp_path, rc_expected_machine, capsys
):
    context = _rc_context(tmp_path)
    _install_internal_rc_preflight(context)
    stage_suite._save_state(context, [])

    def pass_base(stage_context):
        manifest = {
            "stage": "LOCAL-BASE-0",
            "verdict": "PASS",
            "release_sha": stage_context.release_sha,
            "frontend_sha": stage_context.frontend_sha,
        }
        target = stage_context.evidence_root / "LOCAL-BASE-0.json"
        stage_suite.write_stage_manifest(target, manifest)
        stage_suite._checksum_manifest(target)
        stage_suite._save_state(stage_context, ["LOCAL-BASE-0"])
        return manifest

    original_write = stage_suite.write_stage_manifest
    original_unlink = Path.unlink

    def fail_advanced_state_write(path, payload):
        if Path(path).name == "stage-state.json" and payload.get("completed") == [
            "LOCAL-BASE-0"
        ]:
            raise OSError("injected advanced state write failure")
        return original_write(path, payload)

    def refuse_pass_rollback(path, *args, **kwargs):
        if path.name == "LOCAL-BASE-0.json":
            raise OSError("injected PASS rollback failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(stage_suite, "run_local_base", pass_base)
    monkeypatch.setattr(stage_suite, "write_stage_manifest", fail_advanced_state_write)
    monkeypatch.setattr(Path, "unlink", refuse_pass_rollback)
    args = _rc_stage_cli_args(tmp_path)
    args.extend(["--harness-root", str(context.harness_root)])

    assert stage_suite.main(args) == stage_suite.FAILURE_MANIFEST_EXIT_CODE
    assert capsys.readouterr().err.splitlines() == [
        "FAIL rc_stage_publication_rollback_failed"
    ]
    assert not (context.evidence_root / "LOCAL-BASE-0-failure.json").exists()


@pytest.mark.parametrize("snapshot_failure", ("state_bytes", "checksum_index"))
def test_rc_stage_publication_snapshot_failure_returns_exit_70_without_a_verdict(
    monkeypatch, tmp_path, rc_expected_machine, capsys, snapshot_failure
):
    context = _rc_context(tmp_path)
    _install_internal_rc_preflight(context)
    stage_suite._save_state(context, [])

    def pass_base(stage_context):
        manifest = {
            "stage": "LOCAL-BASE-0",
            "verdict": "PASS",
            "release_sha": stage_context.release_sha,
            "frontend_sha": stage_context.frontend_sha,
        }
        target = stage_context.evidence_root / "LOCAL-BASE-0.json"
        stage_suite.write_stage_manifest(target, manifest)
        stage_suite._checksum_manifest(target)
        stage_suite._save_state(stage_context, ["LOCAL-BASE-0"])
        return manifest

    original_read_bytes = Path.read_bytes
    original_read_index = stage_suite._read_checksum_index

    def fail_state_snapshot(path):
        if (
            path.name == "stage-state.json"
            and (context.evidence_root / "LOCAL-BASE-0.json").exists()
        ):
            raise OSError("injected prior state snapshot failure")
        return original_read_bytes(path)

    def fail_index_snapshot(path):
        if (
            Path(path).name == "SHA256SUMS"
            and (context.evidence_root / "LOCAL-BASE-0.json").exists()
        ):
            raise OSError("injected prior index snapshot failure")
        return original_read_index(path)

    monkeypatch.setattr(stage_suite, "run_local_base", pass_base)
    if snapshot_failure == "state_bytes":
        monkeypatch.setattr(Path, "read_bytes", fail_state_snapshot)
    else:
        monkeypatch.setattr(stage_suite, "_read_checksum_index", fail_index_snapshot)
    args = _rc_stage_cli_args(tmp_path)
    args.extend(["--harness-root", str(context.harness_root)])

    assert stage_suite.main(args) == stage_suite.FAILURE_MANIFEST_EXIT_CODE
    assert capsys.readouterr().err.splitlines() == [
        "FAIL rc_stage_publication_rollback_failed"
    ]
    assert not (context.evidence_root / "LOCAL-BASE-0-failure.json").exists()


@pytest.mark.parametrize("cleanup_failure", ("pass_unlink", "index_repair"))
def test_rc_stage_binding_cleanup_failure_returns_exit_70_without_a_verdict(
    monkeypatch, tmp_path, rc_expected_machine, capsys, cleanup_failure
):
    context = _rc_context(tmp_path)
    _install_internal_rc_preflight(context)
    stage_suite._save_state(context, [])

    def pass_base(stage_context):
        manifest = {
            "stage": "LOCAL-BASE-0",
            "verdict": "PASS",
            "release_sha": stage_context.release_sha,
            "frontend_sha": stage_context.frontend_sha,
        }
        target = stage_context.evidence_root / "LOCAL-BASE-0.json"
        stage_suite.write_stage_manifest(target, manifest)
        stage_suite._checksum_manifest(target)
        stage_suite._save_state(stage_context, ["LOCAL-BASE-0"])
        return manifest

    original_write = stage_suite.write_stage_manifest
    original_unlink = Path.unlink
    original_write_index = stage_suite._write_checksum_index

    def fail_binding_manifest(path, payload):
        if Path(path).name == "LOCAL-BASE-0.json" and "rc_attempt" in payload:
            raise OSError("injected RC binding failure")
        return original_write(path, payload)

    def refuse_pass_unlink(path, *args, **kwargs):
        if path.name == "LOCAL-BASE-0.json":
            raise OSError("injected PASS unlink failure")
        return original_unlink(path, *args, **kwargs)

    def refuse_index_repair(path, entries):
        if "LOCAL-BASE-0.json" not in entries:
            raise OSError("injected checksum-index repair failure")
        return original_write_index(path, entries)

    monkeypatch.setattr(stage_suite, "run_local_base", pass_base)
    monkeypatch.setattr(stage_suite, "write_stage_manifest", fail_binding_manifest)
    if cleanup_failure == "pass_unlink":
        monkeypatch.setattr(Path, "unlink", refuse_pass_unlink)
    else:
        monkeypatch.setattr(stage_suite, "_write_checksum_index", refuse_index_repair)
    args = _rc_stage_cli_args(tmp_path)
    args.extend(["--harness-root", str(context.harness_root)])

    assert stage_suite.main(args) == stage_suite.FAILURE_MANIFEST_EXIT_CODE
    assert capsys.readouterr().err.splitlines() == [
        "FAIL rc_stage_publication_rollback_failed"
    ]
    assert not (context.evidence_root / "LOCAL-BASE-0-failure.json").exists()


@pytest.mark.parametrize(
    ("interrupt_step", "interrupt"),
    (
        ("state_snapshot", KeyboardInterrupt()),
        ("index_snapshot", SystemExit(31)),
        ("state_write", KeyboardInterrupt()),
        ("state_checksum", SystemExit(32)),
    ),
)
def test_rc_stage_publication_interrupt_compensates_and_propagates_exactly(
    monkeypatch, tmp_path, rc_expected_machine, interrupt_step, interrupt
):
    context = _rc_context(tmp_path)
    _install_internal_rc_preflight(context)
    stage_suite._save_state(context, [])
    state_path = context.evidence_root / "stage-state.json"
    prior_state = state_path.read_bytes()

    def pass_base(stage_context):
        manifest = {
            "stage": "LOCAL-BASE-0",
            "verdict": "PASS",
            "release_sha": stage_context.release_sha,
            "frontend_sha": stage_context.frontend_sha,
        }
        target = stage_context.evidence_root / "LOCAL-BASE-0.json"
        stage_suite.write_stage_manifest(target, manifest)
        stage_suite._checksum_manifest(target)
        stage_suite._save_state(stage_context, ["LOCAL-BASE-0"])
        return manifest

    original_read_bytes = Path.read_bytes
    original_read_index = stage_suite._read_checksum_index
    original_write = stage_suite.write_stage_manifest
    original_checksum = stage_suite._checksum_manifest
    injected = [False]

    def maybe_interrupt_state_snapshot(path):
        if (
            not injected[0]
            and interrupt_step == "state_snapshot"
            and path.name == "stage-state.json"
            and (context.evidence_root / "LOCAL-BASE-0.json").exists()
        ):
            injected[0] = True
            raise interrupt
        return original_read_bytes(path)

    def maybe_interrupt_index_snapshot(path):
        if (
            not injected[0]
            and interrupt_step == "index_snapshot"
            and Path(path).name == "SHA256SUMS"
            and (context.evidence_root / "LOCAL-BASE-0.json").exists()
        ):
            injected[0] = True
            raise interrupt
        return original_read_index(path)

    def maybe_interrupt_state_write(path, payload):
        if (
            not injected[0]
            and interrupt_step == "state_write"
            and Path(path).name == "stage-state.json"
            and payload.get("completed") == ["LOCAL-BASE-0"]
        ):
            injected[0] = True
            raise interrupt
        return original_write(path, payload)

    def maybe_interrupt_state_checksum(path):
        if (
            not injected[0]
            and interrupt_step == "state_checksum"
            and Path(path).name == "stage-state.json"
            and json.loads(Path(path).read_text())["completed"] == ["LOCAL-BASE-0"]
        ):
            injected[0] = True
            raise interrupt
        return original_checksum(path)

    monkeypatch.setattr(stage_suite, "run_local_base", pass_base)
    monkeypatch.setattr(Path, "read_bytes", maybe_interrupt_state_snapshot)
    monkeypatch.setattr(
        stage_suite, "_read_checksum_index", maybe_interrupt_index_snapshot
    )
    monkeypatch.setattr(
        stage_suite, "write_stage_manifest", maybe_interrupt_state_write
    )
    monkeypatch.setattr(
        stage_suite, "_checksum_manifest", maybe_interrupt_state_checksum
    )
    args = _rc_stage_cli_args(tmp_path)
    args.extend(["--harness-root", str(context.harness_root)])

    with pytest.raises(BaseException) as caught:
        stage_suite.main(args)

    assert caught.value is interrupt
    assert state_path.read_bytes() == prior_state
    assert not (context.evidence_root / "LOCAL-BASE-0.json").exists()
    assert not (context.evidence_root / "LOCAL-BASE-0-failure.json").exists()


@pytest.mark.parametrize("interrupt", (KeyboardInterrupt(), SystemExit(33)))
def test_rc_stage_compensation_interrupt_remains_authoritative(
    monkeypatch, tmp_path, rc_expected_machine, interrupt
):
    context = _rc_context(tmp_path)
    _install_internal_rc_preflight(context)
    stage_suite._save_state(context, [])

    def pass_base(stage_context):
        manifest = {
            "stage": "LOCAL-BASE-0",
            "verdict": "PASS",
            "release_sha": stage_context.release_sha,
            "frontend_sha": stage_context.frontend_sha,
        }
        target = stage_context.evidence_root / "LOCAL-BASE-0.json"
        stage_suite.write_stage_manifest(target, manifest)
        stage_suite._checksum_manifest(target)
        stage_suite._save_state(stage_context, ["LOCAL-BASE-0"])
        return manifest

    original_write = stage_suite.write_stage_manifest
    original_unlink = Path.unlink
    interrupted = [False]

    def fail_advanced_state_write(path, payload):
        if Path(path).name == "stage-state.json" and payload.get("completed") == [
            "LOCAL-BASE-0"
        ]:
            raise OSError("injected state publication failure")
        return original_write(path, payload)

    def interrupt_compensation(path, *args, **kwargs):
        if not interrupted[0] and path.name == "LOCAL-BASE-0.json":
            interrupted[0] = True
            raise interrupt
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(stage_suite, "run_local_base", pass_base)
    monkeypatch.setattr(stage_suite, "write_stage_manifest", fail_advanced_state_write)
    monkeypatch.setattr(Path, "unlink", interrupt_compensation)
    args = _rc_stage_cli_args(tmp_path)
    args.extend(["--harness-root", str(context.harness_root)])

    with pytest.raises(BaseException) as caught:
        stage_suite.main(args)

    assert caught.value is interrupt
    assert not (context.evidence_root / "LOCAL-BASE-0-failure.json").exists()


def test_rc_dispatched_stage_failure_binds_the_exact_preflight_attempt(
    monkeypatch, tmp_path, rc_expected_machine
):
    context = _rc_context(tmp_path)
    _install_internal_rc_preflight(context)
    monkeypatch.setattr(
        stage_suite,
        "run_local_base",
        lambda _context: (_ for _ in ()).throw(
            stage_suite.StageGateError("base_probe_failed")
        ),
    )

    assert stage_suite.main(_rc_stage_cli_args(tmp_path)) == 1
    failure = json.loads(
        (context.evidence_root / "LOCAL-BASE-0-failure.json").read_text()
    )
    assert failure["rc_attempt"] == _rc_stage_attempt()
    stage_suite._verify_checksum_entry(
        context.evidence_root / "LOCAL-BASE-0-failure.json"
    )


def test_rc_dispatched_stage_rejects_date_drift_before_dispatch(
    monkeypatch, tmp_path, rc_expected_machine
):
    context = _rc_context(tmp_path)
    _install_internal_rc_preflight(context)
    monkeypatch.setattr(
        stage_suite,
        "run_local_base",
        lambda _context: pytest.fail("date drift must block stage dispatch"),
    )
    args = _rc_stage_cli_args(tmp_path)
    args[args.index("--as-of-date") + 1] = "2026-11-03"

    assert stage_suite.main(args) == 1
    failure = json.loads(
        (context.evidence_root / "LOCAL-BASE-0-failure.json").read_text()
    )
    assert failure["failed_gate"] == "rc_stage_attempt_identity_mismatch"
    assert failure["rc_attempt"] == _rc_stage_attempt(as_of_date="2026-11-03")


def test_rc_guest_parser_and_main_dispatch_preflight_without_changing_stage_order(
    monkeypatch, tmp_path, rc_expected_machine
):
    (tmp_path / "evidence").mkdir()
    captured = []
    monkeypatch.setattr(
        stage_suite,
        "run_local_rc_preflight",
        lambda context, **kwargs: captured.append((context, kwargs)),
        raising=False,
    )

    assert stage_suite.STAGE_ORDER[-1] == "LOCAL-WRITE-ACT-1"
    assert "LOCAL-RC-1" not in stage_suite.STAGE_ORDER
    assert stage_suite.main(_rc_cli_args(tmp_path, "preflight")) == 0
    assert len(captured) == 1
    assert captured[0][1] == {
        "dependency_sha256": "c" * 64,
        "guest_id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
        "expected_machine_id": "f" * 32,
    }


def test_rc_guest_rejects_machine_replacement_before_dispatch_or_evidence(
    monkeypatch, tmp_path
):
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    monkeypatch.setattr(
        stage_suite,
        "_actual_machine_id",
        lambda: "e" * 32,
        raising=False,
    )
    monkeypatch.setattr(
        stage_suite,
        "run_local_rc_preflight",
        lambda *_args, **_kwargs: pytest.fail("replacement must not dispatch"),
    )

    with pytest.raises(
        stage_suite.StageGateError,
        match="rc_guest_machine_identity_mismatch",
    ):
        stage_suite.main(_rc_cli_args(tmp_path, "preflight"))

    assert list(evidence_root.iterdir()) == []


def test_rc_preflight_failure_is_checksummed_without_fabricating_stage_state(
    monkeypatch, tmp_path, rc_expected_machine
):
    context = _rc_context(tmp_path)
    evidence_root = context.evidence_root
    monkeypatch.setattr(
        stage_suite,
        "run_local_rc_preflight",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            stage_suite.StageGateError("rc_database_not_clean")
        ),
        raising=False,
    )

    args = _rc_cli_args(tmp_path, "preflight")
    args.extend(["--harness-root", str(context.harness_root)])

    assert stage_suite.main(args) == 1
    failure = json.loads((evidence_root / "LOCAL-RC-1-failure.json").read_text())
    assert failure == {
        "stage": "LOCAL-RC-1",
        "rc_phase": "preflight",
        "verdict": "FAIL",
        "release_sha": "a" * 40,
        "frontend_sha": "b" * 40,
        "dependency_sha256": "c" * 64,
        "guest": {
            "name": "munbon-control-plan-local",
            "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
            "architecture": "arm64",
            "machine_id": "f" * 32,
        },
        "harness_hashes": {
            name: hashlib.sha256((context.harness_root / name).read_bytes()).hexdigest()
            for name in stage_suite.HARNESS_ARTIFACTS
        },
        "as_of_date": "2026-11-02",
        "failed_gate": "rc_database_not_clean",
        "failed_at": failure["failed_at"],
    }
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", failure["failed_at"])
    assert not (evidence_root / "stage-state.json").exists()
    stage_suite._verify_checksum_entry(evidence_root / "LOCAL-RC-1-failure.json")


@pytest.mark.parametrize(
    "cleanup_artifact", ("RC-PREFLIGHT.json", "stage-state.json", "SHA256SUMS")
)
def test_rc_preflight_publication_cleanup_failure_returns_exit_70(
    monkeypatch, tmp_path, rc_expected_machine, capsys, cleanup_artifact
):
    context = _rc_context(tmp_path)
    real_preflight = stage_suite.run_local_rc_preflight
    external_path = stage_suite._rc_preflight_path(context)
    original_write = stage_suite.write_stage_manifest
    original_unlink = Path.unlink

    monkeypatch.setattr(
        stage_suite,
        "_rc_preflight_snapshot",
        lambda _context: _rc_preflight_checks(),
    )

    def run_preflight_with_owner(stage_context, **kwargs):
        return real_preflight(
            dataclasses.replace(stage_context, owner_path=context.owner_path), **kwargs
        )

    def fail_external_publication(path, payload):
        if Path(path) == external_path:
            raise OSError("injected external preflight publication failure")
        return original_write(path, payload)

    def refuse_cleanup(path, *args, **kwargs):
        if path.name == cleanup_artifact:
            raise OSError("injected preflight cleanup failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(stage_suite, "run_local_rc_preflight", run_preflight_with_owner)
    monkeypatch.setattr(stage_suite, "write_stage_manifest", fail_external_publication)
    monkeypatch.setattr(Path, "unlink", refuse_cleanup)
    args = _rc_cli_args(tmp_path, "preflight")
    args.extend(["--harness-root", str(context.harness_root)])

    assert stage_suite.main(args) == stage_suite.FAILURE_MANIFEST_EXIT_CODE
    assert capsys.readouterr().err.splitlines() == [
        "FAIL rc_preflight_publication_rollback_failed"
    ]
    assert not (context.evidence_root / "LOCAL-RC-1-failure.json").exists()


@pytest.mark.parametrize("external_cleanup_fails", (False, True))
def test_rc_preflight_post_write_failure_compensates_the_external_record(
    monkeypatch, tmp_path, rc_expected_machine, capsys, external_cleanup_fails
):
    context = _rc_context(tmp_path)
    real_preflight = stage_suite.run_local_rc_preflight
    external_path = stage_suite._rc_preflight_path(context)
    original_write = stage_suite.write_stage_manifest
    original_unlink = Path.unlink

    monkeypatch.setattr(
        stage_suite,
        "_rc_preflight_snapshot",
        lambda _context: _rc_preflight_checks(),
    )

    def run_preflight_with_owner(stage_context, **kwargs):
        return real_preflight(
            dataclasses.replace(stage_context, owner_path=context.owner_path), **kwargs
        )

    def fail_after_external_write(path, payload):
        result = original_write(path, payload)
        if Path(path) == external_path:
            raise OSError("injected post-write external publication failure")
        return result

    def maybe_refuse_external_cleanup(path, *args, **kwargs):
        if external_cleanup_fails and path == external_path:
            raise OSError("injected external preflight cleanup failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(stage_suite, "run_local_rc_preflight", run_preflight_with_owner)
    monkeypatch.setattr(stage_suite, "write_stage_manifest", fail_after_external_write)
    monkeypatch.setattr(Path, "unlink", maybe_refuse_external_cleanup)
    args = _rc_cli_args(tmp_path, "preflight")
    args.extend(["--harness-root", str(context.harness_root)])

    result = stage_suite.main(args)

    if external_cleanup_fails:
        assert result == stage_suite.FAILURE_MANIFEST_EXIT_CODE
        assert capsys.readouterr().err.splitlines() == [
            "FAIL rc_preflight_publication_rollback_failed"
        ]
        assert not (context.evidence_root / "LOCAL-RC-1-failure.json").exists()
        return

    assert result == 1
    assert not external_path.exists()
    assert {path.name for path in context.evidence_root.iterdir()} == {
        "LOCAL-RC-1-failure.json",
        "SHA256SUMS",
    }
    stage_suite._verify_checksum_entry(
        context.evidence_root / "LOCAL-RC-1-failure.json"
    )


def test_rc_preflight_failure_without_complete_harness_identity_returns_exit_70(
    monkeypatch, tmp_path, rc_expected_machine, capsys
):
    context = _rc_context(tmp_path)
    (context.harness_root / stage_suite.HARNESS_ARTIFACTS[0]).unlink()
    monkeypatch.setattr(
        stage_suite,
        "run_local_rc_preflight",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            stage_suite.StageGateError("rc_database_not_clean")
        ),
    )
    args = _rc_cli_args(tmp_path, "preflight")
    args.extend(["--harness-root", str(context.harness_root)])

    assert stage_suite.main(args) == stage_suite.FAILURE_MANIFEST_EXIT_CODE
    assert capsys.readouterr().err.splitlines() == [
        "FAIL rc_preflight_failure_harness_identity_unavailable"
    ]
    assert not (context.evidence_root / "LOCAL-RC-1-failure.json").exists()


def test_rc_preflight_interrupt_propagates_without_any_verdict(
    monkeypatch, tmp_path, rc_expected_machine
):
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    interrupt = KeyboardInterrupt()
    monkeypatch.setattr(
        stage_suite,
        "run_local_rc_preflight",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(interrupt),
        raising=False,
    )

    with pytest.raises(KeyboardInterrupt) as caught:
        stage_suite.main(_rc_cli_args(tmp_path, "preflight"))

    assert caught.value is interrupt
    assert list(evidence_root.iterdir()) == []


def _rc_dark_contract():
    return {
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


def _rc_processes():
    return [
        {
            "name": name,
            "status": "online",
            "restarts": index,
            "pid": 100 + index,
            "memory_bytes": 1024 + index,
            "cpu_percent": index / 10,
        }
        for index, name in enumerate(stage_suite.PROCESS_NAMES)
    ]


def _rc_readiness():
    return {
        name: {"status_code": 200, "status": "ready", "checks": {}}
        for name in stage_suite.PROCESS_NAMES
    }


def _rc_runtime_proof():
    return {
        "verified": True,
        "processes": _rc_processes(),
        "processes_online": sorted(stage_suite.PROCESS_NAMES),
        "listeners": [
            {"address": "127.0.0.1", "port": port} for port in (3011, 3021, 3022, 3047)
        ],
        "dark_contract_after": _rc_dark_contract(),
        "final_activation_gates": {
            "control_plan_reads": False,
            "control_plan_evidence_reads": False,
            "water_planning_v2": False,
            "water_planning_submit": False,
        },
        "readiness": _rc_readiness(),
    }


def _write_rc_guest_state(context):
    snapshot = {
        "non_w2_digests": {"scheduler.control_command_outbox": "0" * 32},
        "w2_submissions": [],
        "w2_values": [],
    }
    manifests = {}
    for stage in stage_suite.STAGE_ORDER:
        steps = {}
        if stage == "LOCAL-PERSIST-ONLY-1":
            steps["operator_principal"] = {"subject": "operator-persist"}
        if stage == "LOCAL-WRITE-ACT-1":
            write_rate_key = stage_suite._planning_depth_rate_key("operator-write")
            steps = {
                "operator_principal": {"subject": "operator-write"},
                "runtime_restoration": _rc_runtime_proof(),
                "persist_snapshot_sha256": stage_suite._canonical_json_sha256(snapshot),
                "rate_state_after_browser": {
                    "configured_window_ms": 300000,
                    "minimum_elapsed_ms": 900000,
                    "snapshot_completed_monotonic_ms": 20100,
                    "snapshot": {
                        write_rate_key: {"value": 3, "ttl_ms": 6000},
                    },
                },
                "active_after_rollback": {
                    "submission_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "levels_count": 41,
                    "zones_covered": [f"01-{zone:02d}" for zone in range(1, 7)],
                },
                "persisted_diff": {
                    "w2_submissions_added": [
                        "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    ]
                },
            }
        manifest = {
            "stage": stage,
            "verdict": "PASS",
            "release_sha": context.release_sha,
            "frontend_sha": context.frontend_sha,
            "completed_at": "2026-11-02T01:02:03Z",
            "rc_attempt": _rc_stage_attempt(),
            "steps": steps,
        }
        path = context.evidence_root / f"{stage}.json"
        stage_suite.write_stage_manifest(path, manifest)
        stage_suite._checksum_manifest(path)
        manifests[stage] = manifest
    stage_suite._save_state(context, list(stage_suite.STAGE_ORDER))
    return manifests, snapshot


def _write_rc_preflight_record(context):
    record = {
        "schema_version": 1,
        "phase": "preflight",
        "verdict": "PASS",
        "release_sha": context.release_sha,
        "frontend_sha": context.frontend_sha,
        "dependency_sha256": "c" * 64,
        "guest": {
            "name": "munbon-control-plan-local",
            "id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
            "architecture": "arm64",
            "machine_id": "f" * 32,
        },
        "as_of_date": "2026-11-02",
        "checks": _rc_preflight_checks(),
        "captured_at": "2026-11-02T01:02:03Z",
    }
    stage_suite.write_stage_manifest(stage_suite._rc_preflight_path(context), record)
    return record


@pytest.mark.parametrize("mutation", ("missing", "date"))
def test_rc_load_stage_manifests_rejects_attempt_lineage_drift(
    monkeypatch, tmp_path, mutation
):
    context = _rc_context(tmp_path)
    _install_internal_rc_preflight(context)
    _write_rc_guest_state(context)
    stage_path = context.evidence_root / "LOCAL-BASE-0.json"
    manifest = json.loads(stage_path.read_text())
    if mutation == "missing":
        manifest.pop("rc_attempt")
    else:
        manifest["rc_attempt"]["as_of_date"] = "2026-11-03"
    stage_suite.write_stage_manifest(stage_path, manifest)
    stage_suite._checksum_manifest(stage_path)
    monkeypatch.setattr(stage_suite, "_verify_source_checkouts", lambda _context: None)

    with pytest.raises(
        stage_suite.StageGateError,
        match="rc_finalize_stage_attempt_invalid",
    ):
        stage_suite._rc_load_stage_manifests(context)


def test_rc_final_snapshot_proves_runtime_history_and_expected_rate_keys(
    monkeypatch, tmp_path
):
    context = _rc_context(tmp_path)
    manifests, snapshot = _write_rc_guest_state(context)
    runtime = _rc_runtime_proof()
    rate_state = {}
    monkeypatch.setattr(
        stage_suite,
        "_verify_write_activation_restoration",
        lambda *_args, **_kwargs: runtime,
    )
    monkeypatch.setattr(
        stage_suite, "_take_persist_snapshot", lambda _context: snapshot
    )
    monkeypatch.setattr(
        stage_suite,
        "_snapshot_planning_depth_rate_keys",
        lambda _context: rate_state,
    )
    monkeypatch.setattr(stage_suite, "_read_json", lambda _path: {"commandable": False})
    monotonic_values = iter((920.0, 921.0))
    monkeypatch.setattr(stage_suite.time, "monotonic", lambda: next(monotonic_values))

    result = stage_suite._rc_final_snapshot(context, manifests)

    assert result == {
        "verdict": "PASS",
        "completed": list(stage_suite.STAGE_ORDER),
        "runtime_dark": True,
        "processes_stable": True,
        "readiness_green": True,
        "listeners_accepted": True,
        "immutable_history": True,
        "proof": {
            "processes": runtime["processes"],
            "dark_contract": runtime["dark_contract_after"],
            "frontend_activation_gates": runtime["final_activation_gates"],
            "readiness": runtime["readiness"],
            "listeners": runtime["listeners"],
            "persist_snapshot_sha256": stage_suite._canonical_json_sha256(snapshot),
            "rate_state": rate_state,
            "rate_minimum_elapsed_ms": 900000,
            "rate_snapshot_started_monotonic_ms": 920000,
            "rate_snapshot_completed_monotonic_ms": 921000,
            "write_activation_manifest_sha256": hashlib.sha256(
                (context.evidence_root / "LOCAL-WRITE-ACT-1.json").read_bytes()
            ).hexdigest(),
        },
    }


def test_rc_final_snapshot_accepts_a_surviving_key_at_the_elapsed_decay_bound(
    monkeypatch, tmp_path
):
    context = _rc_context(tmp_path)
    manifests, snapshot = _write_rc_guest_state(context)
    write_key = stage_suite._planning_depth_rate_key("operator-write")
    reference = manifests["LOCAL-WRITE-ACT-1"]["steps"]["rate_state_after_browser"]
    reference["minimum_elapsed_ms"] = 1000
    reference["snapshot_completed_monotonic_ms"] = 20000
    write_path = context.evidence_root / "LOCAL-WRITE-ACT-1.json"
    stage_suite.write_stage_manifest(write_path, manifests["LOCAL-WRITE-ACT-1"])
    stage_suite._checksum_manifest(write_path)
    monkeypatch.setattr(
        stage_suite,
        "_verify_write_activation_restoration",
        lambda *_args, **_kwargs: _rc_runtime_proof(),
    )
    monkeypatch.setattr(
        stage_suite, "_take_persist_snapshot", lambda _context: snapshot
    )
    monkeypatch.setattr(
        stage_suite,
        "_snapshot_planning_depth_rate_keys",
        lambda _context: {write_key: {"value": 3, "ttl_ms": 5000}},
    )
    monkeypatch.setattr(stage_suite, "_read_json", lambda _path: {"commandable": False})
    monotonic_values = iter((21.0, 22.0))
    monkeypatch.setattr(stage_suite.time, "monotonic", lambda: next(monotonic_values))

    result = stage_suite._rc_final_snapshot(context, manifests)

    assert result["proof"]["rate_state"] == {write_key: {"value": 3, "ttl_ms": 5000}}
    assert result["proof"]["rate_minimum_elapsed_ms"] == 1000
    assert result["proof"]["rate_snapshot_started_monotonic_ms"] == 21000
    assert result["proof"]["rate_snapshot_completed_monotonic_ms"] == 22000


def test_rc_final_snapshot_rejects_ttl_above_the_true_final_elapsed_bound(
    monkeypatch, tmp_path
):
    context = _rc_context(tmp_path)
    manifests, snapshot = _write_rc_guest_state(context)
    write_key = stage_suite._planning_depth_rate_key("operator-write")
    reference = manifests["LOCAL-WRITE-ACT-1"]["steps"]["rate_state_after_browser"]
    reference["minimum_elapsed_ms"] = 1000
    reference["snapshot_completed_monotonic_ms"] = 20000
    write_path = context.evidence_root / "LOCAL-WRITE-ACT-1.json"
    stage_suite.write_stage_manifest(write_path, manifests["LOCAL-WRITE-ACT-1"])
    stage_suite._checksum_manifest(write_path)
    monkeypatch.setattr(
        stage_suite,
        "_verify_write_activation_restoration",
        lambda *_args, **_kwargs: _rc_runtime_proof(),
    )
    monkeypatch.setattr(
        stage_suite, "_take_persist_snapshot", lambda _context: snapshot
    )
    monkeypatch.setattr(
        stage_suite,
        "_snapshot_planning_depth_rate_keys",
        lambda _context: {write_key: {"value": 3, "ttl_ms": 4000}},
    )
    monkeypatch.setattr(stage_suite, "_read_json", lambda _path: {"commandable": False})
    monotonic_values = iter((23.0, 24.0))
    monkeypatch.setattr(stage_suite.time, "monotonic", lambda: next(monotonic_values))

    with pytest.raises(
        stage_suite.StageGateError, match="rc_finalize_rate_state_invalid"
    ):
        stage_suite._rc_final_snapshot(context, manifests)


@pytest.mark.parametrize(
    ("monotonic_values", "accepted"),
    (
        ((21.0, 22.0), False),
        ((25.0, 27.0), False),
        ((26.0, 27.0), True),
        ((27.0, 28.0), True),
    ),
)
def test_rc_final_snapshot_accepts_a_missing_key_only_after_natural_expiry(
    monkeypatch, tmp_path, monotonic_values, accepted
):
    context = _rc_context(tmp_path)
    manifests, snapshot = _write_rc_guest_state(context)
    reference = manifests["LOCAL-WRITE-ACT-1"]["steps"]["rate_state_after_browser"]
    reference["minimum_elapsed_ms"] = 1000
    reference["snapshot_completed_monotonic_ms"] = 20000
    write_path = context.evidence_root / "LOCAL-WRITE-ACT-1.json"
    stage_suite.write_stage_manifest(write_path, manifests["LOCAL-WRITE-ACT-1"])
    stage_suite._checksum_manifest(write_path)
    monkeypatch.setattr(
        stage_suite,
        "_verify_write_activation_restoration",
        lambda *_args, **_kwargs: _rc_runtime_proof(),
    )
    monkeypatch.setattr(
        stage_suite, "_take_persist_snapshot", lambda _context: snapshot
    )
    monkeypatch.setattr(
        stage_suite, "_snapshot_planning_depth_rate_keys", lambda _context: {}
    )
    monkeypatch.setattr(stage_suite, "_read_json", lambda _path: {"commandable": False})
    moments = iter(monotonic_values)
    monkeypatch.setattr(stage_suite.time, "monotonic", lambda: next(moments))

    if not accepted:
        with pytest.raises(
            stage_suite.StageGateError, match="rc_finalize_rate_state_invalid"
        ):
            stage_suite._rc_final_snapshot(context, manifests)
        return

    result = stage_suite._rc_final_snapshot(context, manifests)

    assert result["proof"]["rate_state"] == {}
    assert result["proof"]["rate_snapshot_started_monotonic_ms"] == int(
        monotonic_values[0] * 1000
    )
    assert result["proof"]["rate_snapshot_completed_monotonic_ms"] == int(
        monotonic_values[1] * 1000
    )


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("process", "rc_finalize_process_stability_invalid"),
        ("history", "rc_finalize_immutable_history_invalid"),
        ("rate", "rc_finalize_rate_state_invalid"),
    ],
)
def test_rc_final_snapshot_rejects_runtime_history_or_rate_drift(
    monkeypatch, tmp_path, mutation, error
):
    context = _rc_context(tmp_path)
    manifests, snapshot = _write_rc_guest_state(context)
    runtime = _rc_runtime_proof()
    if mutation == "process":
        runtime["processes"][0]["pid"] += 1
    if mutation == "history":
        snapshot = {**snapshot, "w2_submissions": [{"unexpected": True}]}
    rate_state = {}
    if mutation == "rate":
        rate_state[stage_suite._planning_depth_rate_key("other-operator")] = {
            "value": 1,
            "ttl_ms": 1000,
        }
    monkeypatch.setattr(
        stage_suite,
        "_verify_write_activation_restoration",
        lambda *_args, **_kwargs: runtime,
    )
    monkeypatch.setattr(
        stage_suite, "_take_persist_snapshot", lambda _context: snapshot
    )
    monkeypatch.setattr(
        stage_suite,
        "_snapshot_planning_depth_rate_keys",
        lambda _context: rate_state,
    )
    monkeypatch.setattr(stage_suite, "_read_json", lambda _path: {"commandable": False})
    monkeypatch.setattr(stage_suite.time, "monotonic", lambda: 920.1)

    with pytest.raises(stage_suite.StageGateError, match=error):
        stage_suite._rc_final_snapshot(context, manifests)


@pytest.mark.parametrize(
    "rate_state",
    [
        lambda key: {key: {"value": 4, "ttl_ms": 1000}},
        lambda key: {key: {"value": 3, "ttl_ms": 1}},
        lambda key: {key: {"value": 3, "ttl_ms": 300001}},
    ],
)
def test_rc_final_snapshot_rejects_counter_or_ttl_drift(
    monkeypatch, tmp_path, rate_state
):
    context = _rc_context(tmp_path)
    manifests, snapshot = _write_rc_guest_state(context)
    write_key = stage_suite._planning_depth_rate_key("operator-write")
    monkeypatch.setattr(
        stage_suite,
        "_verify_write_activation_restoration",
        lambda *_args, **_kwargs: _rc_runtime_proof(),
    )
    monkeypatch.setattr(
        stage_suite, "_take_persist_snapshot", lambda _context: snapshot
    )
    monkeypatch.setattr(
        stage_suite,
        "_snapshot_planning_depth_rate_keys",
        lambda _context: rate_state(write_key),
    )
    monkeypatch.setattr(stage_suite, "_read_json", lambda _path: {"commandable": False})
    monkeypatch.setattr(stage_suite.time, "monotonic", lambda: 920.1)

    with pytest.raises(
        stage_suite.StageGateError, match="rc_finalize_rate_state_invalid"
    ):
        stage_suite._rc_final_snapshot(context, manifests)


def test_run_local_rc_finalize_embeds_preflight_and_writes_checksummed_rc_evidence(
    monkeypatch, tmp_path
):
    context = _rc_context(tmp_path)
    manifests, _snapshot = _write_rc_guest_state(context)
    preflight = _write_rc_preflight_record(context)
    final = {
        "verdict": "PASS",
        "completed": list(stage_suite.STAGE_ORDER),
        "runtime_dark": True,
        "processes_stable": True,
        "readiness_green": True,
        "listeners_accepted": True,
        "immutable_history": True,
        "proof": {"bounded": True},
    }
    monkeypatch.setattr(stage_suite, "_verify_source_checkouts", lambda _context: None)
    monkeypatch.setattr(
        stage_suite,
        "_rc_final_snapshot",
        lambda _context, loaded: (
            final if loaded == manifests else pytest.fail("wrong stage manifests")
        ),
        raising=False,
    )

    manifest = stage_suite.run_local_rc_finalize(
        context,
        dependency_sha256="c" * 64,
        guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
        expected_machine_id="f" * 32,
    )

    assert manifest["preflight"] == {
        "verdict": "PASS",
        **_rc_preflight_checks(),
        "record": preflight,
        "record_sha256": hashlib.sha256(
            (json.dumps(preflight, indent=2, sort_keys=True) + "\n").encode()
        ).hexdigest(),
    }
    assert manifest["final"] == final
    summary = json.loads((context.evidence_root / "RC-SUMMARY.json").read_text())
    assert summary["passed"] == [*stage_suite.STAGE_ORDER, "LOCAL-RC-1"]
    assert summary["campaign_ledger_eligible"] is False
    assert summary["aws_actions_authorized"] is False
    stage_suite._verify_checksum_entry(context.evidence_root / "LOCAL-RC-1.json")
    stage_suite._verify_checksum_entry(context.evidence_root / "RC-SUMMARY.json")
    assert not stage_suite._rc_preflight_path(context).exists()


def test_run_local_rc_finalize_rejects_incomplete_stage_state(monkeypatch, tmp_path):
    context = _rc_context(tmp_path)
    _write_rc_preflight_record(context)
    monkeypatch.setattr(stage_suite, "_verify_source_checkouts", lambda _context: None)

    with pytest.raises(
        stage_suite.StageGateError, match="rc_finalize_stage_state_incomplete"
    ):
        stage_suite.run_local_rc_finalize(
            context,
            dependency_sha256="c" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            expected_machine_id="f" * 32,
        )


def test_run_local_rc_finalize_rejects_preflight_identity_drift(monkeypatch, tmp_path):
    context = _rc_context(tmp_path)
    _write_rc_guest_state(context)
    preflight_path = stage_suite._rc_preflight_path(context)
    record = _write_rc_preflight_record(context)
    record["dependency_sha256"] = "d" * 64
    stage_suite.write_stage_manifest(preflight_path, record)
    monkeypatch.setattr(stage_suite, "_verify_source_checkouts", lambda _context: None)

    with pytest.raises(
        stage_suite.StageGateError, match="rc_finalize_preflight_invalid"
    ):
        stage_suite.run_local_rc_finalize(
            context,
            dependency_sha256="c" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            expected_machine_id="f" * 32,
        )


def test_run_local_rc_finalize_rejects_noncanonical_preflight_bytes(
    monkeypatch, tmp_path
):
    context = _rc_context(tmp_path)
    _write_rc_guest_state(context)
    record = _write_rc_preflight_record(context)
    stage_suite._rc_preflight_path(context).write_text(
        json.dumps(record, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stage_suite, "_verify_source_checkouts", lambda _context: None)
    monkeypatch.setattr(
        stage_suite,
        "_rc_final_snapshot",
        lambda *_args: pytest.fail("noncanonical preflight must fail before probes"),
    )

    with pytest.raises(
        stage_suite.StageGateError, match="rc_finalize_preflight_invalid"
    ):
        stage_suite.run_local_rc_finalize(
            context,
            dependency_sha256="c" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            expected_machine_id="f" * 32,
        )


def test_rc_process_identity_rejects_boolean_restart_count():
    processes = _rc_processes()
    processes[0]["restarts"] = True

    with pytest.raises(
        stage_suite.StageGateError, match="rc_finalize_process_stability_invalid"
    ):
        stage_suite._rc_process_identity(processes)


def test_run_local_rc_finalize_rolls_back_pass_artifacts_when_preflight_cleanup_fails(
    monkeypatch, tmp_path
):
    context = _rc_context(tmp_path)
    manifests, _snapshot = _write_rc_guest_state(context)
    _write_rc_preflight_record(context)
    final = {
        "verdict": "PASS",
        "completed": list(stage_suite.STAGE_ORDER),
        "runtime_dark": True,
        "processes_stable": True,
        "readiness_green": True,
        "listeners_accepted": True,
        "immutable_history": True,
        "proof": {"bounded": True},
    }
    monkeypatch.setattr(stage_suite, "_verify_source_checkouts", lambda _context: None)
    monkeypatch.setattr(
        stage_suite,
        "_rc_final_snapshot",
        lambda _context, loaded: (
            final if loaded == manifests else pytest.fail("wrong stage manifests")
        ),
    )
    preflight_path = stage_suite._rc_preflight_path(context)
    original_unlink = Path.unlink

    def fail_preflight_unlink(path, *args, **kwargs):
        if path == preflight_path:
            raise OSError("injected preflight cleanup failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_preflight_unlink)

    with pytest.raises(OSError, match="injected preflight cleanup failure"):
        stage_suite.run_local_rc_finalize(
            context,
            dependency_sha256="c" * 64,
            guest_id="01KZSKQ6FY4EVCCY94XGWZ9NDS",
            expected_machine_id="f" * 32,
        )

    assert preflight_path.exists()
    assert not (context.evidence_root / "LOCAL-RC-1.json").exists()
    assert not (context.evidence_root / "RC-SUMMARY.json").exists()
    checksum_entries = stage_suite._read_checksum_index(
        context.evidence_root / "SHA256SUMS"
    )
    assert "LOCAL-RC-1.json" not in checksum_entries
    assert "RC-SUMMARY.json" not in checksum_entries


def _prepare_rc_finalize_main(monkeypatch, tmp_path):
    context = _rc_context(tmp_path)
    manifests, _snapshot = _write_rc_guest_state(context)
    _write_rc_preflight_record(context)
    final = {
        "verdict": "PASS",
        "completed": list(stage_suite.STAGE_ORDER),
        "runtime_dark": True,
        "processes_stable": True,
        "readiness_green": True,
        "listeners_accepted": True,
        "immutable_history": True,
        "proof": {"bounded": True},
    }
    real_finalize = stage_suite.run_local_rc_finalize
    monkeypatch.setattr(stage_suite, "_verify_source_checkouts", lambda _context: None)
    monkeypatch.setattr(
        stage_suite,
        "_rc_final_snapshot",
        lambda _context, loaded: (
            final if loaded == manifests else pytest.fail("wrong stage manifests")
        ),
    )

    def run_finalize_with_owner(stage_context, **kwargs):
        return real_finalize(
            dataclasses.replace(stage_context, owner_path=context.owner_path), **kwargs
        )

    monkeypatch.setattr(stage_suite, "run_local_rc_finalize", run_finalize_with_owner)
    args = _rc_cli_args(tmp_path, "finalize")
    args.extend(["--harness-root", str(context.harness_root)])
    return context, args


@pytest.mark.parametrize(
    "publication_leg",
    (
        "rc_write",
        "rc_checksum",
        "summary_write",
        "summary_checksum",
        "preflight_unlink",
    ),
)
def test_rc_finalize_publication_failure_publishes_only_a_collectable_failure(
    monkeypatch, tmp_path, rc_expected_machine, publication_leg
):
    context, args = _prepare_rc_finalize_main(monkeypatch, tmp_path)
    original_write = stage_suite.write_stage_manifest
    original_checksum = stage_suite._checksum_manifest
    original_unlink = Path.unlink
    external_path = stage_suite._rc_preflight_path(context)

    def fail_after_success_write(path, payload):
        result = original_write(path, payload)
        name = Path(path).name
        if (publication_leg, name) in {
            ("rc_write", "LOCAL-RC-1.json"),
            ("summary_write", "RC-SUMMARY.json"),
        }:
            raise OSError(f"injected {publication_leg} failure")
        return result

    def fail_after_success_checksum(path):
        result = original_checksum(path)
        name = Path(path).name
        if (publication_leg, name) in {
            ("rc_checksum", "LOCAL-RC-1.json"),
            ("summary_checksum", "RC-SUMMARY.json"),
        }:
            raise OSError(f"injected {publication_leg} failure")
        return result

    def fail_preflight_unlink(path, *args, **kwargs):
        if publication_leg == "preflight_unlink" and path == external_path:
            raise OSError("injected external preflight unlink failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(stage_suite, "write_stage_manifest", fail_after_success_write)
    monkeypatch.setattr(stage_suite, "_checksum_manifest", fail_after_success_checksum)
    monkeypatch.setattr(Path, "unlink", fail_preflight_unlink)

    assert stage_suite.main(args) == 1
    assert external_path.exists()
    assert not (context.evidence_root / "LOCAL-RC-1.json").exists()
    assert not (context.evidence_root / "RC-SUMMARY.json").exists()
    index = stage_suite._read_checksum_index(context.evidence_root / "SHA256SUMS")
    assert "LOCAL-RC-1.json" not in index
    assert "RC-SUMMARY.json" not in index
    failure_path = context.evidence_root / "LOCAL-RC-1-failure.json"
    stage_suite._verify_checksum_entry(failure_path)


@pytest.mark.parametrize("cleanup_artifact", ("LOCAL-RC-1.json", "RC-SUMMARY.json"))
def test_rc_finalize_unproved_publication_cleanup_returns_exit_70(
    monkeypatch, tmp_path, rc_expected_machine, capsys, cleanup_artifact
):
    context, args = _prepare_rc_finalize_main(monkeypatch, tmp_path)
    original_checksum = stage_suite._checksum_manifest
    original_clear = stage_suite._clear_checksum_artifact

    def fail_summary_checksum(path):
        if Path(path).name == "RC-SUMMARY.json":
            raise OSError("injected summary checksum failure")
        return original_checksum(path)

    def fail_success_cleanup(root, name):
        if name == cleanup_artifact:
            raise OSError("injected finalize cleanup failure")
        return original_clear(root, name)

    monkeypatch.setattr(stage_suite, "_checksum_manifest", fail_summary_checksum)
    monkeypatch.setattr(stage_suite, "_clear_checksum_artifact", fail_success_cleanup)

    assert stage_suite.main(args) == stage_suite.FAILURE_MANIFEST_EXIT_CODE
    assert capsys.readouterr().err.splitlines() == [
        "FAIL rc_finalize_publication_rollback_failed"
    ]
    assert not (context.evidence_root / "LOCAL-RC-1-failure.json").exists()


@pytest.mark.parametrize("interrupt", (KeyboardInterrupt(), SystemExit(34)))
def test_rc_finalize_compensation_interrupt_propagates_exactly(
    monkeypatch, tmp_path, rc_expected_machine, interrupt
):
    context, args = _prepare_rc_finalize_main(monkeypatch, tmp_path)
    original_checksum = stage_suite._checksum_manifest
    interrupted = [False]

    def fail_summary_checksum(path):
        if Path(path).name == "RC-SUMMARY.json":
            raise OSError("injected summary checksum failure")
        return original_checksum(path)

    def interrupt_cleanup(_root, _name):
        if not interrupted[0]:
            interrupted[0] = True
            raise interrupt
        return None

    monkeypatch.setattr(stage_suite, "_checksum_manifest", fail_summary_checksum)
    monkeypatch.setattr(stage_suite, "_clear_checksum_artifact", interrupt_cleanup)

    with pytest.raises(BaseException) as caught:
        stage_suite.main(args)

    assert caught.value is interrupt
    assert isinstance(caught.value.__cause__, OSError)
    assert not (context.evidence_root / "LOCAL-RC-1-failure.json").exists()


def test_rc_finalize_parser_dispatches_exact_identity(
    monkeypatch, tmp_path, rc_expected_machine
):
    (tmp_path / "evidence").mkdir()
    captured = []
    monkeypatch.setattr(
        stage_suite,
        "run_local_rc_finalize",
        lambda context, **kwargs: captured.append((context, kwargs)),
        raising=False,
    )

    assert stage_suite.main(_rc_cli_args(tmp_path, "finalize")) == 0
    assert captured[0][1] == {
        "dependency_sha256": "c" * 64,
        "guest_id": "01KZSKQ6FY4EVCCY94XGWZ9NDS",
        "expected_machine_id": "f" * 32,
    }


def test_rc_finalize_failure_preserves_external_preflight(
    monkeypatch, tmp_path, rc_expected_machine
):
    context = _rc_context(tmp_path)
    preflight_path = stage_suite._rc_preflight_path(context)
    preflight_path.write_text('{"preserve": true}\n')
    monkeypatch.setattr(
        stage_suite,
        "run_local_rc_finalize",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            stage_suite.StageGateError("rc_finalize_stage_state_incomplete")
        ),
        raising=False,
    )

    assert stage_suite.main(_rc_cli_args(tmp_path, "finalize")) == 1
    assert preflight_path.read_text() == '{"preserve": true}\n'
    failure = json.loads(
        (context.evidence_root / "LOCAL-RC-1-failure.json").read_text()
    )
    assert failure["failed_gate"] == "rc_finalize_stage_state_incomplete"


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt(), SystemExit(17)])
def test_rc_finalize_interrupt_preserves_preflight_without_verdict(
    monkeypatch, tmp_path, interrupt, rc_expected_machine
):
    context = _rc_context(tmp_path)
    preflight_path = stage_suite._rc_preflight_path(context)
    preflight_path.write_text('{"preserve": true}\n')
    monkeypatch.setattr(
        stage_suite,
        "run_local_rc_finalize",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(interrupt),
        raising=False,
    )

    with pytest.raises(BaseException) as caught:
        stage_suite.main(_rc_cli_args(tmp_path, "finalize"))

    assert caught.value is interrupt
    assert preflight_path.read_text() == '{"preserve": true}\n'
    assert list(context.evidence_root.iterdir()) == []
