# Coding Log — Path 3 → Path 1 → Path 2 → Path 4

- Created: 2026-08-20T17:17:55+07:00
- Worktree: `/Users/subhajlimanond/dev/munbon2-backend-path3-write-act-rc`
- Initial branch: `docs/path3-promotion-table-truth`
- Initial base: `origin/main` `5e70508ec0e39b9a5a0f6f4efa7fd65aa289aa60`
- Protected existing worktrees: roster v1, RID v2, write-UI logout transport, write-UI race
- Runtime boundary: no guest/database campaign, AWS, deployment, activation, credential, or production action is authorized by this source lifecycle.

## Clarified contract

Execute four sequential source lifecycles, one PR at a time:

1. Path 3: correct only the stale promotion table, then perform only the explicitly authorized merged-branch and exact temporary-environment cleanup after read-only safety checks. Never touch either named guest.
2. Path 1 / PR 8: source-implement `LOCAL-WRITE-ACT-1` with activation, fault drills, 15-minute stability, rollback, immutable-history proof, and final dark state. Do not execute it against a guest.
3. Path 2 / PR 9: source-implement `LOCAL-RC-1` as an exact-identity clean-run wrapper and RC-specific evidence contract. Do not provision or run it without a new runtime grant.
4. Path 4: merge a documentation-only handoff that stops at the AWS boundary. Inventory, promotion, deployment, activation, post-deployment verification, and rollback execution require new authority.

The genuine 2026-08-20 campaign remains historical nine-stage 9/9 evidence. It does not prove WRITE-ACT or RC. Schema-v1 ledger validation must continue to interpret its bytes against the frozen nine-stage roster.

# Plan Draft A — extend the live progressive campaign

## Overview

Correct the runbook truth first, then append `LOCAL-WRITE-ACT-1` as the tenth live progressive stage while freezing the schema-v1 ledger roster at nine stages. Add `LOCAL-RC-1` as a separate clean-run controller that invokes all ten stages and emits RC-only evidence.

## Files to change

- `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`: Path 3 table truth; later WRITE-ACT/RC source contracts and final AWS handoff.
- `ops/control-plan-read-local/tests/test_local_artifacts.py`: scoped runbook regression and static wiring contracts.
- `ops/control-plan-read-local/orchestrate.py`: frozen ledger-v1 order, live tenth stage, stage timeout, collectors, RC CLI/controller/evidence.
- `ops/control-plan-read-local/run-stage-suite.py`: WRITE-ACT stage plus RC preflight/finalize phases.
- `ops/control-plan-read-local/tests/test_stage_suite.py`: guest-stage RED contracts.
- `ops/control-plan-read-local/tests/test_orchestrate.py`: host/controller/collector RED contracts.
- `.github/workflows/control-plane-hardening-tests.yml`: inspect only; edit only if existing path/test wiring is disproved.

## Implementation steps

1. Path 3 TDD: add a section-scoped static test, confirm RED on stale failed/unreached cells, correct exactly two table cells, run focused/full harness tests.
2. PR 8 TDD slice A: RED for frozen `CAMPAIGN_LEDGER_V1_STAGE_ORDER` and live ten-stage parity; implement constants and collector compatibility.
3. PR 8 TDD slice B: RED for distinct WRITE-ACT RID scope and browser artifact; parameterize existing helpers.
4. PR 8 TDD slice C: RED for activation ordering, fault drills, stability, immutable history, rollback, and containment; implement `run_local_write_activation()`.
5. Wire parser, dispatch, host timeout, strict inventories, runbook, and static checks; run scoped tests three times and full gates.
6. PR 9 TDD slice A: RED for `run-rc` arguments, exact identities, guest shape/ID, clean destinations, order, first-failure stop, and no retry/repair/reprovision.
7. PR 9 TDD slice B: RED for guest RC preflight/finalize, clean DB/evidence/rate/command state, all-ten completion, final dark/listener/readiness proof.
8. Implement RC collectors and RC-specific index formats; explicitly reject them from campaign-ledger promotion.
9. Path 4: document merged source identities and runtime-unexecuted state; run static tests.

