# Coding Log: PR #186 exact-SHA local CI remediation

- Started: 2026-08-13 20:53:47 +07
- Isolated worktree: `/Users/subhajlimanond/dev/munbon2-backend-pr186-local-ci-remediation`
- Branch: `fix/pr186-local-ci-remediation`
- Base: `origin/main@2e5597c46cfb7a2fcad32a14aca99fdc6402c7f9`
- Scope: source-only remediation of four exact-SHA local CI failures discovered after PR #186
- Protected state: no guest, campaign, deployment, activation, live runtime, or AWS mutation
- Evidence boundary: hosted zero-step billing-lock results remain separate from local exact-SHA source evidence
- Skill limitation: `g2-planning`, `g2-coding`, and `g2-review` exist on disk but were not prompt-visible skills in this session. The visible `g-planning`, `g-coding`, and `g-check` lifecycle is used; filesystem presence is not treated as invocation authority.

## Worktree ledger

- Session-owned: this worktree and branch only; dispose after merge, local-main landing, and exact-SHA post-merge verification.
- Pre-existing worktrees: 21 registrations were recorded before creation and are out of scope for cleanup.
- Primary checkout was clean at `main@2e5597c46cfb7a2fcad32a14aca99fdc6402c7f9` before session worktree creation.

## Requirement clarification and locked interpretation

The request already identifies the four failures, exact base, runtime versions, database isolation, delivery lifecycle, and protected operational state. “Authorized admin merge” is interpreted as authority to override only the known zero-step billing lock after all local source gates and reviews pass; it never authorizes bypassing a source, test, review, or merge-conflict failure.

## Repository discovery

RepoPrompt was bound to the exact isolated worktree and used for a focused context build covering the workflow, Scheduler settings/migrations, BFF/ROS migration parity, the full-tree baseline, related tests, and Coding Log evidence. Direct exact-string checks are reserved for confirming known identifiers and local scan behavior.

Confirmed defects at the base SHA:

1. `.github/workflows/control-plane-hardening-tests.yml::scheduler-tests` runs bare Scheduler pytest without the `POSTGRES_URL` required by `services/scheduler/src/config/settings.py`.
2. `services/bff-water-planning/tests/unit/test_planning_depth_runtime.py::test_runtime_migration_parity_requires_the_exact_bff_manifest` expects ROS latest/count `0003`/3 while the canonical roster is `0001` through `0004`.
3. `.github/workflows/control-plane-hardening-tests.yml::scheduler-postgres-integration` applies all Scheduler migrations but rolls back only `0006` through `0001`; the tracked roster is `0001` through `0013`.
4. `.security/full-tree-baseline.txt` omits the pre-existing carrier `services/scheduler/coding-logs/2026-07-18 Impl (pr-4-4a-2-runtime-readiness).md`.

The tracked control-plane workflow contains ten jobs. The separately tracked `.github/workflows/secret-scan.yml` defines the additional `scan-diff` and `full-tree-baseline` jobs, so their exact shell logic is available for local reproduction.

# Plan Draft A: minimal explicit contracts

## Overview

Add independent regression tests for the Scheduler workflow environment, complete rollback roster, and full-tree carrier manifest before changing configuration. Correct the stale BFF expectation through its existing real-filesystem parity test, then make the smallest explicit YAML/baseline edits.

## Files to change

- `ops/control-plan-read-local/tests/test_local_artifacts.py`: add static CI workflow and full-tree manifest contracts.
- `.github/workflows/control-plane-hardening-tests.yml`: add Scheduler dummy `POSTGRES_URL`; list rollbacks `0013` through `0001` explicitly.
- `services/bff-water-planning/tests/unit/test_planning_depth_runtime.py`: expect ROS `0004` and count 4.
- `.security/full-tree-baseline.txt`: add the unchanged historical Scheduler Coding Log carrier exactly once.
- This Coding Log and `.codex/coding-log.current`: lifecycle evidence only.

## TDD implementation sequence

