# PR 3 progress report and PR 4 RID-v2 pickup plan

- Created: 2026-08-05 19:16:49 +0700
- Backend repository: `/Users/subhajlimanond/dev/munbon2-backend`
- Backend canonical remote: `SubhajL/munbon2-backend`
- Frontend repository: `/Users/subhajlimanond/dev/smart-cms-app`
- Frontend canonical remote: `SubhajL/smart-cms-app`
- Scope: detailed current-session report plus decision-complete next-session plan
- Mutations in this planning turn: this Coding Log and `.codex/coding-log.current` only

## Executive outcome

PR 3 is fully complete. The authoritative planning-depth roster v1 was implemented test-first,
reviewed, merged by the explicitly authorized admin path, landed on local backend `main`, and
verified again at the exact squash-merge commit. No write flag, deployment, database outside
disposable test instances, or AWS environment was changed.

The next product-critical backend unit is PR 4: W2 RID identity v2 plus migration 011. It can
start immediately from backend `origin/main` `3e5946c8...`. Frontend PR 5 follows PR 4 and must
start from `SubhajL/smart-cms-app` `origin/main` `215847be...`, which already contains FE-0
through FE-6 and LOCAL-FE-CI-1/2. The `vitsanukomet` remote is legacy upstream context and is
not the pickup baseline.

## Corrected repository authority

An exploratory `gh repo view` initially selected `vitsanukomet/smart-cms-app` because that
remote still exists as `upstream`. That selection was not Git branch authority. The live Git
evidence is decisive:

| Surface | Current truth | Consequence |
| --- | --- | --- |
| Frontend branch tracking | `branch.main.remote=origin` | `origin`, not `upstream`, owns local-main synchronization. |
| Frontend `origin` | `https://github.com/SubhajL/smart-cms-app.git` | This is the canonical frontend repository. |
| Frontend `main` | `main == origin/main == remote origin/main == 215847bedfba06f00462d15971feac8505afbdfa` | FE-0..FE-6 and local CI gates are present. |
| Frontend legacy remote | `upstream=vitsanukomet/smart-cms-app`, `upstream/main=76ae738...` | Reference only; do not base new work there. |
| GitHub CLI rule | Always pass `-R SubhajL/smart-cms-app` | Prevent remote-selection ambiguity. |
| Frontend open PRs/runs | zero open PRs; zero Actions runs in `SubhajL/smart-cms-app` | Local CI exists, hosted CI is still not configured. |

## Live state at handoff

### Backend

- Branch: `main`.
- `HEAD == main == origin/main == remote main`:
  `3e5946c8b5fdba688808bcf150741f719a1ecdd9`.
- Primary checkout retains only pre-existing/user-owned Coding Log and evidence dirtiness.
- PR 3 audit worktree remains at
  `/Users/subhajlimanond/dev/munbon2-backend-pr3-roster-v1`, branch
  `feature/planning-depth-roster-v1`, source commit
  `c4a1efe619bd9ef710c624e84134eafe45a7a4c4`.
- The PR 3 remote feature branch is deleted.
- Backend has three unrelated historical draft PRs #1-#3; none belongs to this write lane.
- Hosted workflow jobs for PR 145 executed zero steps. Exact annotation:
  `The job was not started because your account is locked due to a billing issue.`

### Frontend

- Branch: `main`.
- `HEAD == main == origin/main == remote origin/main`:
  `215847bedfba06f00462d15971feac8505afbdfa`.
- Latest landed commits:
  - `215847b` PR #25: LOCAL-FE-CI-2 exact-SHA browser/runtime gate;
  - `384ade4` PR #24: LOCAL-FE-CI-1 source-quality gate;
  - `3a8590a` PR #23: dark planning-depth submission client;
  - `1fff435` PR #22: dark mutation policy.
- Primary frontend checkout is clean.
- `NEXT_PUBLIC_WATER_PLANNING_V2` and
  `NEXT_PUBLIC_WATER_PLANNING_SUBMIT_ENABLED` remain fail-closed unless exactly `true`.
- `SubhajL/smart-cms-app` has no open PR and no GitHub Actions run.
- Mandatory local candidate gate is
  `npm run ci:local:all -- --base <exact-base-sha>`; LOCAL-FE-CI-1 alone is insufficient for
  runtime/browser changes.

## Current-session delivery report — PR 3

### Scope delivered

- Added `contracts/planning-depth-roster/v1` with Draft 2020-12 schema, manifest,
  checksums, exact active-V5 fixture, and six invalid fixtures.
