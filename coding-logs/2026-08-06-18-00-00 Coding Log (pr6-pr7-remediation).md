# PR 6 / PR 7 remediation — acceptance-readiness

- Created: 2026-08-06 18:00:00 +0700
- Backend baseline: `4029b86b` (origin/main; includes the defective PR 6 #147 + PR 7 #148)
- Frontend baseline: `067b3e2` (smart-cms-app origin/main)
- Trigger: independent senior review found 3 CRITICAL, 4 HIGH, 2 MEDIUM gaps in the
  merged LOCAL-WRITE-UI-1 and LOCAL-PERSIST-ONLY-1 stages.
- Scope chosen by user: **source fix-forward + real OrbStack runtime run** (stages 8→9
  sequentially against one live DB with a real browser at exact SHAs).

## Ground truth established (Phase 1 / Phase 5 verification)

Every reviewer finding was reproduced against the real repo before planning:

- **Single database**: the guest uses one `munbon_local` DB for all services
  (bootstrap-linux.sh lines 277/286/294/298/306 all share `POSTGRES_URL_VALUE`), so a
  single `_psql` connection sees `water_planning`, `ros_gis`, and `scheduler` schemas.
- **Real snapshot tables** (5 of my 6 PR 7 queries were fictional):
  - `water_planning.planning_depth_submissions` (PK `submission_id`; NOT `id`)
  - `water_planning.planning_depth_values` (`submission_id` FK; PK `(submission_id, section_id)`)
  - `ros_gis.water_requirement_runs`  (I used nonexistent `ros_gis.requirement_runs`)
  - `ros_gis.daily_water_requirements` (I used nonexistent `ros_gis.daily_water_demands`)
  - `scheduler.control_plan_runs` (`plan_id, plan_version, draft_content_hash, lifecycle_state`)
    — this is BOTH "scheduler draft" AND "control-plan version/hash". I used nonexistent
    `scheduler.control_plan_drafts` and `scheduler.control_plan_versions`.
  - `scheduler.control_plan_campaign_versions` (campaign identity)
  - My `except StageGateError: snapshot[key] = []` converted every wrong-table failure to
    `[]`, so two broken snapshots compared equal → **fail-open**.
- **Replay is byte-identical** (`planning_depth_repository.py` L239-261): a row is a replay
  only if `(calendar_system, client_submission_id)` matches AND `submitted_by` matches AND
  `request_sha256` matches. My PR 6 retry changed depths (250→280) and
  `expected_active_submission_id`, so it hashes differently → `client_submission_id_conflict`,
  not a replay.
- **Root-per-scope** unique index on `(project_key, calendar_system, week_key)` WHERE
  `supersedes_submission_id IS NULL` (migration 010 + 011). PR 6 leaves a v2 root for
  `(mun-bon, rid-irrigation-v1, W_ui)`; PR 7 submitting `active=None` for the SAME scope
  can never return 201 → `stale_active_submission`. Fix: persist-only uses a DISTINCT RID week.
- **Frontend SHA is unrunnable by construction**: `run-stage-suite.py:1601` hard-pins
  `context.frontend_sha == EXPECTED_FRONTEND_SHA` (`fbd4ce4…`), while `orchestrate.py:417`
  requires `--frontend-sha == frontend origin/main` (now `067b3e2…`). The two can never both
  hold.
- **Frontend write env missing**: the proxy routes require `API_SERVER`,
  `PLANNING_DEPTH_SUBMIT_PATH`, `PLANNING_DEPTH_ACTIVE_PATH`, `PLANNING_DEPTH_ROSTER_PATH`
  (route.ts + environment.example). The harness `frontend_process_environment` set none of
  them, so every proxy returns 503 "not configured" even with flags on → the real run would
  fail at create. Exact values:
  - `API_SERVER=http://127.0.0.1:3022`
  - `PLANNING_DEPTH_SUBMIT_PATH=/api/v2/water-planning/planning-depth-submissions`
  - `PLANNING_DEPTH_ACTIVE_PATH=/api/v2/water-planning/planning-depth-submissions/active`
  - `PLANNING_DEPTH_ROSTER_PATH=/api/v1/water-planning/planning-depth-roster/v1`
- **v2 active** returns exactly 41 expanded levels; **v2 receipt** carries
  `supersedes_submission_id` + `replayed`; **roster** is `/api/v1/water-planning/planning-depth-roster/v1`.

## Process failure being corrected

PR 7 skipped g2-planning entirely and never grep-verified table names (Phase 5). PR 6/PR 7
were self-reviewed with g2-check only, never an independent Tier-2 reviewer (g2-qcheck).
Source tests validated the validators with hand-fed dicts — vacuous against schema, contract,
sequencing, and browser-evidence reality. This remediation fixes the code AND proves it with a
real runtime run.

## Codex adversarial review (gpt-5.6-sol xhigh) — synthesis + dispositions

The independent adversarial gate found the first DREP still substantially broken — including
two run-blockers and two factually-impossible claims. Every finding dispositioned (silent
omission of a Codex finding is a defect):

**Run-blockers (ACCEPTED, verified):**
- Credential alias: operator.env sets `MUNBON_OPERATOR_EMAIL/PASSWORD` (bootstrap L328-329;
  read/go-read browsers use these). My run-write-browser.js required `LOCAL_OPERATOR_*` → exits
  before login. Fix: use `MUNBON_OPERATOR_*`; test asserts every JS-required env name is
  populated by the `_run_*_browser` env dict.
- Proxy receipt is reduced camelCase `{success, submissionId, submittedAt, replayed}`
  (route.ts:186) — NO `client_submission_id`/`week_key`/`request_sha256`. Evidence must capture
  the browser's OUTGOING POST body (holds client_submission_id) and correlate with the reduced
  receipt. Validator rewritten around captured-request + reduced-receipt.

**Two requirements REFRAMED to what is provable (product authz forbids the literal claim):**
- Field-team "sees reads": FALSE for planning-depth. Roster (planning_depth_roster.py:32) AND
  active (planning_depths_v2.py:140) both call `load_operator_principal` → 403 for non-operator.
  Reframed R14: prove field-team is **denied the planning-depth submit capability** (Submit absent;
  roster/active 403 → mutation-policy `forbidden`) and a non-planning-depth read view still
  renders. Not "sees planning-depth reads."
- Outage "preserves reads": FALSE. BFF down → proxy 502 (upstream-guard.ts); Scheduler down →
  `load_operator_principal` fails → active+roster fail. Reframed R10: prove **submit hidden/disabled
  AND no successful POST** during the induced outage; name the exact surviving non-planning-depth
  read + DOM selector if any is claimed. Drop `reads_preserved=true` for planning-depth reads.

**Design corrections (ACCEPTED):**
- Replay lives in JS: browser captures create POST body, resends byte-identical (same
  client_submission_id + levels + expected_active), correlates `replayed=true` + same `submissionId`.
  Provider clears pending UUID after success (L304); stable reuse only holds while an identical
  pending request remains (L243) — so the replay is an explicit resend of the captured body, NOT a
  second UI click after success.
- Real UI create = target week aligned to UI default (**today**, WaterPlanningProvider.tsx:116) →
  edit cm input → **Save** (mandatory; canSubmit needs `!hasUnsavedChanges`, PlanningRhsPanel.tsx:430)
  → **Submit** ("ส่งแผน"). persist-only (API-driven) uses a DISTINCT week.
- `data-testid="submit-planning-depth"` does NOT exist at 067b3e2 — use accessible name "ส่งแผน" +
  correlate its POST.
- Frontend SHA hard pin is at run-stage-suite.py:1601 inside **run_local_base** (stage 0), not
  `_verify_frontend_source` (2518). **Non-goal updated**: the shared SHA fix may touch run_local_base.
  Fix = verify guest checkout == `context.frontend_sha` (orchestrate already validates == frontend
  origin/main), not a frozen constant. Do NOT just bump the pin.
- Dark frontend env: `frontend_process_environment` starts `**os.environ`, so inherited write-path
  vars survive when dark. Must delete `API_SERVER`/`PLANNING_DEPTH_*` when submit not armed; test in
  a polluted env.
- Persist-only diff binds to: target (project_key, calendar_system, week_key), create+correct
  receipt IDs + client IDs, `S2.supersedes==S1`, 41 values each (82 total), expected request/expanded
  hashes, and NO other W2 delta. Non-W2 tables: deterministic digest of the FULL row projection
  (status/published_at/failure_reason mutable while content_hash is not — 0002 migration).
- Redis (R15): rate-limit key in **DB 2**, hashed subject, increments before replay/conflict
  (planning_depth_submission.py:231); snapshot specifies DB 2 + expected delta + TTL. Auth: login
  persists `auth.refresh_tokens` (revoked, not deleted, on logout — auth.service.js:185), NOT
  `auth.sessions`. Add cleanup-failure test.
- Logout (R11): capture the real `/api/auth/logout` status + prove refresh-token revocation (a
  later refresh fails); client redirects even on failed logout (auth client:131). Logout every
  context.
- Distinct week (R4): `_persist_only_rid_week` gets a real algorithmic contract; boundary tests
  for R01, R52/R53, Oct25–Nov8, leap spans, supported-year endpoints; validate BOTH key and
  canonical week-start; guarantee != write-UI week, 1..53, supported year.
- Both-context monitoring: extract a **pure JS request-classifier**, unit-test with `node --test`
  (like test_go_read_browser_inventory.js); string inventory insufficient.
- Snapshot tests: assert columns + fail-closed on error; real SQL execution proven by the runtime
  run.
- orchestrate.py lacks `--as-of-date` passthrough — add it. Migrations apply in LOCAL-RTA-1, not
  provisioning; run all 9 in order; do NOT re-provision between stages; provision AFTER the
  remediation lands (harness hashes bind stage identity, run-stage-suite.py:1541).
- Evidence closure (R16): formal QCHECK/g-check disposition, coding-log closure, evidence archive
  inventory + checksum + sanitization test, and test_seed_local_operators.js for the field-team seed.

**REJECTED/none** — every finding accepted; the two reframings are truthful necessities.
This synthesis supersedes the first DREP's R7/R10/R11/R14/§5/§6 wording.

## PIVOT (2026-08-06, 2nd senior review) — drop local-JWT; adopt truthful-evidence path

A second senior reviewer's three claims were **verified true against the code**:
1. `verify_bearer.py:116 decode_jwt_claims` base64-decodes the payload only — NO signature
   check. Mirroring it in the BFF would accept forged tokens. My Tier B suggestion was wrong.
2. Scheduler `core/deps.py:21 verify_token` is the real authority: `jwt.decode` with algorithm
   PINNED from settings, `exp` required, clock-skew leeway, and `get_current_user` fail-closes
   on the Redis revocation store. A hand-rolled BFF verifier would regress security + contradict
   "Scheduler is the JWT authority".
3. Roster provenance HIGH (pre-existing, PR 3/4): roster is read in a separate connection that
   closes BEFORE the advisory-locked write txn (route L74-75 vs repository L221), and the INSERT
   (L263-296) stores only request/expanded hashes — NOT dataset_version_id/source_hash. TOCTOU +
   no provenance binding.

**User decisions (with corrected framing):** ADOPT reviewer's path; INCLUDE R0 first.
My earlier Question 2 framing created a false dilemma — truthful 403/503 + Submit-hidden +
no-write IS what the original review required, not a deviation. My Tier B ("mirror
verify_bearer.py") was dangerous. Both owned.

**Superseding plan (this remediation = PR 6 + PR 7 only; PR 8/9 are later):**
- **DROPPED**: local JWT in BFF, read/write authz split, `can_submit` contract, frontend policy
  PR. Scheduler stays sole JWT authority; planning-depth reads stay operator-only. **Frontend
  unchanged at 067b3e2** (existing UI already hides Submit on forbidden/unavailable policy).
- **R0** (BFF, migration 012): bind roster INSIDE the write txn; store dataset_version_id +
  source_hash on every submission (v1+v2); real-Postgres authority-activation race test.
- **R1** (harness core + persist-only): real tables + fail-closed + full-row digest (now incl
  the R0 provenance columns) + receipt-bound diff + distinct RID week (boundary contract) +
  SHA/env/credential fixes + migration parity tail → 012 + Redis DB2/auth.refresh_tokens +
  orchestrate --as-of-date.
- **R2** (browser): real UI edit→Save→Submit; capture+byte-identical replay; both-context
  classifier (node --test); real Scheduler outage (coordination pattern) → reads unavailable +
  Submit disabled/absent + no POST (NEVER reads_preserved=true); field-team → 403 + Submit
  absent + no write; logout response + refresh-token revocation. MUNBON_OPERATOR_* creds.
- Then: 9-stage sequential OrbStack run at landed backend SHA + frontend 067b3e2, both flags
  restored false. Then remove worktree. (PR 8 LOCAL-WRITE-ACT-1 / PR 9 LOCAL-RC-1 are a
  separate later effort.)

## R0 mini-DREP — Codex adversarial (gpt-5.6-sol xhigh) — NO-GO as written; dispositions

All ACCEPTED (the snapshot-used direction is right, but every refinement was only partially
closed):
- **Race test T3 was not a barrier test / wrong level.** Must exercise the real v1/v2 ROUTE,
  block after snapshot capture but before the write via an injected asyncio.Event barrier +
  a spy on create, activate V2 through a SECOND connection, release, assert persisted provenance
  == V1 AND the route passed the same snapshot object into create. Repository-only tests pass
  even if the route still uses the old loader.
- **`sections_current` is a derived JOIN VIEW, not a table** (ROS 0001:108). V2 activation must
  insert V2 rows into `dataset_versions` (+ underlying sections) and supersede V1 — NOT "update
  sections_current". (Factual correction.)
- **Value assertion is weak**: every valid roster normalizes to the same 41-section canonical
  shape, so expanding V2 while storing S1 can yield identical values. Distinguish by IDENTITY —
  V1 and V2 must have DIFFERENT source_hash/dataset_version_id; assert the stored identity is V1's.
- **frozen dataclass + list is NOT immutable** → use `tuple`/Sequence for sections. "Cannot
  mismatch" relies on the authoritative loader returning identity+sections from ONE query +
  exact-object route wiring, not the dataclass — add route tests proving same-object pass-through.
- **Insert-site audit was FALSE**: the integration helper (test_planning_depth_postgres.py:202)
  and fixtures (356, 691) do DIRECT inserts → the new required-provenance trigger breaks them.
  Migrate every fixture to supply valid provenance.
- **Trigger masks the all-or-none CHECK test**: a half-null insert is rejected by the trigger
  before the CHECK fires. Test the CHECK with the trigger temporarily dropped OR assert the exact
  constraint name. Rejection tests must assert specific constraint/trigger identity, not just
  exception class (23514 could pass for the wrong reason). Note existing BEFORE INSERT predecessor
  trigger (011:99) — name the new trigger for correct ordering.
- **Replay**: add explicit tests — post-012 replay retains original S1 provenance (no new insert);
  legacy replay retains NULL,NULL.
- **T4 must use the real tracked runner** `apply_migrations` (migration_runner.py:148): registry
  at 009-011, seed v1+v2 rows, run, prove only 012 applied.
- **Migration test coverage expanded**: update test_planning_depth_migrations.py (009-011 hard-pin
  → +012 with LITERAL immutable 010/011 hashes) and integration migration-status (3→4 entries).
- **Down migration is unsupported** (BFF runner is forward-only, migration_runner.py) — false
  claim removed. Rollback = app tolerates the additive columns and retains 012; never drop
  (would destroy captured provenance).
- **LOCAL-RTA-1 WILL break** (harness parity gate run-stage-suite.py:1237 requires bff tail 011;
  unit oracle test_planning_depth_runtime.py:49 expects latest 011/count 3). **R0 non-goal
  corrected: R0 MUST also bump the harness migration-parity tail 011→012** (run-stage-suite.py
  validate_migration_parity + _apply_migrations, ops test_stage_suite.py parity test,
  bff test_planning_depth_runtime.py). R0 blast radius now includes the harness parity gate.

Net: R0's real change set = migration 012 (+ trigger + checks) · manifest + migration tests ·
RosterSnapshot(tuple) + snapshot loader · both write routes pass the snapshot · repository INSERT
· migrate existing direct-insert fixtures · route-level same-object + barrier race tests ·
replay-provenance tests · harness parity tail 011→012. Larger than first scoped, but correct.

### R0 implementation progress (branch feat/planning-depth-roster-provenance)

DONE + validated:
- migration 012 written; **DB-validated on real Postgres** (disposable docker pg16): valid
  provenance accepted; NULL→trigger P0001 `planning_depth_roster_provenance_required`; half-null
  (trigger dropped)→all-or-none CHECK; bad hex→format CHECK. 010/011 bytes unchanged.
- manifest.json: 012 entry + sha256 61d167f6…
- repository: `RosterSnapshot` (frozen, `sections: tuple`) + `load_planning_depth_roster_snapshot`
  (identity+sections from ONE projection); `_create_planning_depth_submission` expands
  `roster.sections` and INSERTs `roster_dataset_version_id`/`roster_source_hash`; both create
  wrappers take `RosterSnapshot`.
- routes v1+v2: use the snapshot loader; expand `roster.sections`; pass the same snapshot object.
- migrated existing unit tests to the new signature (repository test asserts provenance; both
  route mocks patch `load_planning_depth_roster_snapshot` and return a `RosterSnapshot`).
- migration tests: added 012 to manifest/apply lists; **literal immutable hash pins for 010 AND
  011 AND 012**; unlisted-migration probe moved to 013.
- harness parity tail 011→012: `validate_migration_parity` (run-stage-suite.py), bff runtime
  parity unit test, ops test_stage_suite parity test. **BFF 94 planning-depth unit tests GREEN;
  ops harness 189 GREEN.**
- local BFF venv (py3.13, non-geo deps) built for TDD; disposable pg16 on :55432.

REMAINING for R0 (not yet done — do NOT treat R0 as landed):
- migrate integration fixtures: `_insert_submission` helper + ~11 `load_planning_depth_roster`
  call sites in tests/integration/test_planning_depth_postgres.py → snapshot + provenance; and
  the integration migration-status assertion (3→4).
- NEW acceptance tests: provenance stored (v1+v2, integration); all-or-none in isolation
  (trigger dropped, assert constraint name); ROUTE-LEVEL barrier race (asyncio.Event between
  snapshot capture and write, activate V2 via dataset_versions/section_master_history, assert
  stored==V1 identity + same-object pass-through); migration 011→012 upgrade via the real
  apply_migrations runner with existing v1+v2 rows; replay retains original/NULL provenance.
- run the full integration suite against BFF_TEST_POSTGRES_URL (disposable pg).
- independent Codex Tier-2 QCHECK; then PR → admin-merge → land. THEN R1, R2, real run.

### R0 implementation COMPLETE (2026-08-06 resume) — green, awaiting QCHECK verdict

Env: disposable PostGIS docker (postgis/postgis:16-3.4) on :55432, db bff_r0_test (ROS 0001
migration needs the postgis extension — plain postgres:16 is insufficient). venv pytest pinned
7.4.3 (pytest 8 breaks pytest-asyncio 0.21.1 async fixtures). BFF_TEST_POSTGRES_URL set to the
disposable loopback db.

Done this resume:
- Integration fixture migration: import + all ~11 `load_planning_depth_roster` → snapshot;
  `_insert_submission` now supplies provenance (fixed valid value; column has no FK);
  migration-status assertion 3→4; the immutable/one-successor direct-INSERT test got provenance
  on ALL FOUR inserts (the require-provenance trigger fires BEFORE the uniqueness constraints
  those cases exercise); the roster-projection test iterates `roster.sections`.
- NEW R0 acceptance tests (integration, real Postgres): provenance stored v1 + v2 (assert by
  IDENTITY — seeded active roster source_hash = '1'*64); deterministic snapshot-used race
  (capture V1 → activate V2 via dataset_versions/section_master_history → create(V1) → stored ==
  V1, NOT V2); post-012 replay retains original provenance; all-or-none CHECK in isolation
  (trigger dropped, assert constraint name `planning_depth_roster_provenance_all_or_none`);
  011→012 upgrade via the REAL runner with existing v1+v2 rows (only 012 applies; legacy rows
  keep NULL; new insert without provenance → trigger rejects with the stable message).
- NEW unit test: v2 route passes the loader's EXACT snapshot object into create (same-object).
- Migration DDL behaviors DB-validated earlier; provenance tests **mutation-verified**: storing a
  wrong source_hash fails all 4 provenance tests, revert → green (non-vacuous per 2c-bis).

Results (Claude ran each): BFF full suite **360 passed / 1 skipped** (unit + integration incl. 6
new R0 integration tests + same-object unit test); planning-depth subset 95 unit + 24 integration;
ops harness **189 passed**; R0 integration subset green **3× consecutive** (no flakiness). The 9
transient failures seen mid-run were a local-venv gap (missing `uvicorn`), not R0 — installing it
→ all pass; NOT a regression.

Status: R0 IMPLEMENTED + GREEN; **independent Codex Tier-2 QCHECK in flight** (the gate skipped on
the original PR 6/7). No commit/PR until QCHECK is clean and CRITICAL/HIGH fixed. Files all staged
in the index (still no commit).

### QCHECK round 1 (independent Codex gpt-5.6-sol xhigh) — findings + fixes

No CRITICAL. **1 HIGH + 4 MED/LOW, all ACCEPTED and remediated:**
- **HIGH — migration 012 permitted FABRICATED provenance.** Format/positivity/presence were
  checked, but not that (dataset_version_id, source_hash) identifies a real section_master
  dataset → a direct insert of a bogus pair became immutable, defeating provenance. FIX: the
  require-provenance trigger now also `RAISE`s `planning_depth_roster_provenance_unknown` unless
  the pair EXISTS in ros_gis.dataset_versions with dataset_kind='section_master' — deliberately
  NOT gated on status='active' (superseded snapshots remain valid). plpgsql late-binds ros_gis,
  so 012 applies even before ros_gis exists. Fixtures updated to real pairs (_insert_submission
  looks up the active pair; immutable test uses subqueries). New tests: mismatched/nonexistent
  rejected; superseded-but-real accepted. **Mutation-verified**: disabling the check (IF FALSE,
  manifest hash bumped so apply proceeds) fails the mismatch test; restored → green.
- **MED — format/positivity CHECKs had no behavioral test.** Added isolation tests (drop the
  trigger, assert the specific constraint names planning_depth_roster_source_hash_format /
  planning_depth_roster_dataset_version_positive).
- **MED — v1 route same-object untested.** Added v1 route same-object test (mirror of v2).
- **MED — v2 replay-provenance untested.** Added test_post_012_replay_retains_original_provenance_v2.
- **LOW — docs stale.** acceptance doc + runtime README BFF tail 011→012. The `migration_011`
  evidence-step key in run_write_foundation_drills is a pre-existing mislabel in the merged
  LOCAL-WRITE-FOUNDATION-1 stage (it checks the write flag, not the parity gate) — out of R0
  scope; left as-is.
- Migration 012 hash changed to eeb43a63…; re-pinned in manifest + migration unit test +
  integration migration-status.

Post-fix: BFF full suite **366 passed / 1 skipped**; ops harness **189 passed**; R0 provenance
subset (13 tests) green **3× consecutive**. QCHECK round 2 (loop-until-dry) in flight.

### QCHECK round 2 (independent Codex, loop-until-dry) — findings, fixes, and residual scope

Round 2 was NOT dry (loop working). 2 HIGH + 1 LOW. Split by shape:

**Fixed now (proportionate, in-scope):**
- HIGH-1 (partial): a real but DRAFT section_master pair was accepted (ROS permits `draft`; my
  existence check only verified row existence). FIX: existence check now requires `status <>
  'draft'` (published: active or superseded — superseded still valid per snapshot-used). Verified
  `sections_current` filters `status='active'`, so legitimate app snapshots are never rejected.
  New test `test_database_rejects_draft_roster_provenance`. 012 hash → a557b990…; re-pinned in all
  three sites.
- LOW: both replay tests reused the same snapshot. STRENGTHENED: replay now activates a DIFFERENT
  roster first and passes the new snapshot, asserting the ORIGINAL provenance is retained (v1+v2).
  Added `_activate_replacement_roster` helper (also used by the snapshot-used test).

**Residual — cross-service / architectural; user decision = LAND R0 now, FILE as follow-ups:**
- HIGH-1 (residual): a privileged DIRECT SQL writer could still attach a real published-but-
  UNRELATED pair. Complete fix = a SECURITY-DEFINER controlled-insert procedure (change to how
  ALL submissions are written). The application path never does this and is verified correct.
  FOLLOW-UP: "planning-depth controlled-insert procedure" hardening (separate decision).
- HIGH-2 (drift): `ros_gis.dataset_versions.source_hash` is DB-mutable, so a stored pair could
  later orphan. LATENT (grep: nothing in ROS updates source_hash). Fix belongs to ROS's schema
  (make dataset_versions identity immutable) or a composite FK needing a new unique index on
  ROS's table + migration-order coordination — cross-service either way. FOLLOW-UP: "ROS
  dataset_versions.source_hash immutability".

These residuals do not block R0's mandate (record, atomically+immutably, the real snapshot the
app used, with null/nonexistent/mismatched/draft all rejected). Round 3 not run: user elected to
land now with residuals filed; round-2 fixes are contained and the HIGH existence-check fix is
mutation-verified.

Post round-2: BFF full **367 passed / 1 skipped**; ops harness **189 passed**.

## SESSION PAUSE HANDOFF (2026-08-06) — R0 IMPLEMENTED BUT NOT ACCEPTED; NO PR

Status label: **R0 implemented, NOT accepted, NOT PR-ready.** No commit, no PR. Do not treat
R0 as landed. Do not remove or prune the worktree.

### Exact git state
- Worktree: `.claude/worktrees/pr6-pr7-remediation` (keep — do NOT prune).
- Branch: `feat/planning-depth-roster-provenance`.
- HEAD = `4029b86bcdd9da3bbe6a7c98128f6b9ee9afa622` (no commits on the branch yet).
- Base = origin/main = main = `4029b86bcdd9da3bbe6a7c98128f6b9ee9afa622` (all equal; verified).
- Product changes are isolated in this worktree; the primary checkout is untouched.

### Index / worktree inventory (mixed index is DELIBERATE)
Staged (index):
- `A  services/bff-water-planning/migrations/012_planning_depth_roster_provenance.sql`
  — staged via `git add -f` ON PURPOSE. `*.sql` is gitignored (.gitignore:100), and
  `test_manifest_pins_every_owned_sql_file_and_git_tracks_them` requires the file to be
  git-tracked (`git ls-files --error-unmatch`). Unstaging it reverts that test to RED and
  makes the file an invisible ignored artifact. Leave it staged. This matches how 009/010/011
  are tracked. Do NOT commit it alone — the next session commits the whole R0 set together.

Unstaged (worktree, modified):
- `ops/control-plan-read-local/run-stage-suite.py` (validate_migration_parity bff tail 011→012)
- `ops/control-plan-read-local/tests/test_stage_suite.py` (parity test → 012/count 4)
- `services/bff-water-planning/migrations/manifest.json` (012 entry + sha256 61d167f6…)
- `services/bff-water-planning/src/api/routes/planning_depths.py` (snapshot loader)
- `services/bff-water-planning/src/api/routes/planning_depths_v2.py` (snapshot loader)
- `services/bff-water-planning/src/db/planning_depth_repository.py` (RosterSnapshot + INSERT)
- `services/bff-water-planning/tests/unit/test_planning_depth_migrations.py` (012 + literal hash pins)
- `services/bff-water-planning/tests/unit/test_planning_depth_repository.py` (snapshot loader)
- `services/bff-water-planning/tests/unit/test_planning_depth_routes.py` (mock → snapshot)
- `services/bff-water-planning/tests/unit/test_planning_depth_runtime.py` (parity → 012/4)
- `services/bff-water-planning/tests/unit/test_planning_depth_v2_routes.py` (mock → snapshot)
- `.codex/coding-log.current` (pointer to this log)

Untracked:
- `coding-logs/2026-08-06-18-00-00 Coding Log (pr6-pr7-remediation).md` (this log — the handoff).
- `services/bff-water-planning/venv/` (gitignored; local py3.13 TDD venv, non-geo deps installed;
  reusable next session — avoids reinstall).

### Commands run + reported results (this session)
- Migration DDL validated on real Postgres (disposable): valid provenance INSERT `INSERT 0 1`;
  NULL provenance → `planning_depth_roster_provenance_required` (trigger, P0001); half-null with
  trigger dropped → `planning_depth_roster_provenance_all_or_none` (CHECK); bad hex →
  `planning_depth_roster_source_hash_format` (CHECK).
- `./venv/bin/python -m pytest tests/unit/ -q -k planning_depth` → **94 passed** (0 failed).
- `python3 -m pytest tests/` in ops/control-plan-read-local → **189 passed** (0 failed).
- 010/011 bytes unchanged (shasum matches recorded manifest hashes).
- Integration suite (tests/integration) **NOT run yet** — no BFF_TEST_POSTGRES_URL wired, fixtures
  not migrated. This is why **R0 is not PR-ready**.

### Disposable Postgres — lifecycle / recreation (no secrets; use a throwaway local password)
The validation container was removed at pause. Recreate fresh next session:
```
docker run -d --name munbon-r0-pg -e POSTGRES_PASSWORD=<throwaway-local-pw> \
  -e POSTGRES_DB=bff_r0_test -p 55432:5432 postgres:16
# wait: docker exec munbon-r0-pg pg_isready -U postgres
# integration tests read BFF_TEST_POSTGRES_URL and require a loopback DB whose name
# contains 'test' (see test_planning_depth_postgres.py::_assert_disposable_loopback_url):
export BFF_TEST_POSTGRES_URL="postgresql://postgres:<throwaway-local-pw>@127.0.0.1:55432/bff_r0_test"
```
The harness applies the BFF migration set + the ROS `0001_dataset_version_parent` migration and
seeds an active roster (source_hash = repeat('1',64)) + a superseded one (repeat('0',64)); that
active source_hash/dataset_version_id is the V1 identity the race test asserts. Do NOT use the
user's existing timescale container.

### NEXT-SESSION PICKUP ORDER (no re-planning needed — reread this log + the R0 dispositions)
0. Reread this log; `git rev-parse origin/main` (expect 4029b86b); `git status` (expect the
   inventory above); recreate disposable Postgres (above).
1. **Fixture migration**: `_insert_submission` helper (add roster provenance cols/params) + the
   ~11 `load_planning_depth_roster` call sites in tests/integration/test_planning_depth_postgres.py
   → `load_planning_depth_roster_snapshot`; update the integration migration-status assertion 3→4.
2. **Provenance v1/v2** (integration): new submissions persist the active roster's
   dataset_version_id + source_hash; assert by IDENTITY (not values — every valid roster
   normalizes to the same 41-section shape).
3. **All-or-none in isolation**: drop only the require-provenance trigger, attempt a half-null
   insert, assert the CHECK constraint name `planning_depth_roster_provenance_all_or_none`.
4. **Controlled route-level race** (deterministic, barrier not sleep): drive the real v1/v2 route,
   block via an asyncio.Event after snapshot capture but before create, activate V2 through
   `dataset_versions` + `section_master_history` (NOT `sections_current`, which is a view),
   release, assert persisted provenance == V1 identity AND the route passed the same snapshot
   object into create.
5. **Runner upgrade**: registry at 009–011 with existing v1+v2 rows, run the real
   `apply_migrations`, prove only 012 applied and legacy rows keep NULL/all-or-none.
6. **Replay provenance**: post-012 replay retains original S1 provenance (no new insert); legacy
   replay retains NULL,NULL.
7. Focused + full BFF gates (unit + integration) green against the disposable PG; ops harness
   suite green.
8. Independent Codex Tier-2 QCHECK (never self-review); fix CRITICAL/HIGH.
9. Formal independent review; then PR → admin-merge → land. THEN R1 → R2 → real 9-stage OrbStack
   run → remove worktree.

Reverify frontend 067b3e2 == smart-cms-app origin/main immediately before the real run; evidence
must bind the explicit SHA, not a pin. Distinctions to maintain: source-landed → independently
reviewed → runtime-accepted → gate-activated (a temporary local false→true→false flip is part of
acceptance; a deployed/persistent gate flip needs separate authorization).