## Test coverage

- `test_promotion_table_records_current_nine_stage_success`: scoped table matches ledger truth.
- `test_campaign_ledger_v1_uses_frozen_nine_stage_order`: historical rows remain valid.
- `test_stage_order_places_write_activation_after_persist_only`: exact tenth-stage dependency.
- `test_write_activation_requires_clean_distinct_rid_scope`: avoids predecessor collisions.
- `test_write_activation_arms_backend_before_frontend`: fixed activation order.
- `test_write_activation_fault_drills_leave_zero_partial_rows`: Redis/DB failures fail closed.
- `test_write_activation_retries_429_once_with_same_client_id`: bounded idempotent retry.
- `test_write_activation_stability_requires_31_ordered_samples`: 900-second sampled invariant.
- `test_write_activation_rolls_back_frontend_before_backend`: fixed safe rollback order.
- `test_write_activation_rollback_preserves_active_read`: immutable read remains available.
- `test_write_activation_failure_manifest_records_containment`: primary error plus dark proof.
- `test_run_rc_orders_preflight_ten_stages_finalize_collect`: complete clean-run sequence.
- `test_run_rc_stops_without_retry_repair_or_reprovision`: first defect terminates.
- `test_rc_collector_rejects_identity_or_inventory_drift`: exact artifact contract.
- `test_campaign_ledger_rejects_rc_outer_index`: RC cannot masquerade as 9/9.

## Decision completeness

- Goal: source-deliver truthful Path 3, safe WRITE-ACT, clean RC, and an AWS-boundary handoff.
- Non-goals: actual guest/database campaigns, guest deletion, AWS inventory, deployment, activation, credentials, production verification, migrations, or frontend repair without a proven source defect.
- Success: each PR is locally gated, QCHECK/g-check clean, merged to `origin/main`, exact merge SHA landed on local `main`; final session worktree removed.
- Public interfaces: add `LOCAL-WRITE-ACT-1` to `run-stage --stage`; add `run-rc`, `collect-rc`, and `collect-rc-partial-failure`; add `LOCAL-WRITE-ACT-1.json`, `LOCAL-RC-1.json`, `RC-SUMMARY.json`, and RC checksum indexes. No endpoint, env-var, DB schema, or migration change.
- Failure mode: fail closed. If BFF cannot be proven dark, stop it and require its listener absent. Preserve primary failure and containment failure separately. RC never retries or repairs.
- Rollout/backout: source stays dark and runtime-unexecuted. Revert the source PR before any authorized use; after runtime begins, preserve evidence/guest and obtain recovery authority.
- Observability: sanitized readiness/PM2/listener/restart/flag samples only; no secrets or raw environments.

## Dependencies and validation

- Python 3.11 gate environment, existing offline dependency contract, and Smart CMS exact SHA at runtime.
- Commands: focused pytest per slice; all three harness test files; Black check; Ruff; compileall; Node syntax check; `git diff --check`; affected tests three consecutive times.
- Runtime commands are templates only until separately authorized.

## Wiring verification

| Component | Entry point | Registration | Schema/contract |
|---|---|---|---|
| `LOCAL-WRITE-ACT-1` | host `run-stage`/`run-all` | host and guest `STAGE_ORDER`, parser, dispatch | stage manifest + `SHA256SUMS` |
| WRITE-ACT browser evidence | `_run_write_browser()` | stage-specific artifact argument | sanitized browser JSON |
| WRITE-ACT collector | `collect`/`collect-partial-failure` | strict expected inventory | ten manifests + two browser artifacts |
| `LOCAL-RC-1` | host `run-rc` | host parser/action dispatch; internal guest RC phases | RC manifest/summary/index |
| RC recovery | `collect-rc*` | host parser/action dispatch | RC complete/partial inventories |
| Ledger compatibility | `validate_campaign_ledger()` | frozen schema-v1 stage roster | unchanged ledger JSONL bytes |

# Plan Draft B — keep WRITE-ACT entirely post-campaign

## Overview

