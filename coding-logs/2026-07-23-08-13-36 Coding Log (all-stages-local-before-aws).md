# All stages local before AWS

Date: 2026-07-23

Status: final local-first sequencing plan; implementation not started

## Overview

Every roadmap stage will be implemented and exercised through a local equivalent
before any new AWS deployment, audit, cleanup, or cutover. AWS becomes a single
final promotion lane after one clean, combined local release-candidate run passes.

Local tests will use the real service entry points, databases, Redis, auth,
migrations, feature flags, and browser routes. Local source data is deterministic
acceptance data and is never relabeled as the real-data evidence required by the
production AC-1 gate.

## Verified baseline

- Backend `main == origin/main == 8095bfe37550200da00ecb554edc646febf8aff9`.
- Frontend local/remote `main == 3a16498a60927996ac38e741b276150968d0cadc`.
- FE-4 is already landed and remains dark by default.
- W1, W2, BFF migration 010, FE-5, and FE-6 are not yet landed.
- Physical development host is Apple M4 Pro arm64. The new isolated OrbStack
  guest must use native `arm64`, not emulated `amd64`.
- No AWS operation is authorized or scheduled before final local acceptance.

## Exploration note

Auggie semantic search timed out at the required two-second ceiling. Planning is
based on direct inspection and exact-string searches of `AGENTS.md`, `CONTEXT.md`,
the revised roadmap, the two local-first planning logs, runtime scripts, ROS
source-loader tables/invariants, Scheduler/BFF routes/tests/migrations, and the
current Smart CMS feature flags/routes.

## Goal

Produce backend and frontend release-candidate SHAs for which Stages 0-7 all
have passing local proofs—including local equivalents of runtime acceptance,
real-path data production, read activation, evidence rendering, planning-depth
writes, two-browser reconciliation, failure drills, and rollback—before touching
AWS.

## Non-goals

- No AWS SSH, probe, inventory, cleanup, stop, deletion, install, deployment, or
  spend before the final combined local gate passes.
- No claim that deterministic local data satisfies production AC-1.
- No commandability, SCADA command, Modbus write, authority issuance, or
  Scheduler execution activation locally or in AWS.
- No recurring/startup ROS production; the local producer is manual and bounded.
- No W4 recomputation implementation. DEC-W4 remains persist-only unless the
  user separately supplies and approves the missing product semantics.
- No editing of the historical roadmap or prior planning logs.
- No reuse of existing Mac databases, containers, credentials, or OrbStack
  Ubuntu guest.

## Locked local gate names

| Roadmap stage            | Local proof                |
| ------------------------ | -------------------------- |
| Stage 0 / BASE-0         | `LOCAL-BASE-0`             |
| Stage 1 / RTA-1          | `LOCAL-RTA-1`              |
| Stage 2 / AC-1           | `LOCAL-AC-1`               |
| Stage 2 / READ-ACT-1     | `LOCAL-READ-ACT-1`         |
| Stage 3 / ME-1 and FE-8  | `LOCAL-EVIDENCE-1`         |
| Stage 4 / W1 and W2      | `LOCAL-WRITE-FOUNDATION-1` |
| Stage 5 / FE-5 and FE-6  | `LOCAL-WRITE-UI-1`         |
| Stage 6 / DEC-W4         | `LOCAL-PERSIST-ONLY-1`     |
| Stage 7 / WRITE-ACT-1    | `LOCAL-WRITE-ACT-1`        |
| Combined clean candidate | `LOCAL-RC-1`               |

# Plan Draft A — build everything, test once at the end

## Overview

Implement remaining backend and frontend stages in dependency order using their
unit/integration suites, then provision the complete local environment once and
run all activation scenarios at the end.

## Files to change

- Add the local runtime harness and acceptance-data seeder under
  `ops/control-plan-read-local/`.
- Implement ME-1, W1, W2, FE-5, FE-6, and FE-8 in the exact files listed by the
  historical roadmap.
- Add local operations documentation at
  `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`.

## Implementation and TDD sequence

For each source slice:

1. Stub its focused tests.
2. Run and confirm failure for the intended missing behavior.
3. Implement the smallest passing change.
4. Refactor only when needed for clarity/testability.
5. Run formatter, lint/type checks, focused and service-full tests.

After all slices land, run LOCAL-BASE-0 through LOCAL-RC-1 once.

Functions follow the historical roadmap plus:

- `seed_local_approved_sources(conn, scenario)` writes deterministic source rows
  only into the disposable database.
- `run_local_stage(stage, context)` executes one named local gate.
- `collect_stage_evidence(stage, results)` writes a secret-safe stage manifest.

## Test coverage

- `test_seed_matches_approved_roster_invariants` — seeds 41 sections and 47,385 rai.
- `test_stage_runner_enforces_dependency_order` — rejects skipped prerequisite stage.
- `test_final_candidate_requires_every_stage` — refuses partial local evidence.
- Existing W1/W2/FE/ME tests — validate their planned behavior contracts.

## Decision completeness

- Public interfaces: all historical roadmap APIs/flags/contracts plus the local
  CLI and evidence schema described below.
- Failure behavior: any slice test failure blocks the final combined run.
- Rollout: no AWS; source PRs still land sequentially.
- Backout: revert unactivated source normally; discard disposable DB when needed.
- Success: one final full local run passes every stage.

## Dependencies and validation

- All remaining source work must finish before full integration feedback exists.
- Validation is one clean local provision and full stage suite.

## Wiring verification

| Component              | Entry point                | Registration                  | Schema/table                |
| ---------------------- | -------------------------- | ----------------------------- | --------------------------- |
| Local stage runner     | `run-stage-suite.py all`   | local operator CLI            | all disposable schemas      |
| Source seeder          | `seed-approved-sources.py` | LOCAL-AC-1 setup              | source tables listed below  |
| Remaining roadmap code | planned routes/clients     | service/frontend entry points | migration 010 and contracts |

## Draft A trade-offs

Advantage: fewer environment rebuilds and fewer local evidence ceremonies.

Gap: wiring failures are discovered late, after several dependent PRs land. A
bad ME/W1/W2 boundary can contaminate later work and make diagnosis expensive.

# Plan Draft B — progressive local promotion train

## Overview

Provision the local platform first, then require each roadmap stage to pass its
own real-path local gate before starting the next dependent stage. After all
incremental gates pass, rebuild from clean state and run the complete sequence
again as LOCAL-RC-1.

## Files to change

Local platform:

- `ops/control-plan-read-local/orchestrate.py`
- `ops/control-plan-read-local/bootstrap-linux.sh`
- `ops/control-plan-read-local/run-stage-suite.py`
- `ops/control-plan-read-local/seed-approved-sources.py`
- `ops/control-plan-read-local/seed-local-operators.js`
- `ops/control-plan-read-local/run-ros-manual-producer.sh`
- `ops/control-plan-read-local/systemd/munbon-local-auth.service`
- `ops/control-plan-read-local/tests/test_orchestrate.py`
- `ops/control-plan-read-local/tests/test_stage_suite.py`
- `ops/control-plan-read-local/tests/test_approved_sources.py`
- `ops/control-plan-read-local/tests/test_seed_local_operators.py`
- `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`

Roadmap source files remain those already specified for ME-1, W1, W2, FE-5,
FE-6, and FE-8. FE-4 is not reopened unless its local gate proves a defect.

## Implementation and TDD sequence

1. Tests-first implementation of the local platform and LOCAL-RTA-1.
2. Pass LOCAL-AC-1 and LOCAL-READ-ACT-1 on the current landed read stack.
3. Implement ME-1 tests/code, land it, then implement FE-8 tests/code and pass
   LOCAL-EVIDENCE-1.
4. Implement W1 tests/code and pass its real local auth/revocation matrix.
5. Implement W2 tests/code/migration and pass LOCAL-WRITE-FOUNDATION-1.
6. Implement FE-5/FE-6 tests/code and pass LOCAL-WRITE-UI-1.
7. Prove LOCAL-PERSIST-ONLY-1, then run LOCAL-WRITE-ACT-1 including failures and
   rollback.
