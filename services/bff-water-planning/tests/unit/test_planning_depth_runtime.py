import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]


def _load_stage_suite():
    path = REPO_ROOT / "ops" / "control-plan-read-local" / "run-stage-suite.py"
    spec = importlib.util.spec_from_file_location("planning_depth_stage_suite", path)
    if spec is None or spec.loader is None:
        raise AssertionError("stage suite cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_runtime_migration_parity_requires_the_exact_bff_manifest():
    stage_suite = _load_stage_suite()
    scheduler_ids = [
        path.name.removesuffix(".up.sql")
        for path in sorted(
            (REPO_ROOT / "services" / "scheduler" / "migrations").glob("*.up.sql")
        )
    ]
    ros_ids = [
        path.name.removesuffix(".up.sql")
        for path in sorted(
            (REPO_ROOT / "services" / "ros-gis-integration" / "migrations").glob(
                "*.up.sql"
            )
        )
    ]
    bff_manifest = json.loads(
        (
            REPO_ROOT
            / "services"
            / "bff-water-planning"
            / "migrations"
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    bff_ids = [migration["migration_id"] for migration in bff_manifest["migrations"]]

    assert stage_suite.validate_migration_parity(
        scheduler_ids,
        ros_ids,
        bff_ids,
    ) == {
        "scheduler_latest": "0013_operator_approved_execution",
        "scheduler_count": 13,
        "ros_latest": "0003_daily_requirement_producer",
        "ros_count": 3,
        "bff_latest": "011_planning_depth_rid_calendar_v2",
        "bff_count": 3,
    }
    with pytest.raises(stage_suite.StageGateError, match="migration_parity_failed"):
        stage_suite.validate_migration_parity(
            scheduler_ids,
            ros_ids,
            bff_ids[:-1],
        )
