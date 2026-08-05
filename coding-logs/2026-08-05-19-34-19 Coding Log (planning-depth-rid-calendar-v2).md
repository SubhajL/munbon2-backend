# Planning-depth RID calendar v2 — PR 4

- Created: 2026-08-05 19:34:19 +0700
- Repository: `/Users/subhajlimanond/dev/munbon2-backend-pr4-rid-v2`
- Remote: `https://github.com/SubhajL/munbon2-backend.git`
- Branch: `feature/planning-depth-rid-calendar-v2`
- Base: `origin/main` `3e5946c8b5fdba688808bcf150741f719a1ecdd9`
- Source handoff: primary checkout `coding-logs/2026-08-05-19-16-49 Coding Log (pr3-progress-and-pr4-rid-v2-pickup).md` (732 lines, SHA-256 `a3547750500f37c359d5189254973e48cb58923f3b5fa43374cd0ca42f254569`)
- Semantic-search limitation: Auggie exceeded the mandatory two-second cutoff. This plan is based on complete handoff review, repository instructions, direct file inspection, and exact-identifier searches.
- Clarifying assumption stated to user: preserve the handoff outcome while adapting implementation details to current `origin/main` if they conflict.

## Settled baseline

PR 3 is merged as GitHub PR #145 and local `main == origin/main == 3e5946c8b5fdba688808bcf150741f719a1ecdd9`. The primary checkout contains user-owned Coding Logs/evidence and is not used for PR 4 edits. PR 4 is isolated in this worktree. The current user objective supplies fresh authorization for the documented admin-merge path after local gates and reviews; hosted zero-step jobs remain a separate evidence boundary.

The earlier reconciled roadmap fixes the legacy discriminator as `legacy-calendar-v1`. RID v2 uses the literal `rid-irrigation-v1`. Migration 010 and every v1 contract byte remain immutable.

# Plan Draft A — separate v2 surface with calendar-aware shared persistence

## Overview

Add a separate planning-depth contract and API v2 for RID administrative-week identity, while retaining v1 request/response bytes and behavior. Migration 011 adds calendar identity to the shared immutable tables, replaces global scope constraints with calendar-scoped equivalents, and rejects cross-scope predecessor lineage at the database boundary.

## Files to change

- `contracts/planning-depth-submissions/v2/manifest.json` — pin the complete v2 schema/fixture set and hashes.
- `contracts/planning-depth-submissions/v2/submission-request.schema.json` — require schema 2, RID calendar literal, ending-year RID key, exact week-start date, and current level shape.
- `contracts/planning-depth-submissions/v2/submission-receipt.schema.json` — publish explicit immutable RID identity.
- `contracts/planning-depth-submissions/v2/active-submission.schema.json` — publish RID identity with exactly 41 expanded section values.
- `contracts/planning-depth-submissions/v2/*.example.json` and `fixtures/invalid/*.json` — cover boundary weeks, schema/calendar/key/date mismatches, unknown calendar, and extra fields.
- `services/bff-water-planning/src/schemas/planning_depth_v2.py` — strict v2 Pydantic request, receipt, and active models, reusing stable v1 level/value types.
- `services/bff-water-planning/src/services/planning_depth_submission.py` — add a separate v2 canonicalizer that includes `calendar_system`; do not alter v1 canonical bytes.
- `services/bff-water-planning/src/db/planning_depth_repository.py` — make private persistence primitives calendar-aware; retain v1 wrappers fixed to `legacy-calendar-v1` and add v2 wrappers fixed to `rid-irrigation-v1`.
- `services/bff-water-planning/src/api/routes/planning_depths_v2.py` — add authenticated, no-store v2 POST and active GET while reusing the existing auth, roster, flag, limiter, and error envelope.
- `services/bff-water-planning/src/main.py` — register the v2 router.
- `services/bff-water-planning/migrations/011_planning_depth_rid_calendar_v2.sql` — forward-only discriminator, scoped indexes/constraints, identity validation, and same-scope predecessor enforcement.
- `services/bff-water-planning/migrations/manifest.json` — append migration 011 with exact checksum.
- `services/bff-water-planning/tests/unit/test_planning_depth_v2_contract.py` — manifest/schema/model/hash parity and v1 byte regression.
- `services/bff-water-planning/tests/unit/test_planning_depth_v2_submission.py` — RID canonicalization and exact week-start behavior.
- `services/bff-water-planning/tests/unit/test_planning_depth_v2_routes.py` — auth, dark flag, errors, no-store, query, and route wiring.
- `services/bff-water-planning/tests/unit/test_planning_depth_migrations.py` — manifest 011, ordering, idempotency, and checksum behavior.
- `services/bff-water-planning/tests/unit/test_planning_depth_runtime.py` — exact runtime parity through 011.
- `services/bff-water-planning/tests/unit/test_boot.py` — assert v1 and v2 live route surfaces.
- `services/bff-water-planning/tests/integration/test_planning_depth_postgres.py` — seeded-v1 migration, v1/v2 coexistence, calendar-scoped replay/active/successor, direct-SQL constraints, immutability, concurrency, rollback, and reapply.
- `ops/control-plan-read-local/run-stage-suite.py` — require BFF latest migration 011/count 3.
- `ops/control-plan-read-runtime/README.md` — document parity through 011.
- `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md` — advance the literal parity prerequisite to 011.