8. Recreate the disposable data/runtime state and run LOCAL-RC-1 from Stage 0
   through Stage 7 with exact final SHAs.

Functions:

- `validate_stage_transition(current, requested)` enforces the local dependency
  graph and exact-SHA invalidation.
- `seed_local_approved_sources(conn, scenario)` creates actual queried tables:
  `gis.zone`, `water_planning.zone_planting_dates`,
  `ros_gis.section_crop_settings`, `ros.eto_monthly`, `ros.kc_weekly`, and
  `ros.effective_rainfall_monthly`.
- `run_local_manual_requirement(as_of_date)` temporarily runs ROS with
  `DAILY_REQUIREMENT_ENABLED=true` while both startup/schedule flags stay false.
- `run_local_ac1(client, as_of_date)` calls the actual ROS run, Scheduler draft,
  BFF projection, auth logout, and token-reuse paths without direct plan inserts.
- `run_local_read_activation(frontend)` builds/tests flag false, then true, then
  false rollback.
- `run_local_write_activation(clients)` executes operator/field-team/revoked,
  replay/conflict/outage/rollback/two-browser scenarios.
- `assert_persist_only(before, after)` proves planning-depth writes do not change
  ROS requirement runs or Scheduler drafts.
- `write_local_stage_manifest(stage, evidence)` rejects secrets and records exact
  SHAs, flags, migrations, and verdicts.

## Test coverage

Local platform:

- `test_machine_command_uses_native_arm64_isolation` — creates correct isolated guest.
- `test_stage_transition_rejects_skipped_gate` — enforces progressive promotion order.
- `test_sha_change_invalidates_downstream_evidence` — prevents stale proof reuse.
- `test_source_seed_queries_real_loader_tables` — matches production loader names.
- `test_source_seed_has_balanced_positive_areas` — avoids pathological one-section concentration.
- `test_source_seed_matches_approved_manifest` — preserves count, IDs, total area.
- `test_manual_producer_never_schedules_recurring_job` — keeps automatic ROS dark.
- `test_local_ac1_uses_routes_not_plan_inserts` — proves real application path.
- `test_manifest_rejects_secret_shaped_fields` — keeps evidence export safe.

Read/evidence:

- `test_local_read_activation_false_true_false` — proves activation and rollback.
- `test_local_ac1_returns_all_eight_projections` — exercises complete stored read surface.
- `test_local_evidence_renders_absent_and_present_states` — avoids empty-success inference.
- `test_gate_link_targets_exact_local_gate_id` — verifies read-only deep link.

Write/reconciliation:

- W1/W2/FE-5/FE-6 tests from the historical roadmap.
- `test_local_write_activation_two_browser_reconciliation` — proves shared server authority.
- `test_local_write_activation_replay_and_stale_conflict` — proves idempotency and concurrency.
- `test_local_write_activation_redis_and_db_fail_closed` — exercises dependency failures.
- `test_local_write_activation_false_true_false` — proves reversible write visibility.
- `test_persist_only_changes_no_requirement_or_plan` — locks DEC-W4 default.

## Decision completeness

- Goal: every roadmap stage gets incremental and final combined local proof.
- Non-goals: no AWS and no W4 recomputation.
- Public interfaces: locked below.
- Failure behavior: fail closed at each stage; no dependent work promotion.
- Rollout: sequential source PRs, local promotion after each merge, one clean
  final release-candidate run.
- Backout: local flags return false; disposable state can be discarded; migration
  behavior still tests forward-fix semantics before discard.
- Success: all named local gates plus LOCAL-RC-1 pass for exact final SHAs.

## Dependencies and validation

- Native-arm64 isolated Debian guest with PostgreSQL/PostGIS, Redis, InfluxDB,
  central auth, PM2, backend services, frontend, and browser automation.
- Deterministic local acceptance dataset generated from the tracked approved
  crosswalk and real loader invariants, not from production.
- Validation is incremental evidence plus a clean all-stage rerun.

## Wiring verification

| Component              | Entry point               | Registration                 | Schema/table                     |
| ---------------------- | ------------------------- | ---------------------------- | -------------------------------- |
| Stage orchestrator     | `run-stage-suite.py`      | local operator CLI           | stage manifest registry          |
| Approved source seeder | LOCAL-AC-1 setup          | loader source DB             | six exact source tables          |
| Manual ROS producer    | local-only wrapper        | PM2 temporary ROS process    | `ros_gis.water_requirement_*`    |
| Local AC-1             | real HTTP routes          | ROS/Scheduler/BFF routers    | requirement/control-plan tables  |
| Read activation        | frontend build/start      | Next feature helper          | none                             |
| ME-1/FE-8              | contracts and detail UI   | Scheduler/BFF/Next           | evidence read tables             |
| W1                     | Scheduler principal route | v1 router                    | Redis revocation only            |
| W2                     | BFF POST/GET              | BFF router                   | `water_planning.*`, registry 010 |
| FE-5/FE-6              | Next policy/proxy/hooks   | auth context and planning UI | W2 API                           |
| Persist-only assertion | stage runner              | before/after queries         | ROS and Scheduler tables         |
| Local write activation | browser/API scenario      | W1/W2/FE routes              | W2 immutable rows                |

## Draft B trade-offs

Advantage: catches integration defects at the earliest dependent stage while
still producing one final clean release-candidate proof.

Cost: more local runs and evidence packets, but no production risk or AWS churn.

# Comparative synthesis

Draft A minimizes ceremonies but delays the most valuable feedback. Draft B
fits the user's explicit requirement: every stage is locally exercised before
AWS, and each dependency is proven before downstream implementation continues.

Draft B is selected. Draft A contributes the requirement for one final clean
combined run so incremental success cannot hide state leakage.

# Unified execution plan

## Public interfaces and configuration locks

Existing/landed:

- ROS `POST /api/v1/water-requirements/runs`.
- Scheduler `POST /api/v1/control-plans/drafts` and existing read projections.
- BFF control-plan projections.
- Frontend `NEXT_PUBLIC_CONTROL_PLAN_READS`, strict `true`; default false.

Planned by the roadmap:

- Scheduler `GET /api/v1/auth/principal`.
- BFF `POST /api/v1/water-planning/planning-depth-submissions`.
- BFF `GET /api/v1/water-planning/planning-depth-submissions/active`.
- BFF migration `010_planning_depth_submissions.sql` plus ordered manifest.
- Frontend `NEXT_PUBLIC_WATER_PLANNING_SUBMIT_ENABLED`, strict `true`; default false.
- FE-8 `NEXT_PUBLIC_CONTROL_PLAN_EVIDENCE_READS`, strict `true`; default false.
- FE-8 `NEXT_PUBLIC_GATE_OPERATIONS_URL`, validated HTTP(S) base.

Missing W2 backend flag is now locked:

- `PLANNING_DEPTH_WRITES_ENABLED`, strict `true`; default false.
- Authenticated/authorized POST while false returns `503` with safe code
  `planning_depth_writes_disabled` and `Cache-Control: no-store`.
- GET active read-back remains available when writes are false after migration.
- Missing/invalid bearer is evaluated before the feature flag so the dark
  endpoint never weakens authentication behavior.

Local CLI:

- `orchestrate.py provision|run-stage|run-all|collect|teardown`.
- `run-stage` accepts only the locked local stage names.
- Source/backend/frontend SHAs are required full 40-character values.
- Architecture is fixed to `arm64`; guest isolation flags are not configurable.

## LOCAL-BASE-0

1. Record exact backend/frontend SHAs and landed status.
2. Record that FE-4 is complete and remaining source begins ME-1/W1 according to
   dependencies, not FE-4 reimplementation.
3. Generate stage manifest with every activation flag false.
4. Any new accepted SHA invalidates that stage and all downstream local evidence.

## LOCAL-RTA-1

