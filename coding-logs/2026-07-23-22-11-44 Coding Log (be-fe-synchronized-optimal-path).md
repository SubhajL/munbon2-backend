# Coding Log: BE/FE synchronized optimal path

- Started: 2026-07-23 22:11:44 +0700
- Backend repository: `/Users/subhajlimanond/dev/munbon2-backend`
- Frontend repository: `/Users/subhajlimanond/dev/smart-cms-app`
- Backend baseline: `main == origin/main == 428baa769df65569fc0a99e03fa01df5990773bf`
- Frontend baseline: `main == origin/main == 3a16498a60927996ac38e741b276150968d0cadc`
- Delivery model: normal branch, TDD, QCHECK, g-check, PR, admin merge, and exact local-main landing
- Runtime boundary: local first; no AWS action without a later explicit authorization
- Safety boundary: evidence, writes, authority, and machine commands remain dark by default

## Evidence and planning basis

The current remote `main` tips were verified directly. FE-1 through FE-4 are
merged, while ME-1, W1, W2, FE-5, FE-6, FE-7 acceptance, FE-8, and the remaining
local gates are not implemented. The frontend has no active FE-5 through FE-8
pull request; the unrelated historical PR 3 remains open against `dev` and is
not part of this train.

Auggie semantic search could not be given the required two-second deadline.
This plan therefore uses direct inspection and exact-string searches of:

- `AGENTS.md`
- `CONTEXT.md`
- `coding-logs/2026-07-23-08-13-36 Coding Log (all-stages-local-before-aws).md`
- `coding-logs/2026-07-22-10-10-17 Coding Log (revised-control-plan-runtime-write-roadmap).md`
- `/Users/subhajlimanond/dev/smart-cms-app/coding-logs/2026-07-23-21-57-21 Coding Log (fe5-fe8-calendar-and-evidence-roadmap).md`
- `services/scheduler/src/api/v1/routes.py`
- `services/scheduler/src/schemas/control_plan.py`
- `services/bff-water-planning/src/main.py`
- `services/bff-water-planning/src/config/settings.py`
- `services/bff-water-planning/src/api/routes/control_plans.py`
- `ops/control-plan-read-local/run-stage-suite.py`
- `ops/control-plan-read-runtime/apply_bff_migration.py`
- `services/scada-gate-control-web/src/app/gates/[id]/page.tsx`
- the existing Smart CMS control-plan and Water Planning V2 files named below

## Locked dependency graph

```text
Backend critical unlock:
ME-1 contract publish
  ├─> FE-8 implementation ─> LOCAL-EVIDENCE-1
  └─> backend continues W1 ─> W2
                              └─> FE-5 ─> FE-6
                                           └─> LOCAL-WRITE-UI-1
                                               ─> LOCAL-PERSIST-ONLY-1
                                               ─> FE-7 / LOCAL-WRITE-ACT-1

Independent evidence prerequisite:
GO-READ-1 read-only gate route ────────────────> LOCAL-EVIDENCE-1

All local gates ─> clean disposable LOCAL-RC-1
LOCAL-RC-1 PASS ─> separately authorized AWS turn
```

ME-1 and FE-8 are not fully parallel. FE-8 may prepare test structure and
non-contract UI seams while ME-1 is in review, but it must not implement or
merge decoders, proxy allowlists, or evidence rendering until the merged ME-1
manifest and bytes are available. `LOCAL-EVIDENCE-1` runs only after ME-1,
FE-8, and GO-READ-1 are landed at exact SHAs.

# Plan Draft A: fully serialized train

## Overview

Land every slice in one global order: ME-1, GO-READ-1, FE-8, evidence
acceptance, W1, W2, FE-5, FE-6, and write acceptance. This has the simplest
coordination model but leaves the frontend team idle during backend work and
unnecessarily delays W1/W2.

## Files to change

- ME-1: `contracts/control-plan-evidence/v1/**` and the Scheduler/BFF
  machine-boundary contract suites.
- GO-READ-1: a new read-only SCADA web route and focused component/page tests.
- W1: Scheduler auth endpoint, response schema, router registration, and API
  tests.
- W2: BFF migration registry, migration 010, schemas, principal client,
  repository, service, routes, settings, runtime migration wiring, and tests.
