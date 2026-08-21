# Coding Log: local RC runtime resume

## Session ownership and frozen identities

- Resume authority: the user explicitly resumed the active goal on `2026-08-21`.
- Goal attachment SHA-256: `e2d670d3f09db6f9ab4130a10272b993cd92ba1af0e06ecdb20be7764b261a3b`.
- Lifecycle worktree: `/Users/subhajlimanond/dev/munbon2-backend-local-rc-runtime-acceptance`.
- Branch: `test/local-rc-1-runtime-acceptance`.
- Backend candidate: `ce309918ef5a799ba37c561b470d3c5708d6fca2`; `HEAD == main == origin/main` at resume.
- Frontend candidate: `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`; `HEAD == main == origin/main` at resume.
- Both origins use SSH. The frontend primary checkout has unrelated user-owned dirty files which remain untouched.
- Dependency archive: `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/dependencies-ce309918ef5a799ba37c561b470d3c5708d6fca2-067b3e22401854f8c6d6db42dc0c5c1872fca6f8.tar.gz`.
- Dependency archive SHA-256: `94bef9e1c3ad97cdf52f3593a5f12f7d4d42bfacb534a6b28c44fe9d8db8f3b1`.
- Retired predecessor: `munbon-control-plan-local` / `01M0F27Z1GZQ7SQF07XH9M3VQT`.
- The predecessor was deleted once by exact name after a final singleton/stopped/identity-equivalence guard. Exact ID and name are now absent. Unrelated OrbStack guests were preserved.
- Canonical replacement name: `munbon-control-plan-local`. Its new stable Orb ID and `/etc/machine-id` must be recorded immediately after provisioning and must differ from the retired identity.
- Canonical acceptance attempt ceiling: exactly one `run-rc` invocation. Provisioning/bootstrap failure does not consume that attempt; any `run-rc` invocation does.
- Promotion, deployment, activation, post-deployment verification, and rollback execution remain outside this local runtime-acceptance lifecycle.

## Plan Draft A: runtime-first exact-candidate acceptance

### Overview

Validate the already-built dependency closure, provision one pristine canonical guest for the frozen candidates, lock its immutable runtime identity, and execute the canonical `LOCAL-RC-1` workflow exactly once. Preserve the first outcome without retry or in-place repair. Only after an independently validated PASS, update the runbook through a test-first documentation contract and complete review, GitHub delivery, exact local-main landing, and worktree cleanup.

### Files to change

- `.codex/coding-log.current`: point lifecycle tooling to this resume log.
- This Coding Log: record planning, immutable inputs, runtime receipts, evidence hashes, test/gate/review results, PR/merge identities, and cleanup.
- `ops/control-plan-read-local/tests/test_local_artifacts.py`: after PASS, add the smallest test that requires the exact accepted runtime status.
- `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md`: after the expected RED, replace only the stale LOCAL-RC-1 status with exact PASS facts and explicit non-production boundaries.
- Production files are not pre-authorized. If the one-shot run proves a source defect, the primary owns the RED contract and a separately locked Luna-Max slice owns the smallest production allowlist.

### Execution outline

1. Revalidate worktree ownership, exact SSH origin heads, archive existence/digest/content, OrbStack health, canonical-name absence, unrelated guest preservation, and fresh evidence destinations.
2. Create one unique session root below `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/`, with absent `success-attempt-1`, `partial-failure-attempt-1`, and `bootstrap-failure` children.
3. Invoke `orchestrate.py provision` once with the exact candidates, dependency archive and digest, and bootstrap-failure destination.
4. If provisioning succeeds, immediately record the exact single canonical name match, new stable Orb ID, `/etc/machine-id`, owner metadata, state, candidate identities, and archive digest. Repeat inventory once to detect drift before acceptance.
5. Invoke `orchestrate.py run-rc` exactly once with the locked new guest ID, exact candidates, exact dependency digest, Bangkok as-of date `2026-08-21`, and fresh success destination.
6. Stop on the first outcome. Never rerun, replay, repair, or reprovision this candidate/guest attempt.
7. If the attempt fails before automatic evidence publication and bounded partial collection remains eligible, invoke `collect-rc-partial-failure` at most once into the separate absent partial destination. If all stages/finalization passed and collection alone failed, `collect-rc` is the only eligible one-time collection recovery; it is not a run retry.
8. Independently validate the resulting archive and live guest. PASS requires exact identities, all ordered stages, RC PASS, checksum closure, final darkness, revoked sessions, expected listeners/processes/readiness, stable guest identity, and no post-command state drift.
9. After PASS, add the runbook contract test, confirm expected RED against stale text, update the runbook, run focused and full gates three consecutive times, perform QCHECK and formal `g-check`, and remediate any production finding only through a new bounded Luna-Max slice.
10. Commit and push over SSH, create a standard GitHub PR, verify exact head and mergeability, admin-merge under the standing zero-step billing-lock policy after local acceptance/review, land the exact merge SHA on local `main`, verify post-merge artifacts, and safely remove only this lifecycle worktree and branch.

### Behavioral contracts and tests

- Provisioning must reject an existing canonical name and must bind the new guest to exact backend/frontend/archive identities.
- RC execution must validate stable Orb ID and machine ID before phases and stages, stop on the first failure, publish no false PASS, and restore dark flags and sessions.
- Existing identity, stage-order, checksum, compensation, darkness, interruption, and frozen-ledger tests remain authoritative.
- `test_all_stages_runbook_records_exact_local_rc_acceptance` will pin the final accepted identities, evidence/index digest, PASS verdict, and non-production boundary.
- Any observed source defect receives a minimal independently meaningful RED before a production handoff; the failed canonical attempt remains failed even if source is later fixed.

### Decision completeness

- Goal: one authoritative, independently validated LOCAL-RC-1 result for the exact frozen backend/frontend/dependency candidates, followed by durable documentation and the authorized source lifecycle.
- Non-goals: predecessor evidence reuse, acceptance retry or in-place repair, frozen nine-stage ledger reinterpretation, AWS work, deployment, or activation.
- PASS: pristine replacement guest; exact stable identities; ten ordered live stages plus RC PASS; complete inner/outer checksum closure; final merged/default flags false; acceptance sessions revoked; expected PM2 processes, listeners, readiness and inventories; unchanged post-command outer index; clean review; merged PR; exact local-main landing; owned worktree removal.
- Failure: provisioning failure preserves bootstrap evidence and does not consume RC; any `run-rc` result is authoritative and consumes the sole attempt; identity/checksum/order/darkness/session uncertainty fails closed; no PASS is inferred from a prefix or from historical 9/9 evidence.
- Public interfaces: no API, schema, migration, topic, CLI, or environment change is planned.
- Rollout/backout: isolated OrbStack only. Backout means verified darkness and session cleanup, never erasing evidence or relabeling a failed attempt.

