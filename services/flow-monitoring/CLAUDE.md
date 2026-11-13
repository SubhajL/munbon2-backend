# flow-monitoring — gate hydraulics & demand→gate control

**Python 3 / FastAPI** · Entry: `src/main.py` (`app = FastAPI(...)`, `uvicorn.run(port=settings.port)`) · **Extends [../../CLAUDE.md](../../CLAUDE.md)**

## Purpose
Computes canal/gate hydraulics for the Munbon network: gate flow law (K1/K2 rating), required gate openings, demand→gate aggregation over the network graph, and (intended) SCADA command generation. Current source/remaining gates are tracked in the [Development completion register](../../docs/development/DEVELOPMENT_COMPLETION_REGISTER.md). `docs/remediation/` retains historical specifications and per-PR verdicts; it is not a fresh status checklist.

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

## Migrations (PR 4.1)
Tracked DDL pairs in `migrations/` (`<id>.up.sql`/`<id>.down.sql`; scoped .gitignore
negation past the blanket `*.sql` guard). Commands:
`python migrations/migrate.py apply|rollback <id>` and `status` — one transaction per
migration, pair checksums in `flow_monitoring.schema_migrations`, drift refuses apply AND
rollback, `POSTGRES_URL` only (no default host). `0001_prediction_persistence`:
`flow_monitoring.prediction_runs` + `prediction_artifacts` (content-addressed run id,
deferred composite FK so a committed header provably has its exact artifact, immutability
triggers, ONE zlib canonical artifact — never per-timestep rows or release-parameter
copies). Runtime NEVER creates this schema: lifespan probes `to_regclass` and the
prediction routes answer 503 until the migration is applied. Integration tests skip unless
`FLOW_PREDICTION_TEST_POSTGRES_URL` names a disposable LOOPBACK database.

## Deploy / runtime (PR 4.4a-2)
PM2 is the documented topology (`infra/pm2/build-irrigation-config.ts`) — the EC2
Docker workflow `.github/workflows/deploy-flow-monitoring.yml` was **retired**
(no tracked Dockerfile; locked removed by `test_legacy_gates_quarantine.py`).
`start.sh` is **migrate-before-start**: it runs `migrations/migrate.py apply-all`
and `exec`s uvicorn ONLY on success (a checksum drift / unreachable DB aborts
startup so PM2 never boots a falsely-ready process). PM2 wires
`HYDRAULIC_MODEL_RELEASE_PATH=data/model-releases/engineering-prior-v5-v1.json`

`HYDRAULIC_COMMANDABILITY_APPROVAL_PATH` is optional and dark by default. When unset,
model snapshots remain byte-compatible schema v3 with every commandability gate false.
When set, the capped external schema-v1 approval must reproduce its content hash and
exactly bind the loaded release, prediction engine, five model-config hashes, operating
envelope, D6 capability pair, pilot gate scope, and attestation. Only an approved document
emits snapshot v4; set-but-invalid configuration fails startup/readiness.
(committed `commandable=false`). `/health` is process liveness ONLY; `/ready`
(`core/readiness.check_flow_readiness`) is dependency truth — 503 unless Postgres
is healthy, a valid commandable=false release is loaded, the prediction service is
initialized, and both prediction tables + the migration checksum are present. No
host/cred/exception leaks in either body.

## Integration
- Consumes canonical demand from **ros-gis-integration** (`ros_gis` schema / HTTP). Scheduler/SCADA validation, guarded approved-execution and immediate readback source are delivered (F-02's dark/shadow boundary). Periodic reconciliation still receives empty approved baselines; field/pilot/D6/model-commandability integration and actual actuation acceptance remain separate owner-gated work. Do not rebuild a missing bridge or infer physical authority from source wiring.

## Gotchas / Watch-outs
- **C10**: historical duplicate K1/K2-law implementations were retired; `core/gate_flow.py` is the canonical rating law, guarded by regressions. Never add another implementation or resurrect deleted variants because an old finding list names them. The retained `gate_hydraulics.py` classic-orifice model is a separate forward solver used through `hydraulic_solver.py` and the dual-mode controller; do not conflate it with a retired duplicate K1/K2 rating implementation.
- **F-01 source-complete**: corrected rating/clamping/inversion source and `tests/unit/test_gate_flow.py` are delivered. The old inverted-law blow-up is a historical defect, not current source status. Preserve regressions; new physics requires a new RED/domain contract. Source correctness does not establish field calibration.
- **F-04 source-complete**: `core/canal_capacity.py` and `tests/unit/test_canal_capacity.py` provide real per-reach capacity/limit source, replacing the historical 15.0 stub. Preserve those regressions.
- **F-11/F-11b**: the canonical topology is `src/config/network.json`, REGENERATED from the gate-id naming grammar (`core.network_topology.edges_from_names`) and locked by test. The historical variants (incl. `munbon_network_updated.json`, whose star wiring was wrong on laterals) are deleted — never resurrect them.
- **Engineering-prior release (PR 2.1c)**: `data/model-releases/engineering-prior-v5-v1.json` is GENERATED by `scripts/build_hydraulic_model_release.py` from `engineering-prior-policy-v1.json` + the five canonical artifacts (byte-reproducible, clock-free, lineage byte-hashed; `--check` verifies). 41 transports parameterized (Muskingum-Cunge t10/t90 surrogate at the policy reference flow, seepage loss, 90%/75% derated capacity by terminating-gate calibration_method), the 170 m flume explicitly unavailable. Never hand-edit either JSON; runtime release loading is fail-closed, and `HYDRAULIC_COMMANDABILITY_APPROVAL_PATH` stays UNSET/dark unless separately authorized.
- **Operator withdrawals (PR 2.1b)**: Waste Way/FTO releases are typed `OperatorWithdrawalEvent`s targeting canonical structure node ids (e.g. `M(0,0;1,0)`), held step-function style until replaced. Withdrawal leaves at the structure's upstream junction BEFORE downstream allocation (withdrawal edges never take caller branch fractions); predicted = min(planned, available, authoritative q_max if present); shortfall and `capacity_check_status` are explicit per step. V5 provides authoritative capacities for both FTO structures while Waste Way remains unavailable; `withdrawn_m3` is its own mass-balance category — never conveyance loss or agricultural delivery. Offline case schema is **v3** (events + sealed capacity map, CLI-verified against gate_calibrations). No event = zero withdrawal.
- **Typed routing topology (PR 2.1a)**: `src/config/routing_topology.json` is DERIVED from network + geometry_coverage + canal_geometry by `core/routing_topology.derive_routing_topology()` (59 elements: 1 boundary / 42 transport / 13 branch / 3 withdrawal; single virtual junction `J(LMC,0+170)` splits the composite M(0,0)→M(0,2) span, Waste Way re-parents to it). Only TRANSPORT elements carry reach responses — model-release coverage, transient states, and snapshot/offline coverage are transport-only (42). `config_loader.load_routing_topology()` re-derives at startup and fails closed on any element/hash/lineage drift; the artifact is an interchange copy, never a second source of truth. Snapshot API is **schema v2** (scada_graph vs routing_topology vs transport_response_coverage split); the offline case contract is **v3** as of PR 2.1b (see the operator-withdrawals bullet). Never hand-edit the artifact; regenerate via `scripts/build_scada_config.py`.
- The historical saint-venant/manning/rating façades were retired (Wave 1.4). Real prediction/model-lineage source now exists; the engineering-prior release remains planning-only without separate field/model commandability approval. Do not treat old roadmap language as missing source.
- All tests live under `tests/`; bare `pytest` from the service root is the gate (script-style src tests were purged in Waves 1.8–1.9).
