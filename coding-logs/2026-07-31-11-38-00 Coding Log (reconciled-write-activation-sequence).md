# Reconciled control-plan write activation sequence

- Created: 2026-07-31 11:38:00 +0700
- Backend planning baseline: `b27eccc845e2a622b3fecf9581e08f316246af73`
- Frontend `origin/main` baseline: `fbd4ce4df0bb0476b7cd402ac1a4e180a91a7792`
- Existing frontend PRs:
  - FE-5: `#22`, `feature/fe5-mutation-policy`, `5d4072f24aee598c4215c9b2aa547c3b45d4bfbd`
  - FE-6: `#23`, `feature/fe6-submission-client`, `47b92458f9ddc0bd6091af0ef7242a96aeb87d72`
- Submission workflow: ordinary `git` and GitHub CLI (`gh`) only; no Graphite.
- Scope: planning only. No product implementation, push, merge, activation, deployment, or AWS action occurred.

## Exploration basis

Auggie semantic search could not be given the required real two-second deadline, so it was
skipped rather than allowed to block planning. This plan is based on direct file inspection,
exact-identifier searches, current Git/GitHub state, and two bounded read-only Terra checks.

Primary inspected files:

- Backend:
  - `contracts/rid-calendar/v1/README.md`
  - `services/bff-water-planning/src/schemas/planning_depth.py`
  - `services/bff-water-planning/src/services/planning_depth_submission.py`
  - `services/bff-water-planning/src/db/planning_depth_repository.py`
  - `services/bff-water-planning/src/api/routes/planning_depths.py`
  - `services/bff-water-planning/migrations/010_planning_depth_submissions.sql`
  - `services/ros-gis-integration/data/requirement_sources.json`
  - `services/ros-gis-integration/src/services/requirement_source_loader.py`
  - `ops/control-plan-read-local/orchestrate.py`
  - `ops/control-plan-read-local/run-stage-suite.py`
  - `ops/control-plan-read-local/tests/test_stage_suite.py`
  - `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`
- Frontend:
  - `lib/auth/mutation-policy.ts`
  - `lib/water-planning/planning-depth-errors.ts`
  - `lib/water-planning/planning-depth-submission.ts`
  - `lib/water-planning/irrigation-calendar.ts`
  - `lib/water-planning/planning-state.ts`
  - `lib/water-planning/draft-storage.ts`
  - `components/smart-water/dashboard/water-planning/WaterPlanningProvider.tsx`
  - `components/smart-water/dashboard/water-planning/PlanningRhsPanel.tsx`
  - `components/smart-water/dashboard/water-planning/WaterPlanningWorkspaceV2.tsx`
  - `components/smart-water/dashboard/water-planning/usePlanningDepthSubmission.ts`
  - the FE-5 and FE-6 same-origin Next route files and tests

## Confirmed current state

1. Backend `main == origin/main == b27eccc8`.
2. `LOCAL-WRITE-FOUNDATION-1` already landed through backend PRs `#142` and `#143`.
3. `LOCAL-WRITE-FOUNDATION-1` is the last registered/runnable local stage.
4. `LOCAL-WRITE-UI-1`, `LOCAL-PERSIST-ONLY-1`, `LOCAL-WRITE-ACT-1`, and
   `LOCAL-RC-1` are documented but not implemented in the stage runner.
5. The operations runbook is stale: it still labels W1/W2 and the write foundation as
   planned.
6. FE-5 and FE-6 are ordinary dependent Git branches, not a Graphite stack.
7. Both frontend PRs are open and GitHub reports them mergeable, but neither has hosted
   checks or a review decision.
8. Both frontend commit messages contain prohibited Claude attribution/session metadata
   and must be amended before landing.
9. Both PRs are dark behind
   `NEXT_PUBLIC_WATER_PLANNING_SUBMIT_ENABLED=false`.
10. FE-6 can land dark, but it is not activation-ready:
    - the frontend emits a RID-period key in a legacy `YYYY-Wnn` namespace with a
      starting-year label;
    - W2 v1 requires a real ISO Monday and matching ISO `YYYY-Wnn`;
    - the landed RID contract uses an ending-year CE/BE identity and `YYYY-Rnn`;
    - FE-6 emits only edited zone defaults, while W2 requires all six authoritative zones;
    - a retry generates a new `client_submission_id`;
    - `parsePlanningDepthFailure()` is not wired to the submit path.

## Meaning of dark versus locally exercised

`Dark` describes the merged/default state, not the whole local test run. The local acceptance
guest is specifically allowed to override the frontend and backend write flags temporarily:

1. prove both flags false and no browser mutation workflow;
2. enable backend writes while the frontend remains false and run direct W2 drills;
3. enable the frontend inside the isolated OrbStack guest and run the browser workflow;
4. restore the frontend flag false first and the backend flag false second;
5. verify the actual PM2 process environments and disabled responses after restoration.

This pattern is already proven for the backend foundation. At backend `f6584acc`, the isolated
OrbStack guest passed all seven then-implemented stages, created a real W2 submission with 41
expanded values, and restored `PLANNING_DEPTH_WRITES_ENABLED=false`.

That evidence proves the foundation and the flag-restoration mechanism. It is not final
acceptance for later backend/frontend SHAs: exact-SHA UI, persist-only, activation, and RC
evidence must be generated again after their source and harness PRs land.

# Plan Draft A — land both frontend slices dark, then close activation contracts

## Overview

Land FE-5 and FE-6 now as the already-separated, dark frontend source slices. Then land
the authoritative roster and versioned W2 RID identity, add one focused frontend readiness
follow-up, and implement each local acceptance gate in dependency order.