## Implementation steps

1. Add/stub v2 contract/model/service/route/repository/migration/runtime/PostGIS tests.
2. Run focused tests and record RED caused by missing v2 artifacts/symbols/migration, not harness syntax.
3. Add strict v2 models. `PlanningDepthSubmissionRequestV2.require_rid_week_start()` constructs `IrrigationWeek` from `YYYY-Rnn`, requires the supported ending year/week, and requires `week_date == irrigation_week_span(identity).start`.
4. Add `canonicalize_planning_depth_request_v2()` with the v2 discriminator; keep `canonicalize_planning_depth_request()` untouched and pin its known fixture hashes.
5. Implement migration 011 without changing migration 010 bytes:
   - add `calendar_system TEXT NOT NULL DEFAULT 'legacy-calendar-v1'` so old v1 inserts remain compatible;
   - replace the schema/key check with exact valid pairs: `(1, legacy-calendar-v1, YYYY-Www, ISO Monday)` or `(2, rid-irrigation-v1, YYYY-Rnn, exact RID start)`;
   - replace global client uniqueness with `(calendar_system, client_submission_id)`;
   - replace root/scope indexes with `(project_key, calendar_system, week_key)`;
   - retain one successor per predecessor and add a trigger that rejects predecessor project/calendar/week mismatch;
   - preserve both immutable-row triggers.
6. Parameterize private `_load_active_row`, receipt/active reconstruction, advisory lock, client replay lookup, insert, root lookup, and successor scope by calendar. Keep public v1 wrappers and outputs fixed; add v2 wrappers and outputs.
7. Add `submit_planning_depth_v2()` and `get_active_planning_depth_v2()`. Reuse bearer/principal, database-manager, `NoStorePlanningDepthRoute`, authoritative roster, flag, limiter, and error taxonomy. The active query requires `project_key=mun-bon`, `calendar_system=rid-irrigation-v1`, and `YYYY-Rnn`.
8. Register the v2 router in `main.py` and prove both route families boot.
9. Advance migration-parity literals and documentation atomically.
10. Run formatter/static/focused/full/repeated/PostGIS/cross-language gates, wiring verification, independent QCHECK, and formal g-check.
11. Commit conventionally, push, open an ordinary PR, inspect actual hosted step execution, use the explicitly authorized admin merge while recording the billing-lock boundary, fast-forward local main, and rerun exact-merge gates.

### TDD sequence

1. Scaffold missing public symbols/artifacts only as needed for importable RED tests.
2. Add tests before each production behavior.
3. Run and preserve the exact failing command/reason.
4. Implement the smallest behavior that makes the test pass.
5. Refactor minimally only for demonstrable v1/v2 reuse.
6. Run Black, focused pytest, full bare pytest, PostGIS integration, JSON/YAML checks, and `git diff --check` after each coherent block.

### Function outline

