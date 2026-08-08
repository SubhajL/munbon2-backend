# Revised control-plan runtime, read UI, and planning-depth roadmap

Date: 2026-07-22 (Asia/Bangkok)

Backend baseline: `main` / `origin/main` = `8095bfe37550200da00ecb554edc646febf8aff9`

Frontend baseline: `/Users/subhajlimanond/dev/smart-cms-app` `main` / `origin/main` = `7f8c8bde5b1d47212d5b42aea71d24e58540c9cd`
Supersedes: `2026-07-21-12-19-11 Coding Log (consolidated-control-plan-fe-w-runtime-roadmap).md` from archived branch `ops/archive-control-plan-runtime-roadmap-20260721`

## 1. Outcome

The original sequence is directionally correct but no longer describes the live repository. RT-1, RT-2, RT-3, RT-4, OPS-1, the bearer-verifier correction, and the 7.3 dark-deployment foundations are already merged. They must not be reimplemented. The remaining work begins with runtime acceptance, not source implementation.

The revised default sequence is:

1. Accept the already-landed runtime on a capacity-qualified host (`RTA-1`).
2. Build FE-4 now and keep it dark; do not serialize source delivery behind runtime acceptance.
3. Produce one real requirement run and one real control-plan draft, then prove all bearer reads (`AC-1`).
4. Activate core control-plan reads with a reversible configuration release (`READ-ACT-1`).
5. Publish proper schemas for the three machine-boundary evidence reads (`ME-1`).
6. Build FE-8 against those schemas, merge it dark, and activate only after real evidence exists.
7. Deliver the write lane independently: Scheduler principal (`W1`) -> planning-depth identity/migration/API (`W2`) -> frontend policy/proxy/reconciliation (`FE-5` and `FE-6`).
8. Default to persist-and-read-back only. Do not alter canonical ROS demand unless a later product decision explicitly selects and specifies recomputation (`W4`).
9. Activate writes in staging, then production, as an operations release (`WRITE-ACT-1`), not as part of a frontend merge.

The roadmap uses four states for every slice:

- **Landed**: source is merged to `origin/main`.
- **Deployed dark**: the exact merged SHA is running with producer, write, execution, and UI flags off.
- **Accepted**: runtime, real-data, authorization, migration, and rollback evidence passes.
- **Activated**: an explicit configuration release exposes the capability to its intended users.

No slice may be called complete merely because it is merged.

## 2. Planning method and evidence boundary

Auggie semantic search was attempted first and exceeded the two-second planning limit. This roadmap therefore uses direct file inspection and exact-string searches. The main inspected surfaces were:

- `CLAUDE.md`, `CONTEXT.md`, `services/scheduler/CLAUDE.md`
- `services/bff-water-planning/CLAUDE.md`
- `services/ros-gis-integration/CLAUDE.md`
- `services/scheduler/src/core/{auth,deps}.py`
- `services/scheduler/src/api/v1/{routes.py,endpoints/control_plans.py}`
- `services/scheduler/migrations/`
- `services/bff-water-planning/src/{main.py,db/database_manager.py}`
- `services/bff-water-planning/src/api/routes/control_plans.py`
- `services/bff-water-planning/migrations/`
- `ops/control-plan-read-runtime/`
- `services/ros-gis-integration/src/services/requirement_source_loader.py`
- `services/ros-gis-integration/{migrations,data/requirement_sources.json}`
- `/Users/subhajlimanond/dev/smart-cms-app/lib/control-plans/`
- `/Users/subhajlimanond/dev/smart-cms-app/lib/water-planning/`
- `/Users/subhajlimanond/dev/smart-cms-app/app/api/smart-water-backend/`
- `/Users/subhajlimanond/dev/smart-cms-app/components/smart-water/`

Runtime state was not re-probed in this planning pass. The last archived runtime evidence reported a capacity failure, but that evidence is historical and may be stale. `RTA-1` begins by measuring the current host again.

## 3. Corrected live-state ledger

### 3.1 Backend source already landed

| Slice | PR | Merged source | Remaining obligation |
|---|---:|---|---|
| RT-1 | #109 | Scheduler/ROS dependency manifests and boot locks | Runtime install and boot acceptance |
| RT-2 | #110 | BFF Strawberry/runtime-compatible pin | Runtime install and full BFF boot acceptance |
| RT-3 | #111 | Canonical PostgreSQL DSN parsing | Runtime DB connection acceptance with reserved characters |
| RT-4 | #112 | Truthful ROS readiness and BFF ROS probe | Sustained dependency-backed readiness |
| OPS-1 | #113 | Reproducible control-plan read runtime tooling | Run on a capacity-qualified host and retain evidence |
| OPS-1 correction | #114 | Explicit bearer audience | Prove current issuer token against deployed services |
| 7.3a | #115 | Dark commissioning trust contracts | Keep noncommandable; verify preflight surfaces |
| Test repair | #116 | SCADA authority-boundary race fix | Included in exact-SHA gates |
| 7.3b | #117 | Dark deployment readiness tooling | Execute preflight/evidence; do not enable authority |

Current backend `main` is clean and equals `origin/main` at `8095bfe3`. There are no RT pull requests waiting to land and no conflict with a pending “PR7” stack. The 7.2 and 7.3 changes are already part of the same linear `main` history.

### 3.2 Frontend source already landed

FE-0 through FE-3 are merged. The control-plan v2 manifest hash is pinned on both sides. The frontend has strict read decoders, authenticated fetch helpers, API proxies, hooks, and view-models for list, detail, prediction coverage, ledger, and lifecycle history. It has no control-plan pages or navigation entry yet; FE-4 remains pending.

### 3.3 Still pending

- Fresh runtime capacity and exact-SHA acceptance.
- A real, non-fixture requirement publication and control-plan draft.
- FE-4 list/detail UI and dark navigation.
- Read activation.
- Versioned schemas/manifest for machine-boundary evidence reads.
- FE-8 evidence UI and Gate Operations deep link.
- W1 Scheduler effective-principal projection.
- W2 immutable planning-depth persistence and authoritative read-back.
- FE-5 mutation policy and distributed backend rate limiting.
- FE-6 fixed write/read-back adapter and draft reconciliation.
- Write activation.
- W4 only if product explicitly chooses canonical-demand recomputation.

## 4. Material corrections to the original roadmap

### 4.1 Deployment is not implementation

RT-1 through OPS-1 are now prerequisites consumed by `RTA-1`, not future implementation PRs. Reopening them would duplicate landed work and risk regression.

### 4.2 Runtime acceptance precedes activation, not frontend coding

FE-4 can be implemented and merged while runtime acceptance proceeds. Only activation depends on capacity and real-data acceptance. This shortens the critical path without exposing an unaccepted capability.

### 4.3 BFF migration ownership must be repaired before W2

`ops/control-plan-read-runtime/apply_bff_migration.py` applies only `009_crop_registry.sql`. A new `010` file would otherwise exist outside deterministic deployment wiring. W2 must replace the one-file behavior with an ordered tracked registry whose checksums and applied state are verified before the planning-depth schema is used.

The root blanket `*.sql` ignore means every new BFF migration pair/manifest must be explicitly allowlisted or force-added and locked by a repository test. An untracked migration is a release blocker.

### 4.4 The canonical section roster is `gis.zone`, not `ros_gis.sections_current`

