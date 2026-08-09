# Coding Log: WRITE-UI diagnostics and ROS runtime parity

Created: 2026-08-09 22:14:30 +07:00

## Exploration basis

Auggie semantic search was unavailable through a safely bounded two-second tool call, so this plan uses direct inspection and exact-string searches. Inspected:

- `CLAUDE.md`, `CONTEXT.md`, and `services/ros-gis-integration/CLAUDE.md`
- `ops/control-plan-read-local/run-stage-suite.py`
- `ops/control-plan-read-local/orchestrate.py`
- `ops/control-plan-read-local/bootstrap-linux.sh`
- `ops/control-plan-read-local/tests/test_stage_suite.py`
- `ops/control-plan-read-local/tests/test_local_artifacts.py`
- `ops/control-plan-read-runtime/run-ros.sh`
- `ops/control-plan-read-runtime/tests/test_runtime_artifacts.py`
- `services/ros-gis-integration/migrations/0004_dataset_version_identity_immutable.up.sql`
- `services/ros-gis-integration/tests/integration/test_dataset_version_immutability_postgres.py`
- `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`
- GitHub issue #159 and the frozen guest evidence for backend `0228f495...`

The primary checkout's two untracked Coding Log pointer backups and the existing `munbon2-backend-wui`, `munbon2-backend-pr3-roster-v1`, and `munbon2-backend-pr4-rid-v2` worktrees are protected and out of cleanup scope.

## Plan Draft A — structured diagnostics and runtime proof

### Overview

Preserve the failed `0228f495...` acceptance attempt, then make WRITE-UI failures self-diagnosing without retaining secrets: checksum the failure manifest, save the sanitizer-approved browser result before validation, and attach all failing predicate codes. Add an explicit non-acceptance diagnostic mode that runs only on a disposable guest/database and never advances `stage-state.json`; land this as PR A, use it to identify the live mismatch, then land issue #159 as PR B with migration-registry and trigger-existence proof.

### Files to change

- `coding-logs/evidence/2026-08-09-nine-stage-orbstack-0228f495/**`: frozen seven-stage/failure bundle and outer checksums.
- `ops/control-plan-read-local/run-stage-suite.py`: predicate diagnostics, rejected-result artifact, failure checksumming, and explicit diagnostic mode.
- `ops/control-plan-read-local/tests/test_stage_suite.py`: unit tests for multi-failure enumeration, sanitization, checksums, and non-acceptance state isolation.
- `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`: diagnostic-lane contract and truthful 7/9 boundary.
- `ops/control-plan-read-runtime/run-ros.sh`: apply ROS migration 0004 after 0003.
- `ops/control-plan-read-runtime/tests/test_runtime_artifacts.py`: lock the complete ordered runtime migration sequence.
- `ops/control-plan-read-local/run-stage-suite.py`: raise ROS parity to 0004 and assert exact immutable trigger names.
- `ops/control-plan-read-local/tests/test_stage_suite.py`: parity and trigger-presence tests.

### Implementation steps

1. PR A RED: add tests proving two independent bad browser fields yield two stable predicate codes, unsafe raw results are never persisted, safe rejected results and failure manifests are checksummed, and diagnostic mode cannot update acceptance stage state.
2. Run the targeted tests and record the expected failures.
3. Implement the smallest validator refactor: evaluate named predicates from one source of truth, attach only allowlisted codes to `StageGateError`, persist only a sanitizer-approved browser result, checksum failure artifacts, and add `--diagnostic` restricted to `LOCAL-WRITE-UI-1` with a non-default evidence root.
4. Keep acceptance behavior fail closed: any failed predicate still produces stage FAIL; diagnostic success produces `DIAGNOSTIC_PASS` only and never writes `stage-state.json` or an acceptance PASS manifest.
5. Run formatter, targeted tests three times, the full local harness suite, shell/static gates, wiring checks, independent QCHECK, formal `g-check`, PR, merge, and exact merged-SHA post-merge tests.
6. Clone the frozen OrbStack guest to a disposable diagnostic machine. Update only the clone to PR A's merged SHA, choose a fresh unsubmitted RID week via `--as-of-date`, run diagnostic mode with a separate evidence root, replay/inspect the saved JSON, and record every failed predicate. Do not alter the frozen guest or its evidence.
7. PR B RED: update runtime-artifact and RTA parity tests to require 0004 and exact triggers; confirm they fail on the old wrapper/parity implementation.
8. Implement ordered 0004 apply, exact four-migration parity, and a real PostgreSQL catalog assertion for `dataset_versions_identity_is_immutable` and `dataset_versions_no_truncate`.
9. Run targeted tests three times, the ROS integration test against a disposable PostgreSQL database, full relevant gates, QCHECK, formal `g-check`, PR, merge, and exact merged-SHA verification.
10. Apply/verify 0004 on the disposable acceptance clone and query the real catalog to prove both triggers exist. Close #159 through the merged PR.