- `PlanningDepthSubmissionRequestV2.require_rid_week_start()` — fail closed unless the explicit ending-year RID key and date resolve to the exact administrative week start.
- `canonicalize_planning_depth_request_v2()` — produce deterministic v2 bytes including calendar system while preserving the v1 function and hashes.
- `_load_active_row(connection, project_key, calendar_system, week_key)` — isolate active lineage within one explicit calendar namespace.
- `_create_planning_depth_submission(...)` — perform scoped lock, replay, stale-active check, immutable insert, and value insert for an explicit request/response model pair.
- `create_planning_depth_submission_v2()` — v2 wrapper fixed to RID identity and response model.
- `_get_active_planning_depth_submission(...)` — hash-check and reconstruct the exact versioned active response.
- `get_active_planning_depth_submission_v2()` — v2 wrapper fixed to RID identity.
- `submit_planning_depth_v2()` — authenticated dark-gated POST using authoritative roster and existing limiter semantics.
- `get_active_planning_depth_v2()` — authenticated no-store active GET scoped to the literal RID namespace.
- `enforce_planning_depth_predecessor_scope()` (SQL trigger function) — reject cross-project/calendar/week lineage before insert.

## Test coverage

- `test_v2_manifest_pins_complete_contract_set` — pins every v2 schema and fixture byte.
- `test_v2_schema_models_match_every_fixture` — enforces schema/model parity for all vectors.
- `test_v2_request_matches_rid_boundary_vectors` — validates exact ending-year boundary identities.
- `test_v2_request_rejects_non_start_and_mismatched_identity` — rejects interior or mismatched dates.
- `test_v2_request_rejects_iso_key_and_unknown_calendar` — prevents namespace inference.
- `test_v1_contract_and_canonical_hashes_remain_unchanged` — protects existing public bytes.
- `test_v2_canonicalization_includes_calendar_identity` — distinguishes otherwise equal namespaces.
- `test_manifest_pins_migration_011_without_changing_010` — protects migration ownership.
- `test_migration_011_labels_seeded_v1_rows_without_mutation` — proves legacy preservation.
- `test_database_rejects_invalid_schema_calendar_key_date_pairs` — makes DB identity fail closed.
- `test_v1_and_v2_roots_coexist_in_calendar_scopes` — permits shared week/client values safely.
- `test_v2_lock_replay_and_active_read_are_calendar_scoped` — prevents cross-calendar collisions.
- `test_database_rejects_cross_calendar_successor` — protects lineage via direct SQL.
- `test_concurrent_v2_successors_commit_exactly_one` — validates advisory-lock behavior.
- `test_v2_value_failure_rolls_back_submission_and_values` — validates transaction atomicity.
- `test_v2_route_preserves_auth_dark_rate_limit_errors_and_no_store` — matches the v1 safety envelope.
- `test_live_route_surface_includes_v1_and_v2` — proves runtime registration.
- `test_runtime_migration_parity_requires_011` — advances exact local runtime gate.
- `test_apply_reapply_and_checksum_drift_refusal_through_011` — proves forward-only ownership.

## Decision completeness

### Goal

Land explicit, immutable RID administrative-calendar identity for W2 submissions and active reads without changing or reinterpreting legacy v1 data.

### Non-goals

- No frontend changes.
- No edit to migration 010, planning-depth v1 contract bytes, or RID-calendar v1 contract bytes.
- No change to `/api/v1` request/response/canonical semantics.
- No flag activation, local UI acceptance, deployment, AWS, ROS workbook/import, or legacy backfill beyond the migration discriminator default.

### Success criteria

- `/api/v1` fixture hashes, canonical bytes, response shapes, and database semantics remain compatible.
- `/api/v2` accepts only schema 2, `rid-irrigation-v1`, supported ending-year `YYYY-Rnn`, and exact RID week starts.
- Migration 011 preserves existing v1 rows as `legacy-calendar-v1`, permits v1/v2 coexistence, and rejects invalid/cross-scope identity.
- Lock, replay, root, active, and successor semantics include calendar namespace.
- Candidate gates pass three consecutive full BFF runs and three disposable PostGIS runs; merge SHA receives separate post-merge verification.

### Public interfaces

- `POST /api/v2/water-planning/planning-depth-submissions`.
- `GET /api/v2/water-planning/planning-depth-submissions/active` with `project_key`, `calendar_system`, and `week_key`.
- Planning-depth request/receipt/active schema version 2.
- Literal `calendar_system: "rid-irrigation-v1"` and ending-year `YYYY-Rnn`.
- Migration `011_planning_depth_rid_calendar_v2`; no new environment variables or topics.

### Edge cases and failure modes