Current ROS source loading reads section `code`, zone, and `props.Area_Rai` from `gis.zone`, validates exactly sections 03-43 and total 47,385 rai, then activates a versioned local projection. `ros_gis.sections_current` is not a verified live source and must not appear in W2 SQL.

W2 will resolve submitted section IDs by exact equality with `gis.zone.code`; it will derive the Mun Bon zone namespace from the row's `props->>'Zone'` and validate that each submitted section belongs to the claimed zone. It will fail closed if the approved 41-section roster, area total, zone range 1-6, or ID uniqueness drifts.

### 4.5 “Water level” is an unsafe storage name for an operator plan input

The repository already contains observed/manual water-level paths such as `ros_gis.manual_water_level_readings`, `ros_gis.sensor_water_levels`, and `ros_gis.water_level_aggregations`. The new data is neither a sensor observation nor an authoritative measured state.

The durable API and tables will use **planning depth**:

- `POST /api/v1/water-planning/planning-depth-submissions`
- `GET /api/v1/water-planning/planning-depth-submissions/active`
- `water_planning.planning_depth_submissions`
- `water_planning.planning_depth_values`

The frontend's existing local `waterLevelMm` vocabulary may be migrated in FE-6, but the backend boundary must use `planning_depth_mm`. No write may touch observed-water-level tables.

### 4.6 Decimal precision must be preserved

The current UI accepts `0.1` mm increments. W2 must not impose an integer-only contract. Store `planning_depth_mm` as `NUMERIC(12,3)` with `>= 0`, reject non-finite JSON numbers, and canonicalize to three fractional digits for hashing. No arbitrary physical upper bound will be invented; the payload is bounded by the canonical roster and request-size limits.

### 4.7 FE-8 lacks a publication-quality contract

The three machine-boundary reads currently share only example JSON under `contracts/control-plans/v1`. They do not have JSON schemas or a complete-set manifest. FE-8 must not hand-maintain another mirror from examples alone. `ME-1` publishes a separate evidence contract before FE-8.

### 4.8 Distributed rate limiting belongs at the authoritative mutation boundary

The Next.js app has no Redis dependency and is not the authoritative writer. W2's BFF already owns Redis. The distributed limiter will run in the BFF before the database transaction, keyed by normalized subject and operation. FE-5 presents the policy and forwards `429`; it does not create a divergent in-memory or second Redis enforcement implementation.

### 4.9 W4 is not part of the default launch

Persist-and-read-back is the accepted default. Planning depth does not change canonical ROS demand until product provides an explicit equation, temporal allocation rule, precedence rule, and correction policy. This preserves forecast-only truth and prevents a UI input from silently becoming measured state.

## 5. Non-negotiable invariants

1. Control-plan reads remain noncommanding. No FE-4 or FE-8 control can call a mutation or SCADA command route.
2. Scheduler execution, ROS scheduled production, control authority, and planning-depth writes remain disabled through dark deployment.
3. All authenticated read and write responses use `Cache-Control: no-store`.
4. Bearer tokens are forwarded, never logged, persisted, or transformed into service tokens.
5. Scheduler remains the JWT/revocation/effective-role authority.
6. BFF remains the authoritative planning-depth writer and rechecks effective roles server-side.
7. Frontend role checks are UX only; they never replace backend authorization.
8. Planning-depth rows and values are immutable. Correction creates a successor.
9. Idempotent replay never creates a second submission; stale-client writes fail `409`.
10. Database, Redis, Scheduler-principal, roster, and contract drift fail closed.
11. A missing read returns `404`/explicit `no_publication`, never fabricated empty success or zero values.
12. No integration acceptance uses a fixture, mock bearer, synthetic plan, or fabricated source data.
13. Any source PR follows: branch from current `main` -> tests first -> gates -> QCHECK/g-check -> PR -> required checks -> admin merge -> land local `main` with `pull --ff-only`.
14. One backend PR lands at a time; rebase each next branch on the newly landed `origin/main`.
15. Frontend `dev` is not modified or synchronized; work branches from frontend `main`.

## 6. Plan Draft A — parallel dark delivery with separate activation

This draft treats runtime operations, read UI, evidence contracts, and write capability as independent lanes with explicit joins.

```text
merged RT/OPS/7.3 ──> RTA-1 ──> AC-1 ───────────────> READ-ACT-1
                             └──────────────────────> WRITE-ACT-1 capacity gate

frontend FE0-3 ─────> FE-4 (dark) ──────────────────> READ-ACT-1
                         │
machine examples ─────> ME-1 ──> FE-8 (dark) ──────> evidence activation

Scheduler auth ───────> W1 ──> W2 ──> FE-5 ──> FE-6 ──> WRITE-ACT-1
                                      └────────> persist-only default
product recompute decision ─────────────────────> W4 only if selected
```

Advantages:

- Removes already-merged RT work from the implementation queue.
- Lets FE-4 and W1 start without waiting for host capacity.
- Keeps every activation reversible and smaller than its implementation PR.
- Isolates cross-repo failures and preserves one-PR-at-a-time review.
- Allows persist-only planning-depth value delivery without pretending the values affect demand.

Costs:

- More checkpoints and evidence packets.
- Requires disciplined state labels so “merged” is not mistaken for “live.”
- FE-8 waits for a small additional backend contract PR.

## 7. Plan Draft B — bundled vertical release trains

This alternative uses two larger feature trains:

1. Read train: runtime acceptance + AC-1 + ME-1 + FE-4 + FE-8 + one read activation.
2. Write train: W1 + W2 + FE-5 + FE-6 + optional W4 + one write activation.

Advantages:

- Fewer release ceremonies.
- One acceptance packet per user-visible capability.
- Less temporary time where code is merged but dark.

Costs:

- Couples two repositories and multiple services into each rollback unit.
- Delays useful FE-4 source delivery behind machine-evidence work.
- Makes W1/W2 review substantially larger and harder to audit.
- A host-capacity failure blocks all visible progress.
- Encourages premature W4 bundling before its product semantics are settled.
- Conflicts with the established preference for atomic PRs, skeptical review, merge, and local landing one item at a time.

## 8. Comparative synthesis

| Criterion | Draft A | Draft B |
|---|---|---|
| Smallest reversible release | Strong | Weak |
| Parallel progress | Strong | Limited by bundles |
| Cross-repo rollback | Isolated | Coupled |
| Review clarity | High | Lower |
| Time to FE-4 merged dark | Shorter | Longer |
| Operational ceremony | More | Less |
| Product uncertainty around W4 | Contained | Risks contaminating train |
| Fit with normal dev lifecycle | Best | Poorer |

**Decision: use Draft A.** Draft B is retained only as a comparison; it is not the execution plan.

## 9. Unified execution plan

### Stage 0 — freeze the corrected baseline

#### BASE-0 — status and contract ledger

Status: completed by this roadmap.

Purpose: prevent new sessions from reopening landed RT/OPS work or claiming unaccepted runtime as live.

Acceptance:

- Backend SHA and landed PRs are recorded in section 3.
- Frontend SHA and FE-0..3 status are recorded.
- Pending work starts at RTA-1/FE-4/W1, not RT-1.
- The old roadmap remains historical evidence and is not edited.

### Stage 1 — runtime acceptance of landed code