This plan distinguishes source landing from activation acceptance. Known contract gaps block
`LOCAL-WRITE-UI-1`; they do not block dark source merges.

## Files to change

### Existing FE-5 PR

- Amend only the FE-5 commit metadata.
- Retain the existing FE-5 source/test files:
  - `lib/auth/mutation-policy.ts`
  - `lib/auth/mutation-policy.test.ts`
  - `lib/water-planning/planning-depth-errors.ts`
  - `lib/water-planning/planning-depth-errors.test.ts`
  - `components/.../PlanningRhsPanel.tsx`
  - `components/.../PlanningRhsPanel.test.tsx`

### Existing FE-6 PR

- Rebase/retarget onto landed frontend `main`.
- Amend only the FE-6 commit metadata.
- Retain the existing route, hook, provider, builder, and test files in PR `#23`.

### Authoritative roster PR

- `services/ros-gis-integration/data/requirement_sources.json`
- `services/ros-gis-integration/src/services/requirement_source_loader.py`
- `services/ros-gis-integration/tests/unit/test_requirement_source_loader.py`
- `services/ros-gis-integration/tests/integration/test_water_requirement_repository_postgres.py`
- `contracts/planning-depth-roster/v1/*` (new)
- `services/bff-water-planning/src/schemas/planning_depth_roster.py` (new)
- `services/bff-water-planning/src/db/planning_depth_repository.py`
- `services/bff-water-planning/src/api/routes/planning_depth_roster.py` (new)
- `services/bff-water-planning/src/main.py`
- focused BFF unit/integration tests

### W2 RID identity PR (S4a)

- `contracts/planning-depth-submissions/v2/*` (new)
- `services/bff-water-planning/src/schemas/planning_depth.py`
- `services/bff-water-planning/src/services/planning_depth_submission.py`
- `services/bff-water-planning/src/db/planning_depth_repository.py`
- `services/bff-water-planning/src/api/routes/planning_depths.py`
- `services/bff-water-planning/migrations/011_planning_depth_calendar_identity.sql` (new)
- `services/bff-water-planning/migrations/manifest.json`
- W2 contract, unit, repository, migration, and disposable-Postgres tests

### Frontend write-readiness follow-up

- `lib/water-planning/irrigation-calendar.ts`
- `lib/water-planning/planning-state.ts`
- `lib/water-planning/draft-storage.ts`
- `lib/water-planning/planning-depth-submission.ts`
- `lib/water-planning/planning-depth-errors.ts`
- `components/.../usePlanningDepthSubmission.ts`
- `components/.../WaterPlanningProvider.tsx`
- `components/.../PlanningRhsPanel.tsx`
- `components/.../WaterPlanningWorkspaceV2.tsx`
- same-origin roster/POST/active route files
- colocated tests plus pinned RID and W2 v2 contract fixtures

### Local gate PRs

- `ops/control-plan-read-local/orchestrate.py`
- `ops/control-plan-read-local/run-stage-suite.py`
- `ops/control-plan-read-local/bootstrap-linux.sh`
- `ops/control-plan-read-local/run-write-browser.js` (new)
- `ops/control-plan-read-local/tests/test_stage_suite.py`
- `ops/control-plan-read-local/tests/test_local_artifacts.py`
- `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`
- new sanitized evidence directories after each exact-SHA run

## Implementation steps

Every implementation PR follows the same TDD loop:

1. Add or stub defect-sensitive tests.
2. Run them and confirm RED for the intended missing behavior.
3. Implement the smallest passing change.
4. Refactor only when necessary for readability or testability.
5. Run formatter, lint/type checks, focused tests, service-full tests, QCHECK, and formal
   `g-check`.

Execution order:

1. Amend and land FE-5 dark through normal `git`/`gh`.
2. Rebase only the FE-6 commit onto landed frontend `main`, retarget PR `#23`, amend
   attribution, validate the isolated diff, and land dark.
3. Pin the exact 41-section-to-six-zone roster and expose a strict, authenticated,
   read-only roster projection.
4. Add W2 v2 RID period identity with a discriminator; preserve W2 v1 rows and routes.
5. Update the frontend to consume the roster and W2 v2, complete all six zone defaults,
   use stable retry identity, and expose safe error/retry behavior.
6. Implement `LOCAL-WRITE-UI-1`.
7. Implement `LOCAL-PERSIST-ONLY-1`.
8. Implement FE-7 / `LOCAL-WRITE-ACT-1`.
9. Implement and pass a clean `LOCAL-RC-1`.
10. Stop. AWS requires a separate explicitly authorized turn.

## Function outline

- `build_planning_depth_roster_projection()` — returns the exact dataset version/hash,
  six zones, 41 sections, and 45,204-rai total.
- `get_planning_depth_roster()` — authenticated read-only endpoint; fail closed when the
  active projection is missing or inconsistent.
- `validate_planning_period_identity()` — validates v1 legacy or v2 RID key/date according
  to the explicit discriminator.
- `create_planning_depth_submission()` — includes calendar system in active scope, replay,
  successor, and advisory-lock identity.
- `get_active_planning_depth_submission()` — reads one explicit calendar scope only.
- `formatIrrigationWeekKey()` — emits landed contract keys such as `2025-R01`.
- `migrateDraftStoreV1ToV2()` — migrates only the frontend's known v1 RID-draft keys from
  starting-year `YYYY-Wnn` to ending-year `YYYY+1-Rnn`.
- `buildPlanningDepthSubmission()` — takes an explicit stable client ID and authoritative
  six-zone roster; emits all defaults plus optional section overrides.