1. Provision the isolated native-arm64 guest from clean exact Git bundles.
2. Install four isolated Python environments and locked Node dependencies.
3. Start local PostgreSQL/PostGIS, Redis, InfluxDB, and central auth.
4. Run the original RTA twelve-step procedure unchanged: capacity, migrations,
   promtool/preflight, four loopback apps, dark flags, five-minute readiness,
   real local bearer lifecycle, and PM2 save last.
5. This proves baseline runtime behavior but does not end local testing.

## LOCAL-AC-1

1. Generate a deterministic, balanced 41-section source dataset totaling exactly
   47,385 rai. Section IDs/zones/gates come from the tracked approved crosswalk;
   crop/weather values are fixed, plausible, versioned local scenario inputs.
2. Seed only the six tables the actual source loader queries. Never insert a
   requirement run or control plan directly.
3. Restart ROS through the local manual-producer wrapper with
   `DAILY_REQUIREMENT_ENABLED=true`, startup catch-up false, schedule false.
4. Login through local central auth and invoke the real ROS run route.
5. Require a published non-empty run with lineage/hash/41-section evidence.
6. Invoke the real Scheduler draft route using that run and actual Flow path.
7. Require a persisted non-empty truthful plan or fix the local scenario; never
   change production code to force feasibility.
8. Through BFF, require list, detail, coverage, ledger, lifecycle, intent,
   readback, execution state, no-store, 404, logout, and token-reuse denial.
9. Stop the manual producer mode and restore all automatic producer flags false.

## LOCAL-READ-ACT-1

1. Build/run frontend with `NEXT_PUBLIC_CONTROL_PLAN_READS=false`; verify no
   navigation and route 404.
2. Rebuild/run with the flag true against the local accepted plan.
3. Use real browser automation for signed-out, login, navigation, list, detail,
   refresh, deep link, missing plan, and independent panel failure behavior.
4. Rebuild/run with false and prove rollback restores the dark surface.

## LOCAL-EVIDENCE-1

1. Implement/land ME-1 with strict versioned schemas, manifest, examples,
   invalid fixtures, and both service contract suites.
2. Implement/land FE-8 with strict decoders and the narrower evidence flag.
3. Populate evidence only through existing local plan lifecycle/readback paths;
   no direct response fixture is used for the end-to-end gate.
4. Test present, absent, unavailable, held, and malformed behavior.
5. Point Gate Operations to a local read-only route target and verify exact
   encoded gate ID. No control request is implemented or issued.
6. Roll evidence visibility back to false after the stage passes.

## LOCAL-WRITE-FOUNDATION-1

1. Implement/land W1 tests first, endpoint second; run real local operator,
   field-team, revoked, Redis-outage, and no-store scenarios.
2. Implement/land W2 tests first, ordered migration 009/010 second, then route,
   principal client, limiter, roster, transaction, repository, and read-back.
3. Apply migrations from a clean registry, reapply idempotently, and prove
   checksum-drift refusal on a disposable clone.
4. Keep `PLANNING_DEPTH_WRITES_ENABLED=false` and prove authorized POST fails
   closed while active GET remains truthful.
5. Enable the backend flag only in the local guest and prove first submission,
   replay, content match, correction chain, stale conflict, concurrency,
   unauthorized role, Redis outage, DB rollback, and immutable rows.
6. Restore the backend flag false.

## LOCAL-WRITE-UI-1

1. Implement/land FE-5 policy/principal behavior and route inventory tests.
2. Implement/land FE-6 fixed W2 adapter, bearer proxy, client ID handling,
   active read-back, reconciliation, storage, and approved terminology.
3. With frontend submit flag false, prove no POST/active GET mutation workflow.
4. Enable backend writes, then enable frontend submission locally.
5. Use two independent browser contexts to prove first submit, second-browser
   read-back, correction, stale conflict, manual retry, logout, and reload.
6. Prove field-team-only and principal-outage paths preserve reads and hide writes.
7. Disable frontend flag first, then backend flag, and verify rollback.

## LOCAL-PERSIST-ONLY-1

1. Snapshot hashes/counts of ROS requirement runs and Scheduler control-plan
   drafts before a planning-depth submission.
2. Submit and correct planning depth through W2/FE-6.
3. Prove only W2 immutable submission/value rows change.
4. Prove no ROS run, demand, Scheduler draft, or control-plan hash/version changes.
5. Record DEC-W4 as persist-only. Do not create migration 0004 or recomputation
   code without a separate product decision.

## LOCAL-WRITE-ACT-1

Repeat the production activation order locally:

1. Exact SHAs and migration 009/010 parity.
2. W1 auth/revocation role matrix.
3. Backend flag true while frontend false; direct authorized W2 scenarios.
4. Frontend flag true; full two-browser scenarios.
5. Redis failure, DB transaction failure, 429/retry-after, 409, logout/reload.
6. Confirm persist-only truth and all command/execution/producer flags false.
7. Observe readiness/restart counts/resources for 15 continuous minutes.
8. Back out frontend visibility first and backend writes second; confirm reads
   remain available and immutable history remains intact.

## LOCAL-RC-1 — final clean all-stage gate

1. Stop local applications and recreate disposable application data from clean
   databases; keep only exact Git bundles and generated secret material.
2. Reinstall/reverify all manifests and lockfiles from the final SHAs.
3. Apply migrations from empty registries and prove idempotent reapply.
4. Run LOCAL-BASE-0 through LOCAL-WRITE-ACT-1 without manual DB repair or skipped
   failure drill.
5. Require all fast/full test suites, formatting, lint/type checks, QCHECK and
   g-check reports for each source PR to be green.
6. End with all production-equivalent flags false and four backend processes
   stable/readiness green.
7. Produce one signed/hash-listed evidence index linking every stage manifest.
8. Only `LOCAL-RC-1 PASS` authorizes beginning the AWS inventory/promotion lane.

## AWS promotion boundary

No AWS action occurs before LOCAL-RC-1 passes. Afterwards, in a new explicitly
authorized operations turn:

1. Read-only AWS inventory and current runtime classification.
2. Exact target cleanup proposal and explicit approval.
3. Approved cleanup/cutover with rollback evidence.
4. Deploy the final backend/frontend SHAs dark.
5. Run unchanged production RTA-1.
6. Run production AC-1 with real approved sources.
7. Activate reads/evidence/writes using the already-rehearsed order and retain
   the original production monitoring/backout gates.

## Local acceptance-data contract

The deterministic scenario is stored as generator code, not an opaque SQL dump.
It must:

- derive exact section IDs, zones, gate IDs, and channels from
  `services/ros-gis-integration/data/requirement_sources.json`;
- generate 41 positive, non-pathological section areas summing 47,385 rai;
- seed zones 1-6 planting dates for one fixed week;
- seed complete ETo, Kc, and effective-rainfall coverage for the tested horizon;
- retain a content SHA-256 and scenario version in local evidence;
- use only local identities such as `local-acceptance-operator`;
- never include production identifiers, credentials, database dumps, or PII.

The legacy `scripts/db/populate-munbon-areas.sql` is not reused because its eight
zones and 83,318.75-rai hierarchy do not match the approved six-zone/47,385-rai
control-plan source contract.

## Evidence schema

Each stage manifest contains only:

- schema version, stage name, local-only marker, run ID, exact SHAs;
- start/end timestamps, migration IDs/checksums, allowlisted flags;
- safe status codes/header verdicts, record counts/hashes, restart/resource data;
- dependency/failure-drill verdicts and rollback verdict;
- hash links to prior-stage manifests.

It never contains tokens, cookies, passwords, PM2 raw environment, DSNs,
response bodies with identity data, browser storage, or production endpoints.

## Failure modes