Leave both live `STAGE_ORDER` constants and the current strict campaign collector unchanged. Implement WRITE-ACT as a separate post-nine-stage action that consumes a prior 9/9 outer digest, then implement RC as another independent controller/evidence family.

## Files and TDD sequence

Use the same files, but add new `run-write-act`/`collect-write-act` actions instead of extending `run-stage`/`run-all`. Write RED host action/identity tests, RED guest post-campaign precondition tests, implement separate evidence schemas, then add RC over the nine-stage runner plus post-campaign WRITE-ACT.

## Test coverage

- `test_write_act_binds_exact_base_nine_stage_outer_digest`: no historical substitution.
- `test_write_act_rejects_candidate_identity_drift`: exact source binding.
- `test_write_act_does_not_change_campaign_stage_order`: historical and live roster unchanged.
- All activation, fault, stability, rollback, immutable-history, and RC tests from Draft A.

## Decision completeness

- Public surface adds more commands and evidence types but minimizes semantic change to campaign collection.
- Failure remains fail-closed; no migrations or runtime authority.
- Success requires separate validation of base 9/9 and post-campaign evidence.

## Trade-offs

- Strength: strongest preservation of the existing nine-stage campaign model.
- Weakness: duplicates lifecycle state/collection semantics, creates more operator commands, and makes a future clean RC compose two incompatible runners rather than one exact progressive order.

## Wiring verification

| Component | Entry point | Registration | Schema/contract |
|---|---|---|---|
| post-campaign WRITE-ACT | `run-write-act` | new host and guest action paths | separate WRITE-ACT outer index |
| RC | `run-rc` | new host and guest action paths | RC manifest/summary/index |
| campaign | existing `run-all` | unchanged nine-stage registries | unchanged 9/9 inventory |

# Comparative analysis

- Draft A reuses the established stage transition, state, failure-manifest, parser, and strict collection machinery; its mandatory frozen ledger-v1 roster preserves historical evidence.
- Draft B isolates semantics most strongly but duplicates authority, state, collection, and recovery surfaces and complicates the requirement that RC execute the complete ordered lifecycle without repair.
- Both preserve the AWS/runtime stop line and require the same defect-sensitive activation tests.
- Draft A has fewer moving parts and a clearer future operator flow, provided historical schemas are explicitly versioned and regression-tested.

# Unified Execution Plan

Adopt Draft A with two safeguards from Draft B: name the frozen nine-stage roster explicitly as `CAMPAIGN_LEDGER_V1_STAGE_ORDER`, and version all new WRITE-ACT/RC evidence schemas so historical archives are never re-finalized or reinterpreted.

## PR boundaries and exact order

1. Path 3 PR: only the runbook table and its scoped static regression test.
2. After merge/landing, delete only the three proven merged local/remote `ops/9of9-*` branches and exact inactive temp environment. Preserve all guests and evidence.
3. PR 8: live tenth-stage WRITE-ACT source, tests, runbook; no runtime execution.
4. PR 9: RC wrapper/evidence source, tests, runbook; no runtime execution.
5. Path 4 docs PR: exact merged identities and explicit runtime/AWS stop.

## Path 3 exact contract

- Change `LOCAL-WRITE-UI-1` status from latest failed to implemented/latest campaign passed.
- Change `LOCAL-PERSIST-ONLY-1` status from not reached to implemented/latest campaign passed.
- Keep `LOCAL-WRITE-ACT-1` planned and `LOCAL-RC-1` required/unpassed.
- Scope the regression test to the promotion table so historical failure prose cannot mask stale cells.
- Cleanup preconditions: each branch tip and remote tip is an ancestor of refreshed `origin/main`, zero unique commits, not checked out; temp realpath exact, directory/non-symlink/current-user-owned, roughly 338 MB, no open process/cwd/reference.

## PR 8 functions

