# flow-monitoring — gate hydraulics & demand→gate control

**Python 3 / FastAPI** · Entry: `src/main.py` (`app = FastAPI(...)`, `uvicorn.run(port=settings.port)`) · **Extends [../../CLAUDE.md](../../CLAUDE.md)**

## Purpose
Computes canal/gate hydraulics for the Munbon network: gate flow law (K1/K2 rating), required gate openings, demand→gate aggregation over the network graph, and (intended) SCADA command generation. This service is under active **P0 remediation** — see `docs/remediation/`.

## Commands
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt          # numpy, pytest, pytest-asyncio, pytest-cov, hypothesis
pytest -v                                # tests live in tests/unit/test_*.py
pytest tests/unit/test_gate_flow.py -v   # (P0) the F-01 regression/invariant suite
uvicorn src.main:app --reload            # dev server (port from settings)
```
Gate before PR: `pytest`.

## Structure (`src/`)
- `core/` — pure hydraulic/domain logic (**put I/O-free code here so it's unit-testable**): `gate_flow.py` (the SINGLE flow law), `network_topology.py`, `node_id.py`, `config_loader.py`, `demand_aggregation.py`, `conveyance_loss.py`, `canal_capacity.py`, `network_flow_controller.py`. (The live gate registry is `services/gate_registry.py`, feeding the `/gates/config` API; the legacy duplicates — `calibrated_flow_model*.py`, `enhanced_hydraulic_solver.py` — were deleted in Waves 1.6/1.8.)
- `services/` — orchestration + I/O: `hydraulic_service.py` (the `_calculate_required_opening`, `_get_gate_capacity`, `_get_canal_capacity` methods being remediated).
- `utils/gate_calibration_loader.py` — loads K1/K2 from `src/config/gate_calibrations.json` (59 gates, 10 calibrated; confidence 0.95/0.80/0.60).
- `api/`, `controllers/`, `schemas/`, `db/`, `config/`; provenance/generator scripts in `scripts/`.
- `tests/` — `tests/unit/test_*.py` (pytest), `tests/conftest.py`.

## Config / Ports / Env
- Port: `settings.port` (config-driven). DBs: TimescaleDB/Postgres per `src/config`. Calibration data: `src/config/gate_calibrations.json`.

## Integration
- Consumes demand from **ros-gis-integration** (`ros_gis` schema / HTTP). Intended to drive **scada-gate-control** (continuous opening → discrete level 1-4) — this bridge is **not yet connected** (remediation F-02).

## Gotchas / Watch-outs (P0 remediation — read `docs/remediation/REMEDIATION_MASTER.md`)
- **Divergent duplicate flow laws** exist and diverge: `core/calibrated_flow_model.py`, `_v2.py`, `calibrated_gate_flow.py`, `gate_opening_calculator.py`, a 2nd `_calculate_required_opening` in `enhanced_flow_monitoring_integration.py`, and `gate_hydraulics.py`. **Do not add another** — consolidate to `core/gate_flow.py` (C10).
- **F-01**: the wired gate flow law is inverted/unclamped (`Cs = k1*(opening**k2)`, hardcoded `upstream_depth=2.0`/`head_diff=0.2`) → returns ~287 m³/s at 10% open. Fix per `docs/remediation/FIX_F01_GATE_FLOW_LAW_SPEC.md`.
- **F-04**: `_get_canal_capacity` returns a hardcoded `15.0`; real per-reach `design_discharge` is unused.
- **F-11**: 6 conflicting `munbon_network_*.json` topology files; `munbon_network_updated.json` is the correct one — regenerate one canonical `network.json` + a loader connectivity guard.
- `saint-venant`/`manning` API options return **hardcoded literals** (façade) — not real solvers.
- Many script-style `test_*.py` in `src/` are NOT pytest tests — real tests are in `tests/unit/`.