- Unknown/wrong calendar, malformed/out-of-range RID key, or non-start date: 422; DB direct insert also fails closed.
- RID week 53 is accepted only when its exact truncated contract span exists and `week_date` is its start.
- Missing/malformed roster: 503; no raw GIS fallback.
- Stale or concurrent successor: 409; one successor commits.
- Limiter unavailable: 503; exceeded: 429 with bounded existing `Retry-After`.
- Database/stored projection error: existing safe 503 taxonomy.
- Cross-calendar replay/root/successor: isolated or rejected, never silently linked.
- Hosted jobs with zero steps: infrastructure-blocked, never reported as passing.

### Rollout, monitoring, and backout

- Keep `PLANNING_DEPTH_WRITES_ENABLED=false` by default.
- Apply migration 011 before code activation; the v1 app remains insert-compatible through the legacy default.
- Migration is forward-only after v2 rows exist. Application backout returns clients to v1 routes and does not mutate/delete immutable data.
- Watch migration registry/checksum, 422 identity failures, 409 conflicts, 429s, 503 dependency failures, and any predecessor-scope trigger rejection.

### Acceptance checks

- Focused v2/v1 tests pass.
- Bare BFF pytest passes three times.
- RID Python properties/vectors and Node ROS vector suite pass against unchanged RID v1 hashes.
- Fresh disposable PostGIS applies 009/010/011, reapplies as no-op, preserves seeded v1 rows, proves coexistence/constraints/concurrency/rollback, and passes three times.
- Black, JSON parse/schema validation, workflow YAML parse if touched, `git diff --check`, QCHECK, formal g-check, and secret scan pass.

## Dependencies

- Complete: roster v1 merge `3e5946c8`, RID-calendar v1 contract/Python/Node implementations, FE-5/FE-6, frontend local CI harnesses.
- Hosted backend Actions is account-billing blocked; this limits hosted evidence but not local product implementation.
- Current user objective explicitly authorizes the PR 4 admin merge after local acceptance/review.

## Validation commands

- Focused: `pytest -q tests/unit/test_planning_depth_v2_contract.py tests/unit/test_planning_depth_v2_submission.py tests/unit/test_planning_depth_v2_routes.py tests/unit/test_planning_depth_migrations.py tests/unit/test_planning_depth_runtime.py tests/unit/test_boot.py` from the BFF service.
- Full: bare `pytest` from the BFF service, three consecutive runs.
- RID cross-language: BFF RID vector/property tests plus the existing ROS RID calendar unit command discovered from that service's package scripts.
- Integration: provision disposable PostGIS loopback DB, set only `BFF_TEST_POSTGRES_URL` for the test process, and run `tests/integration/test_planning_depth_postgres.py` three times.
- Formatting/static: configured Black invocation, JSON/schema parsing, `CODEX_ALLOW_LARGE_OUTPUT=1 git diff --check`.
- Lifecycle: independent QCHECK, formal staged working-tree g-check, commit/PR checks, exact-merge rerun.

## Wiring verification

| Component | Entry point | Registration | Authority/schema |
| --- | --- | --- | --- |
| v2 models | FastAPI request/response validation | imports in `planning_depths_v2.py` | planning-depth v2 schemas |
| RID validator | request model post-validator | `core.rid_calendar` imports | unchanged RID v1 vectors/hash |
| v2 POST | `/api/v2/.../planning-depth-submissions` | `main.py:app.include_router()` | roster plus shared submission tables |
| v2 active GET | `/api/v2/.../active` | same router registration | calendar-scoped active lineage |
| v2 canonical bytes | v2 repository create wrapper | service import | request text/hash columns |
| calendar persistence | migration runner | manifest entry 011 | `planning_depth_submissions.calendar_system` |
| replay/root/active | repository private primitives | v1/v2 public wrappers | calendar-scoped indexes/queries/lock |
| predecessor scope | insert into submissions | migration 011 trigger | project/calendar/week equality |
| runtime parity | local stage suite | runtime unit test/runbook | manifest through 011 |

## Cross-language schema verification

Exact-string inspection shows the BFF Python repository/tests are the writers/readers of `water_planning.planning_depth_submissions` and `planning_depth_values`. Python RID authority is `services/bff-water-planning/src/core/rid_calendar.py`; Node conformance is `services/ros/src/utils/rid-calendar.js`; both consume `contracts/rid-calendar/v1`. PR 4 does not alter those contract bytes. Frontend consumption begins only in PR 5.

