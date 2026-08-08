# Current-session delivery report and next-session optimal paths

- Created: 2026-08-01 09:58:42 +0700
- Backend repository: `/Users/subhajlimanond/dev/munbon2-backend`
- Frontend repository: `/Users/subhajlimanond/dev/smart-cms-app`
- Backend baseline: `main == origin/main == b27eccc845e2a622b3fecf9581e08f316246af73`
- Frontend landed baseline: local `main == origin/main == 3a8590aaeba5981c9afa202873458768ac32c655`
- Scope: durable session report and decision-complete pickup plan; no product implementation,
  deployment, activation, database mutation, or AWS action in this planning turn

## Executive outcome

The requested FE-5 and FE-6 lifecycle is complete. Both frontend PRs were independently
reviewed, repaired test-first, fully validated locally, exercised at their exact candidate
SHAs in the isolated ARM64 guest, merged normally without an admin override, and landed in
the frontend `main` ref. The write path remains dark by design.

The session did not prove a real RID UI write. That remains blocked by four named contracts:

1. authoritative, versioned six-zone/41-section roster provenance;
2. backend W2 RID-calendar identity v2 using ending-year `YYYY-Rnn`;
3. frontend complete-roster, stable-idempotency, 409, and 429 retry behavior;
4. the missing `LOCAL-WRITE-UI-1`, `LOCAL-PERSIST-ONLY-1`,
   `LOCAL-WRITE-ACT-1`, and `LOCAL-RC-1` harness stages.

There is also a lifecycle infrastructure gap. The frontend repository has no GitHub Actions
workflow, so PRs #22 and #23 had no hosted checks to run. The backend has hosted workflows,
but current jobs fail before a runner starts because the account is locked for billing. A
missing check is not a passing check, and a pre-run infrastructure failure is not a code-test
failure.

## Live state at handoff

| Surface | Verified state | Meaning |
| --- | --- | --- |
| Backend Git | `main == origin/main == b27eccc845e2a622b3fecf9581e08f316246af73` | Product baseline is synchronized. |
| Backend checkout | Modified `.codex/coding-log.current`; user-owned untracked logs/evidence remain | Preserve all dirty logging/evidence state. |
| Frontend Git refs | `main == origin/main == 3a8590aaeba5981c9afa202873458768ac32c655` | FE-5 and FE-6 are landed. |
| Frontend primary checkout | Clean `feature/fe6-submission-client` at `47b92458...`, intentionally not switched | Preserve the user's feature checkout; use a new isolated worktree. |
| Frontend open PRs | Only unrelated historical PR #3 into `dev` | No remaining FE-5/FE-6 PR. |
| Frontend workflows | zero workflows, zero runs, zero candidate check-runs | Hosted CI was not configured. |
| Frontend permission | current identity `SubhajL` has `write`, not admin | Can submit workflow code; cannot guarantee required-check policy. |
| Frontend rules | protection API 404; private-repo rulesets API requests Pro/public | Owner/plan action is needed to enforce required checks. |
| Backend workflows | `control-plane-hardening-tests` and other workflows exist | Backend PRs do have hosted jobs configured. |
| Backend Actions | jobs contain zero steps and annotation says the account is locked for billing | Infrastructure blocker before test execution. |
| Runtime flags | frontend submit false; backend planning-depth writes false | No active customer-visible write path. |
| Deployment/AWS | none performed | Local evidence remains rehearsal only. |

## Current-session delivery details

### FE-5 / frontend PR #22

- Original head: `5d4072f24aee598c4215c9b2aa547c3b45d4bfbd`.
- Reviewed candidate: `5cefe2fa0ad9572640bdc1200673bcd56247882c`.
- Independent QCHECK found an unauthorized fourth `pending` state. The locked three-state
  contract required `not-requested` and `loading` to fail closed as `unavailable`.
- RED reproduced three failures; GREEN restored the contract and strengthened the component
  default-status assertions.
- Focused suite passed 70 tests.
- Full source validation passed three times at 72 files / 666 tests, then passed at UTC,
  Asia/Bangkok, and America/New_York at 72 / 666 each.
- Prettier on the changed surface, TypeScript, lint, and a dark production build passed.
- Formal `g-check` finished with no open findings.
- Exact-candidate guest smoke proved authenticated V2 visibility, Submit count zero,
  unavailable status visible, zero planning-depth mutation requests, backend write flag false,
  and final frontend flags false.
- PR #22 merged normally without admin at `2026-07-31T09:59:30Z` as
  `1fff435623c505e483983a6924883e68d08cc26a`.
- Merged-SHA verification passed the 70 focused tests, TypeScript, and dark build.

### FE-6 / frontend PR #23

- Old dependent head: `47b92458f9ddc0bd6091af0ef7242a96aeb87d72`.
- Replayed only FE-6 onto the merged FE-5 base.
- Reviewed candidate: `6c2768218770cb69c7046ed88e254600382b91c8`.
- Independent QCHECK found one HIGH and two MEDIUM defects:
  - arbitrary browser-facing HTTP 2xx JSON could be accepted as a successful receipt;
  - active-read authorization accepted empty/malformed level projections;
  - the acceptance checklist watched a deleted endpoint.
- All findings were accepted and fixed test-first. The receipt decoder now requires a true
  success marker, UUID, timezone-aware instant, and boolean replay marker. The active decoder
  requires exact fields, 41 unique sections, canonical relationships, and valid depth range
  and precision.
