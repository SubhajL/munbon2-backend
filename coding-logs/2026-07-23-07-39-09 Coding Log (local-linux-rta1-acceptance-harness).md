# Local Linux RTA-1 acceptance harness plan

Date: 2026-07-23

Status: planning complete; implementation not started

Repository baseline inspected: `main == origin/main == 8095bfe37550200da00ecb554edc646febf8aff9`

## Decision summary

Build a disposable, isolated `amd64` Debian 12 OrbStack machine with 8 GiB RAM,
4 CPUs, and 40 GiB disk. Run PostgreSQL/PostGIS, Redis, InfluxDB, central auth,
PM2, and the four RTA services inside that one Linux machine. Transfer an exact
Git bundle into the machine and check out `8095bfe37550200da00ecb554edc646febf8aff9`.
Run the existing tracked RTA scripts unchanged.

This is a local rehearsal of the landed software and operating procedure. It
does not accept the current EC2 host, remove its CAP-1 failure, authorize a host
move/resize, or activate any producer, write, visibility, authority, or
execution lane.

## Goals

- Exercise the actual Linux `/proc` capacity gate, PM2 lifecycle, loopback
  bindings, four isolated Python environments, migrations, five-minute
  stability gate, and real bearer verifier before another server attempt.
- Use exact source SHA `8095bfe37550200da00ecb554edc646febf8aff9` by
  default; accepting a later `origin/main` remains an explicit operator choice.
- Keep application traffic and data local to a disposable Linux machine.
- Generate a sanitized evidence bundle that maps directly to RTA-1 steps 1-12.
- Preserve all existing dark defaults and stop on the existing capacity limits.

## Non-goals

- No SSH, files, credentials, data, PM2 changes, or deployment changes on EC2.
- No weakening of the 512 MiB `MemAvailable` or 1 GiB used-swap limits.
- No source change to `ops/control-plan-read-runtime/*` unless a failing test
  proves a defect in those scripts.
- No commandability, authority issuance, ROS automatic production, control-plan
  UI activation, or planning-depth write activation.
- No claim that a local pass completes official RTA-1 on the production host.
- No reuse of the Mac's existing `munbon-local-*` containers, databases, ports,
  volumes, or credentials.

## Current evidence and constraints

- Current backend `HEAD` and `origin/main` are the accepted `8095bfe3...` SHA.
- The primary checkout already has user-owned untracked `.codex/` and historical
  roadmap-log state; implementation must use a new isolated worktree.
- OrbStack 2.2.0 and Docker are available. The Mac has 24 GiB RAM and currently
  has ports 3005, 3011, 3021, 3022, and 3047 free.
- An OrbStack isolated machine has no Mac filesystem mount, host networking, or
  forwarded SSH agent by default. With `--isolate-network`, it also cannot reach
  other OrbStack machines or host IPs while retaining package-download access.
- Debian 12 supplies CPython 3.11 natively, avoiding a host Python overlay.
- Flow startup needs PostgreSQL, Redis, Timescale-compatible PostgreSQL, and a
  reachable InfluxDB even though only PostgreSQL gates its `/ready` response.
- ROS migration `0001` requires PostGIS. The Timescale extension is optional in
  the current Flow client; plain PostgreSQL remains usable for this read-only
  rehearsal.
- Central auth is a prerequisite on loopback port 3005 and is not one of the
  four PM2 processes. A disposable local operator must be seeded because no
  production credential or database may be reused.
- The repository central preflight expects `services/{flow-monitoring,scheduler}/venv`,
  while the RTA wrappers correctly use `.venv`. Local untracked `venv -> .venv`
  compatibility symlinks satisfy preflight without a second installation or a
  tracked production change.
- The central preflight validates the Scheduler plus the bounded worker topology,
  but RTA activation intentionally starts only Flow, Scheduler, ROS, and BFF
  from `ops/control-plan-read-runtime/ecosystem.config.cjs`. Preflight validation
  must not be confused with starting the worker.
- Control-plan visibility is a frontend build-time concern and planning-depth
  writes are later W1/W2/FE work. The backend rehearsal can prove the landed
  runtime's producer/execution/commandability settings, but cannot turn absent
  future features into runtime flags.