# Plan Draft B — generic versioned domain layer before v2 routes

## Overview

First refactor v1 schemas, repository operations, and route orchestration behind generic versioned protocols, then add v2 as a second configuration. This reduces apparent duplication, but expands the regression surface before the new behavior has an independent boundary.

## Files to change

All Draft A files, plus broader edits to `planning_depth.py` and `planning_depths.py` to introduce union/generic request, response, and handler orchestration.

## Implementation steps

1. Pin all current v1 behavior and canonical hashes.
2. Extract generic request/receipt protocols and shared route orchestration.
3. Re-run full v1 gates before adding v2.
4. Add v2 configuration, migration 011, contracts, and tests.
5. Complete the same validation and lifecycle as Draft A.

## Test coverage

Draft A coverage plus characterization tests for every extracted v1 handler/repository branch and version dispatch failure.

## Decision completeness

- Goal: one generic implementation for all planning-depth versions.
- Non-goal: no behavior change beyond v2.
- Public interfaces, migration, failure behavior, rollout, and acceptance are identical to Draft A.
- Main trade-off: lower future duplication versus a materially larger PR and higher v1 regression risk today.

## Dependencies and validation

Identical to Draft A, with an additional mandatory full v1 characterization pass after the refactor and before v2 behavior.

## Wiring verification

| Component | Entry point | Registration | Authority/schema |
| --- | --- | --- | --- |
| generic version dispatcher | v1/v2 route handlers | shared route/service module | model protocol/union |
| v1 configuration | existing `/api/v1` routes | existing router | legacy contract v1 |
| v2 configuration | new `/api/v2` routes | new router | RID contract v2 |
| migration/runtime components | same as Draft A | same as Draft A | same as Draft A |

## Cross-language schema verification

Identical to Draft A; no RID algorithm copy is permitted.

# Comparative analysis and synthesis

Draft A keeps the public version boundary explicit, preserves the known v1 implementation, and shares only persistence primitives and already-stable safety helpers. Its small amount of wrapper duplication is intentional and testable. Draft B may be attractive after multiple versioned calendars exist, but it front-loads a generic abstraction, broadens the v1 route/model diff, and makes a migration-sensitive PR harder to review.

Choose Draft A. Use narrow private repository parameterization and existing safety helpers, but keep separate v1/v2 public models, canonicalizers, and routers. This satisfies reuse without hiding calendar identity behind a premature generic public layer.

# Unified execution plan

## Overview

Implement Draft A in four TDD blocks: contracts/models/canonicalization; migration/repository; route/runtime wiring; operational parity. Each block records RED/GREEN evidence, followed by full repeated validation, review, ordinary PR submission, authorized admin merge, and exact-SHA local-main landing.

## Files to change

The Draft A list is authoritative. Add no unrelated frontend, ROS algorithm, deployment, or broad refactor files.

## Implementation steps

1. Contract/model RED → strict v2 schema/model/fixture/hash GREEN while v1 hashes remain pinned.
2. Migration/repository RED → calendar-scoped schema, replay, root, active, and predecessor GREEN on real PostGIS.
3. Route/boot RED → separate authenticated no-store v2 POST/GET and `main.py` registration GREEN.
4. Runtime parity RED → manifest/runbook/runtime literal 011 GREEN.
5. Run focused/full/repeated/cross-language/PostGIS gates and fill the wiring table with exact non-test call sites.
6. Run independent QCHECK and primary formal g-check; fix accepted findings test-first and rerun impacted gates/review.
7. Stage only intended files, conventional commit, push, open PR, inspect check step execution and review state, and record the hosted billing boundary.
8. Admin-merge as authorized, refresh local main without touching primary dirty artifacts, and rerun exact merged-SHA full/PostGIS verification.

## Test coverage

The Draft A test list is authoritative; each test must be capable of failing for the named defect and use independent RID vectors or direct database behavior as its oracle.

## Decision completeness

- Goal/non-goals/success/public interfaces/failures/rollout/backout are fixed by Draft A.
- Exact legacy literal: `legacy-calendar-v1`.
- Exact RID literal: `rid-irrigation-v1`.
- Exact namespace scope: project + calendar system + week key; client replay uniqueness is calendar-scoped.
- Exact lineage rule: predecessor must share project, calendar system, and week key.
- No implementation decision remains open.