| Failure                                  | Required behavior                               |
| ---------------------------------------- | ----------------------------------------------- |
| Stage prerequisite missing               | Refuse stage start.                             |
| Accepted SHA changes                     | Invalidate that and downstream evidence.        |
| Local source invariant fails             | Stop before ROS manual run.                     |
| Plan is infeasible/unavailable           | Fix scenario truthfully; no code bypass.        |
| Manual ROS leaves schedule enabled       | Fail and stop ROS.                              |
| Read flag rollback fails                 | Block all later stages.                         |
| Contract drift                           | Fail before FE integration.                     |
| Migration drift/reapply fails            | Block W2; discard/inspect DB, forward-fix code. |
| Auth/Redis/DB fail-open                  | Block write foundation.                         |
| Two-browser conflict silently overwrites | Block FE-6.                                     |
| Planning depth changes ROS/Scheduler     | Block release; DEC-W4 violation.                |
| Fifteen-minute stability restarts        | Fail LOCAL-WRITE-ACT-1.                         |
| Evidence contains secret-shaped field    | Refuse export and LOCAL-RC-1.                   |

## Cross-language schema verification

| Boundary            | Producer              | Consumer                 | Lock                                        |
| ------------------- | --------------------- | ------------------------ | ------------------------------------------- |
| Control-plan v2     | Scheduler Python      | BFF Python + frontend TS | existing manifest/golden fixtures           |
| Evidence v1         | Scheduler/BFF Python  | frontend TS              | ME-1 manifest/examples/invalid fixtures     |
| Effective principal | Scheduler Python      | BFF Python + frontend TS | strict response fixtures                    |
| Planning-depth W2   | BFF Python/Postgres   | frontend TS              | valid/invalid JSON and decimal/hash vectors |
| Canonical roster    | local seeder/Postgres | ROS loader + W2          | 41 IDs, six zones, 47,385 rai               |
| Local evidence      | Python runner         | operator review          | additional-properties-false schema          |

Before W2 migration/code is written, exact-string verification must confirm
`water_planning.planning_depth_submissions`,
`water_planning.planning_depth_values`, and
`water_planning.schema_migrations` agree across SQL, Python repositories,
operations runner, fixtures, and frontend contracts.

## Final wiring verification

| Component            | Runtime entry point             | Registration/caller     | Schema/table                  |
| -------------------- | ------------------------------- | ----------------------- | ----------------------------- |
| Local orchestrator   | CLI                             | operator                | stage manifest registry       |
| Local source seeder  | LOCAL-AC-1 setup                | stage runner            | six loader source tables      |
| ROS manual producer  | ROS HTTP POST                   | local-only PM2 wrapper  | `ros_gis.water_requirement_*` |
| Scheduler draft      | Scheduler HTTP POST             | LOCAL-AC-1 client       | Scheduler control-plan tables |
| FE-4 activation      | Next pages/navigation           | feature helper          | read projections              |
| ME-1 contracts       | contract tests/runtime decoders | Scheduler/BFF/FE        | evidence schemas              |
| FE-8 evidence        | detail page component           | hooks/API/server proxy  | evidence projections          |
| W1 principal         | Scheduler HTTP GET              | v1 router               | Redis revocation              |
| W2 migration         | ops runner                      | manifest apply          | W2 tables/registry            |
| W2 APIs              | BFF HTTP POST/GET               | BFF router/main         | W2 tables                     |
| FE-5 policy          | auth context/policy             | Smart Water UI          | W1 response                   |
| FE-6 submission      | Next proxy/hook/provider        | planning UI             | W2 APIs                       |
| Persist-only probe   | stage runner                    | before/after DB queries | ROS/Scheduler/W2 tables       |
| Browser activation   | Playwright two contexts         | stage runner            | frontend plus APIs            |
| Final evidence index | LOCAL-RC-1                      | stage runner            | stage manifests               |

## Validation commands and outcomes

- Backend focused/full pytest suites pass per service.
- `npm --prefix infra/pm2 run verify` and `promtool` checks pass.
- Frontend focused Vitest, Prettier, typecheck, full tests, and dark builds pass.
- Local four-service runtime passes the existing five-minute gate.
- All stage HTTP/browser scenarios and failure drills pass.
- LOCAL-WRITE-ACT-1 has 15 minutes of stable readiness/restarts.
- Final flags are false and LOCAL-RC-1 evidence index verifies all hashes.

## Success criteria

- Every Stage 0-7 local gate passes incrementally.
- LOCAL-RC-1 passes from clean disposable state using final exact SHAs.
- Read and write activation plus rollback are demonstrated locally.
- Real service paths—not direct plan/run inserts—produce the local requirement
  run, control plan, projections, planning-depth submissions, and read-back.
- Dependency outages, auth roles, replay/conflict, two-browser reconciliation,
  no-store, and token lifecycle are all exercised.
- Persist-only truth is proven; no command/authority/automatic producer is armed.
- No AWS action occurs before LOCAL-RC-1 PASS.

## Decision-complete checklist

- [x] All roadmap stages have named local equivalents.
- [x] Progressive and final-clean local gates are both required.
- [x] Local architecture is native arm64 and isolated.
- [x] Exact local source tables and invariants are locked.
- [x] Real-path versus production-real-data distinction is explicit.
- [x] Missing backend W2 feature flag is named and fail-closed.
- [x] Read/evidence/write flags and rollback order are locked.
- [x] W4 remains persist-only with a tested non-effect invariant.
- [x] Every stage has failure behavior, tests, evidence, and wiring.
- [x] AWS begins only after final local release-candidate acceptance.

## Implementation Summary (2026-07-23 09:29:30 +07) - LOCAL-BASE-0 and LOCAL-RTA-1

### Outcome

- Ran an isolated native-arm64 local acceptance guest named `munbon-control-plan-local`; no AWS action was taken and the pre-existing `ubuntu` guest was not changed.
- `LOCAL-BASE-0` passed at backend `8095bfe37550200da00ecb554edc646febf8aff9` and frontend `3a16498a60927996ac38e741b276150968d0cadc`.
- `LOCAL-RTA-1` passed all 12 ordered gates, including the 300-second readiness window, unchanged zero PM2 restart counts, real bearer lifecycle, dark flags, monitoring/preflight, and `pm2 save` last.
- Final sanitized evidence is under `coding-logs/evidence/2026-07-23-local-rta-1-8095bfe3-final/`; the earlier otherwise-passing attempt with unexpected wildcard Prometheus listeners is retained separately as failed historical evidence.

### TDD and Runtime Corrections

- Began with failing tests for the host orchestrator, stage runner, artifacts, local operator seed, and secret-safe bearer evidence; implemented until green.
- Corrected isolated-guest transfer, required GDAL/GEOS packages, InfluxDB loopback systemd behavior, disposable operator email migration, broad safe rollback on verifier failures, and non-loopback listener rejection.
- Formal review then found and fixed three VM-reuse guard gaps with failing tests first: exact requested machine resources, exact live machine limits, and a harness ownership marker.

### Validation

- `pytest -q ops/control-plan-read-runtime/tests ops/control-plan-read-local/tests` - 83 passed.
- `node --test ops/control-plan-read-local/tests/test_seed_local_operators.js` - 2 passed.
- `black` - pass; `ruff check` - pass; `prettier --check` - pass; `bash -n` - pass; `node --check` - pass.
- Guest `systemd-analyze verify` - pass; final SHA256 evidence check - pass.
- Four PM2 processes remain online with restart count zero in the isolated guest.