## Plan Draft A — isolated native Linux host

### Shape

1. Create `munbon-rta1-local` with:
   `orb create --arch amd64 --memory 8G --cpus 4 --disk 40G --isolated --isolate-network debian:12 munbon-rta1-local`.
2. Keep Mac mounts and SSH-agent forwarding disabled.
3. Create a temporary Git bundle from local commits, copy it with `orb push`,
   clone it inside Linux, and detach at the exact accepted SHA. Do not copy the
   dirty working tree.
4. Install OS prerequisites inside the disposable machine: build tools,
   CPython 3.11 venv tooling, PostgreSQL/PostGIS, Redis, InfluxDB 2, Node.js,
   `promtool`, Git, and a pinned PM2.
5. Bind PostgreSQL, Redis, InfluxDB, auth, and the four application services to
   loopback only. Generate all local-only passwords/tokens inside Linux and
   store them in mode-600 files outside the source checkout.
6. Create the local database, PostGIS extension, Influx org/bucket/token, and an
   auth schema. Use TypeORM's development synchronize only in this disposable
   auth database, then idempotently seed one `operator` role and operator user.
7. Run auth as a user systemd service on `127.0.0.1:3005`; keep PM2 limited to
   the four tracked RTA applications.
8. Install each Python service from its own tracked `requirements.txt` into its
   own `<service>/.venv`; run `pip check`; install auth and infra Node packages
   with their tracked lockfiles.
9. Run monitoring validation and the repository central preflight, then call the
   existing `activate.sh`, the existing bearer verifier, and the evidence
   collector.

### Advantages

- Highest useful parity with the target: one Linux host, real `/proc`, PM2,
  loopback service URLs, systemd, and exact tracked wrappers.
- Strongest isolation from the Mac and all existing local Munbon data.
- A failure is meaningful because it exercises the same stop conditions and
  ordering as RTA-1.
- Clean rollback: stop named processes or explicitly delete one disposable
  machine after evidence is copied.

### Disadvantages

- Longer first provision because PostGIS and InfluxDB are native services.
- `amd64` on Apple Silicon is emulated and slower than an arm64 machine.
- The harness must carefully validate package versions and native service
  readiness before application startup.

## Plan Draft B — normal Linux machine plus Mac Docker dependencies

### Shape

1. Create a non-isolated OrbStack Linux machine for the application processes.
2. Run PostgreSQL/PostGIS, Redis, and InfluxDB as dedicated Docker Compose
   containers managed from macOS.
3. Connect the Linux services to forwarded container ports through
   `docker.orb.internal`; keep Flow, Scheduler, ROS, BFF, and auth in Linux.
4. Run the same PM2, stability, migration, and bearer steps.

### Advantages

- Faster dependency provisioning and teardown.
- Container image versions are easy to pin.
- Avoids installing database services into the Linux machine.

### Disadvantages

- A normal machine can reach Mac files and the host network, which is a weaker
  safety boundary for npm/PyPI install scripts.
- Dependencies are no longer on the same loopback host, so the topology is less
  representative of RTA-1.
- Two lifecycle controllers—Docker on macOS and systemd/PM2 in Linux—make
  evidence and rollback more complex.
- Existing local containers and ports increase the chance of accidental reuse
  or collision.

## Comparative synthesis

Draft A is selected. The extra native provisioning cost is paid once and buys
the properties that matter most here: a single Linux capacity boundary, exact
loopback topology, real PM2 behavior, and isolation from the Mac and production.
Draft B remains a useful future CI smoke-test shape, but it is not strong enough
to be called an RTA-1 operating-procedure rehearsal.

The selected design borrows Draft B's version-pinning discipline, but not its
host Docker dependencies.

## Unified execution plan

### Phase 1 — add a tested local harness in an isolated worktree

Create a detached implementation worktree from current `origin/main`; do not
edit the dirty primary checkout. Use TDD in this order:

1. Add failing unit tests for accepted-SHA validation, exact OrbStack isolation
   flags, local endpoint allowlisting, port gates, secret-safe command output,
   and RTA step ordering.
2. Add failing tests for evidence redaction and the invariant that `pm2 save`
   cannot be scheduled before capacity, preflight, startup, stability, and
   bearer success.