- FE-8: pinned evidence contracts, strict decoders, proxy allowlist, hooks,
  evidence summary, feature flags, and tests.
- FE-5/FE-6: mutation policy, fixed planning-depth proxies/adapters, active
  read-back, reconciliation, calendar binding, provider/UI changes, and tests.
- Local gates: stage runner, orchestrator/runbook, evidence schema, and tests.

## Implementation steps

For each slice:

1. Write the named defect-sensitive tests.
2. Run them and confirm RED for the intended missing behavior.
3. Implement the smallest passing change.
4. Refactor only when required for clarity or isolated testing.
5. Run focused tests, formatting, lint/type checks, and service gates.
6. Run QCHECK and formal g-check.
7. Commit, push, open one PR, admin merge, and fast-forward local `main`.
8. Start the next slice from refreshed `origin/main`.

## Test coverage

- ME-1: manifest completeness, hash parity, valid examples, and invalid fixture
  rejection.
- GO-READ-1: exact gate lookup, read-only rendering, and zero command-capable
  imports or requests.
- W1: effective roles, revoked token, unknown role, Redis outage, no-store, and
  no sensitive fields.
- W2: roster validation, decimal canonicalization, replay, conflict, limiter,
  migration drift, transaction atomicity, and authoritative active read-back.
- FE-8: byte pinning, strict projection decoding, independent failure states,
  dark flag, and exact read-only gate link.
- FE-5/FE-6: authoritative mutation policy, fixed W2 mapping, both calendar
  modes, manual retry, conflict reconciliation, and two-browser read-back.
- Local gates: exact SHA binding, flag restoration, no-command inventory, and
  clean release-candidate replay.

## Decision completeness

- Goal: finish the entire BE/FE train safely in one sequence.
- Non-goals: daily-demand inference, ROS recomputation, direct Scheduler calls
  from Smart CMS, SCADA commands, AWS work, and production activation.
- Success: all source PRs land dark and every named local gate passes.
- Public interfaces: ME-1 evidence v1, W1 principal GET, W2 planning-depth
  POST/active GET, FE same-origin proxies, and a read-only gate route.
- Failure policy: missing contract, auth, Redis, roster, database, migration, or
  target truth fails closed.
- Rollout: frontend visibility off first and on last; rollback reverses that
  order.

## Dependencies

Every item waits for the preceding item, even where no technical dependency
exists.

## Validation

Run each repository's focused and full gates, then the applicable exact-SHA
local acceptance stage.

## Wiring verification

| Component   | Entry point                    | Registration             | Schema/table         |
| ----------- | ------------------------------ | ------------------------ | -------------------- |
| ME-1        | Scheduler/BFF evidence reads   | contract test imports    | evidence v1 files    |
| GO-READ-1   | `/read-only/gates/{id}`        | Next App Router          | status GET only      |
| W1          | `GET /api/v1/auth/principal`   | Scheduler v1 router      | Redis revocation     |
| W2          | planning-depth POST/active GET | BFF `main.py` router     | migration 010 tables |
| FE-8        | control-plan detail            | proxy/hooks/detail mount | ME-1 evidence v1     |
| FE-5/FE-6   | Water Planning V2 RHS          | provider/proxy/hooks     | W2 API               |
| Local gates | stage runner                   | orchestrator choices     | evidence manifests   |

## Cross-language schema verification

The backend Python models and JSON contract fixtures are authoritative. The
frontend TypeScript decoders consume exact copied bytes. W2 SQL names are
verified across migration, repository, stage runner, and frontend fixtures.

## Decision-complete checklist

- [x] All public routes and flags are named.
- [x] Every behavior has a defect-sensitive test.
- [x] Runtime registration is identified.
- [x] Rollback and failure policy are explicit.
- [x] No implementation decision remains open.

# Plan Draft B: contract-pipelined two-lane train

## Overview

Use ME-1 as the first backend unlock. After ME-1 merges, the frontend team
implements FE-8 while the backend owner continues W1 then W2. GO-READ-1 is
independent and may proceed in a separate isolated worktree or be supplied by
the SCADA web owner. After W2 freezes, the frontend team implements FE-5 then
FE-6. This minimizes idle time without guessing contracts.