Major function behavior:

- `validate_write_browser_result(body)`: remains the sole acceptance decision point and returns the existing sanitized projection only when no predicate fails.
- `collect_write_browser_predicate_codes(body)`: evaluates all named acceptance predicates independently and returns a stable, allowlisted tuple; it contains no raw values.
- `_persist_write_browser_result(context, body)`: applies `validate_evidence_payload`, atomically writes the browser result, and indexes it in `SHA256SUMS` before acceptance validation.
- `run_local_write_ui(context, diagnostic=False)`: shares the live drill and restoration path; diagnostic mode skips acceptance prerequisites/state writes and emits an explicitly non-acceptance manifest under a separate evidence root.
- `validate_ros_dataset_version_triggers(names)`: requires the exact non-internal trigger set installed by 0004.

### Test coverage

- `test_validate_write_browser_result_reports_every_failed_predicate`: reports all independent validator disagreements.
- `test_validate_write_browser_result_never_reports_raw_values`: failure metadata contains codes only.
- `test_drive_write_browser_checksums_safe_result_before_rejection`: retains replayable sanitized evidence.
- `test_drive_write_browser_rejects_unsafe_result_without_persisting`: prevents secret-bearing result artifacts.
- `test_write_ui_failure_manifest_is_checksummed_with_predicate_codes`: freezes complete failure evidence.
- `test_write_ui_diagnostic_requires_separate_evidence_root`: protects canonical acceptance evidence.
- `test_write_ui_diagnostic_never_advances_stage_state`: prevents diagnostic evidence becoming acceptance proof.
- `test_ros_wrapper_applies_every_tracked_migration_in_order`: runtime installs 0001 through 0004.
- `test_validate_migration_parity_requires_ros_0004`: RTA fails closed on an omitted tail.
- `test_validate_ros_dataset_version_triggers_requires_exact_0004_set`: catalog proof cannot be vacuous.
- Existing PostgreSQL immutability integration suite: update/delete/truncate remain rejected.

### Decision completeness

- Goal: preserve the failed attempt, diagnose every WRITE-UI disagreement safely in isolation, and activate #150's 0004 protection in the acceptance runtime.
- Non-goals: no final nine-stage acceptance claim, no stage 9 claim, no production/AWS activation, no frontend product change, no cleanup of existing worktrees, no mutation of the frozen guest.
- Success criteria: archive hashes verify; diagnostic mode cannot touch canonical stage state; a disposable run retains a sanitizer-approved browser result and enumerates all failing predicates; PR A and PR B merge; runtime parity reports four ROS migrations; real PostgreSQL contains both 0004 triggers; all flags/restoration remain dark.
- Public interfaces: one local runner CLI flag `--diagnostic`; no API, message, or product schema change. PR B activates an already-landed DB migration, not new DDL.
- Failure modes: unsafe browser output fails closed and is not stored; malformed output yields allowlisted codes; checksum failure prevents evidence from being called complete; diagnostic mode on the default evidence root rejects; missing/extra ROS migration or trigger rejects RTA.
- Rollout/backout: PR A changes harness evidence only and stays dark; PR B sequentially applies idempotent migration 0004. Backout is code rollback while leaving 0004 applied, because removing audit-integrity triggers is not a safe automatic rollback.
- Acceptance checks: targeted pytest commands, three-run reliability loop, full harness tests, `bash -n`, disposable PostgreSQL integration, real clone catalog query, and dark/listener restoration checks.

### Dependencies