3. Add an env-contract test asserting the actual runtime allowlist:
   `CONTROL_EXECUTION_MODE=disabled`, readback `off`, `GATES_API_ENABLED=false`,
   ROS enabled/startup/schedule flags false, no SCADA base URL, and only
   loopback service/dependency URLs.
4. Add a disposable-PostgreSQL integration test for idempotent auth bootstrap:
   schema synchronization, one operator role, one active operator user, bcrypt
   password hashing, and repeat-safe seeding.
5. Implement the smallest orchestration functions needed to make those tests
   pass. Keep shell fragments bounded and use argument arrays rather than
   interpolated commands wherever possible.

Planned files:

- `ops/control-plan-read-local/orchestrate.py`
  - validate tools/resources/ports and a full accepted SHA;
  - create/push the Git bundle and local harness;
  - create and address the isolated machine;
  - run named phases with fail-closed state tracking;
  - pull only the sanitized evidence directory.
- `ops/control-plan-read-local/bootstrap-linux.sh`
  - install pinned OS/runtime prerequisites;
  - configure loopback PostgreSQL/PostGIS, Redis, and InfluxDB;
  - create service-local venvs from all four manifests;
  - install auth/infra packages from lockfiles;
  - never install Python packages into system Python.
- `ops/control-plan-read-local/seed-local-operator.js`
  - initialize the disposable auth schema with real TypeORM entities;
  - idempotently upsert the exact `operator` role/user;
  - accept credentials only through environment/file descriptors and print no
    credential values.
- `ops/control-plan-read-local/run-linux-acceptance.py`
  - execute RTA steps 1-12 around the unchanged tracked runtime scripts;
  - query only allowlisted PM2/process environment fields;
  - write sanitized structured evidence and stop on the first failed gate.
- `ops/control-plan-read-local/systemd/munbon-local-auth.service`
  - run central auth on loopback from the exact checkout and a mode-600 env file.
- `ops/control-plan-read-local/tests/test_orchestrate.py`
- `ops/control-plan-read-local/tests/test_run_linux_acceptance.py`
- `ops/control-plan-read-local/tests/test_seed_local_operator.py`
- `docs/operations/CONTROL_PLAN_LOCAL_LINUX_ACCEPTANCE.md`
  - prerequisites, one-command lifecycle, evidence interpretation, known local
    versus production boundary, rerun behavior, and explicit cleanup.

Do not edit `ops/control-plan-read-runtime/*` in this phase. If a real test shows
a defect there, stop and propose a separately reviewed, tests-first fix.

#### Function and test outline

`orchestrate.py` should remain a small functional CLI rather than a class-based
framework:

- `parse_args(argv)`: require `plan|provision|run|collect|teardown`, default the
  source SHA to the recorded accepted SHA, and require an explicit evidence root.
- `validate_accepted_sha(repo, sha)`: require a full lowercase 40-character SHA,
  prove the object is a commit, and reject anything other than `8095bfe3...`
  unless `--accept-later-origin-main` is supplied and the SHA equals a freshly
  fetched `origin/main`.
- `inspect_host()`: return bounded RAM/disk/tool/port facts without environment
  variables or process command lines.
- `build_machine_command(spec)`: return the exact argument array containing
  `amd64`, resource limits, `--isolated`, and `--isolate-network`.
- `create_source_bundle(repo, sha, temp_dir)`: create a Git bundle containing the
  accepted commit and verify it with `git bundle verify`.
- `invoke_orb(machine, argv)`: run one bounded remote command without a shell,
  time out, and map failures to fixed safe phase codes.
- `collect_evidence(machine, remote_dir, local_dir)`: pull only the declared
  sanitized filenames and verify their SHA256 manifest.
- `resolve_owned_machine(name)`: require the exact ownership marker before any
  stop or deletion command.

`run-linux-acceptance.py` should expose:

- `validate_runtime_urls(config)`: parse every URL and allow only loopback hosts.
- `capture_host_snapshot()`: project `/proc/meminfo`, swap, kernel, safe PM2 state,
  and allowlisted listeners into a typed dictionary.
- `run_checked(step, argv, timeout)`: capture bounded output, redact before write,
  record first failure, and never continue a failed phase.
