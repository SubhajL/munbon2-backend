import importlib.util
import json
import os
from pathlib import Path
import sys

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


def test_stage_transition_requires_base_before_rta():
    stage_suite.validate_stage_transition((), "LOCAL-BASE-0")
    stage_suite.validate_stage_transition(("LOCAL-BASE-0",), "LOCAL-RTA-1")

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


def test_write_stage_manifest_is_mode_600_atomic_and_secret_safe(tmp_path):
    target = tmp_path / "LOCAL-BASE-0.json"
    payload = {"stage": "LOCAL-BASE-0", "sha": "8" * 40, "verdict": "PASS"}

    stage_suite.write_stage_manifest(target, payload)

    assert json.loads(target.read_text()) == payload
    assert os.stat(target).st_mode & 0o777 == 0o600
    assert not target.with_suffix(".json.tmp").exists()

    with pytest.raises(stage_suite.StageGateError, match="evidence_contains_secret"):
        stage_suite.write_stage_manifest(target, {"password": "no"})


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