## Review (2026-07-23 09:29:30 +07) - working-tree LOCAL-BASE-0/LOCAL-RTA-1 harness

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-local-acceptance`
- Branch: `feature/control-plan-local-acceptance`
- Scope: working tree at `8095bfe37550200da00ecb554edc646febf8aff9`
- Commands Run: `git status --porcelain=v1`, bounded staged diff name/stat/check inspection, targeted source/test inspection, `pytest`, Node test runner, `black`, `ruff`, Prettier, `bash -n`, `node --check`, live OrbStack inventory/ownership validation, PM2 projection, `systemd-analyze verify`, and evidence SHA256 verification.

### Findings

CRITICAL

- No findings.

HIGH

- No findings.

MEDIUM

- No outstanding findings. Review-discovered machine resource, live-limit, and ownership validation gaps were remediated with regression tests before this disposition.

LOW

- No findings.

### Open Questions / Assumptions

- This is a software and operations rehearsal on disposable local infrastructure, not production RTA-1 acceptance.
- Debian repository packages are installed from current signed repositories, so a future clean rebuild can encounter upstream package drift even at the same application SHA.
- The isolated guest is intentionally retained for the next local stages.

### Recommended Tests / Validation

- Keep the 83 Python and 2 Node tests as the preflight for subsequent local-stage changes.
- Re-run `LOCAL-RTA-1` from a clean guest before the final `LOCAL-RC-1` release-candidate gate.
- Revalidate SHA256 evidence and zero non-loopback listeners after every later activation/rollback stage.

### Rollout Notes

- No AWS resources or external deployment state changed.
- Scheduler execution, machine commands, ROS producers, control-plan visibility, and planning-depth writes remained dark.
- Do not treat this result as authorization to enter AWS; AWS starts only after every planned local stage and final local release-candidate acceptance pass.

## Development Lifecycle (2026-07-23 12:22 +07) - PR opened, CI infrastructure blocked

- Committed the reviewed product slice as `75e23881df0790d21d6976ab5f3768603e428a4c` with message `feat(ops): add local control-plane acceptance harness`.
- Pushed `feature/control-plan-local-acceptance` and opened normal GitHub PR `#118`.
- Product commit contains only the harness, tests, verifier update, and runbook. Generated runtime evidence and Coding Logs remain outside the product commit.
- PR is mergeable and `main` is not branch-protected, but both `scan-diff` and `full-tree-baseline` were prevented from starting.
- GitHub check annotation for both jobs: `The job was not started because your account is locked due to a billing issue.`
- No admin or documented merge exception was used. Merge and exact-main verification await explicit user authorization for that exception or restoration of GitHub Actions billing.
- No AWS action occurred.

## Development Lifecycle Complete (2026-07-23 12:38:42 +07)

- User explicitly authorized an admin merge despite the recorded GitHub Actions billing lock.
- PR `#118` was squash-merged into `origin/main` as `2ee640c5eed939b68035c7695a4c129570e9ca5a`.
- The first `gh pr merge --squash --delete-branch --admin` invocation completed the remote merge but reported that local `main` was already owned by the primary worktree; this was a local cleanup constraint, not a merge failure.
- Fast-forwarded the primary checkout's local `main` from `8095bfe37550200da00ecb554edc646febf8aff9` to `2ee640c5eed939b68035c7695a4c129570e9ca5a`.
- Verified exact equality: local `HEAD == origin/main == 2ee640c5eed939b68035c7695a4c129570e9ca5a`.
- Deleted the merged remote feature branch. The isolated worktree remains because it contains the retained local runtime evidence.
- Post-merge exact-main validation: Python `83 passed`; Node `2 passed`; Ruff, Prettier, Bash syntax, and Node syntax passed.
- Existing untracked Coding Logs and `.codex/coding-log.current` in the primary checkout were preserved.
- This lifecycle action changed Git/GitHub state only. It performed no AWS operation and did not redeploy the local or EC2 runtime.

## Implementation Summary (2026-07-23 15:18:41 +0700) - LOCAL-AC-1 and LOCAL-READ-ACT-1

### Outcome

- Created `/Users/subhajlimanond/dev/munbon2-backend-local-ac-read` from exact backend `origin/main` `2ee640c5eed939b68035c7695a4c129570e9ca5a`; preserved the dirty primary checkout and the existing `munbon2-backend-local-acceptance` evidence worktree.
- Re-ran `LOCAL-BASE-0` and `LOCAL-RTA-1` on exact current main in the isolated native-arm64 guest. Both passed, including the 300-second stability window and dark runtime contract.
- Implemented and exercised `LOCAL-AC-1`: deterministic approved source seeding, real manual ROS publication, real Flow snapshot, native-CBC Scheduler draft and prediction, all eight authenticated BFF projections, missing/no-store behavior, and token logout/reuse denial.
- Implemented and exercised `LOCAL-READ-ACT-1`: frontend source pin, focused tests and production builds in false → true → false order, real Chromium login/list/detail/refresh/deep-link/missing-plan/panel-failure proof, rollback, and no residual frontend listener.
- No AWS action was taken. Execution, recurring producer, write, visibility, authority, and machine-command gates finish dark.

### TDD and Review Corrections

- Added failing tests before each implementation slice and runtime defect correction, including approved-source invariants, stage progression, frontend activation order, asyncpg record hashing, native CBC selection/fallback, browser evidence validation, and exact bundle/bootstrap behavior.
- Independent QCHECK found an unauthenticated ROS producer trigger, an unverified evidence chain, and asserted-only frontend write absence. Remediation added a transient guest-local internal trigger with missing/invalid 403 proof, cumulative checksum verification bound to backend/frontend/harness identity, derived frontend gate evidence, non-button action-control inspection, zero observed mutation requests, and five negative mutation/authority route probes.
- Formal review then found that guest reprovision could reuse an earlier database publication. Reprovision now quiesces the harness, archives evidence, recreates the harness-owned database, flushes local Redis, and accepts only a newly `published` manual requirement run.
- Production portability fixes allow asyncpg Record-like values in deterministic source hashing and prefer system-native CBC while retaining the packaged solver fallback.

### Validation

- Local harness: `85 passed` on three consecutive runs; local operator Node tests: `2 passed`.
- ROS/GIS full suite in the isolated guest: `190 passed, 2 skipped`; focused changed tests: `29 passed` on three consecutive runs.
- Scheduler full suite under the compatibility test policy with execution/readback dark: `1027 passed, 59 skipped`; focused optimizer tests: `23 passed` on three consecutive runs.
- Black, Ruff, scoped mypy, Bash syntax, Node syntax, and `git diff --check`: pass.
- Development runtime proof passed all four local stages. A clean exact-committed-candidate reprovision and four-stage rerun remains the final closeout step.