- `collect_migration_parity()`: read only migration IDs/checksums and exact BFF
  object/checksum evidence.
- `collect_dark_runtime_contract()`: resolve four PM2 PIDs, select only named
  non-secret environment keys, and record required absence as booleans.
- `run_rta_steps()`: encode steps 1-12 as an ordered state transition in which
  migration/preflight precedes activation, bearer follows stability, and save
  confirmation is last.
- `write_evidence_bundle()`: serialize only the evidence schema below using
  atomic rename and mode 600, then create `SHA256SUMS`.

`seed-local-operator.js` should export one testable `seedLocalOperator(dataSource,
input)` function. It must look up by canonical email/role name, create or update
only that disposable identity, use the real entity hook to hash a changed
password, attach exactly the `operator` role, and return only `{created,
roleCreated}` booleans. Its CLI wrapper must never return user IDs, email, or
password.

Required tests:

- `test_build_machine_command_requires_amd64_resource_and_both_isolation_flags`
- `test_validate_accepted_sha_rejects_short_unrelated_and_stale_origin_sha`
- `test_validate_runtime_urls_rejects_every_non_loopback_host`
- `test_run_rta_steps_stops_at_each_failed_gate`
- `test_run_rta_steps_cannot_save_before_stability_and_bearer_pass`
- `test_capture_host_snapshot_never_contains_env_commandline_or_dsn_keys`
- `test_collect_dark_runtime_contract_reports_only_the_allowlist`
- `test_write_evidence_bundle_rejects_secret_shaped_values_before_export`
- `test_seed_local_operator_is_idempotent_and_hashes_the_password`
- `test_seed_local_operator_assigns_exactly_the_operator_role`

#### Cross-language and artifact contracts

The macOS Python orchestrator writes `run-request.json` for the Linux runner with
only these fields: `schema_version`, `run_id`, `accepted_sha`, `machine_name`,
`source_bundle_name`, `evidence_dir`, and numeric resource limits. JSON must use
`additionalProperties: false` validation in both producer and consumer. It must
not contain URLs or credentials.

The Python runner passes auth bootstrap inputs to Node only as process
environment variables read from a mode-600 file: `LOCAL_OPERATOR_EMAIL`,
`LOCAL_OPERATOR_PASSWORD`, and local `DATABASE_URL`. Node returns a one-line JSON
object containing only `schema_version`, `created`, and `role_created`.

Each evidence JSON file has top-level `schema_version`, `run_id`, `local_only:
true`, `accepted_sha`, `captured_at`, and a file-specific `checks` object. All
schemas reject additional fields so a newly introduced raw diagnostic cannot
silently enter the export set.

### Phase 2 — provision the isolated Linux machine

1. Recheck Mac RAM/disk and ports 3005/3011/3021/3022/3047.
2. Refuse an existing machine named `munbon-rta1-local` unless it has the exact
   harness ownership marker. Never overwrite an unrelated machine.
3. Create the `amd64` Debian 12 machine with 8 GiB/4 CPU/40 GiB,
   `--isolated`, `--isolate-network`, and no mounts/SSH forwarding.
4. Push a Git bundle and clone into `/opt/munbon-rta1/source`; detach at the
   accepted full SHA and prove `git status --porcelain --untracked-files=no` is
   empty.
5. Bootstrap packages and record OS/kernel/architecture/Python/Node/npm/PM2/
   PostgreSQL/Redis/InfluxDB/promtool versions.
6. Configure every dependency to loopback. Before writing env files, parse every
   URL and reject hosts outside `{127.0.0.1, localhost, ::1}`. Explicitly reject
   the known production IP as a defense-in-depth test, not as the only guard.
7. Generate fresh local credentials; create mode-700 config directories and
   mode-600 service/auth/verifier env files. Never copy any existing `.env`.
8. Initialize dependencies, seed auth, start its systemd unit, and require
   dependency-backed auth readiness on `127.0.0.1:3005`.

### Phase 3 — install and validate without activating PM2

1. Build Flow, Scheduler, ROS, and BFF `.venv` environments one at a time from
   their four exact manifests; record only package-check verdicts and resource
   readings, never full environment dumps.
2. Create untracked `venv -> .venv` symlinks only for Flow and Scheduler to meet
   the current repository preflight's required-path contract.