- Running OrbStack guest `munbon-control-plan-local` for cloning only after archive verification.
- Canonical frontend SHA `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`.
- Disposable PostgreSQL/OrbStack clone; no production credentials or AWS actions.

### Validation

- `python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py`
- `python3 -m pytest -q ops/control-plan-read-runtime/tests/test_runtime_artifacts.py`
- `bash -n ops/control-plan-read-runtime/run-ros.sh`
- `DATASET_VERSION_TEST_POSTGRES_URL=<disposable-loopback-db> pytest -q services/ros-gis-integration/tests/integration/test_dataset_version_immutability_postgres.py`
- `shasum -a 256 -c coding-logs/evidence/2026-08-09-nine-stage-orbstack-0228f495/SHA256SUMS`
- Disposable clone diagnostic command with a non-default evidence root, followed by checksum/replay and dark restoration verification.

### Wiring verification

| Component | Entry point | Registration location | Schema/table |
|---|---|---|---|
| Predicate diagnostics | `validate_write_browser_result()` | `_drive_write_browser()` | N/A |
| Browser-result artifact | `_drive_write_browser()` after JSON parse | `_checksum_manifest()` | N/A |
| WRITE-UI diagnostic mode | runner CLI `LOCAL-WRITE-UI-1 --diagnostic` | `_parse_args()` and `main()` | existing planning-depth tables on disposable DB only |
| Failure checksum/codes | `main()` exception path | `write_stage_manifest()` then `_checksum_manifest()` | N/A |
| Migration 0004 runtime apply | `run-ros.sh` startup and `_apply_migrations()` | PM2 runtime wrapper and LOCAL-RTA-1 | `ros_gis.dataset_versions`, `ros_gis.schema_migrations` |
| Trigger catalog proof | `_apply_migrations()` | `run_local_rta()` migration step | `pg_trigger`, `ros_gis.dataset_versions` |

## Plan Draft B — minimal raw capture, manual diagnostics

### Overview

Make the smallest observability change: save the sanitized browser JSON before calling the unchanged generic validator, checksum failures, and use an ad hoc clone command to replay the artifact. Then apply migration 0004 and update parity without a trigger catalog assertion.

### Files to change

- Same frozen evidence archive.
- `run-stage-suite.py` and its tests for raw capture/checksums only.
- `run-ros.sh`, parity constants, and their existing tests for 0004.
- Acceptance runbook documentation.

### Implementation steps

1. RED tests for saved rejected JSON and checksummed failure manifest.
2. Persist sanitizer-approved browser JSON before the unchanged validator.
3. Clone the guest manually, patch runner arguments on the clone, and replay with an import snippet.
4. RED/GREEN the four-migration wrapper/parity update.
5. Run standard gates and land sequential PRs.

### Test coverage

- `test_drive_write_browser_retains_sanitized_rejected_result`: replay artifact survives.
- `test_failure_manifest_is_checksummed`: failure is archive-bound.
- Existing validator tests: acceptance behavior remains unchanged.
- Runtime wrapper/parity tests: 0004 is present.

### Decision completeness

- Goal and non-goals match Draft A.
- Success criteria are weaker: diagnosis depends on manual replay and runtime proof depends on registry rows plus the separate integration suite.
- Public interfaces: no new CLI; migration activation only.
- Failure modes: raw artifact sanitizer fails closed; manual clone mistakes are operator risk.
- Rollout/backout: same dark harness and forward-only integrity migration policy.
- Acceptance checks: targeted tests, manual replay, migration status, separate integration test.

### Dependencies

- Operator-authored clone commands and Python import snippets.
- Disposable DB for migration behavior.

### Validation

- Same source tests, checksum validation, and PostgreSQL integration suite as Draft A, without a supported diagnostic CLI or catalog assertion.

### Wiring verification

| Component | Entry point | Registration location | Schema/table |
|---|---|---|---|
| Raw browser artifact | `_drive_write_browser()` | before `validate_write_browser_result()` | N/A |
| Migration 0004 | runtime wrapper/RTA | existing ordered apply sequence | `ros_gis.dataset_versions` |

## Comparative analysis

Draft A is safer and repeatable: it prevents diagnostics from contaminating acceptance state, enumerates all predicate mismatches without duplicating raw values, and proves the triggers exist in the actual RTA database. It adds a small CLI surface and requires a careful single-source validator refactor.

