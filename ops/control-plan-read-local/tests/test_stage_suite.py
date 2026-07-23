import importlib.util
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "run-stage-suite.py"
SPEC = importlib.util.spec_from_file_location(
    "control_plan_local_stage_suite", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
stage_suite = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = stage_suite
SPEC.loader.exec_module(stage_suite)


def test_validate_runtime_urls_accepts_only_exact_loopback_http_endpoints():
    urls = {
        "flow": "http://127.0.0.1:3011",
        "scheduler": "http://127.0.0.1:3021",
        "ros": "http://127.0.0.1:3047",
        "bff": "http://127.0.0.1:3022",
        "auth": "http://127.0.0.1:3005",
    }

    assert stage_suite.validate_runtime_urls(urls) == urls


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
        "water_planning_v2": False,
        "water_planning_submit": False,
    }


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

    stage_suite.clear_failure_manifest(tmp_path, "LOCAL-AC-1")

    assert not current.exists()
    assert other.exists()


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


def test_validate_migration_parity_requires_scheduler_0013_ros_0003_and_bff_009():
    scheduler = [f"{index:04d}_migration" for index in range(1, 13)] + [
        "0013_operator_approved_execution"
    ]
    ros = [
        "0001_dataset_version_parent",
        "0002_water_requirement_publication",
        "0003_daily_requirement_producer",
    ]

    assert stage_suite.validate_migration_parity(scheduler, ros, True) == {
        "scheduler_latest": "0013_operator_approved_execution",
        "scheduler_count": 13,
        "ros_latest": "0003_daily_requirement_producer",
        "ros_count": 3,
        "bff_latest": "009_crop_registry",
    }


@pytest.mark.parametrize(
    "scheduler,ros,bff",
    [
        (["0012_authority_grants"], ["0003_daily_requirement_producer"], True),
        (
            ["0013_operator_approved_execution"],
            ["0002_water_requirement_publication"],
            True,
        ),
        (
            ["0013_operator_approved_execution"],
            ["0003_daily_requirement_producer"],
            False,
        ),
    ],
)
def test_validate_migration_parity_fails_closed_on_any_missing_tail(
    scheduler, ros, bff
):
    with pytest.raises(stage_suite.StageGateError, match="migration_parity_failed"):
        stage_suite.validate_migration_parity(scheduler, ros, bff)