- Pinned all 41 ordered section identities, all six zone memberships, each approved area,
  and the 45,204-rai total.
- Added the 41-member authority to the ROS requirement source manifest and bound it into the
  immutable dataset/source hash.
- ROS rejects missing, duplicate, moved, out-of-range, non-integer, wrong-area, and wrong-total
  authority before activation.
- Added authenticated read-only BFF endpoint:
  `GET /api/v1/water-planning/planning-depth-roster/v1`.
- The route uses `Cache-Control: no-store`, projects active `dataset_version_id` and
  `source_hash`, reads only `ros_gis.sections_current` joined to active
  `ros_gis.dataset_versions`, and returns `503 canonical_roster_unavailable` on authority or
  database failure.
- Planning-depth writes now reuse the same strict projection. No raw `gis.zone` fallback was
  added.
- Added ROS and BFF unit/contract/route/repository/boot/integration coverage.
- Added a ROS/PostGIS integration job and corrected the BFF integration job to use PostGIS.
- Corrected the local acceptance runbook so old foundation evidence is not presented as
  acceptance for the new final source train.

### TDD and review evidence

- Initial ROS RED: 7 failed, 21 passed.
- Initial BFF RED: 14 failed, 19 passed, 8 skipped.
- Strict JSON membership RED reproduced string/bool coercion; GREEN passed.
- Strict schema-authority RED reproduced duplicate/moved/swapped/area-shift acceptance;
  GREEN passed after exact schema/model enforcement.
- Independent QCHECK found one HIGH and three MEDIUM issues:
  - plain PostgreSQL image could not apply the PostGIS migration;
  - published schema did not encode exact authority;
  - fixture areas lacked an independent ROS-manifest oracle;
  - changed ROS/PostGIS integration was absent from CI.
- All four findings were fixed and rerun.
- Formal `g-check` completed with no remaining findings.

### Exact-candidate validation

- ROS full pytest: 211 passed, 3 environment-gated skips, three consecutive runs.
- BFF full pytest: 305 passed, 9 environment-gated skips, three consecutive runs.
- ROS disposable PostGIS: migrations 0001/0002/0003 plus 2 passing tests, three runs.
- BFF disposable PostGIS: 8 passing tests, three runs.
- Black, JSON parse, workflow YAML parse, and diff check passed.

### PR, hosted gate, merge, and landing

- Source commit: `c4a1efe619bd9ef710c624e84134eafe45a7a4c4`.
- PR: `https://github.com/SubhajL/munbon2-backend/pull/145`.
- Hosted jobs: failed before execution with zero steps because of the billing lock; not called
  passing and not classified as a product-test failure.
- User explicitly authorized an admin merge for PR 3.
- Squash merge commit: `3e5946c8b5fdba688808bcf150741f719a1ecdd9`.
- Source and merge tree are identical:
  `f043caa432fe917d912599fe67266685a0691cfc`.
- Local `main` was fast-forwarded without disturbing the primary dirty logs/evidence.

### Exact-merge verification

- ROS full pytest: 211 passed, 3 skipped.
- BFF full pytest: 305 passed, 9 skipped.
- Fresh ROS/PostGIS: 2 passed after migrations 0001/0002/0003.
- Fresh BFF/PostGIS: 8 passed.
- Both disposable containers were stopped and auto-removed.

## Gate ledger after PR 3

| Gate | Status | Evidence boundary |
| --- | --- | --- |
| FE-5/FE-6 source | LANDED DARK | `SubhajL/smart-cms-app` main `215847b` contains the merged lineage. |
| LOCAL-FE-CI-1/2 harness | LANDED | PRs #24/#25; rerun on every exact frontend candidate. |
| Frontend hosted CI | NOT CONFIGURED | No workflow runs in `SubhajL/smart-cms-app`; local CI is not hosted CI. |
| Authoritative roster v1 | MERGED / LOCALLY VERIFIED | Backend PR #145, merge `3e5946c8...`. |
| Backend hosted CI | INFRASTRUCTURE BLOCKED | Account billing lock; every PR 145 job had zero steps. |
| W2 RID identity v2 / migration 011 | NOT IMPLEMENTED | Immediate next backend PR. |
| Frontend roster/RID/retry readiness | NOT IMPLEMENTED | Depends on PR 4; base is `SubhajL/main`. |
| LOCAL-WRITE-UI-1 | NOT IMPLEMENTED | Depends on backend PR 4 and frontend PR 5. |
| LOCAL-PERSIST-ONLY-1 | NOT IMPLEMENTED | Follows UI proof. |
| LOCAL-WRITE-ACT-1 | NOT IMPLEMENTED | Temporary local flags only; restore false. |
| LOCAL-RC-1 | NOT IMPLEMENTED | Must rerun at exact final backend/frontend/harness SHAs. |
| AWS/production | OUT OF SCOPE | Requires separate authorization after local RC. |