## Plan Draft B: full-source-gates before runtime

### Overview

Rerun the complete Python, Node, formatting, lint, syntax, and integrity gates plus a source review before provisioning. Then execute the identical one-shot runtime plan. This can catch static regressions before consuming the sole runtime attempt, but repeats gates already run on the same candidate and delays the only step capable of proving environment-bound behavior.

### Trade-offs

- Advantage: maximizes static confidence before provisioning and one-shot runtime execution.
- Cost: substantial duplicate work on an unchanged reviewed candidate; may add machine load and time without increasing runtime evidence quality.
- The runtime identity, no-retry, evidence, failure, test-first documentation, review, delivery, and cleanup contracts are identical to Draft A.

## Unified execution plan

Use Draft A with a bounded source sanity preflight rather than a full duplicate matrix before provisioning. The candidate already passed its source-delivery gates and the dependency closure is exact; the highest-value next evidence is pristine runtime acceptance. Before the one-shot run, verify exact SHAs/remotes, archive checksum/content, critical harness syntax and targeted orchestrator tests, OrbStack health/name absence, and destination freshness. Reserve the complete three-round gate matrix for the final post-PASS documentation candidate or for a proved source remediation.

### Wiring verification table

| Component | Entry point | Registration/config load | Contract checked |
|---|---|---|---|
| Host controller | `ops/control-plan-read-local/orchestrate.py:main()` | `provision`, `run-rc`, and collection actions | exact CLI candidate/archive/guest/date bindings |
| Guest RC phases | `run_rc()` | guest `run-stage-suite.py --rc-phase` | preflight/finalize identity, darkness, cleanup schemas |
| Ten live stages | `run_rc()` stage loop | `STAGE_ORDER` and `_run_stage()` | ordered stop-on-first-failure manifests |
| Browser write proof | WRITE-ACT stage | `run-write-browser.js` | mutation-attempt inventory and session/dark evidence |
| Evidence publication | `collect_rc()` / `finalize_rc_collection()` | automatic run collection or narrow eligible recovery | exact archive inventory and inner/outer checksum closure |
| Durable status | local-artifact test and runbook | pytest discovery and documentation gate | exact PASS identities without AWS/deployment claims |

### Validation checklist

- [ ] Frozen candidates and SSH origin heads unchanged.
- [ ] Dependency archive independently rehashed and structurally validated.
- [ ] Canonical name absent; unrelated guests unchanged.
- [ ] Unique session root and all three evidence children fresh/absent.
- [ ] Pristine guest provisioned once; new Orb ID and machine ID locked.
- [ ] One and only one `run-rc` invocation recorded.
- [ ] First outcome preserved without retry/repair.
- [ ] Collected archive independently validated, including recomputed inner and outer hashes.
- [ ] Live post-command identity, darkness, process, readiness, listener, and session state match evidence.
- [ ] PASS-only test-first runbook update completed.
- [ ] Focused/full gates pass three consecutive times on unchanged candidate.
- [ ] QCHECK and formal `g-check` findings resolved or explicitly dispositioned.
- [ ] PR head, admin merge SHA, origin/main, and local main exactly reconciled.
- [ ] Only the lifecycle worktree/branch removed; user-owned state preserved.

## Resume evidence

