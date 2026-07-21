import json
import re
import subprocess
from pathlib import Path


RUNTIME_DIR = Path(__file__).resolve().parents[1]
WRAPPERS = [
    RUNTIME_DIR / "run-flow.sh",
    RUNTIME_DIR / "run-scheduler.sh",
    RUNTIME_DIR / "run-ros.sh",
    RUNTIME_DIR / "run-bff.sh",
]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_runtime_files_are_secret_free_and_have_no_compensation_overlays():
    forbidden = [
        "LEGACY_POSTGRES_URL",
        "DECODED_POSTGRES",
        "pip install",
        "/home/ubuntu",
        "runtime-artifacts/control-plan-read-3885ee63",
    ]
    for path in [
        *WRAPPERS,
        RUNTIME_DIR / "ecosystem.config.cjs",
        RUNTIME_DIR / "activate.sh",
    ]:
        body = _text(path)
        for value in forbidden:
            assert value not in body, f"{value} leaked into {path.name}"
        assert not re.search(r"postgres(?:ql)?://[^\s]+:[^\s]+@", body)


def test_wrappers_bind_exact_loopback_ports_and_run_migrations_before_start():
    expected = {
        "run-flow.sh": 3011,
        "run-scheduler.sh": 3021,
        "run-ros.sh": 3047,
        "run-bff.sh": 3022,
    }
    for wrapper in WRAPPERS:
        body = _text(wrapper)
        port = expected[wrapper.name]
        assert f"--host 127.0.0.1 --port {port}" in body
        assert body.index("migration") < body.index("uvicorn")
        subprocess.run(["bash", "-n", str(wrapper)], check=True)


def test_ros_wrapper_applies_every_tracked_migration():
    body = _text(RUNTIME_DIR / "run-ros.sh")
    for migration_id in (
        "0001_dataset_version_parent",
        "0002_water_requirement_publication",
        "0003_daily_requirement_producer",
    ):
        assert migration_id in body


def test_ecosystem_is_repo_relative_and_registers_exact_processes():
    script = (
        "const value=require(process.argv[1]);"
        "process.stdout.write(JSON.stringify(value.apps.map(a=>({name:a.name,script:a.script}))));"
    )
    result = subprocess.run(
        ["node", "-e", script, str(RUNTIME_DIR / "ecosystem.config.cjs")],
        check=True,
        capture_output=True,
        text=True,
    )
    apps = json.loads(result.stdout)

    assert [app["name"] for app in apps] == [
        "flow-monitoring",
        "scheduler",
        "ros-gis-integration",
        "bff-water-planning",
    ]
    assert all(Path(app["script"]).parent == RUNTIME_DIR for app in apps)


def test_activation_orders_capacity_start_snapshot_stability_and_save():
    body = _text(RUNTIME_DIR / "activate.sh")
    positions = [
        body.index("runtime_gate.py capacity"),
        body.index("pm2 start"),
        body.index("runtime_gate.py snapshot"),
        body.index("--startup-timeout 120"),
        body.index("--duration 300"),
        body.index("pm2 save"),
    ]

    assert positions == sorted(positions)
    assert (
        "pm2 stop flow-monitoring scheduler ros-gis-integration bff-water-planning"
        in body
    )
    subprocess.run(["bash", "-n", str(RUNTIME_DIR / "activate.sh")], check=True)


def test_readme_names_capacity_backout_env_permissions_and_bearer_proof():
    body = _text(RUNTIME_DIR / "README.md")

    for required in (
        "512 MiB",
        "1 GiB",
        "mode 600",
        "five-minute",
        "verify_bearer.py",
        "pm2 stop flow-monitoring scheduler ros-gis-integration bff-water-planning",
        "POSTGRES_URL",
        "REQUIREMENT_SOURCE_POSTGRES_URL",
    ):
        assert required in body
