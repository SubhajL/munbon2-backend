# Munbon backend — implemented architecture and ownership

Updated: 2026-11-02, Asia/Bangkok. [Development completion register](docs/development/DEVELOPMENT_COMPLETION_REGISTER.md) owns current named-scope status; [supersession index](docs/development/PLAN_SUPERSESSION_INDEX.md) preserves historical architecture/plans. [CLAUDE.md](CLAUDE.md) owns development policy.

This document describes inspected source, not fresh production inventory or permission to operate a system. There is **no root workspace**, root build, Turborepo or pnpm workspace. Services are standalone Node.js/JavaScript/TypeScript and Python applications; historical Go/Java/Kubernetes aspirations are not evidence those service implementations or deployment states exist.

## Smart Farm ownership boundary

Canonical service: `services/smartfarm-water-control`. Related smart-farm BFF, moisture/weather services remain their own artifacts; verify their current contracts before changing them. `services/smart-farm-water-control` is a legacy directory with one tracked template, not a second implemented control service. P07 owns exact retirement; do not recursively delete ignored files or inspect/copy secrets.

- Node/Express entrypoint: `services/smartfarm-water-control/src/index.js`; services and repositories are under its `src/`.
- Sensor/outbox database: Timescale/PostgreSQL `sensor_data`, including `water_control_smartfarm.sensor_readings_outbox`. Planning/config/snapshot storage uses the separately configured `munbon_dev` database, including `ros_gis_smartfarm`/smartfarm configuration tables. Follow actual pool ownership; a PostgreSQL trigger cannot cross databases implicitly.
- Valve commands use the MSSQL smartfarm command adapter, distinct from canal gate actuation. Sharing sensor infrastructure does not make those command contracts interchangeable.
- Existing dedicated listeners/outbox mechanisms are delivered, but P02 still owns failure acknowledgement, overlap/claim ownership, post-send uncertainty, producer migrations, lifecycle and missing executable worker aliases. Do not describe this runtime as reliability-complete.
- Approved target: durable outbox is sole automatic processing owner; LISTEN wake-up only; aliases reuse shared factories; valve commands independently default-deny, with no dark MSSQL initialization; uncertain outcomes held without automatic replay. These are contracts for upcoming work, not assertions that the current source already enforces every invariant.
- P02-D supplies a **separate** dark smartfarm PM2/preflight artifact. Do not insert smartfarm into the accepted canal process set or apply Scheduler migration assumptions to its outbox.

Smart Farm work must not incidentally change canal planning/scheduler/Flow/SCADA source. Read counterparts only to verify shared API/schema contracts; announce any proposed shared sensor schema, mapping, message/topic/key or command-payload change before implementation.

## Irrigation Canal ownership boundary

Main implemented path:

1. `services/ros-gis-integration` Python daily requirement producer/loader publishes canonical ROS/Excel demand with immutable dataset provenance.
2. `services/bff-water-planning/src/main.py` registers control-plan, authoritative-roster and planning-depth v1/v2 routers. It owns planning-depth mutation/rate enforcement; Scheduler supplies effective-principal authorization.
3. `services/scheduler` Python auth, planning lifecycle and bounded shadow/operator-approved dispatch compose planning and downstream validation.
4. `services/flow-monitoring` Python/FastAPI provides canonical hydraulics, prediction/model lineage and readiness. Its engineering-prior release is not field commandability approval.
5. `services/scada-gate-control` Node/TypeScript provides guarded validation/execution receipts and immediate readback. A delivered route is not permission for PLC/field writes.
6. The separate `smart-cms-app` frontend contains delivered dark control-plan/read/write/proxy source. Its own AGENTS.md requires both existing exact-clean-candidate local gates. Frontend visibility is not backend authorization.