- Formal `g-check` found one additional stale enablement-documentation defect; it was fixed.
- RED failed 16 tests as intended. GREEN passed 3 files / 88 tests, then the strengthened
  integration suite passed 4 files / 133 tests.
- Full validation passed three times at 73 files / 759 tests, then passed at UTC,
  Asia/Bangkok, and America/New_York at 73 / 759 each.
- Changed-surface Prettier, diff check, TypeScript, quiet lint, and a dark build passed.
- Exact-candidate guest smoke proved authenticated V2 visibility, Submit count zero, zero
  automatic planning requests, direct active GET and submit POST both returning 503 while
  dark, frontend server stopped, and both final flags false.
- PR #23 was retargeted to `main` and merged normally without admin at
  `2026-07-31T10:26:00Z` as
  `3a8590aaeba5981c9afa202873458768ac32c655`.
- Merged-SHA verification passed the 133 focused tests, TypeScript, and dark build.

### Hosted-check and merge disposition

- Neither frontend PR used `--admin` or any admin override.
- GitHub reported both frontend PRs mergeable/clean with no review requirement.
- Each candidate has zero check-runs because `vitsanukomet/smart-cms-app` currently contains
  no workflow definitions and has no workflow history.
- This is a missing lifecycle layer, not evidence that hosted CI passed.
- Backend PRs are different: `.github/workflows/control-plane-hardening-tests.yml` exists, but
  a current job annotation is exactly: `The job was not started because your account is
  locked due to a billing issue.`

## Gate ledger

| Gate | Status | Evidence boundary |
| --- | --- | --- |
| FE-5 source/TDD/QCHECK/g-check | PASS | Exact candidate `5cefe2fa...` and merge `1fff4356...`. |
| FE-6 source/TDD/QCHECK/g-check | PASS | Exact candidate `6c276821...` and merge `3a8590aa...`. |
| FE-5/FE-6 local exact-SHA dark smoke | PASS | Isolated guest; no mutation and flags restored false. |
| Frontend hosted CI | NOT CONFIGURED | No workflows, runs, or check-runs. |
| Backend hosted CI | INFRASTRUCTURE BLOCKED | Workflow exists; billing lock prevents job start. |
| Real RID UI POST/read-back | NOT ACCEPTED | Roster, RID-v2, and retry blockers remain. |
| Persist-only proof | NOT IMPLEMENTED | `LOCAL-PERSIST-ONLY-1` absent. |
| Local activation/rollback | NOT IMPLEMENTED | `LOCAL-WRITE-ACT-1` absent. |
| Clean release candidate | NOT IMPLEMENTED | `LOCAL-RC-1` absent. |
| AWS/production acceptance | OUT OF SCOPE | Requires local RC plus separate authorization. |

## Exploration basis and limitations

Auggie semantic retrieval exceeded the strict two-second limit and was abandoned at that
boundary. The handoff therefore uses direct exact-string/file inspection, live Git/GitHub
metadata, prior exact-candidate execution evidence, and two bounded read-only Terra audits.

Primary backend surfaces inspected:

- `services/ros-gis-integration/src/services/requirement_source_loader.py`
- `services/ros-gis-integration/data/requirement_sources.json`
- `services/bff-water-planning/src/schemas/planning_depth.py`
- `services/bff-water-planning/src/services/planning_depth_submission.py`
- `services/bff-water-planning/src/db/planning_depth_repository.py`
- `services/bff-water-planning/src/api/routes/planning_depths.py`
- `services/bff-water-planning/migrations/010_planning_depth_submissions.sql`
- `services/bff-water-planning/migrations/manifest.json`
- `contracts/rid-calendar/v1/*`
- `ops/control-plan-read-local/orchestrate.py`
- `ops/control-plan-read-local/run-stage-suite.py`
- `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`
- `.github/workflows/control-plane-hardening-tests.yml`

Primary frontend surfaces inspected:

- `package.json`, `package-lock.json`, `eslint.config.mjs`, `next.config.ts`
- `lib/water-planning/irrigation-calendar.ts`
- `lib/water-planning/planning-state.ts`
- `lib/water-planning/draft-storage.ts`
- `lib/water-planning/planning-depth-submission.ts`
- `lib/water-planning/planning-depth-errors.ts`
- `components/smart-water/dashboard/water-planning/WaterPlanningProvider.tsx`
- `components/smart-water/dashboard/water-planning/usePlanningDepthSubmission.ts`
- `components/smart-water/dashboard/water-planning/PlanningRhsPanel.tsx`
- both same-origin planning-depth route families and their tests

## Reconciled authority and stale-state corrections

1. The public roster contract must not treat raw `gis.zone` as its live projection. Current
   code loads the effective hybrid authority through the ROS requirement-source loader,
   activates an immutable dataset, and has W2 read `ros_gis.sections_current`. Roster v1 must
   expose that active projection together with its dataset version and source hash.
2. A bare `sections_current` result is still insufficient: version/hash provenance, exact
   41-section membership, six zones, and 45,204 rai must be validated and emitted.
3. `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md` is stale. It still calls
   W1/W2 and the foundation planned, calls only six stages implemented, and omits the landed
   foundation from its sequence. Source truth says the foundation is the seventh and last
   runnable stage.
4. Migration 011 does not exist. No later stage may claim 009/010/011 parity until PR 4 lands.
5. FE-5 and FE-6 must not be reopened. They are landed dark; their real-write acceptance is
   a dependency of later gates, not a missing source merge.