3. Run each service's relevant unit/integration tests plus the existing runtime
   script tests. Run `npm --prefix infra/pm2 ci`, `verify`, and `build`.
4. Stage the monitoring files under the disposable machine's
   `/etc/prometheus`, with local non-example target files, then run:
   `promtool check config` and `promtool check rules`.
5. Apply migrations through the exact tracked runners:
   - Flow: all tracked Flow migrations;
   - Scheduler: through `0013_operator_approved_execution` with full checksum
     parity;
   - ROS: through `0003_daily_requirement_producer`;
   - BFF: exact tracked `009_crop_registry.sql`.
6. Run the repository central preflight against the full accepted SHA and the
   disposable PostgreSQL evidence. Provide only generated local placeholder
   values for required-but-dark ecosystem settings. Do not start
   `scheduler-control-dispatch`.

### Phase 4 — execute the local RTA-1 rehearsal

Map the run exactly to the original 12 items:

1. Capture timestamp, Linux host identity hash, OS/kernel/architecture, exact
   SHA, safe PM2 projection, restart counts, `/proc/meminfo`, swap, and listeners.
2. Require exact accepted source and a clean tracked tree.
3. Run the unchanged capacity gate and require both original thresholds plus no
   conflicts on 3011/3021/3047/3022; also reserve auth 3005 locally.
4. On failure, stop. Do not lower the gate or auto-recreate a larger machine.
5. Confirm the four service-local venvs and `pip check` verdicts.
6. Query migration registries/checksums and BFF 009 object parity.
7. Record `promtool`, infra verify/build, and central preflight verdicts.
8. Start exactly four PM2 apps through the tracked ecosystem/wrappers.
9. Read only allowlisted live process settings and readiness identity to prove
   Scheduler execution/readback dark, Flow gates API off and model release
   noncommandable, ROS automatic producers off, and SCADA trust inputs absent.
   Record frontend visibility and future planning-depth writes as outside this
   backend-local runtime, not falsely as activated or accepted.
10. Let the unchanged `activate.sh` enforce startup plus a continuous 300-second
    dependency-backed readiness window with unchanged restart counts.
11. Load the generated local operator credentials into the verifier process,
    run the unchanged bearer verifier, capture fixed PASS/FAIL/status/header
    verdicts only, and confirm no token appears in files or logs.
12. Confirm `pm2 save` occurred only after the stable window. Hash and pull the
    sanitized evidence bundle to
    `~/munbon-rta1-evidence/<UTC-run-id>/` on macOS.

### Phase 5 — evidence contract

Retain only:

- `run-manifest.json`: local-rehearsal label, exact SHA, UTC timestamps, tool
  versions, and phase verdicts;
- `host-before.json` and `host-after.json`: sanitized resource/listener/process
  projections;
- `migration-parity.json`: IDs and checksums, with no DSN;
- `monitoring-preflight.json`: promtool and repository-preflight verdicts;
- `readiness-stability.json`: four listeners/statuses, baseline/final restart
  counts, 300-second duration, and sample count;
- `bearer-verdicts.txt`: the verifier's fixed safe output only;
- `dark-flags.json`: allowlisted actual values/absence plus explicit scope notes
  for frontend visibility and unlanded planning-depth work;
- `SHA256SUMS` over the evidence files.

Never retain env files, `/proc/*/environ`, PM2 raw `jlist`, database URLs,
operator passwords, cookies, access/refresh tokens, response bodies, or Influx
tokens in the evidence bundle.

### Phase 6 — validation gates for the harness change

Run from the isolated implementation worktree:

1. New pure unit tests for orchestration, fail-closed ordering, allowlists, and
   evidence redaction.
2. New auth bootstrap integration test on a disposable loopback PostgreSQL.
3. Existing `ops/control-plan-read-runtime` tests unchanged.
4. `npm --prefix infra/pm2 run verify`.
5. Python formatting/lint/type checks appropriate to the added files.
6. QCHECK and formal `g-check` review.
7. Conventional commit and a normal OPS PR containing behavior, affected paths,
   test evidence, local-only credentials boundary, flags, and rollback notes.

### Phase 7 — rollback and cleanup