1. Add three source-contract tests to `test_local_artifacts.py`.
2. Run them and confirm RED is exactly missing Scheduler `POSTGRES_URL`, incomplete rollback roster, and the one omitted historical carrier.
3. Run the existing BFF runtime parity test and confirm RED is only its stale `0003`/3 expected result versus canonical `0004`/4.
4. Lock assertions; make the minimum YAML, BFF test-oracle, and baseline changes.
5. Rerun each focused test on the primary thread and confirm GREEN.
6. Run formatter/lint/compile checks relevant to the changed Python/YAML/text surface.
7. Run all twelve local equivalents with Python 3.11, Node 20, and disposable loopback databases where required.
8. Repeat the affected focused scope three consecutive times.

## Test coverage

- `test_scheduler_bare_pytest_job_provides_required_postgres_url`: requires explicit non-live Scheduler DB setting.
- `test_scheduler_postgres_workflow_rolls_back_every_migration_in_reverse_order`: locks exact 0013-to-0001 rollback order.
- `test_full_tree_baseline_lists_scheduler_legacy_ip_carrier`: binds the pre-existing carrier to the manifest.
- `test_runtime_migration_parity_requires_the_exact_bff_manifest`: expects canonical ROS 0004 roster.

## Decision completeness

- Goal: make all four failures fail-fast under repository tests and restore the twelve local source gates.
- Non-goals: no migration SQL changes; no runtime settings defaults; no production/live database access; no guest/campaign/deployment/activation/AWS changes; no hosted billing remediation.
- Success criteria: four REDs confirmed for intended reasons; focused GREEN; ten tracked workflow jobs pass locally; two local secret-scan behaviors pass without overstating hosted equivalence; affected scope passes three times; QCHECK and formal g-check have no unresolved finding; PR merged; local main equals exact merge SHA.
- Public interfaces: no API/schema/topic/CLI change. Workflow-only `POSTGRES_URL` is added as a clearly dummy value. No migration identifiers or checksums change.
- Failure modes: import-time missing env fails closed; migration roster drift fails static contract; rollback order drift fails static contract and disposable DB round-trip; new/unlisted baseline carriers fail the tracked full-tree scan; unavailable hosted runner remains infrastructure-blocked, not green.
- Rollout/backout: source-only CI repair. Backout is PR revert; no data repair or runtime rollback exists because only disposable databases are touched.
- Monitoring: GitHub check annotations are observed separately. Local commands, versions, SHAs, exit codes, and disposable DB identifiers are recorded here.

## Dependencies and validation

- Python 3.11 with each service’s pinned requirements.
- Node 20 with `npm ci`; host Node 26 is not acceptable evidence.
- Disposable `postgis/postgis:16-3.4` databases for ROS/BFF and `postgres:16` for Scheduler, loopback only.
- Git history for campaign-ledger base comparison.
- Docker is local infrastructure only; no named/shared runtime containers or volumes may be reused.

## Wiring verification

| Component | Entry point | Registration/config load | Schema/contract match |
|---|---|---|---|
| Scheduler dummy `POSTGRES_URL` | `scheduler-tests` bare pytest | YAML step `env` | Settings import only; no DB service and no connection expected |
| Scheduler rollback roster | `scheduler-postgres-integration` migration round-trip | YAML shell block | Filesystem roster `0001`-`0013`; explicit down order `0013`-`0001` |
| BFF/ROS parity oracle | BFF unit test calls stage-suite validator | Dynamic load of `run-stage-suite.py` | ROS migration files exactly `0001`-`0004` |
| Full-tree carrier manifest | tracked `full-tree-baseline` job | `.github/workflows/secret-scan.yml` | New/unlisted carrier rejection against `.security/full-tree-baseline.txt` |

# Plan Draft B: introduce a reusable CI contract verifier

## Overview