- `usePlanningDepthRosterQuery()` — retrieves and strictly decodes the roster only when the
  dark flag and authoritative mutation policy permit it.
- `run_local_write_ui()` — drives two browsers through POST, active read-back, correction,
  stale conflict, retry, logout, and rollback.
- `run_local_persist_only()` — proves only W2 immutable rows change.
- `run_local_write_activation()` — performs false/true/false flags, failures, stability,
  and frontend-first rollback.
- `run_local_rc()` — recreates disposable state and reruns every stage at exact SHAs.

## Test coverage

### FE-5

- `resolvePlanningMutationPolicy grants authorized active read only`
- `resolvePlanningMutationPolicy fails closed on outage and forbidden`
- `parsePlanningDepthFailure preserves safe Retry-After`
- `PlanningRhsPanel hides submit without authoritative permission`

### FE-6 dark landing

- `active proxy returns 503 while flag false`
- `POST proxy returns 503 while flag false`
- `active decoder rejects unexpected successful payload`
- `provider threads active submission concurrency identity`

### Roster

- `manifest pins every section to exactly one zone`
- `roster contains six zones and forty-one sections`
- `roster area total equals 45204 rai`
- `roster projection includes active dataset hash`
- `roster endpoint rejects incomplete active projection`
- `roster endpoint emits no mutable GIS interpretation`

### W2 v2

- `legacy W2 rows retain legacy calendar discriminator`
- `RID request accepts contract key and span start`
- `RID request rejects ISO key under RID discriminator`
- `active lookup never crosses calendar systems`
- `advisory lock scope includes calendar discriminator`
- `replay and successor identity include calendar discriminator`
- `migration applies and reapplies without row mutation`
- `migration checksum drift fails before service start`

### Frontend readiness

- `RID vectors match ending-year CE and BE identity`
- `date and RID modes emit identical R-key`
- `v1 draft migration preserves every valid draft`
- `submission includes all six zone defaults`
- `manual retry reuses client submission identity`
- `typed failure preserves status and Retry-After`
- `roster outage hides submit and performs no POST`

### Local gates

- `stage order requires every preceding write gate`
- `write browser proves cross-context active read-back`
- `persist-only snapshot allows W2 rows only`
- `activation sequence ends frontend and backend dark`
- `write activation holds readiness for fifteen minutes`
- `RC rejects predecessor-SHA evidence`
- `RC index verifies every manifest checksum`

## Decision completeness

### Goal

Land FE-5 and FE-6 dark, close their authoritative roster and RID/W2 blockers, prove the
complete local write lifecycle, and produce an exact-SHA local release candidate.

### Non-goals

- No Graphite.
- No AWS inventory, deployment, cleanup, promotion, or activation.
- No command/machine authority.
- No reinterpretation of legacy `calendar_week`/`calendar_year`.
- No ROS workbook upload repair.
- No broader ROS runtime repair unless a named write gate proves it is required.
- No ROS recomputation triggered by planning-depth writes.

### Success criteria

- FE-5 and FE-6 are merged to frontend `main` with dark flag false and clean commit
  metadata.
- Roster contract proves 41 unique sections, six zones, and 45,204 rai.
- W2 v1 and v2 coexist without cross-calendar collision or legacy-row mutation.
- Frontend emits ending-year `YYYY-Rnn` and all six zone defaults.
- Stable replay ID, typed retry behavior, two-browser correction/conflict, and rollback pass.
- Every named local gate passes at exact final backend/frontend SHAs.
- Final frontend/backend write flags are false.
- Evidence is sanitized, hash-listed, and contains `aws_actions=false`.

### Public interfaces

- New authenticated read-only roster API and `planning-depth-roster/v1` contract.
- New `planning-depth-submissions/v2` RID request/receipt/active contract.
- W2 v1 route remains legacy-compatible.
- New migration `011`; migration `010` is never edited.
- Existing `NEXT_PUBLIC_WATER_PLANNING_SUBMIT_ENABLED` remains the only frontend
  submission flag and defaults false.
- Existing `PLANNING_DEPTH_WRITES_ENABLED` remains the backend write flag and defaults
  false.

### Edge cases and failure modes

- Missing or inconsistent roster: fail closed with no submit affordance and no POST.
- Unknown calendar discriminator: reject.
- RID key/date mismatch: reject.
- Legacy request on RID route or RID request on legacy route: reject.
- Stale active ID: `409`, preserve draft, refresh authoritative active read.
- Rate limit: preserve bounded `Retry-After`; do not mint a new replay ID.
- Redis/principal/DB outage: fail closed; reads remain where safely supported.
- Browser storage corruption: drop invalid entries without affecting valid v2 entries.
- Migration ambiguity: retain legacy label; never infer RID meaning.
- Rollback: frontend flag false first, backend flag false second; immutable history remains.

### Rollout and monitoring

- Every source PR lands dark.
- Run direct backend proof with frontend false before enabling the frontend locally.
- Monitor readiness, restart counts, `4xx/5xx`, rate-limit results, roster version/hash,
  submission replay/conflict counts, and browser forbidden-request inventory.
- Use exact-SHA evidence; never reuse predecessor evidence.
- Hosted billing-lock failures are infrastructure blockers. An admin override requires
  fresh explicit authorization per PR.

### Acceptance checks

- Frontend: focused Vitest, full `npm test`, timezone matrix, Prettier check, TypeScript
  check, production build with submission flag false, QCHECK, formal `g-check`.
- BFF: focused/unit/full pytest, contract tests, disposable-Postgres integration,
  migration apply/reapply/checksum tests, Black/Ruff/mypy where configured.