#### RTA-1 — capacity-qualified dark runtime acceptance

Type: operations acceptance; no source PR unless the scripts themselves fail.

Depends on: merged #109-#117.

Blocks: AC-1, READ-ACT-1, WRITE-ACT-1.

Use existing files:

- `ops/control-plan-read-runtime/runtime_gate.py`
- `ops/control-plan-read-runtime/activate.sh`
- `ops/control-plan-read-runtime/verify_bearer.py`
- `ops/control-plan-read-runtime/ecosystem.config.cjs`
- `infra/pm2/`
- `infra/monitoring/`
- `docs/operations/CONTROL_PLANE_DARK_DEPLOYMENT.md`

Run order:

1. Capture timestamp, host identity, deployed git SHA, PM2 process list, restart counts, memory, swap, and listening ports without exposing secrets.
2. Require exact source SHA `8095bfe3` or a later explicitly accepted `origin/main`; record the actual SHA.
3. Re-run the capacity gate. Require at least 512 MiB `MemAvailable`, used swap at most 1 GiB, and no port conflict.
4. If capacity fails, stop. Resize/relocate the runtime or authorize a separately reviewed footprint change. Do not lower the gate inside the acceptance run.
5. Install from the four service manifests in isolated environments. No host-level overlay packages.
6. Verify migration parity: Scheduler through `0013_operator_approved_execution`, ROS through `0003_daily_requirement_producer`, and BFF 009.
7. Validate monitoring configuration with `promtool` and the repository preflight.
8. Start Flow `3011`, Scheduler `3021`, ROS `3047`, and BFF `3022` on loopback using the tracked ecosystem/wrappers.
9. Keep Scheduler execution disabled, authority noncommandable, ROS recurring/startup production disabled, control-plan reads hidden, and planning-depth writes disabled.
10. Require dependency-backed `/ready` success continuously for five minutes with unchanged PM2 restart counts.
11. Run the real bearer verifier: login -> Scheduler/BFF authenticated list -> missing detail -> logout -> token reuse denied. Never paste or persist the bearer.
12. Run `pm2 save` only after the stable window and retain sanitized evidence.

Acceptance evidence:

- Exact SHA and migration IDs.
- Capacity readings before and after startup.
- Four loopback listeners and readiness responses.
- Five-minute stability with restart-count equality.
- Bearer lifecycle verdicts, status codes, and `no-store` headers.
- Monitoring/preflight verdicts.
- Confirmation that every producer/execution/write/visibility flag remains false.

Rollback:

- Stop/delete only the four named PM2 processes created by the tracked ecosystem.
- Restore the prior PM2 saved process set if one existed.
- Do not roll migrations back after durable runtime data exists; forward-fix migration failures.
- Preserve evidence and the failed gate reason.

#### RTA-1 failure branch — CAP-1

CAP-1 is not permission to weaken checks. Select one:

1. **Preferred:** resize or move to a host that meets the existing gate.
2. Split the four processes across approved hosts and revise readiness URLs/configuration in a dedicated OPS PR.
3. Reduce measured footprint only through an evidence-backed OPS PR with identical readiness, bearer, and stability gates.

Any infrastructure spend, host replacement, or external deployment change requires the user's explicit operational authorization.

### Stage 2 — core read UI and real-data acceptance

#### FE-4 — control-plan list/detail UI, merged dark

Repository: `/Users/subhajlimanond/dev/smart-cms-app`.

Depends on: FE-0..3 merged.

Does not depend on: RTA-1 or AC-1 for source implementation.

Activation depends on: RTA-1 + AC-1.

Files to add:

- `app/smart-water/control-plans/page.tsx`
- `app/smart-water/control-plans/page.test.tsx`
- `app/smart-water/control-plans/[planId]/versions/[version]/page.tsx`
- `app/smart-water/control-plans/[planId]/versions/[version]/page.test.tsx`
- `components/smart-water/control-plans/ControlPlanListPage.tsx`
- `components/smart-water/control-plans/ControlPlanListPage.test.tsx`
- `components/smart-water/control-plans/ControlPlanDetailPage.tsx`
- `components/smart-water/control-plans/ControlPlanDetailPage.test.tsx`

Files to modify:

- `components/smart-water/shared/SmartWaterNavigation.tsx`
- add `components/smart-water/shared/SmartWaterNavigation.test.tsx`
- reuse `components/smart-water/control-plans/useControlPlanQueries.ts`
- reuse `lib/control-plans/{api,contract,feature,view-model}.ts`

Implementation outline:

1. Page routes fail closed when `isControlPlanReadEnabled()` is false; render `notFound()` or the established unavailable state, not a partially working page.
2. Navigation adds a control-plan item only when `NEXT_PUBLIC_CONTROL_PLAN_READS === "true"`.
3. `ControlPlanListPage` renders bounded summary fields, lifecycle/approval trust, empty state, loading state, explicit upstream error, and opaque-cursor pagination.
4. List rows link using both branded `planId` and integer version.
5. `ControlPlanDetailPage` renders detail, prediction coverage, ledger, and lifecycle history as separate query states so one failed projection is never shown as zero/empty success.
6. Preserve backend vocabulary exactly: unavailable/infeasible/invalidated/stale and `shadow_active` remain distinct.
7. Label the surface “read-only / no machine authority.” Render no approve, activate, hold, resume, grant, dispatch, or command control.
8. Do not poll by default. Refetch only on explicit user action/window focus according to the existing query conventions.

Test-first cases (5-10 word intent each):

- Flag false hides navigation and page content.
- Flag true exposes control-plan navigation exactly once.
- List renders bounded summaries without hidden optimizer documents.
- Empty list renders truthful no-plan state.
- List error never masquerades as empty success.
- Opaque cursor is forwarded without parsing.
- Detail links preserve plan id and version.
- Detail panels preserve independent loading and errors.
- Infeasible prediction never renders as zero delivery.
- Invalidated plan never appears machine-authorized.
- No mutation or command control is rendered.
- Authenticated requests use existing bearer-aware client only.

Quality gates:

```bash
npm test
npm run build
```

`npm run lint` is only a gate if the repository's current Next version exposes a working lint script; do not substitute a passing no-op. Run Prettier check on changed files with the repository formatter.

PR lifecycle:

1. Branch from frontend `main`, never `dev`.
2. TDD, focused tests, full tests/build, QCHECK, formal g-check.
3. Conventional commit and PR with screenshots for flag-on local rendering.
4. Required checks pass; admin merge.
5. Land local frontend `main` with `git pull --ff-only`.
6. Deploy with `NEXT_PUBLIC_CONTROL_PLAN_READS=false`.

Rollback: keep flag false; if the dark bundle causes unrelated regressions, redeploy the prior frontend artifact.

#### AC-1 — real plan production and bearer read acceptance

Type: runtime acceptance, not a fixture-producing code PR.

Depends on: RTA-1.

Blocks: READ-ACT-1 and evidence activation.

Preconditions:

- Real approved GIS/planting/agronomic sources are present.
- ROS manual producer lifecycle is enabled only for the bounded invocation; recurring and startup catch-up remain false.
- Scheduler database has migrations through 0013.
- A genuine current central-auth operator bearer is available through normal login.

Procedure:

1. Invoke `POST /api/v1/water-requirements/runs` through the real ROS path.
2. If inputs are incomplete, retain the `409 failed_incomplete_source` evidence and fix the real source. Do not insert a fixture or substitute zeros.
3. Read the published run and capture run ID, content hash, dataset-version lineage, horizon, and non-empty section count.
4. Create one Scheduler draft through `POST /api/v1/control-plans/drafts` using the real requirement run and runtime-proven model/Flow path.
5. Require a persisted non-empty plan; if optimizer/prediction returns an explicit infeasible/unavailable state, treat it truthfully and correct the real prerequisite rather than fabricating a feasible plan.
6. Through the BFF with the real bearer, prove list, detail, prediction coverage, ledger, lifecycle history, intent timeline, readback observations, and execution state.
7. Verify unknown plan/version returns `404`; malformed upstream projection is fail-closed in test, not injected into production.
8. Verify all responses are `no-store` and contain no command authority claim.
9. Logout and prove bearer reuse is denied.

Acceptance:

- One real published requirement run with immutable lineage.
- One real persisted, non-empty control-plan version.
- All eight read projections return their truthful stored state.
- List includes the plan; detail identity/version matches.
- No fixture, mock bearer, or manual DB insertion was used.
- Sanitized IDs/hashes/statuses are retained in the evidence packet.

Rollback: no destructive deletion. Keep the plan in its truthful draft/shadow state and keep UI visibility false.

#### READ-ACT-1 — reversible core-read activation

Type: configuration release.

Depends on: FE-4 deployed dark + RTA-1 accepted + AC-1 accepted.

Steps:

1. Record current frontend artifact SHA and configuration.
2. Enable `NEXT_PUBLIC_CONTROL_PLAN_READS=true` in staging and rebuild/redeploy because this is a public build-time flag.
3. Run authenticated smoke tests for navigation, list, detail, refresh, deep link, `404`, and signed-out behavior.
4. Observe errors, latency, Scheduler/BFF readiness, and restart counts for the agreed staging window.
5. Promote the same artifact/config change to production.
6. Repeat smoke tests and record activation time/operator.

Backout: rebuild/redeploy with the flag false. Backend reads may remain deployed because they are bearer-protected and noncommanding.

### Stage 3 — machine-evidence contract and FE-8

#### ME-1 — publish versioned machine-evidence schemas

Repository: backend.

Depends on: existing Scheduler/BFF machine-boundary reads.

Blocks: FE-8.

Files to add:

- `contracts/control-plan-evidence/v1/manifest.json`
- `contracts/control-plan-evidence/v1/intent-timeline.schema.json`
- `contracts/control-plan-evidence/v1/intent-timeline.example.json`
- `contracts/control-plan-evidence/v1/readback-observations.schema.json`
- `contracts/control-plan-evidence/v1/readback-observations.example.json`
- `contracts/control-plan-evidence/v1/execution-state.schema.json`
- `contracts/control-plan-evidence/v1/execution-state.example.json`
- invalid fixtures for missing, extra, and scalar-drift cases

Files to modify:

- `services/scheduler/tests/unit/test_control_plan_machine_boundary_contract.py`
- `services/bff-water-planning/tests/unit/test_control_plan_machine_boundary_contract.py`
- service `CLAUDE.md` contract notes if file names/version change

Contract decisions:

- Use a separate `control-plan-evidence/v1` family; do not mutate the pinned five-file control-plan v2 set.
- Manifest pins every required file and complete-set SHA-256 values.
- Schemas use `additionalProperties: false`, strict integer/boolean/date-time types, bounded arrays, and exact enums already enforced by runtime models.
- Existing response bodies do not change in ME-1. This is publication and drift locking only.
- Both Scheduler and BFF validate all examples, invalid fixtures, manifest completeness, and hashes.

Tests first:

- Manifest rejects a missing evidence projection file.
- Manifest rejects an unlisted extra contract file.
- Scheduler examples validate against all three schemas.
- BFF examples validate against all three schemas.
- Extra fields fail both service contract suites.
- Numeric timestamp drift fails strict date-time schema.
- Enum drift fails before frontend pinning.

Gates: Scheduler bare pytest, BFF bare pytest, JSON parse/hash verification, QCHECK, g-check, PR/admin merge/local landing.

#### FE-8 — read-only shadow evidence and Gate Operations link

Repository: frontend.

Depends on: ME-1 merged and pinned; FE-4 merged.

Activation depends on: AC-1 evidence for a real plan.

Files to add/modify:

- add `contracts/control-plan-evidence/v1/` pinned copy in the frontend contract location
- add `lib/control-plan-evidence/contract.ts` and tests
- extend `lib/control-plans/api.ts`, `server.ts`, and tests for the three allowlisted reads
- extend `components/smart-water/control-plans/useControlPlanQueries.ts` and tests
- add `components/smart-water/control-plans/ControlPlanEvidenceSummary.tsx` and tests
- render the summary from the FE-4 detail page
- add a validated `NEXT_PUBLIC_GATE_OPERATIONS_URL` configuration helper and tests

Implementation outline:

1. Strictly decode timeline, observations, and execution state against the pinned contract.
2. Render counts/status/timestamps and explicit absent/unavailable states; never infer successful execution from an empty array.
3. Label evidence as read-only stored truth and show hold/resume history without offering mutation controls.
4. Build Gate Operations links as `<validated-base>/gates/<encoded-gate-id>` to the existing SCADA web route.
5. Reject base URLs with credentials, query, fragment, or non-HTTP(S) schemes. Open cross-origin links with `noopener noreferrer`.
6. Hide/disable the link when no exact gate ID exists. Never use nearest-match mapping.

Tests first:

- Contract pin rejects any changed evidence file hash.
- Timeline renders claimed through validated transitions truthfully.
- Empty observations state does not claim successful readback.
- Held execution state renders hold reason and history.
- Malformed evidence fails closed per projection.
- Gate link uses exact encoded gate identifier.
- Invalid Gate Operations base hides the deep link.
- Evidence component renders no mutation controls.

Deploy dark behind the core read flag or a narrower `NEXT_PUBLIC_CONTROL_PLAN_EVIDENCE_READS=false` flag. Prefer the narrower flag if evidence may activate later than FE-4. Activation requires a real AC-1 plan with truthful evidence rows; otherwise keep the summary dark.

### Stage 4 — planning-depth write foundation

#### W1 — Scheduler effective-principal endpoint

Repository: backend Scheduler.

Depends on: existing strict JWT/revocation/role hierarchy.

Blocks: W2 and FE-5 canonical effective-role checks.

Files to add:

- `services/scheduler/src/api/v1/endpoints/auth.py`
- `services/scheduler/src/schemas/auth.py`
- `services/scheduler/tests/api/test_auth_principal.py`

Files to modify:

- `services/scheduler/src/api/v1/routes.py`
- `services/scheduler/tests/unit/test_auth.py` or `test_deps_auth.py` only for new pure projection coverage

API contract:

```json
GET /api/v1/auth/principal
{
  "subject": "non-empty stable subject",
  "effective_roles": ["field_team", "operator"]
}
```

Decisions:

- Dependency is `require_field_team`; every recognized Scheduler role implies it.
- Invalid/expired/revoked token -> `401`.
- Missing/unavailable revocation Redis -> `503`.
- Valid token with no recognized Scheduler privilege -> `403`.
- Response roles are deduplicated, sorted, and limited to `admin|supervisor|operator|field_team`; issuer aliases are not returned.
- Response contains no raw token, jti, issuer, email, or token hash.
- Response always sets `Cache-Control: no-store`.
- Reuse `get_current_user`, `require_field_team`, `expand_effective_roles`, and `principal_from_user`; do not decode JWT again.

Functions:

- route handler `get_effective_principal(current_user)` composes existing helpers.
- Pydantic `EffectivePrincipalProjection` strictly validates the two response fields.

Tests first:

- Operator token returns sorted inherited effective roles.
- RID admin alias returns canonical effective roles only.
- Unknown role receives forbidden without role leakage.
- Revoked token receives unauthorized response.
- Redis outage receives service unavailable response.
- Principal response excludes sensitive token identity fields.
- Principal response always disables caching.

Gate: Scheduler bare pytest, formatter/linter if configured, QCHECK, formal g-check, PR/admin merge/local landing.

#### W2 — immutable planning-depth submission and authoritative read-back

Repository: backend BFF.

Depends on: W1 landed; canonical `gis.zone` roster reachable; BFF Redis reachable.

Blocks: FE-6 and WRITE-ACT-1.

##### W2.1 Contract

`POST /api/v1/water-planning/planning-depth-submissions`

Request:

```json
{
  "schema_version": 1,
  "client_submission_id": "uuid",
  "project_key": "mun-bon",
  "week_key": "2026-W30",
  "week_date": "2026-07-20",
  "expected_active_submission_id": null,
  "levels": [
    {
      "area_type": "zone",
      "area_id": "01-01",
      "planning_depth_mm": 45.0
    },
    {
      "area_type": "section",
      "area_id": "01-01-01-03",
      "zone_id": "01-01",
      "planning_depth_mm": 20.5
    }
  ]
}
```

New submission -> `201`; exact idempotent replay -> `200`:

```json
{
  "schema_version": 1,
  "submission_id": "uuid",
  "client_submission_id": "uuid",
  "project_key": "mun-bon",
  "week_key": "2026-W30",
  "week_date": "2026-07-20",
  "submitted_at": "ISO-8601 instant",
  "submitted_by": "subject",
  "supersedes_submission_id": null,
  "request_sha256": "64 lowercase hex",
  "replayed": false
}
```

`GET /api/v1/water-planning/planning-depth-submissions/active?project_key=mun-bon&week_key=2026-W30`

- `200` returns metadata plus the expanded authoritative per-section values and their source kind.
- `404` means no active submission for that project/week.
- `levels` are sorted by canonical section ID.
- Each value contains `section_id`, `zone_id`, `planning_depth_mm`, `source_kind=zone_default|section_override`, and `source_area_id`.
- Both POST and active GET require a W1 principal with effective `operator`; field-team-only callers receive `403`.

Error taxonomy:

- malformed JSON/Pydantic structure -> `422`.
- RID week/date mismatch, duplicate area ID, unknown area, wrong section-zone membership, missing zone coverage, or invalid decimal -> `422` with a safe code.
- missing/invalid/revoked bearer -> `401`.
- recognized principal without effective `operator` -> `403`.
- Scheduler principal, Redis, DB, or canonical roster unavailable -> `503`.
- Scheduler response schema drift -> `502`.
- stale `expected_active_submission_id`, conflicting client ID, or concurrent successor -> `409`.
- rate limit exceeded -> `429` plus `Retry-After`.

All responses are `no-store`. No automatic retry is performed after the database transaction begins.

##### W2.2 Migration and storage

Add:

- `services/bff-water-planning/migrations/010_planning_depth_submissions.sql`
- `services/bff-water-planning/migrations/manifest.json`
- explicit `.gitignore` negation for owned migration SQL/manifest
- a migration registry/runner module reusable by ops and tests

Modify:

- `ops/control-plan-read-runtime/apply_bff_migration.py` to apply the ordered manifest, not one filename
- runtime README/preflight tests to require 009 and 010 after W2 deployment

`water_planning.planning_depth_submissions`:

- UUID `submission_id` primary key.
- UUID `client_submission_id` unique.
- project/week/date, subject, canonical request text, SHA-256, submitted timestamp.
- nullable `supersedes_submission_id` self-FK.
- unique non-null `supersedes_submission_id` so one predecessor cannot fork.
- checks for schema version, week-key form, non-empty subject, hash form, and predecessor not self.

Idempotency is owned by `client_submission_id`, not by a globally unique content hash. An exact same-client-ID, same-subject, same-body retry returns the original active submission with `200`; reuse with a different subject/body, or retry after that submission has been superseded, returns `409`. A new client ID whose content already equals the current active submission returns that current row with `200` and creates no successor. Historical content may be submitted again later with a new client ID, so a deliberate revert is not blocked by a hash uniqueness constraint.

`water_planning.planning_depth_values`:

- `(submission_id, section_id)` primary key.
- canonical `zone_id`, `NUMERIC(12,3) planning_depth_mm >= 0`.
- `source_kind` check and exact `source_area_id`.
- immutable update/delete trigger shared by both tables.

Current active row is derived as a submission with no successor. Do not store a mutable `is_active` flag. Serialize writes with a PostgreSQL transaction advisory lock derived from `(project_key, week_key)` and re-read current active inside the lock.

Migration runner requirements:

- ordered manifest with file SHA-256 values.
- `water_planning.schema_migrations` applied registry.
- one transaction per migration.
- checksum drift refusal.
- idempotent status/apply behavior.
- no rollback after a planning-depth row exists; forward-fix instead.
- repository test proves all manifest SQL files are tracked by Git.

##### W2.3 Roster expansion and identity

The repository query reads:

- `gis.zone.code`
- `props->>'Zone'`
- `props->>'Area_Rai'`

It validates the same approved roster invariants as ROS: 41 unique sections, suffix numbers 03-43, six zones, positive areas, and total 47,385 rai. For project `mun-bon`, zone number `n` maps to the existing FE namespace `01-{n:02d}`. A submitted section must exactly equal a returned `gis.zone.code` and must belong to the submitted/derived zone.

Expansion rules:

1. Require one zone default for every zone represented by the canonical roster.
2. Allow at most one override per canonical section.
3. Each canonical section receives its section override if present; otherwise its zone default.
4. Reject explicit entries outside the roster; never silently drop them.
5. Hash normalized explicit input and normalized expanded output as canonical UTF-8 JSON with sorted keys/items and decimals rendered to three places.
6. Store expanded values atomically with the submission.

This contract deliberately stores both explicit intent and expanded authoritative read-back.

##### W2.4 Code organization

Files to add:

- `src/schemas/planning_depth.py`
- `src/clients/scheduler_principal_client.py` or a narrowly added method in the existing Scheduler client
- `src/services/planning_depth_submission.py`
- `src/db/planning_depth_repository.py`
- `src/api/routes/planning_depths.py`
- focused unit and disposable-Postgres integration tests

Files to modify:

- `src/main.py` to register the router
- `src/config/settings.py` and `.env.example` for Scheduler principal URL and limiter settings
- `src/db/database_manager.py` only to expose the existing pool/Redis through established accessors
- `ops/control-plan-read-runtime/` migration/preflight wiring

Functions:

- `canonicalize_planning_depth_request(request)` — pure canonical text/hash.
- `validate_planning_depth_roster(levels, roster)` — pure exact identity checks.
- `expand_planning_depth_values(levels, roster)` — pure deterministic expansion.
- `load_effective_principal(bearer)` — W1 client, strict response, fail-closed taxonomy.
- `consume_planning_depth_write_limit(subject)` — atomic Redis Lua/fixed-window decision.
- `create_planning_depth_submission(conn, request, principal, roster)` — transaction/advisory lock/replay/successor.
- `get_active_planning_depth_submission(conn, project_key, week_key)` — authoritative projection.

Do not add a class for the pure canonicalize/validate/expand functions.

##### W2.5 Rate limit

Authoritative BFF policy:

- operation: `planning_depth.submit`.
- effective roles: `operator`, `supervisor`, or `admin`.
- default: 10 accepted attempts per subject per 300-second window.
- both values are explicit environment settings and documented.
- Redis key contains a SHA-256 subject digest, never raw subject or bearer.
- atomic Redis script sets expiry on first increment and returns remaining TTL.
- Redis failure -> `503`, never allow-through.
- structurally invalid requests are rejected before consuming the limiter; authorized semantically valid write attempts consume it whether they become 201, replay 200, or conflict 409.

##### W2.6 Tests first

Pure unit tests:

- Decimal canonicalization produces stable three-place request hash.
- Input order does not change canonical request hash.
- Missing zone default rejects incomplete roster coverage.
- Unknown section rejects before any database write.
- Wrong section-zone membership rejects exact submitted identity.
- Section override wins over its zone default.
- Expansion produces exactly forty-one sorted section values.
- Observed water-level vocabulary never appears in storage SQL.

Client/route tests:

- Bearer is forwarded unchanged only to Scheduler principal.
- Missing bearer returns unauthorized without Scheduler call.
- Effective field-team-only principal returns forbidden.
- Scheduler revocation outage returns service unavailable.
- Scheduler schema drift returns bad gateway.
- Redis limiter returns retry-after and no DB call.
- POST returns created for a first submission.
- Exact client replay returns same submission with 200.
- Reused client id with changed body returns conflict.
- Stale expected active id returns conflict.
- Active GET returns authoritative expanded values.
- Missing active submission returns not found.
- Every route response disables caching.

Disposable PostgreSQL tests:

- Apply 009 then 010 from empty registry.
- Reapply is idempotent and records checksums.
- Modified applied SQL checksum fails closed.
- Concurrent successors yield one commit and one conflict.
- Update/delete triggers preserve both immutable tables.
- Derived active query follows a linear successor chain.
- Database rejects one predecessor with two successors.
- Transaction failure leaves no submission or values.
- Git tracking test includes migration 010 and manifest.

Gates:

```bash
cd services/bff-water-planning
pytest
```

Also run the env-gated disposable PostgreSQL migration/apply/reapply tests with an explicitly disposable loopback database. Then QCHECK, formal g-check, PR/admin merge/local landing. Deploy W2 with its write flag false and migration applied through the manifest.

### Stage 5 — frontend write policy, fixed adapter, and reconciliation

#### FE-5 — explicit mutation policy and backend-limiter integration

Repository: frontend plus W2 contract documentation; no second rate-limit authority.

Depends on: W1/W2 contracts stable.

Blocks: FE-6.

Files to add/modify:

- add `lib/auth/mutation-policy.ts` and tests
- add a bearer-forwarded frontend principal proxy if the UI needs canonical effective roles
- update `app/smart-water/auth-context.tsx` only to expose canonical effective roles separately from raw issuer roles
- document/handle W2 `429` and `Retry-After` in the submission client
- audit every Smart Water mutation route into the policy table

Policy matrix:

| Action | Minimum effective role | Authoritative enforcement |
|---|---|---|
| Control-plan reads | operator | Scheduler existing route |
| Submit/correct planning depth | operator | BFF W2 after W1 principal |
| Review/approve/activate/hold/resume | supervisor plus existing confirmation/step-up rules | Scheduler existing routes |
| Authority grant/renew/revoke | supervisor plus existing rules | Scheduler existing routes |
| Gate command | no Smart CMS control in this roadmap | SCADA/Scheduler authority boundary |

The frontend may hide controls based on effective roles but must still send the bearer to W2. It never trusts locally decoded raw roles as final authorization and never implements an in-memory limiter.

Tests first:

- Raw issuer alias is not treated as effective role.
- Canonical operator role exposes planning-depth submit UX.
- Field-team-only principal keeps submit UX unavailable.
- Principal outage hides writes and preserves reads.
- Retry-after is preserved in the user error model.
- Mutation inventory contains every Smart Water POST route.

#### FE-6 — W2 submission/read-back and cross-browser draft reconciliation

Repository: frontend.

Depends on: W2 deployed dark; FE-5.

Blocks: WRITE-ACT-1.

Files to replace/modify:

- `lib/water-planning/water-level-submission.ts` -> migrate boundary vocabulary to planning depth
- add/rename tests alongside it
- `app/api/smart-water-backend/water-planning/submissions/route.ts`
- its route tests
- `components/smart-water/dashboard/water-planning/useSubmitPlanningMutation.ts`
- `WaterPlanningProvider.tsx` and focused tests
- add an active-submission GET proxy/hook
- feature/environment configuration

Implementation decisions:

1. Replace configurable `WATER_PLANNING_SUBMIT_PATH` with the fixed W2 path. Keep only a validated BFF origin setting.
2. Forward the incoming bearer exactly as the existing control-plan proxy does.
3. Translate camelCase UI state explicitly to the snake_case W2 request; never pass a loosely typed object through.
4. Generate `clientSubmissionId` once per user submit attempt and retain it for manual retry of that same attempt.
5. Send `expectedActiveSubmissionId` from the last authoritative GET; a `409` forces refresh/reconciliation, not overwrite.
6. Accept 201 as new and 200 as replay. Require strict acknowledgement identity/timestamp/hash fields.
7. Fetch active read-back after success and reconcile local draft against expanded authoritative section values.
8. Keep unsaved local edits when the server has not changed. If both local and server changed from the last common state, present an explicit conflict; never silently merge or overwrite.
9. Persist only non-sensitive draft state in the established browser storage. Never persist bearer, subject, or server authorization response.
10. Do not auto-retry POST. Network ambiguity offers a manual retry using the same client ID.
11. Rename user-facing copy to “planned water depth”/the approved Thai wording; never call it sensor-measured level.

Tests first:

- Builder preserves decimal planning depth without rounding loss.
- Adapter emits fixed snake-case W2 contract only.
- Submission proxy forwards bearer and no refresh cookie.
- Proxy cannot redirect the write to another origin.
- Created acknowledgement updates active submission identity.
- Replay acknowledgement does not create duplicate local history.
- Network ambiguity reuses client id only on manual retry.
- Stale active conflict refreshes without overwriting draft.
- Clean local draft adopts authoritative read-back.
- Diverged local and remote states show explicit conflict.
- Reloaded tab reconciles using server as authority.
- Separate browser sees the same active submission.
- Disabled flag performs no POST or GET mutation work.
- Field-team-only user cannot invoke submit control.

Gates: full frontend test suite, build, changed-file formatting, QCHECK, g-check, PR/admin merge/local landing. Deploy with `NEXT_PUBLIC_WATER_PLANNING_SUBMIT_ENABLED=false`.