## Exploration basis and limitation

Auggie semantic search timed out at the mandatory two-second cutoff. Planning therefore uses
direct inspection and exact-string searches of:

- `contracts/rid-calendar/v1/*`
- `contracts/planning-depth-submissions/v1/*`
- `services/bff-water-planning/src/core/rid_calendar.py`
- `services/bff-water-planning/src/schemas/planning_depth.py`
- `services/bff-water-planning/src/services/planning_depth_submission.py`
- `services/bff-water-planning/src/db/planning_depth_repository.py`
- `services/bff-water-planning/src/api/routes/planning_depths.py`
- `services/bff-water-planning/migrations/010_planning_depth_submissions.sql`
- `services/bff-water-planning/migrations/manifest.json`
- BFF contract, migration, route, repository, runtime, and disposable-Postgres tests
- `ops/control-plan-read-local/run-stage-suite.py`
- `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`
- explicit Git/GitHub queries for both `SubhajL` repositories

# Plan Draft A — backend PR 4 first, owner lanes in parallel (recommended)

## Overview

Start backend PR 4 immediately from exact backend `origin/main` and deliver W2 RID identity v2
plus forward-only migration 011 while keeping v1 fully compatible. In parallel, the owner can
resolve backend Actions billing and decide whether to add hosted frontend CI; neither owner
lane changes the PR 4 product design.

## Files to change

- `contracts/planning-depth-submissions/v2/manifest.json` — pin v2 schemas/fixtures/hashes.
- `contracts/planning-depth-submissions/v2/submission-request.schema.json` — require schema 2,
  `calendar_system=rid-irrigation-v1`, `YYYY-Rnn`, RID-week start date.
- `contracts/planning-depth-submissions/v2/submission-receipt.schema.json` — return explicit
  calendar identity.
- `contracts/planning-depth-submissions/v2/active-submission.schema.json` — expose the same
  explicit identity with 41 expanded values.
- v2 valid/invalid fixtures — boundaries, mismatches, unknown discriminator, and legacy ISO
  under RID.
- `services/bff-water-planning/src/schemas/planning_depth_v2.py` — strict v2 Pydantic models.
- `services/bff-water-planning/src/services/planning_depth_submission.py` — v2 canonical bytes
  without changing v1 canonical hashes.
- `services/bff-water-planning/src/db/planning_depth_repository.py` — calendar-scoped create,
  replay, active, lock, and successor operations.
- `services/bff-water-planning/src/api/routes/planning_depths_v2.py` — new authenticated,
  no-store v2 POST and active GET.
- `services/bff-water-planning/src/main.py` — register the v2 router.
- `services/bff-water-planning/migrations/011_planning_depth_rid_calendar_v2.sql` — add calendar
  identity and v1/v2 integrity without editing migration 010.
- `services/bff-water-planning/migrations/manifest.json` — append exact 011 checksum.
- `services/bff-water-planning/tests/unit/test_planning_depth_v2_contract.py` — schema/model
  parity and hashes.
- `services/bff-water-planning/tests/unit/test_planning_depth_v2_routes.py` — auth/dark/error
  behavior and route wiring.
- repository, migration, boot, runtime, and Postgres integration tests — coexistence,
  immutability, parity, concurrency, and rollback compatibility.
- `ops/control-plan-read-runtime/README.md`,
  `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`, and literal migration-parity
  expectations — advance the named BFF latest migration from 010 to 011.

## Implementation steps

1. Create isolated worktree `munbon2-backend-pr4-rid-v2` and branch
   `feature/planning-depth-rid-calendar-v2` from exact `origin/main` `3e5946c8...`.
2. Add/stub v2 contract/model/route/repository/migration tests before product code.
3. Run focused tests and confirm RED for missing v2 models, route, SQL, and manifest entry.
4. Add the smallest strict v2 models using existing `irrigation_week()` and
   `irrigation_week_span()`; `week_date` is the exact first day of the named RID week.
5. Add migration 011. Preserve migration 010 bytes and existing v1 rows. Add
   `calendar_system` with a legacy-safe default, permit only the two valid
   schema/discriminator/key combinations, and scope indexes by calendar identity.