- ROS-GIS: source-loader unit suite and disposable-Postgres source activation tests.
- Ops: full `ops/control-plan-read-local/tests`, shell syntax, browser script syntax,
  progressive exact-SHA runtime stages.
- GitHub: inspect PR file list and checks; merge only through `gh` after lifecycle gates.

## Dependencies

- FE-6 source depends on FE-5 source.
- Roster authority depends on the active V5 `ros_gis.sections_current` projection.
- W2 v2 depends on the landed `contracts/rid-calendar/v1` semantics.
- Frontend readiness depends on both roster v1 and W2 v2.
- `LOCAL-WRITE-UI-1` depends on merged frontend readiness and both backend contracts.
- `LOCAL-PERSIST-ONLY-1` depends on a passing write UI gate.
- `LOCAL-WRITE-ACT-1` depends on persist-only proof.
- `LOCAL-RC-1` depends on every prior local stage.
- AWS depends on `LOCAL-RC-1 PASS` and separate authorization.

## Validation

The plan is accepted when each PR has its own RED/GREEN evidence, source gates, QCHECK,
formal `g-check`, normal GitHub PR, merge verification, and local-main landing. Runtime
acceptance remains separate from source merge and must cite exact backend/frontend SHAs.

## Wiring verification

| Component | Runtime entry point | Registration location | Schema/table |
|---|---|---|---|
| FE-5 mutation policy | `PlanningRhsPanel.DraftActionBar` | direct import | W2 active-read outcome |
| FE-6 active query | `WaterPlanningWorkspaceV2` | hook import | W2 active contract |
| FE-6 POST | `PlanningRhsPanel.onSubmit` | mutation hook + Next route | W2 request/receipt |
| Roster projection | roster GET handler | BFF `main.py` router include | `ros_gis.sections_current`, `dataset_versions` |
| W2 v2 validator | v2 POST route | planning-depth router | contract v2 |
| W2 v2 storage | repository create/read | route dependency | `water_planning.planning_depth_submissions` |
| Migration 011 | BFF migration runner | migration manifest | planning-depth submissions/indexes |
| Draft migration | provider hydration | `draft-storage.ts` import | browser localStorage v1/v2 |
| Complete-zone builder | provider submit builder | `PlanningRhsPanel` callback | roster v1 + W2 v2 |
| Write UI browser | `run_local_write_ui()` | stage dispatch + bootstrap artifacts | HTTP/UI + W2 tables |
| Persist-only proof | `run_local_persist_only()` | stage dispatch | W2, ROS, Scheduler snapshots |
| Write activation | `run_local_write_activation()` | stage dispatch | flags/readiness/evidence |
| Final RC | `orchestrate.py run-rc` | CLI parser/dispatcher | all stage manifests |

## Cross-language schema verification

Before migration 011:

1. Search every Python, JavaScript, and SQL use of `week_key`, `week_date`,
   `calendar_week`, and `calendar_year`.
2. Record W2's actual table/index/lock/query scope.
3. Record frontend `ActivePeriod`, localStorage, request-builder, query-key, and route
   semantics.
4. Record the landed RID vector/hash and ending-year identity.
5. Confirm roster source identity and dataset hash in ROS-GIS and BFF.
6. Prove v1 and v2 routes cannot select the other calendar system.

## Decision-complete checklist

- [x] Goal, non-goals, success criteria, public interfaces, rollout, and backout locked.
- [x] FE-5 and FE-6 dark landing separated from activation acceptance.
- [x] Normal Git/GitHub workflow locked; Graphite excluded.
- [x] Every behavior change has defect-sensitive tests.
- [x] Migration 010 remains immutable; migration 011 is additive/versioned.
- [x] Wiring covers routes, storage, frontend consumers, stages, and evidence.
- [x] AWS boundary remains separate.

# Plan Draft B — hold FE-6 until backend contracts are activation-ready

## Overview

Land FE-5 dark, but keep FE-6 open while roster and W2 RID contracts are implemented. Amend
FE-6 in place against the final backend contracts, then land it once it is ready for
`LOCAL-WRITE-UI-1`.

This reduces the number of frontend follow-up PRs, but prolongs and expands the already-open
FE-6 PR.

## Files to change

The backend roster, W2 v2, frontend readiness, and harness files are the same as Draft A.
The difference is that the frontend readiness changes are folded into PR `#23` instead of a
separate post-merge frontend PR.

## Implementation steps

1. Land FE-5 through ordinary `git`/`gh`.
2. Keep FE-6 dark and open.
3. Land roster authority/read contract.
4. Land W2 v2 RID identity and migration 011.
5. Rebase FE-6 onto frontend `main`, expand it to consume both contracts, and complete retry
   and error handling.
6. Land FE-6 once its entire activation-readiness source surface passes.
7. Implement the four local gates in the same order as Draft A.

The same tests-first loop applies to every implementation PR.

## Function outline

The functions are the same as Draft A. The only structural difference is that
`formatIrrigationWeekKey()`, `migrateDraftStoreV1ToV2()`,
`usePlanningDepthRosterQuery()`, and the expanded `buildPlanningDepthSubmission()` are added
inside FE-6 PR `#23`.

## Test coverage

Use every Draft A test. Require the expanded FE-6 PR to prove dark behavior and
activation-readiness behavior in the same review.

## Decision completeness

### Goal

Deliver one complete FE-6 PR against settled backend contracts.

### Non-goals

The same as Draft A, including no Graphite and no AWS.

### Success criteria

- FE-6 lands only after roster and RID contracts are stable.
- No follow-up frontend readiness PR is needed before `LOCAL-WRITE-UI-1`.
- All Draft A gate and evidence criteria pass.