- RepoPrompt Context Builder completed a repository-grounded plan on `2026-08-21`, chat `resume-local-rc-1-75F716`.
- The active goal tracker still reports its earlier blocked state, but the user's explicit `resume /goal` is the current execution authority; this discrepancy does not broaden scope.
- Pre-provision source sanity: `py_compile` passed for the orchestrator and stage suite; the targeted provisioning/RC identity/collection pytest scope passed `54 passed, 186 deselected`.
- Dependency preflight independently recomputed archive SHA-256 `94bef9e1c3ad97cdf52f3593a5f12f7d4d42bfacb534a6b28c44fe9d8db8f3b1`, verified all `968` indexed payload entries, and confirmed the schema-v2 manifest binds backend `ce309918ef5a799ba37c561b470d3c5708d6fca2`, frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`, Debian 12 ARM64, Node `22.23.1`, npm `10.9.8`, and Python `3.11`.
- OrbStack preflight: v2.2.3 running; canonical name match count `0`; unrelated rehearsal, diagnostic, and Ubuntu guests remained present and running at their preserved IDs.
- Fresh session root: `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/2026-08-21-local-rc1-ce309918ef5a-067b3e224018-20260821T131700Z-9c64277f`.
- `SESSION.json` records the frozen inputs, zero attempts consumed, preserved guest inventory, and three fresh child destinations. The success, partial-failure, and bootstrap-failure child paths were absent before provisioning.
- Provisioning completed successfully in its single invocation; no bootstrap-failure directory was published and no RC attempt was consumed.
- Locked replacement guest identity: Orb ID `01M0J7GX1E7CBNQWGM89KSH4F4`, `/etc/machine-id` `6db94a5d8cc14171a1fab9495a055ae0`, fixed canonical name `munbon-control-plan-local`, running Debian 12 ARM64, isolated network, 8 GiB RAM, 4 CPUs, 40 GiB disk.
- The new Orb ID differs from retired ID `01M0F27Z1GZQ7SQF07XH9M3VQT`. Two consecutive inventories returned the same singleton ID and preserved all three unrelated guests.
- Guest owner and provisioning state are `ready` and bind the exact backend/frontend/dependency identities. `GUEST-IDENTITY.json` preserves the complete lock receipt.
- Final RC preflight passed: all three evidence child paths remained absent, archive digest was unchanged, canonical singleton ID/state and machine ID were stable, and owner metadata remained exact. The sole `run-rc` attempt was marked consumed at `2026-08-21T13:22:49Z` immediately before invocation.

## Canonical attempt 1: authoritative preflight failure

- The sole `run-rc` invocation stopped at RC preflight with `FAIL orchestration: rc_preflight_failed`; no live stage ran and the success destination remained absent.
- The guest failure manifest gives the exact gate `backend_source_identity_stale`, timestamp `2026-08-21T13:23:09Z`, and the correct candidate, dependency, Orb ID, and machine-ID bindings.
- Exactly one eligible `collect-rc-partial-failure` invocation succeeded. Its summary records verdict `FAIL`, phase `preflight`, passed `[]`, failed `[LOCAL-RC-1]`, all ten live stages unreached, `acceptance_evidence=false`, and `campaign_ledger_eligible=false`.
- Independent checksum verification passed for both `RC-PARTIAL-SHA256SUMS` and `RC-PARTIAL-OUTER-SHA256SUMS`. The outer index SHA-256 is `0e5863d47c595c30f2a51ffe884063a63a7278a2403a9a574c7942601f659cf1`.
- The failed guest remains preserved and unmodified. Its backend HEAD is the exact candidate and frontend is clean, but backend status contains exactly two untracked symlinks: `services/flow-monitoring/venv -> .venv` and `services/scheduler/venv -> .venv`.
- Root cause: bootstrap deliberately creates those two runtime interpreter links, while root `.gitignore` contains directory-only pattern `venv/`. Git does not apply a directory-only pattern to a symlink, so the harness's strict `git status --porcelain --untracked-files=all` source-identity check correctly reports drift.
- Preflight stopped before the PM2 stage check; live inspection found only the bootstrap PM2 daemon and loopback infrastructure listeners. No acceptance PASS or runtime-stage result is claimed.

## Remediation slice S-RC-VENV-IGNORE

- Locked behavior: the two bootstrap-created `venv -> .venv` links must be ignored by Git so a freshly provisioned exact source checkout remains clean; the strict source-identity checker itself must not be weakened.
- Primary-owned test: `test_bootstrap_runtime_venv_links_are_ignored_by_source_identity_gate` constructs the exact symlink shape under a temporary Git repository using the repository `.gitignore` and requires both paths from `git check-ignore`.
- Expected RED confirmed: the focused test failed with `(returncode, paths) == (1, [])`, proving neither runtime link is ignored.
- Production allowlist: `.gitignore` only. Protected paths: every other production/source file, all tests, both Coding Logs, pointer file, evidence archives, and guest state.
- Wiring: bootstrap creates the two links; Git ignore resolution controls the `git status` consumed by `_verify_source_checkouts()` and `run_local_base()`.
- Scoped GREEN command: `python3 -m pytest -q ops/control-plan-read-local/tests/test_local_artifacts.py::test_bootstrap_runtime_venv_links_are_ignored_by_source_identity_gate`.

### S-RC-VENV-IGNORE rejected GREEN

- Luna-Max changed one `.gitignore` rule from directory-only `venv/` to bare `venv`; the ownership receipt verified for role `luna_implementer`, model `gpt-5.6-luna`, effort `max`, and exact `.gitignore` SHA-256 `47b1c80516564c5a4b7c2552bfa5bab179e6e0d29f4c93c300baf506800c6b13`.
- Primary GREEN was `1 passed`; related source/bootstrap scope was `11 passed, 552 deselected`; the complete interim matrix was Python `820 passed`, Node `51 passed`, with Black, Ruff, compileall, Bash/JavaScript syntax, and whitespace integrity passing.
- Independent Terra QCHECK rejected the design: bare `venv` ignores any file or symlink with that basename at any depth, so a wrong-target or replaced link could disappear from Git status and weaken the fail-closed drift contract.
- Disposition: do not deliver the broad ignore. Restore `.gitignore` and accept the bootstrap artifacts only inside the strict source checker after verifying the exact two backend paths, their symlink type, and literal `.venv` targets. Frontend remains exception-free; all other tracked/untracked drift remains fatal.

## Remediation slice S-RC-VENV-STRICT

- Primary removed the obsolete ignore-behavior test and added exact source-checker contracts covering: valid pair acceptance; missing/extra/tracked drift; wrong-target symlink; regular-file replacement; frontend rejection; and NUL-delimited porcelain status invocation.
- Expected RED confirmed: focused source-preflight scope produced `3 failed, 5 passed, 517 deselected`. The valid pair still failed as backend drift, frontend never reached its own rejection, and the status command lacked the locked NUL-delimited shape.
- Production allowlist: `.gitignore` solely to restore `venv/`, plus `ops/control-plan-read-local/run-stage-suite.py` for the narrow verified exception. No bootstrap/orchestrator or other runtime edit is authorized.
- Scoped GREEN: `python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py -k 'source_preflight'`.

### Primary QCHECK follow-up

- S-RC-VENV-STRICT receipt verified for Luna-Max and exact allowlisted hashes. Focused GREEN was `8 passed, 517 deselected`; the post-format complete matrix passed Python `826`, Node `51`, Black, Ruff, compileall, Bash/JavaScript syntax, whitespace integrity, and three consecutive focused rounds.
- Primary QCHECK found an additional fail-open edge: original `venv/` legitimately hides an actual directory. If a required runtime symlink were missing or replaced by a directory, Git could report an empty status and the first strict implementation would accept it without filesystem validation.
- Added a parameterized test requiring `backend_source_identity_stale` for both missing-link and directory-replacement cases under an otherwise clean Git status. Final contract now requires both exact `.venv` symlinks for every accepted backend status, including empty status.
- Luna-Max S-RC-VENV-ALWAYS-VERIFY receipt passed ownership validation; focused GREEN became `10 passed, 517 deselected`. The complete unchanged-candidate matrix passed Python `828`, Node `51`, Black, Ruff, compileall, Bash/JavaScript syntax, whitespace integrity, and three consecutive focused rounds.
- Independent final QCHECK found no CRITICAL/HIGH/MEDIUM issue. Its LOW test gap was resolved by adding an explicit positive clean-status + valid-link test; malformed non-NUL porcelain rejection was also added. The residual boundary is intentional: link type and literal target are source-identity concerns, while ignored `.venv` contents/existence are validated by bootstrap dependency installation and runtime readiness.
- Final post-QCHECK matrix: Python `830 passed`, Node `51 passed`; focused source-preflight `12 passed, 517 deselected` for three consecutive rounds; Black, Ruff, compileall, Bash/JavaScript syntax, and whitespace integrity passed.

## Review (2026-08-21 20:45:15 +0700) - working-tree

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-local-rc-runtime-acceptance`
- Branch: `test/local-rc-1-runtime-acceptance`
- Scope: staged working tree at baseline `ce309918ef5a799ba37c561b470d3c5708d6fca2`; RepoPrompt snapshot `2026-08-21/2042` plus the final primary-owned LOW-gap tests.
- Commands Run: staged status/stat and targeted complete production/test diffs; RepoPrompt staged artifact publication; focused/full pytest; Node test inventory; Black; Ruff; compileall/py_compile; Bash and JavaScript syntax; whitespace integrity; three consecutive focused rounds; Luna ownership snapshot/receipt verification for all production slices; independent Terra QCHECK.
- RepoPrompt Context Builder review fallback: the bound tab reported `Context Builder is already MCP-controlled`; one Oracle review attempt was cancelled. Per g-check fallback policy, review continued with bounded staged artifacts, targeted reads/searches, primary QCHECK, and independent Terra QCHECK without retrying the unavailable provider.