# Plan Draft A — CI integrity first, then resume the write critical path

## Overview

First land a focused frontend CI-foundation PR, remediate the backend Actions billing lock in
the owner lane, then continue PR 3 through PR 9. This is the safest response to the newly
confirmed hosted-check gap and is the recommended path.

## Files to change

### Frontend CI foundation (`ci/frontend-hosted-quality-gates`)

- `.github/workflows/frontend-ci.yml` (new)
- `package.json`
- `package-lock.json`
- `eslint.config.mjs`
- `scripts/check-changed-format.mjs` (new, if changed-file formatting is selected)
- `scripts/check-changed-format.test.ts` (new, if the helper contains non-trivial logic)

The current full-repository Prettier baseline fails on 218 files, and Prettier is not a locked
project dependency. Do not disguise that debt with a broad ignore file. The first CI PR should:

1. lock Prettier in `devDependencies`;
2. enforce Prettier on added/changed supported files against the PR base;
3. record full-repository formatting as explicit debt;
4. run full tests/static/build regardless of changed paths.

The workflow should target `pull_request` to `main`, `push` to `main`, and
`workflow_dispatch`, use read-only contents permission and concurrency cancellation, pin a
Node version satisfying `>=20.19.0`, run `npm ci`, changed-file Prettier, TypeScript without
incremental output, lint, the three-timezone test matrix, and a dark production build with
both frontend flags false. Direct ESLint must ignore only generated `next-env.d.ts`; it must
not globally weaken `triple-slash-reference`.

The formatter helper must receive an explicit base SHA rather than guess from a shallow
checkout: PR base SHA for `pull_request`, `github.event.before` for `push`, and `HEAD^` for a
manual run on `main`. A zero/missing push base must fail with a clear instruction or perform a
documented full baseline audit; it must never silently skip formatting.

### Backend CI coverage completed with PR 3

- `.github/workflows/control-plane-hardening-tests.yml`

Add path coverage for:

- `services/ros-gis-integration/**`
- `contracts/planning-depth-roster/**`
- `contracts/rid-calendar/**`

Add a ROS roster/source-loader job so PR 3 does not trigger only BFF tests while leaving the
authority producer untested. Use Python 3.11, the service's pinned requirements, and the
focused loader/contract suite plus any new public-contract tests.

### Backend PR 3 — authoritative roster v1

- `contracts/planning-depth-roster/v1/manifest.json` (new)
- `contracts/planning-depth-roster/v1/roster.schema.json` (new)
- valid/invalid fixtures under `contracts/planning-depth-roster/v1/`
- `services/ros-gis-integration/data/requirement_sources.json`
- `services/ros-gis-integration/src/services/requirement_source_loader.py`
- `services/ros-gis-integration/tests/unit/test_requirement_source_loader.py`
- `services/bff-water-planning/src/schemas/planning_depth_roster.py` (new)
- `services/bff-water-planning/src/api/routes/planning_depth_roster.py` (new)
- `services/bff-water-planning/src/db/planning_depth_repository.py`
- `services/bff-water-planning/src/main.py`
- BFF contract, route, repository, and disposable-Postgres tests
- `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`

### Backend PR 4 — W2 RID identity v2

- `contracts/planning-depth-submissions/v2/*` (new)
- `services/bff-water-planning/src/core/rid_calendar.py` or the existing RID adapter surface
- `services/bff-water-planning/src/schemas/planning_depth.py`
- `services/bff-water-planning/src/api/routes/planning_depths.py`
- `services/bff-water-planning/src/db/planning_depth_repository.py`
- `services/bff-water-planning/migrations/011_planning_depth_rid_calendar_v2.sql` (new)
- `services/bff-water-planning/migrations/manifest.json`
- planning-depth contract, service, repository, route, migration, and Postgres tests

### Frontend PR 5 — RID/roster/retry readiness

- pinned backend contract fixtures/hashes under the frontend test surface
- `lib/water-planning/irrigation-calendar.ts` and test
- `lib/water-planning/planning-state.ts` and test
- `lib/water-planning/draft-storage.ts` and test
- `lib/water-planning/planning-depth-roster.ts` and test (new)
- `lib/water-planning/planning-depth-submission.ts` and test
- `lib/water-planning/planning-depth-errors.ts` and test
- `WaterPlanningProvider.tsx` and test
- `usePlanningDepthSubmission.ts` and test
- `PlanningRhsPanel.tsx` and test
- roster, submit, and active same-origin route files/tests

### Local gate PRs 6 through 9

- `ops/control-plan-read-local/orchestrate.py`
- `ops/control-plan-read-local/run-stage-suite.py`
- `ops/control-plan-read-local/tests/test_orchestrate.py`
- `ops/control-plan-read-local/tests/test_stage_suite.py`
- dedicated write-browser driver and tests
- exact-stage runbook and evidence schema/index updates

## TDD and implementation sequence

1. CI foundation: write a failing clean-worktree rehearsal/assertion for the intended CI
   commands; add the workflow/scripts; prove a clean `npm ci` executes the exact job locally;
   open the PR and require a real hosted run before merging.
2. PR 3 RED: exact 41 memberships, six zones, 45,204 rai, active dataset version/hash,
   duplicates, moved sections, wrong total, non-positive areas, inactive/missing authority,
   strict schema and authenticated route failures.