### Public interfaces

Identical to Draft A.

### Edge cases and failure modes

Identical to Draft A. Additionally, rebase conflicts or backend-contract drift block FE-6
landing rather than being deferred.

### Rollout and monitoring

FE-5 remains dark. FE-6 remains unmerged until activation-ready, then still lands with the
flag false. Monitoring and rollback are identical to Draft A.

### Acceptance checks

Identical to Draft A, but the FE-6 source gate is larger and must be rerun after every
backend-contract adjustment.

## Dependencies

FE-6 becomes dependent on FE-5, roster v1, and W2 v2 before source landing. Remaining gate
dependencies are identical to Draft A.

## Validation

Validate that PR `#23` contains FE-6 plus only the intentionally added readiness scope after
rebasing. Require one final contract-byte parity check before merge.

## Wiring verification

The wiring table is identical to Draft A. All frontend roster/RID/retry rows are delivered
inside PR `#23`.

## Cross-language schema verification

Identical to Draft A.

## Decision-complete checklist

- [x] Goal and gate semantics locked.
- [x] Backend-before-FE-6 trade-off explicit.
- [x] Public interfaces and migration unchanged from Draft A.
- [x] No Graphite or AWS action.

# Comparative analysis

## Draft A strengths

- Honors the agreed sequence: FE-5 then FE-6 both land dark.
- Keeps existing PR `#23` reviewable and preserves its original source boundary.
- Separates source availability from activation proof.
- Lets roster/calendar work proceed without keeping a cross-repo frontend PR open.

## Draft A gaps/costs

- Requires a focused frontend follow-up before the UI gate.
- Produces a temporarily merged but intentionally non-activatable FE-6 path.
- Documentation must be precise so “FE-6 merged” is not mistaken for “write accepted.”

## Draft B strengths

- Can make FE-6 activation-ready in one PR.
- Reduces the number of frontend PRs.
- Avoids merging a known non-activatable adapter.

## Draft B gaps/costs

- Contradicts the agreed dark-source landing order.
- Expands and prolongs an already-open PR across unsettled backend contracts.
- Increases review size, rebase risk, and cross-repo coupling.
- Forces repeated FE-6 validation after every backend contract adjustment.

## Compliance

Both drafts preserve TDD, fail-closed behavior, versioned migration, dark defaults,
one-at-a-time source PRs, normal Git/GitHub submission, QCHECK/formal review, and the AWS
authorization boundary.

# Unified execution plan

Draft A is selected. It matches the user's clarified intent and keeps each source PR
reviewable. The plan adds an explicit acceptance-state label so FE-6 may merge dark without
being mistaken for gate-ready.

## Sequence and dependency graph

```text
DONE: backend #142/#143 -> LOCAL-WRITE-FOUNDATION-1 implemented

frontend #22 FE-5 dark
  -> frontend #23 FE-6 dark

backend authoritative roster v1
  -> backend W2 RID identity v2 / migration 011 (S4a)
      -> frontend RID/roster/retry readiness follow-up
          -> LOCAL-WRITE-UI-1
              -> LOCAL-PERSIST-ONLY-1
                  -> FE-7 / LOCAL-WRITE-ACT-1
                      -> clean LOCAL-RC-1
                          -> separately authorized AWS turn

After the write release candidate, unless separately pulled in by a failed named gate:
ROS-GIS RID producer integration -> ROS boot repair -> workbook vertical slice
-> remaining legacy-calendar audit/backfill (S4b)
```

## PR 0 — acknowledge completed foundation

- Do not rebuild `LOCAL-WRITE-FOUNDATION-1`.
- Update the stale operations runbook during the first harness/documentation PR.
- Re-run foundation at the final candidate SHA; do not reuse predecessor evidence.
- A missing tracked current-SHA foundation archive is an evidence task, not missing source
  implementation.

## PR 1 — FE-5 existing PR #22

1. Create an isolated frontend worktree for `feature/fe5-mutation-policy`.
2. Fetch and verify the remote branch tip before rewriting.
3. Amend the commit message:
   - retain Conventional Commit intent;
   - remove `Co-Authored-By` Claude/Anthropic references;
   - remove Claude session metadata.
4. Run focused FE-5 tests, full frontend tests, formatting, typecheck, timezone tests, and
   dark production build.
5. Install the FE-5 candidate in the isolated OrbStack guest with both write flags false and
   smoke the fail-closed visibility behavior.
6. Run QCHECK and formal `g-check`; remediate all confirmed findings.
7. Push only with `--force-with-lease`.
8. Inspect PR files/checks/review state using `gh`.
9. Merge with ordinary `gh pr merge` when gates permit.
10. If hosted jobs still fail to start because of billing, stop; do not assume an admin
   override from a previous PR.
11. Fast-forward local frontend `main` and verify `main == origin/main`.

Exit: FE-5 merged, flag false, no submit route or visibility activation.

## PR 2 — FE-6 existing PR #23

1. Record the old FE-5 and FE-6 OIDs.
2. After FE-5 lands, replay only the FE-6 commit(s) onto refreshed frontend
   `origin/main`; do not replay the old FE-5 commit.
3. Amend prohibited attribution/session metadata.
4. Change PR `#23` base from the FE-5 branch to `main` with `gh pr edit`.
5. Verify `origin/main..HEAD` and the PR file list contain FE-6 only.
6. Run FE-6 focused/full gates, dark build, QCHECK, and formal `g-check`.
7. Install the FE-6 candidate in OrbStack with the frontend flag false and prove the new
   proxies/control remain dark. A successful RID UI POST is not claimed at this step because
   roster and W2 v2 are not landed yet.
