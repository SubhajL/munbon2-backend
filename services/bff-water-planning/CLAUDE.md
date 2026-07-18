# bff-water-planning — water-planning BFF (GraphQL)

**Python 3.11 / FastAPI 0.104 + Strawberry GraphQL** · Entry: `src/main.py` (`app`, v2.0.0) · **Extends [../../CLAUDE.md](../../CLAUDE.md)**

## Purpose
Backend-for-Frontend aggregating water-demand planning (ROS + GIS + AWD). Exposes GraphQL
(+ REST) read paths over `ros_gis` demand data and publishes "demand ready" Redis events to
the Water Control BFF. **It does NOT produce canonical weekly demand** — production is owned
by ros-gis-integration per ADR D5 (Wave 2.6a deleted the unbootable weekly-calculator stack;
see `services/flow-monitoring/docs/remediation/ADR-D5-DEMAND_PRODUCER_OWNERSHIP.md`).

## Commands
```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn src.main:app --reload --port 3002   # dev (README)
./start.sh                                             # prod launcher (forces USE_MOCK_SERVER=false)
pytest tests/unit/                                     # unit tests
psql ... -f migrations/00X_*.sql                       # raw-SQL migrations (001–008)
```

## Structure (`src/`)
`main.py`, `config/settings.py` (pydantic-settings), `db/` (`database_manager.py` asyncpg+SQLAlchemy async, `weekly_demand_repository.py`), `api/` (`schema.py`, GraphQL, `routes/` REST), `clients/` (ros, gis, awd, weather, sensor_data, scheduler, flow_monitoring, rid_ms HTTP clients), `services/` (daily demand calculator + scheduler, `ros_sync_service`, `demand_event_publisher`; weekly/crop-season calculators deleted in 2.6a — ADR D5), `dataloaders/`, `schemas/`.

## Tests
pytest + pytest-asyncio + pytest-cov. Real tests in `tests/` (`unit/`; `integration/` is empty) and `src/tests/`. Many ad-hoc `test_*.py`/`verify_*.py` at root are integration scripts, **not** the unit suite. Run `pytest tests/unit/` — the gate since 2.6a; `tests/conftest.py` provides the src path + the dummy `CORS_ORIGINS` that import-time `Settings()` requires (never depend on a developer `.env`).

## Config / Ports / Env
- ⚠️ **Port is inconsistent**: `settings.py` default 4002, `.env.example` 3022, docker/README 3002, `start.sh` 3022 — **confirm the intended port before relying on it**.
- `POSTGRES_URL` (main `munbon_dev`), `REDIS_URL` (db 2), `CORS_ORIGINS` (required; wildcard rejected in prod), `DEMAND_COMBINATION_STRATEGY=aquacrop_priority`. Service URLs are env-overridable (ROS/GIS/AWD/flow/scheduler…) and **differ between settings and .env.example**.
- DBs: Postgres `munbon_dev` (BFF) + schema `ros_gis` (weekly demands) + GIS `munbon_gis`/`gis` (from scripts); Redis db 2.

## Integration
Reads/writes `ros_gis.weekly_water_demands`, queries `gis.crop_registry`; talks to ROS/GIS/AWD/Flow/Scheduler/Weather/Sensor via `src/clients/`; publishes Redis demand events.

Canonical daily reads are projections of ros-gis-integration:
`GET /api/v1/water-demand/daily` and
`GET /api/v1/water-demand/sections/{section_id}/daily`. They preserve immutable
run/requirement lineage and `no_publication|stale|published|superseded` status;
upstream failures never fall back to zero or mutable rows. The former mutable
section query remains temporarily at the deprecated
`/api/v1/water-demand/legacy/sections/{section_id}/daily` path.

**Control-plan projections (PR 4.4)** — four READ-ONLY GETs under
`/api/v1/control-plans/{plan_id}/versions/{plan_version}` (`` = detail,
`/prediction-coverage`, `/ledger`, `/lifecycle-history`) let operators inspect the
scheduler's non-commanding shadow plans without DB access. They are **strict
validated pass-through** (`schemas/control_plan.py`, `extra="forbid"`,
snake_case mirror of the scheduler OUT schemas) — no new status vocabulary, no
success booleans, no fabricated delivery numbers. The BFF forwards the operator's
**bearer token** to the scheduler (`HTTPBearer`, no service token; scheduler stays
the JWT authority) and preserves every upstream state exactly:
`unavailable|infeasible|invalidated|stale` are never collapsed to zero/empty/
success. `source_data_status="stale"` is the immutable snapshot-time source
status, NOT a live freshness recompute. Error taxonomy (never swallows, unlike the
legacy schedule methods): 404→404, scheduler 401/403→same, 503/transport→503,
malformed body or schema **drift**→502 (fail-closed), other→502. There is **no
list route** (the scheduler has none — do not fabricate one) and these projections
must **not** be cached. New client methods
`SchedulerClient.get_control_plan_projection/.get_control_plan_ledger` and typed
errors `SchedulerControlPlanError` + subclasses live in `clients/scheduler_client.py`.
The service now ships a `pytest.ini` (`testpaths=tests`, `asyncio_mode=strict`) so
bare `pytest` is the gate and never collects the root integration scripts.

## Gotchas / Watch-outs
- 🚨🚨 **CONFIRMED hardcoded PRODUCTION DB credentials** in `scripts/populate_weekly_demands_with_events.py` (`GIS_DB_CONFIG`/`BFF_DB_CONFIG`: host `43.208.201.191`, plaintext password). The **same password appears in ~34 `scripts/` files** and the prod IP in ~40 files — this is the **SEC / F-07** remediation item. Rotate the password, move to env/secrets, add secret-scanning. Do **not** copy this pattern.
- `/health` external-service checks are **stubbed** (hardcoded `True`, no real probing); `/health` reports version `1.0.0` while the app is `2.0.0`.
- **The weekly/crop-season calculator stack was DELETED in Wave 2.6a** (`weekly_demand_calculator{,_v2,_v2_updated}.py`, `weekly_scheduler.py`, `weekly_accumulation_scheduler.py`, `crop_season_demand_calculator.py`, `api/routes/crop_season_demand.py`): every module imported never-committed dependencies (`services.calculation_engine`, `utils.date_utils`, `db.database`, `utils.logger`, `services.scheduler_client`) and made the service **unbootable since birth**. `tests/unit/test_boot.py` guards against resurrection. Do not re-add a demand producer here — that's ros-gis-integration's job (ADR D5, PR 2.6).
- `Settings()` instantiates at import time and `cors_origins` has no default — `import main` fails without `CORS_ORIGINS` in the env.
- **Fail-closed rule (Wave 2.6b)**: `daily_demand_calculator._get_active_plots` serves mock plots ONLY under `USE_MOCK_SERVER`; a real-mode DB failure logs + raises (the scheduler's own try/except contains it per run) — never re-add fabricate-on-failure fallbacks. `DatabaseManager.get_connection` (raw asyncpg) was ADDED in 2.6b — before that the "real" path raised AttributeError into the fabricating except on every call. Locked by `tests/unit/test_daily_demand_fail_closed.py`.