6. Add calendar-aware repository operations. Include calendar system in advisory lock,
   active lookup, replay scope, successor scope, receipt, and active projection.
7. Register separate `/api/v2/...` routes. Reuse authentication, no-store, roster, limiter,
   and dark-write helpers; do not change `/api/v1/...` behavior.
8. Refactor only where a shared helper is genuinely reused and v1 canonical bytes remain
   proven unchanged.
9. Run focused/full BFF gates, RID Python vectors/properties, Node ROS RID vectors,
   disposable PostGIS apply/reapply/coexistence tests, Black, JSON/YAML, and diff checks.
10. Run independent QCHECK, remediate findings, formal `g-check`, commit, push, ordinary PR,
    inspect actual hosted steps, and stop at the billing blocker unless the user gives fresh
    explicit merge authority.
11. After merge, fast-forward backend local `main` and rerun exact-merge gates.

### Function outline

- `PlanningDepthSubmissionRequestV2.require_rid_week_start()` — require the explicit RID
  discriminator, ending-year key, and exact administrative week start.
- `canonicalize_planning_depth_request_v2()` — produce deterministic v2 bytes including
  calendar system while preserving v1 hashes.
- `_load_active_row(..., calendar_system, week_key)` — isolate active reads by explicit
  calendar namespace.
- `create_planning_depth_submission_v2()` — lock, replay, conflict, insert, and successor
  logic scoped to RID identity.
- `get_active_planning_depth_submission_v2()` — reconstruct and hash-check the 41-row active
  RID projection.
- `submit_planning_depth_v2()` — authenticated dark-gated POST using authoritative roster.
- `get_active_planning_depth_v2()` — authenticated no-store GET for explicit RID identity.

## Test coverage

- `test_v2_contract_manifest_pins_every_schema_and_fixture` — pins all v2 bytes.
- `test_v2_model_matches_every_rid_boundary_vector` — validates ending-year boundaries.
- `test_v2_request_requires_exact_rid_week_start` — rejects interior/mismatched dates.
- `test_v2_request_rejects_iso_key_under_rid_discriminator` — prevents namespace inference.
- `test_v1_contract_and_canonical_hashes_remain_unchanged` — protects compatibility.
- `test_migration_011_preserves_v1_rows_as_iso_identity` — proves no reinterpretation.
- `test_migration_011_rejects_invalid_schema_calendar_key_combinations` — DB fails closed.
- `test_v1_and_v2_roots_coexist_in_distinct_scopes` — validates shared-table coexistence.
- `test_v2_lock_and_replay_include_calendar_system` — prevents cross-calendar collision.
- `test_v2_successor_cannot_cross_calendar_scope` — protects lineage integrity.
- `test_v2_active_read_returns_only_rid_scope` — filters exact namespace.
- `test_v2_route_preserves_auth_dark_rate_limit_and_no_store` — matches safety envelope.
- `test_runtime_migration_parity_requires_011` — advances exact runtime gate.
- `test_apply_reapply_and_checksum_drift_refusal_through_011` — proves migration ownership.

## Decision completeness

### Goal

Add explicit, immutable RID-calendar submission identity without changing or reinterpreting
legacy ISO-v1 submissions.

### Non-goals

- No frontend code.
- No edit to migration 010 or rid-calendar v1 contract bytes.
- No write-flag activation, local UI acceptance, deployment, or AWS action.
- No ROS workbook/import or legacy backfill work.

### Success criteria

- `/api/v1` behavior and canonical hashes are unchanged.
- `/api/v2` accepts only `calendar_system=rid-irrigation-v1`, `YYYY-Rnn`, and exact RID week
  starts.
- Migration 011 preserves all v1 rows and permits v1/v2 coexistence.
- Lock/replay/active/successor semantics include calendar system.
- Full and disposable-Postgres gates pass repeatedly; exact hosted status is recorded.

### Public interfaces

- POST `/api/v2/water-planning/planning-depth-submissions`.
- GET `/api/v2/water-planning/planning-depth-submissions/active` with `project_key`,
  `calendar_system`, and `week_key` query parameters.
- Request/receipt/active schema version 2.
- Required literal field `calendar_system: "rid-irrigation-v1"`.
- `week_key` format `YYYY-Rnn`, ending-year CE identity.
- `week_date` is the first day returned by `irrigation_week_span()`.
- Migration `011_planning_depth_rid_calendar_v2` adds calendar persistence and constraints.
- No new env var or message topic.

### Edge cases and failure modes