Entrypoints/configuration:
- BFF: `services/bff-water-planning/src/main.py` and its actual `app.include_router` calls.
- Scheduler: `services/scheduler/src/main.py` and `src/jobs/shadow_dispatch_once.py`.
- Flow: `services/flow-monitoring/start.sh` applies owned migrations before the configured Uvicorn process.
- SCADA: `services/scada-gate-control/src` entrypoint specified by its package and PM2 builder.
- Tracked canal PM2 wrapper/builder: `infra/pm2/ecosystem-irrigation.config.js` and `build-irrigation-config.ts`. The builder already registers `scheduler-control-dispatch` as `-m jobs.shadow_dispatch_once`, a bounded one-shot relaunched by PM2. It is not a missing FastAPI background loop.
- Periodic reconciliation currently receives `baselines={}`. This is a deliberate field-baseline boundary; immediate execution readback is implemented separately. C-FIELD must lock approved versioned expected-baseline semantics before changing that boundary.

Irrigation Canal work must not incidentally change Smart Farm source/automatic consumers. Shared `sensor_data`, `munbon_dev`, `sensor_management` and external interface changes require explicit cross-lane coordination. No second scheduler, canonical demand producer or duplicate hydraulic algorithm.

## Data and immutable contracts

- Active planning roster: `ros_gis.sections_current` joined to active dataset versions; 41 sections/six zones/45,204 rai with approved hybrid provenance. Old raw-GIS 47,385-rai instructions are superseded for this interface.
- BFF `water_planning.planning_depth_submissions`/values retain RID ending-year calendar, immutable provenance and three-decimal contracts. Supersession replay returns the original receipt under current source/tests.
- Canonical ROS demand/publication ownership stays with ROS-GIS. Legacy ROS/RID-MS/AquaCrop/sync paths need explicit F-06/F-09 caller dispositions; their existence must not be hidden under universal unification claims.
- Migration numbering/ownership follows current tracked manifests. ROS `0004` already means dataset-version immutability; old W4 numbering is not reusable. W4 stays persist-only unless separately selected.
- Timescale/PostGIS/Postgres, Redis and command adapters are actual dependency boundaries, not permission to reuse a shared local database. Integration requires owner-approved disposable identity, fixture data and compatible runtime/image versions. Loopback alone proves no ownership.

## Active supporting source

- Sensor ingestion/chart API: `services/sensor-data` Node/TypeScript, including `src/cmd/consumer/main.ts`; not a Go service. P06-S must repair required-processing-failure acknowledgement and establish safe unit/real-lab selectors. Do not run existing integration defaults against operator data.
- Notifier: `services/daily-chart-notifier` tracked TypeScript email source. Ignored local Telegram output is separate artifact drift, not committed source. P03/P04 own clean build and truthful bounded log-window coverage.
- RID-MS: restored Node `JobScheduler` supplies boot/cron wiring; its daily source-check callback remains a logging scaffold. F-08-boot and F-08-ingest are distinct statuses.
- Older/experimental service directories, Dockerfiles, cloud workflows and infrastructure manifests require fresh source/reachability/owner qualification before being counted in the supported release. Their presence is not a deployment inventory.

## Local evidence and operations

`ops/control-plan-read-local/orchestrate.py` and `run-stage-suite.py` already implement the current ten local stages and LOCAL-RC-1 wrapper. Preserve their exact acceptance/campaign families; do not rebuild them or invoke a nonexistent `aws-inventory` action.

Accepted runtime remains backend `a26c0fd000b0b6da443135ffeadb992eded8fb5b` with frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`. Current backend baseline `2a53090c608331b282e331502ae1ec5851ae9c15` is a later documentation/static-test descendant, not automatically runtime-accepted. P01 performs no fresh guest, DB, queue, browser, production-health or live-gate probe.

Use per-service package/venv commands from canonical service guides, with pinned application runtimes. Host Node/Python availability is not permission to replace application-pinned Node/Linux/Python environments. Ports, hosts, credentials, targets and live process inventory must be read from separately authorized current configuration—not copied from historical examples into a new artifact.

Source delivery, local gates, real-DB qualification, hosted checks, effective repository governance, security closure, exact local runtime acceptance, deployment and activation are separate states. None grants the next. Credential response/history verification and main protection have named owner gates in the register; actual changes need separate authorization.