- `run_local_write_activation(context)`: execute dark → backend armed → frontend armed → failure drills → 900-second stability → frontend dark → backend dark, preserving immutable history and containment.
- `_write_activation_rid_week(as_of_date)`: produce a canonical scope distinct from UI/persist-only, including R52/R53 boundaries.
- `_project_control_surface(...)`: map existing actual flags/process/listener state to logical dark invariants without serializing secrets.
- `_observe_write_activation_stability(...)`: collect 31 monotonic samples through 900 seconds with injectable clock/sleep.
- `_validate_write_activation_history(...)`: allow only exact browser create/correction rows, 41 values each, correct supersession, no command/authority/execution/producer writes.
- Parameterize existing browser artifact helpers; do not copy the browser algorithm.

Required drills/assertions:

- Redis unavailable → exact 503, zero rows.
- DB transaction unavailable → exact 503, zero partial rows.
- 429 → one bounded `Retry-After` retry using the same client ID and no duplicate root.
- Field-team 403 never becomes conflict/retry behavior.
- Browser-originated roster, active, submit, correction, conflict, reconciliation, logout requests are observed.
- After rollback, active GET returns exact expected submission/hash/value count while POST is disabled.
- Scheduler restored; temporary listener absent; unexpected restart counts unchanged; all flags false.

## PR 9 functions

- `run_rc(args)`: validate exact origin-main identities/archive/guest, run preflight, all ten stages, finalize, atomic collection; stop after first failure.
- `_validate_rc_guest_identity(...)`: require unique fixed running Debian/ARM64 guest with expected immutable ID; never mutate guest inventory.
- `run_local_rc_preflight(context)`: prove empty evidence/W2/rate/actionable-command state, clean sources/migrations, dark flags, accepted listeners, and no repair.
- `run_local_rc_finalize(context)`: require all ten checksummed PASS artifacts and final dark/readiness/listener/immutable-history proof.
- `finalize_rc_collection(...)` / partial counterpart: exact inventory, atomic destination, RC-only outer index, no campaign acceptance semantics.

## Edge cases and failure rules

- Any source, archive, date, guest ID/shape, owner, or destination drift fails before stage dispatch.
- Existing W2/rate/actionable command state fails RC preflight; no cleanup is attempted.
- Any stage failure stops dispatch and collects exact completed prefix/failure evidence when authorized.
- Interrupts preserve state and propagate without inventing PASS/FAIL.
- Missing/duplicate/non-monotonic stability samples fail WRITE-ACT.
- Containment failure blocks every later stage and preserves both diagnoses.
- Old nine-stage archives remain valid historical objects but fail the new live ten-stage collector if re-submitted.

## Acceptance commands

Use the repository’s pinned Python 3.11 environment. Run each separately and record exact results:

1. `python -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py`
2. `python -m pytest -q ops/control-plan-read-local/tests/test_orchestrate.py`
3. `python -m pytest -q ops/control-plan-read-local/tests/test_local_artifacts.py`
4. `python -m black --check <changed Python files>`
5. `python -m ruff check <changed Python files>`
6. `python -m compileall -q ops/control-plan-read-local`
7. `node --check ops/control-plan-read-local/run-write-browser.js`
8. `git diff --check`
9. Repeat affected pytest scope three consecutive times.

## Decision-complete checklist

- Goal/non-goals/success criteria locked: yes.
- Public CLI/evidence surfaces named consistently: yes.
- Every behavior has a defect-sensitive test: yes.
- Validation commands scoped and explicit: yes.
- Wiring table covers every new component: yes.
- Rollout/backout and dark failure behavior specified: yes.
- DB migrations: none.
- Open implementation decisions: none. A proven frontend source defect triggers a stop and separately scoped frontend PR rather than silent expansion.

## Worktree ledger

- Session-created: `/Users/subhajlimanond/dev/munbon2-backend-path3-write-act-rc`; branch `docs/path3-promotion-table-truth`; purpose Path 3 then sequential PR 8/9/Path 4; remove after all requested source lifecycles land.
- Pre-existing and protected: `/Users/subhajlimanond/dev/munbon2-backend-pr3-roster-v1`, `/Users/subhajlimanond/dev/munbon2-backend-pr4-rid-v2`, `/Users/subhajlimanond/dev/munbon2-backend-write-ui-logout-transport`, `/Users/subhajlimanond/dev/munbon2-backend-wui`.

