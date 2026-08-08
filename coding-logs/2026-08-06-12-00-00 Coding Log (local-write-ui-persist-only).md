# Local write UI and persist-only acceptance stages

- Created: 2026-08-06 12:00:00 +0700
- Backend baseline: `23aca5ed` (main)
- Scope: PR 6 (LOCAL-WRITE-UI-1) and PR 7 (LOCAL-PERSIST-ONLY-1)
- Submission workflow: ordinary git and GitHub CLI (gh) only; no Graphite.

## PR 6 — LOCAL-WRITE-UI-1

Branch: `test/local-write-ui-1`

Adds the LOCAL-WRITE-UI-1 stage to the local acceptance harness. This stage
drives the write-browser workflow with flags temporarily enabled, proving the
full UI write path at exact SHAs, then restores all flags false.

## Review (2026-08-06 12:45 +0700) — working-tree, PR 6

### Reviewed
- Repo / branch: munbon2-backend worktree / test/local-write-ui-1
- Scope: working-tree diff (8 modified, 1 new file, 1 coding log)
- Commands run: git diff, pytest 3x, node --check, rg for wiring
- Not inspected: runtime execution in OrbStack (source PR only)

### Findings

CRITICAL
1. `_write_ui_rid_week` disagrees with the canonical RID calendar on every input.
   The function snaps the year start to a Monday (`rid_year_start_monday`), but the
   canonical `_irrigation_year_span` starts on Nov 1 exactly regardless of weekday.
   Week numbers and `week_date` diverge — the BFF v2 route's `_require_rid_week_start`
   will reject every submission this function builds.
   — `run-stage-suite.py:4360` — fix: use the canonical `irrigation_year` /
   `irrigation_week` / `irrigation_week_span` from
   `services/bff-water-planning/src/core/rid_calendar.py`, or replicate the exact
   same arithmetic (year span starts on `date(ce-1, 11, 1)`, weeks count from
   there). — test: `test_write_ui_rid_week_uses_ending_year_rid_identity` must pin
   exact canonical values (currently only asserts pattern match, not correctness).

HIGH
2. `forbiddenMutations` is declared but never pushed to in `run-write-browser.js`.
   `forbidden_mutation_count` is always 0 regardless of what the browser does. The
   validator's `forbidden_mutation_count != 0` check is therefore vacuous — it will
   never fire.
   — `run-write-browser.js:49,325` — fix: classify mutations as forbidden when they
   occur while the stage is supposed to be dark, or when they target unexpected
   routes. — test: `test_validate_write_browser_result_rejects_forbidden_mutations`
   tests the validator correctly, but no test proves the browser actually populates
   the field.

MEDIUM
3. `RID_WEEK_KEY_PATTERN` defined at `run-stage-suite.py:4356` is dead code — never
   referenced by any function. — fix: remove it, or use it in a validation path.

4. The outage test in `run-write-browser.js:291-304` fabricates `reads_preserved:
   true` in every branch. It checks the roster endpoint status but always reports
   reads as preserved without actually verifying a read succeeds. — fix: attempt a
   real read (e.g. active GET) and report its actual outcome.

5. The logout test navigates to `/login` directly (`page.goto`) rather than clicking
   a logout button. This proves navigation, not the logout flow. —
   `run-write-browser.js:307` — fix: invoke the logout API or click the UI logout
   control.

LOW
6. `_build_dark_probe_request_v2` uses `depth_offset="0.000"` which produces
   identical zone depths to a real request with offset 0. If this probe were
   accidentally persisted against an armed runtime, the levels would be
   indistinguishable from real data. The v1 `_build_dark_probe_request` had the same
   structure, so this is inherited, but worth noting. — `run-stage-suite.py:4411`

### Open Questions / Assumptions
- The `EXPECTED_FRONTEND_SHA` constant (`fbd4ce4…`) is stale. The coding log
  records FE-5/FE-6 landed at later SHAs. This is a runtime concern (the SHA is a
  CLI default, overridden at invocation time), but it will need updating before
  this stage can actually run.