- Wrong/unknown calendar system: 422, fail closed.
- ISO key in v2 or RID key in v1: 422/model or DB constraint failure.
- Correct key with non-start/interior date: 422.
- Week 53 partial span: accepted only at its exact contract start.
- Out-of-range RID year/date: 422.
- Missing active roster: 503, unchanged fail-closed behavior.
- Cross-calendar replay/successor: conflict/DB refusal.
- Concurrent successor: 409.
- Limiter/database unavailable: existing 503 taxonomy.
- Backend billing lock: infrastructure stop; never call hosted CI passing.

### Rollout, monitoring, and backout

- Keep `PLANNING_DEPTH_WRITES_ENABLED=false` by default.
- Apply migration 011 before code activation. The old app remains compatible because legacy
  inserts receive the ISO discriminator default and still use W keys.
- Migration is forward-only once v2 rows exist; back out application code by returning to
  v1 routes, not by editing or deleting immutable rows.
- Monitor migration status/checksum, 422 identity failures, 409 conflicts, 503 roster/DB
  failures, and unexpected cross-calendar constraint failures.

### Acceptance checks

- Focused v2 contract/model/service/repository/route tests pass.
- Existing v1 contract and full BFF suite pass unchanged.
- RID Python and Node vector suites agree on contract hash/vectors.
- Fresh disposable PostGIS applies 009/010/011, reapplies no-op, preserves seeded v1 rows,
  and proves v1/v2 coexistence.
- Black, JSON/YAML, `git diff --check`, QCHECK, and formal g-check pass.

## Dependencies

- Backend roster v1 merge `3e5946c8...` — complete.
- Existing `contracts/rid-calendar/v1` and Python/Node implementations — complete.
- Backend Actions billing remediation — owner lane; affects hosted evidence, not local design.
- Fresh admin-merge authorization — not inherited from PR 3.

## Validation

- BFF focused pytest for v2 and v1 regression surfaces.
- BFF full bare pytest three consecutive runs.
- Disposable PostGIS migration/integration three consecutive runs.
- Node ROS RID calendar unit suite once because shared vectors are a cross-language boundary.
- Exact-candidate formatting/static checks, independent QCHECK, and formal g-check.
- PR metadata and zero/non-zero hosted steps inspected explicitly.
- Exact-merge focused/full/PostGIS verification after landing.

## Wiring verification

| Component | Entry point | Registration location | Schema/table |
| --- | --- | --- | --- |
| v2 request/response models | FastAPI v2 handler validation/serialization | imports in `planning_depths_v2.py` | v2 JSON schemas |
| v2 POST | `/api/v2/.../planning-depth-submissions` | `main.py:app.include_router()` | submissions + values |
| v2 active GET | `/api/v2/.../active` | same v2 router include | submissions + values |
| RID validation | request model validator | calls `core.rid_calendar` | RID v1 vectors/hash |
| v2 canonical bytes | repository create path | `canonicalize_planning_depth_request_v2()` import | request text/hash columns |
| calendar persistence | migration runner | manifest entry for 011 | `planning_depth_submissions.calendar_system` |
| scoped lock/replay | repository create path | v2 handler calls repository | advisory lock + submission indexes |
| migration parity | local stage suite | runtime test and runbook | BFF migration manifest |

## Cross-language schema verification

- Exact search confirms only BFF Python and its tests read/write
  `water_planning.planning_depth_submissions` and `planning_depth_values`.
- Python authoritative calendar implementation is `src/core/rid_calendar.py`.
- Node conformance implementation is `services/ros/src/utils/rid-calendar.js`.
- Both already consume `contracts/rid-calendar/v1`; PR 4 must not change those contract bytes.
- New planning-depth v2 JSON fixtures remain backend canonical until frontend PR 5 pins and
  consumes identical hashes.

## Decision-complete checklist

- [x] Goal/non-goals/success criteria fixed.
- [x] v1 compatibility and v2 public routes fixed.
- [x] Calendar discriminator, key, and date semantics fixed.
- [x] Migration number, table, column, index, and immutability strategy fixed.
- [x] Tests exist for each changed behavior and failure boundary.
- [x] Wiring and cross-language authority identified.
- [x] Rollout/backout and hosted blocker handling fixed.
- [x] No implementer decision remains open.

# Plan Draft B — frontend hosted CI first, then PR 4

## Overview

First add a GitHub-hosted frontend workflow in `SubhajL/smart-cms-app`, then implement backend
PR 4. This maximizes lifecycle symmetry but delays the independent backend contract and must
not pretend LOCAL-FE-CI-1/2 can run unchanged on a GitHub-hosted runner without a deliberate
runner/container design.