## Review (2026-07-23 15:18:41 +0700) - working-tree LOCAL-AC-1/LOCAL-READ-ACT-1

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-local-ac-read`
- Branch: `feature/control-plan-local-ac-read`
- Base: backend `2ee640c5eed939b68035c7695a4c129570e9ca5a`, frontend `3a16498a60927996ac38e741b276150968d0cadc`
- Scope: working-tree LOCAL-AC-1 and LOCAL-READ-ACT-1 harness, ROS manual-trigger boundary, Scheduler CBC portability, tests, and runbook
- Commands Run: bounded status/diff inspection; harness tests three times; ROS/GIS full and focused suites; Scheduler full and focused suites; Black; Ruff; scoped mypy; Bash and Node syntax checks; exact runtime PM2/browser/evidence inspection.

### Findings

CRITICAL

- No findings.

HIGH

- No outstanding findings. The unauthenticated manual producer identified by independent QCHECK is remediated with a fail-closed internal trigger and negative authorization tests.

MEDIUM

- No outstanding findings. Evidence-chain verification, live source identity checks, frontend mutation/authority absence, and clean disposable-state reprovision were added during review.

LOW

- No findings.

### Open Questions / Assumptions

- The development AC/READ evidence used reviewed overlays on exact main and is not the final candidate-provenance artifact.
- Final acceptance requires committing the candidate, reprovisioning from that exact commit with clean disposable state, and rerunning all four stages.
- This is local acceptance only and grants no AWS, write activation, authority, or machine-command authorization.

### Recommended Tests / Validation

- Reprovision the isolated guest from the exact committed candidate and exact frontend main.
- Rerun `LOCAL-BASE-0`, `LOCAL-RTA-1`, `LOCAL-AC-1`, and `LOCAL-READ-ACT-1`; verify every `SHA256SUMS` entry, clean source identity, loopback-only listeners, and final dark PM2 state.

### Rollout Notes

- No deployment or AWS action occurred.
- Keep `CONTROL_EXECUTION_MODE=disabled`, `CONTROL_READBACK_RECONCILIATION_MODE=off`, `ALLOW_MACHINE_COMMANDS=false`, automatic ROS producer flags false, planning-depth writes false, and frontend read visibility false after rollback.

## Exact Candidate Closeout (2026-07-23 15:34:23 +0700)

- Product-only commit: `4a5e48b92ca6bd853291f1d2116e1c99457d22da` (`feat(ops): add local AC and read acceptance`).
- Exact frontend: `3a16498a60927996ac38e741b276150968d0cadc`.
- Clean reprovision used bundles whose `main` refs resolved exactly to those SHAs, archived previous guest evidence, recreated `munbon_local`, flushed guest Redis, and retained all secrets inside the guest.
- The clean bootstrap exposed two working-directory defects before Stage 0: inherited `/root` caused Prisma EACCES, then neutral `/` exposed that Prisma did not run from the frontend project. Both were reproduced, locked with tests, fixed, and included in the final exact commit.
- `LOCAL-BASE-0`: PASS.
- `LOCAL-RTA-1`: PASS, including 300-second stability, unchanged zero restarts, bearer lifecycle, loopback-only listeners, and `pm2 save` last.
- `LOCAL-AC-1`: PASS with a new `published` run, 287 requirements, missing/invalid internal-header 403 responses, feasible Scheduler draft, completed prediction, all BFF projections, and dark restoration.
- `LOCAL-READ-ACT-1`: PASS with false → true → false builds, real Chromium proof, zero action controls, zero observed control-plan mutations, five rejected mutation/authority probes, and dark rollback.
- Guest and collected `SHA256SUMS` each verify all four stage manifests plus `stage-state.json`.
- Backend and frontend tracked trees are clean at the exact accepted SHAs. Final listeners are loopback-only; there is no port 9999 listener.
- Final process environments: Flow `GATES_API_ENABLED=false`; Scheduler `CONTROL_EXECUTION_MODE=disabled` and readback `off`; ROS manual/startup/schedule producers all `false`; machine-command and planning-write enablement are absent.
- Sanitized exact-candidate evidence: `coding-logs/evidence/2026-07-23-local-ac-read-candidate-4a5e48b9/`.
- No AWS action, deployment, write activation, authority activation, or machine command occurred.

## Development Lifecycle Complete (2026-07-23 15:37:20 +0700)

- Pushed `feature/control-plan-local-ac-read` and opened PR `#119`.
- GitHub reported the PR mergeable and clean. The repository’s Actions workflows remain documented as dormant under the billing lock, and no check runs were created for this PR.
- Completed an ordinary squash merge without `--admin`; PR `#119` merged to `origin/main` as `bf547850a4da7e3dac89c30d655ded46b516d796`.
- Verified the merged `origin/main` tree is byte-identical to exact-tested candidate `4a5e48b92ca6bd853291f1d2116e1c99457d22da`.
- Verified the merged remote feature branch is deleted.
- Per the user’s preservation constraint, did not update or clean the dirty primary checkout. Its local `main` remains at `2ee640c5eed939b68035c7695a4c129570e9ca5a` with its untracked logs intact.
- The pre-existing `munbon2-backend-local-acceptance` worktree remains at `75e23881df0790d21d6976ab5f3768603e428a4c` with its retained evidence untouched.
- Product history contains no generated evidence or Coding Log artifacts; those remain uncommitted in the fresh implementation worktree.

## Remediation Summary (2026-07-23 19:00:22 +0700) - exact lineage and reproducible gates

### Goal

- Close post-merge audit gaps from PR `#119` without changing control behavior: make the planned ROS run lineage explicit in sanitized evidence, make the runbook SHA-durable, and pass the repository-pinned formatter gates.

### Changes

- `ops/control-plan-read-local/run-stage-suite.py`: added fail-closed validation and live PostgreSQL collection for the published run content hash, section/crosswalk dataset version IDs and source hashes, crop/weather/method versions, and the approved scenario hash.
- `ops/control-plan-read-local/tests/test_stage_suite.py`: added an independent exact-structure test plus malformed-hash rejection for the lineage validator.
- `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`: replaced the stale backend baseline example with explicit accepted-SHA variables, documented the new lineage evidence, and made clean exact-SHA reruns mandatory for every candidate.
- `ops/control-plan-read-local/run-read-browser.js`, `ops/control-plan-read-local/seed-approved-sources.py`, `services/ros-gis-integration/src/services/requirement_source_loader.py`, and `services/ros-gis-integration/tests/unit/test_water_requirement_read_api.py`: applied the repo-pinned Prettier `3.9.6` and Black `23.11.0` output missed before PR `#119`.

### TDD Evidence

- RED: `python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py::test_validate_requirement_run_lineage_requires_exact_database_hashes` failed with `NotImplementedError` from the scaffolded validator.
- GREEN: the same command passed after implementing strict UUID/version/hash validation.
- The formatter-only changes have no meaningful RED behavior run because they preserve the parsed Python/JavaScript behavior and solely remediate reproducible format gates.

### Validation

- `pytest -q -p no:cacheprovider ops/control-plan-read-local/tests` - `75 passed` on three consecutive runs.
- `pytest -q -p no:cacheprovider ops/control-plan-read-runtime/tests ops/control-plan-read-local/tests` - `109 passed`.
- ROS focused tests - `29 passed` on three consecutive runs; full suite - `190 passed, 2 skipped`.
- Scheduler full suite with `CONTROL_EXECUTION_MODE=disabled` and `CONTROL_READBACK_RECONCILIATION_MODE=off` - `1027 passed, 59 skipped`.
- Black `23.11.0`, Ruff, Prettier `3.9.6`, Bash syntax, Node syntax, Python compile, and `git diff --check` - pass.
- Scoped mypy with skipped imports passed for `run-stage-suite.py` and `requirement_source_loader.py`. A broader import-following invocation reproduced 106 pre-existing ROS typing errors outside this slice and is not used as the scoped gate.
- A read-only query against the retained local guest's real published ROS run returned all nine fields expected by the new validator.

### Wiring and Safety

- Runtime path: `run_local_ac()` calls `_psql()` after the authenticated manual publication, validates the row against the accepted run ID and approved scenario hash, and writes the result below `steps.manual_requirement_run.lineage`.
- Schema: `ros_gis.water_requirement_runs` joins `ros_gis.dataset_versions` twice using the migration-owned `section_master` and `gate_crosswalk` kinds.
- The query and evidence contain only IDs, versions, and SHA-256 values. No credential, DSN, response body, production endpoint, or identity data is added.
- No AWS action or deployment occurred. Execution, readback, recurring production, visibility, planning-write, authority, and machine-command gates remain dark.

### Remaining Lifecycle Work

- Independent QCHECK and formal `g-check`.
- Commit the reviewed product slice, run all four local stages from that exact candidate SHA, open/merge the follow-up PR, land local `main`, and verify the exact merged commit.
- Correct the historical “no check runs” statement with current GitHub evidence; PR `#119` now exposes failed post-merge check records even though the merge itself completed.

## Review (2026-07-23 19:10:29 +0700) - working-tree lineage and gate remediation

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend`
- Branch: `fix/local-ac-read-format-gates`
- Scope: staged working tree against `bf547850a4da7e3dac89c30d655ded46b516d796`
- Commands Run: `git status --porcelain=v1`; staged name/stat and targeted patch inspection; local harness and combined runtime tests; ROS focused/full tests; Scheduler focused/full tests with execution/readback dark; Black `23.11.0`; Ruff; Prettier `3.9.6`; scoped mypy; Bash/Node/Python syntax; `git diff --check`; live read-only PostgreSQL lineage query; independent QCHECK.

### Findings

CRITICAL

- No findings.

HIGH

- No outstanding findings. Independent QCHECK found that the documented `collect` command still used the obsolete backend baseline. The runbook now uses the accepted backend/frontend variables for provision, all four stages, and collect; a RED-to-GREEN runbook contract test and a six-command CLI validation test lock the flow.

MEDIUM

- No outstanding findings. Independent QCHECK requested stronger lineage wiring coverage. The SQL collector is now isolated behind `collect_requirement_run_lineage()`, its exact table joins, dataset kinds, published-run filter, result structure, and failure validation are unit-tested, and the same SQL shape was verified read-only against the retained guest's real published run.
- The independent reviewer used host Black `25.9.0`, which disagrees with repository-pinned Black `23.11.0` on multiline-string layout. The staged files pass the repository-pinned `23.11.0` gate; no formatter bypass or ignore marker was added.

LOW

- No findings.

### Open Questions / Assumptions

- GitHub Actions for PR `#119` did create post-merge check records, contrary to the earlier historical log entry. Every failed job inspected has the exact annotation `The job was not started because your account is locked due to a billing issue.`; this is CI infrastructure evidence, not a product-test failure.
- The follow-up candidate still requires clean, exact-SHA local reprovision and all four stage passes before it can be submitted and treated as accepted.