8. Push rewritten history only with `--force-with-lease`.
9. Merge with ordinary `gh`, subject to current checks/authorization.
10. Fast-forward local frontend `main`.

Exit: FE-6 source merged dark. Status label: `source-delivered, activation-blocked`.

## PR 3 — authoritative roster v1

Branch: `feat/ros-gis-zone-roster-v1`.

1. Write RED manifest/source-loader tests for exact section-to-zone membership.
2. Pin all 41 section memberships, not only counts/ranges.
3. Include the roster in the immutable source hash/version.
4. Add a strict `planning-depth-roster/v1` schema, valid fixture, and invalid fixtures.
5. Add BFF projection/query that joins the active dataset version and source hash.
6. Add authenticated read-only roster route.
7. Reject missing, duplicated, moved, out-of-range, non-positive-area, wrong-total, or
   non-six-zone projections.
8. Run source-loader, BFF contract/API, and disposable-Postgres tests.
9. Complete normal branch -> review -> `gh` PR -> merge -> local-main landing.

Exit: FE can retrieve six authoritative zone IDs and exact section membership without
hardcoding mutable GIS properties.

## PR 4 — W2 RID identity v2 (S4a)

Branch: `feat/planning-depth-rid-calendar-v2`.

1. Write contract and migration RED tests first.
2. Add contract v2 with explicit `calendar_system="rid-irrigation-v1"`,
   ending-year `YYYY-Rnn`, and contract-conformant week start.
3. Add migration 011:
   - preserve migration 010;
   - label existing rows `legacy-calendar-v1`;
   - support v2 RID rows without converting legacy keys;
   - include calendar system in active scope/index/lock/replay/successor identity;
   - preserve immutable row triggers;
   - apply/reapply safely.
4. Keep v1 request/active routes bound to legacy semantics.
5. Add v2 request/active routes bound to RID semantics.
6. Pin conformance to `contracts/rid-calendar/v1` vectors/hash.
7. Prove v1/v2 coexistence, conflict isolation, and no legacy-row mutation in real
   PostgreSQL.
8. Complete normal lifecycle and land.

Exit: W2 can persist and read authoritative RID weeks without reinterpreting historical
legacy keys.

## PR 5 — frontend RID/roster/retry readiness

Branch: `fix/water-planning-rid-write-readiness`.

1. Copy/pin exact RID and W2 v2 contract fixtures/hashes into the frontend test surface.
2. Write RED calendar tests for ending-year CE/BE identity and `YYYY-Rnn`.
3. Replace the frontend's starting-year `YYYY-Wnn` RID identity.
4. Add versioned local-draft migration:
   - only v1 frontend draft stores are transformed;
   - `YYYY-Wnn` maps one-to-one to ending-year `YYYY+1-Rnn`;
   - valid drafts/submission receipts are preserved;
   - corrupt values fail closed;
   - no backend legacy data is touched.
5. Add roster query/decoder and require the authoritative six-zone set.
6. Change submission builder to emit six zone defaults plus optional section overrides.
7. Move `client_submission_id` lifecycle outside the one-shot builder so manual retry reuses
   it until success/cancel/new edit.
8. Wire safe status/`Retry-After` classification into the mutation/UI.
9. Update POST/active same-origin paths to W2 v2.
10. Preserve flag false and fail closed on roster/active/principal/config outages.
11. Run frontend full gates, timezone tests, build, QCHECK, formal `g-check`, normal `gh`
    PR, merge, and local-main landing.

Exit: merged frontend source is technically capable of the named UI gate but remains dark.

## PR 6 — LOCAL-WRITE-UI-1

Branch: `test/local-write-ui-1`.

1. Add the stage to both stage-order tuples, CLI choices, dispatch, saved state, and
   run-all behavior.
2. Add a dedicated write-browser driver; do not weaken the existing read-only browser
   allowlists.
3. Add RED stage-order, artifact, browser-result, failure-manifest, rollback, and evidence
   tests.
4. Prove:
   - frontend false performs no active GET/POST mutation workflow;
   - backend true/frontend false direct W2 works;
   - frontend true permits authorized operator only;
   - date mode and RID-week mode resolve the same `YYYY-Rnn`;
   - two browser contexts see create/read-back/correction;
   - stale tab receives conflict and reconciles;
   - manual retry reuses the same client ID;
   - logout and reload fail safely;
   - field-team and principal outage preserve reads and hide writes;
   - rollback disables frontend first, backend second.
5. Emit sanitized hash-listed `LOCAL-WRITE-UI-1.json`.
6. Restore all flags false.

This gate runs with the flags temporarily true in the isolated OrbStack guest; `dark` does
not apply during the positive drill. The exit condition requires the real UI write path to
pass at exact SHAs and both flags to be false again.

## PR 7 — LOCAL-PERSIST-ONLY-1

Branch: `test/local-persist-only-1`.

1. Add the stage registration and RED snapshot/diff tests.
2. Snapshot W2 submission/value rows, ROS requirement runs/demands, Scheduler drafts, and
   control-plan hashes/versions.
3. Submit and correct planning depth through FE/W2.
4. Prove only W2 immutable submission/value rows changed.
5. Prove no ROS run/demand, Scheduler draft, control-plan version/hash, producer flag, or
   command path changed.
6. Emit sanitized `LOCAL-PERSIST-ONLY-1.json`; restore flags false.

Exit: DEC-W4 remains persist-only.

## PR 8 — FE-7 / LOCAL-WRITE-ACT-1

Branch: `test/local-write-act-1`.

