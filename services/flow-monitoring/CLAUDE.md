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
python src/main.py                       # dev server (uvicorn src.main:app CANNOT boot: config imports are src-rooted)
```
Gate before PR: `pytest`.

## Structure (`src/`)
- `core/` — pure hydraulic/domain logic (**put I/O-free code here so it's unit-testable**): `gate_flow.py` (the SINGLE flow law), `network_topology.py`, `node_id.py`, `config_loader.py`, `demand_aggregation.py`, `conveyance_loss.py`, `canal_capacity.py`, `network_flow_controller.py`. (The live gate registry is `services/gate_registry.py`, feeding the `/gates/config` API; the legacy duplicates — `calibrated_flow_model*.py`, `enhanced_hydraulic_solver.py` — were deleted in Waves 1.6/1.8.)
- `services/` — orchestration + I/O: `hydraulic_service.py` (the `_calculate_required_opening`, `_get_gate_capacity`, `_get_canal_capacity` methods being remediated).
- `utils/gate_calibration_loader.py` — loads K1/K2 from `src/config/gate_calibrations.json` (58 gates, 10 measured and 48 inferred).
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
- **F-11/F-11b**: the canonical topology is `src/config/network.json`, REGENERATED from the gate-id naming grammar (`core.network_topology.edges_from_names`) and locked by test. The historical variants (incl. `munbon_network_updated.json`, whose star wiring was wrong on laterals) are deleted — never resurrect them.
- **Typed routing topology (PR 2.1a)**: `src/config/routing_topology.json` is DERIVED from network + geometry_coverage + canal_geometry by `core/routing_topology.derive_routing_topology()` (59 elements: 1 boundary / 42 transport / 13 branch / 3 withdrawal; single virtual junction `J(LMC,0+170)` splits the composite M(0,0)→M(0,2) span, Waste Way re-parents to it). Only TRANSPORT elements carry reach responses — model-release coverage, transient states, and snapshot/offline coverage are transport-only (42). `config_loader.load_routing_topology()` re-derives at startup and fails closed on any element/hash/lineage drift; the artifact is an interchange copy, never a second source of truth. Snapshot API and offline case contracts are **schema v2** (scada_graph vs routing_topology vs transport_response_coverage split). Never hand-edit the artifact; regenerate via `scripts/build_scada_config.py`.
- The saint-venant/manning/rating model façades were DELETED (Wave 1.4); their routes answer 501. Real modeling arrives with the scheduler/SCADA waves.
- All tests live under `tests/`; bare `pytest` from the service root is the gate (script-style src tests were purged in Waves 1.8–1.9).