Create a new Python verifier that parses the workflow, discovers Scheduler migration pairs, checks required job environment, validates rollback order, derives legacy-IP carriers, and exposes one CLI used by tests. Replace the explicit YAML rollback list with generated iteration over discovered migration IDs.

## Files to change

- New `scripts/verify-control-plane-ci-contract.py` plus tests.
- Workflow, BFF expectation, and baseline files from Draft A.
- Potential workflow invocation of the verifier.

## TDD implementation sequence

1. Write verifier unit tests against fixture workflow/baseline text.
2. Confirm RED for all four base defects.
3. Implement parsing/discovery and CLI with fail-closed errors.
4. Wire the verifier into the workflow and local harness suite.
5. Run focused and full gates.

## Test coverage

- `test_verify_scheduler_env_rejects_missing_postgres_url`: rejects incomplete job env.
- `test_verify_scheduler_rollbacks_require_reverse_discovered_roster`: rejects missing down steps.
- `test_verify_full_tree_baseline_requires_set_equality`: rejects missing and stale entries.
- Existing BFF parity test updated as in Draft A.

## Decision completeness

- Goal/non-goals/success criteria and public interfaces match Draft A.
- New interface: repository-only verifier CLI.
- Failure modes: YAML parsing/Git absence/path encoding would fail closed.
- Rollout/backout: revert verifier wiring; no runtime state.
- Acceptance: verifier unit tests plus the same twelve local gates.

## Wiring verification

| Component | Entry point | Registration/config load | Schema/contract match |
|---|---|---|---|
| CI contract verifier | harness pytest and workflow step | new script import/CLI | workflow YAML, migration filenames, baseline paths |
| Dynamic rollback loop | Scheduler integration job | shell/Python output | discovered paired migration roster |
| BFF/ROS parity | same as Draft A | same as Draft A | ROS `0001`-`0004` |

## Trade-offs

Draft B centralizes drift detection and reduces manually repeated lists, but it adds a new parser/CLI and makes rollback behavior depend on generated shell state. It also duplicates discovery already implemented in `migrations/migrate.py` without providing runtime value. For thirteen safety-sensitive down migrations, the explicit reviewed order is easier to audit.

# Comparative analysis

- Draft A is the smallest change, reuses the established `test_local_artifacts.py` pattern, and keeps the destructive disposable-DB sequence fully explicit.
- Draft B is more extensible but introduces unnecessary parsing, a new CLI contract, and another place for migration discovery to diverge.
- Both preserve source/runtime/acceptance boundaries and TDD.
- Draft A’s full-tree test should compare the complete carrier set, not merely assert the named path, so it catches both omissions and stale allowlist entries.
- Draft A must not hide `POSTGRES_URL` in Scheduler `conftest.py`; the workflow owns import-time configuration.
- The BFF Postgres fixture remains at its intentional ROS 0001 schema prerequisite; runtime migration parity is a separate contract.

# Unified execution plan

Adopt Draft A with a focused carrier regression test plus the tracked full-tree workflow logic.

## Ordered work units

1. Preserve pre-remediation evidence at base SHA without touching live state.
2. Add and RED-confirm the three local artifact contracts.
3. RED-confirm the existing BFF parity test.
4. Add the dummy Scheduler workflow `POSTGRES_URL`; explicitly prepend rollbacks `0013` through `0007`; update BFF `0004`/4 expectation; add the historical carrier to the baseline in Scheduler lexical grouping.
5. GREEN-confirm focused tests and inspect the complete changed-file set.
6. Run all twelve local equivalents:
   - `scheduler-tests` — Python 3.11, no DB service, dummy env.
   - `bff-tests` — Python 3.11, no DB service.
   - `ros-tests` — Python 3.11, no DB service.
   - `control-plan-local-harness-tests` — Python 3.11 plus append-only campaign-ledger comparison against the exact base SHA.
   - `ros-postgis-integration` — disposable PostGIS 16-3.4.
   - `bff-postgres-integration` — disposable PostGIS 16-3.4.
   - `scheduler-postgres-integration` — disposable Postgres 16, apply/rollback/reapply/reset/integration.
   - `scada-gate-control-tests` — Node 20.
   - `scada-gate-control-web-tests` — Node 20.
   - `pm2-infrastructure-tests` — Node 20.
   - `scan-diff` — tracked per-commit plus endpoint added-line scan.
   - `full-tree-baseline` — tracked full-tree password and unlisted legacy-IP carrier scan.