## Files to change

The file set is identical to Draft A, but ownership is split:

- Evidence lane: ME-1, GO-READ-1, FE-8, `LOCAL-EVIDENCE-1`.
- Write lane: W1, W2, FE-5, FE-6, `LOCAL-WRITE-UI-1`,
  `LOCAL-PERSIST-ONLY-1`, and FE-7/`LOCAL-WRITE-ACT-1`.
- Final integration: `LOCAL-RC-1`.

## Implementation steps

1. Backend lands ME-1 first because it is the shortest frontend unlock.
2. Frontend starts FE-8 from refreshed `main` and pins exact ME-1 bytes.
3. Backend starts W1 immediately after the ME-1 lifecycle completes.
4. GO-READ-1 proceeds independently without touching command-capable behavior.
5. Backend lands W1, then builds and lands W2 from refreshed `main`.
6. Frontend runs FE-8 gates and lands it dark while W2 is being built.
7. Run `LOCAL-EVIDENCE-1` as soon as ME-1, FE-8, and GO-READ-1 are ready; do
   not wait for FE-5/FE-6.
8. Backend publishes the merged W2 fixtures and exact SHA.
9. Frontend lands FE-5 and then FE-6, one PR at a time, both dark.
10. Run the write gates and FE-7 false/true/false activation.
11. Recreate disposable state and run `LOCAL-RC-1`.

## Test coverage

Use Draft A coverage plus:

- `ME-1 merge artifact exactly matches FE-8 pin` — prevents contract drift.
- `evidence flag cannot expose write controls` — proves lane independence.
- `submit flag cannot expose evidence panels` — proves lane independence.
- `W2 merged fixture exactly matches FE-6 decoder` — prevents hand-copied drift.
- `later backend merge does not invalidate prior evidence manifest` — keeps
  SHA-bound acceptance truthful.

## Decision completeness

- Goal: minimize calendar time while preserving one-at-a-time merges.
- Non-goals: same-checkout concurrent edits, guessed contracts, stacked PRs, or
  combined mega-PRs.
- Success: FE work begins immediately at each backend contract freeze and no
  team waits on the unrelated lane.
- Public interfaces and failure policy match Draft A.
- Rollout: each source PR remains dark; acceptance enables only one narrow
  capability at a time and restores it false.

## Dependencies

- FE-8 depends on merged ME-1, not W1/W2.
- FE-5/FE-6 depend on merged W1/W2, not FE-8.
- `LOCAL-EVIDENCE-1` depends on ME-1, FE-8, and GO-READ-1.
- FE-7 depends on FE-5/FE-6 and the persist-only proof.
- `LOCAL-RC-1` depends on both lanes.

## Validation

Each lane runs focused source gates independently. The final gate uses one exact
combined backend SHA and one exact combined frontend SHA from clean disposable
state.

## Wiring verification

| Component   | Runtime caller                | Registration owner           | Contract authority        |
| ----------- | ----------------------------- | ---------------------------- | ------------------------- |
| ME-1        | existing Scheduler/BFF routes | existing tests/models        | backend manifest          |
| FE-8        | control-plan detail page      | Smart CMS proxy/hooks        | pinned ME-1 bytes         |
| W1          | BFF W2 principal client       | Scheduler v1 router          | strict W1 schema          |
| W2          | Smart CMS active GET/POST     | BFF router/main              | migration 010 + W2 models |
| FE-5/FE-6   | Water Planning V2 provider    | Smart CMS App Router         | pinned W2 fixtures        |
| Local gates | local stage orchestrator      | `STAGE_ORDER` and dispatcher | exact-SHA manifests       |

## Cross-language schema verification

Contract handoffs are merge artifacts, never chat descriptions. Every frontend
decoder suite runs the backend valid and invalid fixtures unchanged.

## Decision-complete checklist

- [x] Parallel work is limited to independent lanes.
- [x] Contract freeze points are explicit.
- [x] Merge order is serialized within each repository.
- [x] Acceptance waits for exact merged SHAs.
- [x] All dark flags are restored after local proof.

# Comparative analysis

Draft A is simpler to schedule but wastes the frontend team's availability and
delays W1/W2 behind FE-8 acceptance. Draft B preserves the same dependency and
safety rules while overlapping frontend FE-8 with backend W1/W2. Draft B is
therefore optimal.