3. PR 3 GREEN: bind the immutable ROS hybrid projection to the contract and expose only the
   strict read-only BFF projection. Add CI path/job wiring and repair the stale local-stage
   runbook in the same lifecycle.
4. PR 4 RED: RID ending-year/date vectors, explicit discriminator, v1/v2 coexistence,
   lock/replay/successor isolation, immutable legacy rows, migration checksum/apply/reapply.
5. PR 4 GREEN: add v2 routes and migration 011 while preserving v1 routes and migration 010.
6. PR 5 RED: date/RID equivalence, CE/BE ending-year keys, v1 draft migration, complete roster,
   stable UUID across retry/reload, 409 reconciliation, bounded 429 `Retry-After`, no retry on
   401/403, and fail-closed outages.
7. PR 5 GREEN: consume roster v1/W2 v2, build all six defaults with optional section
   overrides, retain client identity until terminal resolution, and keep the flag false.
8. PRs 6-9: add each stage RED first, implement one stage, generate fresh exact-SHA evidence,
   restore flags false, review, merge, land main, then start the next stage.

## Function outline

- `build_requirement_snapshot()` / `_effective_section_master()` — continue as producer
  authority; bind exact effective membership and raw-source provenance.
- `build_planning_depth_roster_projection()` — return strict six-zone/41-section projection
  with dataset version and source hash.
- `get_planning_depth_roster()` — authenticated read-only route; fail closed on missing or
  inconsistent active authority.
- `validate_planning_period_identity()` — validate legacy ISO v1 or RID v2 according to an
  explicit discriminator; never infer between them.
- `create_planning_depth_submission()` — include calendar system in lock, replay, active, and
  successor identity.
- `migrateDraftStoreV1ToV2()` — transform only known frontend draft storage from starting-year
  `YYYY-Wnn` to ending-year `YYYY+1-Rnn`; never touch backend legacy rows.
- `buildPlanningDepthSubmission()` — accept a caller-owned client UUID and emit six roster
  defaults plus optional section overrides.
- `usePlanningDepthRosterQuery()` — fetch and strictly decode only when the dark/authorization
  prerequisites allow it.
- `usePlanningDepthSubmission()` — retain typed failures and pending identity; reconcile 409,
  respect 429 delay, and never retry authorization failures.
- stage runners — enforce stage order, exact SHA/manifest hashes, sanitized evidence, and
  frontend-first/backend-second rollback.

## Test coverage

### CI foundation

- clean `npm ci` uses only the committed lockfile;
- changed-file formatter handles added, modified, renamed, deleted, spaced, and non-Prettier
  paths without shell interpolation;
- generated `next-env.d.ts` is excluded narrowly;
- TypeScript, lint, three timezones, and dark production build pass on a clean clone;
- hosted workflow creates a real check-run and executes non-empty steps.

### Roster v1

- exact six zones, exact 41 membership rows, exact 45,204 rai;
- dataset version and source hash are present and contract-bound;
- missing, duplicate, moved, out-of-range, invalid-area, wrong-total, inactive, and hash-drift
  projections fail closed;
- route is authenticated and read-only;
- source loader, BFF unit, and disposable-Postgres projection agree.

### W2 RID v2

- RID vectors match the landed contract for CE/BE and cross-year boundaries;
- RID request rejects ISO key under RID discriminator and vice versa;
- v1 and v2 rows coexist without reinterpretation;
- lock/replay/active/successor scopes include calendar system;
- legacy rows/triggers remain immutable;
- migration 011 applies, reapplies, and fails on checksum drift.

### Frontend readiness

- date and RID selection resolve the same ending-year `YYYY-Rnn`;
- only known draft-v1 keys migrate one-to-one; corrupt state fails closed;
- roster decoder requires exact version/hash/six-zone/41-section structure;
- submit body contains all six zone defaults and only valid section overrides;
- retry after ambiguous network/5xx reuses the same payload and UUID;
- 409 refetches/reconciles; 429 delays according to bounded `Retry-After`;
- 401/403 do not retry; user/week changes cannot reuse another pending request;
- roster, active, principal, and configuration outages hide Submit and send no POST.

### Local acceptance

- stage order/CLI/dispatch/run-all/saved-state transitions;
- exact candidate hashes and artifact manifests;
- two-context create/read/correct/conflict/reconcile;
- persist-only database snapshot/diff;
- 15-minute stability and ordered rollback;
- clean-state migration apply/reapply and all-stage RC without manual repair.

## Decision completeness

### Goal

Restore a truthful hosted validation layer, then deliver authoritative roster and RID write
contracts, a technically ready but dark frontend, and exact-SHA local write acceptance without
changing production/AWS state.

### Non-goals

- no deployment or AWS action;
- no customer-visible activation;
- no command, producer, ROS recomputation, or field-device authority;
- no reinterpretation/backfill of legacy W2 rows;
- no broad 218-file formatting cleanup hidden inside CI or feature work;
- no admin merge without fresh explicit authorization.

### Success criteria

- frontend CI produces executed hosted checks for subsequent frontend PRs;
- backend billing is restored or every pre-run blocker is explicitly recorded and merge held;
- PR 3 and PR 4 land one at a time with exact contracts and real database tests;
- PR 5 lands dark with complete roster and durable retry behavior;
- PR 6 through PR 9 pass in order at their exact final SHAs;
- final flags are false and no external activation occurred.

### Public interfaces

