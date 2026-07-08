# bff-water-planning — water-planning BFF (GraphQL)

**Python 3.11 / FastAPI 0.104 + Strawberry GraphQL** · Entry: `src/main.py` (`app`, v2.0.0) · **Extends [../../CLAUDE.md](../../CLAUDE.md)**

## Purpose
Backend-for-Frontend aggregating water-demand planning (ROS + GIS + AWD). Computes daily/weekly crop water demands, exposes GraphQL (+ REST), and publishes "demand ready" Redis events to the Water Control BFF.

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
`main.py`, `config/settings.py` (pydantic-settings), `db/` (`database_manager.py` asyncpg+SQLAlchemy async, `weekly_demand_repository.py`), `api/` (`schema.py`, GraphQL, `routes/` REST), `clients/` (ros, gis, awd, weather, sensor_data, scheduler, flow_monitoring, rid_ms HTTP clients), `services/` (daily/weekly demand calculators + schedulers, `ros_sync_service`, `demand_event_publisher`), `dataloaders/`, `schemas/`.

## Tests
pytest + pytest-asyncio + pytest-cov. Real tests in `tests/` (`unit/`; `integration/` is empty) and `src/tests/`. Many ad-hoc `test_*.py`/`verify_*.py` at root are integration scripts, **not** the unit suite. Run `pytest tests/unit/`.

## Config / Ports / Env
- ⚠️ **Port is inconsistent**: `settings.py` default 4002, `.env.example` 3022, docker/README 3002, `start.sh` 3022 — **confirm the intended port before relying on it**.
- `POSTGRES_URL` (main `munbon_dev`), `REDIS_URL` (db 2), `CORS_ORIGINS` (required; wildcard rejected in prod), `DEMAND_COMBINATION_STRATEGY=aquacrop_priority`. Service URLs are env-overridable (ROS/GIS/AWD/flow/scheduler…) and **differ between settings and .env.example**.
- DBs: Postgres `munbon_dev` (BFF) + schema `ros_gis` (weekly demands) + GIS `munbon_gis`/`gis` (from scripts); Redis db 2.

## Integration
Reads/writes `ros_gis.weekly_water_demands`, queries `gis.crop_registry`; talks to ROS/GIS/AWD/Flow/Scheduler/Weather/Sensor via `src/clients/`; publishes Redis demand events.

## Gotchas / Watch-outs
- 🚨🚨 **CONFIRMED hardcoded PRODUCTION DB credentials** in `scripts/populate_weekly_demands_with_events.py` (`GIS_DB_CONFIG`/`BFF_DB_CONFIG`: host `43.208.201.191`, plaintext password). The **same password appears in ~34 `scripts/` files** and the prod IP in ~40 files — this is the **SEC / F-07** remediation item. Rotate the password, move to env/secrets, add secret-scanning. Do **not** copy this pattern.
- `/health` external-service checks are **stubbed** (hardcoded `True`, no real probing); `/health` reports version `1.0.0` while the app is `2.0.0`.
- Weekly-demand script uses a hardcoded ET0-by-month table and `effective_rainfall_mm=0`.
- Duplicate/versioned modules (`weekly_demand_calculator.py`, `_v2.py`, `_v2_updated.py`) — confirm which is authoritative before editing.