### Findings

CRITICAL

- None.

HIGH

- None.

MEDIUM

- None.

LOW

- None remaining. Independent QCHECK's clean-status positive-case gap and optional malformed non-NUL status case were both added and passed.

### Open Questions / Assumptions

- The source-identity contract validates the two runtime entries as symlinks with the literal target `.venv`; it intentionally does not hash ignored virtual-environment contents. Offline dependency manifest/checksum validation, pip checks, and runtime readiness own that separate integrity boundary.
- The first canonical attempt remains an authoritative preflight FAIL and cannot become PASS through this source remediation.

### Recommended Tests / Validation

- Deliver this remediation as a new exact backend candidate, rebuild and independently validate a candidate-bound dependency archive, then provision a new pristine canonical guest.
- Execute one fresh-candidate `run-rc` attempt with a new guest ID/machine ID and fresh success/failure destinations. Do not reuse or repair the failed candidate/guest attempt.
- After PASS, complete the separate test-first runbook status update and rerun the complete final gate/review matrix.

### Rollout Notes

- No API, schema, migration, feature-flag default, deployment, AWS, or activation change is included.
- Failed-attempt evidence remains checksum-valid, `acceptance_evidence=false`, and campaign-ledger-ineligible.
- Formal g-check disposition: clean; no actionable finding remains before source delivery.

## Source delivery: source-cleanliness remediation

- Candidate commit: `1d733c4f8e4b904a650ae9dcebdd5ce3f74b8f4b` (`fix(control-plan): validate bootstrap runtime links`).
- SSH push succeeded after correcting the GitHub CLI transport preference to `ssh` and independently confirming non-interactive SSH authentication.
- PR: `#197` (`https://github.com/SubhajL/munbon2-backend/pull/197`). Exact head matched candidate `1d733c4f8e4b904a650ae9dcebdd5ce3f74b8f4b`; PR was mergeable and not draft.
- Admin merge completed under the standing zero-step billing-lock policy; no hosted job is called passing. Merge SHA: `5333e7ef7553832e438e3db9b0d991fdcf86c784`.
- Exact landing: primary checkout `HEAD == main == origin/main == 5333e7ef7553832e438e3db9b0d991fdcf86c784`, clean.
- Runtime acceptance remains unaccepted. The next candidate is backend `5333e7ef7553832e438e3db9b0d991fdcf86c784`, frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`; it requires a new candidate-bound dependency archive, a new pristine guest, and fresh evidence destinations.

## Replacement dependency archive

- Built exactly once on the preserved diagnostic builder for backend `5333e7ef7553832e438e3db9b0d991fdcf86c784` and frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`.
- Archive: `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/dependencies-5333e7ef7553832e438e3db9b0d991fdcf86c784-067b3e22401854f8c6d6db42dc0c5c1872fca6f8.tar.gz`.
- Outer SHA-256: `abb6173272c436b9f94c4669561ef438eebb679e1fff0609fba81a5ea9782349`.
- Independent validation passed: outer digest matched the builder receipt; every entry in `bundle/SHA256SUMS` verified; the schema-2 manifest binds the exact candidate SHAs, Debian 12 ARM64, Node `22.23.1`, npm `10.9.8`, and Python `3.11`.
- The failed first-attempt guest and its checksum-valid partial evidence remain unchanged. Replacement is authorized only after a guarded identity/evidence preflight, using the user-authorized exact name because OrbStack exact-ID deletion panics.

## Fresh candidate attempt 2: authoritative preflight failure