The useful parallelism is:

- ME-1 preparation and FE-8 non-contract test scaffolding only.
- FE-8 implementation after ME-1 merges, in parallel with backend W1/W2.
- GO-READ-1 in parallel with either lane because it is isolated from command
  behavior.
- `LOCAL-EVIDENCE-1` in parallel with late W2 work only when it uses a separate
  disposable runtime and pins exact SHAs.

The unsafe parallelism is:

- FE-8 strict decoders before ME-1 is frozen.
- FE-5/FE-6 request/response implementation before W2 is frozen.
- two product branches editing the same frontend checkout.
- acceptance against moving branch heads.

# Unified execution plan

## Overview

Use Draft B with contract-freeze handoffs and one-at-a-time PR landing per
repository. The first backend action is ME-1 because it immediately unlocks the
frontend team; the backend then continues W1 and W2 while FE-8 proceeds. This
shortens the critical path without weakening contract, runtime, or command
boundaries.

## Goal

Land ME-1, GO-READ-1, W1, W2, FE-5, FE-6, and FE-8; complete FE-7 local
activation; and pass all remaining local gates at exact merged SHAs.

## Non-goals

- No daily-demand API or division of weekly demand by seven.
- No ROS recomputation; W2 remains persist-only.
- No direct browser-to-Scheduler or browser-to-database path.
- No current command-capable `/gates/{id}` deep link.
- No hold, resume, authority, or machine command UI.
- No automatic POST retry.
- No AWS inventory, deploy, or production activation in this plan.

## Success criteria

1. ME-1 and W2 manifests/fixtures pin exact bytes across backend and frontend.
2. FE-8 and FE-5/FE-6 land with narrow public flags false.
3. Date and RID-week modes resolve one canonical `ActivePeriod.weekKey` and
   `weekDate`; `selectedDate` remains display-only.
4. `LOCAL-EVIDENCE-1`, `LOCAL-WRITE-FOUNDATION-1`,
   `LOCAL-WRITE-UI-1`, `LOCAL-PERSIST-ONLY-1`, and
   `LOCAL-WRITE-ACT-1` pass.
5. Rollback restores frontend visibility false before backend writes false.
6. A clean `LOCAL-RC-1` passes with exact final backend/frontend SHAs.

## Public interfaces and flags

- ME-1: `contracts/control-plan-evidence/v1/**`.
- W1: `GET /api/v1/auth/principal`.
- W2 POST: `/api/v1/water-planning/planning-depth-submissions`.
- W2 GET:
  `/api/v1/water-planning/planning-depth-submissions/active`.
- Frontend same-origin POST/GET:
  `/api/smart-water-backend/water-planning/planning-depth-submissions[/active]`.
- Evidence projections: `intent-timeline`, `readback-observations`, and
  `execution-state`.
- Read-only gate target: `/read-only/gates/{encoded-gate-id}`.
- `NEXT_PUBLIC_CONTROL_PLAN_READS`: existing, exact `true`.
- `NEXT_PUBLIC_CONTROL_PLAN_EVIDENCE_READS`: new, default false.
- `NEXT_PUBLIC_WATER_PLANNING_V2`: existing, exact `true`.
- `NEXT_PUBLIC_WATER_PLANNING_SUBMIT_ENABLED`: existing name, default false.
- `NEXT_PUBLIC_GATE_OPERATIONS_URL`: optional accepted read-only route prefix.
- Backend W2 write flag: explicit exact-true setting, default false.
- Remove `WATER_PLANNING_SUBMIT_PATH`; reuse `WATER_PLANNING_BFF_URL`.

## Optimal execution sequence

### Checkpoint 0: preserve baselines

1. Keep the dirty primary checkouts untouched for product implementation.
2. Create isolated branches/worktrees from exact current `origin/main`.
3. Record backend and frontend SHAs at every contract handoff and local gate.
4. Land only one PR at a time per repository.

### Checkpoint 1: backend ME-1

Files:

- add `contracts/control-plan-evidence/v1/manifest.json`
- add the three schemas, examples, and missing/extra/scalar-drift invalid
  fixtures