7. Run affected focused tests three consecutive times and final formatting/lint/type/build/wiring gates.
8. QCHECK against function, test, and implementation checklists; remediate and rerun affected gates.
9. Stage only intended files; formal g-check on the staged working tree; disposition every finding.
10. Conventional commit, push, one PR to main, inspect required check annotations. Admin-merge only if all local gates/reviews pass and the only hosted blocker is the documented zero-step billing lock.
11. Fast-forward local primary main to `origin/main`; verify exact merged SHA with relevant post-merge checks.
12. Read and execute the worktree closeout protocol; preserve the unique Coding Log through merge and remove only this session-owned worktree/branch as permitted.

## Exact acceptance behavior

- Every changed behavior has a defect-sensitive assertion.
- No public/runtime interface changes.
- No migration SQL or checksum changes.
- No operational host, credential, guest, campaign, deployment, activation, or AWS mutation.
- Disposable DB names and container resources are unique to this run and removed after checks.
- Hosted billing evidence, local base-SHA failures, local candidate-SHA passes, and post-merge exact-SHA evidence remain distinct.

## Work unit: four regression contracts RED to GREEN (2026-08-13 21:03 +07)

### Goal and files

- Added workflow/baseline regression contracts in `ops/control-plan-read-local/tests/test_local_artifacts.py`.
- Added a clearly dummy `POSTGRES_URL` to Scheduler bare pytest and completed the explicit 0013-to-0001 rollback sequence in `.github/workflows/control-plane-hardening-tests.yml`.
- Corrected the BFF runtime-parity test oracle to ROS `0004`/4.
- Replaced the stale `.github/workflows/deploy-flow-monitoring.yml` baseline entry with the pre-existing Scheduler Coding Log carrier; the historical carrier itself was not edited.

### RED evidence

- Command: `/tmp/munbon-pr186-ci.B0fwM5/ros/bin/python -m pytest -q ops/control-plan-read-local/tests/test_local_artifacts.py -k 'scheduler_bare_pytest_job_provides_required_postgres_url or scheduler_postgres_workflow_rolls_back_every_migration_in_reverse_order or full_tree_baseline_matches_tracked_legacy_ip_carriers'`
- Result: 3 failed for the intended contracts only: missing Scheduler `POSTGRES_URL`; rollback actual `0006`-`0001` versus expected `0013`-`0001`; exact carrier-set mismatch with the Scheduler log missing and an absent workflow stale in the baseline.
- Command: `CORS_ORIGINS=http://localhost:3000 /tmp/munbon-pr186-ci.B0fwM5/bff/bin/python -m pytest -q tests/unit/test_planning_depth_runtime.py`
- Result: 1 failed for the intended stale oracle only: actual ROS latest/count `0004_dataset_version_identity_immutable`/4 versus expected `0003_daily_requirement_producer`/3.

### GREEN evidence

- The same artifact-contract command passed: 3 passed, 38 deselected.
- The same BFF parity command passed: 1 passed.

### Wiring and risk notes

- Scheduler bare pytest loads workflow-local dummy configuration and has no database service; the dummy URL must never be opened.
- Scheduler round-trip reaches the existing migration CLI against a dedicated disposable loopback Postgres only.
- The focused baseline test proves the historical Scheduler carrier remains present and is listed. The tracked full-tree job separately enforces that no unlisted carrier exists; stale entries are notices under its current contract.
- Independent `terra_support` evidence confirmed the four defects and identified the stale baseline entry and Node-version split. No delegate edited files or lifecycle artifacts.
- The local acceptance harness pins Node 22.23.1 while the three Node workflow jobs pin Node 20. Each will be run at its own declared version; this distinction prevents false equivalence.