## Files to change

Frontend CI PR:

- `.github/workflows/frontend-ci.yml` — hosted source/static/test/dark-build workflow.
- `package.json` only if a hosted-specific aggregate script is needed.
- CI documentation explaining the boundary between hosted checks and LOCAL-FE-CI-1/2.
- Tests for any non-trivial workflow helper.

Backend PR 4 files are identical to Draft A.

## Implementation steps

1. Create isolated frontend worktree from exact `SubhajL/origin/main` `215847b`.
2. Write workflow/helper assertions first and rehearse the exact clean-install commands.
3. Add a hosted workflow that runs deterministic source/static/test/dark-build checks; do not
   claim the local ARM64/OrbStack browser harness runs on GitHub unless a compatible runner is
   explicitly provided.
4. Run mandatory `npm run ci:local:all -- --base 215847b...`, QCHECK, g-check, ordinary PR,
   and require a real non-empty hosted run.
5. Merge/land the CI PR, then execute backend PR 4 exactly as Draft A.

### Function outline

- Hosted workflow stages — clean install, changed formatting, typecheck/lint, timezone tests,
  and dark production build.
- Optional helper functions — resolve explicit base/candidate SHAs and fail closed on missing
  event ancestry.
- All PR 4 function outlines are identical to Draft A.

## Test coverage

- Hosted run contains non-empty steps on PR and main push.
- Clean install uses committed lockfile.
- Changed formatting handles rename/delete/spaces safely.
- Typecheck/lint/timezone tests/dark build pass.
- LOCAL-FE-CI-1/2 still pass exact candidate SHA locally.
- Backend PR 4 coverage remains identical to Draft A.

## Decision completeness

### Goal

Close the frontend hosted-evidence gap before the next backend feature PR.

### Non-goals

- Do not replace LOCAL-FE-CI-1/2 with weaker hosted checks.
- Do not activate frontend write flags.
- Do not combine frontend CI and backend RID changes in one PR.

### Success criteria

- A real `SubhajL/smart-cms-app` Actions run executes non-empty steps and passes.
- Local exact-SHA gates also pass.
- Backend PR 4 then proceeds unchanged.

### Public interfaces

- New GitHub workflow/check names only; no product API, DB, env, or UI change.
- Backend interfaces remain those in Draft A.

### Edge cases and failure modes

- Hosted job absent/zero-step: stop; not passing.
- Runner architecture cannot support local harness: keep evidence boundaries separate.
- Full legacy formatting debt appears: use changed-file gate; do not mass-format silently.
- Backend billing remains separately blocked.

### Rollout, monitoring, and backout

- Workflow-only rollout; remove/disable the workflow through a new PR if it is structurally
  broken.
- Monitor real step execution, duration, flakiness, and dark-build flags.
- Product remains dark.

### Acceptance checks

- Local workflow rehearsal, LOCAL-FE-CI-ALL, hosted non-empty checks, post-merge source check.
- Then all Draft A backend checks.

## Dependencies

- GitHub Actions enabled for `SubhajL/smart-cms-app`.
- A deliberate choice of hosted runner versus local-only browser evidence.
- Backend PR 4 dependencies remain unchanged.

## Validation

- Inspect workflow runs with explicit `-R SubhajL/smart-cms-app`.
- Verify checks execute actual steps.
- Preserve LOCAL-FE-CI manifests separately.
- Use Draft A validation for PR 4.

## Wiring verification

| Component | Entry point | Registration location | Schema/table |
| --- | --- | --- | --- |
| Hosted frontend workflow | PR/push/manual event | `.github/workflows/frontend-ci.yml` | none |
| Hosted scripts | workflow run steps | `package.json` script if added | lockfile |
| Local exact-SHA gates | `npm run ci:local:all` | existing local harness | evidence manifests |
| Backend RID v2 | same as Draft A | same as Draft A | migration 011 |

## Cross-language schema verification

- No cross-language schema changes in the CI PR.
- Backend PR 4 verification remains identical to Draft A.

## Decision-complete checklist

- [x] Canonical frontend repository and SHA fixed.
- [x] Hosted versus local evidence boundary explicit.
- [x] Product flags remain false.
- [x] Backend PR remains separate.
- [ ] Owner confirms Actions/runner expectations if this alternative is chosen.

# Comparative analysis and synthesis

## Draft A strengths