- modify
  `services/scheduler/tests/unit/test_control_plan_machine_boundary_contract.py`
- modify
  `services/bff-water-planning/tests/unit/test_control_plan_machine_boundary_contract.py`

TDD:

1. Add manifest completeness/hash and valid/invalid fixture tests.
2. Confirm RED because the evidence family does not exist.
3. Add the smallest complete evidence family.
4. Run Scheduler and BFF contract suites, JSON/hash verification, formatting,
   QCHECK, and g-check.
5. PR, admin merge, and land local backend `main`.

The runtime response shapes do not change. ME-1 publishes and locks their
existing truth.

Handoff to frontend:

- merged backend SHA
- complete manifest and aggregate hash
- exact valid and invalid fixture bytes
- confirmation that the five-projection control-plan v2 family is unchanged

### Checkpoint 2: FE-8 and backend W1/W2 overlap

Immediately after ME-1 merges:

- Frontend starts FE-8 from refreshed frontend `main`.
- Backend starts W1 from refreshed backend `main`.
- GO-READ-1 may proceed independently in an isolated worktree.

#### FE-8

Add/modify the exact files from the synchronized frontend plan:

- `contracts/backend/control-plan-evidence/v1/**`
- `lib/control-plan-evidence/{contract,contract-pin,feature,gate-operations-url}.ts`
- `lib/control-plans/{api,server}.ts`
- the dynamic control-plan projection route
- `useControlPlanQueries.ts`
- `ControlPlanEvidenceSummary.tsx`
- `ControlPlanDetailPage.tsx`
- focused tests and `README.md`

Principal functions:

- `parseIntentTimeline()`, `parseReadbackObservations()`, and
  `parseExecutionState()` strictly decode ME-1.
- `isControlPlanEvidenceReadEnabled()` requires both read flags.
- `buildGateOperationsReadUrl()` accepts only the approved read-only prefix and
  appends one encoded gate ID.

Required tests:

- changed contract byte rejects the pin
- empty evidence is absent, not success
- null observed level never becomes zero
- held/resumed order is retained
- one malformed projection leaves siblings visible
- evidence summary has no action controls
- unsafe or command-capable gate target hides the link

FE-8 lands dark and does not wait for W1/W2.

#### W1

Add:

- `services/scheduler/src/api/v1/endpoints/auth.py`
- `services/scheduler/src/schemas/auth.py`
- `services/scheduler/tests/api/test_auth_principal.py`

Modify:

- `services/scheduler/src/api/v1/routes.py`
- focused existing auth unit tests when needed

Principal function:

- `get_effective_principal(current_user)` reuses existing auth helpers and
  returns only subject plus sorted canonical effective roles.

Required tests:

- operator and RID admin aliases return canonical inherited roles
- unknown role is `403`
- revoked token is `401`
- Redis outage is `503`
- sensitive token fields are absent
- every response is `no-store`

Land W1 before beginning W2 integration.

#### GO-READ-1

Add a separate route under:

- `services/scada-gate-control-web/src/app/read-only/gates/[id]/page.tsx`
- colocated/focused page and component tests

The route may call only status/read APIs. It must not import
`ConfirmCommandModal`, command-level helpers, horn helpers, control-authority
actions, or any POST-capable client. The existing `/gates/{id}` remains
command-capable and forbidden as an FE-8 target.

Required tests:

- exact route ID drives exact status GET
- read-only route contains no command controls
- no level/horn/control-authority request occurs
- signed-out and unavailable states fail closed

#### W2

After W1 merges, add/modify:

- `services/bff-water-planning/migrations/010_planning_depth_submissions.sql`
- `services/bff-water-planning/migrations/manifest.json`
- BFF migration registry/runner and
  `ops/control-plan-read-runtime/apply_bff_migration.py`
- `src/schemas/planning_depth.py`
- Scheduler principal client
- `src/services/planning_depth_submission.py`
- `src/db/planning_depth_repository.py`
- `src/api/routes/planning_depths.py`
- `src/main.py`, settings, `.env.example`, runtime preflight, and tests

Principal functions:

- `canonicalize_planning_depth_request()`
- `validate_planning_depth_roster()`
- `expand_planning_depth_values()`
- `load_effective_principal()`
- `consume_planning_depth_write_limit()`
- `create_planning_depth_submission()`
- `get_active_planning_depth_submission()`