Draft B has fewer code changes and lower immediate refactor risk, but it leaves diagnosis dependent on manual patching/import commands, cannot guarantee all mismatches are found in one replay, and treats migration registry presence as a proxy for installed triggers. Those gaps conflict with the user's explicit requirements to identify every failing predicate and verify real acceptance triggers.

Both retain fail-closed semantics, dark defaults, TDD, separate PRs, and no production activation. Draft A better satisfies evidence integrity and repeatability.

## Unified Execution Plan

Use Draft A, with two constraints from Draft B: keep the diagnostic CLI scoped to the existing runner rather than adding a new script, and preserve the existing accepted projection/behavior exactly. Deliver in two sequential PRs.

### Overview

PR A archives the current failure and adds safe, checksummed, multi-predicate diagnostics plus an acceptance-isolated WRITE-UI mode. After landing, use it on an OrbStack clone with a fresh week to identify the actual mismatch. PR B then closes #159 by activating migration 0004 in both runtime paths, raising parity, and proving the two immutable triggers exist in the real disposable acceptance PostgreSQL database.

### Files to change

- PR A: frozen archive, `ops/control-plan-read-local/run-stage-suite.py`, `ops/control-plan-read-local/tests/test_stage_suite.py`, acceptance runbook.
- PR B: `ops/control-plan-read-runtime/run-ros.sh`, runtime tests, `ops/control-plan-read-local/run-stage-suite.py`, stage-suite tests, acceptance runbook.

### TDD sequence

For each PR: scaffold the narrow callable/flag, add named failing tests, run and record RED, implement the smallest GREEN change, minimally refactor only the validator structure needed for one source of truth, run formatter and focused gates, run tests three times, run full relevant suites, verify wiring, QCHECK, formal staged `g-check`, remediate, commit, PR, required-check disposition, admin merge, local-main landing, and exact merged-SHA verification.

### Test coverage

Use the Draft A test list. Every behavior change has a defect-sensitive test; malformed, multiple-failure, unsafe-output, default-evidence-root, missing-migration, extra/missing-trigger, and restoration boundaries fail closed.

### Decision completeness

- Goal: all of items 1–4 complete with truthful evidence and merged source.
- Non-goals: stages 8/9 acceptance completion, AWS/production, frontend changes, old worktree cleanup.
- Measurable success: verified archive; exact predicate list from clone; two merged PRs; #159 closed; four registered ROS migrations; exact trigger set in real PostgreSQL; dark flags and no armed listener after diagnostics.
- Interfaces: `--diagnostic` is local-ops-only; no user API change; existing migration 0004 becomes active.
- Failure policy: all integrity and evidence checks fail closed; raw unsafe data is discarded; restoration still runs and is recorded.
- Rollout/backout: use disposable clone first; no change to frozen guest. Migration remains forward-applied on rollback of source because weakening immutable provenance is unsafe.
- Monitoring: observe failure predicate codes, checksum status, scheduler restoration, PM2/readiness, write flag, listener 9999, migration registry, and trigger catalog.
- Acceptance checks: exact commands listed above plus Git/GitHub SHA equality after each merge.

### Dependencies

OrbStack clone capability, the existing local guest, local GitHub access, and a disposable local PostgreSQL database. No additional packages or secrets are introduced.

### Wiring verification

| Component | Entry point | Registration location | Schema/table |
|---|---|---|---|
| Predicate collector | `validate_write_browser_result()` | same module and call path | N/A |
| Safe browser artifact | browser subprocess JSON completion | `_drive_write_browser()` | N/A |
| Diagnostic lane | runner CLI | `_parse_args()` -> `main()` -> `run_local_write_ui()` | planning-depth tables in cloned DB |
| Failure evidence | runner exception path | `main()` | N/A |
| Runtime migration 0004 | ROS PM2 start and RTA provisioning | `run-ros.sh`, `_apply_migrations()` | `ros_gis.dataset_versions` |
| Trigger verification | RTA migration step | `_apply_migrations()` | `pg_trigger`, `ros_gis.dataset_versions` |

## Decision-complete checklist