## Work unit 1 — Path 3 promotion-table truth (2026-08-20T17:22:00+07:00)

- Goal: make the current promotion table agree with the checksum-bound successful 9/9 campaign without rewriting historical failure sections or claiming WRITE-ACT/RC completion.
- Files changed: `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md` (two status cells) and `ops/control-plan-read-local/tests/test_local_artifacts.py` (section-scoped structured table assertion), plus this required Coding Log and pointer.
- RED: `/tmp/munbon-9of9-gate.jd0ldB/venv/bin/python -m pytest -q ops/control-plan-read-local/tests/test_local_artifacts.py::test_all_stages_runbook_locks_local_before_aws_and_documents_current_commands` failed with only two mismatches: WRITE-UI `latest run failed` and PERSIST-ONLY `latest run not reached` versus expected `latest campaign passed`.
- GREEN: the same command passed `1 passed` after changing exactly those two cells.
- Relevant suite: `.../python -m pytest -q ops/control-plan-read-local/tests/test_local_artifacts.py` passed `43 passed`.
- Full harness gate: `.../python -m pytest -q test_stage_suite.py test_orchestrate.py test_local_artifacts.py` passed `492 passed`.
- Formatter: pinned 9/9 environment lacked Black; system `python3 -m black --check ops/control-plan-read-local/tests/test_local_artifacts.py` passed with Black 26.3.1.
- Lint: `python3 -m ruff check ops/control-plan-read-local/tests/test_local_artifacts.py` passed with Ruff 0.8.6.
- Whitespace: `CODEX_ALLOW_LARGE_OUTPUT=1 git diff --check` passed.
- Runtime wiring: the test reads the tracked runbook directly, extracts only `## Promotion sequence` through `## Provision`, parses each unique three-cell `LOCAL-*` row, and locks the full current status mapping. Historical result prose cannot mask a stale promotion cell.
- Behavior/risk: documentation-only truth correction; no guest, database, evidence archive, ledger, workflow, runtime, or AWS mutation. WRITE-ACT remains planned and RC remains required/unpassed.
- Follow-up: complete three-run stability, QCHECK/formal g-check, PR lifecycle, and exact-SHA landing before branch/temp cleanup.