Required tests:

- canonical decimal/hash stability and input-order independence
- 41-section/six-zone roster validation and exact membership
- W1 auth/revocation/outage taxonomy
- limiter atomicity and `Retry-After`
- replay `200`, create `201`, conflict `409`
- active GET `200` and no-row `404`
- migration apply/reapply/checksum drift
- concurrent successor serialization and transaction rollback
- immutable update/delete triggers

W2 lands with writes false. The merged W2 SHA, manifest, fixtures, status
taxonomy, and migration checksum form the frontend handoff.

### Checkpoint 3: local evidence gate

Run `LOCAL-EVIDENCE-1` as soon as ME-1, FE-8, and GO-READ-1 are all landed.
This may overlap late W2 work only in a separate disposable runtime.

The gate must prove:

- backend/frontend ME-1 byte parity
- three real bearer-forwarded projections
- present, absent, unavailable, held, and malformed states
- exact read-only gate link
- no-command import/request inventory
- zero mutation, authority, hold/resume, level, or horn requests
- evidence flag restored false

### Checkpoint 4: FE-5 then FE-6

After W2 merges:

1. Frontend refreshes `origin/main`.
2. FE-5 implements only pure policy/error classification and lands dark.
3. FE-6 starts from merged FE-5 and implements fixed W2 integration.

FE-5 functions:

- `resolvePlanningMutationPolicy()`
- `parsePlanningDepthFailure()`
- `canRenderPlanningDepthSubmit()`

FE-6 functions:

- `buildPlanningDepthSubmission()`
- `createClientSubmissionId()`
- `parsePlanningDepthAcknowledgement()`
- `parseActivePlanningDepthSubmission()`
- `reconcilePlanningDepthDraft()`
- `submitPlanningDepth()`
- `fetchActivePlanningDepth()`

Calendar lock:

- `week_key = activePeriod.weekKey`
- `week_date = activePeriod.weekDate`
- date and RID-week modes use the same canonical week identity
- `selectedDate` is display-only and is never sent as daily-demand truth

Required FE-5/FE-6 tests:

- W2 `200/404` allows, `403` forbids, `502/503` is unavailable, `401` signs out
- W2 `409/429/Retry-After` remain distinct
- both calendar modes produce the same week identity
- decimal planning depth remains exact
- no automatic POST retry
- manual retry reuses the client submission ID
- stale active ID refetches without overwriting the local draft
- two browsers observe one authoritative active row
- frontend flag false issues no active GET or POST

### Checkpoint 5: write acceptance and FE-7

1. Pass `LOCAL-WRITE-FOUNDATION-1` with backend writes temporarily enabled and
   frontend submission false.
2. Pass `LOCAL-WRITE-UI-1` with both calendar modes and two browsers.
3. Pass `LOCAL-PERSIST-ONLY-1`; only W2 immutable rows may change.
4. Execute FE-7/`LOCAL-WRITE-ACT-1`:
   - frontend false, backend false
   - backend true, frontend false
   - frontend true locally
   - exercise success/replay/correction/conflict/error scenarios
   - observe readiness, restarts, and resources for 15 continuous minutes
   - frontend false first
   - backend false second
   - prove reads and immutable history remain

Any defect becomes a separate TDD product PR followed by a full exact-SHA
rerun.

### Checkpoint 6: final clean release candidate

Recreate disposable data/runtime state and pass `LOCAL-RC-1` from the exact
final backend and frontend SHAs. Earlier stage evidence is lineage input, not a
substitute for this clean combined run.

Only a `LOCAL-RC-1 PASS` permits a later, separately authorized AWS inventory
or promotion turn.

## Failure modes

| Failure                              | Required behavior                            |
| ------------------------------------ | -------------------------------------------- |
| ME-1 or W2 byte/hash drift           | stop frontend integration                    |
| FE branch based on stale main        | recreate/rebase before continuing            |
| missing/revoked bearer               | `401`, refresh once, then sign out           |
| insufficient principal               | `403`, keep reads, hide writes               |
| Redis/principal/DB/roster outage     | `503`, no optimistic write                   |
| producer schema drift                | `502`, isolate the failed panel/path         |
| stale active submission              | `409`, refetch and preserve draft            |
| rate limit                           | `429` plus `Retry-After`, no automatic retry |
| unsafe gate target                   | hide link and fail evidence link check       |
| command request during evidence gate | immediate gate failure                       |
| local stability or restart failure   | rollback flags and stop                      |