- No implementation decisions remain open.
- All changed local CLI, evidence, migration, and operational surfaces are named.
- Every behavior change has a defect-sensitive test.
- Validation commands are scoped and concrete.
- Runtime entry points, registrations, and schema objects are mapped.
- Rollout is disposable-first, dark, and preserves the frozen guest.
- PRs are sequential and independently landed from refreshed `origin/main`.

## Implementation summary (2026-08-09 22:35 +07:00) — PR A

### Goal

Preserve the `0228f495...` 7/9 failure and make subsequent WRITE-UI failures safely replayable and multi-predicate-diagnostic without allowing a diagnostic run to become acceptance evidence.

### Changes by file

- `coding-logs/evidence/2026-08-09-nine-stage-orbstack-0228f495/**`: copied the live guest bundle before any rebuild, added the missing outer hash coverage for the failure manifest/log, and recorded the restored dark final state.
- `ops/control-plan-read-local/run-stage-suite.py`: named every WRITE-UI acceptance predicate, retained all failed codes on the generic stage error, persisted sanitizer-approved browser JSON before validation, checksum-indexed browser/failure artifacts, removed cleared failure entries from the checksum index, preserved predicate codes when restoration also fails, and added clone-only `--diagnostic` mode.
- `ops/control-plan-read-local/tests/test_stage_suite.py`: added defect-sensitive tests for multi-failure enumeration, safe/unsafe result persistence, ordering, failure checksums, diagnostic state isolation, canonical-machine rejection, and combined restoration failures.
- `ops/control-plan-read-local/tests/test_local_artifacts.py`: raised the source lock to cover the browser-result and failure checksum call sites.
- `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`: recorded the truthful 7/9 status and documented the disposable diagnostic contract.

### TDD evidence

RED command:

`python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py -k 'reports_every_failed_predicate or persist_write_browser_result or failure_manifest_is_checksummed_with_predicate_codes or parse_args_rejects_diagnostic or parse_args_accepts_write_ui_diagnostic or diagnostic_manifest_never_advances'`

RED result: 6 failed, 1 passed. Failures were the intended missing predicate metadata, persistence callable, failure checksum/codes, diagnostic flag, and diagnostic manifest behavior.

Additional RED commands:

- `python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py::test_clear_failure_manifest_removes_only_the_completed_stage` — failed because the removed manifest's stale checksum entry remained.
- `python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py::test_accept_write_browser_output_persists_before_predicate_rejection` — failed because the ordered parse/persist/validate helper did not exist.
- `python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py::test_write_ui_diagnostic_rejects_canonical_acceptance_machine` — failed because machine-level isolation was not enforced.
- `python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py::test_run_write_browser_keeps_the_primary_diagnosis_when_restore_also_fails` — failed because the combined restoration error dropped predicate metadata.

GREEN commands:

- `python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py` — 270 passed at the first full-suite green point.
- `python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py ops/control-plan-read-local/tests/test_local_artifacts.py` — 282 passed after source-lock/runbook updates.
- `for i in 1 2 3; do python3 -m pytest -q ops/control-plan-read-local/tests || exit 1; done` — 331 passed on each of three consecutive runs before the final isolation/combined-error hardening.

### Wiring verification

| Component | Production call site | Registration | Evidence |
|---|---|---|---|
| `collect_write_browser_predicate_codes` | `validate_write_browser_result` | same harness module | accepted projection remains downstream only on zero failures |
| `_persist_write_browser_result` | `_accept_write_browser_output` | `_drive_write_browser` subprocess completion path | persistence occurs before validator rejection and updates `SHA256SUMS` |
| `_write_local_write_ui_manifest` | `run_local_write_ui` | acceptance and diagnostic completion paths | diagnostic omits `_save_state`; acceptance retains it |
| `_verify_write_ui_diagnostic_isolation` | `run_local_write_ui(diagnostic=True)` | `main` dispatch from `--diagnostic` | rejects canonical machine/root and roots containing stage state |
| failure predicate/checksum projection | `main` exception path | all stage failures | codes are fixed-format strings; manifest is written then checksummed |

### Behavior and risk notes