- Guarded name deletion removed only failed guest `01M0J7GX1E7CBNQWGM89KSH4F4` after exact ID/name/shape/owner and checksum revalidation. The old evidence remained checksum-valid; all unrelated guests remained running.
- Fresh session: `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/2026-08-21-local-rc1-5333e7ef7553-067b3e224018-20260821T135716Z-9e867164`.
- Provisioning completed once with no bootstrap-failure publication. Locked fresh identity: Orb ID `01M0J9TZQ787D9N6C4KRT0DP30`, machine ID `c2b8079f7bdd40b2885cd67ef93d0f63`; both differ from the replaced failed guest.
- Owner/provision state binds backend `5333e7ef7553832e438e3db9b0d991fdcf86c784`, frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`, and dependency SHA-256 `abb6173272c436b9f94c4669561ef438eebb679e1fff0609fba81a5ea9782349`.
- The sole fresh-candidate `run-rc` invocation failed at preflight gate `rc_database_not_clean`; no live stage ran and no success destination was created. Exactly one partial-failure collection succeeded.
- Partial evidence is checksum-valid, records `acceptance_evidence=false`, `campaign_ledger_eligible=false`, all ten stages unreached, and outer-index SHA-256 `6d51ec4ad3e897a8e503d84d57fd5925082c8e9fc2262469771be9c5315a3996`.
- Read-only database inspection proves only `auth` and `public` schemas exist. The exact `_rc_database_clean()` SQL casts its Boolean to text, so PostgreSQL returns `true`; production compares only with `t`. The unit test mocks `t\n`, which does not match the real query result. This is a source-contract defect, not guest/database contamination.
- The failed guest is preserved and will not be retried or repaired. A new source candidate, dependency archive, pristine guest, and evidence namespace are required after test-first remediation.

## Remediation slice S-RC-DB-BOOL

- Locked contract: `_rc_database_clean()` must accept PostgreSQL's two canonical true spellings produced by the supported query shapes (`t` and text-cast `true`) and must reject false or empty/unproven results. It continues to require all four application schemas absent.
- Primary-owned parameterized test covers successful `t\n` and the live reproduced `true\n`, plus rejection of `f\n`, `false\n`, and empty output. Expected RED: `1 failed, 4 passed, 528 deselected`; only the real `true\n` case fails.
- Minimal production allowlist: `ops/control-plan-read-local/run-stage-suite.py` only. Tests, Coding Logs, guest/evidence state, bootstrap, orchestrator, and every other source file are protected.
- Wiring: `_rc_preflight_snapshot()` calls `_rc_database_clean()` before rate/runtime/listener checks; `run-rc` publishes the exact failure gate if this parser rejects the query result.
- Scoped GREEN: `python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py -k 'rc_database_preflight_accepts_absent_application_schemas or rc_database_preflight_rejects_present_or_unproven_application_schemas'`.

### S-RC-DB-BOOL GREEN and QCHECK

- Luna-Max receipt `/tmp/munbon-s-rc-db-bool-receipt.json` passed the g-coding ownership validator: role `luna_implementer`, model `gpt-5.6-luna`, effort `max`, exact sole production path, and production SHA-256 `da962c1e7d7032c87df3ba8632248ffb398ec74a94e606db06babd91752422af`.
- The production change accepts only stripped `t` or `true`; `f`, `false`, empty, malformed/multi-row output, and probe errors remain fail-closed as `rc_database_not_clean`.
- Scoped GREEN passed `5 passed, 528 deselected` for three consecutive rounds before the LOW-gap additions; broader RC database/preflight scope passed `21 passed, 512 deselected`.
- Initial complete matrix passed Python `834`, Node `51`, Black, Ruff, compileall, Bash/JavaScript syntax, and whitespace integrity.
- Independent Terra QCHECK found no CRITICAL/HIGH/MEDIUM issue. It confirmed `auth` and `public` are the intentional pristine baseline and that accepting `t` is harmless compatibility with uncast psql Boolean rendering.
- Both LOW hardening gaps were closed in primary-owned tests: multi-row `true\ntrue\n` is rejected, and `_psql` exceptions normalize to `rc_database_not_clean`. Focused post-QCHECK result: `7 passed, 528 deselected`.

## Review (2026-08-21 21:16:33 +0700) - working-tree S-RC-DB-BOOL

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-local-rc-runtime-acceptance`.
- Branch/baseline: `test/local-rc-1-runtime-acceptance` at `1d733c4f8e4b904a650ae9dcebdd5ce3f74b8f4b`; `origin/main` is `5333e7ef7553832e438e3db9b0d991fdcf86c784`.
- Scope: complete uncommitted production/test/Coding-Log diff; RepoPrompt snapshot `2026-08-21/2112-2`; Context Builder review chat `review-db-boolean-9DFDBD`; independent Terra QCHECK.
- Commands: exact ownership verification; focused tests and three consecutive focused rounds; broader RC preflight tests; full Python/Node suites; Black; Ruff; compileall/py_compile; Bash/JavaScript syntax; whitespace integrity; targeted complete diff inspection.

### Findings

CRITICAL

- None.

HIGH

- None.

MEDIUM

- None.

LOW

- None actionable. Terra's multi-row and probe-exception gaps were added and passed.

### Residual hardening disposition

- RepoPrompt suggested a future real-PostgreSQL transport integration test that creates each prohibited schema. It explicitly classified this as residual hardening, not a current defect.
- Disposition: do not mutate the authoritative failed guest to manufacture integration states. The live read-only exact transport already reproduced `true`; source tests now lock both supported true renderings and all relevant fail-closed outputs. A disposable PostgreSQL integration fixture can be added separately without blocking this narrow source repair.

### Final validation

- Python: `836 passed`; Node: `51 passed`.
- Focused post-QCHECK: `7 passed, 528 deselected`.
- Black, Ruff, compileall/py_compile, Bash/JavaScript syntax, and whitespace integrity: PASS.
- Formal `g-check` disposition: clean; no actionable finding remains.

## Fresh candidate attempt 4: nine stages passed, final-stage rate-budget failure

