"""PR 2.6a boot-restoration guard.

The service was unbootable since birth: main.py (and one mounted route) imported
modules that were never committed (services.calculation_engine, utils.date_utils,
db.database, utils.logger, services.scheduler_client — verified absent from all
git history). 2.6a deletes that stack; demand production is owned by
ros-gis-integration per ADR D5 (docs/remediation, flow-monitoring).
"""

import importlib
import importlib.util
from importlib.metadata import version
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[2]

# Modules deleted in 2.6a. Resurrecting any of them (or re-adding an import of
# the never-committed modules they depended on) must fail this suite.
DELETED_WEEKLY_STACK = [
    "services.weekly_demand_calculator",
    "services.weekly_demand_calculator_v2",
    "services.weekly_demand_calculator_v2_updated",
    "services.weekly_scheduler",
    "services.weekly_accumulation_scheduler",
    "services.crop_season_demand_calculator",
    "api.routes.crop_season_demand",
]

NEVER_COMMITTED_PHANTOMS = [
    "services.calculation_engine",
    "utils.date_utils",
    "utils.logger",
    "db.database",
    "services.scheduler_client",
]


def _module_exists(module_name: str) -> bool:
    # find_spec raises (rather than returning None) when a dotted parent
    # package is itself missing.
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False


def test_main_imports_and_exposes_the_app():
    main = importlib.import_module("main")
    assert main.app.title == "Water Planning BFF Service"


def test_bff_schema_imports_with_pinned_strawberry():
    requirements = (SERVICE_ROOT / "requirements.txt").read_text().splitlines()

    assert "strawberry-graphql[fastapi]==0.322.2" in requirements
    assert "python-multipart==0.0.32" in requirements
    assert version("strawberry-graphql") == "0.322.2"
    assert version("python-multipart") == "0.0.32"

    schema_module = importlib.import_module("api.schema")
    graphql_app = schema_module.create_graphql_app()
    schema_sdl = schema_module.schema.as_str()

    assert "type Query {" in schema_sdl
    assert "type Mutation {" in schema_sdl
    assert "/graphql" in {route.path for route in graphql_app.routes}


def test_live_route_surface_survives_boot():
    main = importlib.import_module("main")
    route_paths = {route.path for route in main.app.routes}
    for expected in (
        "/health",
        "/api/v1/status",
        "/graphql",
        "/api/v1/water-planning/planning-depth-submissions",
    ):
        assert any(
            path.startswith(expected) for path in route_paths
        ), f"expected live route {expected} missing after boot restoration"


@pytest.mark.parametrize("module_name", DELETED_WEEKLY_STACK)
def test_deleted_demand_stack_stays_deleted(module_name):
    assert not _module_exists(module_name), (
        f"{module_name} was resurrected; it depends on never-committed modules "
        "and demand production belongs to ros-gis-integration (ADR D5)"
    )


@pytest.mark.parametrize("module_name", NEVER_COMMITTED_PHANTOMS)
def test_phantom_dependencies_do_not_exist(module_name):
    assert not _module_exists(module_name), (
        f"{module_name} appeared; if it is being (re)introduced deliberately, "
        "update ADR D5 and the 2.6 producer plan first"
    )


def _cleanup_test_app(monkeypatch, calls):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    import api.schema as schema_module

    async def record_cleanup(context):
        calls.append(context)

    monkeypatch.setattr(schema_module, "cleanup_context", record_cleanup)

    app = FastAPI()
    schema_module.register_graphql_context_cleanup(app)

    @app.get("/with-context")
    async def with_context(request: Request):
        request.state.graphql_context = {"request_id": "req-1"}
        return {"ok": True}

    @app.get("/without-context")
    async def without_context():
        return {"ok": True}

    return TestClient(app)


def test_graphql_context_cleanup_runs_after_the_response(monkeypatch):
    calls = []
    client = _cleanup_test_app(monkeypatch, calls)

    response = client.get("/with-context")

    assert response.status_code == 200
    # TestClient completes the full response cycle including background tasks.
    assert calls == [{"request_id": "req-1"}]


def test_no_cleanup_when_request_sets_no_graphql_context(monkeypatch):
    calls = []
    client = _cleanup_test_app(monkeypatch, calls)

    response = client.get("/without-context")

    assert response.status_code == 200
    assert calls == []