### Stage 6 — recomputation decision

#### DEC-W4 — product decision, default persist-only

Default decision: **persist and read back only**. W2 data is a planning annotation and does not affect `ros_gis.water_requirement_runs` or Scheduler drafts.

W4 may be planned and implemented only if the user/product owner explicitly selects recomputation and supplies all of:

- whether depth represents standing water, delivered water, or another planning quantity.
- equation and units.
- whether a weekly value is subtracted once, spread daily, or applied by another temporal rule.
- precedence between zone default and section override (W2 currently defines storage precedence only).
- valid effective date/week behavior and late-correction policy.
- whether a correction supersedes already-published requirements and existing control plans.
- audit wording and operator authority required.

If selected, W4 uses a new ROS migration `0004_planning_depth_input_lineage`, reads only immutable active W2 submissions, snapshots submission ID/hash and per-section applied values into ROS-owned immutable lineage, includes that snapshot in the requirement run content hash, and publishes a new run/version. It must never mutate an existing requirement or relabel planning depth as observed state.

Required W4 tests would cover the approved equation, temporal allocation, zero floor, decimal precision, correction supersession, missing-week behavior, input-hash change, and immutable lineage. Until DEC-W4 changes, none of this code is created.

### Stage 7 — write activation

#### WRITE-ACT-1 — staging then production planning-depth activation

Type: operations/configuration release; renamed from FE-7 because both backend and frontend gates change.

Depends on: RTA-1, W1, W2, FE-5, FE-6; DEC-W4 remains persist-only unless explicitly changed.

Staging procedure:

1. Verify exact backend/frontend SHAs and BFF migration 010 checksum.
2. Confirm Scheduler principal strict JWT/revocation behavior with real operator, field-team, revoked, and outage cases.
3. Enable the backend W2 write flag while the frontend submit flag remains false.
4. Exercise POST/GET with an authorized staging operator, exact replay, stale conflict, unauthorized role, Redis failure simulation, and DB rollback simulation.
5. Confirm no observed-water-level or ROS requirement table changed.
6. Enable the frontend submit flag in staging and test two browsers: first submit, read-back, correction, stale conflict, logout, and reload.
7. Observe error rate, `429`, `409`, latency, Redis, DB connections, readiness, and restart counts for the staging window.

Production procedure:

1. Take a migration backup/restore checkpoint according to OPS-1 policy.
2. Apply the manifest and prove 009/010 checksum parity before starting W2-capable code.
3. Deploy backend dark; repeat auth/read-only smoke tests.
4. Enable backend writes, then rebuild/deploy frontend with its flag true.
5. Perform one bounded authorized production submission for the current planning week and verify authoritative read-back from a second browser.
6. Confirm persist-only truth: no canonical ROS demand recomputation occurred.
7. Record operator, timestamps, IDs/hashes, metrics, and rollback decision point without tokens or PII.

Backout:

1. Disable frontend submit visibility first.
2. Disable backend write acceptance; keep authenticated GET read-back available.
3. Do not delete immutable submissions or roll back 010 after data exists.
4. Redeploy prior frontend if necessary; backend can remain dark/read-only.
5. Forward-fix schema/code and retain the audit trail.

## 10. Cross-language contract verification

| Boundary | Producer | Consumer | Lock |
|---|---|---|---|
| Control-plan v2 core reads | Scheduler | BFF + frontend | Existing manifest/hash/schema suites |
| Machine evidence v1 | Scheduler | BFF + frontend FE-8 | ME-1 manifest and all three language/runtime decoders |
| Effective principal | Scheduler W1 | BFF W2 + frontend policy proxy | Strict Pydantic + TS decoder fixtures |
| Planning-depth POST/GET | BFF W2 | frontend FE-6 | Canonical JSON examples, invalid fixtures, decimal/hash vectors |
| Canonical roster | `gis.zone` | ROS producer + BFF W2 | Same 41-section/47,385-rai/03-43 invariant tests |
| Planning-depth lineage if W4 | BFF immutable rows | ROS producer | Submission ID/hash/value snapshot contract |

For W1/W2, commit shared valid/invalid JSON fixtures in the backend contract tree and pin them into frontend tests. Cross-language golden vectors must include decimals `0`, `0.1`, `20.5`, and the maximum payload of 41 expanded sections so Python `Decimal` and JavaScript number canonicalization produce the same request hash.

## 11. Wiring verification table

| Capability | Declared in | Registered/called from | Runtime proof |
|---|---|---|---|
| Scheduler principal | `endpoints/auth.py` | `api/v1/routes.py` under `/auth` | real bearer 200/401/403/503 matrix |
| Planning-depth router | `routes/planning_depths.py` | BFF `main.py` | OpenAPI + POST/GET smoke |
| W2 principal client | BFF client | POST dependency path | bearer forwarded; revocation denial |
| BFF migration registry | migration module/manifest | ops apply script + preflight | empty apply, status, reapply, drift refusal |
| Canonical roster | BFF repository | W2 validation/expansion | exact 41 rows and total area |
| Distributed limiter | BFF service/Redis | before W2 DB transaction | 429/Retry-After and Redis-outage 503 |
| FE-4 pages | Next app routes | flag-gated navigation | authenticated local/staging navigation |
| Core read proxy | existing Next route | FE-4 hooks | all five strict projections |
| Evidence proxy | allowlisted Next route | FE-8 hooks | all three strict projections |
| Planning-depth proxy | fixed Next route | FE-6 mutation | bearer POST, no redirect, strict ack |
| Active read-back | Next GET route | FE-6 reconciliation | two-browser authoritative equality |
| Gate Operations deep link | FE-8 component | validated env base | exact encoded gate route |
| Activation flags | deploy configuration | frontend/backend startup | dark default and explicit rollback |

## 12. Per-PR quality and landing checklist

For every implementation PR:

1. Confirm current `main == origin/main` and clean intended worktree.
2. Create one conventional branch from current main.
3. Scaffold only the minimum seam needed for the first failing test.
4. Write the agreed tests first and capture the relevant failing result.
5. Implement without changing unrelated behavior.
6. Run focused tests, service full suite, formatting, lint/type checks available to that service, and integration gates.
7. Verify route/router/runtime wiring and cross-language fixtures.
8. Run QCHECK against functions, tests, implementation practices, security, failure modes, and rollout.
9. Run formal g-check and append its severity-ordered report to the active coding log.
10. Resolve every correctness/security finding; document accepted non-blocking debt.
11. Scan the intended diff for secrets and production identifiers.
12. Commit conventionally, push branch, create PR with behavior, affected services, tests, migrations/flags/rollback.
13. Wait for required GitHub checks and review findings.
14. Admin merge; never push directly to main.
15. Switch local main and `git pull --ff-only`.
16. Verify local/main/origin SHAs and append landing evidence before starting the next dependent PR.

## 13. Optimal PR/order queue

Source work and runtime work may run in parallel, but merges remain one at a time per repository.