- Fresh session: `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/2026-08-21-local-rc1-324cfc9f56ba-067b3e224018-20260821T145414Z-49090f32`.
- One provisioning run passed. Locked pristine identity: Orb ID `01M0JD3D6KPD3NRB7BK6511J6B`, machine ID `1e48131c82024e39a1b5f194f73d33fa`, exact backend `324cfc9f56ba07168adbaa500b07c93bd0461bfb`, frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`, and dependency SHA-256 `6ae49bc88af0c5e3c10fc05be0c821c02548d9d174eb14385de7239a0889488a`.
- The sole `run-rc` invocation passed strict preflight and the first nine current stages, then failed `LOCAL-WRITE-ACT-1` at `conflict_not_409`. Restoration passed: BFF, scheduler, frontend, dark rendering, operator logout, and refresh revocation all returned to the required dark/closed state.
- Read-only BFF access logs prove the stale-conflict request returned `429`. The same operator consumes three rate-counted foundation requests, three write-UI requests, two persist-only requests, and three write-activation requests: request 11 exceeded the implicit 10-per-300-second default before repository conflict validation could emit `409`.
- The sole partial-collection invocation passed stream and extraction but failed publication at `rc_partial_evidence_inventory_invalid`. The failed frontend context retained `.frontend-write-activation-armed.log` (`13197` bytes, SHA-256 `d0f5a12c9d708691912d10a1ef416807e154d105abdf7650b0ec13f8b40175d7`), while the strict collector accepts only indexed artifacts. No collection retry occurred.
- Diagnostic-only packet `diagnostic-attempt-1` preserves the exact failure manifest, bounded manager-log status sequence, root-cause derivation, and collector failure. All files pass `SHA256SUMS`; checksum-index SHA-256 is `dc84e9901875984d701d85b6d8af8697e763fedb7c7553ee77016567406e7254`. It is explicitly not acceptance evidence.
- The failed guest remains preserved and was not retried, repaired, or otherwise mutated after failure.

## Remediation slice S-RC-RATE-COLLECTOR

- Locked rate contract: pristine local bootstrap must explicitly set `PLANNING_DEPTH_WRITE_LIMIT=11`, derived from the current stage request counts `3 + 3 + 2 + 3`. This changes only the canonical local guest configuration; BFF service defaults and production source remain unchanged.
- Locked collector contract: `_frontend_server()` must stop the child process and remove its transient hidden log on both success and body failure, preserving the existing exact partial-evidence inventory rather than relaxing it.
- Primary-owned RED: `test_bootstrap_budgets_every_rate_counted_rc_write_request` failed with missing value (`None != "11"`); `test_frontend_server_removes_transient_log_after_body_failure` failed because the hidden log remained. Exactly two expected failures were confirmed before production handoff.
- Production allowlist: `ops/control-plan-read-local/bootstrap-linux.sh` and `ops/control-plan-read-local/run-stage-suite.py` only. Snapshot: `/tmp/munbon-s-rc-rate-collector-snapshot.json`.
- Luna-Max receipt `/tmp/munbon-s-rc-rate-collector-receipt.json` passed the ownership validator for role `luna_implementer`, model `gpt-5.6-luna`, effort `max`; exact production hashes are `0478b5572f95121926cca1278738027ab2494c556429c62fbd04228ead4b113e` and `028a15484fe331e5d6f1726bceaf0c4c9cccbe1bb0a79b7b3a09e4627d9f005f` respectively.
- Focused GREEN passed three consecutive rounds. Related strict partial-collection scope passed `7`; write-activation/frontend/rate scope passed `77`; complete Python suite passed `840`; Node browser-inventory suite passed `51`; Black, Ruff, compileall, Bash/JavaScript syntax, and whitespace integrity passed.

### Wiring verification

| Component | Non-test call site | Registration/config load | Contract evidence |
|---|---|---|---|
| Local BFF rate budget | `bootstrap-linux.sh:428` writes `PLANNING_DEPTH_WRITE_LIMIT=11` | `_restart_bff_with_flag()` reloads the same `bff.env` through PM2 `--update-env`; BFF `Settings` reads the variable and the v2 route passes it to `consume_planning_depth_write_limit()` | Derived bootstrap test plus the observed `3 + 3 + 2 + 3 = 11` campaign sequence |
| Transient frontend log cleanup | `_frontend_server()` always unlinks after child shutdown | `LOCAL-WRITE-ACT-1` calls that exact context manager before browser/stability execution | Body-failure test proves the hidden log is absent; existing strict partial collector remains unchanged |

- Runtime acceptance remains unaccepted. Source remediation still requires QCHECK/formal review, delivery to a new merge SHA, a new archive, a new pristine guest, and a fresh one-shot RC attempt.

## Source delivery: scheduler dark bootstrap remediation

- Candidate commit: `18c8a7adbb40658efab4f9dcb0459419fdd62380` (`fix(control-plan): bootstrap scheduler dark defaults`).
- SSH push and PR `#199` succeeded: `https://github.com/SubhajL/munbon2-backend/pull/199`.
- Exact PR head matched candidate `18c8a7adbb40658efab4f9dcb0459419fdd62380`; PR was non-draft and mergeable against base `2c62aaaee93f5a43e4554d5fc31a739b21885c10`.
- Admin merge proceeded under the standing zero-step billing-lock policy without waiting on or investigating queued hosted jobs; no hosted job is called passing.
- Merge SHA: `324cfc9f56ba07168adbaa500b07c93bd0461bfb`.
- Exact landing: primary checkout `HEAD == main == origin/main == 324cfc9f56ba07168adbaa500b07c93bd0461bfb`, clean.
- Runtime acceptance remains unaccepted. Failed guest `01M0JBH0N243F8Q8S1YPRV9Z09` remains preserved and must not be reused; the merge SHA requires another exact archive, pristine guest, and fresh evidence namespace.

## Candidate `324cfc9f` dependency archive

- One diagnostic-builder invocation passed and published `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/dependencies-324cfc9f56ba07168adbaa500b07c93bd0461bfb-067b3e22401854f8c6d6db42dc0c5c1872fca6f8.tar.gz`.
- Outer SHA-256: `6ae49bc88af0c5e3c10fc05be0c821c02548d9d174eb14385de7239a0889488a`.
- Independent validation passed all `968` inner checksum entries. The schema-2 manifest binds exact backend `324cfc9f56ba07168adbaa500b07c93bd0461bfb`, frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`, Debian 12 ARM64, Node `22.23.1`, npm `10.9.8`, and Python `3.11`.
- Guarded exact-name deletion first revalidated failed guest `01M0JBH0N243F8Q8S1YPRV9Z09`, machine ID `0c5d2b159d7c496e8265b6c00f7d7057`, its exact candidate/archive owner, singleton shape, and three unrelated running guests. The guest was stopped, revalidated as the same stopped singleton, and deleted once by exact name. The ID and name are absent; unrelated guests remained running; the prior partial evidence still passes both checksum indexes with unchanged outer-index SHA-256 `ff4b2ee8a60a4f42572d06148fb390492316d1a3edda27d281701442a17c6965`.

## Source delivery: database-clean Boolean remediation

- Candidate commit: `b17616a56292ac9a13bf707e7e2b0ac17060a663` (`fix(control-plan): accept PostgreSQL boolean text`).
- SSH push succeeded on branch `fix/local-rc-db-bool`; PR `#198`: `https://github.com/SubhajL/munbon2-backend/pull/198`.
- Exact PR head matched `b17616a56292ac9a13bf707e7e2b0ac17060a663`; PR was non-draft and mergeable against base `5333e7ef7553832e438e3db9b0d991fdcf86c784`.
- Hosted jobs were unavailable under the standing zero-step billing-lock policy and are not called passing. Admin merge completed without investigating or retrying them.
- Merge SHA: `2c62aaaee93f5a43e4554d5fc31a739b21885c10`.
- Exact landing: primary checkout `HEAD == main == origin/main == 2c62aaaee93f5a43e4554d5fc31a739b21885c10`, clean.
- Runtime acceptance remains unaccepted. The next exact candidate requires a new dependency archive, new pristine canonical guest, and fresh evidence namespace; failed guest `01M0J9TZQ787D9N6C4KRT0DP30` remains preserved and must not be reused.

## Candidate `2c62aaae` dependency archive