- authenticated read-only `planning-depth-roster/v1`;
- versioned `planning-depth-submissions/v2` RID POST and active GET;
- contract manifests, schemas, fixtures, and hashes consumed by Python and TypeScript;
- four new local evidence artifacts ending in one `LOCAL-RC-1` index.

### Edge cases and failure modes

- hosted job absent: classify not configured, never green;
- hosted job has zero steps with billing annotation: infrastructure blocked, never code failed;
- roster missing/hash drift/inconsistent: fail closed with no Submit/POST;
- RID key/date/discriminator mismatch: reject;
- legacy/v2 collision: isolate by calendar system;
- ambiguous request result: reuse idempotency identity and reconcile;
- 409: refetch, compare, and require deliberate correction;
- 429: honor safe bounded retry delay;
- auth/principal outage: no automatic retry and no mutation affordance;
- rollback: frontend false first, backend false second;
- candidate SHA changes: re-provision and rerun evidence.

### Rollout and monitoring

Each source PR remains dark. Local acceptance temporarily enables the backend, then frontend,
inside the isolated guest only. Record exact SHAs, contract hashes, dataset version/hash,
response classes, restart counts, evidence checksums, and final process environments. External
promotion begins only after a clean local RC and a separately authorized operations plan.

### Acceptance checks

- conventional commits without prohibited attribution/session metadata;
- focused and service-full tests, formatter, static checks, and builds;
- disposable-Postgres migration/projection/replay tests;
- independent QCHECK and formal `g-check` disposition;
- real hosted check execution where configured;
- ordinary PR merge, local-main landing, and post-merge verification;
- no acceptance claim based only on source inspection or predecessor evidence.

## Dependencies

- owner billing remediation is required for backend hosted jobs to execute;
- owner/admin and possibly plan changes are required to make frontend checks mandatory;
- PR 3 is the backend prerequisite for frontend roster readiness;
- PR 4 depends on the landed RID contract and must follow PR 3 in this sequence;
- PR 5 depends on PR 3, PR 4, and the frontend CI foundation;
- PR 6 depends on merged PR 5 and both backend contracts;
- PR 7 depends on PR 6 PASS;
- PR 8 depends on PR 7 PASS;
- PR 9 depends on all prior source and local stages;
- AWS depends on PR 9 PASS plus separate authorization.

## Validation commands and evidence

Exact commands must be taken from each service's current scripts/configuration. At minimum:

- frontend clean install, changed-file Prettier, lint, TypeScript, `npm run test:tz`, and dark
  `npm run build`;
- ROS-GIS focused loader/contract tests plus its full relevant pytest suite;
- BFF bare pytest plus disposable PostgreSQL planning-depth integration;
- migration apply/reapply/checksum verification;
- `git diff --check`, changed-file inventory, QCHECK, formal `g-check`;
- GitHub PR metadata and check-run steps, not only mergeability;
- exact-SHA guest evidence with final flags/process state.

## Wiring verification

| Feature | Entry point | Runtime registration | Persistence/dependency |
| --- | --- | --- | --- |
| Frontend CI | PR/push/workflow dispatch | `.github/workflows/frontend-ci.yml` | lockfile, Node, no secrets |
| ROS roster authority | `_effective_section_master()` / loader | requirement-source activation | raw GIS + workbook authority + dataset hash |
| Roster projection | roster GET handler | BFF `main.py` router include | active `ros_gis.sections_current` + dataset version/hash |
| RID v2 validation | v2 request schema/route | planning-depth router | `contracts/rid-calendar/v1` vectors/hash |
| RID v2 persistence | repository create/active | migration manifest + migration 011 | Postgres lock/index/immutable rows |
| Frontend roster | same-origin roster route/query | Water Planning provider/workspace | roster v1 contract/hash |
| Complete submit body | `buildPlanningDepthSubmission()` | submit hook/RHS callback | six defaults + section overrides |
| Durable retry | submit hook/pending storage | RHS status/reconcile actions | stable UUID + 409/429 semantics |
| Local write UI | stage runner | both stage tuples/CLI/dispatch | browser driver + W2/frontend |
| Persist-only | stage runner | both stage tuples/CLI/dispatch | DB snapshots/diffs |
| Activation rehearsal | stage runner | both stage tuples/CLI/dispatch | PM2 flags/readiness/restart counts |
| Clean RC | RC orchestrator | clean run-all command | exact sources, migrations, evidence index |

## Cross-language schema verification

1. Canonical JSON schemas/manifests/fixtures live in backend `contracts/`.
2. Python schema and repository tests validate every valid/invalid roster and W2-v2 fixture.
3. Frontend TypeScript decoders consume pinned identical fixtures and fail closed on unknown
   keys, missing rows, invalid precision, wrong hashes, and RID mismatches.
4. Both repositories record the same contract-set hash in their candidate evidence.
5. RID vectors prove ending-year CE/BE identity in Python and TypeScript across timezones.
6. Decimal planning depths cross JSON as canonical decimal strings/numbers without binary
   rounding changing the accepted three-decimal value.

## Decision-complete checklist

- [x] Current backend/frontend SHAs and dirty-state boundaries verified.
- [x] FE-5/FE-6 merge and exact-candidate evidence reconciled.
- [x] Missing frontend checks classified as not configured.
- [x] Backend pre-run failures classified as infrastructure/account blockage.
- [x] Roster authority conflict reconciled to active ROS hybrid projection plus provenance.
- [x] Files, symbols, tests, migrations, routes, stages, and dependencies identified.
- [x] Public contracts, failure behavior, rollout, monitoring, and non-goals specified.
- [ ] Frontend CI foundation implemented and hosted run green.
- [ ] Backend billing restored and hosted jobs execute.
- [ ] PR 3 through PR 9 completed sequentially.
- [ ] AWS boundary separately authorized after local RC.

