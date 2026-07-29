# LOCAL-WRITE-FOUNDATION-1 — runtime correctness + re-runnability

Created: 2026-07-29 +07
Baseline: `origin/main` at `7f8b8a84`

## Context

PR #142 landed the LOCAL-WRITE-FOUNDATION-1 stage. A post-merge trace of the
real BFF write path (`services/planning_depth_submission.py`,
`db/planning_depth_repository.py`) found three defects that make the stage
unable to pass, and unable to be re-run.

## Findings this PR fixes

### F1 — Zone area_ids are not the canonical roster (blocker)

`_build_planning_depth_request` emitted `zone-upper-1`, `zone-mid-1`, … but
`validate_planning_depth_roster` requires the zone `area_id`s to equal the
roster zone set, which `_zone_id()` derives as `01-{n:02d}` → `01-01`…`01-06`.
Result: `unknown_area` → **422** on the create drill. The stage could never
reach 201.

This was raised by Tier-2 (Codex) on PR #142 as HIGH and wrongly deferred as a
"runtime integration concern". The IDs are deterministic and verifiable in-repo,
so it was a hard blocker, not an environment question.

### F2 — The stage was single-shot per database

`create_planning_depth_submission` returns a **replay (200)** when the
`client_submission_id` already exists with the same submitter and
`request_sha256`. With hardcoded client ids and a hardcoded week, the second
ever run of the stage returns 200 where the drill demands 201, permanently,
until the database is rebuilt.

Subtlety: the client-id lookup is **globally scoped**
(`WHERE client_submission_id = $1`, no project/week filter), and `week_key` is
part of the canonicalised document. So changing *only* the week turns the
failure from a 200 replay into a 409 `client_submission_id_conflict`. The week
and the client ids must co-vary. Both are now derived.

### F3 — A dirty target week failed late and opaquely

With F2 fixed the stage still cannot create into a week that already holds an
active submission. Previously that surfaced as "expected 201, got 200" four
drills deep. It now fails before the write flag is touched at all, with
`write_foundation_week_not_clean`.

## Non-findings (verified, deliberately unchanged)

- **No past-week validation exists** anywhere in the service or repository, so a
  stale Monday does not rot on its own. The week derivation is for
  re-runnability, not for avoiding an expiry.
- **`planning_depth_mm` must stay a JSON number.** `_planning_depth_decimal`
  rejects strings outright (`not isinstance(value, (int, float, Decimal))`).
  Floats are safe here: `Decimal(str(value))` then a numeric-equality quantize
  check. Do not "harden" these into strings.
- **Rate limit is 10 per 300s**; the stage performs 3 writes.

## Stop line

Q0 fired — the standing user directive (2026-07-17) retires delegation to
DeepSeek and it has not been re-ratified. **Claude implements the whole slice.**
Phase 2c-ter therefore applies in full: per unit of behaviour, test → RED →
implement → GREEN. No seams were written ahead of tests.

## Test strategy

F1's original bug was a fake encoding a wrong interface assumption — the test
and the builder shared the same invented field vocabulary, so the suite was
green while the code could not work. The replacement test pins the builder
against the roster the harness itself seeds, deriving the expected zone set from
`seed-approved-sources._zone_for_section` over the real section range rather
than restating a literal.

Week-derivation expectations are independently pre-computed (including the
2026-W53 ISO-year boundary), never taken from the function under test.

## QCHECK

Implementer: Claude (whole slice). Tier 2 was **mandatory** — the change is
entirely about fidelity to the BFF replay/conflict contract.

- **Tier 1a** — Opus agent, contract fidelity vs the real service. All four
  fidelity claims PASS. 6 findings (0 CRITICAL/HIGH).
- **Tier 1b** — Opus agent, logic + test quality. 7 findings, **2 HIGH**.
- **Tier 2** — Codex `gpt-5.6-sol`, `model_reasoning_effort=xhigh`. 0
  CRITICAL/HIGH/MEDIUM, 1 LOW. Independently corroborated Tier 1b's HIGH-2.

### Dispositions — all findings fixed