- A failed run stops/deletes only the four named PM2 applications created by the
  tracked RTA ecosystem and stops the local auth unit.
- Do not run down-migrations after the local runtime has written durable test
  data; discard the disposable database/machine or forward-fix a migration bug.
- Preserve the sanitized evidence and the first failed gate reason.
- Machine deletion is a separate explicit cleanup command and must resolve the
  exact ownership marker/name first. It is not automatic at the end of a pass.
- Cleanup never reaches EC2, existing Mac containers, other OrbStack machines,
  or user-owned worktrees.

## Failure modes and responses

| Failure | Required response |
| --- | --- |
| Mac resource/port preflight fails | Stop before machine creation; name the exact conflict. |
| Machine exists without ownership marker | Stop; do not reuse or delete it. |
| SHA is not full/accepted or tree is dirty | Stop before installs/migrations. |
| Any URL is non-loopback | Stop before writing env files. |
| Package or `pip check` failure | Stop; retain sanitized install verdict; no overlay fix. |
| Migration checksum mismatch | Stop; preserve DB and evidence; forward-fix only. |
| `promtool` or repository preflight fails | Stop before PM2 activation. |
| Capacity gate fails | Apply original RTA step 4 verbatim; do not resize automatically. |
| Startup/readiness/restart gate fails | Stop the four named PM2 apps; do not `pm2 save`. |
| Bearer lifecycle fails | Mark local rehearsal failed; preserve safe codes only. |
| Evidence redaction test fails | Do not export the evidence directory. |

## Wiring verification table

| Producer | Boundary | Consumer | Verification |
| --- | --- | --- | --- |
| Mac orchestrator | `orb create/push/pull` argument arrays | isolated Debian machine | unit command-shape tests plus ownership marker |
| Git bundle | full accepted commit | `/opt/munbon-rta1/source` | exact `rev-parse`, clean tracked tree |
| local secret generator | mode-600 env files | auth and four tracked wrappers | permission and loopback-URL tests |
| PostgreSQL/PostGIS | loopback DSN | Flow/Scheduler/ROS/BFF/auth | real migrations and dependency-backed readiness |
| Redis | loopback DB URLs | Flow/Scheduler/ROS/BFF/auth | startup and readiness probes |
| InfluxDB | local org/bucket/token | Flow startup | local `/health` and Flow startup verdict |
| auth seed | operator role/user | central auth login | real bearer verifier claims check |
| central auth | access/refresh lifecycle | Scheduler/BFF | login/list/detail/logout/reuse verifier |
| tracked wrappers | mode-600 service env | four PM2 processes | listener, process-name, env-allowlist evidence |
| Scheduler migrations | `scheduler.schema_migrations` | infra central preflight/readiness | full ID/checksum parity through 0013 |
| ROS migrations | `ros_gis.schema_migrations` | ROS readiness/runtime | parity through 0003 |
| BFF migration runner | `gis.crop_registry` | BFF/runtime | exact 009 checksum/object query |
| promtool | tracked YAML plus local targets | monitoring verdict | check config and check rules |
| `activate.sh` | capacity/snapshot/stability | PM2 saved state | save timestamp after 300-second pass |
| evidence collector | allowlisted projections | macOS evidence directory | redaction tests and SHA256 manifest |

## Success criteria

- The local machine is `amd64` Linux, isolated from Mac files/host/other
  machines, and runs exact accepted source with a clean tracked tree.
- All dependencies and five local application processes bind only to loopback;
  PM2 contains exactly the four RTA applications.
- All four service manifests install independently and pass package checks.
- Scheduler/ROS/BFF migration targets and Scheduler checksums match exactly.
- `promtool` and the repository central preflight pass.
- Original capacity thresholds pass before and after startup.
- Four exact listeners return dependency-backed `status: ready` continuously for
  five minutes with identical restart counts.
- The real bearer verifier passes login, authenticated Scheduler/BFF reads,
  missing detail, logout, and refresh reuse denial without persisting tokens.
- `pm2 save` occurs only after stability.
- Sanitized evidence is exported and contains no secrets.
- The result is reported as `LOCAL REHEARSAL PASS`, never as production RTA-1
  acceptance; the unchanged EC2 CAP-1 status remains explicit.