- One diagnostic-builder invocation passed and published `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/dependencies-2c62aaaee93f5a43e4554d5fc31a739b21885c10-067b3e22401854f8c6d6db42dc0c5c1872fca6f8.tar.gz`.
- Outer SHA-256: `5894fa886fcfc0f5d70b946fdbab09d87cc9a162223f7f3560f8aece0b2d742b`.
- Independent validation passed all `968` inner checksum entries. The schema-2 manifest binds exact backend `2c62aaaee93f5a43e4554d5fc31a739b21885c10`, frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`, Debian 12 ARM64, Node `22.23.1`, npm `10.9.8`, and Python `3.11`.

## Fresh candidate attempt 3: authoritative preflight failure

- Guarded name deletion removed only failed guest `01M0J9TZQ787D9N6C4KRT0DP30`; its checksum-valid packet remained intact and unrelated guests remained running.
- Fresh session: `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/2026-08-21-local-rc1-2c62aaaee93f-067b3e224018-20260821T142655Z-8f200825`.
- Provisioning completed once. Locked fresh identity: Orb ID `01M0JBH0N243F8Q8S1YPRV9Z09`, machine ID `0c5d2b159d7c496e8265b6c00f7d7057`, exact candidate/archive ownership, and no bootstrap failure.
- The sole `run-rc` invocation failed at preflight gate `rc_runtime_not_dark`; no live stage ran. Exactly one partial collection passed with all ten current stages unreached, `acceptance_evidence=false`, `campaign_ledger_eligible=false`, and outer-index SHA-256 `ff4b2ee8a60a4f42572d06148fb390492316d1a3edda27d281701442a17c6965`.
- Read-only guest inspection found only one configured gate variable across the four runtime env files: `bff.env:PLANNING_DEPTH_WRITES_ENABLED=false`. The model release is correctly `commandable=false`.
- Exact root cause: `_rc_configured_dark()` requires the scheduler contract to evaluate to `CONTROL_EXECUTION_MODE=disabled` and `CONTROL_READBACK_RECONCILIATION_MODE=off`, but pristine bootstrap does not write either variable into `scheduler.env`. Missing values are intentionally not proof of darkness, so preflight fails closed.
- This does not invalidate historical 9/9 evidence. That closed campaign used older exact identities and its historical nine-stage scope; `LOCAL-RC-1` is a separate newer wrapper with stricter pristine preflight plus ten current stages.
- The failed guest remains preserved and must not be retried or repaired.

## Remediation slice S-RC-SCHEDULER-DARK-ENV

- Locked contract: pristine bootstrap must write `CONTROL_EXECUTION_MODE=disabled` and `CONTROL_READBACK_RECONCILIATION_MODE=off` inside the actual `scheduler.env` heredoc consumed by RC preflight and later scheduler process startup.
- Primary-owned test parses only the scheduler runtime-env block and requires both exact fail-closed values. Expected RED confirmed: `1 failed`; both values were absent (`None`).
- Production allowlist: `ops/control-plan-read-local/bootstrap-linux.sh` only. Tests, stage runner, orchestrator, Coding Log, guest/evidence state, and every other source/runtime file are protected.
- Wiring: bootstrap publishes `/etc/munbon/control-plan-read-runtime/scheduler.env`; `_rc_configured_dark()` loads that exact file and requires the two values before stage 1; scheduler process startup later sources the same file.
- Scoped GREEN: `python3 -m pytest -q ops/control-plan-read-local/tests/test_local_artifacts.py::test_bootstrap_writes_scheduler_dark_preflight_contract`.

### S-RC-SCHEDULER-DARK-ENV GREEN

- Luna-Max receipt `/tmp/munbon-s-rc-scheduler-dark-env-receipt.json` passed the ownership validator for role `luna_implementer`, model `gpt-5.6-luna`, effort `max`, exact sole production path, and SHA-256 `a65c650f050d58967c51487f3dc7af18a34c2fdf13be82d59cd4c428dd62cdb4`.
- Complete diff adds only the exact two variables to the existing scheduler heredoc; every prior entry is preserved.
- Primary scoped GREEN passed three consecutive times; the related `_rc_configured_dark`/RC-preflight scope passed `6 passed, 529 deselected`; Bash syntax passed.
- Complete matrix: Python `837 passed`; Node `51 passed`; Black, Ruff, compileall, Bash/JavaScript syntax, and whitespace integrity passed.

## Review (2026-08-21 21:41:58 +0700) - working-tree S-RC-SCHEDULER-DARK-ENV

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-local-rc-runtime-acceptance`.
- Branch/baseline: `fix/local-rc-db-bool` at `b17616a56292ac9a13bf707e7e2b0ac17060a663`; `main/origin/main` is `2c62aaaee93f5a43e4554d5fc31a739b21885c10`.
- Scope: complete working-tree bootstrap, unit/integration test, runtime README, and Coding-Log diff; RepoPrompt snapshot `2026-08-21/2139`; targeted bootstrap/consumer/startup reads; independent Terra QCHECK.
- RepoPrompt Context Builder was unavailable because the exact bound tab was already MCP-controlled. Per g-check fallback, review proceeded immediately with the bounded complete diff, exact-string wiring reads, executable gates, and independent Terra without blind retry.
- Commands: ownership verification; targeted complete diff; scoped test three rounds; bootstrap-to-preflight integration test; related RC-preflight scope; full Python/Node suites; Black; Ruff; compileall; Bash/JavaScript syntax; whitespace integrity.

### Findings

CRITICAL

- None.

HIGH

- None.

MEDIUM

- None.

LOW

- Terra found the runtime README omitted the two canonical scheduler settings. Fixed in `ops/control-plan-read-runtime/README.md`.
- Terra suggested an end-to-end env-file-to-preflight test. Added `test_bootstrap_runtime_environment_satisfies_rc_dark_contract`, which materializes all four actual bootstrap heredocs, uses the real non-commandable model release, and passes `_rc_configured_dark()`.

### Open Questions / Assumptions

- Missing Boolean-style gate variables intentionally evaluate dark, while scheduler execution/readback are enumerated strings and must be explicit. SCADA URL/token/capability inputs remain absent, and startup explicitly unsets them.
- The authoritative failed guest remains preserved and was not mutated to validate this source change.

### Recommended Tests / Validation

- No additional actionable test remains before source delivery. A new exact candidate still requires a rebuilt archive, pristine guest, and fresh one-shot RC attempt.

### Rollout Notes

- This is a dark-default bootstrap correction only. It does not activate control execution, readback reconciliation, machine commands, planning-depth writes, deployment, or AWS actions.
- Final post-QCHECK gates: Python `838 passed`; Node `51 passed`; formatting, lint, compilation, shell/JavaScript syntax, and whitespace integrity passed.
- Formal `g-check` disposition: clean; no actionable finding remains.

## Attempt 4 failure and rate/collector remediation closure

