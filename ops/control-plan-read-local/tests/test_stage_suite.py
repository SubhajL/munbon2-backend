import ast
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


def test_validate_manual_requirement_run_requires_exact_complete_publication():
    run_id = str(uuid4())

    assert stage_suite.validate_manual_requirement_run(
        200,
        {
            "status": "published",
            "runId": run_id,
            "asOfDate": "2026-07-23",
            "requirementCount": 287,
        },
        as_of_date="2026-07-23",
    ) == {
        "status": "published",
        "run_id": run_id,
        "as_of_date": "2026-07-23",
        "requirement_count": 287,
    }
    with pytest.raises(
        stage_suite.StageGateError,
        match="manual_requirement_run_not_accepted",
    ):
        stage_suite.validate_manual_requirement_run(
            200,
            {
                "status": "deduplicated",
                "runId": run_id,
                "asOfDate": "2026-07-23",
                "requirementCount": 287,
            },
            as_of_date="2026-07-23",
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
        "dataset_versions_identity_is_immutable\tO\t27\t\tt\t"
        "ros_gis.reject_dataset_version_identity_change()"
    ),
    (
        "dataset_versions_no_truncate\tO\t34\t\tt\t"
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
            ROS_DATASET_VERSION_TRIGGER_ROWS[0].replace("\t\tt\t", "\t1 2\tt\t"),
            ROS_DATASET_VERSION_TRIGGER_ROWS[1],
        ],
        [
            ROS_DATASET_VERSION_TRIGGER_ROWS[0].replace("\t\tt\t", "\t\tf\t"),
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
        [*ROS_DATASET_VERSION_TRIGGER_ROWS, "unexpected_trigger\tO\t27\t\tt\tfn()"],
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

    def request(self, method, url, *, payload=None, bearer=None, **kwargs):
        self.calls.append((method, url, payload))
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
    return {
        "create_result": {
            "status": 201,
            "submission_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            "replayed": False,
        },
        "active_readback": {
            "status": 200,
            "submission_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            "levels_count": 41,
            "distinct_depths": [250.0, 260.0, 270.0, 280.0, 290.0, 300.0],
        },
        "correct_result": {
            "status": 201,
            "submission_id": "d4c3b2a1-f6e5-4b7a-9d8c-1e0f2a3b4c5d",
        },
        "conflict_result": {"status": 409},
        "conflict_reconciliation": {
            "status": 200,
            "submission_id": "d4c3b2a1-f6e5-4b7a-9d8c-1e0f2a3b4c5d",
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
        assert argv == ["pm2", "jlist"]
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


def test_parse_args_rejects_diagnostic_mode_for_acceptance_evidence_root():
    with pytest.raises(SystemExit):
        stage_suite._parse_args(
            [
                "LOCAL-WRITE-UI-1",
                "--release-sha",
                "8" * 40,
                "--frontend-sha",
                "9" * 40,
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
        if argv[:2] == ["pm2", "jlist"]:
            events.append("jlist:scheduler")
            return _scheduler_jlist("online")
        events.append(f"{argv[1]}:{argv[2]}")
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
        if argv[:2] == ["pm2", "jlist"]:
            # The restart genuinely never took: pm2 still reports it stopped.
            return _scheduler_jlist("stopped")
        events.append(f"{argv[1]}:{argv[2]}")
        if argv[1] == "restart":
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
        if argv[:2] == ["pm2", "jlist"]:
            return _scheduler_jlist("online")
        events.append(f"{argv[1]}:{argv[2]}")
        if argv[1] == "stop":
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
        if argv[:2] == ["pm2", "jlist"]:
            # Dead for real: the primary diagnosis must still lead the code.
            return _scheduler_jlist("stopped")
        events.append(f"{argv[1]}:{argv[2]}")
        if argv[1] == "restart":
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
    assert stage_suite.STAGE_ORDER[-1] == "LOCAL-PERSIST-ONLY-1"
    assert stage_suite.STAGE_ORDER[-2] == "LOCAL-WRITE-UI-1"


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

    result = stage_suite.validate_persist_only_rate_accounting(before, after)

    assert result["operator_rate_key"] == _OP_KEY


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

    def failing_body(ctx, c, token, evidence):
        raise stage_suite.StageGateError("injected_body_failure")

    monkeypatch.setattr(stage_suite, "_persist_only_body", failing_body)

    with pytest.raises(stage_suite.StageGateError, match="injected_body_failure"):
        stage_suite.run_local_persist_only(_persist_only_context(tmp_path))

    # the primary error propagated AND the session was still torn down once
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