## Dependencies

Roster v1 and RID v1 conformance are complete. Hosted billing is an evidence limitation, not permission to skip local gates. The active user objective supplies merge authorization.

## Validation

Use the Draft A commands and evidence boundaries. Candidate and merge SHA evidence are distinct and must both be recorded here.

## Wiring verification

Use the Draft A table; before commit every component must have a non-test call site/registration and exact schema/table evidence.

## Decision-complete checklist

- [x] Goal, non-goals, and measurable success criteria fixed.
- [x] v1 compatibility and v2 public interfaces fixed.
- [x] Calendar literals, key, date, lock, replay, root, active, and lineage semantics fixed.
- [x] Migration number, forward-only strategy, backout, and immutability fixed.
- [x] Tests cover every behavior/failure boundary and real-DB rules.
- [x] Wiring and cross-language authority identified.
- [x] Validation commands and three-run reliability scope identified.
- [x] Normal PR, authorized admin merge, local-main landing, and exact-merge verification fixed.
- [x] No open implementation decision remains.

## Implementation summary — contract/model/canonicalization block (2026-08-05 19:43:37 +0700)

### Goal

Publish the strict RID planning-depth v2 contract/model boundary and deterministic request identity without changing v1 bytes.

### What changed

- Added `contracts/planning-depth-submissions/v2/**`: three Draft 2020-12 schemas, two valid request boundaries, receipt/41-value active examples, seven invalid fixtures, and a complete SHA-pinned manifest.
- Added `src/schemas/planning_depth_v2.py`: strict schema-2 models fixed to `rid-irrigation-v1`, `YYYY-R01..R53`, the supported RID ending-year range, and exact `irrigation_week_span(...).start`.
- Added `canonicalize_planning_depth_request_v2()` while leaving the v1 canonicalizer unchanged.
- Added v2 contract/model/canonical tests plus exact v1 contract-set and request-hash regression assertions.

### TDD evidence

- Tests added: `test_planning_depth_v2_contract.py` and `test_planning_depth_v2_submission.py`.
- RED command: `CORS_ORIGINS='["http://localhost"]' /Users/subhajlimanond/dev/munbon2-backend/services/bff-water-planning/venv/bin/pytest -q tests/unit/test_planning_depth_v2_contract.py tests/unit/test_planning_depth_v2_submission.py`.
- RED result: 5 failed, 9 passed. Failures were the intended missing v2 manifest/schemas, empty stub-model rejection, and unimplemented v2 canonicalizer surface.
- GREEN command: `CORS_ORIGINS='["http://localhost"]' /Users/subhajlimanond/dev/munbon2-backend/services/bff-water-planning/venv/bin/pytest -q tests/unit/test_planning_depth_v2_contract.py tests/unit/test_planning_depth_v2_submission.py tests/unit/test_planning_depth_contract.py tests/unit/test_planning_depth_submission.py`.
- GREEN result: 29 passed.
- Formatter: Black on the four changed Python source/test files; passed.

### Wiring verification

- V2 request validation calls the existing `core.rid_calendar.IrrigationYear`, `IrrigationWeek`, and `irrigation_week_span`; no calendar algorithm copy was added.
- V2 canonicalization is a production service symbol ready for the repository create wrapper in the next block.
- Contract/model field equality and serialized-output validation cover request, receipt, and active schemas.

### Behavior and risk notes

- Identity ambiguity fails closed at model validation.
- Week 53 one/two-day spans are accepted only at their exact start.
- V1 contract set `f05abc...` and canonical request hash `77bf9b...` remain pinned.
- Known gap: persistence, migration, route registration, and runtime parity are intentionally next; no v2 runtime entry point exists yet.

## Implementation summary — migration/repository block (2026-08-05 19:55:44 +0700)

### Goal

Persist v1 and RID-v2 submissions in one immutable table without calendar collisions or cross-scope lineage.

### What changed