1. Add the stage and RED activation-order/failure/stability/rollback tests.
2. Verify exact SHAs and migrations 009/010/011 parity.
3. Repeat production-equivalent local sequence:
   - both false;
   - backend true/frontend false;
   - frontend true;
   - failures and two-browser reconciliation;
   - 15 continuous minutes of stable readiness/restart counts;
   - frontend false;
   - backend false.
4. Confirm command/execution/producer flags remain false.
5. Confirm immutable history remains after rollback.
6. Emit sanitized `LOCAL-WRITE-ACT-1.json`.

Exit: write activation and rollback are rehearsed locally; nothing is activated externally.

## PR 9 — LOCAL-RC-1

Branch: `test/local-rc-1`.

1. Add a clean-RC orchestrator command and RED exact-SHA/index/clean-state tests.
2. Stop local apps and recreate disposable application data.
3. Install exact final backend/frontend source and manifests.
4. Apply all migrations from empty registries and prove idempotent reapply.
5. Run every local stage without skipped drills or manual DB repair.
6. Require all source gates and formal reviews to be green.
7. Finish with all production-equivalent flags false and processes stable.
8. Produce one sanitized signed/hash-listed evidence index.

Exit: `LOCAL-RC-1 PASS` at exact final SHAs.

## Step 10 — AWS boundary

No AWS action is part of this plan. After `LOCAL-RC-1 PASS`, a new explicitly authorized
operations turn may begin with read-only inventory, followed by a separately reviewed
promotion/rollback proposal.

## Deferred RID/ROS train

The write-critical portion of S4 is split out as S4a before the UI gate. The remaining work
does not block this persist-only write release unless a named local gate proves otherwise:

1. `feat/ros-gis-rid-calendar-integration`
2. `fix/ros-runtime-boot-contract`
3. `feat/ros-workbook-import-v1`
4. S4b legacy writer audit, historical profiling, and any required backfill

The Node ROS boot/workbook path is not the four-process `ros-gis-integration` runtime already
used by `LOCAL-WRITE-FOUNDATION-1`; it must not be inserted as a write-lane dependency merely
because both are called “ROS.”

## Final lifecycle rule

Every PR is handled one at a time through:

```text
refreshed main -> branch/worktree -> RED -> GREEN -> focused/full gates
-> QCHECK -> formal g-check -> conventional commit -> push
-> ordinary gh PR -> required checks/disposition -> gh merge
-> local main fast-forward -> post-merge verification
```

No `gt` or Graphite command is used anywhere.

## Execution update (2026-07-31 17:01:00 +0700) - plan analysis and PR 1 landed

### Plan analysis

- Draft A remains the correct sequence: FE-5 and FE-6 are independently reviewable dark source slices, while roster v1, W2 RID identity v2, retry identity, and complete-zone readiness remain later blockers to activation rather than blockers to source landing.
- Live GitHub state matched the plan baseline: PR #22 and PR #23 were open at the recorded OIDs, #23 was based on the FE-5 branch, neither PR had hosted checks or a review requirement, and both commit messages contained prohibited attribution/session metadata.
- The protected backend checkout remained untouched except for this user-owned current Coding Log; implementation and runtime work used isolated frontend worktrees and the harness-owned OrbStack machine.
- Auggie timed out at the required two-second boundary. Analysis fell back to the named plan, exact frontend/backend files, current Git/GitHub metadata, and two bounded read-only Terra reviews.

### PR 1 - FE-5 / frontend #22

- Old head: `5d4072f24aee598c4215c9b2aa547c3b45d4bfbd`.
- Rewritten reviewed head: `5cefe2fa0ad9572640bdc1200673bcd56247882c`.
- Independent QCHECK found that `not-requested` and `loading` had drifted from the locked DREP's `unavailable` state to an unplanned fourth `pending` state. The finding was accepted and fixed test-first.
- RED: `npx vitest run lib/auth/mutation-policy.test.ts components/smart-water/dashboard/water-planning/PlanningRhsPanel.test.tsx` failed 3 tests because the policy returned `pending` and the default panel omitted the unavailable status.
- GREEN: the focused FE-5 suite passed 70 tests after restoring the three-state contract and strengthening default-status component assertions.
- Full source gates passed: three complete Vitest runs (72 files / 666 tests each), UTC/Asia-Bangkok/America-New-York full matrix (72 / 666 each), Prettier, TypeScript, lint with baseline warnings only, and production build with `NEXT_PUBLIC_WATER_PLANNING_SUBMIT_ENABLED=false`.
- Formal `g-check` recorded no remaining findings after remediation. Numeric-only `Retry-After` matches the locked `retryAfterSeconds` return contract and remains unwired until FE-6.
- Isolated-guest exact-head smoke: authenticated V2 planning workspace visible, Submit count `0`, unavailable-status count `1`, planning-depth mutation request count `0`; live BFF process flag remained `PLANNING_DEPTH_WRITES_ENABLED=false`; frontend server stopped; final frontend build restored both V2 and submit flags false.
- Two temporary smoke-wrapper failures were diagnosed without product changes: the first npm invocation omitted dev dependencies because `NODE_ENV=production`; the second started Next from the wrapper directory. After correcting the temporary wrapper, the exact-head smoke passed.
- Push used an exact old-OID `--force-with-lease`. GitHub reported #22 `MERGEABLE/CLEAN`, no checks configured, and no review requirement. No admin override was used.
- PR #22 merged normally at `2026-07-31T09:59:30Z` as squash commit `1fff435623c505e483983a6924883e68d08cc26a`.
- Frontend local `main == origin/main == 1fff435623c505e483983a6924883e68d08cc26a`.
- Exact merged-SHA verification passed 70 focused tests, `npx tsc --noEmit`, and the dark production build.