## Work unit: pre-commit local workflow matrix (2026-08-13 21:04-21:05 +07)

### Python 3.11 source jobs

- Scheduler bare pytest with workflow dummy env: 1044 passed, 59 skipped, 103 pre-existing deprecation warnings.
- BFF bare pytest: 337 passed, 31 skipped, 59 pre-existing warnings.
- ROS bare pytest: 268 passed, 16 skipped, 38 pre-existing warnings.
- Control-plan harness: 445 passed after the final source-contract addition.
- Campaign-ledger append-only validation against exact base `2e5597c46cfb7a2fcad32a14aca99fdc6402c7f9`: PASS. The historical/exhausted campaign records were read and compared only; no campaign state was written.

### Node 20 source jobs

All three ran in ephemeral `node:20` containers and reported Node `v20.20.2`.

- SCADA gate control: typecheck and lint passed; 424 tests passed, 7 skipped.
- SCADA gate control web: typecheck and lint passed; 187 tests passed; Next.js production build passed.
- PM2 infrastructure: lint plus verify passed; Prettier, typecheck, lint, and 39 Jest tests passed.
- Existing npm audit output reported dependency vulnerabilities (SCADA service: 17, web: 7 high, PM2: 8 including 1 critical). No dependency file changed in this remediation; record as residual supply-chain risk rather than silently auto-fixing outside scope.

### Disposable database jobs

- ROS PostGIS `postgis/postgis:16-3.4`, dedicated container `munbon-pr186-ros-205347`, loopback random port: migrations 0001-0004 applied; repository integration 4 passed; dataset immutability 11 passed; container removed.
- BFF PostGIS `postgis/postgis:16-3.4`, dedicated container `munbon-pr186-bff-205347`, loopback random port: planning-depth integration 30 passed; container removed.
- Scheduler Postgres `postgres:16`, dedicated container `munbon-pr186-scheduler-205347`, loopback random port: migrations 0001-0013 applied, rolled back 0013-0001, reapplied, and status confirmed all 13.

The first Scheduler integration invocation then failed collection for the intended configuration root cause: its workflow step provided `SCHEDULER_TEST_POSTGRES_URL` but omitted the import-time `POSTGRES_URL`. This was not a database/setup failure. The plan was amended within the same requested defect:

- Added `test_scheduler_postgres_integration_provides_runtime_postgres_url`.
- Initial assertion was tightened after it accidentally substring-matched `SCHEDULER_TEST_POSTGRES_URL`; valid RED then failed on the missing exact YAML key.
- Added `POSTGRES_URL` pointing to the same disposable loopback Scheduler database in that pytest step.
- Static GREEN passed, then the exact integration env passed 59 tests with 103 pre-existing warnings.
- The Scheduler container was removed after the successful rerun. The schema drop occurred only inside this dedicated disposable container.

### Independent QCHECK and remediation

- MEDIUM: the first local baseline regression asserted exact carrier-set equality, stricter than the tracked hosted job, which fails only unlisted carriers and reports stale entries as notices. Remediation: narrowed the regression to the exact historical carrier and reserved hosted-equivalent enforcement for `.github/workflows/secret-scan.yml`.
- MEDIUM: discovery text incorrectly said both Secret Scan job definitions were absent. Remediation: corrected all plan/evidence claims after direct inspection of tracked `.github/workflows/secret-scan.yml`.
- LOW: Scheduler env assertions were initially job-wide, then were not bounded at the following step. Remediation: `_workflow_step` now slices from the exact named pytest step only through the next step delimiter, so unrelated step env cannot satisfy the contract.
- LOW: the carrier regression initially required the historical IP to remain forever. Remediation: it now uses implication semantics—while the file contains the IP it must be baselined; a future cleanup can pass and remove the stale baseline entry.
- QCHECK found no defect in the explicit reverse migration order, dummy/disposable DSNs, BFF parity correction, or current carrier manifest content.