## Review (2026-08-20T17:24:51+07:00) - working-tree

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend-path3-write-act-rc`
- Branch: `docs/path3-promotion-table-truth`
- Scope: staged working tree at base `5e70508ec0e39b9a5a0f6f4efa7fd65aa289aa60`; RepoPrompt snapshot `2026-08-20/1721`
- Commands Run: staged diff inventory/artifacts, focused RED/GREEN, 492-test harness gate, three consecutive 43-test runs, Black, Ruff, and diff check

### Findings
CRITICAL
- None.

HIGH
- None.

MEDIUM
- `ops/control-plan-read-local/tests/test_local_artifacts.py`: the dictionary comprehension collapses duplicate stage keys with last-write-wins semantics. A stale WRITE-UI or PERSIST-ONLY row followed by a correct duplicate could pass; row order and malformed extra-column rows were not locked. Replace it with an exact ordered row list, assert one promotion section, require exactly three cells for every `LOCAL-*` row, and reject additional rows.

LOW
- None.

### Open Questions / Assumptions
- None. The runbook change itself is truthful and preserves historical failure prose and all WRITE-ACT/RC/AWS authority boundaries.

### Recommended Tests / Validation
- Add duplicate/order/shape-sensitive parsing, rerun the focused static test, full harness, Black, Ruff, diff check, and affected scope three consecutive times.

### Rollout Notes
- Changes requested before commit. No runtime rollout or operational action is part of this review.

### Primary disposition
- Accepted. Remediate the parser and repeat formal g-check because the reviewed test surface materially changes.

## Work unit 1 review remediation (2026-08-20T17:26:00+07:00)

- Replaced last-write-wins dictionary parsing with an exact ordered `(stage, status)` row list.
- Added uniqueness assertions for the promotion and provision section delimiters.
- At this intermediate revision, every canonical column-zero table row containing a backticked `LOCAL-*` gate had to contain exactly three cells; the second formal review correctly identified equivalent Markdown forms it still ignored.
- This is review-driven test hardening over an already-correct runbook, so no new production RED was legitimate; the earlier RED still proves the two-cell behavior change. The new focused test passed.
- Revalidation: full harness `492 passed`; Black and Ruff passed; diff check passed; affected file passed three consecutive runs at `43 passed` each.
- Formal finding disposition: resolved; repeat formal g-check required before commit.

## Review (2026-08-20T17:29:58+07:00) - working-tree recheck

### Reviewed
- Repo/branch: `/Users/subhajlimanond/dev/munbon2-backend-path3-write-act-rc`, `docs/path3-promotion-table-truth`
- Scope: remediated staged snapshot `2026-08-20/1726`
- Commands Run: RepoPrompt staged snapshot/review plus previously recorded local gates

### Findings
CRITICAL
- None.

HIGH
- None.

MEDIUM
- None.

LOW
- Test-strength gap: exact column-zero pipe and heading strings can ignore indented pipe rows, unbackticked `LOCAL-*` rows, normalized-equivalent duplicate headings, or surplus backticks. Such rendered/pipe-like duplicates could coexist with the expected canonical rows.

### Open Questions / Assumptions
- None. The runbook cells and authority boundaries remain correct.

### Recommended Tests / Validation
- Normalize level-two headings, inspect every pipe-like `LOCAL-*` row in the scoped section regardless of indentation/backticks, require one exact canonical row form, then rerun all prior gates.

### Rollout Notes
- Changes requested before commit; no operational rollout.

### Primary disposition
- Accepted. Strengthen the parser again, correct the earlier overbroad claim, and repeat formal g-check.

## Work unit 1 second review remediation (2026-08-20T17:32:00+07:00)

- Normalized all level-two headings with 0–3 leading spaces, optional trailing hashes, and surrounding whitespace; require exactly one `Promotion sequence` and one later `Provision` heading.
- Inspect every pipe-like line containing `LOCAL-` in the scoped section after removing indentation for classification.
- Require the whole line to match one canonical three-cell Markdown row with one backticked `LOCAL-[A-Z0-9-]+` stage and no extra pipe cells. Indented duplicates, unbackticked rows, surplus backticks, malformed rows, reordered/missing/unexpected rows, and normalized-equivalent duplicate headings now fail.
- Black reformatted the test after the first check correctly reported formatting drift; the check then passed. Ruff and diff check passed.
- Focused static test passed; full harness passed `492`; affected file passed three consecutive runs at `43 passed` each.
- Second formal finding disposition: resolved; repeat formal g-check required.

## Review (2026-08-20T17:38:00+07:00) - final working-tree recheck

### Reviewed
- Repo/branch: `/Users/subhajlimanond/dev/munbon2-backend-path3-write-act-rc`, `docs/path3-promotion-table-truth`
- Scope: staged snapshot `2026-08-20/1731`
- Commands Run: RepoPrompt staged snapshot/final review plus primary-run 492-test, Black, Ruff, diff-check, and three-run evidence

### Findings
CRITICAL
- None.

HIGH
- None.

MEDIUM
- None.

LOW
- A valid GFM row without a leading pipe would not be selected by the canonical-row parser.
- A second Setext or inline-formatted heading could evade the normalized ATX-heading uniqueness check.

### Open Questions / Assumptions
- None affecting current correctness. The tracked runbook uses canonical leading-pipe tables and ATX headings, and the exact staged patch contains neither variant.

### Recommended Tests / Validation
- Optional future Markdown-lint/parser hardening if the repository begins accepting multiple equivalent Markdown syntaxes for lifecycle tables.

### Rollout Notes
- No blocking correctness or authority-boundary findings. Source remains documentation/static-test only.

### Primary disposition
- Accepted as non-blocking LOW hardening. The test intentionally locks the repository's canonical leading-pipe ATX table format; the exact staged ordered rows prove the current runbook cannot retain either stale cell in that contract. No current defect or authority expansion remains.