- Fresh attempt-4 session `/Users/subhajlimanond/dev/munbon-control-plan-rc-evidence/2026-08-21-local-rc1-324cfc9f56ba-067b3e224018-20260821T145414Z-49090f32` provisioned exact guest `01M0JD3D6KPD3NRB7BK6511J6B`, machine ID `1e48131c82024e39a1b5f194f73d33fa`, backend `324cfc9f56ba07168adbaa500b07c93bd0461bfb`, frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`, and archive SHA-256 `6ae49bc88af0c5e3c10fc05be0c821c02548d9d174eb14385de7239a0889488a`.
- The sole RC run passed strict preflight and the first nine current stages, then failed `LOCAL-WRITE-ACT-1` because the eleventh same-operator submit was rate-limited at `429` before the repository could return the expected stale-conflict `409`. Restoration returned BFF, scheduler, frontend, and operator sessions to the required dark/closed state.
- Exact rate accounting is foundation `3` + write UI `3` + persist-only `2` + write activation `3` = `11`. The pristine local BFF previously inherited the service default `10`; the remediation explicitly writes local-only `PLANNING_DEPTH_WRITE_LIMIT=11`. The service default remains unchanged, and a twelfth admitted request remains limited by the existing `count > limit` boundary.
- The sole strict partial-collection attempt rejected an unindexed `.frontend-write-activation-armed.log`. Diagnostic-only packet `diagnostic-attempt-1` preserves the failure manifest, bounded manager log, diagnosis, and checksum index; it is explicitly not acceptance evidence. The failed guest remains preserved and was not retried or repaired.
- Primary-owned RED contracts covered rate-budget configuration, transient-log removal after stage failure, primary exception identity, cleanup-only fixed gates, unproven process shutdown, late-exit proof, poll failure containment, sanitized secondary teardown evidence, manifest publication, and deterministic process-over-log precedence.
- All five Luna-Max receipts passed the ownership validator with role `luna_implementer`, model `gpt-5.6-luna`, effort `max`, unchanged HEAD, exact runner/bootstrap allowlists, and no protected-file drift: `S-RC-RATE-COLLECTOR` (`89abefdadc951c5d0599d89f9ddf675a1ef3ae6e122c511e538982080c6bc6c5`), `S-RC-FRONTEND-CLEANUP-ATTRIBUTION` (`d7b220e46c0da73283d7e632500388e9ec99a0d5211052038c3bae7ad9dfbf05`), `S-RC-FRONTEND-PROCESS-TEARDOWN` (`e74afc460406bbe0366d62dd91a08a6f895186e4a12923c8df4da9c45e0a8d4b`), `S-RC-FRONTEND-TEARDOWN-EVIDENCE` (`e3adc31eb16b43c359f4ec079788c473487a6a836f8ee5a7de338567f1ca681c`), and `S-RC-FRONTEND-LOG-ATTRIBUTION` (`a6f1b5bd3c242c62b2fbc7bc0f7cad784c4b7365d85d28ed7f2ef70095be9428`).
- Final production SHA-256 values: `bootstrap-linux.sh` `0478b5572f95121926cca1278738027ab2494c556429c62fbd04228ead4b113e`; `run-stage-suite.py` `ef730c47b7208c2dcd8a4e9aea6d9e4bb9a29204c0cb6059d86dfe8661936736`.
- Final primary gates: focused frontend/manifest contract `13 passed` for three consecutive rounds; related strict partial collector `43 passed`; complete Python `852 passed`; Node `51 passed`; Black, Ruff, compileall, Bash/JavaScript syntax, and whitespace integrity all passed.
- Final independent QCHECK: no CRITICAL, HIGH, or MEDIUM findings. Residual LOW hardening is an executable-seam rate-admission count test; the current static `3+3+2+3` proof is correct but can drift if the scripted campaign changes.
- Runtime acceptance remains unaccepted until this source is merged, a dependency archive is rebuilt for the exact merge SHA, the failed guest is deleted by its guarded exact name, and a new pristine guest completes one fresh RC run.

## Review (2026-08-21 23:18:06 +0700) - working-tree S-RC-RATE-COLLECTOR

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-local-rc-runtime-acceptance`.
- Branch: `fix/local-rc-scheduler-dark-env`.
- Scope: complete working tree at baseline `18c8a7adbb40658efab4f9dcb0459419fdd62380`; RepoPrompt authoritative snapshot `2026-08-21/2317`.
- Commands run: ownership snapshot/receipt verification for five Luna-Max slices; targeted complete diffs and wiring reads; focused RED/GREEN tests and three-repeat frontend/manifest contract; related rate/collector suites; complete Python and Node suites; Black; Ruff; compileall/py_compile; Bash and JavaScript syntax; `git diff --stat`; `git diff --check`; independent Terra QCHECK; RepoPrompt Context Builder and continued Oracle review.

### Findings

CRITICAL

- None.

HIGH

- None.

MEDIUM

- None. Earlier exception masking, unproven frontend shutdown, late-exit false attribution, unguarded polling, and missing process/log cleanup evidence findings were each locked by primary-owned RED tests, remediated through bounded Luna-Max production slices, ownership-validated, and rerun through the full matrix.

LOW

- The static rate-budget test restates `3+3+2+3` instead of deriving admissions from the four executable drivers. The current count and limit are correct; an executable-seam admission counter is residual hardening.
- Frontend teardown coverage is comprehensive but mock-process based. A disposable real-process-group integration test would add platform assurance without changing the current correctness disposition.
- The application and harness both default the write window to 300 seconds. Documentation now states that the pristine bootstrap relies on the matching application default; a static cross-default assertion would guard future drift.

### Open Questions / Assumptions

- The limit override is intentionally local-campaign-only. The BFF service default remains `10`, and neither production behavior nor AWS/deployment state is changed.
- An actual filesystem refusal to unlink the transient frontend log remains fail-closed under the strict collector. The primary failure manifest now records the exact sanitized secondary cleanup code for diagnostic attribution; the collector inventory is not relaxed.

### Recommended Tests / Validation

- No actionable validation remains before source delivery. The next acceptance proof must use the exact merged SHA, one rebuilt dependency archive, a newly provisioned guest, and one fresh RC run.

### Rollout Notes

- Final source gates: focused contract `13 passed` for three consecutive rounds; strict partial collector `43 passed`; complete Python `852 passed`; Node `51 passed`; formatting, lint, compilation, shell/JavaScript syntax, and whitespace integrity passed.
- Formal `g-check`: no CRITICAL, HIGH, or MEDIUM finding remains. Runtime acceptance is still separate and not yet claimed.