- Advances the next product-critical, already-unblocked backend dependency immediately.
- Preserves v1 and migration 010 while making RID identity explicit.
- Lets billing and hosted-frontend CI proceed independently without combining repositories.
- Unblocks frontend PR 5 as soon as PR 4 lands.

## Draft A risks/costs

- Backend hosted jobs may again stop at the billing annotation.
- Frontend hosted CI remains absent during PR 4, although PR 4 changes no frontend source.
- Migration 011 demands careful compatibility and real-Postgres proof.

## Draft B strengths

- Establishes real frontend hosted evidence before any further feature train.
- Clarifies hosted-versus-local runner expectations early.
- Gives later frontend PR 5 an Actions check from the start.

## Draft B risks/costs

- Delays independent backend RID work.
- A hosted runner cannot automatically reproduce the existing ARM64/OrbStack exact-SHA
  browser gate.
- Does nothing to resolve backend Actions billing.
- Requires one remaining owner choice, so it is less pickup-ready.

## Synthesis

Choose Draft A. Backend PR 4 is the critical-path dependency and is decision-complete now.
Run two owner lanes concurrently: restore backend Actions billing, and decide/add frontend
hosted CI before frontend PR 5 if practical. Never conflate those owner lanes with local
product acceptance or use them to weaken exact-SHA gates.

# Unified execution plan

## Recommended sequence

```text
backend PR 3 roster v1 — COMPLETE at 3e5946c8
    |
backend PR 4 W2 RID identity v2 + migration 011 — NEXT
    |
frontend PR 5 roster/RID/retry readiness on SubhajL/main 215847b — DARK
    |
PR 6 LOCAL-WRITE-UI-1
    |
PR 7 LOCAL-PERSIST-ONLY-1
    |
PR 8 FE-7 / LOCAL-WRITE-ACT-1, restore both flags false
    |
PR 9 clean LOCAL-RC-1 at exact final SHAs
    |
new explicit authorization only: AWS inventory/promotion

parallel owner lanes:
  - unlock backend Actions billing
  - add/decide frontend hosted CI; always keep LOCAL-FE-CI-1/2 mandatory
```

## Immediate next-session pickup

1. Read this Coding Log completely.
2. Reverify backend primary without cleaning/switching it:
   `git status --short --branch`, `git branch --show-current`,
   `git rev-parse HEAD main origin/main`, and remote `main`.
3. Reverify frontend using only `origin` and explicit GitHub repository
   `SubhajL/smart-cms-app`; do not infer authority from `upstream` or bare `gh repo view`.
4. Create `/Users/subhajlimanond/dev/munbon2-backend-pr4-rid-v2` from exact refreshed backend
   `origin/main` on `feature/planning-depth-rid-calendar-v2`.
5. Follow Draft A tests-first. Preserve migration 010 and all v1 contract bytes.
6. Implement separate v2 contracts/models/routes plus calendar-scoped shared-table persistence
   in migration 011.
7. Run focused/full/repeated/PostGIS/cross-language gates, QCHECK, and formal g-check.
8. Commit conventionally, push, open an ordinary PR, and inspect actual hosted step execution.
9. If billing still blocks every job before execution, report the exact annotation and stop at
   the merge gate. PR 3 admin authorization does not carry forward.
10. After a valid merge disposition, land local backend `main`, verify exact merge SHA, and
    only then start frontend PR 5 from current `SubhajL/origin/main`.

## Unified files-to-change list

Immediate PR 4:

- `contracts/planning-depth-submissions/v2/**`
- `services/bff-water-planning/src/schemas/planning_depth_v2.py`
- `services/bff-water-planning/src/services/planning_depth_submission.py`
- `services/bff-water-planning/src/db/planning_depth_repository.py`
- `services/bff-water-planning/src/api/routes/planning_depths_v2.py`
- `services/bff-water-planning/src/main.py`
- `services/bff-water-planning/migrations/011_planning_depth_rid_calendar_v2.sql`
- `services/bff-water-planning/migrations/manifest.json`
- relevant BFF unit/integration/runtime tests
- migration-parity runbook/runtime literals

Following frontend PR 5:

- pinned roster-v1 and planning-depth-v2 contract fixtures/hashes
- `lib/water-planning/irrigation-calendar.ts`
- planning state/draft storage/roster/submission/error modules and tests
- Water Planning provider/hook/RHS components and tests
- same-origin roster/v2-submit/v2-active route files and tests
- mandatory exact-SHA `ci:local:all` evidence

## Unified TDD sequence

