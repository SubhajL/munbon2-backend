# ros-gis-integration — demand pipeline (ROS/Excel → ros_gis)

**Python 3.11 / FastAPI + Strawberry GraphQL** · Entry: `src/main.py` (`main:app`) · **Extends [../../CLAUDE.md](../../CLAUDE.md)**

## Purpose
Bridges agricultural water demand (ROS / AquaCrop / Excel) with hydraulic delivery: calculates & aggregates per-section demands, syncs ROS→GIS, and submits prioritized weekly demands to the Scheduler. This is the **single operational demand lineage** (ROS/`ros_gis`).

## Commands
```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
./start.sh                    # venv uvicorn src.main:app --port 3047
python src/main.py            # dev (reload when environment=development)
pytest                        # tests/unit/ (currently only test_settings.py)
```
No Dockerfile, README, pyproject, or Makefile in this service.

## Structure (`src/`)
`main.py` (REST + sync-trigger endpoints), `config/settings.py`, `api/graphql_schema.py` + `api/routes/admin.py`, `services/` (`ros_sync_service.py`, `daily_demand_calculator.py`, `demand_aggregator.py`, `priority_engine.py`, `spatial_mapping.py`, `integration_client.py`, …), `clients/` (`ros_client.py`, `gis_client.py`, both mock-capable), `db/database_manager.py` (asyncpg + SQLAlchemy async + redis), `schemas/`.

## Tests
pytest + pytest-asyncio. Only `tests/unit/test_settings.py` exists (coverage is minimal). No conftest/pytest.ini.

## Config / Ports / Env
- Port: settings default 3022 but `.env`/`start.sh` force **3047** (effective). Endpoints: `/graphql`, `/health`, `/metrics`, `/api/v1/*` (sections/zones/sync trigger), `/api/v1/admin/*`.
- `POSTGRES_URL` (`.env` → remote `43.208.201.191:5432/munbon_dev`), `REDIS_URL`, `USE_MOCK_SERVER`, `DEMAND_COMBINATION_STRATEGY=aquacrop_priority`, service URLs (`FLOW_MONITORING_URL`, `SCHEDULER_URL`, `ROS_SERVICE_URL`, `GIS_SERVICE_URL`).
- Schemas: `ros_gis` (`aquacrop_results`, `sections`, `plots`, `daily_demands`, `gate_mappings`).

## Integration
ROS Service (REST) → demand calc → `_combine_demands()` (strategy-driven) → upsert `ros_gis.daily_demands` → aggregate by section/gate → submit to **Scheduler** (`POST /api/v1/scheduler/demands`). Syncs ROS→GIS (`POST /api/v1/ros-demands/bulk`). Consumes **flow-monitoring** for gate/level state.

## Gotchas / Watch-outs
- 🐛 **Likely KeyError bug**: `IntegrationClient.base_urls` defines only `flow_monitoring`/`scheduler`/`weather`, but code reads `base_urls['gis']` and `base_urls['ros']` (in `integration_client.py` + `ros_sync_service.py`) → `KeyError` in the ROS-sync / crop-requirements paths.
- **AquaCrop demand is effectively empty**: `ros_gis.aquacrop_results` is **READ but written by nothing in-repo** (only the mock-server embeds a randomized dict in an HTTP response). With default `aquacrop_priority`, the strategy **silently falls back to ROS** (remediation F-06). Log the source.
- Mock/real split by `USE_MOCK_SERVER`: in mock mode the ROS clients return hardcoded data and the periodic sync loop does **not** start.
- Many hardcoded "real-path" constants: `et_mm_day=5.5`, `water_need_mm=6.6`, `percolation_mm=14`, `moistureDeficitPercent=20`, area factor `×1.6`, hardcoded Kc/zone maps, `Authorization: Bearer mock-token`, synthetic delivery paths, `_get_mock_plots()` fallback. Treat outputs as provisional.
- Port collision: `ROS_SERVICE_URL` default `:3047` equals this service's own effective port.
