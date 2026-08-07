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
subset (13 tests) green **3× consecutive**. QCHECK round 2 (second independent round) in flight.

### QCHECK round 2 (independent Codex, second round) — findings, fixes, and residual scope

R0 was reviewed in **two independent rounds, ending with two explicitly accepted residual HIGH
findings** — NOT a clean loop-until-dry pass. Round 2 returned 2 HIGH + 1 LOW; round 3 was not
run (see below). Split by shape:

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

### R0 LANDED (PR #149, squash → c99e06b5); evidence-wording + post-land corrections

- **R0 merged**: PR #149 squash-merged as `c99e06b5`; primary HEAD == main == origin/main ==
  c99e06b5; landed non-destructively (the primary checkout's unrelated dirty state preserved).
- **Review wording (correction):** R0 had **two independent Codex Tier-2 rounds ending with two
  explicitly accepted residual HIGH findings** — NOT a clean loop-until-dry pass; round 3 not run.
- **Evidence wording (correction):** "BFF 367 / ops 189" are **LOCAL green evidence** only. Every
  hosted PR check failed **before execution**: "The job was not started because your account is
  locked due to a billing issue." No hosted CI evidence exists for R0.
- **Branch hygiene:** the squash left the pre-squash R0 commit (2af6e7d) on
  `feat/planning-depth-roster-provenance` (a sibling of c99e06b5). That branch was deleted
  locally and on origin. R1 continues on a fresh branch `fix/local-persist-only-harness-remediation`
  created from origin/main (c99e06b5).
- **Residuals now TRACKED as GitHub issues (not merely documented):**
  - #150 — ROS `dataset_versions.source_hash` immutability. Owner @SubhajL. Exit gate: ROS
    migration/FK making identity immutable + real-PG orphan-prevention test, OR formal acceptance.
    **Sequenced BEFORE the real nine-stage run** and before any external gate flip.
  - #151 — controlled-insert (role-separated) sole write path for planning_depth_submissions.
    Owner @SubhajL. Exit gate: SECURITY-DEFINER procedure + raw-INSERT-denied test, OR formal
    acceptance. May remain outside R1/R2; MUST be resolved/accepted **before any external gate
    flip** (a temporary local false→true→false during acceptance is allowed without it).

## R1 (persist-only / shared-harness) — DREP + Codex round 1 synthesis

R1 DREP written; independent Codex (gpt-5.6-sol xhigh) returned **NO-GO, 5 HIGH** + MEDIUMs.
All dispositioned (accepted); it also corrected one of my errors. Key design change: the
no-side-effect proof now **dynamically digests EVERY base table in ros_gis + scheduler** (21
tables — verified list below), not a hand-picked 4, so no table can be missed.

Full control-plane surface (must be unchanged): ros_gis.{daily_water_requirements, dataset_versions,
gate_mapping_history, section_crop_settings, section_master_history, water_requirement_contributions,
water_requirement_runs}; scheduler.{control_active_gate_authority, control_authority_grant_events,
control_authority_grants, control_command_execution_events, control_command_execution_receipts,
control_command_outbox, control_command_validation_receipts, control_gate_readback_observations,
control_plan_campaign_versions, control_plan_requirements, control_plan_runs,
control_state_transitions, gate_plan_events, section_delivery_ledger}.

Dispositions (ACCEPTED):
- **HIGH-1 inventory incomplete** → digest ALL ros_gis+scheduler base tables (dynamic
  information_schema enumeration; exclude views like sections_current); catches any child/command
  write.
- **HIGH-2 receipt-bound diff not real** → snapshot EVERY W2 row (full projection incl R0
  provenance) and EVERY value tuple (not counts). Assert: entire before-set unchanged;
  after-minus-before == exactly the 2 receipts (submission_ids match; target project/calendar/week;
  S2.supersedes==S1; S1 root) + exactly 82 value rows (41 per submission, canonical section set,
  source_kind, depths from the submitted requests). Bind stored request_sha256 to the receipts;
  the v2 receipt has **no expanded_sha256** (confirmed) so assert the value ROWS directly (stronger
  than a digest).
- **HIGH-3 non-atomic snapshot** → take the whole snapshot in ONE read-only REPEATABLE READ
  transaction (single _psql invocation; SET LOCAL timezone/datestyle for deterministic to_jsonb;
  md5 over to_jsonb(t) ordered).
- **HIGH-4 no RID algorithm** → concrete: persist week = R(n+1) for write-ui R01..R52; R53→R52;
  same ending-year; week_date = canonical span start; reject ending-year outside 1901..2401;
  property-test all supported weeks + endpoints (1900-11-01→persist 1901-R02; 2401-10-31→2401-R52;
  reject 1900-10-31 & 2401-11-01). Plus a **clean-target precondition** (active read 404 before
  arming) so a prior failed attempt is detected.
- **HIGH-5 credential (R1.11)** → NOT closable in R1 (it's run-write-browser.js LOCAL_OPERATOR_*);
  **deferred to R2**. Dropped from R1.
- **MED Redis** → account via redis-cli `--raw -n 2` scan of
  `bff-water-planning:rate:planning_depth.submit:*` with counts+TTL; assert ONLY the operator key
  (+2) changed, no new keys; fail-closed on subprocess/parse error; TTL-aware (don't false-fail on
  an unrelated key expiring). Confirmed: db2, exactly 2 in-window POSTs, redis-cli present.
- **MED auth** → CORRECTION: table IS `refresh_tokens` (refresh-token.entity.js) — my
  "can't-determine-offline" was wrong; but auth is still OUTSIDE the before→after window
  (login precedes before, logout follows after), so no auth snapshot. logout in an OUTER finally
  starting immediately after successful login; test with an INJECTED failure (not AST).
- **MED --as-of-date** → thread through BOTH run_stage AND run_all_stages in orchestrate.
- **SQL executability** → offline unit tests pin logic + query strings; the digest/snapshot SQL is
  validated against a disposable Postgres with ALL (bff+ros+scheduler) migrations during
  implementation, and re-proven in the guest run. Stale CLI frontend-SHA defaults left (fail-closed).

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

---

## R1 IMPLEMENTATION (2026-08-06) — persist-only + shared-harness remediation

Branch `fix/local-persist-only-harness-remediation` off `c99e06b5` (has R0). Files changed:
`ops/control-plan-read-local/{run-stage-suite.py, orchestrate.py, tests/test_stage_suite.py,
tests/test_orchestrate.py}`. Stop line: **N/A — Q0 fired** (fail-closed acceptance gate +
security-adjacent). Claude implemented the whole slice solo, **test-first** per behaviour
(test → RED for the right reason → implement → GREEN), with mutation to establish non-vacuity
where a fresh validator had no independent RED.

### Disposition of the 5 Codex plan-review HIGHs — how each is CLOSED in the code
1. **Incomplete inventory → CLOSED.** `_take_persist_snapshot` now dynamically enumerates EVERY
   base table in `ros_gis` + `scheduler` from `information_schema` (`_persist_only_enumerate_tables`)
   and digests all 21 (7 ros_gis + 14 scheduler, incl. command outbox/events/receipts and
   water_requirement_contributions). `PERSIST_ONLY_EXPECTED_NON_W2_TABLES` (frozenset of 21) is a
   fail-closed floor: enumeration must be a superset or → `persist_only_table_missing`. A newly
   migrated table is auto-included. `water_planning` holds ONLY the 2 planning_depth tables
   (verified across all bff migrations), so "everything else unchanged" is the whole non-W2 set.
2. **Receipt-bound full-row diff → CLOSED.** `validate_persist_only_diff` (keyword-only:
   create_receipt, correct_receipt, target_week_key/date, create/correct_zone_depths) now:
   before-set byte-identical (submissions + values, full `to_jsonb` rows) or
   `persist_only_w2_existing_mutated`; new submission set == exactly the 2 receipt ids; each new
   row bound to its receipt (submission_id, client_submission_id, request_sha256, submitted_by,
   scope, schema_version=2, supersede chain, R0 provenance present+format-valid, expanded_sha256
   format-valid); the two expanded_sha256 must differ; exactly 41 new value rows per new
   submission (82 total), each value bound to its zone's requested depth (defeats the "41 wrong
   values" attack), no value under an unrelated submission_id. v2 receipt has NO expanded_sha256,
   so request_sha256 is bound to the receipt and expanded_sha256 is checked for format + distinctness
   (not reproduced — that would duplicate BFF internals). Mutation-verified: disabling the depth
   bind / the digest compare / the request_sha bind each kills its named test.
3. **Atomic snapshot → CLOSED.** `_build_persist_snapshot_sql` emits ONE statement — a single
   `SELECT json_build_object(...)` over all 21 per-table digests + the two full-row W2 projections —
   so it is one MVCC snapshot. Per-table digest = `md5(coalesce(string_agg(md5(to_jsonb(t)::text),''
   ORDER BY to_jsonb(t)::text),''))`: every column (jsonb-normalized), total order without needing a
   per-table PK, empty table → md5(''). `_persist_snapshot_psql` pins `timezone=UTC` for
   timestamptz determinism. Fail-closed: enumerate/read/parse errors raise; a malformed document
   raises `persist_only_snapshot_malformed` (the old `except: snapshot[key]=[]` fail-open is gone).
4. **Distinct RID week → CLOSED (already, R1 slice 1).** `_persist_only_rid_week` = the write-ui
   successor week (R(n+1); R53→R52), canonical span-start `week_date`, ending-year clamped to
   1901..2401 (else `persist_only_week_out_of_supported_range`). Property test sweeps ~500 years.
5. **Redis accounting + logout → CLOSED.** `_snapshot_planning_depth_rate_keys` reads db2 via one
   atomic `redis-cli --raw EVAL` (key<TAB>value<TAB>pttl triples; loopback-only URL or
   `persist_only_rate_url_invalid`; fail-closed). `validate_persist_only_rate_accounting`: exactly
   ONE namespace key changed, by +2 OR expired-then-reset-to-2 (TTL-aware, no false-fail), matching
   `bff-water-planning:rate:planning_depth.submit:<64hex>`; a vanished persistent key or any other
   change → `persist_only_rate_side_effect_detected`. It identifies the operator key by the +2 delta
   + regex (does NOT reproduce sha256(subject)). Logout: `run_local_persist_only` wraps everything
   after login in try/except → best-effort logout on failure (never masks the primary error), strict
   logout on success (a failed logout fails the stage). Tested with an INJECTED body failure asserting
   logout still ran once + the primary error propagated (behavioural, not AST).

### Shared-harness fixes
- **F6/R1.9 (SHA hard-pin):** removed the `EXPECTED_FRONTEND_SHA` constant ENTIRELY (was a stale
  historical pin). `run_local_base` now calls `_accepted_frontend_sha` = 40-hex format gate only;
  identity is bound by orchestrate (== frontend origin/main) + `_verify_frontend_source` (==guest
  checkout HEAD, run-stage-suite.py L2519-2535). Guest `--frontend-sha` made `required` (killed the
  stale default trap — Codex MEDIUM).
- **F7/R1.10 (frontend v2 env):** `frontend_process_environment` sets `API_SERVER=http://127.0.0.1:3022`
  + `PLANNING_DEPTH_{SUBMIT,ACTIVE,ROSTER}_PATH` when armed, and STRIPS all four when dark (polluted
  parent env cannot pre-arm behind the SUBMIT flag). Values VERIFIED against the real consumer
  (smart-cms-app `app/api/smart-water-backend/water-planning/*/route.ts` — they read exactly these
  vars and fetch `${API_SERVER}${PATH}`) and the real BFF routes (`planning_depths_v2.py` prefix +
  POST/`/active`; `planning_depth_roster.py` prefix + `/v1`). getApiServer() is fail-closed (no
  prod-IP default, unlike the sensor routes).
- **F8/R1.12 (--as-of-date):** threaded through orchestrate `run_stage` AND `run_all_stages` +
  `_parse_args` (ISO-validated in `main`, `as_of_date_not_accepted` on malformed).
- **R1.11 (credential alias):** the persist-only + all API stages already use the canonical
  `operator.env` via `_login_operator` (no `LOCAL_OPERATOR_*`). The only `LOCAL_OPERATOR_*` names are
  in `run-write-browser.js` = the R2 write-UI browser → **DEFERRED to R2** (owns the browser); nothing
  to change in R1. Matches Codex's plan finding.

### Verification
- Ops-harness unit suite: **234 passed, 3× deterministic** (baseline this session 193 → +41 R1 tests).
- Non-vacuity: 3 source mutations (depth-bind / digest-compare / request_sha-bind) each killed only
  the matching test; restored green.
- **Integration proof (real DB, 12/12):** disposable Postgres (postgis:16-3.4, all real bff+ros+
  scheduler migrations → 21 base tables) run through the REAL `_take_persist_snapshot` path:
  enumeration finds ⊇21; single-statement SQL executes; 21 digests; deterministic (two reads
  identical); empty table == md5(''); a non-W2 insert flips exactly that digest; **a real W2
  submit+values leaves ALL 21 non-W2 digests byte-identical** (the core persist-only property PR-7
  never proved); full 15-column W2 projection incl. R0 provenance; values ordered by section_id.
  Probe: scratchpad `persist_r1_integration_probe.py` (not committed). Full guest 9-stage run remains
  DEFERRED (gated on #150) — this is the offline logic + real-schema SQL proof, not the runtime run.
- Lint: my additions ruff-clean; the one ruff finding (`re` unused in test_stage_suite.py) is
  PRE-EXISTING at HEAD (left untouched to keep the PR atomic). Repo is NOT black-managed (HEAD not
  black-clean) → matched surrounding hand-formatting, did not run black.
- Codex Tier-2: **genuinely quota-blocked** (re-tested per standing note; usage limit resets Aug 8).
  Per g2-qcheck fallback, substituted an independent adversarial review agent (uncorrelated Claude
  context). Verdict recorded below.

## Review (2026-08-06) — R1 working tree (independent Tier-2, Codex substitute)

Independent adversarial review (uncorrelated Claude context; Codex quota-blocked). It traced the
implementation, both test files, the RID calendar, the BFF v2 routes/schemas, and migrations
010/011/012. **Verdict: GO** to merge as a test/ops-harness PR (write flags stay disabled, no
runtime run). All five plan-review HIGHs independently confirmed CLOSED in the CODE — it attempted
to construct passing inputs for each receipt-bound attack (41 wrong values, unrelated submission_id,
mutated immutable row, broken supersede chain) and could not; confirmed the v2 receipt actually
returns supersedes/calendar_system/week_date/request_sha256 (so the bind won't false-fail); confirmed
the real limiter always sets a finite TTL (so the vanish branch can't false-fail); confirmed no
fail-open path remains and `main()` converts any unexpected exception to a FAIL manifest.

Findings + disposition:
- **MEDIUM (re-runnability) → FIXED in this PR.** persist-only had no clean-week precheck, so a
  re-run against an already-written week replayed the create POST to 200 and failed with the opaque
  `w2_submission_result_not_accepted` (fail-closed, but misleading; the sibling WRITE-FOUNDATION has
  `validate_w2_week_is_clean`). Added `assert_persist_target_week_clean(before_snapshot, week_key)` —
  raises `persist_only_target_week_not_clean` when a submission already exists in the (mun-bon,
  rid-irrigation-v1, week_key) scope — wired right after the before-snapshot (reuses data already
  captured; no extra query). 2 tests.
- **LOW (redis password on argv) → FIXED in this PR.** `_snapshot_planning_depth_rate_keys` now
  passes `-h/-p/-n` + the password via `REDISCLI_AUTH` env (never argv), mirroring `_psql`'s
  PGPASSWORD; db is selected explicitly and validated numeric. 1 test asserts db-flag + password
  absent from argv + auth in env.
- **LOW (inter-stage rate coupling) → ACCEPTED residual.** The rate key is per operator subject,
  shared across WRITE-FOUNDATION→WRITE-UI→PERSIST-ONLY in one suite run; a very tight limit/window
  could 429 persist-only's 2 submits → false FAIL. Fails closed, runtime-config dependent, not a
  code defect. Recorded, not changed.
- **LOW (rate snapshot namespace-scoped) → ACCEPTED residual.** Only `planning_depth.submit:*` keys
  are enumerated; a submit-path write in another Redis namespace would be invisible. The v2 submit
  path writes no other key today (verified), so this is completeness/defense-in-depth, not a live gap.
- **NIT (client_submission_id reuses WRITE_UI_NAMESPACE; per-zone row-count not asserted) →
  ACCEPTED.** Uniqueness holds via the distinct week_key + drill; `_assert_expanded_values` checks
  total-41 + all-6-zones + per-row depth (roster fan-out is fixed).

Post-fix: **237 unit tests pass, 3× deterministic**; the 3 non-vacuity mutations still hold; the
real-DB integration proof (12/12) is unaffected (snapshot path untouched).

---

## R2 (write-UI browser) — DREP + Opus-5 adversarial synthesis (2026-08-07)

Branch `fix/write-ui-browser-harness-remediation` off `origin/main` (`45bb5433`, has R0+R1).
Scope (user, "your call on scope" → **MINIMAL, like R1**): make `run-write-browser.js` + the
`LOCAL-WRITE-UI-1` stage produce **truthful field-team / outage / logout evidence**. Ops-harness
only; write flags stay DARK; **NO runtime run** (deferred to the 9-stage OrbStack run, gated on
#150). Codex unavailable → independent adversarial plan review by **claude-opus-5 (high)** in
place of gpt-5.6-sol.

### The three untruths being corrected (source spec = R2 plan L163-166 + R10/R11/R14 reframes)
- **Outage:** today induces NO outage, maps `submit_visible:=rosterOk`, asserts
  `reads_preserved:True` (FALSE for planning-depth). Truthful: real scheduler outage (pm2 stop,
  coordination) → roster/active **502** (unavailable) + Submit hidden (DOM) + no successful POST;
  `reads_preserved` REMOVED.
- **Logout:** today validator checks only `redirect_url` is a *string* and emits
  `safe_redirect:True` UNCONDITIONALLY. Truthful: capture real `/api/auth/logout` status +
  `waitForURL(/login)` + prove refresh-token revocation (operator refresh reuse → **401**); logout
  every context.
- **Field-team:** today ABSENT. Truthful: field_team (role literally `field_team`) → BFF **403**
  on roster/active + `ส่งแผน` Submit ABSENT (DOM) + no successful write.

### Opus-5 adversarial review — 2 CRITICAL, 3 HIGH, 4 MED, 3 LOW; ALL dispositioned (accepted)
- **C1 no bearer on raw fetches → 401 not 403/502/201** (proxy `extractBearerToken`→401,
  never forwards cookies; bearer is in-memory, attached only by app `authenticatedFetch`
  client.ts:149-154). FIX: capture `accessToken` from the login response + attach
  `Authorization: Bearer` on happy-path raw fetches; drive the real page for field-team/outage so
  the APP fires roster/active (bearer attached) and OBSERVE via `page.on("response")` + DOM
  assertions. NEW oracle: pure `authorizedRequestInit` bearer test.
- **C2 `LOCAL_OPERATOR_*` alias → throws before login** (R1 deferred this to R2). FIX: browser
  reads `MUNBON_OPERATOR_*`; env-name-completeness test.
- **H3 only primary context monitored** → extract `installRequestBoundary` per-context (primary +
  second + field-team). **H4 field-team submit→403 exceeds spec** → primary gate = Submit-absent +
  roster/active 403 + zero field-team mutations; scripted 403 = optional corroboration. **H5
  redirect race** (client router.push, no middleware gate) → `waitForURL(/login)`.
- **M6 classifier lacks forbidden/phase logic** → extract phase-aware boundary classifier
  `{kind,mutation,forbidden}`, node-test it. **M7 proxy always 502 never 503** → assert 502. **M8
  stale coordination file** → pre-unlink before start + finally. **M9 offline blind to browser
  truthfulness** → PR states the offline gate ≠ deferred-run-passes; add bearer-attachment +
  env-completeness oracles that DO catch C1/C2; do NOT stand up the full stack.
- **L10** `context.request.post(/api/auth/logout)` for status. **L11** `MUNBON_FIELD_TEAM_*`.
  **L12** add outage + field-team screenshots (parity w/ go-read).
- SOUND (confirmed by reviewer): field-team 403 chain, logout revoke-not-delete → refresh 401,
  scheduler outage induction + restored-dark-gate ordering, reads_preserved/safe_redirect targets.

### Change set (ops-harness only; Q0 fires — fail-closed acceptance gate, Claude owns solo)
F1 `run-write-browser.js` (MUNBON creds, capture+attach bearer, per-context boundary, field-team
context, real outage coordination, logout status+waitForURL, screenshots, export pure helpers) ·
F2 `run-stage-suite.py` (`_run_write_browser`→Popen+`pm2 stop/restart scheduler` coordination;
`validate_write_browser_result` rewrite — new outage/logout/field_team shape, drop
reads_preserved/unconditional safe_redirect; operator refresh-reuse→401 proof; field-team env) ·
F3 `seed-local-operators.js` (seed field_team role) · F4 `bootstrap-linux.sh` (field-team.env +
seed) · F5 NEW `tests/test_write_browser_inventory.js` (node --test: boundary classifier +
authorizedRequestInit + validateControlPath) · F6 `tests/test_stage_suite.py` (truthful fixture +
accept/reject + coordination + refresh-reuse injected + mutation) · F7
`tests/test_seed_local_operators.js` (field_team) · F8 docs. Full DREP in scratchpad
`g2-drep-r2-write-ui.md`.

### R2 IMPLEMENTATION (2026-08-07) — truthful write-UI evidence

Branch `fix/write-ui-browser-harness-remediation` off `45bb5433` (has R0+R1), in worktree
`.claude/worktrees/pr6-pr7-remediation`. Stop line: **N/A — Q0 fired** (fail-closed acceptance
gate proving authz denial + outage + token revocation; security-adjacent). **Claude implemented
the whole slice solo — no delegation, 0 delegate fix rounds.** Per g2-coding 2c-ter, solo work
kept the same discipline: test → RED for the right reason → implement → GREEN per behaviour, with
mutation wherever a fresh validator had no independent RED.

**Codex Tier-2 was smoke-tested, not assumed:** `codex exec` returned "You've hit your usage
limit … try again at Aug 8th, 2026 10:56 AM." Per the user's instruction, **claude-opus-5-0**
substituted as the independent Tier-2 reviewer. Independence here is an uncorrelated context, NOT
a different model family — recorded as a real limitation of this round.

#### Ground truth that CORRECTED the DREP (verified at source before coding)
- Proxy auth is header-only (`upstream-guard.ts:66-71`) → the merged happy path, which fetched
  with cookies only, would have returned **401** at create. Broken by construction; never run.
- Every upstream failure collapses to **502** (`upstream-guard.ts:48-58`) — the DREP's
  `{502,503}` was wrong; 503 never reaches the browser.
- Upstream **403 passes through as 403** (`planning-depth-roster/route.ts:79-80`), but a missing
  bearer is **401** — so the field-team context MUST carry a bearer or the denial proof is a
  masquerading auth error.
- Submit receipt is reduced camelCase `{success, submissionId, submittedAt, replayed}`
  (`route.ts:186-193`); the **active** route returns the BFF body VERBATIM in snake_case with 41
  levels (`active/route.ts:158`). Mixing the two conventions is the drift that made PR 6 vacuous.
- `PlanningRhsPanel.tsx:497` renders Submit only when `submitEnabled && policyAllowed &&
  rosterAuthorized` → the control is **ABSENT** (not disabled) for both denial and outage, and the
  two states carry **different banners** (`:517` denial vs `:522` unavailable). This is a STRONGER
  oracle than the DREP specified and closes a false pass where an outage reads as a denial.

#### A FOURTH and FIFTH vacuous claim found during implementation (beyond the three planned)
- `retry_result.client_submission_id_reused` compared two fields the reduced receipt does not
  return — both `None`, always equal, so the check could never fail. **Removed**, not rebuilt
  (capture+byte-identical replay is an explicit R2 Non-Goal, still deferred).
- `conflict_result.detail == "stale_active_submission"` — the proxy returns `{success,error}` and
  has no `detail`, so this would have RAISED at runtime. Reduced to the status assertion.

#### Change set
`run-write-browser.js` (rewritten: MUNBON_* creds, bearer capture+attach, per-context response
boundary, field-team context, real outage coordination, logout+revocation, pure exports) ·
`run-stage-suite.py` (`validate_write_browser_result` rewrite; `_write_browser_environment`;
`_drive_write_browser` Popen + `pm2 stop/restart scheduler`; `_restore_scheduler`;
`_assert_operator_refresh_reuse_rejected` wired into `run_local_write_ui`) ·
`seed-local-operators.js` (`seedLocalUser(roleName)`; field_team seeded with EXACTLY
`["field_team"]`) · `bootstrap-linux.sh` (FIELD_TEAM_PASSWORD + backfill, field-team.env, seeder
sources it) · tests F5/F6/F7 + `tests/test_local_artifacts.py` (**added to the modify list** — its
source-string inventory pinned the old markers; now also asserts the fabrications are ABSENT) ·
docs.

#### Tier 1 (g2-check, self, contract-correctness framing) — 4 findings, ALL FIXED
- **HIGH — `authorizedRequestInit` was an ORPHAN.** Exported and unit-tested but never called at
  runtime (the fetches inlined their own header), so its test was a vacuous guard: the runtime
  could drop the bearer and T13 would still pass. FIXED: inits are now built in Node by
  `authorizedRequestInit` and passed into `page.evaluate`, making the oracle load-bearing.
  Caught by the Phase 4b wiring rule (import ≠ runtime call site).
- **HIGH — tautological logout evidence.** `waitForURL(pathname==="/login")` followed by recording
  `page.url()` made `redirect_url` `/login` BY CONSTRUCTION — a fresh instance of the very
  `safe_redirect: True` defect being deleted. FIXED via `landingPathAfter()`: wait, tolerate the
  timeout, record the REAL landing path; a live session now reports the dashboard and is rejected.
- **HIGH — cross-context observation contamination.** `observed` was keyed by one GLOBAL phase
  while three contexts ran concurrently; a background refetch on the still-open operator page
  during the field-team window could overwrite the 403 that IS the denial proof. FIXED: buckets
  are per-context (`operatorBucket` / `fieldTeamBucket`); the phase no longer flips to field_team.
- **MEDIUM — outage bucket race.** Phase flipped to `outage` before an up-to-180s wait, so a
  pre-outage 200 could seed the bucket. FIXED: the bucket is reset when the release arrives (i.e.
  once the scheduler is actually down).

#### Non-vacuity (mandatory — these validators had no independent RED)
Mutation harness reverted ONE behaviour at a time and required the NAMED test to fail. First run:
**7 of 8 killed, 1 SURVIVED** — `rejects_forbidden_write` set both the count and the list, so the
count check alone satisfied it and the list check was unpinned. That is exactly the merged bug in
miniature (`forbiddenMutations` was never appended to, so the count read 0 forever). Added
`rejects_forbidden_writes_when_count_claims_zero` to pin the list independently → **8/8 killed.**

#### Gates (Claude ran each)
pytest **254 passed** (baseline 237, +17), **3× deterministic** · node --test **17 passed** ·
`ruff check .` **clean** (my `re` usage also retires the pre-existing unused-import finding R1
noted) · `node --check` OK · wiring verified: every new export has a non-test runtime call site.

#### Scope/limitation stated plainly
This is an **offline** gate. It proves the validator, classifier, seed, coordination ordering,
credential completeness, and bearer attachment. It does **NOT** certify that the deferred real
nine-stage OrbStack run will pass — no browser ran. Write flags stay DARK; no runtime run is
claimed. The real run remains gated on issue #150.

**`.gitignore` trap:** `tests/` is ignored wholesale (`.gitignore:288`), so the new
`tests/test_write_browser_inventory.js` needs `git add -f` — the sibling test files are tracked
only because they were force-added the same way. A plain `git add` would have shipped the helpers
with none of their oracles.

#### Tier 1 rounds 2-3 (adversarial/secrets, then merged-artifact) — no further defects
- **Secrets:** `field-team.env` is written at `bootstrap-linux.sh:344`, BEFORE the
  `chmod 600 "${RUNTIME_ENV_DIR}"/*.env` at :349, so it is covered by the existing hardening. The
  only credential-shaped literal is the same generated disposable pattern already used for the
  operator (`L1!$(openssl rand -hex 20)aA`). No literal secret, no non-loopback host in the diff.
- **Sanitizer:** the new `refresh_revoked` / `refresh_reuse_status` / `revoked` manifest keys do
  not collide with `validate_evidence_payload`'s forbidden list (password/authorization/token/
  cookie/secret/dsn/*_url), so the new evidence survives sanitization.
- **Timing seams:** Python's 300s ready-poll vs the browser's 180s release-wait cannot deadlock —
  Python acts within ~0.1s of seeing ready plus <=30s for `pm2 stop`. `_stop_temporary_process` is
  guarded by `poll() is None`, so it is safe on an already-exited process.
- **Restoration under failure:** if `_restore_scheduler` raises, it surfaces (the primary failure
  is retained as its `__context__`), and `run_local_write_ui`'s outer `finally` still restores the
  frontend and BFF flags. The restored dark-gate probe needs the scheduler, so a silent
  failure-to-restore would be caught there too.
- **Repo-answerable risk CHECKED rather than deferred** (g2-qcheck rule): would the app actually
  FIRE roster/active for a denied field-team user, or short-circuit and leave the status `null`?
  Answer: `WaterPlanningWorkspaceV2.tsx:84-88` gates BOTH `useActiveSubmissionQuery` and
  `usePlanningDepthRosterQuery` on `submitEnabled` — the armed FEATURE FLAG, not on any role — so
  both fire for any authenticated user and return the real 403. Both also set `retry: false`, so
  each drill issues exactly one request and the outage produces no retry storm.

#### Tier-2 reviewer round 1 FAILED — recorded, not counted as a pass
The first claude-opus-5-0 Tier-2 agent **stalled** (no progress for 600s; watchdog did not
recover) and produced only "I'll start by getting the full diff." Per g2-qcheck's false-negative
rule, a reviewer that never reviewed is indistinguishable from a clean review and MUST NOT be
recorded as one. Re-launched with the diff pre-materialized to scratchpad so the reviewer spends
its budget reviewing rather than exploring.

#### Tier-2 round 1 (claude-opus-5-0, contract framing) — **NO-GO**, 1 CRITICAL / 2 HIGH / 4 MED / 5 LOW
Every finding dispositioned; silent omission would be a process defect.

- **C1 CRITICAL — ACCEPTED, FIXED (reproduced independently before fixing).** `isForbiddenWrite`
  was called on EVERY response with no `kind === "mutation"` gate — I dropped that filter when
  moving from request- to response-based classification. `POST /api/auth/login -> 200` with
  `writeExpected=false` returned `true`, so all THREE logins were recorded as forbidden writes and
  the validator's non-empty-list check made the stage **permanently red**. Neither suite caught it:
  the node test only fed water-planning paths and the Python fixture hardcodes `forbidden_writes:
  []`. Green tests + impossible runtime is the exact class this PR exists to remove. FIX: the
  product-path gate now lives INSIDE the predicate (`pathname.startsWith(W2_BASE + "/")`) so it
  cannot drift from a caller again; new test covers login/logout/non-product paths.
- **H1 HIGH — ACCEPTED IN PART, FIXED; one sub-claim REFUTED with evidence.** Accepted: roster/
  active statuses were harvested opportunistically from whatever the app happened to fire. FIX:
  added `probePlanningDepthReads()` — explicit roster+active probes in both drills; the passive
  per-context observation is retained only as an `observed_roster_status` cross-check. REFUTED: the
  claim that an outage disables the active query (`weekKey === null`) — `WaterPlanningProvider.tsx:
  155-156` derives `activePeriod` from LOCAL reducer state via `getActivePeriod(state)`, not a
  backend call, so `weekKey` stays non-null, the query stays enabled, returns 502, and the
  unavailable banner renders. Per g2-qcheck, rejecting a finding needs the same evidence standard
  as accepting one.
- **H2 HIGH — ACCEPTED, FIXED.** "Not 2xx" accepted a 409 as proof of denial — but a 409 means the
  field team got PAST authorization to the concurrency check, i.e. was wrongly authorized: exactly
  the regression R7 exists to detect. A 401 (bearer not attached) and a transport failure were
  likewise accepted. FIX: `fetchWithInit` now returns `{status: null, transport_error}` instead of
  a fake `0`, and the validator pins EXACTLY `field_team.submit_status == 403` /
  `outage.submit_status == 502`. Both pins are evidence-backed: the BFF raises **503**
  `scheduler_principal_unavailable` (`planning_depths.py:109-111`) which the proxy collapses to
  502, and **403** for a non-operator (`:119-120`) which passes straight through.
- **M1 MEDIUM — ACCEPTED, FIXED.** `state["scheduler_stopped"] = True` was set AFTER `pm2 stop`
  returned; a stop that exceeds the 30s timeout usually still takes effect, so the restore was
  skipped and every later stage would run against a dead scheduler. FIX: set BEFORE the call
  (`_restore_scheduler` is idempotent). The new test's RED output was literally
  `['browser_spawned', 'browser_ready', 'stop:scheduler']` — no restart.
- **M2 MEDIUM — ACCEPTED, FIXED, and the fix itself needed a second fix.** `reload_result` was a
  duplicate `goto`. Adding `page.reload()` alone would have been WORSE: after the client-side
  redirect the reload would reload `/login`, making the assertion trivially true. FIX: the reload
  path uses `waitUntil: "commit"`, which resolves before hydration runs the redirect, so the reload
  genuinely re-requests the PROTECTED path.
- **M3 MEDIUM — ACCEPTED, FIXED.** The field-team context was closed without logging out. FIX:
  logout before close; `field_team_result.logout_status` is now validated.
- **M4 + L1 — ACCEPTED, FIXED.** The validator checked the banners but dropped them from the
  emitted evidence, and emitted `True`/`0` literals that a preceding check happened to guarantee —
  structurally the same shape as the fabrications being deleted. FIX: every emitted field now
  echoes an OBSERVED value (`submit_absent`, `denied_banner`, `unavailable_banner`,
  `redirect_to_login`, `len(forbidden_writes)`).
- **L2 — ACCEPTED, FIXED.** `assert "safe_redirect" not in body` was VACUOUS: `body` is the JS file
  but `safe_redirect` only ever existed in the Python validator. FIX: assert the emitted dict key
  `"safe_redirect":` is absent from `run-stage-suite.py` (targets emission, not the docstring that
  deliberately names it). Mutation-verified: KILLED.
- **L3 — CLOSED by H1's fix.** The passive bucket is no longer load-bearing.
- **L4 — ACCEPTED as pre-existing.** Hardcoded `EVIDENCE_ROOT` matches the `run-go-read-browser.js:8`
  precedent; not a regression. Recorded, not changed.
- **L5 — NOT TAKEN.** `_reject_unless` raising a bare `ValueError` collapses ~14 reasons into one
  code; debuggability only, no correctness impact. Recorded as a follow-up candidate.

Post-fix: pytest **261 passed** (from 254), node **18 passed**, ruff clean, all **3× deterministic**.
Mutation harness re-run against the changed validator: **10/10 killed** (added pins for
field-team-403 and field-team-logout).

#### Tier-2 round 2 (claude-opus-5-0, merged-artifact/adversarial framing) — **NO-GO**, 1 CRITICAL / 0 HIGH / 4 MED / 4 LOW

- **CRITICAL — ACCEPTED, VERIFIED, FIXED. `WATER_PLANNING_PATH` pointed at a route that has never
  existed.** `app/smart-water/dashboard/` in smart-cms-app contains only `page.tsx`; there is no
  `water-planning` segment. The V2 workspace renders at **`/smart-water/dashboard`** itself
  (`page.tsx:41-45`), which is also where login redirects (`app/login/page.tsx:26,45`). So the
  stage navigated to a 404: `getByRole("button", {name:"ส่งแผน"}).count()` → 0 → the
  `submit_affordance_not_visible` assert throws → the ready file is never written → the Python
  side times out after 300s with `write_browser_ready_timeout`, reporting a timeout rather than a
  routing error. **This path was INHERITED VERBATIM from the merged PR 6** — one more proof that
  stage never ran — and my refactor hoisted it into a constant driving five of the seven evidence
  claims, widening the blast radius. FIX: `/smart-water/dashboard`, plus a runtime guard —
  `readPanelAffordance` now asserts `response.status() === 200` → `water_planning_route_missing`,
  so a wrong route can never again be recorded as "the affordance is correctly absent".
- **MED dead code — ACCEPTED, FIXED.** `_is_successful_write_status` became unreferenced the moment
  the exact-status pins landed, and ruff does not flag unused module-level functions. Leaving it
  would advertise an invariant as enforced in Python when it is enforced only in JS. Deleted.
- **MED restore replaces the diagnosis — ACCEPTED, FIXED.** The failure manifest persists only the
  error CODE, so a failing `_restore_scheduler` overwrote `write_browser_result_not_accepted` with
  `pm2_restart_failed` — the difference between "the evidence was untruthful" and "pm2 hiccuped".
  FIX: raise `f"{primary_code}_and_scheduler_restore_failed"`. New test pins the primary code; its
  RED output was literally `Input: 'pm2_restart_failed'`.
- **MED one-sided banner discriminator — ACCEPTED, FIXED.** The validator asserted only the
  PRESENCE of the expected banner, so the runbook's "the two banners differ" claim was unenforced —
  and `resolvePlanningMutationPolicy` collapses not-requested/loading/unauthenticated/unavailable
  into one `unavailable` state, so an expired session renders the outage banner. FIX: both drills
  report BOTH flags and the validator asserts mutual exclusivity; runbook prose updated to state
  the two-sided rule and that the 403/502 probes carry the primary discrimination.
- **MED source-substring tests — ACCEPTED, FIXED for the reload case.** `assert "page.reload(" in
  body` survives a behavioural revert that leaves the comment intact. FIX: extracted a pure
  `navigationSteps({reload})` that the navigation loop actually consumes, node-tested
  (`["goto"]` vs `["goto","reload"]`); removed the substring assertion.
- **LOW `observed_roster_status` — ACCEPTED, FIXED.** It was the explicit probe echoed back (last
  write wins), not an independent cross-check. Now snapshotted BEFORE the probe.
- **LOW undrained stdout/stderr pipes — ACCEPTED as pre-existing** (identical to the go-read
  precedent at `:3232-3248`). Recorded as a diagnostic hint for the real run: a
  `write_browser_ready_timeout` with no stderr should be suspected here first.
- **LOW EVIDENCE_ROOT coupling / credentials error code — recorded, not changed.**
- Reviewer independently CONFIRMED the round-1 H1 refutation (`getActivePeriod` over local reducer
  state; `createInitialPlanningState` seeds `selectedDate: todayBangkokIso()`, so `weekKey` is
  never null from a backend outage) and confirmed the C1 fix + its test are load-bearing.

#### Own first-contact check this round (not from the reviewer)
The banner constants were the OPENING words of each banner, which are also prefixes of two
`submitErrorLabel` strings (`PlanningRhsPanel.tsx:383,387`) — a transient submit error could have
set the wrong flag, and the two flags are now asserted mutually exclusive. Switched to the
distinctive TAIL of each banner; verified each occurs exactly once in the component and only in
the policy banner (`:517`, `:522`). Login selectors (`input[name="email"]`, `input[name="password"]`,
`button[type="submit"]`) verified present in `app/login/page.tsx:109,133,188`.

Post-round-2: pytest **264 passed**, node **19 passed**, ruff clean, 3× deterministic. Mutation
harness **13/13 killed**.

#### Tier-2 round 3 (claude-opus-5-0, first-contact-realism framing) — **GO**, 0 CRITICAL / 1 HIGH / 2 MED / 3 LOW
The reviewer re-verified the whole first-contact surface against the real frontend and found the
round-1/round-2 defect classes exhausted: login selectors, the post-login landing URL,
`data.accessToken`, the corrected route, the ส่งแผน render condition, the banner strings, and the
41-level pin all check out. It also confirmed the new 200-assert cannot break the outage drill
(`/smart-water/dashboard` is a client page whose SSR output is the AuthGuard spinner, so stopping
the scheduler cannot turn it into a 500).

- **HIGH undeclared third-party dependency — ACCEPTED, VERIFIED, FIXED (more strongly than
  proposed).** `waitUntil: "networkidle"` on a page that unconditionally mounts a Leaflet map
  (`WaterPlanningWorkspaceV2.tsx:134` -> `WaterQualityMap`) fetching tiles/icons from
  `tile.openstreetmap.org`, `server.arcgisonline.com`, and `unpkg.com`. On an isolated guest those
  stall until timeout and abort at the FIRST checkpoint, before any evidence exists; on a connected
  guest the gate silently depends on three public hosts in a stage that is otherwise rigorously
  loopback-pinned. Rather than blocklist three hosts, `installOriginBoundary` now aborts ANY
  off-origin request on ALL THREE contexts (`context.route("**/*")` + `route.abort` — the go-read
  pattern), so the run is genuinely loopback-only. `networkidle` is gone; readiness comes from the
  product's own `draft-action-bar`. Pure `isOffOriginRequest`/`panelReadySteps` exported + node-tested.
  **Own follow-up check:** `draft-action-bar` sits inside a panel that returns null when
  `!activeWeekStatus`, which would have made the new wait hang — but
  `WaterPlanningProvider.tsx:201` derives it from LOCAL reducer state
  (`getWeekDraftStatus(state, weekKey)`), so it renders in all three drill states. Safe.
- **MED weak readback oracle — ACCEPTED, FIXED.** `levels_count == 41` cannot distinguish a correct
  zone->section fan-out from one serving every section a single zone's depth — the repo's OWN
  `validate_w2_active_result` docstring (`:3986-3989`) says exactly this, but that strong check
  covers the DIRECT API path against a different submission. The browser now emits
  `active_readback.distinct_depths` and the validator pins it to the six submitted zone depths.
  Verified against the contract: `PlanningDepthExpandedValue.planning_depth_mm`
  (`planning_depth.py:127`) serializes to float, so the six values survive the round trip.
- **MED `observed_roster_status` half-wired — ACCEPTED, FIXED.** It was captured, carried across the
  process boundary, and discarded unread while a docstring called it a cross-check — the same
  defect class rounds 1-2 deleted. `_reject_passive_contradiction` now raises when the passive
  observation disagrees with the explicit probe (a plausible stale-cache scenario given
  `staleTime: 30_000`), while `None` stays legitimate.
- **LOW reload commit race — ACCEPTED, FIXED.** `commit` is a timing assumption, not a guarantee.
  `landingPathAfter` now returns `{landing, reloaded_from}` so a race that reloads `/login` degrades
  to a visibly weaker proof rather than a silently self-fulfilling one.
- **LOW `getByRole` substring match — ACCEPTED, FIXED** (`{ exact: true }`).
- **LOW banner `data-testid` — NOT TAKEN.** Would require a frontend change, an explicit non-goal.
  Mitigated instead by matching each banner's distinctive TAIL (verified unique).

**Mutation harness caught my own regression:** adding `_reject_passive_contradiction` made two older
tests pass for the WRONG reason (the contradiction fired before the check they named). Their
fixtures were decoupled so each pins its own check. **15/15 killed** after.

Post-round-3: pytest **267 passed**, node **21 passed**, ruff clean, 3× deterministic.

#### Tier-2 round 4 (claude-opus-5-0, regression-of-the-fixes framing) — **NO-GO**, 0 CRITICAL / 1 HIGH / 3 MED / 3 LOW
The round-3 origin-boundary fix and the `distinct_depths` oracle were both confirmed correct
(the reviewer traced `expand_planning_depth_values` and verified the fan-out copies each zone
default verbatim with no area weighting, so `[250.0…300.0]` is exactly right). But the READINESS
half of my networkidle fix had over-corrected.

- **HIGH readiness fired before the app's reads were issued — ACCEPTED, FIXED.** `draft-action-bar`
  renders from LOCAL draft state alone, before `useActiveSubmissionQuery`/`usePlanningDepthRosterQuery`
  are even issued; their placeholder is `not-requested`, which `resolvePlanningMutationPolicy` maps
  to `unavailable` — the OUTAGE banner. Consequences: the healthy drill would see no Submit control
  and die at checkpoint 3; the field-team drill would record the wrong banner and reject a correctly
  denying product; and worst, **the outage drill would PASS for the wrong reason**, recording exactly
  `submit_absent/unavailable_banner` from a panel that had asked nothing. That is new self-fulfilling
  evidence of precisely the class this PR deletes — I swapped a wait that settled the product's reads
  for one that fires before they start. Rendered != settled. FIX: `panelSettledSignals()` returns the
  three TERMINAL markers (node-tested to contain neither `draft-action-bar` nor `networkidle`);
  `readPanelAffordance` arms `waitForResponse` for roster AND active BEFORE navigating, awaits both,
  waits for any terminal signal, then reads — and returns `panel_roster_status`/`panel_active_status`,
  which the validator pins to the drill's explicit probe statuses. A banner can no longer stand in
  for a read. Verified the pin applies ONLY to the field-team/outage drills, so the healthy path's
  legitimate `200 {active:null}` first-submission case cannot false-fail.
- **MED `reloaded_from` captured then discarded — ACCEPTED, FIXED.** My round-3 claim that a lost
  race "degrades to a visibly weaker proof" was false: nothing read the field, so it degraded
  INVISIBLY. Now emitted and rejected unless it equals the protected path.
- **MED `total_mutations` unbounded — ACCEPTED, FIXED.** `forbidden_writes == []` is also what an
  inventory that observed NOTHING produces — the merged stage's defect in a new costume. Now
  requires `>= 5` (the exact number of W2 POSTs the drills issue) and the `.get(..., 0)` default
  is gone.
- **MED route-handler teardown crash — ACCEPTED, FIXED.** Playwright leaves the route handler's
  promise uncaught and rethrows, so an in-flight request during `context.close()` would become an
  unhandled rejection and kill the process BEFORE the evidence was written — losing a completed
  10-minute drill. Handler body wrapped; `closeContext()` does `unrouteAll({ignoreErrors})` first.
  This failure mode did not exist before round 3 added routes.
- **LOW origin normalization — FIXED** (`new URL(frontendOrigin).origin` on both sides; a trailing
  slash would otherwise have aborted 100% of traffic).
- **LOW absent-vs-None passive key — FIXED** via direct subscript. Redundantly enforced (helper +
  emit), so no SINGLE-line mutation can kill it; non-vacuity verified with a COMBINED mutation, and
  the redundant explicit `not in` check was removed rather than left as a line that pins nothing.
- **LOW undrained pipes — ACCEPTED, FIXED.** A genuine regression of my own Popen rewrite: the
  merged code used `_run_checked`, which drains concurrently. stderr now goes to a
  `tempfile.TemporaryFile` spill file, so the healthy phase cannot deadlock on a full buffer.

**Mutation harness caught two more of my own regressions this round** (the new panel-status check
fired before two older tests' named checks, making them pass for the wrong reason); fixtures
decoupled. **18/18 killed.**

Post-round-4: pytest **272 passed**, node **21 passed**, ruff clean, 3× deterministic.

#### Tier-2 round 5 (claude-opus-5-0, regression-of-round-4 framing) — **NO-GO**, 0 CRITICAL / 1 HIGH / 1 MED / 4 LOW

- **HIGH the settle predicate was INERT, and my own test PINNED the defect — ACCEPTED, VERIFIED,
  FIXED.** `panelSettledSignals()` included `UNAVAILABLE_BANNER`, but that banner renders from the
  `not-requested` PLACEHOLDER: `resolvePlanningMutationPolicy` (`mutation-policy.ts:20`) maps every
  non-authorized/forbidden outcome to `unavailable`, `DEFAULT_OUTCOME` is `{kind:"not-requested"}`
  (`PlanningRhsPanel.tsx:597,741`), and the banner is NOT gated on `submitEnabled` (`:520`). So the
  text is present from the first client render in EVERY drill, `signals.some(...)` resolved on its
  first poll, and the gate did nothing. Round 4's HIGH therefore survived: the outage drill could
  still sample placeholder state and pass having asked nothing, while healthy/field-team became
  newly flaky in the fail-closed direction. Worse, the node test I added asserted the signal list
  EQUALS one containing that banner — a passing test pinning the defect. FIX: readiness is no
  longer a DOM signal at all. `installReadRecorder` wraps `window.fetch` via `addInitScript` on all
  three contexts to record the app's OWN planning-depth read completions; `readPanelAffordance`
  waits until both are recorded, then flushes two `requestAnimationFrame`s so React has committed,
  and only then reads the oracles. The defect-pinning test was DELETED (not amended) and replaced
  with `planningReadPaths()`, asserted to contain neither banner nor the container.
- **MED runbook documented the removed readiness model — ACCEPTED, FIXED.** The doc still said
  readiness "is taken from the product's own `draft-action-bar`" while contradicting itself eight
  lines earlier; a future implementer could have reintroduced round 4's HIGH with documentation
  cover. Rewritten to state that readiness is neither network quiescence nor any DOM element, and
  why each candidate fails. Pinned in `test_local_artifacts.py`.
- **LOW "undrained pipes FIXED" was OVERSTATED — ACCEPTED, FIXED.** I had spilled only stderr;
  `stdout=PIPE` remained undrained for the whole healthy phase. Harmless today (the child writes
  stdout only at the end) but any future `console.log` would refill the buffer and reproduce the
  exact misleading `write_browser_ready_timeout` the fix claims to prevent. Both pipes now spill to
  temp files; the test fake writes to the sink rather than returning from `communicate()`.
- **LOW pre-navigation response could satisfy a waiter (outage only) / week-key asymmetry in the
  panel-vs-probe pin / `required()` outside the try — RECORDED, NOT TAKEN.** All three are
  fail-closed and none affects manifest truthfulness; recorded as follow-ups.
- Reviewer independently CONFIRMED: the healthy path's `panel_*` values are not pinned (so the
  legitimate `200 {active:null}` first-submission case cannot false-fail); `unrouteAll` exists in
  the pinned playwright@1.54.2; both hard status pins (403 field-team, 502 outage) are correct
  against the real stack; no secrets, all hosts loopback.

Post-round-5: pytest **272 passed**, node **21 passed**, ruff clean, 3× deterministic, mutations
all killed.

#### Tier-2 round 6 (claude-opus-5-0, regression-of-round-5 framing) — **GO**, 0 CRITICAL / 0 HIGH / 2 MED / 5 LOW
First round with no high-severity finding. The reviewer traced the round-5 fix to ground truth and
confirmed it works: `authenticatedFetch` -> `fetchImpl`, whose default is the unqualified global
`fetch` evaluated at `createAuthClient()` call time (`client.ts:52`, called with no argument at
`auth-context.tsx:53`) — i.e. AFTER the init script, so the wrapper is captured. No axios, no XHR,
no captured-before-wrap reference. `addInitScript` is on the CONTEXT and Playwright re-runs it on
every navigation including the reload. Both reads are issued in all three drills (their `enabled`
gates resolve to build-time/local constants, not network state).

- **MED-1 headers-vs-body, and my comment claimed a guarantee it did not provide — ACCEPTED,
  FIXED.** The recorder wrote at `await original(...)` resolution, i.e. EXACTLY headers-received —
  the same moment `waitForResponse` fires. It added provenance, not timing, and my comment said
  otherwise. FIX: `await response.clone().arrayBuffer()` before recording, so a read registers only
  once its body has arrived (the app cannot derive policy from a body it has not read); the comment
  now states the two conditions honestly, says the rAF flush is a HEURISTIC, and records that the
  banners are therefore CORROBORATION while `panel_*_status` + the 403/502 probes are probative.
- **MED-2 the replacement observation path had ZERO coverage — ACCEPTED, FIXED.** Round 5's defect
  was caught by a node test; round 5's fix deleted that test and shipped an untested mechanism.
  FIX: extracted the pure `recordPlanningRead(reads, url, status, paths, origin)`, injected into the
  page via `new Function(recordPlanningRead.toString())` so the UNIT-TESTED function is the code that
  actually runs (no second copy — CLAUDE.md MUST NOT #3). Four assertions: query strings ignored,
  off-path traffic (incl. `/api/auth/login`) not recorded, relative URLs resolved, malformed URL
  never throws. **Mutation-verified 3/3**: dropping the path filter, keying by full URL, and
  removing the try/catch each kill the test. The three subsumed banner asserts were deleted (they
  could not fail independently of the deepEqual).
- **LOW-1 inverted timeout ladder — FIXED** (`waitForFunction` 20s -> 35s, now >= the 30s waiters).
- **LOW-2 recorder nonce / LOW-3 field-team 403 at the scheduler boundary / LOW-4 access-token TTL
  across the 180s outage park / LOW-5 unpkg subtree — RECORDED as #150 run-plan items, not taken.**
  All fail-closed; each could cost a guest run, none can fabricate a pass.

**Own follow-up (post-packet, disclosed):** verified smart-cms-app sets NO CSP anywhere (no header
config, no middleware, no `script-src`), so the `new Function` injection is safe. Added a
`read_recorder_not_installed` assert so that if a strict CSP is ever introduced, the failure is
immediate and precise instead of an opaque 35s timeout. This one-line defensive assert landed
AFTER the round-7 review packet was materialized — disclosed here rather than left as silent drift.

Post-round-6: pytest **272 passed**, node **23 passed**, ruff clean, 3× deterministic; validator
mutations all killed; recorder mutations 3/3 killed.

#### Tier-2 round 7 (claude-opus-5-0, final dryness) — **NO-GO -> GO**, 0 CRITICAL / 1 HIGH / 0 MED / 5 LOW

- **HIGH the whole test file was GITIGNORED and would not have been committed — ACCEPTED, VERIFIED,
  FIXED.** I had spotted the `tests/` blanket ignore early and planned `git add -f`, which was an
  UNDER-fix: `-f` leaves the path ignored, so any future file added there silently drops out again.
  The blast radius was also larger than I had stated — `test_write_browser_inventory.js` is **11 of
  23** node tests, including the entire round-6 MED-2 remediation and the only oracles for all 8
  exported browser functions. `git add -An` confirmed it was invisible to a normal `git add -A`, so
  the ordinary flow would have merged an untested observation path with no signal at all, while the
  author's machine stayed green. FIX: a negation block in `.gitignore` mirroring the existing
  `!services/auth/tests/` precedent, so the directory is genuinely tracked.
  **Verified by artifact, not reasoning:** `git archive HEAD` extracted to a temp dir runs
  **23 node tests and 272 pytest** in a clean tree.
- **LOW-1 the body-before-record ordering had no oracle — FIXED.** Added
  `await response.clone().arrayBuffer()` and `recordPlanningRead` to the declared source-substring
  fallback in `test_local_artifacts.py` (this tree's stated mechanism for behaviour a pure test
  cannot reach).
- **LOW-3 the clone applied to EVERY response — FIXED.** Now path-gated, so the instrumentation
  touches only the two planning-depth reads instead of the product's whole network surface.
- **LOW-5 test description over-promised — FIXED.** Renamed to state exactly what the final assert
  verifies (repo Writing-Tests rule 3).
- **LOW-2 eval-free init-script refactor / LOW-4 ready-deadline derived from the JS timeouts —
  RECORDED, NOT TAKEN.** Both fail-closed. Verified independently that smart-cms-app sets NO CSP,
  so the `new Function` injection works today; a `read_recorder_not_installed` assert now makes a
  future CSP fail immediately and precisely rather than as an opaque 35s timeout.
- Reviewer independently confirmed clean: no secrets, all hosts loopback, no new self-fulfilling
  evidence or fail-open path, the round-6 MED fixes behaviourally correct, and every frontend
  precondition the readiness predicate depends on.

### R2 REVIEW SUMMARY (7 rounds)
Cumulative: **2 CRITICAL, 5 HIGH, 13 MEDIUM, ~20 LOW.** All CRITICAL/HIGH/MEDIUM fixed; LOWs either
fixed or recorded with reasons. **Three of the defects were introduced by my own fixes to earlier
findings** (a tautological logout redirect, an inert settle predicate whose test pinned the defect,
and a headers-vs-body comment claiming a guarantee the code lacked) — the loop-until-dry discipline,
not any single review, is what caught them. The mutation harness independently caught three further
cases where a new check made an OLDER test pass for the wrong reason.

**Reviewer-independence caveat, recorded honestly:** every round was claude-opus-5-0 substituting
for Codex, which was smoke-tested and genuinely quota-blocked (resets Aug 8 10:56). That is an
uncorrelated CONTEXT, not a different model family. A real Codex round is recommended before the
nine-stage run.

### Final gates
pytest **272**, node --test **23**, ruff clean, **3× deterministic**; validator mutations all
killed; recorder mutations 3/3 killed; clean-checkout verification passed.
