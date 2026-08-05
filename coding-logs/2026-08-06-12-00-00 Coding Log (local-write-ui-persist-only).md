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