### Recommended Tests / Validation

- Commit the reviewed candidate, cleanly reprovision `munbon-control-plan-local` from that exact backend SHA and frontend `3a16498a60927996ac38e741b276150968d0cadc`, run `LOCAL-BASE-0`, `LOCAL-RTA-1`, `LOCAL-AC-1`, and `LOCAL-READ-ACT-1`, collect/verify `SHA256SUMS`, and inspect the new `manual_requirement_run.lineage` evidence.
- Preserve the final dark contract: Scheduler execution disabled/readback off; ROS automatic producers false; Flow gates API false; no write, authority, visibility, or machine-command activation.

### Rollout Notes

- Review scope is local tooling, documentation, evidence hardening, tests, and mechanical formatting only.
- No AWS action, deployment, write activation, authority activation, or machine command is authorized or performed.

## Development Lifecycle and Exact-Main Acceptance Complete (2026-07-23 19:23:50 +0700)

### PR and Main Landing

- Reviewed candidate commit: `334f749b55ce5e49d56bec27d0de14faa31131d1` (`fix(ops): close local acceptance evidence gates`).
- Pushed `fix/local-ac-read-format-gates` and opened normal GitHub PR `#120`.
- PR `#120` was mergeable. Its `scan-diff` and `full-tree-baseline` jobs each failed before starting with the exact annotation `The job was not started because your account is locked due to a billing issue.`
- Completed an ordinary squash merge without `--admin`; PR `#120` merged into `origin/main` as `428baa769df65569fc0a99e03fa01df5990773bf`.
- The merge command fast-forwarded the primary checkout. Verified exact equality: local `HEAD == local main == origin/main == 428baa769df65569fc0a99e03fa01df5990773bf`.
- Verified the merge tree is byte-identical to reviewed candidate `334f749b55ce5e49d56bec27d0de14faa31131d1`, and the remote feature branch is deleted.
- Historical correction: PR `#119` did create post-merge check records. Every inspected failure annotation states that the job was not started because the account is locked due to a billing issue; the earlier “no check runs were created” statement is not current GitHub truth.

### Exact-Main Local Acceptance

- The orchestrator accepted exact backend `428baa769df65569fc0a99e03fa01df5990773bf` and frontend `3a16498a60927996ac38e741b276150968d0cadc` with native-arm64 isolation, network isolation, and `aws_actions=false`.
- Clean reprovision verified both exact Git bundles, archived prior guest evidence, recreated the harness-owned local database, flushed guest Redis, installed the tracked runtime, and passed bootstrap.
- `LOCAL-BASE-0`: PASS.
- `LOCAL-RTA-1`: PASS with the 300-second stability window, unchanged zero restart counts, all four dependency-backed readiness checks, bearer lifecycle, loopback-only listeners, zero swap, and `pm2 save`.
- `LOCAL-AC-1`: PASS with 41 sections/47,385 rai, a new published 287-requirement run, exact approved-source SHA, run content SHA, section/crosswalk dataset IDs and source SHAs, real Flow publication, feasible Scheduler draft/completed prediction, eight BFF projections, and dark restoration.
- `LOCAL-READ-ACT-1`: PASS with false → true → false focused tests/builds; dark route 404 before and after; real Chromium list/detail/refresh/deep-link/missing-plan/panel-isolation proof; zero action controls; zero observed mutations; and five denied mutation/authority probes.
- Both guest and collected `SHA256SUMS` verify `LOCAL-BASE-0.json`, `LOCAL-RTA-1.json`, `LOCAL-AC-1.json`, `LOCAL-READ-ACT-1.json`, and `stage-state.json`.
- Sanitized exact-main evidence: `coding-logs/evidence/2026-07-23-local-ac-read-main-428baa76/`.

### Post-Merge Gates and Final Safety

- Exact merged main: combined runtime/local tests `111 passed`.
- Candidate/full validation retained: local harness `77 passed` on three consecutive runs; ROS `190 passed, 2 skipped`; Scheduler `1027 passed, 59 skipped`; affected ROS and Scheduler focused tests passed three consecutive runs.
- Black `23.11.0`, Ruff, Prettier `3.9.6`, scoped mypy, syntax checks, and diff checks pass.
- Final listeners are loopback-only on 3005, 3011, 3021, 3022, 3047, 5432, 6379, and 8086; no port 9999 listener exists.
- Final dark contract is unchanged: Flow gates API false; Scheduler execution `disabled` and readback `off`; ROS manual/startup/recurring producers false; planning-depth writes/visibility false; model release non-commandable; no SCADA or machine-command configuration.
- No AWS action, deployment, write activation, authority activation, or machine command occurred.

## BE/FE Plan Synchronization Addendum (2026-07-23 22:06:05 +0700)

### Authority and exact baselines

This addendum supersedes conflicting FE-5 through FE-8 details in the historical
roadmap while preserving the earlier record.

- Backend `HEAD == main == origin/main`:
  `428baa769df65569fc0a99e03fa01df5990773bf`.
- Frontend `HEAD == main == origin/main`:
  `3a16498a60927996ac38e741b276150968d0cadc`.
- FE-1 through FE-4 are landed. FE-4 is the separate dark control-plan
  list/detail surface.
- The synchronized frontend source plan is:
  `/Users/subhajlimanond/dev/smart-cms-app/coding-logs/2026-07-23-21-57-21 Coding Log (fe5-fe8-calendar-and-evidence-roadmap).md`.
- ME-1, W1, W2, FE-5, FE-6, FE-7 acceptance, FE-8, and their downstream local
  gates remain unimplemented.

### Locked frontend ownership

The two V2 concepts are distinct:

1. **Water Planning V2 workspace**
   - Route: `/smart-water/dashboard`.
   - Gate: `NEXT_PUBLIC_WATER_PLANNING_V2`.
   - Owns GIS interaction, day/RID-week selection, planning-depth drafts,
     authoritative submission/read-back, reconciliation, and FE-7 activation.
   - FE-5, FE-6, and FE-7 belong to this surface.
2. **Control-plan contract v2 and read UI**
   - Routes: `/smart-water/control-plans` and the plan/version detail route.
   - Gate: `NEXT_PUBLIC_CONTROL_PLAN_READS`.
   - Owns bounded plan/prediction/ledger/lifecycle reads and later machine
     evidence.
   - FE-8 belongs to this surface after ME-1.

FE-5/FE-6 must preserve the existing calendar contract:

- `PlanningMode = "date" | "rid-week"`.
- Both modes resolve one canonical `ActivePeriod`.
- `week_key = activePeriod.weekKey`.
- `week_date = activePeriod.weekDate`, the RID-week start in both modes.
- `selectedDate` remains display context in date mode and is not a daily-demand
  or daily-submission claim.
- Demand stays weekly. No division by seven or invented daily contract is
  allowed.
- Drafts, replay identity, active read-back, and reconciliation remain scoped
  by canonical RID week.

### Synchronized dependency lanes

```text
Evidence lane:
FE-4 at 3a16498 -> ME-1 -> FE-8 -> LOCAL-EVIDENCE-1

Write lane:
Water Planning V2 calendar -> W1 -> W2 -> FE-5 -> FE-6
  -> LOCAL-WRITE-UI-1 -> LOCAL-PERSIST-ONLY-1
  -> FE-7 / LOCAL-WRITE-ACT-1

Final:
both lanes -> LOCAL-RC-1 -> separately authorized AWS inventory/promotion
```