1. RTA-1 operational acceptance of already-landed backend.
2. FE-4 frontend PR, merged and deployed dark.
3. AC-1 real-data acceptance once RTA-1 passes.
4. READ-ACT-1 activation.
5. ME-1 backend contract PR.
6. FE-8 frontend PR, dark then evidence activation.
7. W1 backend Scheduler PR.
8. W2 backend BFF/schema/ops PR.
9. FE-5 frontend policy PR; if very small it may be the first commit in FE-6, but review/landing remains independently identifiable.
10. FE-6 frontend adapter/reconciliation PR.
11. WRITE-ACT-1 staging and production activation.
12. W4 only after an explicit decision replacing the persist-only default.

If only one engineer/session is available, the best next action is RTA-1 because it exposes the highest-risk external blocker. If production access/capacity authorization is unavailable, implement FE-4 next because it is independent, already contract-pinned, and can land safely dark. W1 is the next backend coding slice after FE-4 or while runtime access is being arranged.

## 14. Decision-completeness checklist

- [x] Already-landed RT/OPS/7.3 work removed from future implementation queue.
- [x] Landed/deployed/accepted/activated states separated.
- [x] Runtime current-state uncertainty handled by a fresh audit, not an assumption.
- [x] FE-4 coding decoupled from AC-1 while activation remains gated.
- [x] Current migration numbers corrected: Scheduler 0013, ROS 0003, BFF 010 available.
- [x] BFF one-file migration deployment defect included in W2.
- [x] Canonical roster corrected to `gis.zone` and exact invariants specified.
- [x] Planned inputs separated structurally from observed water levels.
- [x] Decimal 0.1 mm UI precision preserved.
- [x] W1 response and error semantics fixed.
- [x] W2 request, response, replay, concurrency, read-back, and error semantics fixed.
- [x] Distributed limiter placed at the authoritative BFF boundary.
- [x] Frontend role checks explicitly non-authoritative.
- [x] Cross-browser conflict behavior fixed; no silent overwrite.
- [x] Machine-evidence schema/manifest gap closed before FE-8.
- [x] Gate Operations link uses exact ID and validated base URL.
- [x] Persist-only is the default; W4 cannot slip into scope implicitly.
- [x] Dark rollout, activation, and backout paths defined.
- [x] TDD, QCHECK, formal g-check, PR/admin merge, and local landing lifecycle defined.

## 15. Immediate next-session handoff

Start by reading this file and verifying `.codex/coding-log.current` points to it. Then:

1. Refresh backend/frontend `main` and GitHub PR state.
2. If runtime access is available, execute RTA-1 and append the sanitized evidence here.
3. If runtime access is not available, create the FE-4 frontend branch from `main`; do not touch `dev`.
4. Follow the FE-4 tests and files exactly, run QCHECK/g-check, open the PR, admin merge, and land frontend main.
5. Return to AC-1 when runtime capacity and credentials are available.

Do not restart at RT-1, do not reopen merged PRs, and do not claim the read or write capability is live until its activation gate is recorded.

## 16. BASE-0 verification and RTA-1 acceptance attempt (2026-07-22)

### BASE-0 verification

- Backend tracked source is clean and `main == origin/main == 8095bfe37550200da00ecb554edc646febf8aff9`; merged PRs #109 through #117 remain in the accepted source ledger.
- Frontend tracked source is clean and `main == origin/main == 7f8c8bde5b1d47212d5b42aea71d24e58540c9cd`; FE-0 through FE-3 remain merged and FE-4 remains pending.
- Pending work still begins at RTA-1, FE-4, and W1. No RT/OPS slice was reopened.
- The archived superseded roadmap was read as evidence only and was not edited.

### RTA-1 sanitized baseline

- Capture time: `2026-07-22T05:50:19+00:00` (`2026-07-22T12:50:19+07:00`).
- Authorized host: `ip-172-31-1-209`; machine identity is retained only as SHA-256 `8b28fef32a80c3e2c4893f941c67ff613a0f53171d38087f6400bbaa43c83a77`.
- The stale `AWS-Lab01` alias timed out; the previously verified direct host path was used without changing SSH or infrastructure configuration.
- Host memory: `MemTotal=3926016 kB`, `MemAvailable=428556 kB` (about 419 MiB).
- Host swap: `SwapTotal=4194300 kB`, `SwapFree=3300568 kB`, used swap `893732 kB` (about 873 MiB).
- Exact `8095bfe3` `runtime_gate.py capacity` verdict: `FAIL capacity: mem_available_below_512_mib` with exit code 1.
- Expected ports are loopback listeners owned by the old runtime: Flow 3011, Scheduler 3021, ROS 3047, and BFF 3022. Central auth is also loopback on 3005.
- The four named PM2 processes were online with restart count 0 at capture. Their RSS readings were Flow 20,881,408 bytes, Scheduler 34,152,448 bytes, ROS 25,784,320 bytes, and BFF 29,913,088 bytes.
- The deployed runtime remains the historical `3885ee63` tree at `/home/ubuntu/runtime/control-plan-read-3885ee63`, not accepted source `8095bfe3`. No exact-SHA deployment checkout exists at the checked canonical paths.
- `promtool` is not installed on the host; monitoring validation was not reached because the capacity gate failed first.

### CAP-1 result and mutation boundary

- RTA-1 is **not accepted**. CAP-1 is active because available memory is below the mandatory 512 MiB floor.
- Execution stopped at run-order step 4. No service environment was installed, no migration was applied or rolled back, no PM2 process was started/stopped/deleted/reloaded, no readiness or bearer acceptance was claimed, and `pm2 save` was not run.
- No capacity threshold was weakened. The next authorized action must be host resize/relocation, an approved split-host OPS change, or an evidence-backed footprint OPS change before RTA-1 is rerun from step 1.

## 17. Authorized non-acceptance runtime experiment (2026-07-22)

- The user explicitly authorized a separate same-host experiment after CAP-1 while keeping the official 512 MiB memory and 1 GiB used-swap RTA-1 gates unchanged. This experiment cannot satisfy RTA-1 while either gate fails.
- Exact source `8095bfe37550200da00ecb554edc646febf8aff9` was cloned into `/home/ubuntu/runtime/munbon2-backend-8095bfe37550200da00ecb554edc646febf8aff9`; the tracked tree remained clean.
- Four service-specific environment files were derived from the existing operator-owned settings without printing their values. They remain mode 600 under `/home/ubuntu/.config/munbon/control-plan-read-runtime-8095bfe37550200da00ecb554edc646febf8aff9`.
- The prior PM2 saved-state file was copied to a mode-600 rollback backup. Its retained checksum is `c91a208066305551bf358ab29c9b5e1298e9da3e489f57b6fc9785125e94156e`.
- Flow's isolated Python 3.11 environment installed successfully from its tracked manifest and passed `pip check`. Provisioning then observed `MemAvailable=215796 kB` and used swap `2010292 kB`, so the experimental safety guard stopped before installing Scheduler, ROS, or BFF.
- After the installer exited, memory recovered to `MemAvailable=550184 kB`, but used swap remained `1232716 kB` (about 1.18 GiB). The exact gate still failed with `swap_used_above_1024_mib`.
- No migration ran. The four original PM2 processes retained their previous PIDs, zero restart counts, and `/home/ubuntu/runtime/control-plan-read-3885ee63` cwd. No process was started, stopped, deleted, or reloaded, and `pm2 save` was not run.
- The partial exact-SHA checkout, mode-600 environment files, Flow virtual environment, secure install log, and rollback backup were retained without destructive cleanup. RTA-1 remains **not accepted**.