# Plan Draft B — resume PR 3 immediately and hold on hosted-gate blockers

## Overview

Begin the authoritative roster PR immediately, use the complete local TDD/QCHECK/g-check
lifecycle, add the missing backend roster CI job/path wiring inside PR 3, then open the PR.
If Actions remains billing-locked, stop before merge unless the user explicitly authorizes an
admin override. Land the frontend CI foundation later, but before frontend PR 5.

## Files to change

PR 3 through PR 9 use the same exact files listed in Draft A. The frontend CI files move to
the slot between PR 4 and PR 5; no file scope is dropped or broadened.

## Implementation steps

1. Start PR 3 from refreshed backend `main`, add RED roster/source-provenance tests, implement
   the strict contract/route/projection, repair backend CI coverage and the stale runbook, and
   complete local review gates.
2. Open the ordinary PR. Merge only if hosted jobs execute and pass; otherwise hold at the
   exact billing annotation unless the user separately authorizes an admin override.
3. Complete PR 4 RID v2 and migration 011 with the same stop rule.
4. Land the frontend CI foundation and require an executed hosted run.
5. Continue PR 5 through PR 9 exactly as Draft A.

The sequence is:

```text
PR 3 roster candidate/PR
  -> backend Actions execute, or hold at exact billing blocker
  -> PR 4 RID v2
  -> frontend CI foundation
  -> PR 5 frontend readiness
  -> PR 6 -> PR 7 -> PR 8 -> PR 9
```

## Function outline

The function contracts are identical to Draft A: versioned roster projection/read,
discriminator-bound RID validation/persistence, frontend draft migration/complete submission,
durable retry/reconciliation, and ordered harness stages. Draft B must not weaken any function
boundary merely because CI lands later.

## Test coverage

The RED/GREEN and acceptance matrices are identical to Draft A. PR 3 additionally records the
hosted job outcome separately from local test results; a zero-step billing failure does not
invalidate local GREEN and does not satisfy the merge gate.

## Decision completeness

### Goal

Maximize immediate product-contract progress without silently weakening the hosted gate.

### Success criteria

- PR 3 reaches a reviewed, exact candidate and an ordinary PR quickly;
- backend CI coverage is correct even if account state prevents execution;
- no merge claims hosted success when jobs did not start;
- frontend CI is green before PR 5 begins.

### Risks and failure handling

- A billing-locked PR can stop at the merge gate after substantial implementation work.
- Deferring frontend CI repeats the process gap temporarily, though no frontend product PR is
  allowed before it is closed.
- If the user later authorizes an admin merge, retain the exact infrastructure annotation,
  local gate evidence, and post-merge verification; do not label hosted CI passed.

### Non-goals, interfaces, rollout, monitoring, and acceptance

Identical to Draft A. Only scheduling differs.

## Dependencies

PR 3 can be implemented without frontend CI. PR 4 follows PR 3. Frontend CI must land before
PR 5. PR 6 still depends on PR 3, PR 4, and PR 5; PR 7 through PR 9 remain strictly serial.
Backend billing and frontend required-check enforcement remain owner-lane dependencies.

## Validation

Use the same local, database, cross-language, QCHECK, formal-review, GitHub, and post-merge
validation as Draft A. Add an explicit merge-stop assertion when hosted jobs do not execute.

## Wiring verification

Use Draft A's wiring table without change. PR 3 must still register the roster router and CI
job/path filters in the same candidate; deferring frontend CI does not defer backend wiring.

## Cross-language schema verification

Use the same canonical backend contracts, Python validators, pinned TypeScript fixtures,
contract hashes, RID vectors, and decimal checks as Draft A.

## Decision-complete checklist

- [x] Immediate product-critical starting branch and file surface identified.
- [x] Hosted-gate stop rule stated.
- [x] Frontend CI deadline fixed before PR 5.
- [x] Remaining contract/gate dependencies unchanged.
- [ ] User explicitly chooses Draft B over the recommended Draft A.
- [ ] Backend hosted jobs execute or a separately authorized disposition is recorded.

# Comparative analysis and synthesis

## Draft A strengths

- Directly addresses the lifecycle concern raised after PRs #22/#23.
- Makes the next frontend change produce real hosted evidence.
- Discovers clean-runner Node/lockfile/build faults before they combine with PR 5.
- Establishes a stable check name that an owner can later make required.

## Draft A costs

- Adds one infrastructure PR before feature work.
- Full-repo Prettier cannot be enabled immediately because 218 baseline files fail; the
  changed-file gate and recorded cleanup debt must be explicit.
- Required-check enforcement remains an owner/plan action.
- Frontend CI does not unblock backend billing by itself.

## Draft B strengths

- Starts the true activation critical path immediately.
- PR 3 is independently useful and can be completed locally while billing is remediated.
- Backend CI workflow/path improvements live next to the authority they validate.

## Draft B costs

- The PR may stop at a known hosted infrastructure blocker.
- It postpones demonstrated hosted CI in the frontend repo.
- An explicit no-merge stop rule is necessary to avoid another lifecycle exception.

## Synthesis