### PR 1 boundary

- FE-5 is source-delivered dark. No frontend submit activation, backend write activation, deployment, AWS action, database change, or command authority occurred.
- PR 2 may now replay only FE-6 onto refreshed frontend main; the old FE-5 commit must not be replayed.

## Execution update (2026-07-31 17:28:00 +0700) - PR 2 landed and lifecycle closed

### PR 2 - FE-6 / frontend #23

- Old stacked head: `47b92458f9ddc0bd6091af0ef7242a96aeb87d72`.
- Merged FE-5 base used for the replay:
  `1fff435623c505e483983a6924883e68d08cc26a`.
- Reviewed one-commit FE-6 candidate:
  `6c2768218770cb69c7046ed88e254600382b91c8`.
- The isolated replay included only the old FE-6 commit, not the superseded FE-5
  commit. The final PR diff contained 27 FE-6 files against `main`.
- Independent QCHECK reported one HIGH and two MEDIUM findings:
  - a malformed browser-facing HTTP 2xx could be treated as a successful
    receipt, invalidate the active cache, and mark a week submitted;
  - the authorization-bearing active normalizer accepted empty or malformed
    level projections;
  - the manual acceptance checklist watched a deleted endpoint.
- All three findings were accepted and fixed. The browser receipt now requires
  `success: true`, a UUID submission id, a timezone-aware instant, and a boolean
  replay marker. The active-read proxy now requires the v1 projection's exact
  fields, exactly 41 unique expanded sections, canonical zone/section and
  source relationships, and contract depth precision/range. The checklist now
  asserts no request to either current planning-depth route while dark.
- RED: the first focused run failed 16 tests / passed 72, covering the missing
  receipt decoder, malformed active projections, and malformed-2xx success.
  GREEN after implementation: 3 files / 88 tests.
- The stricter receipt boundary correctly exposed four old component fixtures
  using non-UUID `up-*` ids. Contract-valid fixtures restored the integration
  suite. A new panel regression proves malformed 2xx leaves the week unsent;
  temporarily bypassing the decoder failed exactly that test, and restoration
  returned the component file to 45/45.
- Final source gates passed:
  - focused integration: 4 files / 133 tests;
  - full suite: 73 files / 759 tests, three consecutive passes;
  - UTC, Asia/Bangkok, and America/New_York: 73 / 759 each;
  - branch-wide Prettier and `git diff --check`;
  - `npx tsc --noEmit`;
  - `npm run lint -- --quiet` with no warnings or errors;
  - production build with both frontend flags false.
- A branch-wide formatting audit found nine FE-6 files that the older record had
  incorrectly treated as formatted. They were mechanically formatted, then a
  complete 759-test/static/build pass was rerun on the exact formatted tree.
- Formal `g-check` found one additional MEDIUM documentation defect: the F8
  enablement section still described the deleted anonymous placeholder route,
  obsolete `WATER_PLANNING_SUBMIT_PATH`, and a config-only activation. It was
  rewritten for both current paths, verified-token fail-closed behavior, and
  the real activation blockers. Formal disposition: PASS, no open findings.

### Exact-candidate dark runtime evidence

- The isolated ARM64 guest checked out exact candidate
  `6c2768218770cb69c7046ed88e254600382b91c8` from a verified bundle.
- The live local auth and BFF processes were used; the BFF process flag remained
  `PLANNING_DEPTH_WRITES_ENABLED=false`.
- With V2 true and submit false, an authenticated operator saw the planning RHS,
  Submit count was `0`, and automatic planning-depth request count was `0`.
- Direct same-origin probes proved both the new active-read GET and submit POST
  return 503 while the frontend flag is false.
- The frontend server stopped, the final frontend build restored both V2 and
  submit flags false, port 9999 had no listener, the guest worktree remained at
  the exact candidate SHA, and the backend write flag remained false.
- Temporary harness-only failures caused no product or service mutation: a host
  invocation used a guest-only path, the approved transfer helper rejected a
  non-input destination, and the root-only input directory prevented the
  runtime user from reading the first bundle path. The bundle checksum matched;
  routing it through the approved input path and then copying it into the
  runtime-owned directory resolved the harness issue.

### Push, PR, merge, and local-main landing

- Push used exact old-OID lease
  `47b92458f9ddc0bd6091af0ef7242a96aeb87d72`; the remote head became exact
  candidate `6c2768218770cb69c7046ed88e254600382b91c8`.
- PR #23 was retargeted from the old FE-5 branch to `main`. GitHub reported
  `MERGEABLE/CLEAN`, no hosted checks, and no review requirement.
- The stale stacked/test-count/generated-session PR body was replaced with the
  exact candidate evidence and activation boundary.
- PR #23 merged normally without admin override at `2026-07-31T10:26:00Z` as
  squash commit `3a8590aaeba5981c9afa202873458768ac32c655`.
- Frontend local `main == origin/main ==
  3a8590aaeba5981c9afa202873458768ac32c655`.
- Exact merged-SHA verification passed 133 focused tests, `npx tsc --noEmit`,
  and the dark production build.

### Final boundary and next pickup

- PR 1 and PR 2 from this requested lifecycle are both merged and locally
  landed. FE-5 and FE-6 are source-delivered dark.
- FE-6 is **activation-blocked**, not accepted for a real RID UI POST. The
  frontend submit flag and backend write flag remain false.
- No deployment, AWS action, database mutation, backend activation, producer/
  command authority, or customer-visible write occurred.
- The plan's next independent lifecycle is PR 3 (roster v1); it was not started
  because this request authorized only PR 1 and PR 2.