## Formal g-check remediation round 1 (2026-08-13 21:16 +07)

- MEDIUM: adding the proven historical carrier contradicted the baseline header's unconditional “NEVER add” text. Disposition: accepted and remediated. The user explicitly required this omitted carrier to be listed; the header now permits only an explicitly approved, source-history-proven pre-baseline omission while continuing to forbid newly introduced carriers and requiring normal later cleanup.
- LOW: workflow source tests could accept comment-only or mis-scoped DSNs/rollback commands. Disposition: accepted and remediated. `_workflow_step_env` now parses only exactly indented executable environment entries before `run:`, and `_workflow_rollback_ids` accepts only exactly indented executable rollback commands. A negative test proves comments, `SCHEDULER_TEST_POSTGRES_URL`, and wrong indentation cannot satisfy the contracts.
- The formal reviewer found the explicit 0013-to-0001 order and BFF/ROS 0004 parity correct. Hosted zero-step billing results remain infrastructure-blocked and separate from local evidence.

## Review (2026-08-13 21:19 +07) - staged working tree

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-pr186-local-ci-remediation`
- Branch: `fix/pr186-local-ci-remediation`
- Scope: staged working tree based on `2e5597c46cfb7a2fcad32a14aca99fdc6402c7f9`; refreshed staged snapshot `2026-08-13/2117`
- Commands Run: staged status/stat and RepoPrompt diff artifacts; focused RED/GREEN; Python 3.11 Scheduler/BFF/ROS/harness suites; tracked campaign-ledger validation; Node 20 SCADA/SCADA-web/PM2 gates; disposable ROS/BFF/Scheduler database jobs; Black; Ruff; compileall; `git diff --check`; affected scope three consecutive runs; independent QCHECK with remediation rounds; formal RepoPrompt review with one remediation round.

### Findings

CRITICAL

- No findings.

HIGH

- No findings.

MEDIUM

- No remaining findings. Initial baseline-policy contradiction was remediated by narrowly documenting explicitly approved, source-history-proven omissions without permitting newly introduced carriers.

LOW

- No remaining findings. Initial workflow text-oracle weakness was remediated with exact executable env/rollback parsing and negative comment/mis-scope coverage.

### Open Questions / Assumptions

- No open source decision. Hosted execution remains externally blocked by the known GitHub billing lock.
- Admin merge authority applies only if local exact-SHA gates remain green and hosted jobs have zero executed steps for the documented billing reason.

### Recommended Tests / Validation

- Validate workflow syntax with `actionlint` if installed.
- Reproduce tracked `scan-diff` and `full-tree-baseline` logic at the exact candidate SHA.
- After merge, rerun relevant focused tests and secret scans at the exact merge SHA before cleanup.

### Rollout Notes

- Source-only CI remediation: no migration SQL, live database, guest, campaign, deployment, activation, or AWS mutation.
- Hosted zero-step jobs remain infrastructure-blocked, never passing; local evidence is reported separately.
- Formal g-check disposition: no remaining CRITICAL/HIGH/MEDIUM/LOW findings.

### Repeated focused and quality evidence

- Four artifact contracts plus the BFF parity test passed three consecutive runs: each run was 4 passed plus 1 passed.
- Black initially reported the modified artifact test needed formatting; it was formatted, then the repeated focused tests passed.
- Ruff passed on both modified Python test files; Python 3.11 compileall passed; `git diff --check` passed.
- No migration SQL or historical Coding Log content changed. Runtime wiring remains workflow-only.

## Decision-complete checklist

- [x] No open implementation decision remains.
- [x] Every changed interface is listed; only workflow-local env changes.
- [x] Every behavior change has a real-defect regression test.
- [x] Validation commands and runtime versions are specified.
- [x] Wiring table covers workflow env, migration rollback, parity, and baseline.
- [x] Backout and evidence boundaries are specified.