- Added forward-only migration 011 and pinned its checksum; migration 010 remains exactly `c9045102...`.
- Added `calendar_system` with legacy default, exact v2 RID key/date constraints, calendar-scoped client/root/active indexes, and a same-project/calendar/week predecessor trigger.
- Refactored private repository persistence/read primitives to accept an explicit calendar scope; retained v1 wrappers fixed to `legacy-calendar-v1` and added v2 wrappers fixed to `rid-irrigation-v1`.
- Added real-PostGIS coverage for seeded-v1 preservation, shared client UUID coexistence, invalid identity, cross-calendar successor rejection, v2 concurrency, v2 rollback, reapply, and checksum drift.

### TDD evidence

- Migration RED command: `CORS_ORIGINS='["http://localhost"]' /Users/subhajlimanond/dev/munbon2-backend/services/bff-water-planning/venv/bin/pytest -q tests/unit/test_planning_depth_migrations.py`.
- Migration RED result: 3 failed, 1 passed because manifest/apply/status lacked 011.
- Repository sensitivity RED drill: after restoring the v2 wrapper to its planned stub, `... pytest -q tests/integration/test_planning_depth_postgres.py::test_v1_and_v2_roots_replay_and_active_reads_are_calendar_scoped` failed with `NotImplementedError`; the implementation was restored immediately through `apply_patch`.
- Unit GREEN: migration plus v1 contract/service regression command passed 19 tests.
- PostGIS GREEN: `CORS_ORIGINS='["http://localhost"]' BFF_TEST_POSTGRES_URL='postgresql://munbon_test:...@127.0.0.1:55439/munbon_pr4_test' .../pytest -q tests/integration/test_planning_depth_postgres.py` passed 18 tests.
- Disposable database: named loopback-only `munbon-pr4-bff-postgis`, `postgis/postgis:16-3.4`.

### Wiring verification

- V1 create/read wrappers call the calendar-aware private primitives with `legacy-calendar-v1`.
- V2 create/read wrappers call the same primitives with `rid-irrigation-v1` and v2 canonical/response models.
- Advisory lock, client replay lookup, root lookup, active lookup, insert, and successor visibility all include calendar scope.
- Migration runner discovers 011 through the checksum-pinned manifest without runner code changes.

### Behavior and risk notes

- Migration 011 deliberately preserves the old v1 DB key regex rather than tightening historical direct-row semantics to ISO-Monday validation; v1 Pydantic behavior remains unchanged. This is the compatibility-preserving interpretation of “do not reinterpret legacy rows.”
- V2 direct inserts fail closed unless the key year is 1901..2401 and `week_date` equals the exact November-1-anchored week start.
- Client UUID uniqueness is calendar-scoped, while predecessor scope is project + calendar + week.

## Implementation summary — route/runtime parity block (2026-08-05 19:55:44 +0700)

### Goal

Expose and register the separate v2 POST/active GET surface with the existing auth/dark/no-store safety envelope and advance runtime parity to 011.

### What changed

- Added `api/routes/planning_depths_v2.py` and registered it in `main.py`.
- Reused v1 bearer/principal dependencies, operator authorization, database manager, no-store route class, authoritative roster, write flag, Redis limiter, and error taxonomy.
- Added route tests covering 401, 403, 422, 409, 429 with `Retry-After`, 503, created/replayed response, active scope, 404, and no-store headers.
- Advanced BFF parity to 011 in stage-suite code/tests, runtime unit tests, runtime README, and all-stages acceptance documentation; evidence key is now `migration_011`.

### TDD evidence

- RED command: `CORS_ORIGINS='["http://localhost"]' .../pytest -q tests/unit/test_planning_depth_v2_routes.py tests/unit/test_planning_depth_runtime.py tests/unit/test_boot.py`.
- RED result: 14 failed, 16 passed because the stub router returned 404, `main.py` lacked registration, and parity still expected 010.
- GREEN command: the same focused command after implementation.
- GREEN result: 30 passed.
- Stage-suite focused GREEN: parity success/fail-closed tests passed 4 tests.
- Formatter: Black passed on new/changed focused Python files; unrelated whole-file formatter churn in legacy files was removed from the diff.

### Wiring verification

- Runtime call path: `main.py` → `planning_depths_v2.router` → v2 route handler → v2 repository wrapper → shared calendar-scoped repository → migration-011 tables.
- All response paths, including validation and HTTP exceptions, are wrapped by `NoStorePlanningDepthRoute`.
- Runtime parity reads the same BFF migration manifest used by the migration runner and now requires exact latest 011/count 3.

### Behavior and risk notes