## Rollout and monitoring

- Every new public capability is exact-true and false by default.
- Source merge does not imply runtime activation.
- Acceptance records exact SHAs, flags, route/status matrix, process readiness,
  restart counters, latency, Redis/DB health, and mutation counts.
- Evidence activation disables evidence visibility after proof.
- Write activation disables frontend visibility before backend writes.
- No AWS state changes occur in this plan.

## Validation commands

Backend slices use focused service tests first, then service formatting/lint
gates and the relevant local stage. Frontend slices use:

```bash
npx vitest run <focused changed tests>
npx prettier --check <changed files>
npx tsc --noEmit
npm run lint
for run_number in 1 2 3; do npm test || exit 1; done
NEXT_PUBLIC_WATER_PLANNING_SUBMIT_ENABLED=false \
NEXT_PUBLIC_CONTROL_PLAN_EVIDENCE_READS=false \
npm run build
```

Every source PR then receives QCHECK, formal g-check, standard PR/admin merge,
and exact local-main verification.

## Final wiring verification

| Component            | Entry point                        | Registration location               | Schema/table                 |
| -------------------- | ---------------------------------- | ----------------------------------- | ---------------------------- |
| ME-1 evidence family | existing three Scheduler/BFF reads | contract suite imports              | evidence v1 manifest/files   |
| FE-8 proxy           | same-origin projection route       | projection allowlist/decoder map    | ME-1 evidence v1             |
| FE-8 summary         | control-plan detail page           | query hooks and detail mount        | three evidence projections   |
| GO-READ-1            | `/read-only/gates/[id]`            | SCADA web App Router                | status GET only              |
| W1 principal         | Scheduler GET                      | `api/v1/routes.py`                  | Redis revocation             |
| W2 migration         | runtime migration apply            | ordered BFF manifest                | `planning_depth_*`           |
| W2 API               | BFF POST/active GET                | `main.py` router                    | immutable submissions/values |
| FE-5 policy          | Planning V2 RHS                    | imported pure policy                | W2 active status             |
| FE-6 proxies/hooks   | Water Planning V2 provider         | Next App Router/React Query         | W2 API                       |
| Local gates          | stage runner                       | stage order/dispatcher/orchestrator | SHA-bound manifests          |

## Cross-language schema verification

Before ME-1 or W2 frontend work:

1. Verify every backend manifest entry exists and every unlisted file is
   rejected.
2. Verify file and aggregate SHA-256 values.
3. Run backend valid/invalid fixtures through Python producer/BFF suites.
4. Copy the exact bytes into Smart CMS.
5. Run the same fixtures through TypeScript decoders.
6. Verify W2 SQL names across migration, repository, stage runner, and tests:
   `water_planning.planning_depth_submissions`,
   `water_planning.planning_depth_values`, and
   `water_planning.schema_migrations`.

## Decision-complete checklist

- [x] Goal, non-goals, success criteria, and exact baselines are locked.
- [x] ME-1, W1, W2, FE-5, FE-6, FE-7, FE-8, and GO-READ-1 are ordered.
- [x] Safe and unsafe parallelism are explicit.
- [x] Contract-freeze handoffs use merged bytes and SHAs.
- [x] Day and RID-week behavior remains one weekly contract.
- [x] All public routes, flags, migrations, and rollback steps are named.
- [x] Every major behavior has a defect-sensitive test.
- [x] Wiring covers entry point, registration, and schema/table.
- [x] Dark-by-default, persist-only, no-command, and local-before-AWS remain
      locked.

## One-line pickup order

```text
BE ME-1 -> FE-8 || BE W1 -> W2 || GO-READ-1
-> LOCAL-EVIDENCE-1 as soon as its three prerequisites land
-> FE-5 -> FE-6 -> write gates/FE-7
-> clean LOCAL-RC-1 -> separately authorized AWS turn
```