1. Stub tests and missing public surfaces.
2. Confirm RED for the exact missing behavior, not syntax/test harness failure.
3. Implement the smallest v2 contract/model change.
4. Implement migration 011 and repository wiring.
5. Register routes and verify boot/runtime wiring.
6. Refactor minimally only where shared v1/v2 code is demonstrably reused.
7. Run formatter/static/focused/full/PostGIS gates.
8. Run QCHECK and formal g-check; fix accepted findings test-first.
9. Complete the ordinary PR/merge/local-main/post-merge lifecycle.

## Unified test matrix

- v2 contract schema/model/hash parity.
- RID vector and property conformance.
- v1 canonical/hash regression.
- v1/v2 migration and row coexistence.
- explicit calendar lock/replay/active/successor scoping.
- migration apply/no-op/checksum drift and runtime parity through 011.
- auth/dark/no-store/rate-limit/error route behavior.
- authoritative 41-row roster expansion.
- concurrency and failed-value rollback on real PostGIS.
- full BFF suite repeated three times before PR.
- exact-merge full plus PostGIS verification after merge.

## Unified decision completeness

### Goal

Land W2 RID identity v2 safely, then use it as the stable backend boundary for frontend PR 5
and the remaining local acceptance train.

### Non-goals

- No frontend edit in PR 4.
- No activation/deployment/AWS work.
- No rewrite of v1 history, migration 010, or RID calendar v1.
- No inherited admin authorization.

### Measurable success criteria

- Backend main contains migration 011 and v2 routes/contracts.
- Existing v1 tests/hashes/rows remain unchanged.
- Exact RID keys/dates match all golden vectors.
- Real PostGIS proves coexistence, immutability, replay, successor, and active-read behavior.
- Candidate and merge SHAs have separate validation records.

### Public interfaces

- New `/api/v2` POST/active GET.
- New planning-depth submission contract v2.
- Required `calendar_system=rid-irrigation-v1`.
- Ending-year `YYYY-Rnn` plus exact week-start date.
- Migration 011/calendar-system column and scoped indexes/constraints.
- No new env vars; existing write flag remains false.

### Failure behavior

- Identity ambiguity or drift: fail closed 422/DB constraint.
- Missing authority/dependency: fail closed 503.
- Stale/concurrent writes: 409.
- Rate limit: 429 with existing bounded `Retry-After` behavior.
- Hosted job zero-step: infrastructure blocked, not passing.

### Rollout/backout

- Forward-only migration, dark application code, no flag activation.
- Old v1 code remains compatible after migration through the ISO default.
- Backout stops using v2 routes; never mutate/delete immutable rows.

### Acceptance checks

- Commands and expected results are those listed in Draft A validation.
- Frontend PR 5 additionally must run
  `npm run ci:local:all -- --base <exact-base-sha>` on its exact candidate.

## Unified dependencies

- Complete: roster v1, RID contract v1, Python/Node RID conformance, FE-5/FE-6,
  LOCAL-FE-CI-1/2.
- Immediate owner blocker: backend Actions billing.
- Later owner improvement: frontend hosted CI.
- Strict PR dependency: PR 4 before frontend PR 5; PR 5 before local write stages.

## Unified validation and wiring table

| Component | Runtime entry point | Registration | Authority/persistence | Proof |
| --- | --- | --- | --- | --- |
| v2 schema | POST/GET serialization | v2 route imports | contract v2 | fixture parity |
| RID validator | request model | model validator | RID v1 vectors | Python + Node |
| v2 POST | `/api/v2/...` | `main.py` router | roster + submissions | route/PostGIS |
| v2 active GET | `/api/v2/.../active` | same router | scoped active row | route/PostGIS |
| calendar identity | repository insert/read | migration 011 manifest | new column/checks/indexes | migration tests |
| replay/successor | create repository path | advisory lock/query | submission lineage | concurrency tests |
| migration parity | local stage suite | runtime gate | manifest through 011 | runtime test |
| frontend consumer | PR 5 provider/routes | `SubhajL/main` | pinned backend contracts | LOCAL-FE-CI-ALL |

## Final decision-complete checklist

- [x] Canonical backend and frontend repositories/SHAs named.
- [x] Legacy `upstream` explicitly excluded from frontend pickup authority.
- [x] Current session source, tests, review, PR, merge, and exact-merge evidence recorded.
- [x] Immediate next PR, branch, files, functions, tests, migration, and routes named.
- [x] v1 compatibility and v2 semantics fixed.
- [x] Wiring, cross-language authority, rollout, backout, and failures specified.
- [x] Remaining sequence and owner lanes ordered.
- [x] No unresolved implementation decision remains for PR 4.