Use Draft A as the default, with one refinement: owner-side backend billing remediation can
run concurrently with the frontend CI-foundation lifecycle. After that single CI PR, start
PR 3. If the user prioritizes immediate contract implementation over CI setup, Draft B is safe
only with the documented hold-at-hosted-gate rule.

# Unified execution plan

## Recommended sequence

```text
owner lane: unlock backend Actions billing and decide frontend protection/plan
    |
frontend CI-0: real hosted quality gate, dark build, no product behavior
    |
PR 3: authoritative roster v1 + ROS/BFF CI coverage + runbook correction
    |
PR 4: W2 RID identity v2 + migration 011
    |
PR 5: frontend RID/roster/durable-retry readiness, still dark
    |
PR 6: LOCAL-WRITE-UI-1
    |
PR 7: LOCAL-PERSIST-ONLY-1
    |
PR 8: FE-7 / LOCAL-WRITE-ACT-1
    |
PR 9: clean LOCAL-RC-1
    |
new explicit authorization only: AWS inventory/promotion plan
```

## Immediate new-session pickup

1. Read this Coding Log and reverify both repos; do not switch or clean either primary
   checkout.
2. Create an isolated frontend worktree from exact `origin/main` `3a8590aa...` on
   `ci/frontend-hosted-quality-gates`.
3. Implement the frontend CI foundation test-first/rehearsal-first. Use a locked Prettier and
   a changed-file formatting gate because the measured full baseline currently fails 218
   files. Do not hide or mass-format that debt.
4. Run a clean-install local rehearsal, QCHECK, formal `g-check`, commit, push, and open the
   ordinary PR.
5. Require an actual hosted workflow run with non-empty steps. If it does not start, quote the
   exact GitHub annotation and stop; do not call it a code failure or passing gate.
6. Merge normally, land frontend local `main`, and perform post-merge workflow/source checks.
7. Start PR 3 from refreshed backend `origin/main` only after CI-0 is landed, unless the user
   explicitly chooses Draft B.

## PR 3 exact pickup after CI-0

1. Create isolated backend worktree/branch `feat/ros-gis-zone-roster-v1` from refreshed main.
2. Write roster RED tests before implementation.
3. Resolve authority as active immutable ROS hybrid projection plus dataset/source provenance.
4. Add strict contract/schema/fixtures, BFF authenticated read route, ROS/BFF tests, and
   backend CI job/path wiring.
5. Correct only the stale acceptance-runbook statements directly proven obsolete.
6. Run focused/full Python gates, disposable Postgres, formatting/static checks, QCHECK, formal
   `g-check`, ordinary PR, real hosted checks, merge, local-main landing, post-merge checks.
7. Keep both write flags false and perform no UI write/deployment/AWS action.

## Lifecycle rule

Every remaining source or harness PR is handled one at a time:

```text
refresh main -> isolated branch/worktree -> RED -> GREEN -> focused/full gates
-> QCHECK -> formal g-check -> conventional commit -> push -> ordinary gh PR
-> real hosted checks or explicit infrastructure stop -> ordinary merge
-> local main fast-forward -> post-merge verification
```

No Graphite operation, direct main push, destructive cleanup, admin override without explicit
authorization, deployment, or external activation is implied by this handoff.

## Implementation summary (2026-08-05 18:41:39 +0700) - PR 3 authoritative roster v1

### Scope and branch

- Isolated worktree: `/Users/subhajlimanond/dev/munbon2-backend-pr3-roster-v1`.
- Branch: `feature/planning-depth-roster-v1`.
- Base: `b27eccc845e2a622b3fecf9581e08f316246af73` (`origin/main` at branch creation).
- The dirty primary checkout and its Coding Log pointer were preserved.

### Implemented

- Added `contracts/planning-depth-roster/v1` with a Draft 2020-12 schema, one valid
  active-V5 fixture, six invalid fixtures, per-file hashes, and contract-set hash
  `684d7a97f76341f72a65734cc6d7ac21dc07ca60cae9a7d7bcb08945942bb882`.
- The v1 schema pins all 41 ordered section identities, six zone memberships, and
  authoritative per-section areas totaling 45,204 rai.
- Added all 41 section-to-zone memberships to the ROS source manifest. The loader rejects
  missing, duplicate, moved, out-of-range, and non-integer membership values before
  activation. The membership authority is part of the immutable section source hash.
- Added the authenticated, read-only BFF route
  `GET /api/v1/water-planning/planning-depth-roster/v1` with `Cache-Control: no-store`.
  It exposes `dataset_version_id` and `source_hash`, reads only
  `ros_gis.sections_current`, joins the active `section_master` version, and fails closed
  with `503 canonical_roster_unavailable` for database/projection failures.
- Reused the same strict authoritative projection for planning-depth submissions; there is
  no raw `gis.zone` fallback.
- Added unit, shared-contract, route, repository, boot-wiring, and disposable-PostGIS
  integration coverage in both ROS and BFF.
- Added workflow path coverage plus separate ROS/PostGIS and BFF/PostGIS jobs. The BFF job
  now uses a PostGIS image because its integration fixture applies the ROS PostGIS migration.
- Corrected the local acceptance runbook so prior-SHA evidence is not presented as current
  foundation acceptance and the full seven-stage rerun is required.
- No migration, feature activation, deployment, or AWS action is part of this PR.

### TDD evidence

- ROS initial RED:
  `/Users/subhajlimanond/dev/munbon2-backend/services/ros-gis-integration/venv/bin/python -m pytest -q tests/unit/test_requirement_source_loader.py tests/unit/test_planning_depth_roster_contract.py`
  -> 7 failed, 21 passed.