The evidence and write lanes may prepare independently after their respective
backend contracts land. Frontend product PRs still land one at a time from
refreshed `origin/main`; no guessed contract shape or combined mega-PR is
allowed.

### Updated BE/FE responsibility matrix

| Slice       | Backend responsibility                                                                                                                  | Frontend responsibility                                                                                                                        | Completion gate         |
| ----------- | --------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| ME-1 / FE-8 | Publish separate `control-plan-evidence/v1` schemas, examples, invalid fixtures, manifest, hashes, and both service contract suites     | Pin exact ME-1 bytes; add strict decoders, three proxies/hooks, independent evidence summary, narrower flag, and safe read-only gate link      | `LOCAL-EVIDENCE-1`      |
| W1 / FE-5   | Publish strict effective-principal behavior with JWT, revocation, role, and outage taxonomy                                             | Derive mutation visibility from authoritative W2 active-read outcomes; raw issuer roles never authorize                                        | FE-5 source gates, dark |
| W2 / FE-6   | Publish fixed POST/active-GET contracts, migration 010/manifest, immutable storage, limiter, replay, conflict, and transaction behavior | Replace legacy water-level adapter with calendar-bound planning-depth POST/GET, client IDs, manual retry, active read-back, and reconciliation | `LOCAL-WRITE-UI-1`      |
| DEC-W4      | Keep persist-only; no ROS migration/recomputation without a separate product decision                                                   | Label planning depth as planned input, never observed water level                                                                              | `LOCAL-PERSIST-ONLY-1`  |
| FE-7        | Keep backend writes false by default; support rehearsed false/true/false activation and failures                                        | Perform local two-browser activation, failure, monitoring, and rollback proof                                                                  | `LOCAL-WRITE-ACT-1`     |

### FE-5 synchronized contract

- FE-5 adds a pure mutation policy and W2 error classification to the Water
  Planning V2 RHS.
- Do not add a direct browser/Next-to-Scheduler principal path.
- W2 active GET remains the authoritative capability boundary because it
  already resolves W1 principal truth:
  - authorized `200` or `404`: operator may see submission UI;
  - `403`: hide write controls and preserve planning reads;
  - `502`/`503`: capability unavailable; hide writes and preserve reads;
  - `401`: use the existing refresh-once/sign-out flow.
- Preserve W2 `409`, `429`, and `Retry-After` semantics.
- No frontend rate limiter is introduced.

### FE-6 synchronized contract

- Replace browser-facing
  `/api/smart-water-backend/water-planning/submissions` with fixed:
  - `POST /api/smart-water-backend/water-planning/planning-depth-submissions`;
  - `GET /api/smart-water-backend/water-planning/planning-depth-submissions/active`.
- Reuse the validated server-only `WATER_PLANNING_BFF_URL`.
- Remove `WATER_PLANNING_SUBMIT_PATH`; no configurable or legacy write target
  remains.
- Upstream paths are fixed:
  - `POST /api/v1/water-planning/planning-depth-submissions`;
  - `GET /api/v1/water-planning/planning-depth-submissions/active`.
- Forward the bearer and never the refresh cookie; reject redirects; preserve
  `Cache-Control: no-store`.
- Generate one `client_submission_id` per deliberate attempt. A manual retry
  after network ambiguity reuses that ID; no automatic POST retry is allowed.
- Send `expected_active_submission_id`; a `409` refetches and preserves the
  local draft rather than overwriting.
- Reconcile local, last-common, and authoritative active state explicitly.
- Rename the write boundary and user copy to planning depth; observed water
  level tables and terminology remain separate.

### FE-7 synchronized contract

FE-7 is restored as the frontend label for local activation and rollback
acceptance. It is not a standalone feature PR by default and does not authorize
staging, production, AWS, authority, or machine commands.

FE-7 maps to the frontend portion of:

1. `LOCAL-WRITE-UI-1`;
2. `LOCAL-PERSIST-ONLY-1`;
3. `LOCAL-WRITE-ACT-1`.

Required order:

1. Frontend submit false; backend writes false.
2. Backend writes true while frontend remains false; run direct W2 scenarios.
3. Frontend submit true locally; test both calendar modes and two browsers.
4. Exercise first submit, replay, correction, stale conflict, manual retry,
   field-team, revoked token, Redis outage, DB rollback, logout, and reload.
5. Observe readiness/restarts/resources for 15 continuous minutes.
6. Disable frontend visibility first.
7. Disable backend writes second.
8. Prove authenticated reads and immutable W2 history remain.

Any defect found during FE-7 requires a separate TDD product PR and a complete
exact-SHA rerun.

### FE-8 synchronized contract

- FE-8 depends on ME-1 merged and pinned; it does not modify the existing
  five-projection control-plan v2 family.
- Add the three strict projections:
  - `intent-timeline`;
  - `readback-observations`;
  - `execution-state`.
- `NEXT_PUBLIC_CONTROL_PLAN_EVIDENCE_READS` must be exact `true` and must be
  combined with `NEXT_PUBLIC_CONTROL_PLAN_READS`; default is false.
- Present, absent, unavailable, held, and malformed states render independently.
- Empty arrays never mean execution success. Null observed level never becomes
  zero. Timeline remains predicted dispatch evidence, not physical observation.
- The summary contains no mutation, hold/resume, authority, or command controls.

Gate Operations correction:

- The current SCADA `/gates/{id}` page is command-capable: it polls status and
  includes level and horn command controls. FE-8 must not link to it.
- A separately accepted read-only Gate Operations route is a prerequisite for
  the deep link.
- `NEXT_PUBLIC_GATE_OPERATIONS_URL` represents that read-only route prefix.
  FE-8 appends exactly one encoded gate ID.
- Missing, unsafe, command-capable, or unaccepted target configuration hides the
  link and blocks the Gate Operations portion of `LOCAL-EVIDENCE-1`.

### Local gate amendments

`LOCAL-EVIDENCE-1` additionally requires:

- exact ME-1 manifest/byte parity between backend and frontend;
- independent malformed-projection behavior;
- a no-command inventory for the configured Gate Operations target;
- zero control requests during browser acceptance.

`LOCAL-WRITE-UI-1` additionally requires:

- day mode and RID-week mode both resolve the same canonical project/week when
  they refer to the same RID week;
- the clicked day remains display-only context;
- no active GET or POST occurs while frontend submission is false;
- two-browser authoritative read-back and explicit conflict reconciliation.

`LOCAL-WRITE-ACT-1` is the FE-7 gate and retains the existing false/true/false
activation order, 15-minute stability window, persist-only assertion, and
rollback requirements.

### Superseded historical assumptions

The following historical assumptions must not guide new implementation:

- FE-5/FE-6 as generic “planning UI” without the Water Planning V2
  `ActivePeriod` calendar boundary;
- FE-7 as staging/production activation before the final local release
  candidate;
- FE-8 linking to the current `/gates/{id}` page;
- a configurable `WATER_PLANNING_SUBMIT_PATH`;
- a direct frontend Scheduler-principal path;
- “water level” naming for planned operator inputs;
- serialized evidence and write lanes when their independent backend
  prerequisites are available.

### Updated pickup order

1. Land ME-1 in the backend.
2. Land FE-8 from refreshed frontend `main`, with evidence visibility false.
3. Pass `LOCAL-EVIDENCE-1`; restore evidence visibility false.
4. Land W1, then W2; pass `LOCAL-WRITE-FOUNDATION-1`; restore backend writes
   false.
5. Land FE-5, then FE-6 from refreshed frontend `main`, both dark.
6. Pass `LOCAL-WRITE-UI-1` and `LOCAL-PERSIST-ONLY-1`.
7. Execute FE-7 / `LOCAL-WRITE-ACT-1`, including rollback.
8. Recreate disposable state and pass `LOCAL-RC-1`.
9. Begin AWS work only in a separately authorized operations turn.