- Acceptance remains fail closed under the same generic `write_browser_result_not_accepted` gate.
- Diagnostic evidence is explicitly labeled non-acceptance and cannot run on the canonical guest.
- Unsafe browser output fails before persistence.
- Failure cleanup now removes its checksum entry, preventing a later successful archive from referencing a deleted file.
- No product API, frontend, AWS, or production behavior changed.

### Remaining before PR A delivery

- Re-run final three-pass gates after the last hardening edits.
- Complete independent QCHECK and formal staged `g-check`; remediate findings.
- Commit, create PR, handle required checks, admin merge, land local main, and verify exact merged SHA.
- Run the merged diagnostic candidate on a disposable OrbStack clone and record the actual predicate mismatch list.

### Final pre-review hardening and gates

Two additional evidence-integrity RED/GREEN cycles were completed after the first three-run gate:

- `test_run_local_write_ui_clears_stale_browser_result_before_new_drill` failed because a later malformed/early-failing attempt could retain the prior checksum-valid browser JSON; the run now removes the old file and checksum entry after acceptance prerequisites validate and before the new drill.
- `test_write_ui_diagnostic_clears_prior_pass_before_new_attempt` failed because a later diagnostic failure could coexist with a prior `DIAGNOSTIC_PASS`; a new diagnostic attempt now removes the old pass and checksum before source validation.
- `test_write_ui_diagnostic_rejects_canonical_acceptance_machine` locks clone-only execution in addition to separate evidence-root isolation.
- `test_run_write_browser_keeps_the_primary_diagnosis_when_restore_also_fails` now proves the combined restore failure retains all browser predicate codes.

Final reliability command:

`for i in 1 2 3; do python3 -m pytest -q ops/control-plan-read-local/tests || exit 1; done`

Final result: 334 passed on each of three consecutive runs.

Other passing gates:

- `python3 -m black --check ops/control-plan-read-local/run-stage-suite.py ops/control-plan-read-local/tests/test_stage_suite.py ops/control-plan-read-local/tests/test_local_artifacts.py`
- `python3 -m py_compile ops/control-plan-read-local/run-stage-suite.py ops/control-plan-read-local/orchestrate.py`
- `node --check ops/control-plan-read-local/run-write-browser.js`
- `git diff --check`
- both the outer archive and guest-owned `SHA256SUMS` verification commands

### Independent QCHECK

The independent review first found the combined-restoration predicate-code loss and stale-attempt evidence risks. After TDD remediation and recheck, it reported no remaining P0–P2 findings. Residual boundary: source/evidence review only; the live disposable OrbStack diagnostic run remains the post-merge operational step.

## Review (2026-08-09 22:32:29 +0700) - working-tree

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-write-ui-observability`
- Branch: `fix/write-ui-failure-observability`
- Scope: staged working tree against `origin/main` `0228f495b7708b92cc7526f201687eb5b1441565`
- Commands Run: staged status/stat and targeted diff inspection; `git diff --staged --check`; three consecutive full local harness test runs; Black check; Python/Node syntax checks; nested and outer SHA256 verification; sanitizer replay across all archived JSON files.

### Findings

CRITICAL

- No findings.

HIGH

- No findings.

MEDIUM

- No findings. The earlier stale-browser-result, stale-diagnostic-pass, and combined-restoration metadata findings were remediated with RED/GREEN tests before this formal review.

LOW

- No findings.

### Open Questions / Assumptions

- The operational diagnostic will run only after merge on a separately named OrbStack clone with a fresh unsubmitted RID week. The runner now enforces the clone-name and evidence-root portions of that assumption.
- Hosted CI state is not yet available because the PR has not been created. Local gate evidence is not reported as hosted-CI evidence.

### Recommended Tests / Validation

- Preserve the final `334 passed` three-run local result on this exact staged source.
- After merge, install the exact merged SHA in the disposable clone, run `--diagnostic`, verify the browser artifact and failure/pass checksums, and replay it through `validate_write_browser_result`.
- Verify scheduler/BFF restoration, `PLANNING_DEPTH_WRITES_ENABLED=false`, four ready backend services, and no listener on 9999 after the live diagnostic.

### Rollout Notes

- Harness-only observability remains fail closed and changes no product API or default flag.
- Diagnostic manifests are explicitly non-acceptance and never update `stage-state.json`.
- The frozen canonical guest and the earlier `32d89099...` archive remain unchanged.