- Existing write flag remains fail-closed unless exactly `true`; no runtime flag was changed.
- Existing v1 local foundation drill remains v1/ISO; only its migration-parity evidence advances to 011. Frontend v2 consumption remains PR 5.
- No deployment or external database was touched.

## Independent QCHECK remediation — active RID query boundary (2026-08-05 20:04:55 +0700)

### Finding and disposition

- MEDIUM: the v2 active GET originally applied only the `YYYY-R01..R53` regex, so supported-looking keys outside the calendar year range could reach storage and return 404 rather than fail at the RID identity boundary.
- Fixed by extracting `parse_rid_week_key()` from the existing v2 model validator and reusing it as the active-query dependency before any database connection.
- Added parameterized below/above-boundary coverage for `1900-R01` and `2402-R01`, asserting 422, `Cache-Control: no-store`, no repository call, and zero database connections.
- No other independent QCHECK findings remained. The reviewer reported v1 compatibility/scoping, no-store behavior, auth, migration order/checksum, and runtime-parity wiring coherent.

### TDD evidence

- RED: `.../pytest -q tests/unit/test_planning_depth_v2_routes.py -k unsupported_rid_year` failed 2 tests because both unsupported years returned 200 and opened a database connection.
- GREEN: the supported-query plus invalid-calendar plus boundary command passed 4 tests.
- Contract inventory correction: the final v2 set has eight invalid fixtures, including the supported-year-range negative case; the earlier seven-fixture count predated that addition.

## Final candidate validation (2026-08-05 20:07:36 +0700)

### Exact staged candidate gates

- BFF full suite, three consecutive runs: each run passed `335 passed, 19 skipped`; the 59 warnings are existing dependency deprecations.
- Disposable loopback PostGIS integration, three consecutive runs: each run passed all 18 tests against migration 009 → 010 → 011.
- Full local stage-suite unit matrix: 111 passed.
- Shared cross-language RID calendar pin: ROS Jest suite passed 51 tests.
- Focused Black check: all 11 changed BFF Python source/test files would be left unchanged.
- Static artifact gates: 17 v2/manifest JSON files parsed; BFF source/tests compiled; staged and working-tree diff checks passed.
- Migration integrity: 010 remains `c904510204c97269a73ee4592c06c1a35c1fd8f13b53b47885a21b4c5a5c62f6`; 011 is pinned as `3b9244902872aa7ce9d0e5d24add43e132cbc8f8a159cc486a360c78f816098e`.
- Staged secret-pattern scan excluding the Coding Log found no credential/private-key pattern.

### QCHECK disposition

- Functions: calendar parsing is one reusable pure boundary; v1/v2 public wrappers keep vocabulary explicit; repository transaction/active-read logic remains testable through real PostGIS. No unused parameters, hidden changing values, or new class hierarchy was introduced.
- Tests: failure-sensitive RED evidence exists for contract/model, migration, repository, route/runtime, and the independently found active-query boundary. Assertions cover exact response/status/scope structures and real database invariants rather than implementation-derived oracles.
- Implementation: v1 bytes and public behavior remain pinned; v2 uses the authoritative calendar core; storage identity/lineage is scoped; the route remains dark/no-store/authenticated; migration/runtime wiring is complete.
- Independent QCHECK MEDIUM was remediated test-first; no unresolved QCHECK findings remain.

## Review (2026-08-05 20:07:36 +0700) — working-tree

### Reviewed

- Target: all staged PR 4 changes relative to `3e5946c8b5fdba688808bcf150741f719a1ecdd9`.
- Scope: v2 contracts/models/canonicalization, migration 011, repository scoping, v2 routes, runtime parity, documentation, and all new/changed tests.
- Evidence: staged diff and checksum review; three full BFF runs; three real-PostGIS runs; full stage suite; cross-language calendar Jest; Black/compile/JSON/diff/secret gates; independent Terra QCHECK.

### Findings

#### CRITICAL

- No findings.

#### HIGH

- No findings.

#### MEDIUM

- No unresolved findings. The active-query supported-year boundary found by independent QCHECK was fixed and regression-tested before this review.

#### LOW

- No findings.

### Review disposition

- PASS. The staged candidate is ready for commit and PR submission.
- Hosted GitHub checks remain a separate gate; any zero-step billing-lock result must be reported as infrastructure-blocked rather than source-passing.
