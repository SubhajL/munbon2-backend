# Coding Log: local RC runtime acceptance

## Session ownership and evidence baseline

- Implementation worktree: `/Users/subhajlimanond/dev/munbon2-backend-local-rc-runtime-acceptance`
- Branch: `test/local-rc-1-runtime-acceptance`
- Baseline/backend candidate: `56292eed9d331d281237a350920df2c6e23fe632`
- Frontend candidate: `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`
- Origin transport: backend and frontend are SSH-only; both exact candidates equal their live `origin/main` heads.
- Baseline worktree inventory: the primary checkout and four pre-existing worktrees are user-owned and outside cleanup scope. This session owns only the implementation worktree above.
- Existing canonical guest to preserve, validate, then replace by exact ID: `munbon-control-plan-local` / `01M0F27Z1GZQ7SQF07XH9M3VQT`.
- Existing guest owner binds backend `7f032c4c20e7f9cdd443d64f7adbeb37342ff190`, frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`, dependency `89a26cbd783b21037acd3ce2f1e116f0e69ba8ea0d1667be8b6fda22a1aef7ab`.
- Existing frozen 9/9 archive outer checksums passed and the guest identity matches the `successful_closed` campaign-ledger entry.
- Fresh dependency destination: `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/dependencies-56292eed9d331d281237a350920df2c6e23fe632-067b3e22401854f8c6d6db42dc0c5c1872fca6f8.tar.gz`.
- Fresh success destination: `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/2026-08-21-rc-56292eed-attempt-1`.
- Fresh partial-failure destination: `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/2026-08-21-rc-56292eed-attempt-1-partial`.
- Fresh bootstrap-failure destination: `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/2026-08-21-rc-56292eed-bootstrap-failure`.
- RepoPrompt bound to the prior Path 1 workspace but its provider root was unavailable. Planning discovery therefore used direct inspection plus exact-string `rg` searches over `AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`, `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`, `docs/operations/control-plan-campaign-ledger.jsonl`, `ops/control-plan-read-local/orchestrate.py`, `run-stage-suite.py`, `run-write-browser.js`, and the corresponding Python/Node tests.

## Plan Draft A: canonical-runtime-first

### Overview

Build a checksum-bound dependency closure for the exact current candidates, replace only the validated exhausted canonical guest, and execute one no-retry `LOCAL-RC-1` attempt on the newly created pristine guest. Treat the first runtime outcome as authoritative: preserve and independently validate either the complete PASS archive or the bounded ordered-prefix failure archive before any remediation decision.

### Files to change

- `.codex/coding-log.current`: point lifecycle tools at this log.
- `coding-logs/2026-08-21-06-26-45 Coding Log (local-rc-runtime-acceptance).md`: planning, runtime evidence, TDD receipts, gates, reviews, delivery, and cleanup.
- `ops/control-plan-read-local/tests/test_local_artifacts.py`: tests-first status contract for the exact accepted RC identities and evidence digest.
- `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`: after authoritative PASS, replace the stale not-accepted status with exact candidate/guest/archive/darkness facts.
- If and only if the canonical run exposes a source defect: the smallest relevant test file under `ops/control-plan-read-local/tests/`, followed by a separately locked Luna-only production allowlist chosen from `orchestrate.py`, `run-stage-suite.py`, or `run-write-browser.js`. No production file is pre-authorized without an executable defect oracle.

### Implementation steps

1. Build the exact ARM64 dependency archive in the existing diagnostic guest and validate its outer and inner checksums.
2. Re-read the canonical guest inventory, shape, stable ID, owner, provisioning state, stage state, and frozen archive checksums; delete only stable ID `01M0F27Z1GZQ7SQF07XH9M3VQT`, then verify it is absent.
3. Provision the fixed canonical guest name from the exact backend/frontend/dependency identities. Record the new 26-character guest ID and machine ID; do not reuse the old ID.
4. Run `run-rc` once for Bangkok date `2026-08-21`, attempt ceiling one, and the fresh success destination. No retry, repair, replay, or reprovision is permitted.
5. On success, independently validate exact inventory, all inner/outer checksums, candidate and guest bindings, ten-stage ordered PASS, RC PASS, final darkness, session cleanup, and stable runtime identity.
6. On failure, collect only the bounded partial archive into the fresh partial destination when automatic collection did not complete. Preserve the failed phase/gate and unreached suffix; do not retry.
7. If failure proves a source defect, follow strict TDD: add the smallest test, confirm expected RED, lock production allowlist/wiring/GREEN, snapshot ownership, delegate one Luna-Max GREEN slice, validate its receipt, rerun GREEN, then repeat a newly authorized pristine canonical attempt only if the task authorization still provides another attempt.
8. After PASS, add the runbook status test first, confirm RED against stale text, update the runbook, run focused/full gates and three repeats, then QCHECK and formal `g-check`.
9. Commit, push over SSH, create one standard GitHub PR, verify exact head and mergeability, admin-merge under the standing billing-lock policy, land exact merge SHA on local `main`, verify post-merge artifacts, and close the session worktree.

### Functions and behavior

- `build_dependencies()`: bind a fresh archive to exact candidates and committed dependency inputs.
- `provision()`: create only a missing canonical guest with the fixed isolated machine specification; reject reprovisioning.
- `run_rc()`: revalidate guest identity before every phase/stage, stop on first outcome, and collect once.
- `_validated_rc_guest()`: bind stable Orb ID, `/etc/machine-id`, owner, provision state, and dependency checksum.
- `_run_rc_phase()` / `_run_stage()`: dispatch the preflight, ten stages, and finalization with exact identities.
- `collect_rc()` / `finalize_rc_collection()`: validate candidate, guest, stage order, darkness, inventory, and checksum closure before PASS publication.
- `test_all_stages_runbook_records_exact_local_rc_acceptance`: require the exact accepted identities, PASS archive/index digest, and explicit non-production boundary.

### Test coverage

- `test_all_stages_runbook_records_exact_local_rc_acceptance` — pins exact RC candidate and evidence identities.
- Existing `run_rc` identity tests — reject guest ID or machine drift.
- Existing RC collection tests — reject checksum, order, and darkness drift.
- Defect-specific test, named after observed failed invariant — reproduces the exact runtime gap without weakening contracts.

### Decision completeness

- Goal: authoritative fresh `LOCAL-RC-1` PASS for exact backend/frontend candidates, followed by durable source documentation and delivery.
- Non-goals: reusing predecessor evidence; retrying or repairing the canonical attempt; redefining the frozen nine-stage ledger; production AWS deployment in this plan.
- Success: one pristine guest, ten ordered stage PASS manifests plus RC PASS, checksum-valid inner/outer archive, independently recomputed digests, exact candidate/guest bindings, final flags dark, sessions revoked, no unexpected listeners/processes, formal clean review, merged PR, exact-SHA local-main landing, and worktree cleanup.
- Public interfaces: no API, schema, migration, topic, CLI, or environment change is planned. A defect may change an existing RC validation behavior only after a RED contract and explicit Luna allowlist.
- Failure behavior: identity/checksum/source/runtime drift fails closed; build/provisioning failure has no acceptance meaning; stage failure stops immediately; uncertain cleanup or publication produces no PASS; interrupts are authoritative and produce no fabricated verdict.
- Rollout/monitoring: isolated OrbStack only. Watch fixed guest identity, loopback listeners, PM2 restart counts, readiness, mutation inventory, rate state, evidence checksums, and all dark flags. Backout is verified dark restoration and session revocation, not evidence deletion.

### Dependencies and validation

- OrbStack running; diagnostic build guest exact shape; backend and frontend SSH origins; Node/Python closures obtainable only in diagnostic lane.
- Candidate checks: `git ls-remote` over SSH and local `rev-parse` equality.
- Source gates: complete Python harness, complete Node harness, Black check, Ruff, `py_compile`, JavaScript syntax checks, and `git diff --check`.
- Stability: complete affected Python and Node scopes three consecutive times on the unchanged reviewed candidate.
- Evidence: `shasum -a 256 -c` for every outer index plus harness-independent JSON/inventory validation.

### Wiring verification

| Component | Entry point | Registration/config load | Schema/contract match |
|---|---|---|---|
| RC host controller | `orchestrate.py:main()` action `run-rc` | `run_rc()` | exact CLI SHA/date/dependency/guest contract |
| RC guest phases | `run_rc()` | `_run_rc_phase()` invokes guest `run-stage-suite.py --rc-phase` | preflight/finalize evidence schemas |
| Ten progressive stages | `run_rc()` loop over `STAGE_ORDER` | `_run_stage()` | exact checksum-valid completed prefix |
| Browser write proof | `run-stage-suite.py` WRITE-ACT dispatch | `run-write-browser.js` subprocess | mutation inventory and dark-session evidence |
| RC archive | `run_rc()` automatic collection | `collect_rc()` then `finalize_rc_collection()` | RC manifest, summary, inner and outer indexes |

No migration or cross-language DB schema change is planned. Exact existing table/column contracts remain validated by the canonical harness.

## Plan Draft B: exhaustive-source-gate-first

### Overview

Before touching the canonical guest, rerun every complete source gate and perform another full static/formal review of the already merged Path 1/2 source, then build dependencies and execute the same one-shot canonical RC. This lowers the chance of spending the guest attempt on a statically discoverable regression but delays the only evidence capable of exposing environment-bound gaps.

### Files to change

The same lifecycle/test/runbook files as Draft A. No production file changes unless a new RED proves a defect.

### Implementation steps

1. Run the complete Python/Node/static gates and independent review on baseline `56292eed`.
2. Build and verify the exact dependency archive.
3. Validate/preserve/delete the exhausted guest, provision a pristine guest, and lock its IDs.
4. Execute one canonical RC attempt, independently validate evidence, and follow the same TDD/Luna remediation or PASS documentation path as Draft A.

### Test coverage

- Complete existing harness before runtime — detects source regressions early.
- Exact runbook acceptance test after PASS — prevents status overclaim.
- Runtime-failure-specific RED if needed — converts observed gap to executable contract.

### Decision completeness

Goal, non-goals, success criteria, public surfaces, failure semantics, rollout, and acceptance checks are identical to Draft A. The only meaningful difference is gate ordering.

### Dependencies, validation, and wiring

Identical to Draft A. Wiring remains the existing host controller to guest stage runner to evidence collector chain.

## Comparative analysis

- Draft A reaches the missing evidence boundary sooner and preserves the one-shot contract cleanly. Its risk is spending diagnostic-build time before rerunning already-clean full source gates.
- Draft B gives additional static confidence first, but the exact merged source already has documented repeated full gates and clean formal review, while only runtime acceptance is absent.
- Both fail closed, preserve predecessor evidence, use no retry/repair, require a fresh guest and destinations, and route every production remediation through Luna-Max after primary RED.
- Draft A is preferred because current evidence identifies runtime truth, not source uncertainty, as the remaining milestone.

## Unified execution plan

1. Treat `56292eed9d331d281237a350920df2c6e23fe632` and `067b3e22401854f8c6d6db42dc0c5c1872fca6f8` as the exact RC candidate because each is independently verified as current SSH `origin/main`.
2. Build and independently validate the fresh dependency archive before deleting the preserved old guest.
3. Revalidate the old stable guest ID, shape, owner, state, frozen archive, and ledger binding; delete only that exact ID and prove absence.
4. Provision one pristine fixed-name guest, record its new stable ID and `/etc/machine-id`, and verify candidate/dependency ownership.
5. Execute exactly one `run-rc` for `2026-08-21` into the fresh success destination. No retry, repair, or replay.
6. Preserve exactly one authoritative outcome. Independently validate checksums, inventories, exact candidate/guest identity, ordered stages, runtime darkness, listener/process restoration, mutation absence, and session revocation.
7. If a source defect is proved, primary writes the defect-specific test and confirms RED; production GREEN is sequential Luna-Max only with snapshot, exact allowlist, receipt, validator, complete diff audit, GREEN, wiring, full gates, three repeats, QCHECK, and formal `g-check`.
8. After authoritative PASS, primary adds the runbook status test, confirms RED, updates only documentation/status evidence, and runs focused/full/repeat gates.
9. Formal `g-check` must be clean. Deliver one standard Git/GitHub PR, admin-merge after local gates and exact-head/mergeability checks, treat no-step billing-locked hosted jobs as unavailable, land exact merge SHA locally, and verify the merged status contract.
10. Preserve evidence and hashes, prove final darkness and session cleanup, remove the session-owned worktree through `git worktree remove`, prune verified stale registrations, and prove the primary checkout remains unchanged.

### Decision-complete checklist

- No implementation decision is delegated: yes.
- Exact candidates, date, attempt ceiling, old guest ID, and fresh destinations are locked: yes.
- New guest ID is locked immediately after the authorized create and before any RC dispatch: yes.
- Every behavior change requires a real-defect test: yes.
- Production modifications require Luna-Max ownership validation: yes.
- Validation commands and evidence predicates are specific: yes.
- Wiring table covers controller, phases, stages, browser, and archive: yes.
- Deployment target beyond the canonical isolated guest is intentionally outside this milestone and will receive a separate plan after target confirmation: yes.

## Slice RC-CLOSURE-REFRESH-1: executable RED and locked contract

- The first exact diagnostic build failed before archive publication with `FAIL orchestration: diagnostic_dependency_build_failed`; no canonical guest action or acceptance attempt occurred.
- A traced same-input diagnostic replay proved the exact failing invariant: `build-dependency-bundle-linux.sh` resolved 84 `flow-monitoring` wheels with aggregate receipt digest `dc46c984131da3d332291b4c88b3059d95a6d45cd0de62885185f74df8938e58`, while `python-closures.lock` requires `1fcccdfef76712bde019df56c9f6e81e750f97e62e5a05a4d441b5c8ba0c41df`; the script emitted `FAIL dependency_bundle_python_closure` and exited 1.
- A separate exact-source diagnostic wheel measurement completed all four closures. Counts are unchanged and current measured receipt digests are:
  - `flow-monitoring dc46c984131da3d332291b4c88b3059d95a6d45cd0de62885185f74df8938e58 84`
  - `scheduler a1b7faff1f576348d86c0937a35137b9bfaeacd4519bfaa81f9428e4da85befd 96`
  - `ros-gis-integration b93f766833f619c8513a681e3ce6447884e709eafb5deb4004e4522678b1c84d 67`
  - `bff-water-planning d7b3ae0e24d650757912db007a45b75bf66465b3917758e4682024d2f20d8c35 81`
- Honest no-new-test decision: the existing `test_python_closure_lock_content_addresses_all_arm64_wheel_sets` already requires every receipt to be canonical, sorted, count-bound, digest-bound, and exactly equal to the lock. A mock or hard-coded test for current PyPI would not independently prove the live ARM64 closure. The failed exact diagnostic builder is the executable RED and the same full builder command is the scoped GREEN.
- Goal: refresh only the four measured ARM64 closure receipts and their aggregate lock entries to the exact same-source resolution above.
- Non-goals: changing requirements, builder behavior, package versions manually, retry policy, runtime code, tests, docs, guest state, Git state, or the canonical acceptance contract.
- Production allowlist: `ops/control-plan-read-local/python-closures.lock` and the four files under `ops/control-plan-read-local/python-closure-receipts/` named for the measured services.
- Protected paths: every test, `.codex/**`, `coding-logs/**`, runbook, orchestrator, builder/installer/validator script, requirements file, service source file, and Git metadata.
- Receipt contract: each receipt is copied byte-for-byte from the independently measured sorted `sha256sum` output; every line matches the existing receipt schema; each lock digest is SHA-256 of the exact receipt bytes; counts remain 84/96/67/81; no other file changes.
- Scoped GREEN: rerun `test_python_closure_lock_content_addresses_all_arm64_wheel_sets`, then rerun the exact `build-dependencies` command to the still-fresh authorized destination and require archive validation plus the four locked digests.

## Slice RC-CLOSURE-REFRESH-1: Luna receipt and primary verification

- Pre-handoff ownership snapshot: `/tmp/munbon-local-rc-python-closure-refresh.snapshot.json`, SHA-256 `54bf8f93f0c5828293fe014f81162ce716339f667564a1b54b810c49c008abc2`.
- Luna-Max receipt: `/tmp/munbon-local-rc-python-closure-refresh.receipt.json`, SHA-256 `da6b12efeab5d857d1297069d171f36f196b41636b15daac677d752d9aef26d5`; role `luna_implementer`, model `gpt-5.6-luna`, effort `max`.
- Ownership validation passed with exactly the five allowlisted production files, unchanged HEAD, no protected-file modification, and receipt hashes matching the worktree.
- Primary complete-diff audit passed. The only package changes are `idna` 3.18 to 3.19 in all four receipts, `python-dotenv` 1.2.2 to 1.2.3 in flow-monitoring and scheduler, and `protobuf` 7.35.1 to 7.36.0 in scheduler. Counts remain 84/96/67/81. `git diff --check` passed.
- Primary focused contract test passed: `1 passed, 43 deselected` for `test_python_closure_lock_content_addresses_all_arm64_wheel_sets`.
- The immediate builder rerun failed with the same closure mismatch because `_create_bundle` deliberately packages the committed `main` candidate, not uncommitted worktree state. The retained source bundle for `56292eed9d331d281237a350920df2c6e23fe632` still contains the old lock, so this is not a GREEN failure of Luna's five files.
- Integration ordering is therefore locked: complete local gates and formal review, land the five-file refresh as a new backend candidate, independently lock that new exact SHA, then run `build-dependencies` against the new candidate. The canonical guest remains untouched and no acceptance attempt has occurred.

## QCHECK disposition - RC-CLOSURE-REFRESH-1

- Function checklist: no function was added or edited. The existing builder still fails closed on count or aggregate receipt mismatch and still consumes the committed candidate lock.
- Test checklist: no test was added or edited. This is intentional because the existing content-address test independently validates sorted canonical receipt rows, exact counts, receipt byte digests, lock membership, and inventory cardinality. The real Debian ARM64 diagnostic build is the executable package-resolution oracle.
- Implementation checklist: the change is minimal, reuses the existing lock/receipt contract, changes no requirements or package-selection logic, and preserves the required TDD/Luna ownership boundary.
- Full affected Python and JavaScript harnesses passed three consecutive times on the unchanged worktree: Python `819 passed`; Node `51 passed` per run.
- Ruff, Black check, Python compileall, Bash syntax, JavaScript syntax, receipt sort checks, receipt count/digest recomputation, and `git diff --check` passed.
- Disposition: no QCHECK finding. The remaining builder GREEN is correctly blocked on landing a new immutable candidate and is not waived.

## Review (2026-08-21 07:02:11 +07) - working-tree RC-CLOSURE-REFRESH-1

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend-local-rc-runtime-acceptance`
- Branch: `test/local-rc-1-runtime-acceptance`
- Scope: working tree based on `56292eed9d331d281237a350920df2c6e23fe632`
- Commands Run: working-tree status/stat/targeted complete diff; `git diff --check`; focused closure-lock pytest; full affected pytest and Node suites three times; Ruff; Black check; compileall; Bash and JavaScript syntax; receipt sort/count/SHA-256 recomputation; diagnostic builder and retained trace inspection.
- RepoPrompt: correctly bound to this worktree, but focused Context Builder review returned `Context Builder is already MCP-controlled for this tab`; per skill policy the review immediately used the targeted files, exact-string wiring search, tests, and retained runtime evidence already gathered.

### Findings
CRITICAL
- No findings.

HIGH
- No findings.

MEDIUM
- No findings.

LOW
- No findings.

### Open Questions / Assumptions
- The current live Python indexes are assumed to remain the dependency source until the new immutable candidate build begins. Any further index drift will fail closed against these exact receipt digests and require a newly measured, reviewed candidate rather than an in-place retry.
- The canonical acceptance guest remains untouched; this review grants no acceptance verdict.

### Recommended Tests / Validation
- After this five-file refresh lands, lock the exact new backend SHA and run the full diagnostic `build-dependencies` command against that SHA. Require archive publication, local archive validation, and independently recomputed SHA-256 before deleting the predecessor canonical guest.
- Retain the existing one-attempt/no-repair contract for the later canonical `run-rc` campaign.

### Rollout Notes
- This changes only content-addressed dependency receipts and their aggregate lock. It introduces no flag, environment, API, schema, migration, or runtime behavior change.
- Do not build against `56292eed9d331d281237a350920df2c6e23fe632` again: its immutable bundle correctly contains the prior lock. The post-merge SHA is the only eligible backend candidate for the next dependency build.

## Independent QCHECK disposition - RC-CLOSURE-REFRESH-1

- Independent read-only review reported one HIGH lifecycle-ordering condition: uncommitted receipt changes cannot affect immutable candidate `56292eed9d331d281237a350920df2c6e23fe632`; the refresh must land before another builder invocation. This is accepted and already encoded as the required next action, not waived.
- The independent reviewer found no correctness defect in the five-file content-address relationship and confirmed all four lock digests/counts match the refreshed receipts and retained diagnostic evidence.
- Its incomplete residual checks were independently completed by the primary: the focused receipt invariant passed, receipt sort/schema/count/digest recomputation passed, the complete working-tree diff was inspected, and `.codex/coding-log.current` resolves exactly to this log.
- Disposition: clean to commit and submit the minimal refresh. No diagnostic or canonical builder may run again until the new immutable candidate is landed and independently locked.

## Post-merge dependency GREEN and predecessor replacement blocker

- PR `#196` merged the accepted closure-refresh head `6524454064045476474b1741b9a72099973da16b` as `ce309918ef5a799ba37c561b470d3c5708d6fca2`. SSH `origin/main`, the clean primary checkout, and the session worktree were independently landed at that exact merge SHA.
- Hosted jobs failed before executing a first step with the standing billing-lock condition and were recorded once as unavailable, not passing. The authorized admin merge proceeded only after local gates, exact head, ancestry, and mergeability checks passed.
- The exact post-merge dependency build passed for backend `ce309918ef5a799ba37c561b470d3c5708d6fca2` and frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`.
- Fresh archive: `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/dependencies-ce309918ef5a799ba37c561b470d3c5708d6fca2-067b3e22401854f8c6d6db42dc0c5c1872fca6f8.tar.gz`; independently recomputed and validator-accepted SHA-256 `94bef9e1c3ad97cdf52f3593a5f12f7d4d42bfacb534a6b28c44fe9d8db8f3b1`.
- Before predecessor replacement, exact guest `01M0F27Z1GZQ7SQF07XH9M3VQT` was revalidated against name/shape, owner candidate, dependency digest, nine-stage state, `successful_closed` ledger entry, frozen external archive, and all outer checksums.
- `orbctl delete -f 01M0F27Z1GZQ7SQF07XH9M3VQT` panicked in OrbStack 2.2.2 while the guest was running. The exact ID was then stopped successfully and revalidated as stopped. Both forced deletion and interactive confirmed deletion of only that exact ID panic at OrbStack `delete.go:141`.
- Inventory proves the predecessor remains present, stopped, and unchanged. No canonical guest was created and no `LOCAL-RC-1` attempt occurred.
- `orbctl update --check` reports an update available, but installation updates OrbStack's CLI, GUI, kernel, Docker, and other global components. Updating it can affect other user-owned machines and therefore requires explicit authority; name-based deletion and private-storage mutation remain prohibited.

## Authorized OrbStack update and exact-ID deletion retry

- Preserved the original v2.2.2 diagnostic packet at `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/orbstack-delete-crash-2026-08-21`; every indexed file still passes `SHA256SUMS` verification.
- Updated OrbStack from v2.2.2 to signed and Apple-notarized v2.2.3 build 20963 using the official Apple-silicon release. The installed CLI reports `2.2.3 (2020300)`, commit `c83556b0ef8f1ba9a33abbb194622b6b7a1c0307`.
- Pre/post semantic inventory verification preserved all four immutable guest IDs and configurations. After restart, `ubuntu`, the rehearsal guest, and the write-UI diagnostic guest returned to running; predecessor `01M0F27Z1GZQ7SQF07XH9M3VQT` remained stopped.
- `orbctl doctor` passed with only the pre-existing Homebrew Docker PATH warnings. The dependency archive independently retained SHA-256 `94bef9e1c3ad97cdf52f3593a5f12f7d4d42bfacb534a6b28c44fe9d8db8f3b1`.
- The authorized exact-ID retry `orbctl delete --force 01M0F27Z1GZQ7SQF07XH9M3VQT` still exited 2 with the same nil-pointer panic at `scli/cmd/delete.go:141`. The exact target remains present and stopped; all three unrelated guests remain present and healthy.
- Preserved the v2.2.3 retry as a separate checksum-bound addendum at `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/orbstack-delete-crash-2026-08-21-v2.2.3-addendum`; `SHA256SUMS` digest `a2fd4836cc9538e57c4588c9e0a91cc2c9b6a83138f5e08c68230898201bd3ab`.
- No name-based deletion, private-storage modification, canonical provisioning, or `run-rc` attempt followed. The runtime-acceptance goal remains paused because the explicitly required predecessor replacement condition is not satisfied.

## Review (2026-08-21 13:21:17 +0700) - system

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend-local-rc-runtime-acceptance`
- Branch: `test/local-rc-1-runtime-acceptance`
- Scope: LOCAL-RC-1 predecessor retirement, canonical replacement, identity binding, diagnostics, and vendor escalation boundary
- Commands Run: repository root/branch/status/log inventory; RepoPrompt Context Builder subsystem review; bounded architecture/source/runbook/test/log reads; focused pytest selection (`18 passed, 193 deselected`); pure stopped-target classifier probe; packet checksum verification; `orb`/`orbctl` binary/hash/help comparison; bounded manager-log inspection; `orbctl report --help`; OrbStack issue-template and release-note inspection; public and account-owned issue searches; independent Terra review.
- Sources: `AGENTS.md`; `CONTEXT.md`; `README.md`; `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`; `ops/control-plan-read-local/orchestrate.py`; `ops/control-plan-read-local/tests/test_orchestrate.py`; `ops/control-plan-read-local/tests/test_local_artifacts.py`; current and historical Coding Logs; the external v2.2.2 packet and v2.2.3 addendum; OrbStack v2.2.3 release notes and official GitHub bug-report template.

### As-Is Pipeline Diagram
- Operator revalidates the preserved predecessor's immutable ID, fixed name, exact shape, owner/candidate/dependency/stage/checksum state; re-reads inventory; invokes the external OrbStack CLI to delete that exact ID; proves old ID/name absence; then `orchestrate.py provision` sees the fixed name as `missing`, creates a Debian 12 ARM64 isolated guest by fixed name, bootstraps it through name-addressed commands, and only later `run-rc` pins the new Orb ID plus `/etc/machine-id` around every phase, stage, and collection. Today the external exact-ID delete panics before a manager deletion receipt, leaving the stopped predecessor present; the classifier raises `machine_shape_not_accepted`, so provisioning correctly cannot start.

### High-Level Assessment
- No critical safety failure occurred: the exact predecessor remains stopped and unchanged, unrelated guests remain intact, and no canonical provision or acceptance attempt followed the panic.
- The fail-closed pause is correct and required by the runbook.
- The lifecycle is nevertheless incomplete. The instruction's mandatory vendor-escalation branch was not executed, and the repository has no supported transition past a broken external exact-ID delete.
- Stable identity is strong after provisioning but predecessor retirement is manual, external, untested, and non-atomic relative to replacement creation.
- The current packet is useful but not yet a complete OrbStack vendor submission: it lacks a vendor issue/receipt and the official private diagnostic-report value required by OrbStack's issue template.

### Strengths
- The runbook explicitly requires immutable-ID deletion, a final inventory reread, absence proof, and fail-closed stop if Orb cannot address the stable ID; it prohibits name-only deletion and replay.
- `run_rc()` repeatedly validates Orb ID, fixed name/shape, owner/candidate/dependency state, and `/etc/machine-id` before and after operations and evidence collection.
- Both crash attempts preserved the target and unrelated guest state, and both evidence directories are mode 0700 with mode-0600 files and valid checksum indices.
- The decision not to use the historical name fallback or private VM storage was correct.

### Key Risks / Gaps (severity ordered)
CRITICAL
- No findings. The system stopped before destructive or acceptance state could diverge.

HIGH
- Required vendor escalation was not completed. No issue exists in `orbstack/orbstack` from the authenticated account, and neither packet contains an issue URL, vendor report ID, or submission receipt. `orbctl report --help` only describes gathering/uploading the private diagnostic value used by the official issue template; retaining local files is not submission.
- Exact-ID retirement is an external single point of failure. `orchestrate.py` exposes build/provision/run/collect actions but no immutable-ID retirement guard, delete transaction, or absence verifier (`ops/control-plan-read-local/orchestrate.py:3658-3901`). The runbook's serialized validate/read/delete/read sequence is procedural only (`docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md:234-242`). When OrbStack panics, the repository has no supported replacement path.
- Provisioning cannot classify the current stopped predecessor as a validated collision. `_classify_machine_inventory()` accepts only `missing` or exact-shape `running` as `ready`; the exact stopped record collapses to `machine_shape_not_accepted` (`orchestrate.py:428-458`). `_provision()` creates only on `missing` and otherwise validates a running guest before refusing reprovision (`orchestrate.py:1115-1180`). This is safely blocking but operationally opaque and offers no audited handoff state.
- Retirement-to-creation serialization is non-atomic. The operator proves absence outside the repository, `_provision()` checks the fixed name and calls `orb create`, then bootstraps by fixed name before the new Orb ID and machine ID are pinned. There is no repository lock or captured create receipt binding the exact newly created ID before guest mutation (`orchestrate.py:881-885,1148-1216,1491-1555`).

MEDIUM
- The v2.2.3 remediation hypothesis was overstated. Official release notes name crashes with non-POSIX login shells, not machine deletion. Updating was a valid bounded compatibility experiment after global authorization, but there was no evidence that it was a probable fix for `delete.go:141`.
- The vendor packet is split and incomplete for the latest reproduction. The v2.2.2 packet has raw build provenance, full target JSON, and bounded manager evidence. The v2.2.3 addendum has the panic and summarized post-state, but no raw v2.2.3 build-provenance file, fresh full target JSON, bounded post-upgrade manager-log excerpt, official `orb report` value, or vendor-submission receipt.
- Tests cover exact create shape, owner/provision state, stopped RC rejection, immutable-ID drift, and run-wide machine-ID pinning, but not predecessor classification, deletion panic/failure, immutable ID/name equivalence guarding, absence proof, fixed-name collision/race, or old-ID-to-new-ID handoff. Provision tests mock only `missing → ready` (`test_orchestrate.py:183-314,2245-2417,3074-3130,3254-3304`).
- Guest execution remains name-addressed after immutable-ID validation. `_build_guest_command()` uses `orb -m <fixed-name>` (`orchestrate.py:386-404`), while `run_rc()` detects drift before/after commands (`orchestrate.py:3375-3409`). Detection is strong, but the command itself is not targeted by the pinned ID.

LOW
- Historical Coding Logs record a separately authorized validated-name fallback that succeeded after the same panic. The current runbook and current user instruction supersede it, but future operators could misread that history as a standing workaround. The current contract must remain explicit: no name-only deletion.
- `orb` and `orbctl` are byte-identical binaries with identical delete help, so treating them as independent fallback surfaces would be false diversity.

### Drift Matrix
- Intended: submit diagnostics after the repeat panic. Implemented: checksum-bound local packets only. Impact: vendor never receives the defect and no fix/report identity exists. Fix direction: generate the official diagnostic value, submit one issue, and store the receipt.
- Intended: delete only a revalidated stable ID. Implemented: manual external CLI call with no repository transaction. Impact: lifecycle depends on an untested third-party destructive edge and manual TOCTOU controls. Fix direction: keep fail-closed now; later add an exact-ID-only guarded retirement action after vendor behavior is fixed.
- Intended: distinguish a preserved predecessor from malformed inventory. Implemented: stopped exact-shape guest becomes `machine_shape_not_accepted`. Impact: poor operability and no machine-readable blocked-predecessor state. Fix direction: structured inventory classification with an explicit `validated_stopped_predecessor` result.
- Intended: bind the replacement identity before mutation. Implemented: create and bootstrap are fixed-name addressed; ID/machine-ID pinning begins later. Impact: a create/name race is detected late rather than prevented. Fix direction: capture the new ID immediately after create and use immutable addressing wherever vendor CLI support permits.
- Intended: vendor-ready current diagnostics. Implemented: complete v2.2.2 packet plus partial v2.2.3 addendum. Impact: latest-version reproduction is not self-contained and misses OrbStack's required private diagnostic value. Fix direction: add raw v2.2.3 metadata/JSON/log excerpt and official report receipt under a fresh checksum index.
- Intended: update only as evidence-backed remediation. Implemented: generic CLI crash notes were treated as supporting a deletion-fix possibility. Impact: confidence in the upgrade path was higher than the evidence warranted. Fix direction: label future upgrades as version-elimination experiments unless release notes or vendor confirmation name the defect.

### Nit-Picks / Nitty Gritty
- The packet calls v2.2.3 release notes “CLI crash fixes”; the precise note is limited to non-POSIX login shells and should be quoted narrowly.
- Manager-log evidence for the latest attempt is still recoverable from rotated logs, but it was not frozen into the addendum before the review.
- The pure current-target classifier probe returns `OrchestrationError machine_shape_not_accepted`, confirming the stopped state is indistinguishable from a wrong architecture/configuration at the operator-facing boundary.

### Tactical Improvements (1–3 days)
1. Submit one OrbStack bug report using the official template. Done when a public issue URL and private diagnostic report value/receipt are recorded without exposing private diagnostic contents.
2. Complete a self-contained v2.2.3 vendor addendum. Done when raw version/build provenance, exact full target JSON, bounded before/after manager lines, panic, post-state, and a newly verified checksum index exist.
3. Update the active runbook incident note after submission. Done when it names the issue, pins the blocked exact ID/builds, explicitly rejects the historical name fallback, and states that canonical provisioning remains prohibited pending a supported exact-ID fix.
4. Add tests-first structured stopped-predecessor classification. Done when exact stopped ID/name/shape is distinguishable from malformed inventory while `provision` still refuses creation or adoption.
5. Specify a pure immutable-ID retirement guard and absence-verifier contract without enabling deletion. Done when tests cover duplicate/missing/changed ID, name/shape drift, state drift, and unrelated inventory preservation.

### Strategic Improvements (1–6 weeks)
1. Add a separately authorized `retire-predecessor` lifecycle action only after OrbStack fixes or documents exact-ID deletion. Migration: pure guard/receipt model → dry-run evidence → exact-ID delete behind explicit confirmation → post-delete ID/name absence proof. Rollout: diagnostic guest first, then rehearsal predecessor, then canonical only under new authority; any drift fails closed.
2. Pin the replacement immediately after creation. Migration: parse the post-create inventory into one exact new ID → persist an immutable host-side creation receipt → require all bootstrap commands to be bracketed by ID/name checks and use ID addressing if officially supported. Rollout: unit tests, mocked race tests, rehearsal run, then canonical.
3. Add a vendor-diagnostic evidence collector separate from acceptance evidence. Migration: sanitized manifest schema → bounded log/version/inventory collectors → checksum index → optional official diagnostic token reference. Rollout: local fixture tests and privacy review before use.

### Big Architectural Changes
- No broad redesign is justified. A narrow retirement transaction and earlier immutable-ID capture address the recurring failure without weakening the fixed-name or pristine-guest contracts.

### Open Questions / Assumptions
- OrbStack's private source is unavailable, so the exact nil field at `delete.go:141` cannot be established from the stripped binary. The absence of a manager deletion receipt supports, but does not prove beyond all doubt, a CLI-side pre-RPC failure.
- Whether `orb -m` officially accepts an immutable machine ID for all guest commands must be confirmed from vendor documentation before changing dispatch.
- Vendor submission and generation/upload of the official private diagnostic report are external writes and were not performed during this review-only request.

## 2026-08-21 19:59 ICT — Explicitly authorized guarded name deletion succeeded

- The user explicitly revoked the exact-ID-only operational rule for this predecessor and authorized deletion by name. This was applied as a narrow runtime override for the already identified predecessor, not as an unreviewed permanent change to the repository runbook or post-provision RC identity protections.
- Immediately before deletion, fresh JSON inventory proved exactly one name match and exactly one ID match: stopped `munbon-control-plan-local` ID `01M0F27Z1GZQ7SQF07XH9M3VQT`, Debian bookworm ARM64, isolated/network-isolated, user `munbonlocal`, 8192 MiB, 4 CPUs, and 40 GiB. The normalized live record and preserved `target-info.json` both had SHA-256 `d687f3ff23914903221688aa1f7cd7a98e5560efabbb479371fca32271e78a69`.
- Both crash packets passed their checksum indices immediately before deletion. The locked dependency archive retained SHA-256 `94bef9e1c3ad97cdf52f3593a5f12f7d4d42bfacb534a6b28c44fe9d8db8f3b1`.
- The single authorized command `orbctl delete --force munbon-control-plan-local` exited 0 without panic. Current `vmgr.log` records `time="08-21 12:58:31" level=info msg="deleting container" container=munbon-control-plan-local`; host local time was 2026-08-21 19:58 ICT.
- Immediate post-read proved both the old immutable ID and canonical name absent. Unrelated guests remained present and running by their immutable IDs: `ubuntu` `01K2MR34Y1YEF4J11ECPCNQN3C`, write-UI diagnostic `01KZKJMR2PG4Z4X7DYHDYTEX0C`, and rehearsal `01M0EX2FYE4XX511KHB5MCBDP8`.
- No canonical replacement guest was provisioned and no acceptance command was run in this deletion step.