- The frontend write routes may require additional env vars (`API_SERVER`,
  `PLANNING_DEPTH_SUBMIT_PATH`, etc.) beyond the two flags. This depends on PR 5
  (frontend readiness) which has not landed.

### Recommended Tests / Validation
- Pin `_write_ui_rid_week` against exact canonical RID calendar values for several
  dates spanning Nov 1 boundaries and year transitions.
- Add a test that proves `forbiddenMutations.push` is called in the browser script
  source (string assertion in `test_local_artifacts.py`).

### Rollout Notes
- Source PR only — runtime execution is a separate acceptance step at exact SHAs.
- Both write flags default false; the stage arms them temporarily in try/finally.
- Restoration is dual-attempt (frontend first, then BFF), with a post-restoration
  check.

## PR 7 — LOCAL-PERSIST-ONLY-1

Branch: `test/local-persist-only-1`

Adds the LOCAL-PERSIST-ONLY-1 stage. Proves only W2 immutable submission/value
rows change after a planning-depth submission — no ROS, Scheduler, or
control-plan side effects.

## Review (2026-08-06 05:20:33 +0700) - PR 6 and PR 7 merged ranges

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend`
- Branch: `main`
- Scope: logical PR 6 / GitHub #147 (`23aca5ed..b95dba52`) and logical PR 7 / GitHub #148 (`b95dba52..4029b86b`)
- Commits reviewed: `b95dba52a2dcd47d43fbb89ff4922fabb054209f`, `4029b86bcdd9da3bbe6a7c98128f6b9ee9afa622`
- Commands Run: `gh pr view 147/148`, bounded `git diff --name-status/--stat`, direct source/migration/test inspection, exact-string searches, `python3 -m pytest -q --disable-warnings ops/control-plan-read-local/tests/test_stage_suite.py ops/control-plan-read-local/tests/test_orchestrate.py ops/control-plan-read-local/tests/test_local_artifacts.py` (173 passed), `node --check ops/control-plan-read-local/run-write-browser.js`, validator sensitivity probes, GitHub check-annotation inspection
- Semantic search: Auggie timed out at 1.8 seconds; review continued with the required direct-inspection fallback.

### Findings
CRITICAL
- PR 7's side-effect proof fails open. Five of six snapshot queries reference nonexistent tables/columns: `s.id`, `ros_gis.requirement_runs`, `ros_gis.daily_water_demands`, `scheduler.control_plan_drafts`, and `scheduler.control_plan_versions` (`ops/control-plan-read-local/run-stage-suite.py:4717-4741`). The migrations define `submission_id`, `ros_gis.water_requirement_runs`, `ros_gis.daily_water_requirements`, and `scheduler.control_plan_runs` (`services/bff-water-planning/migrations/010_planning_depth_submissions.sql:3-56`, `services/ros-gis-integration/migrations/0002_water_requirement_publication.up.sql:6-64`, `services/scheduler/migrations/0001_control_plan_drafts.up.sql:6-20`). `_take_persist_snapshot` converts every query failure to `[]` (`run-stage-suite.py:4746-4759`), so before/after empty arrays certify “no side effects.” Fix: use the real schema and fail closed on any snapshot error; snapshot immutable IDs/hashes for all actual downstream tables. Test: execute every query against a migration-built Postgres database and assert query failure aborts the stage.
- PR 6's claimed manual retry cannot satisfy the BFF idempotency contract. It reuses the create client UUID but changes both `expected_active_submission_id` and all six depth values (`ops/control-plan-read-local/run-write-browser.js:263-295`). The repository only replays a matching canonical request and otherwise raises `client_submission_id_conflict` (`services/bff-water-planning/src/db/planning_depth_repository.py:229-245`). The script then reads nonexistent receipt fields, while the Python validator expects UUIDs. Fix: preserve and resend the exact original request, then require status 200, `replayed=true`, and the original submission ID; separately prove a changed-body/same-ID request returns 409. Test: BFF-backed browser integration for both cases.
- PR 7 cannot follow PR 6 in the documented nine-stage sequence. PR 6 creates and corrects an append-only RID-v2 submission for `_write_ui_rid_week(context.as_of_date)` and performs no cleanup (`run-stage-suite.py:4582`, `run-write-browser.js:100-208`). PR 7 targets the same week but submits with `expected_active_submission_id=None` and requires 201 (`run-stage-suite.py:4802,4823-4840`). The repository sees PR 6's active row and returns `stale_active_submission` (`planning_depth_repository.py:247-261`). Fix: use a distinct deterministic prechecked-clean week/scope, or deliberately continue from the existing active ID. Test: run stages 8 then 9 against the same clean database.

HIGH
- The documented harness is pinned to frontend `fbd4ce4...`, which predates PR 5 RID-write readiness, while current Smart CMS `origin/main` is `067b3e2...`. `orchestrate.py` requires the supplied SHA to equal frontend `origin/main` (`ops/control-plan-read-local/orchestrate.py:408-419`), but `run_local_base` separately requires the stale constant (`run-stage-suite.py:67,1598-1602`); the runbook also supplies the stale SHA (`docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md:45-55`). No frontend SHA can satisfy both checks, so documented execution stops before either new stage. Fix: pin the accepted PR 5 merge SHA consistently or require an explicit reviewed SHA through one authority. Test: execute the documented provision/base preflight against the accepted frontend exact SHA.
- `LOCAL-WRITE-UI-1` does not exercise the UI write workflow. After merely locating a Submit button, create/correct/conflict/retry are performed by direct `page.evaluate(fetch(...))` calls (`run-write-browser.js:93-129,168-200,210-301`). Form binding, roster-to-six-zone mapping, UI client-ID retention, click handling, reconciliation rendering, and visible errors can all be broken while this script passes. Its mutation listener is attached only to the first page, so writes from `page2` are invisible (`run-write-browser.js:61-79,157-200`). Fix: operate real form/retry controls and attach a method+path allowlist observer to every context/page. Test: break the real submit handler or inject an unexpected `page2` mutation and require failure.
- The outage and logout proofs are not behavioral. No outage is induced; healthy roster status is relabeled as `submit_visible`, making a healthy run fail and a passing run unrelated to DOM visibility (`run-write-browser.js:305-331`). Logout discards the response and the validator accepts any redirect string, including a protected dashboard; retry status is also never checked (`run-write-browser.js:333-351`, `run-stage-suite.py:4464-4483`). A direct sensitivity probe confirmed status 409, zero mutations, and `/still-authenticated` redirects are accepted. Fix: inject deterministic 503/connection failure, inspect the real submit control, assert logout status and `/login` after reload, and validate exact retry status/identity. Tests: negative validator cases plus controlled Playwright runtime coverage.
- PR 7 validates only list-length deltas and accepts zero, negative, substituted, or unrelated W2 changes (`run-stage-suite.py:4763-4782`); a sensitivity probe confirmed `{}` to `{}` returns PASS. It does not bind the two response IDs to new rows, require their predecessor relation, require 41 values each, compare value/hash content, or reject unrelated W2 writes. Restoration checks only `bff.env`, despite existing harness reasoning that the env file is intended state rather than proof of the running process (`run-stage-suite.py:4195-4198,4870-4882`). Fix: compare canonical keyed rows for the exact response IDs, reject every other delta, and perform a post-disarm 503 dark probe. Tests: substitution/unrelated-write/missing-value cases and a stale-armed-process restoration case.

MEDIUM
- The “persist-only” reasoning omits known permitted non-Postgres mutations: rate-limit Redis state is consumed before each database write, and login/logout mutate auth/session state. Logout is not in an outer `finally`, so failures after disarm can leak the session. Define these effects explicitly, isolate their namespace, record them, and guarantee logout cleanup; add failure-injection coverage.
- Review/rollout evidence was not closed. PR 6's own Coding Log retained CRITICAL/HIGH findings and only some were partially remediated, with no final disposition; PR 7 added no formal review section. Neither stage has an on-disk runtime evidence artifact. Both hosted check sets failed before execution with the annotation `The job was not started because your account is locked due to a billing issue.` The source tests therefore establish syntax/unit behavior only, not OrbStack/browser acceptance.

LOW
- No additional low-severity findings; correctness and acceptance-proof failures dominate.

### Open Questions / Assumptions
- The documented stage order and single provisioned database imply PR 7 must execute after PR 6 without resetting W2 rows.
- This review treats #147/#148 as source-delivered only; no `LOCAL-WRITE-UI-1.json` or `LOCAL-PERSIST-ONLY-1.json` runtime artifact was found.
- Current frontend `main == origin/main == 067b3e22401854f8c6d6db42dc0c5c1872fca6f8` was verified locally during review.

### Recommended Tests / Validation
- Migration-built Postgres integration for all persist-only snapshot queries, including fail-closed query-error injection.
- One sequential exact-SHA runtime test covering stages 8 then 9 on the same freshly provisioned database.
- Real Playwright interaction with the rendered planning-depth form, correction/reconciliation UI, byte-identical retry, induced outage, and logout/reload.
- Validator sensitivity tests for retry status/receipt identity, exact redirects, zero mutation counts, empty snapshots, arbitrary W2 substitutions, and exact two-submission/82-value lineage.
- Post-restoration dark POST probes for both stages.

### Rollout Notes
- Do not use #147/#148 as acceptance evidence for `LOCAL-WRITE-ACT-1`, `LOCAL-RC-1`, deployment, or AWS authorization.
- Keep frontend and backend write flags false until remediation is source-reviewed and the full exact-SHA local sequence produces hash-listed runtime evidence.
- Remediate through new PRs; do not rewrite the merged history. Re-run formal g-check and the complete local stage chain after fixes.

## Review (2026-08-06 05:42:28 +0700) - logical PR 1 through PR 5 merged ranges

### Reviewed
- Repos: `/Users/subhajlimanond/dev/munbon2-backend` and `/Users/subhajlimanond/dev/smart-cms-app`
- Branches: backend `main` at `4029b86bcdd9da3bbe6a7c98128f6b9ee9afa622`; frontend `main` at `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`
- Scope: logical PR 1 frontend `1fff435623c505e483983a6924883e68d08cc26a`; PR 2 frontend `3a8590aaeba5981c9afa202873458768ac32c655`; PR 3 backend `3e5946c8b5fdba688808bcf150741f719a1ecdd9`; PR 4 backend `23aca5ed7270476da9f4b2d12192445f78f15abf`; PR 5 frontend range `215847bedfba06f00462d15971feac8505afbdfa..067b3e22401854f8c6d6db42dc0c5c1872fca6f8`
- Commands Run: compact Git/GitHub metadata and check inspection; bounded diff stats/name lists; direct source, migration, contract, test, and Coding Log inspection; `npm test -- --run` (79 files, 880 tests); service-venv BFF focused pytest (55 passed); service-venv ROS-GIS focused pytest (30 passed); ROS RID Jest (51 passed); byte-for-byte comparison of 31 backend/frontend pinned contract files
- Semantic search: Auggie timed out at 1.8 seconds; review continued with direct inspection and exact-string searches as required.

### Findings
CRITICAL
- No findings in the cumulative current PR 1-5 source.

HIGH
- PR 3 publishes roster provenance, but PR 4 drops it before immutable write persistence and performs roster validation outside the write transaction. `load_authoritative_planning_depth_roster` obtains `dataset_version_id` and `source_hash` (`services/bff-water-planning/src/db/planning_depth_repository.py:65-117`), while the v2 route converts that projection to provenance-free rows on one connection and later opens a second connection for insertion (`services/bff-water-planning/src/api/routes/planning_depths_v2.py:74-76,107-114`). The insert stores request/expanded hashes but neither roster version nor source hash (`planning_depth_repository.py:266-294`). An authority activation in that gap can therefore persist a submission against a no-longer-current snapshot, and the immutable ledger cannot later prove which roster revision produced its 41 values. Fix: retain the full roster projection, store its version/hash on every submission, and load/revalidate it inside the same write transaction. Test: real-Postgres activation race plus receipt/readback provenance assertions.

MEDIUM
- PR 5 deliberately suppresses automatic 401 replay for writes, but the auth client returns the 401 without clearing or refreshing the expired session (`smart-cms-app/lib/auth/client.ts:158-184`). The panel then instructs the operator to sign in again (`smart-cms-app/components/smart-water/dashboard/water-planning/PlanningRhsPanel.tsx:376-390`) while `isAuthenticated` can remain true, leaving the application in a stale authenticated state and inviting repeated failed submissions. Fix: on a non-replayed mutation 401, invalidate the in-memory session without resubmitting the write (or refresh only for the next deliberate action). Test: 401 mutation clears/reauthenticates the session while proving exactly one POST occurred.
- Roster v1 is an exact V5 authority contract, not an evolvable schema-only contract: backend and frontend both hard-pin all 41 memberships/areas (`services/bff-water-planning/src/schemas/planning_depth_roster.py:17-74,119-136`; `smart-cms-app/lib/water-planning/planning-depth-roster.ts:62-102`). This is currently fail-closed and consistent, but any legitimate roster correction requires a coordinated versioned backend-contract/frontend rollout; changing only `dataset_version_id` or `source_hash` will not authorize new membership. Fix direction: explicitly document roster-v1 immutability and define the v2 transition/compatibility policy before the first authority rotation. Test: version-roll test that proves v1 rejects changed membership and the next version is intentionally accepted.
- Evidence is incomplete rather than failed product behavior. Frontend PRs 1, 2, and 5 have no hosted checks; PR 5's Coding Log names exact local CI-1/CI-2 evidence directories, but those directories are absent from the current checkout, so their manifests cannot now be independently rehashed. Backend PRs 3 and 4 show every hosted job failed with zero steps because of the account billing lock. Current source/unit tests were rerun successfully, but no warm-stack/browser/live-write acceptance was produced in this review.

LOW
- No additional low-severity findings.

### Open Questions / Assumptions
- Roster v1's literal V5 membership is treated as intentionally immutable; if operators expect same-version dataset rotations to change areas or membership, the current contract is too rigid and the medium rollout finding becomes a functional blocker.
- The PR 5 local CI evidence claims are accepted as historical log statements only; the missing directories mean this review does not independently confirm their original SHA256 manifests.
- Historical PR 2 gaps are not current findings: its schema-v1/`YYYY-Wnn` contract, roster-blind payload construction, and per-build UUID were corrected by PR 5 with v2/RID identity, strict roster gating, and durable pending intent.

### Recommended Tests / Validation
- Add migration-built Postgres coverage that activates a new roster version while a write is in flight and proves the committed row binds the exact roster dataset/hash.
- Add auth-client plus panel integration coverage proving a mutation 401 sends one POST, clears stale authentication, and requires deliberate reauthentication with no hidden replay.
- Define and test the roster-v1-to-v2 authority rotation policy.
- Preserve exact-candidate frontend CI-1/CI-2 manifests in a durable evidence location, restore hosted checks, and run the later real UI/live-write acceptance only after PR 6/7 remediation.

### Rollout Notes
- PR 1-5 cumulative source remains dark-by-default and substantially correct, but it is not activation evidence. Keep frontend and backend write flags false.
- Remediate roster provenance before relying on immutable W2 rows for audit or downstream planning. Treat hosted checks as infrastructure-blocked, not passing.
- The PR 6/7 acceptance defects in the preceding review remain independent blockers even after these PR 1-5 issues are addressed.