- BFF initial RED:
  `/Users/subhajlimanond/dev/munbon2-backend/services/bff-water-planning/venv/bin/python -m pytest -q tests/unit/test_planning_depth_roster_contract.py tests/unit/test_planning_depth_repository.py tests/unit/test_planning_depth_roster_routes.py tests/unit/test_boot.py tests/integration/test_planning_depth_postgres.py`
  -> 14 failed, 19 passed, 8 skipped.
- Strict membership RED -> two failures proved string/bool coercion; GREEN -> 5 passed.
- Schema-authority RED -> four failures proved duplicate/moved/swapped/area-shift documents
  were accepted; GREEN -> 4 passed after prefix-item and exact-area enforcement.

### Exact-candidate validation

- ROS full bare pytest, three consecutive runs: 211 passed, 3 environment-gated skips per run.
- BFF full bare pytest, three consecutive runs: 305 passed, 9 environment-gated skips per run.
- Disposable ROS PostGIS integration, migrations 0001/0002/0003 applied, three consecutive
  runs: 2 passed per run.
- Disposable BFF PostGIS integration, three consecutive runs: 8 passed per run.
- Black check: 13 changed Python files unchanged after formatting.
- JSON parsing, workflow YAML parsing, and `git diff --check`: passed.

### Independent QCHECK disposition

- HIGH: BFF CI used plain PostgreSQL although the fixture applies a PostGIS migration.
  Fixed by using `postgis/postgis:16-3.4`; rehearsed locally against that image.
- MEDIUM: JSON Schema did not encode exact roster authority. Fixed with ordered
  `prefixItems`, exact IDs/zones/areas, and four additional semantic-drift fixtures.
- MEDIUM: fixture areas were not compared to an independent source oracle. Fixed by deriving
  the complete expected map from ROS `excel_overrides` plus `gis_expected_areas`.
- MEDIUM: changed ROS/PostGIS integration was absent from CI. Fixed with the
  `ros-postgis-integration` job and local three-run rehearsal.

## Review (2026-08-05 18:41:39 +0700) - staged working tree

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-pr3-roster-v1`
- Branch: `feature/planning-depth-roster-v1`
- Scope: staged working tree based on `b27eccc845e2a622b3fecf9581e08f316246af73`
- Commands Run: staged status/name/stat inspection; targeted numbered reads of route,
  repository, schema, loader, workflow, and tests; Auggie two-second attempt with direct-file
  fallback; Black check; JSON/YAML parse; `git diff --check`; ROS and BFF full pytest x3;
  ROS/PostGIS and BFF/PostGIS integration pytest x3.

### Findings

CRITICAL

- No findings.

HIGH

- No findings. The independent PostGIS-image finding was remediated and rerun.

MEDIUM

- No findings. The independent schema, area-oracle, and ROS-CI findings were remediated and
  rerun.

LOW

- No findings.

### Open Questions / Assumptions

- Planning-depth-roster v1 deliberately freezes the active V5 membership and per-section
  areas. A future approved area change requires a coordinated contract/manifest revision.
- The route deliberately returns 503 until an authoritative active ROS section dataset exists.

### Recommended Tests / Validation

- Preserve the exact-candidate local gates above as the merge basis.
- Inspect the real hosted check state after PR creation. Do not call an absent/zero-step run
  passing; if Actions remains billing-locked, record the exact blocker separately.
- After merge, fast-forward local `main` and rerun focused contract/route/repository/loader
  checks at the merge SHA.

### Rollout Notes

- Source and contract delivery only. No database migration, write-flag change, external
  activation, deployment, or AWS action.
- Hosted Actions billing was previously locked. The user explicitly authorized an admin merge
  for this lifecycle, but local evidence remains distinct from hosted CI evidence.

## Lifecycle completion (2026-08-05 18:44:57 +0700) - PR 145

- Source commit: `c4a1efe619bd9ef710c624e84134eafe45a7a4c4`.
- PR: `https://github.com/SubhajL/munbon2-backend/pull/145`.
- Hosted state: every job completed with zero steps. GitHub annotation:
  `The job was not started because your account is locked due to a billing issue.`
  This is recorded as an infrastructure refusal, not passing CI and not a product-test failure.
- The user explicitly requested an admin merge. PR 145 was squash/admin merged at
  `2026-08-05T11:43:21Z`.
- Merge commit: `3e5946c8b5fdba688808bcf150741f719a1ecdd9`.
- The merge tree `f043caa432fe917d912599fe67266685a0691cfc` exactly matches the source commit tree.
- Remote feature branch deleted. The isolated local worktree/branch remains available for
  audit; no user-owned dirty file was deleted.
- Primary local `main`, local `origin/main`, and remote `main` all resolve to the merge commit.
- Existing primary dirty Coding Log state was preserved.

### Exact-merge post-merge verification

- ROS full pytest: 211 passed, 3 environment-gated skips.
- BFF full pytest: 305 passed, 9 environment-gated skips.
- Fresh disposable ROS PostGIS with migrations 0001/0002/0003: 2 passed.
- Fresh disposable BFF PostGIS: 8 passed.
- Both disposable containers used `--rm` and were stopped after verification.
- Delivery status: source merged and locally landed. Activation/deployment remains explicitly
  out of scope; the new route continues to fail closed until the authoritative active ROS
  dataset exists.
