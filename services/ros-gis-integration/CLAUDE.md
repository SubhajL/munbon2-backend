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
pytest                        # unit + integration (DB contract skips without its URL)
```
No Dockerfile, README, pyproject, or Makefile in this service.

## Structure (`src/`)
`main.py` (REST + sync-trigger endpoints), `config/settings.py`, `api/graphql_schema.py` + `api/routes/admin.py`, `services/` (`ros_sync_service.py`, `daily_demand_calculator.py`, `demand_aggregator.py`, `priority_engine.py`, `spatial_mapping.py`, `integration_client.py`, …), `clients/` (`ros_client.py`, `gis_client.py`, both mock-capable), `db/database_manager.py` (asyncpg + SQLAlchemy async + redis), `db/water_requirement_repository.py` (append-only canonical requirement runs), `schemas/`.

## Tests
pytest + pytest-asyncio. `tests/conftest.py` puts `src` on the path (src-rooted imports);
suite = `pytest` (settings + the 2.6b fail-closed/interface/query-shape locks
for `daily_demand_calculator` + the 2.5 dataset-version and requirement-publication
schema/repository locks). The PostgreSQL contract test under `tests/integration/` skips
unless `WATER_REQUIREMENT_TEST_POSTGRES_URL` names a disposable migrated database. Tracked via a
scoped `.gitignore` negation (Wave 2.6b).

## Migrations (Wave 2.5)
Tracked DDL pairs in `migrations/` (`<id>.up.sql`/`<id>.down.sql`; a scoped negation
allowlists only those suffixes past the blanket `*.sql` ignore). Commands:
`python migrations/migrate.py apply|rollback <id>` and `status` — one transaction per
migration, pair checksum registry in `ros_gis.schema_migrations`, drift refuses on apply
or rollback (fail closed). The runner loads the service `.env`, parses reserved password
characters into asyncpg keyword arguments, and keeps `status` read-only.
`0001_dataset_version_parent`: dataset_versions parent + effective-dated
section_master_history / gate_mapping_history (gist exclusions reject overlapping
validity; primary-exclusivity scoped per dataset+section+interval) + `*_current` views +
additive current-table hardening. Version tables use separate migration-owned SQLAlchemy
metadata, so development `Base.metadata.create_all` cannot bypass the registry or require
`btree_gist`. Rollback removes owned version objects but deliberately retains additive
legacy-table columns/defaults/geometry widening because ownership-safe reversal is not
possible. Canonical `M(i,j)` validation applies to versioned crosswalk rows; the legacy
table still carries path-like IDs. NOT yet applied to the remote DB (E1 credential
rotation first).

`0002_water_requirement_publication` adds append-only `water_requirement_runs`,
`daily_water_requirements`, and `water_requirement_contributions`. Run lineage uses the
integer/composite dataset-version keys created by `0001`; run and requirement identities
are UUIDs. Publication, correction supersession, failure, horizon/quality/volume checks,
and immutable item rows are enforced both in PostgreSQL and by
`db/water_requirement_repository.py`. Apply `0001` before `0002`; test the pair with
apply, rollback, reapply on disposable PostGIS before shipping.

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
- Many hardcoded "real-path" constants: `et_mm_day=5.5`, `water_need_mm=6.6`, `percolation_mm=14`, `moistureDeficitPercent=20`, area factor `×1.6`, hardcoded Kc/zone maps, `Authorization: Bearer mock-token`, synthetic delivery paths. Treat outputs as provisional.
- **Fail-closed rule (Wave 2.6b)**: `_get_active_plots` serves mock plots ONLY under `USE_MOCK_SERVER`; a real-mode DB failure raises (aborts the run) — never re-add fabricate-on-failure fallbacks. Locked by `tests/unit/test_daily_demand_fail_closed.py`. Client `except` paths still degrade to empty (`[]`/`None`) — silent-empty debt for the 2.6 producer PR.
- Port collision: `ROS_SERVICE_URL` default `:3047` equals this service's own effective port.