| # | Finding | Sev | Disposition |
|---|---|---|---|
| 1b-F1 | ISO-year test was vacuous (2027-01-01 snaps to a Monday whose calendar year already equals its ISO year); the test that did catch it was unstaged | HIGH | **fixed** — staged the `2025-12-29 → 2026-W01` test and renamed the weaker one to what it actually covers |
| 1b-F2 | Orchestrator had no behavioural coverage; removing the flag-restoration `finally` broke nothing | HIGH | **fixed** — extracted `run_write_foundation_drills` with injected collaborators; mutation now kills the named test |
| 1a-F1 | Dark-gate drill inserts a real submission if the flag was left armed, poisoning the week permanently | MEDIUM | **fixed** — `validate_write_flag_is_dark` asserts darkness *before* the probe |
| 1a-F2 | Conflict drill accepted any 409, incl. the `client_submission_id_conflict` this PR's derivation prevents | MEDIUM | **fixed** — pins `stale_active_submission` |
| 1a-F3 | Active drill checked only the count; a collapsed zone fan-out still returns 41 | MEDIUM | **fixed** — per-zone depth + `source_kind` + `source_area_id` oracle |
| 1a-F4 / 1b-F3 | Every non-404 precheck reported as "week not clean" (incl. DB outage) | MEDIUM | **fixed** — `write_foundation_week_precheck_failed` is distinct; 404 detail pinned |
| 1b-F4 | The zone-id test's independence comment overclaimed | MEDIUM | **fixed** — comment now states it pins the section→zone mapping only |
| 1b-F5 | `no-store` branch untested on the w2 validators | MEDIUM | **fixed** — added for clean/not-found/active/conflict |
| 1a-F6 / 1b-F6 | `week_key` derived twice; `validate_w2_week_is_clean` duplicated `validate_w2_not_found_result` | LOW | **fixed** — builder takes `week_key`; shared `_require_absent_active_submission` |
| 1a-F5 / 1b-F7 | Failure carried no remedy | LOW | **fixed** — remedy in the docstring |
| T2-LOW | `inspect.getsource` substring tests are gameable | LOW | **fixed** — same fix as 1b-F2, plus AST call-node counting |

### Mutation evidence (Phase 2c-bis)

Layers written before their tests were proven non-vacuous by reverting one
behaviour at a time and confirming the **named** test fails:

- derived week → hardcoded literal ⇒ `…derives_week_and_ids…` fails
- cleanliness check moved after arming ⇒ `…clean_check_runs_before…` fails
- `iso_year` → `monday.year` ⇒ `…iso_year_ahead_of_calendar_year` fails
  (notably the 2026-W53 test does **not** — which is what exposed 1b-F1)
- `try/finally` → straight-line ⇒ `…restore_the_dark_flag_when_a_drill_fails` fails
- precheck reference kept but non-gating ⇒ `…never_arm_writes_when_the_week_is_dirty` fails

### Verified unchanged

No evidence-manifest `steps` key was dropped by the extraction (added:
`w2_week_clean`, `target_week`); `validate_evidence_payload` accepts the new step
shapes; `write_stage_manifest` dumps with `sort_keys=True`, so reordering
`migration_010` ahead of `w2_dark_flag_gate` cannot perturb the checksum.

## QCHECK round 2 (re-run of both raising tiers)

Both HIGHs independently confirmed **FIXED** by mutation. Round 2 raised four
more, all fixed:

| # | Finding | Sev | Disposition |
|---|---|---|---|
| R2-1 | The dark guard read `bff.env` (intended state). `_restart_bff_with_flag` writes the file *before* the pm2 restart, so a failed disarm leaves the file dark while the process stays armed — the next run's dark-gate POST then persists a submission. Raised independently by **both** tiers. | HIGH | **fixed** — the gate drills now POST `_build_dark_probe_request`, a schema-valid but roster-invalid body. The flag gate precedes roster validation, so it yields 503 when dark and 422 `unknown_area` (before the limiter, before any INSERT) if armed. The file check is retained as a fast early signal, no longer as the safety mechanism. |
| R2-2 | `run_write_foundation_drills` had **no happy-path coverage** — deleting the whole restored-gate drill, or accepting 200 for create, or dropping the replay-id guard, all left the suite green | MEDIUM | **fixed** — happy-path + three targeted tests; all three mutants now killed |
| R2-3 | Active validation still accepted a collapsed fan-out: 41 rows all relabelled into one zone are individually self-consistent | MEDIUM | **fixed** — whole-set zone coverage plus `section_id` must encode its own zone |
| R2-4 | Fakes were correct but unpinned; dead `_drill_kwargs` params; one test name over-claimed; 404 detail not test-pinned | LOW | **fixed** — signature/field pin against `LocalHttpClient.request` and `HttpResult`, dead params removed, test now asserts arming order, wrong-detail case added |

R2-1 is the same class as the defect this PR set out to fix, one level deeper:
round 1 asserted darkness before probing, but asserted the *file*; round 2 made
the probe itself incapable of writing.

### Round-2 mutation evidence

- delete the restored-gate drill ⇒ `…prove_the_gate_is_dark_again_after_disarming` fails
- create `expected_status` 201 → 200 ⇒ `…reject_a_replay_where_a_fresh_create_is_required` fails
- delete the replay-id guard ⇒ `…reject_a_replay_of_a_different_submission` fails

Final: **162 tests, green 3x**, compile clean, every new export wired to a
runtime call site.
