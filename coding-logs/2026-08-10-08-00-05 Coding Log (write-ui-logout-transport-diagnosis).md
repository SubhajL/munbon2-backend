# Coding Log: WRITE-UI logout transport diagnosis

## Context (2026-08-10 08:00:05 +0700)

- Worktree: `/Users/subhajlimanond/dev/munbon2-backend-write-ui-logout-transport`
- Branch: `fix/write-ui-logout-transport`
- Base: `origin/main` at `0ec5275a3d27ae732c052719b272c75443b45b1a`
- Scope: preserve the existing disposable diagnostic evidence, then determine whether logout failure belongs to the harness transport, Smart CMS local cookie/proxy behavior, or central auth.
- Acceptance boundary: all work in this log is diagnostic/qualification only. It cannot advance `stage-state.json` or establish `LOCAL-WRITE-UI-1` acceptance.
- Search: Auggie was attempted once with the complete harness/runtime/test question and timed out at the required two-second bound. Fallback inspection covered `run-write-browser.js`, `run-stage-suite.py`, both focused test suites, Smart CMS auth client/server/routes, the operations guide, and existing evidence conventions.

## Phase 0 preservation (2026-08-10 07:58 +0700)

Goal: preserve the checksum-valid six-predicate diagnostic bundle before any rebuild, deletion, or further run.

- External archive: `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-10-write-ui-diagnostic-2818e367`
- Diagnostic provenance: backend `2818e3676f8d28a9b156b7c835879343e4d2ecfe`; frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`.
- Capture-time guest checkout: backend `0ec5275a3d27ae732c052719b272c75443b45b1a`; this is recorded separately and does not replace diagnostic provenance.
- Copied only `LOCAL-WRITE-UI-1-browser-result.json`, `LOCAL-WRITE-UI-DIAGNOSTIC-failure.json`, and guest-owned `SHA256SUMS`; excluded `.frontend-write-ui-armed.log` and all raw stderr.
- Guest inner checksum verification: both JSON files PASS before and after the copy.
- Host inner and outer checksum verification: PASS. `OUTER-SHA256SUMS` digest is `7ec56a5bf60b4ad7b9eaf4a1e4deaf7f629ed59cc22f28eb2e39d7d67b9c7d34`.
- Preservation state: neither OrbStack guest was rebuilt, deleted, stopped, or reprovisioned.

## Phase 1 plan (2026-08-10 08:02 +0700)

### Alternatives

1. One-off manual Playwright probe: fastest, but weakly repeatable and easy to lose provenance.
2. Diagnostic-only harness comparison: chosen; small, testable, repeatable, and uses the existing sanitizer/checksum path.
3. Edit Smart CMS or central auth immediately: rejected until transport evidence proves ownership.

### Contract

- Only diagnostic mode changes logout transport.
- Primary operator uses page-origin `fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' })`.
- Second operator retains `browserContext.request.post` as the control.
- Each transport records only `transport`, `session_count`, `sessions[{name, domain, path, secure, same_site}]`, `logout_status`, and `refresh_reuse_status`.
- No values, headers, request/response bodies, token material, credentials, or raw stderr are retained.
- Never use an evidence key containing `cookie`; `validate_evidence_payload` rejects it by design.
- Acceptance mode and `validate_write_browser_result` predicates remain unchanged.

### TDD slices and files

1. `ops/control-plan-read-local/tests/test_write_browser_inventory.js`: RED for relative page-origin POST with `credentials: same-origin`; RED for strict value-free session metadata; RED for distinct primary/second proof dependencies while preserving both cleanup attempts.
2. `ops/control-plan-read-local/run-write-browser.js`: minimal page-origin logout, metadata projection, and diagnostic-only dual-transport proof.
3. `ops/control-plan-read-local/tests/test_stage_suite.py`: RED that diagnostic mode alone supplies `LOCAL_WRITE_UI_DIAGNOSTIC=1` through the actual `run_local_write_ui` to `_run_write_browser` path.
4. `ops/control-plan-read-local/run-stage-suite.py`: thread `diagnostic` into `_run_write_browser` and its sanitized environment; no validator change.

### Wiring verification

| Component | Non-test call site | Registration/config load | Schema/contract match |
|---|---|---|---|
| page-origin logout | diagnostic branch in `run-write-browser.js` operator logout block | `LOCAL_WRITE_UI_DIAGNOSTIC` read by Node launcher | same-origin relative POST; integer status only |
| request-context control | same operator logout block, second context | existing `logoutContext` | existing logout and refresh-reuse fields unchanged |
| diagnostic env | `run_local_write_ui(..., diagnostic=True)` to `_run_write_browser` | `_write_browser_environment` | present only for diagnostic runs |
| evidence persistence | `_accept_write_browser_output` before validation | existing diagnostic evidence root and checksum index | sanitizer-approved keys; no acceptance predicate or state advancement |

### Runtime classification

- A: page-origin logout succeeds and reuse is 401 while request-context remains 401/200 -> harness transport defect.
- B: page-origin logout also returns 401 -> Smart CMS local cookie/proxy behavior implicated.
- C: logout succeeds but reuse remains 200 -> central-auth revocation implicated.

### Planned gates

- Focused Node and Python RED/GREEN commands.
- Full `ops/control-plan-read-local/tests` suite.
- Node syntax, Python compile, Black check, and repository diff check.
- Three consecutive affected-suite runs.
- Independent QCHECK, formal `g-check`, and runtime wiring review.
- Exact diagnostic installation/run in the disposable guest against a fresh RID week, with all dark-state/restoration checks repeated.

## TDD slice: diagnostic transport comparison (2026-08-10 08:09 +0700)

Goal: make diagnostic mode compare a real page-origin logout with the existing Playwright request-context logout while retaining only value-free metadata.

Files changed:

- `ops/control-plan-read-local/run-write-browser.js`: added page-origin logout, value-free refresh-session metadata projection, distinct primary/second logout proof dependencies, and diagnostic-only evidence assembly.
- `ops/control-plan-read-local/run-stage-suite.py`: threads diagnostic mode into the launcher and removes any inherited diagnostic flag before adding the explicit diagnostic value.
- `ops/control-plan-read-local/tests/test_write_browser_inventory.js`: pins page-origin request semantics, exact metadata projection, both-context cleanup, and distinct transport proofs.
- `ops/control-plan-read-local/tests/test_stage_suite.py`: pins acceptance/diagnostic environment separation and `_run_write_browser` wiring.

Initial RED commands and expected reasons:

- `node --test ops/control-plan-read-local/tests/test_write_browser_inventory.js` -> 26 PASS / 4 FAIL because the two helpers and distinct transport dependencies did not exist.
- `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py -k 'transport_comparison_only_for_diagnostic or threads_diagnostic_mode_to_the_launcher_environment'` -> 2 FAIL because neither Python function accepted a diagnostic argument.
- Follow-up RED set an inherited `LOCAL_WRITE_UI_DIAGNOSTIC=1`; acceptance incorrectly inherited it. This exposed a real fail-open risk in the launcher environment.

GREEN commands:

- `node --test ops/control-plan-read-local/tests/test_write_browser_inventory.js` -> 30/30 PASS.
- `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py -k 'transport_comparison_only_for_diagnostic or threads_diagnostic_mode_to_the_launcher_environment'` -> 2/2 PASS, 287 deselected.

Behavior and risk notes:

- Acceptance behavior remains on `context.request.post`; only explicit diagnostic mode changes the primary operator to page-origin fetch.
- Both operator sessions are still logged out even when the first proof fails.
- Metadata excludes credential values, headers, bodies, expiry, HttpOnly, and all keys containing `cookie`; the existing sanitizer remains authoritative.
- The inherited-environment RED initially caused pytest to render a credential-bearing environment variable in transient command output. No value was copied into source, evidence, or this log. Rotation was recommended to the user, and the assertion was tightened to prevent a repeat.

## Local gates (2026-08-10 08:15 +0700)

- `node --test ops/control-plan-read-local/tests/test_write_browser_inventory.js` -> 30/30 PASS.
- `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m pytest -q ops/control-plan-read-local/tests` -> 349/349 PASS.
- `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m pytest -q ops/control-plan-read-runtime/tests/test_runtime_artifacts.py` -> 7/7 PASS.
- Combined stability command ran the 356 Python tests plus 30 Node tests on each of three consecutive runs -> 386/386 PASS each run.
- `node --check ops/control-plan-read-local/run-write-browser.js` -> PASS.
- Python compilation for `run-stage-suite.py` and `orchestrate.py` -> PASS.
- Black check for the changed Python files -> PASS after formatting one test file.
- Prettier check for the changed JavaScript files -> PASS.
- `git diff --check` -> PASS.

Runtime wiring evidence:

| Component | Non-test call site | Registration/config load | Schema/contract match |
|---|---|---|---|
| page-origin logout | `run-write-browser.js` diagnostic operator logout block | `LOCAL_WRITE_UI_DIAGNOSTIC === '1'` | relative `/api/auth/logout`, POST, same-origin credentials, integer status |
| request-context control | `proveBothOperatorLogouts` second proof | existing `logoutContext` | existing logout and refresh-reuse result fields unchanged |
| diagnostic env | `run_local_write_ui` passes `diagnostic` into `_run_write_browser` | `_write_browser_environment` strips inherited flag, then conditionally sets `1` | absent in acceptance, exact `1` in diagnostic |
| persisted comparison | raw browser body reaches `_persist_write_browser_result` before validator rejection | existing isolated evidence root and `SHA256SUMS` | value-free names and no key rejected by `validate_evidence_payload`; acceptance projection unchanged |

Residual runtime gate: install an exact committed candidate in the disposable guest, select a fresh RID week, run the diagnostic, verify the persisted sanitized comparison/checksums, and classify A/B/C while confirming scheduler restoration, write-dark state, four PM2 services, and no port-9999 listener.

## Independent QCHECK remediation (2026-08-10 08:18 +0700)

Finding: P1 experimental-control ambiguity. The exact Smart CMS client sends the current access bearer on logout and the proxy forwards it upstream, but the initial diagnostic implementation omitted it from both transports. A divergent result would therefore have changed bearer semantics as well as transport and could not support an ownership conclusion.

Remediation TDD:

- RED: `node --test ops/control-plan-read-local/tests/test_write_browser_inventory.js` -> 29 PASS / 2 FAIL. Page-origin fetch lacked the expected bearer header and `logoutContext` was not exported/testable.
- GREEN: both diagnostic transports now receive their own session's already-captured access token and send identical `Authorization: Bearer ...` semantics. The value is used only in flight; all returned proof and persisted metadata remain status/attribute-only.
- Acceptance mode remains on its pre-existing logout call path. The bearer-controlled comparison is activated only by explicit diagnostic mode.
- Focused Node suite -> 31/31 PASS.
- Post-remediation stability -> 356 Python plus 31 Node, 387/387 PASS on each of three consecutive runs.
- Post-remediation Node syntax, Python compilation, Black, Prettier, and diff checks -> PASS.

Awaiting independent QCHECK recheck and formal `g-check`.

### QCHECK follow-up remediation (2026-08-10 08:20 +0700)

The first recheck confirmed both operator transports were controlled but found the field-team session still used the bearer-less default logout in diagnostic mode. That left the third original 401/200 failure under a different request contract.

- RED: focused Node suite -> 31 PASS / 1 FAIL because `proveRequestContextLogout` did not exist.
- GREEN: the reusable proof wrapper passes the captured bearer only when `diagnostic=true`; with `diagnostic=false` it supplies no override and retains the original acceptance behavior.
- Runtime wiring: field team uses the wrapper with `fieldToken`; the second operator uses it with `token2`; the primary page-origin path uses `token`. All three values remain in-flight only.
- Focused Node suite -> 32/32 PASS.
- Final stability -> 356 Python plus 32 Node, 388/388 PASS on each of three consecutive runs.
- Final syntax, compilation, Black, Prettier, and diff checks -> PASS.
- Operations guide updated with the diagnostic comparison, safe fields, and A/B/C interpretation boundary.

Awaiting the final independent QCHECK recheck and formal `g-check`.

### Final independent QCHECK (2026-08-10 08:21 +0700)

No remaining P0-P2 findings. The recheck confirmed all three diagnostic logout paths use their captured bearer, acceptance mode retains the original request behavior, and no bearer enters persisted evidence. Independent focused checks passed: 32/32 Node, 2/2 Python wiring tests, and diff check.

### Minimal-diff formatter disposition (2026-08-10 08:22 +0700)

The repository has no root Prettier configuration for these ops JavaScript files. Running default Prettier widened the diff through unrelated pre-existing lines, so those formatting-only changes were removed and only the tested semantic edits were retained. A bounded probe confirms default `prettier --check` exits 1 on both the exact `HEAD` file and the final candidate file; this is a pre-existing repository baseline, not a candidate regression. The new/edited blocks were formatted before minimal replay. Final exact-candidate gates are 356 Python plus 32 Node, 388/388 PASS on each of three consecutive runs, with Node syntax, Python compilation, Black, and diff checks passing.

## Review (2026-08-10 08:23:00 +0700) - Phase 1 diagnostic working tree

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-write-ui-logout-transport`
- Branch: `fix/write-ui-logout-transport`
- Scope: staged working tree against `origin/main` `0ec5275a3d27ae732c052719b272c75443b45b1a`
- Commands Run: staged status/stat/name inspection; targeted staged diffs for production, tests, runbook, pointer, and Coding Log; `git diff --staged --check`; 388-test exact-candidate stability command three consecutive times; Node syntax; Python compilation; Black check; baseline/candidate default-Prettier comparison.

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

- The live A/B/C ownership result remains intentionally unknown until the exact committed candidate is installed and run in the disposable guest against a confirmed clean RID week.
- Default Prettier is not a usable repository gate for these ops JavaScript files because both `HEAD` and candidate fail without a root configuration; the candidate introduces no new formatter regression.

### Recommended Tests / Validation

- Install the exact candidate SHA on `munbon-control-plan-write-ui-diagnostic`.
- Preflight a fresh RID week, run `LOCAL-WRITE-UI-1 --diagnostic`, verify the sanitized browser result and both checksum layers, and classify A/B/C from the two controlled transports.
- Verify scheduler restoration attempt one, `PLANNING_DEPTH_WRITES_ENABLED=false`, four PM2 services online/ready, and no port-9999 listener.

### Rollout Notes

- The comparison is diagnostic-only, cannot advance `stage-state.json`, and changes no production API or acceptance predicate.
- Acceptance mode strips inherited diagnostic activation and retains its original logout dependency.
- Access and refresh credentials remain in flight only and are absent from the persisted comparison, failure manifest, Coding Log, and external archive.

## Phase 2 remediation plan (2026-08-10 10:24 +0700)

Goal: replace the diagnostic comparison with one testable page-origin logout proof used by field team, primary operator, and second operator without changing Smart CMS, central auth, cookies, or validation predicates.

- Fresh worktree: `/Users/subhajlimanond/dev/munbon2-backend-phase2-page-origin-logout`.
- Branch: `fix/phase2-page-origin-logout`.
- Base: refreshed `origin/main` at `3614e360413c37566211aeb7568726996cbd541d` (`fix(ops): compare write UI logout transports (#173)`).
- Search: Auggie received one detailed harness/runtime/test query and exceeded the required two-second bound. Targeted fallback inspection covered `run-write-browser.js`, `run-stage-suite.py`, their focused test suites, the root `AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`, and this current Coding Log.
- Clarification: the user required three consecutive focused and full gate runs; this plan treats both scopes literally and the user may narrow that interpretation while work continues.

### Locked behavioral contract

1. Export a testable `provePageOriginLogout(context, page, accessToken, deps)` seam.
2. The seam captures that context's refresh credential before logout, posts `/api/auth/logout` through that context's real page with `credentials: "same-origin"` and its own bearer, then probes the same captured refresh credential.
3. Field team, primary operator, and second operator all use this seam in acceptance and diagnostic runs.
4. Both operator page-origin logout proofs are attempted sequentially; the first failure is surfaced only after the second attempt.
5. Remove request-context logout helpers, comparison metadata/evidence, and the now-dead launcher comparison flag.
6. Retain diagnostic orchestration only as isolated, non-acceptance evidence: it may write `LOCAL-WRITE-UI-DIAGNOSTIC` but must never call `_save_state` or create/advance `stage-state.json`.
7. Preserve every `validate_write_browser_result` predicate and all Smart CMS, central-auth, and cookie behavior unchanged.

### TDD and wiring plan

| Slice | RED behavior | Production wiring |
|---|---|---|
| page-origin seam | exact capture -> page logout -> same-value probe ordering and own bearer | all three real browser pages call `provePageOriginLogout` |
| dual operator cleanup | primary failure still invokes second page proof | `proveBothOperatorLogouts` receives both context/page/bearer tuples |
| dead comparison removal | launcher environment cannot activate removed transport comparison | diagnostic remains a Python orchestration/manifest concern only |
| diagnostic isolation | existing test rejects any `_save_state` call and stage-state creation | `_write_local_write_ui_manifest(..., diagnostic=True)` remains the only diagnostic completion path |

Planned gates: focused Node tests, focused Python diagnostic-isolation tests, complete local ops suite, runtime-artifact suite, Node syntax, Python compilation, Black, formatter baseline/candidate comparison, diff check, then three consecutive focused and full-scope runs, independent QCHECK, and formal `g-check`.

## Phase 2 TDD slice: page-origin logout proof (2026-08-10 10:31 +0700)

Files changed:

- `ops/control-plan-read-local/run-write-browser.js`: replaced request-context and comparison-only helpers with `provePageOriginLogout`; wired field team and both operator pages through it; preserved second-operator attempt-after-primary-failure; removed comparison payload and value-free comparison metadata.
- `ops/control-plan-read-local/run-stage-suite.py`: removed the now-dead diagnostic transport parameter and launcher environment flag while continuing to strip any inherited flag.
- `ops/control-plan-read-local/tests/test_write_browser_inventory.js`: pins capture -> own page/bearer logout -> exact captured-value probe ordering, both-operator attempt behavior, and own page/bearer mapping.
- `ops/control-plan-read-local/tests/test_stage_suite.py`: pins rejection of the removed browser transport switch and retains the existing diagnostic no-state proof.

RED commands and expected reasons:

- `node --test ops/control-plan-read-local/tests/test_write_browser_inventory.js` -> 24 PASS / 5 FAIL: `provePageOriginLogout` was absent and `proveBothOperatorLogouts` still accepted context/request-oriented inputs.
- `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py -k 'rejects_removed_transport_comparison_switch'` -> 2 FAIL: `_write_browser_environment` and `_run_write_browser` still accepted and threaded the obsolete diagnostic transport flag.

GREEN commands:

- `node --test ops/control-plan-read-local/tests/test_write_browser_inventory.js` -> 29/29 PASS.
- `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py -k 'rejects_removed_transport_comparison_switch or diagnostic_manifest_never_advances_acceptance_state'` -> 3/3 PASS, 286 deselected.

Runtime wiring:

| Component | Non-test call site | Registration/config load | Schema/contract match |
|---|---|---|---|
| field-team page-origin proof | `run-write-browser.js` field-team block | `fieldTeamContext`, `fieldPage`, `fieldToken` from its login | existing `logout_status` and `refresh_reuse_status` result fields unchanged |
| primary page-origin proof | `proveBothOperatorLogouts` call at logout checkpoint | `primaryContext`, `page`, `token` | existing primary logout projection unchanged |
| second page-origin proof | same dual-proof call | `secondContext`, `page2`, `token2` | existing second-context projection unchanged; attempted after primary failure |
| diagnostic isolation | `_write_local_write_ui_manifest(..., diagnostic=True)` | CLI `--diagnostic` remains Python-only | `LOCAL-WRITE-UI-DIAGNOSTIC`, `DIAGNOSTIC_PASS`, `acceptance_evidence=false`, no `_save_state` |

Boundaries: Smart CMS, central auth, cookie constants/hardening, refresh validation, and `validate_write_browser_result` were not changed. Refresh and access credentials remain in flight only; removed comparison evidence means no replacement transport claim is persisted.

## Phase 2 final local gates and independent QCHECK (2026-08-10 10:43 +0700)

Preliminary full-suite integration RED:

- `pytest -q ops/control-plan-read-local/tests` initially produced 348 PASS / 1 FAIL because `test_local_artifacts.py` still required the deleted `proveContextLogout` identifier.
- The inventory contract was updated to require `provePageOriginLogout` and `pageOriginLogout`; rerun -> 349/349 PASS.

Independent QCHECK findings and remediation:

- P2: three-context mapping was not pinned in one behavioral contract. Remediated by one test that covers field capture -> own page/bearer logout -> same refresh probe and then distinct primary/second context/page/bearer mappings. Focused Node -> 29/29 PASS.
- P3: the removed-switch Python test asserted a signature `TypeError` before its mock could run. Remediated by running `_run_write_browser` normally with an inherited `LOCAL_WRITE_UI_DIAGNOSTIC=1`, capturing the real launcher environment, and asserting the flag is absent. Focused Python -> 3/3 PASS.
- Independent recheck: both findings resolved; no new P0-P2 findings. Reviewer reran 29/29 Node and 3/3 Python.

Final exact-working-tree stability:

- Focused command ran 29 Node logout/harness tests plus 3 Python switch/isolation tests on each of three consecutive runs -> PASS / PASS / PASS.
- Full command ran 349 local Python tests, 7 runtime-artifact Python tests, and 41 Node tests plus Node syntax, Python compilation, Black, diff integrity, and dead-symbol checks on each of three consecutive runs -> PASS / PASS / PASS.
- Node syntax and Python compilation passed on every full run.
- Black check passed for all three changed Python files on every full run.
- `git diff --check` and the exact dead-symbol search passed on every full run.
- Default Prettier 3.6.2 still exits 1 for both changed JavaScript files. Exact `HEAD` versions also exit 1 under the same command because the ops files have no repository Prettier configuration; this is baseline parity, not a formatter pass. Changed blocks were aligned to Prettier's rendered form where they differ, without widening the patch through unrelated baseline lines.

QCHECK disposition: no unresolved P0-P3 findings. Formal `g-check` remains required before commit.

## Review (2026-08-10 10:42:31 +0700) - Phase 2 remediation working tree

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-phase2-page-origin-logout`
- Branch: `fix/phase2-page-origin-logout`
- Scope: staged working tree against `3614e360413c37566211aeb7568726996cbd541d`
- Commands Run: bounded Auggie attempt; staged status/name/stat/check; targeted staged diff and line inspection; exact symbol/wiring searches; three consecutive focused and full gate runs; independent QCHECK and recheck.

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

- “Capture each context's refresh credential first” is interpreted per context: capture immediately before that context's page-origin logout, then probe that exact value. This is the ordering pinned by the behavioral seam and preserves the required second-operator attempt after a primary failure.
- No live disposable-guest WRITE-UI acceptance was requested in this source remediation lifecycle. Diagnostic output remains explicitly non-acceptance and cannot advance stage state.
- Default Prettier remains a pre-existing repository-baseline failure for both touched JavaScript files; this review does not classify it as a passing gate.

### Recommended Tests / Validation

- Retain the 29-test Node behavioral suite and the diagnostic no-state Python tests as required regression gates.
- A later exact-SHA WRITE-UI acceptance run should use the normal page-origin proof and must remain distinct from diagnostic evidence.

### Rollout Notes

- All three browser identities now use their own real page and bearer for logout; result and validation schemas are unchanged.
- The request-context comparison payload and launcher switch are removed. Diagnostic orchestration remains isolated and non-advancing.
- No Smart CMS, central-auth, cookie, or validation-predicate change is included.

## Phase C economic qualification (2026-08-10 11:06 +0700)

Goal: qualify the merged stage-8 and stage-9 behavior economically in the disposable OrbStack guest without changing authoritative acceptance state.

Context and provenance:

- PR #174 is merged; local `HEAD == main == origin/main == d07fde2ed49950272ca49261a39ec087fcae31ba`.
- The frozen frontend remained `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`.
- Both Phase 0 and Phase 1 external diagnostic archives reverified at their guest inner and host outer checksum layers before guest mutation.
- The exact backend merge SHA was transferred by a local Git bundle, checked out detached in `munbon-control-plan-write-ui-diagnostic`, and the installed `run-stage-suite.py` and `run-write-browser.js` hashes matched the exact checkout.
- No service source differs between the prior diagnostic SHA and this merge SHA; runtime services were not rebuilt. The operations harness was replaced from the exact checkout.
- Auggie semantic retrieval exceeded the required two-second bound. Fallback inspection covered the stage runner, host orchestrator, acceptance runbook, focused tests, and the current pickup plan.

Live database selection:

- A read-only live PostgreSQL query found R41, R42, and R43 already used; R44 onward were initially unused.
- WRITE-UI run 1 used database-proven clean `2026-R44` (`--as-of-date 2026-08-31`).
- WRITE-UI run 2 used separately re-queried clean `2026-R45` (`--as-of-date 2026-09-07`).
- R46 remained unused.
- PERSIST attempt 1 used clean R47; its external wrapper failed at the manifest boundary after the tested body completed, so R47 was preserved as not qualified and never reused.
- PERSIST retry used separately re-queried clean R48 (`as-of 2026-09-21`, persist target R48).

WRITE-UI qualification results:

- Both R44 and R45 completed `LOCAL-WRITE-UI-1 --diagnostic` as `DIAGNOSTIC_PASS` with `acceptance_evidence=false`.
- Each run produced field-team, primary-operator, and second-operator logout statuses `200 / 200 / 200` and refresh-reuse statuses `401 / 401 / 401`.
- Each run restored the scheduler on attempt one with no failed gate.
- After each run all four PM2 services were online, `PLANNING_DEPTH_WRITES_ENABLED=false`, port 9999 was absent, and the isolated root contained no `stage-state.json`.
- No repair or reprovision occurred between the two consecutive runs.

PERSIST-only qualification results:

- The canonical `run_local_persist_only` entry point was intentionally not called because it requires prior acceptance state and invokes `_save_state`.
- A no-state wrapper called the exact merged `_persist_only_body`, retained strict logout and failure behavior, relabeled the manifest `LOCAL-PERSIST-ONLY-QUALIFICATION`, and set `acceptance_evidence=false`.
- Attempt 1 on R47 completed the persist body and restored the BFF, then failed because `clear_failure_manifest` rejects noncanonical stage labels; its fallback also referenced a nonexistent exception attribute. No success manifest existed, so the attempt was classified `QUALIFICATION_FAIL`, preserved with inner and outer checksums, and R47 was consumed rather than reused.
- The corrected wrapper omitted the canonical-only cleanup helper and used `_safe_error_code`. The retry on R48 passed: 33 non-W2 tables unchanged, exactly 2 W2 submissions and 82 W2 values added, correction/supersession shape accepted, rate-accounting increment exactly 2, and no AWS action.
- After the R48 run all four services were online and ready, writes were false, port 9999 was absent, and no qualification root contained stage state.

Durable bundles and outer-index digests:

- `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-10-phase-c-write-ui-r44-d07fde2e/` -> `6ed10c05da2355dfc6b38898f41014c84123f2ce25429577431dcf437542f419`
- `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-10-phase-c-write-ui-r45-d07fde2e/` -> `27c98f55d0f7579e41a763ea87f395545dbe633c28827bc5c168dee35f87b6c2`
- `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-10-phase-c-persist-r47-attempt1-wrapper-failure/` -> `e28b518df943e285b42de2c6cb99c7e7b61670bde0e1e8d23d09eb4316b13731`
- `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-10-phase-c-persist-r48-d07fde2e/` -> `101c746c9322011c9c8b1d0d2f7afdf22cc8badccf4063386a00bd1d9da34946`

Every bundle's guest `SHA256SUMS` and host `OUTER-SHA256SUMS` reverified at finalization. Host projections exclude raw logs, stderr, credentials, cookies, tokens, headers, response bodies, and submission identifiers.

Acceptance truth remains unchanged: the frozen authoritative chain is 7/9 PASS, current main has not received a fresh authoritative nine-stage run, and all Phase C results are qualification-only.

## Phase D authoritative-chain attempt (2026-08-10 12:10 +0700)

Goal: provision a fresh canonical guest and database, then run all nine stages once without repairs, reused submissions, skips, or reprovisioning.

Frozen inputs and preservation:

- Backend `HEAD == main == origin/main == d07fde2ed49950272ca49261a39ec087fcae31ba`; frontend `HEAD == main == origin/main == 067b3e22401854f8c6d6db42dc0c5c1872fca6f8` after fetch.
- The clean detached worktree is `/Users/subhajlimanond/dev/munbon2-backend-phase-d-acceptance` at the exact backend SHA.
- The frozen 7/9 guest evidence matched its external archive digest-for-digest before the canonical guest was replaced. All four Phase C bundles reverified at both checksum layers.
- Only `munbon-control-plan-local` was replaced. The diagnostic guest and every preserved worktree remained untouched.
- Fresh canonical machine ID `01KZMYBSVC4TF6FH69QSKNYAKM` has the required Debian 12 arm64, 8 GiB, 4 CPU, 40 GiB, filesystem-isolated, network-isolated shape.

Provisioning result:

- `provision` passed SHA validation, both bundle creation/verification gates, fresh guest creation, and every harness transfer.
- Bootstrap recreated PostgreSQL/Redis state and reached `service_manifests`.
- All four Python virtual environments report no broken requirements.
- The first Node install, `npm --prefix services/auth ci --omit=dev --silent`, failed with `ERR_SOCKET_TIMEOUT` while fetching from the public npm registry. The preserved guest npm log is `/home/munbon/.npm/_logs/2026-08-10T05_08_20_897Z-debug-0.log`, SHA-256 `3e54b970ed624a9e16c955124adab6b88247a0f5e47f1fb6bbe67525171debd3`.
- This is a pre-stage infrastructure/bootstrap failure, not a product or acceptance-stage verdict: the guest source SHAs are exact, the canonical evidence directory contains zero files, `stage-state.json` is absent, the owner marker is absent, central auth is inactive, and no RID week was consumed.
- The partially provisioned guest was retained for inspection. No repair, retry, reprovision, stage skip, or acceptance command was attempted after the failure.

Authoritative truth remains 7/9 PASS at the older frozen candidate. Advancing Phase D requires explicit authorization to replace the failed partial guest and make a new clean provisioning attempt despite the no-reprovision rule; the next attempt must still run all nine stages sequentially with no repair after stage execution begins.

### Authorized fresh provisioning retry (2026-08-10 13:07 +0700)

- The user explicitly authorized deletion of the failed partial canonical guest. Before deletion, its exact machine ID, `service_manifests` phase, absent owner marker, and absent `stage-state.json` were revalidated.
- The failed guest was deleted and replaced with new canonical machine ID `01KZN1QSBSMMMSGYRF9BSAFW6P` at the same required isolated Debian 12 arm64 shape.
- The retry used the unchanged clean detached worktree and frozen backend/frontend SHAs. Both bundles and every harness transfer passed again.
- Bootstrap again recreated fresh PostgreSQL/Redis state and installed all four Python dependency sets successfully.
- The retry then failed at the same first Node installation boundary: `npm --prefix services/auth ci --omit=dev --silent` returned `ERR_SOCKET_TIMEOUT` while fetching from the public npm registry.
- The second preserved guest npm log is `/home/munbon/.npm/_logs/2026-08-10T06_05_33_144Z-debug-0.log`, SHA-256 `87b50fad0c3345ea64f557fb46f9c85f9b60dfc622fc24c07fb7ea7cd3cbbb82`.
- The second partial guest remains intact. Its source SHAs are exact, central auth is inactive, the owner marker is absent, the evidence directory contains zero files, `stage-state.json` is absent, and no acceptance stage or RID week was consumed.
- No repair, additional retry, stage skip, or acceptance command followed the repeated infrastructure failure.

Phase D remains pre-stage and incomplete. A further fresh attempt requires new authorization and should wait for npm-registry connectivity to be stable; changing bootstrap behavior would be a separate reviewed source remediation and would change the candidate lifecycle.

## Provisioning hermeticity remediation (2026-08-10 17:15:55 +0700)

Goal: preserve the second failed canonical guest, make provisioning failures diagnosable and recoverable without canonical reuse, stage all dependencies before runtime reset, unify Node/npm, and replace live canonical dependency acquisition with a content-addressed ARM64 bundle.

Preflight and preservation:

- Protected primary checkout remained on `main` at `d07fde2ed49950272ca49261a39ec087fcae31ba` with its pre-existing Coding Log modification and two untracked `.codex` pointer backups.
- Created isolated worktree `/Users/subhajlimanond/dev/munbon2-backend-provisioning-hermetic` on `fix/provisioning-hermetic-state` from exact `origin/main`.
- The second canonical guest remains running and unmodified. Reverified raw npm log SHA-256 `87b50fad0c3345ea64f557fb46f9c85f9b60dfc622fc24c07fb7ea7cd3cbbb82`, missing owner marker, missing stage state, and zero evidence files.
- Preserved sanitized host bundle `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-10-phase-d-bootstrap-failure-guest2-d07fde2e/`; inner and outer checksums passed. Outer-index SHA-256 is `db3910531afb0bcb34aa140203528e5116caba9b28eb51c907b93273937bd3d7`; sanitized log SHA-256 is `ee828a0c9da234bb549e9bb6fa3f476ff8682ab98668a437889ee02fa9973b4a`.
- The first capture attempt failed before writing evidence because root Git ownership checks rejected two metadata probes. Removed only the two newly created empty directories, changed those probes to run as `munbon`, and reran atomically.
- Auggie was unavailable through the current tool interface, so the required two-second semantic lookup could not be enforced. Fallback inspection covered `bootstrap-linux.sh`, `orchestrate.py`, `run-stage-suite.py`, the auth systemd unit, focused tests, lockfiles/manifests, and the acceptance runbook.
- Two read-only `terra_support` reviews independently confirmed the failure-observability, state-machine, destructive-ordering, toolchain, and test gaps. They also found that `LOCAL-RTA-1` repeats live pip installs and uses bare Node/npm for PM2 verification; the primary independently inspected those call sites.

Work unit 1 — provisioning contract primitives:

- Files: `ops/control-plan-read-local/provisioning_contract.py`, `ops/control-plan-read-local/tests/test_provisioning_contract.py`.
- Contract: only `created → dependency-staged → runtime-reset → ready` is accepted, with `failed` and `interrupted` terminal transitions; failure classifications are stable safe codes; secret-shaped log lines and credential URLs are redacted; state/failure files are atomic mode 600; dependency manifests bind exact backend/frontend SHAs, Debian ARM64/Python/Node/npm versions, input hashes, inventory, and every artifact hash.
- RED: `python3 -m pytest -q ops/control-plan-read-local/tests/test_provisioning_contract.py` failed 10/10 with the scaffolded functions raising `NotImplementedError`, which is the expected missing-behavior reason.
- GREEN: the same command passed 10/10 in 0.02 seconds.
- Runtime wiring is intentionally pending: the next slices connect these pure contracts to the guest bootstrap, host collector, dependency builder, stage manifest reinstall, and CLI.

Work unit 2 — host failure preservation and lifecycle enforcement:

- Files: `ops/control-plan-read-local/orchestrate.py`, `ops/control-plan-read-local/tests/test_orchestrate.py`.
- Contract: existing incomplete guests cannot be reprovisioned; terminal guests are evidence-only; failure collection does not require an owner marker; inner sanitized log/metadata checksums, exact metadata shape, state/metadata binding, and an outer checksum index are verified before atomic host finalization.
- RED: five focused host tests failed at their new lifecycle, safe-classification, and failure-bundle seams for the expected missing behavior.
- GREEN: focused host tests passed after wiring `CommandExecutionError`, safe collection, archive validation, diagnostic-only dependency building, and explicit CLI arguments. A later timestamp slice produced 3 expected fixture failures before all 52 contract/orchestrator tests passed.

Work unit 3 — content-addressed dependency closure:

- Files: dependency builder/validator, `dependency-roots/package*.json`, `python-closures.lock`, provisioning contract inputs, static behavioral tests, and the operations runbook.
- The build lane is fixed to the existing non-authoritative diagnostic guest and acquires Debian 12 ARM64 packages, Node 22.23.1/npm 10.9.8, PM2 5.4.3, Playwright 1.54.2/Chromium, six npm lock trees, and four Python wheel sets. Canonical bootstrap uses no public package registry.
- Every archive byte is indexed by SHA-256 and bound to exact backend/frontend SHAs and committed inputs. The four complete ARM64 Python wheel sets are additionally fail-closed by committed wheel counts and canonical checksum-index digests: 84 flow, 96 scheduler, 67 ROS/GIS, and 81 BFF wheels.
- RED/GREEN examples: unordered but valid checksum indexes were rejected before the validator was corrected and regression-tested; the validator initially used the guest-installed Node path before a focused RED required use of the Node binary extracted from the bundle itself.

Work unit 4 — prepare/reset/activate bootstrap and one toolchain:

- Files: `bootstrap-linux.sh`, the auth systemd unit, `run-stage-suite.py`, and their tests.
- Bootstrap now records timestamped phase/substep state and a sanitized failure bundle with exit code, classification, Node/npm/Python/Bash versions, and exact source/dependency identities. Dependency archive verification, offline apt/npm/pip installation, Prisma generation, and browser staging precede evidence archival, service quiescence, PostgreSQL recreation, and Redis flush.
- Node 22/npm 10 now runs auth installation/seeding/service execution, PM2, SCADA, Gate Web, Smart CMS, repository preflight, and stage-suite PM2 operations. `LOCAL-RTA-1` reinstalls Python manifests only from the verified local wheelhouse.
- The ready owner binds the dependency archive digest; `LOCAL-BASE-0` requires matching ready state, owner, backend/frontend SHAs, and dependency digest before stage execution.

Work unit 5 — diagnostic cold-cache qualification before commit:

- Built from temporary staged commit `9c902522e31ab500230d6d134be2cd5c9b53f25f` and frozen frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8` in `munbon-control-plan-write-ui-diagnostic`; the canonical guest was not read or mutated by this build.
- First build failed after all six npm cache fills because Debian's system Python had no pip. Remediation created a dedicated wheel-builder venv. Second build reached the final manifest gate and exposed order-sensitive checksum-index validation; remediation made exact-set validation order-independent and added a behavioral regression test.
- Third build passed and produced host archive `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-10-provisioning-precommit-dependencies.tar.gz`, 1,668,530,499 bytes, mode 600, SHA-256 `0c83aff8ef0f42f67ec8bb7a94bc5600e6e56724f6d401ebe3484f3253fa9c55`. Host validation accepted its exact source inputs, platform, inventory, and artifact hashes.
- Cold validation installed all six npm trees with `--offline`, all four Python environments with `--no-index --find-links`, passed all four `pip check` runs, and found bundled Chromium. After correcting the validator to use its scratch-extracted Node runtime, the full cold validation passed again; log SHA-256 is `617d4dc3a931fa1ebd2cdcc050225e3bf50d68e766cb49d2d6b0d5ae951ceae0`.
- This precommit archive is diagnostic evidence only. It cannot provision a canonical guest or qualify the eventual merge SHA.

Current local gates before independent QCHECK:

- `python3 -m pytest -q ops/control-plan-read-local/tests` -> 376/376 PASS.
- `node --test ops/control-plan-read-local/tests/*.js` -> 41/41 PASS.
- Black check, Python byte compilation, and Bash syntax checks for all three shell programs passed.
- The canonical guest remains frozen; no acceptance stage ran and no RID week was consumed.

Independent QCHECK and lifecycle-output remediation:

- Initial QCHECK found release blockers: canonical npm lifecycle scripts could still make direct downloads; the stage user could not read the private provisioning state; host timeout collection did not catch `TimeoutExpired`; the cold validator was not wired; apt recommend policies differed; URI sanitization was too narrow; failure collection was coupled to current `origin/main`; and the diagnostic build guest lacked an explicit identity/authorization preflight.
- All were remediated. npm lifecycle scripts and Prisma generation now run only in the diagnostic lane; six deterministic ARM64 `node_modules` archives are checksum-bound and canonical bootstrap does not invoke npm. The builder itself runs the full validator under `unshare -n`; bcrypt and Prisma Client must load there. Private state/failure evidence remains root-only, while a final atomic owner attestation is readable by the stage user. Host stage launch also validates private state and public owner together.
- `TimeoutExpired` now enters the same safe failure-collection path; canonical apt install uses `--no-install-recommends`; sanitization covers credential userinfo for every URI scheme plus URL/URI/DSN and secret-shaped assignments; failure collection dispatches without consulting current source branches; and the diagnostic lane requires the exact isolated guest shape, `--confirm-diagnostic-build`, and a mode-600 noncanonical purpose marker.
- Diagnostic lifecycle build attempts exposed two honest npm-tree validation exceptions after successful installs: the auth workspace reports missing dev dependencies when production-only, and Prisma generation leaves optional platform packages that `npm ls` reports as extraneous. Those two trees are instead validated by successful lockfile `npm ci`, manifest/artifact hashes, and egress-denied runtime loads of bcrypt/Prisma; the other four trees retain `npm ls --all` validation.
- The complete revised build passed from temporary staged SHA `789ba81f74e06bde485a6981eb4398c57248ed32`. Its egress-denied validator passed all Node, Python, Playwright, bcrypt, and Prisma checks. Host archive `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-10-provisioning-lifecycle-precommit-dependencies.tar.gz` is mode 600, approximately 1.6 GiB, and matched guest/host SHA-256 `465dfe8bb0d093a9dcb8d8d4684e1d8fbe8eec18ff51ce1ab0dd27de2bb8a2fd`; host manifest/inventory/input validation passed.
- QCHECK re-review cleared those findings and found two later publication/safety issues. The private `ready` transition now precedes final atomic owner publication, host `run_stage` rejects a private terminal state even if a stale public owner says ready, and owner-publication failure can transition private ready to failed/interrupted. Every nested Node archive is now validated before root extraction for root confinement, safe member types, safe links, and no member below a symlink path; the exact auth workspace symlink is narrowly allowlisted. All six already-built precommit archives passed the new inventory validator.
- The superseded diagnostic build scratch at `/opt/munbon/dependency-build/9c902522e31a-067b3e224018-30418` was removed only after its host archive and checksum evidence were retained. Failed later task-owned diagnostic scratch remains until final exact-SHA cleanup. No canonical guest file or state was changed.

Final QCHECK follow-up:

- The reported owner-publication gap was stale against the latest tree: `ready → failed/interrupted` was already allowed. Added a direct regression that walks the full lifecycle to private `ready`, simulates both ordinary failure and SIGTERM during final owner publication, and proves a checksummed terminal failure bundle remains collectable.
- The archive-context finding was valid. RED: six focused nested-archive tests failed because the validator had no archive-identity argument. GREEN: validation now requires one of the six exact archive names at every builder, egress-validator, and canonical-bootstrap call site; only the `auth` archive may contain the exact `@munbon/shared` workspace link, and the same link is rejected for all other archives.
- Focused result after remediation: `20 passed` for the provisioning contract, plus Bash syntax PASS for all affected scripts. The three consecutive final full-gate runs follow below.

Final full quality gates:

- Three consecutive identical runs passed with `389 passed` Python tests and `41 passed` Node tests in each run.
- Each run also passed Black check for all seven changed Python/test files, Bash syntax for all three provisioning shell programs, Python byte compilation for the orchestrator/contract/stage suite, and `git diff --check`.
- The recurring `pytest-asyncio` default-loop-scope deprecation warning is pre-existing tool configuration noise; it does not affect these synchronous operations tests or their results.

### Formal g-check — provisioning hermeticity remediation

Scope reviewed: the complete staged change across the host orchestrator, guest bootstrap, dependency builder and egress-denied validator, provisioning contract, stage-suite toolchain/offline reinstall wiring, auth systemd unit, runbook, lock inputs, and all changed tests.

Severity-ordered findings:

- CRITICAL: none.
- HIGH: none.
- MEDIUM: none.
- LOW: none.

Disposition and evidence:

- The two independent QCHECK rounds found and closed all identified safety/lifecycle issues, including lifecycle-script egress, private/public readiness publication, host timeouts, dependency-validator wiring, apt-policy parity, sanitization, diagnostic authorization, unsafe nested archives, and archive-specific workspace-link scoping.
- Function review: new logic is kept in composable functions with explicit state/error vocabulary; streaming hashes avoid unbounded reads; archive/state/failure validation fails closed; no hidden canonical network fallback or retry path remains.
- Test review: behavioral cases cover transport, integrity, interruption, terminal partial state, exact input drift, unsafe outer/inner archives, secrets, timeout propagation, destructive ordering, one toolchain, offline stage installs, stale-owner/private-state mismatch, owner-publication failure, and archive-context confinement. Assertions use independent expected structures/codes and exercise real defect paths.
- Implementation review: dependency acquisition completes and is egress-denied validated before canonical reset; canonical uses exact content and one Node/npm runtime; failure artifacts are atomic, sanitized, checksum-bound, host-preserved, and owner-independent; the second failed canonical guest remains untouched.
- Verification: three consecutive full gate runs each passed 389 Python tests, 41 Node tests, Black, Bash syntax, Python byte compilation, and `git diff --check`.

Open boundary, not a code finding: the precommit dependency archives are diagnostic-only and source-bound to predecessor temporary SHAs. An exact merged-SHA bundle and noncanonical Phase C requalification are still required after merge; no third canonical guest is authorized.

PR and hosted-check handling:

- Committed source as `412c50d63f6fbae05a2cf180a68a0413dbb7b5f0` (`fix(ops): make local provisioning content-addressed`), pushed `fix/provisioning-hermetic-state`, and opened PR #175.
- Both GitHub `Secret Scan (diff)` jobs completed with zero steps and the explicit annotation `The job was not started because your account is locked due to a billing issue.` Hosted CI is infrastructure-blocked, not passing.
- Reproduced the workflow locally at the exact PR head: the per-commit plus endpoint added-line secret scan passed. The full-tree scan found one baseline mismatch in `services/scheduler/coding-logs/2026-07-18 Impl (pr-4-4a-2-runtime-readiness).md`; the same carrier already exists at predecessor `d07fde2e` and is already absent from the predecessor `.security/full-tree-baseline.txt`, so it is pre-existing and unrelated to this change.
- GitHub reports `main` has no branch protection. A normal merge therefore requires no status bypass; the unrelated historical carrier was not changed or added to the baseline in this PR.

## Exact-merge provisioning attempt and base-Python remediation (2026-08-10 19:39:22 +0700)

Goal: qualify merged PR #175 at its exact SHA, replace the explicitly authorized second failed canonical guest only after bundle qualification, and stop truthfully if the new canonical bootstrap failed before acceptance.

Exact inputs and preservation:

- Backend `main == origin/main == b50b3d43745dca464387d383ebbc76147dfd958d`; frontend `main == origin/main == 067b3e22401854f8c6d6db42dc0c5c1872fca6f8` after fetch. The new isolated detached worktree was `/Users/subhajlimanond/dev/munbon2-backend-phase-d-b50b3d43`.
- Independent read-only preflight reverified the second guest ID `01KZN1QSBSMMMSGYRF9BSAFW6P`, exact isolated Debian 12 ARM64 shape, absent owner/provision state/stage state, zero evidence files, inactive central auth, and unchanged raw npm-log digest `87b50fad0c3345ea64f557fb46f9c85f9b60dfc622fc24c07fb7ea7cd3cbbb82`.
- Its preserved host failure bundle passed inner and outer checksum verification again. The older authoritative 7/9 archive also remained independently checksum-valid.
- The diagnostic guest built and egress-validated the exact merged-SHA dependency archive `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-10-phase-d-b50b3d43-dependencies.tar.gz`; host SHA-256 is `20f72cfd59b398f61ee176857486efa8ade8fd22e8b8afc1122b4a9dda72e1ab`.

Authorized replacement and failed bootstrap:

- The first OrbStack deletion command used the exact machine ID but OrbStack panicked before deletion; inventory proved the guest was still present. Deletion by the exact name then succeeded, and inventory proved only `munbon-control-plan-local` was absent. External failure evidence remained intact; the diagnostic and Ubuntu guests were untouched.
- Fresh canonical guest ID `01KZNTNB39DNZ9KNC3JQN7EWYT` was created with the required isolated Debian 12 ARM64, 8 GiB, 4 CPU, and 40 GiB shape. All source, frontend, dependency, harness, browser, auth, and verifier inputs transferred successfully and the dependency archive reverified at its exact host/guest digest.
- Bootstrap then failed before writing its first durable state, and automatic failure collection consequently had no state or failure directory to collect. The fresh Debian base has no `python3`; `bootstrap-linux.sh` invoked `/usr/bin/python3 provisioning_contract.py state` before the verified offline Debian closure installed Python.
- This is a pre-stage source/bootstrap defect. The owner marker, provisioning state, stage state, and evidence files are absent; no acceptance stage or RID week was consumed. The fresh failed guest remains running and unmodified after read-only diagnosis. A further deletion/replacement requires separate authorization.

TDD work unit — install the verified offline base closure before Python contract state:

- Files: `ops/control-plan-read-local/bootstrap-linux.sh`, `ops/control-plan-read-local/tests/test_local_artifacts.py`, and this Coding Log.
- Auggie semantic retrieval was bounded to two seconds and timed out. Fallback inspection covered the bootstrap entry point, orchestration call/collector, provisioning contract, dependency builder/validator, artifact tests, and the live pristine guest's base-tool inventory.
- Locked contract: validate the outer dependency digest and inner checksum index with base shell tools, install the already content-addressed offline Debian closure, and only then invoke the Python provisioning contract. This remains before Node/service staging, evidence archival, runtime quiescence, PostgreSQL recreation, Redis flush, or any acceptance stage.
- RED: `python3 -m pytest -q ops/control-plan-read-local/tests/test_local_artifacts.py -k installs_offline_python` failed because the first Python contract invocation preceded `phase base_packages`.
- GREEN: moved only the initial `created` transition after the offline Debian installation, recording the truthful `base_packages/offline-debian-packages` phase/substep. The same focused test passed, and `bash -n ops/control-plan-read-local/bootstrap-linux.sh` passed.
- Wiring: `orchestrate.py provision` invokes the changed `bootstrap-linux.sh` inside the fresh canonical guest; the verified dependency archive contains the pinned Debian 12 ARM64 `python3` closure; later `dependency-staged`, `runtime-reset`, and `ready` transitions continue through the same `provisioning_contract.py` state machine.
- Full local gate: `390 passed` Python operations tests, `41 passed` Node browser/harness tests, Black check, Bash syntax, Python byte compilation, and `git diff --check` all passed. The affected focused test then passed three consecutive identical runs. The existing `pytest-asyncio` loop-scope deprecation warning remains unrelated.

QCHECK remediation follow-up:

- Independent QCHECK rejected the initial happy-path-only change. P1: checksum, extraction, or offline package failure before Python remained uncollectable. P2: the first ordering test asserted the phase label rather than the actual `apt-get install` command.
- Added `bootstrap-provisioning-state.sh`, a Bash-only initial/terminal state and failure publisher. It validates every interpolated field, atomically publishes mode-600 JSON and checksum indexes, emits only a controlled failure line rather than raw bootstrap output, and classifies dependency-archive failures as integrity failures.
- `orchestrate.py provision` now transfers that helper, and `bootstrap-linux.sh` writes `created` state before archive handling. After offline Python installation, the existing Python contract accepts the shell-created state and owns all later transitions.
- RED for the expanded contract: three focused tests failed because the helper, transfer wiring, and initial-state call did not exist. GREEN proved a pre-Python base-package failure produces terminal state plus inner checksums, the host finalizer writes the outer index, state/metadata binding passes, and the shell-created state transitions through the Python contract to `dependency-staged`.
- Second independent QCHECK found one remaining P1: an executable but broken Python writer was selected and its failure suppressed without Bash fallback. RED: `test_failed_executable_contract_writer_falls_back_to_collectable_shell_bundle` failed because the dispatch function did not exist. GREEN: `write_bootstrap_failure` now prefers the Python publisher only when it returns success and otherwise invokes the Bash publisher. A separate success-path test proves the Python sanitizer remains preferred and redacts a secret-shaped raw line.
- Final independent QCHECK: GO, no P0-P2 findings. It confirmed atomic publication, controlled sanitization, broken-writer fallback, state-machine compatibility, host binding, exact guest-transfer wiring, safe optional interrupt expansion, and unchanged archive/runtime-reset ordering.
- Final primary gates: `395 passed` Python operations tests and `41 passed` Node browser/harness tests; Black, Bash syntax across all four provisioning shell programs, Python byte compilation, and `git diff --check` passed. Seven affected tests passed three consecutive identical runs.
- Runtime boundary remains unchanged: guest `01KZNTNB39DNZ9KNC3JQN7EWYT` is frozen with no owner, state, stage state, or evidence files from the failed predecessor candidate. No acceptance stage ran. Deletion/replacement is not part of this source-remediation PR and requires separate authorization after exact merged-SHA dependency qualification.

## Review (2026-08-10 19:55:51 +0700) - working-tree provisioning bootstrap failure contract

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-phase-d-b50b3d43`
- Branch: `fix/provisioning-bootstrap-python-order`
- Scope: working tree based on `b50b3d43745dca464387d383ebbc76147dfd958d`
- Commands Run: bounded Auggie attempt with direct-inspection fallback; staged status/name/stat and targeted production/test diffs; `python3 -m pytest -q ops/control-plan-read-local/tests`; `node --test ops/control-plan-read-local/tests/*.js`; focused failure-writer/state/collector tests three times; Black; `bash -n`; `py_compile`; `git diff --check`; independent QCHECK with two remediation rounds.

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

- The first exact merged-SHA fresh-guest run is deliberately deferred: the currently retained failed guest belongs to predecessor `b50b3d43`, and repository policy requires a new exact merged-SHA dependency bundle plus separate replacement authorization.
- The Bash-only failure log intentionally contains only a controlled phase code. Raw pre-Python output remains in the frozen guest and is not streamed because it cannot be safely sanitized without the verified Python contract.

### Recommended Tests / Validation

- After merge, rebuild and egress-validate the dependency bundle at the exact merge SHA, then prove on a newly authorized pristine Debian 12 ARM64 guest that shell state creation, offline Python installation, Python state handoff, and canonical readiness all pass.
- Preserve any future failed guest and verify both inner and outer failure indexes before authorizing replacement; do not reuse a partial machine.

### Rollout Notes

- No acceptance stage, runtime activation, write enablement, deployment, or AWS action is part of this source review.
- Runtime reset remains after `dependency-staged`; the new helper does not alter PostgreSQL, Redis, evidence, PM2, services, or flags.
- Formal g-check disposition: no remaining CRITICAL/HIGH/MEDIUM/LOW findings; source is ready for the standard branch/PR lifecycle, subject to exact-SHA runtime requalification after merge.

PR and hosted-check evidence:

- Committed the reviewed source as `a5b9a164581b7eb5d43c3708d866433f5f44c2ed` (`fix(ops): bootstrap pristine guests before Python`), pushed `fix/provisioning-bootstrap-python-order`, and opened PR #176.
- PR #176 is mergeable against base `b50b3d43745dca464387d383ebbc76147dfd958d`. GitHub reports no branch protection or required checks on `main`.
- Both `Secret Scan (diff)` jobs completed with zero steps and the explicit annotation `The job was not started because your account is locked due to a billing issue.` They are infrastructure-blocked, not passing or code-failing CI.
- Reproduced the workflow's per-commit plus endpoint added-line scan and full-tree baseline logic locally against the exact `b50b3d43..a5b9a164` range. It passed with no new secret or legacy-host carrier.

## Exact-merge offline Debian closure remediation (2026-08-10 21:18:32 +0700)

Goal: preserve the failed canonical guest, prove the exact cause of `base_packages/offline-debian-packages` exit 100, and make dependency construction plus validation reject a Debian closure that cannot be jointly installed on a pristine isolated guest.

- Frozen guest `01KZNY7Q6WAJ4QHAYTVVNJXXZ9` remained unmodified. Its checksum-bound failure state is tied to backend `53c6664a62350049ee4d1547a3caa03c0046809a`, frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`, and dependency bundle `ac94e9a3a561469a7d9302dc0b95aba42bde60c97780e4f21928d8bf6aee397c`.
- Read-only APT simulation reproduced the invalid closure. The bundle contained both `libcurl4-gnutls-dev` and `libcurl4-openssl-dev`, plus both `libqt5gui5` and `libqt5gui5-gles`; each pair is mutually conflicting. Recursive textual dependency enumeration selected all alternatives while suppressing conflict edges.
- Auggie semantic retrieval was bounded to two seconds and timed out. Fallback inspection covered `orchestrate.py`, the dependency builder and validator, `bootstrap-linux.sh`, focused artifact tests, the exact bundle inventory, and the frozen guest's sanitized package-manager diagnostics.
- Files changed: `ops/control-plan-read-local/build-dependency-bundle-linux.sh`, `ops/control-plan-read-local/validate-dependency-bundle-linux.sh`, and `ops/control-plan-read-local/tests/test_local_artifacts.py`.
- RED: `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m pytest -q ops/control-plan-read-local/tests/test_local_artifacts.py -k 'apt_resolver_for_pristine_debian_closure or simulates_complete_offline_debian_install'` failed exactly because the builder lacked an empty-status APT resolver and the validator lacked a complete offline installation simulation. Two stale tests that required the defective `apt-cache depends --recurse` path and its `--no-recommends` option were reconciled before implementation.
- GREEN: the builder now runs APT's resolver against an empty package-status database, downloads only the selected closure into the bundle cache, removes cache artifacts, and derives `package-names.txt` deterministically from the downloaded package metadata. The validator now simulates installing the complete explicit `.deb` set with empty status/lists/cache, disabled sources, and `--no-download`.
- Terra implementation stayed within its two-file production allowlist. The primary inspected the complete diff and independently reran the scoped GREEN test plus Bash syntax checks.
- Full gates: `397 passed` Python operations tests, `41 passed` Node browser/harness tests, Black check, Bash syntax across the four provisioning shell programs, Python byte compilation, and `git diff --check` all passed. The three affected tests passed three consecutive identical runs. The pre-existing `pytest-asyncio` loop-scope warning remains unrelated.
- Independent QCHECK: GO, no P0-P2 findings. It confirmed resolver selection, hermetic offline simulation, deterministic package inventory, scratch-only APT state, unchanged canonical guest state, and meaningful wiring assertions.

Wiring verification:

| Component | Non-test call site | Registration/config load | Schema/contract match |
| --- | --- | --- | --- |
| Debian dependency resolver | `ops/control-plan-read-local/build-dependency-bundle-linux.sh:206` | `ops/control-plan-read-local/orchestrate.py:605-628` transfers and invokes the builder | Empty APT status resolves the exact root set and downloaded bytes enter the content-addressed manifest |
| Offline joint-install validator | `ops/control-plan-read-local/validate-dependency-bundle-linux.sh:30` | `ops/control-plan-read-local/build-dependency-bundle-linux.sh:239` invokes it under `unshare -n` | Empty status/lists plus disabled sources and `--no-download` require the explicit local `.deb` set to be complete and conflict-free |
| Canonical package installation | `ops/control-plan-read-local/bootstrap-linux.sh:114` | `ops/control-plan-read-local/orchestrate.py:729` transfers the validator with canonical inputs | Bootstrap installs only the checksum-bound closure already accepted by the same offline validator |

Known boundary: runtime ARM64 bundle construction and pristine-guest installation remain post-merge exact-SHA gates. The failed guest is evidence-only; deletion or another canonical attempt still requires separate authorization.

## Review (2026-08-10 21:18:32 +0700) - working-tree offline Debian closure remediation

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend-offline-debian-closure`
- Branch: `fix/offline-debian-closure-resolution`
- Scope: working tree based on `53c6664a62350049ee4d1547a3caa03c0046809a`
- Commands Run: bounded Auggie attempt with direct-inspection fallback; staged name/stat and targeted diffs; focused RED/GREEN pytest; full Python operations and Node harness suites; Black; Bash syntax; Python byte compilation; affected tests three times; independent QCHECK; `git diff --check`

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
- The diagnostic builder has Debian Bookworm ARM64 repository metadata available during bundle construction; canonical validation and installation remain network-isolated.
- Exact bundle bytes may change as repository candidates change, but every produced archive remains bound by its own SHA-256 manifest and exact backend/frontend input digests.

### Recommended Tests / Validation
- Build the complete dependency archive in the protected diagnostic guest at the exact merged backend SHA and require the source-less APT simulation to pass under `unshare -n`.
- On a separately authorized pristine canonical guest, require the same exact archive to pass checksum validation and `offline-debian-packages` installation before any runtime reset or acceptance stage.

### Rollout Notes
- No acceptance stage, deployment, write activation, AWS action, or canonical guest mutation is part of this source review.
- Formal g-check disposition: no CRITICAL/HIGH/MEDIUM/LOW findings; proceed through the standard PR lifecycle, exact-SHA dependency build, and separately authorized canonical attempt.

## ARM64 Python wheel-closure refresh (2026-08-10 21:34:55 +0700)

Goal: clear the next fail-closed diagnostic bundle gate without weakening dependency reproducibility after PR #177 merged.

- The exact `22f18cb3a9ee3ba6481b6e15bc5e981d6e83f972` diagnostic build stopped before Debian resolution at `FAIL dependency_bundle_python_closure`. This had no acceptance meaning and did not mutate the canonical guest.
- A mode-600 replay log and an isolated ARM64 closure refresh in `munbon-control-plan-write-ui-diagnostic` independently computed all four wheel-set digests and counts. Flow Monitoring remained byte-identical at 84 wheels. Scheduler, ROS/GIS, and BFF retained counts 96, 67, and 81 but each replaced only `greenlet 3.5.4` with `greenlet 3.5.5`.
- Auggie was bounded to two seconds and timed out. Fallback inspection covered the builder, `python-closures.lock`, the four requirements manifests, provisioning manifest inputs, tests, prior lifecycle evidence, and old-versus-new wheel filenames.
- Files changed: `ops/control-plan-read-local/python-closures.lock`, `ops/control-plan-read-local/tests/test_local_artifacts.py`, and this Coding Log.
- RED: `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m pytest -q ops/control-plan-read-local/tests/test_local_artifacts.py -k python_closure_lock_content_addresses_all_arm64_wheel_sets` failed because the three committed digests disagreed with the independently computed ARM64 closure.
- GREEN: refreshed only the three changed digests and strengthened the test to compare the complete four-service digest/count structure against the precomputed expectations. The focused test passed, then passed three consecutive identical runs.
- Full gates: `397 passed` Python operations tests, `41 passed` Node browser/harness tests, Black, Bash syntax, Python byte compilation, and `git diff --check` passed. The pre-existing `pytest-asyncio` warning remains unrelated.
- QCHECK: no findings. The aggregate lock remains fail-closed if any public transitive artifact drifts after commit; exact wheel bytes and every requirements/lock input remain bound by the dependency manifest.

## Review (2026-08-10 21:34:55 +0700) - working-tree ARM64 Python closure refresh

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend-python-closure-refresh`
- Branch: `fix/refresh-python-wheel-closure`
- Scope: working tree based on `22f18cb3a9ee3ba6481b6e15bc5e981d6e83f972`
- Commands Run: bounded Auggie attempt with direct fallback; exact staged diff; diagnostic ARM64 wheel derivation; old/new wheel-name comparison; focused RED/GREEN; full Python and Node suites; affected test three times; Black; Bash syntax; Python byte compilation; `git diff --check`

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
- The `greenlet 3.5.5` ARM64 wheel remains compatible with the existing SQLAlchemy consumers; the diagnostic validator's four isolated `pip install` plus `pip check` runs are the authoritative compatibility gate.

### Recommended Tests / Validation
- Rebuild the complete exact-merge dependency archive and require all four digest/count comparisons, offline wheel installation, four `pip check` runs, and the source-less Debian APT simulation to pass.

### Rollout Notes
- No canonical deletion, provisioning, acceptance stage, deployment, or activation is part of this review.
- Formal g-check disposition: no CRITICAL/HIGH/MEDIUM/LOW findings; proceed through one standard PR and exact-merge bundle rebuild.

## Canonical bootstrap and evidence-integrity remediation (2026-08-10 22:08:22 +0700)

Goal: remove the pristine-guest offline APT failure and close the remaining stage 8/9 session and evidence-publication gaps before another canonical attempt.

- The single fresh canonical guest `01KZP2DG7VJSRQZBBMN9ZV0T9X` failed before stage 1 at `base_packages/offline-debian-packages` with exit 100. The automatic failure state and both inner and outer host checksums passed; no owner, stage state, or acceptance artifact exists.
- Read-only diagnosis on the preserved failed guest proved that configured package sources caused APT to prefer repository URIs despite every exact package being present locally. The same real-status simulation passed when the source list was disabled and every candidate was reported as `local-deb`.
- TDD remediation makes bootstrap create an empty source-parts directory and disables the source list for the canonical `--no-download` install. It also gives WRITE-UI a best-effort post-login cleanup boundary, surfaces manifest write/checksum publication failures through exit 70 and a safe host classification, and validates the exact checksum-bound 9/9 evidence inventory before writing a mode-600 outer checksum index.
- Primary QCHECK caught and fixed two integration gaps before formal review: collection initially finalized while its transport archive was still present, and the host accepted a partial harness-hash identity. A real tar stream/extract/finalize test now covers the former, while exact harness inventory and interrupt-class best-effort cleanup tests cover the latter and ensure cleanup cannot mask the primary failure.
- Files changed: `ops/control-plan-read-local/bootstrap-linux.sh`, `ops/control-plan-read-local/orchestrate.py`, `ops/control-plan-read-local/run-stage-suite.py`, their three focused Python test modules, and this Coding Log.
- RED was confirmed independently for source-enabled bootstrap, missing WRITE-UI failure logout, silent failure-manifest publication, absent host evidence finalization/classification, partial harness identity, and interrupt-class cleanup masking.
- GREEN: `407 passed` Python operations tests and `41 passed` Node harness/browser tests. The 10 affected contracts passed three consecutive runs. Black, Bash syntax, Python byte compilation, and `git diff --check` passed. The pre-existing `pytest-asyncio` warning remains unrelated.

## Review (2026-08-10 22:08:22 +0700) - working-tree canonical bootstrap and stage evidence integrity

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend-canonical-stage-integrity`
- Branch: `fix/canonical-stage-evidence-integrity`
- Scope: working tree based on `f99c1f4f253cd5e70cf832a53e8ea2a735850bf8`
- Commands Run: direct entry-point and invariant inspection after bounded Auggie fallback; working-tree name/stat and targeted diffs; preserved-guest APT source-enabled/source-less simulations; focused RED/GREEN; full Python and Node suites; affected tests three times; Black; Bash syntax; Python byte compilation; `git diff --check`

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
- The source-less real-status simulation is strong behavioral evidence for the bootstrap fix, but an actual pristine ARM64 install remains a post-merge exact-SHA gate.
- Canonical collection intentionally accepts only the exact successful nine-stage inventory; failed-stage evidence remains on the guest and is not misrepresented as a successful collection.

### Recommended Tests / Validation
- Merge through one ordinary PR, rebuild the complete dependency archive at the exact merged backend SHA, and require the diagnostic builder's source-less validator to pass.
- On a separately authorized pristine canonical guest, require offline package installation, all nine stages with one pinned `--as-of-date`, exact stage state, service/dark-flag restoration, host checksum validation, and outer checksum creation.

### Rollout Notes
- The failed guest and immutable failure archive remain preserved. No stage, deployment, activation, AWS action, or retry occurred during this source review.
- Formal g-check disposition: no CRITICAL/HIGH/MEDIUM/LOW findings; proceed through the ordinary PR lifecycle, exact-SHA bundle rebuild, and separately authorized canonical replacement.

## Exact-merge canonical provisioning attempt (2026-08-11 05:05 +0700)

Goal: use the separately authorized replacement of failed guest `01KZP2DG7VJSRQZBBMN9ZV0T9X` for one fresh provisioning at backend `dd81b687a558d696828ebf1d8848d8936f5cade8`, frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`, and dependency bundle `63ed11aaa58901b9ff8451a6f2239ec00267377b5e3760b309588d5afdc08f9f`, followed by one pinned authoritative nine-stage run only if provisioning reached ready.

- Reverified `HEAD == main == origin/main` for both repositories, bundle mode `0600` and SHA-256, both checksum layers of the predecessor failure archive, and the exact live ID/name/shape mapping before mutation. The OrbStack CLI panicked on deletion by ID without changing inventory; deletion by the uniquely mapped authorized name then succeeded. The diagnostic and Ubuntu guests remained unchanged.
- Fresh isolated Debian 12 ARM64 guest `01KZPVAFAXG3ZNQ649ZBFSYMHJ` was created with 8 GiB, 4 CPU, and 40 GiB. Exact source, frontend, dependency, harness, auth, and verifier inputs transferred successfully.
- Provisioning failed before readiness at `base_packages/offline-debian-packages` with exit 100 and classification `nonretryable-bootstrap`. The raw mode-600 guest log records APT 2.6.1 `Internal Error, Pathname to install is not absolute 'perl-modules-5.36_5.36.0-7+deb12u3_all.deb'`; the referenced package archive exists at an absolute checksum-indexed path. The bundle validator's empty-status simulation had passed, and a post-failure no-write real-status simulation also resolved every candidate as `local-deb`, so the uncovered boundary is APT's real install/acquire execution rather than dependency resolution or missing bundle bytes.
- The orchestrator preserved a sanitized mode-600 failure bundle at `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-11-phase-d-dd81b687-bootstrap-failure-canonical-attempt-1`; its inner and outer checksum indexes both pass. Metadata binds the exact backend, frontend, dependency digest, phase, substep, exit 100, and classification.
- The fresh failed guest remains running and unmodified after read-only diagnosis. Its terminal provisioning state is present; owner and stage state are absent; the evidence directory contains zero files; auth is inactive. No acceptance stage, pinned RID date/week, deployment, activation, or AWS action occurred. The authorized single provisioning attempt is consumed, and the nine-stage run was not started.

## APT real-install parity remediation (2026-08-11)

Goal: replace direct local `.deb` installation with one checksum-bound flat repository and a shared installer used by validation and canonical bootstrap, then prove it on one disposable non-authoritative guest before any authorized canonical replacement.

- User authorization covers TDD remediation, the ordinary PR/merge lifecycle, one disposable qualification guest, and only after qualification passes deletion of failed canonical guest `01KZPVAFAXG3ZNQ649ZBFSYMHJ`, one fresh canonical provisioning, and one pinned nine-stage run.
- Work is isolated in `/Users/subhajlimanond/dev/munbon2-backend-apt-real-install-parity` on `fix/apt-real-install-parity`, based exactly on `origin/main@dd81b687a558d696828ebf1d8848d8936f5cade8`. Dirty primary-worktree artifacts remain untouched.
- Auggie semantic retrieval was bounded to two seconds and timed out. Fallback inspection covered the dependency builder, validator, bootstrap, provisioning manifest contract, orchestrator wiring, and focused tests.
- Read-only Terra risk analysis independently confirmed the defect boundary: the builder and validator exercised dependency resolution only, while bootstrap was the first real APT acquire/install transaction. It recommended the same flat-repository acquire path, checksum binding, isolated APT state, and pristine qualification boundary.
- Locked contract: manifest schema 2 requires `debian/Packages`, `debian/Packages.gz`, at least one `.deb`, exact `package-specs.txt`, inventory `package-names.txt`, and `install-debian-closure-linux.sh`. The shared installer must use only a `file:` source, scratch APT lists/cache, exact `Package=Version` requests, and no `--no-download` or direct `.deb` arguments.
- RED: the focused provisioning/artifact selection failed 14 tests for the expected reasons: no repository index/spec generation, no shared installer behavior or wiring, bootstrap still passed direct `.deb` paths with `--no-download`, the orchestrator did not embed the installer, and schema 1 still accepted non-installable inventories.
- GREEN: the builder now creates deterministic `Packages`/`Packages.gz` indexes, exact `Package=Version` specs, and an embedded shared installer before manifest creation. The installer disables host APT configuration and external sources, uses scratch lists/cache plus the checksum-bound `file:` repository, simulates against empty status, and performs real installation against system status without direct `.deb` arguments or `--no-download`.
- Manifest schema 2 now rejects presence-only repositories: it verifies compressed/uncompressed index parity, strict unique package records, exact `.deb` filename/size/SHA-256 coverage, and sorted package-name/spec coherence before accepting or creating a manifest.
- Primary QCHECK added fail-closed rejection of option-shaped package specs and isolated APT main/parts configuration. Independent QCHECK initially returned NO-GO for missing exact-version downgrade permission and missing diagnostic `dpkg-scanpackages` preflight; both were fixed under separate RED/GREEN tests. The final independent re-review returned GO with no P0-P3 findings.
- Exact local downgrades are permitted only in the real-install branch, alongside local-only sources and exact checksum-bound specs. The diagnostic lane now runs a named `dpkg-scanpackages --version` preflight; the live diagnostic guest also exposes `/usr/bin/dpkg-scanpackages`.
- Full gates after remediation: `421 passed` Python operations tests and `41 passed` Node harness/browser tests. The 21 affected contracts passed three consecutive identical runs. Black, Bash syntax across all four affected shell scripts, Python byte compilation, and `git diff --check` passed. The pre-existing `pytest-asyncio` loop-scope warning remains unrelated.
- The root `make test` target returned zero but attempted only `services/sensor-data/vercel-deployment`, whose package has no `test` script; because the Makefile suppresses service failures with `|| true`, this is recorded as a non-authoritative legacy target rather than passing evidence.

Wiring verification:

| Component | Non-test call site | Registration/config load | Schema/contract match |
| --- | --- | --- | --- |
| Flat Debian repository builder | `ops/control-plan-read-local/build-dependency-bundle-linux.sh` | `ops/control-plan-read-local/orchestrate.py` transfers the builder, contract, validator, and installer to the owned diagnostic guest | Schema 2 binds every index, spec, `.deb`, and installer byte before archive creation |
| Shared offline installer | `ops/control-plan-read-local/install-debian-closure-linux.sh` | Embedded at bundle root and invoked by both validator and bootstrap | Simulation uses empty status; canonical installation uses real status; both share local acquire/cache semantics |
| Diagnostic validation | `ops/control-plan-read-local/validate-dependency-bundle-linux.sh` | Builder invokes it under `unshare -n` after schema validation | Exact specs must resolve from the generated local repository with no network namespace |
| Canonical bootstrap | `ops/control-plan-read-local/bootstrap-linux.sh` | `orchestrate.py` transfers bootstrap and the exact content-bound archive | Real APT acquire/install receives absolute scratch-cache paths and permits only exact local downgrades |

## Review (2026-08-11 05:36:32 +0700) - working-tree APT real-install parity remediation

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend-apt-real-install-parity`
- Branch: `fix/apt-real-install-parity`
- Scope: working tree based on `dd81b687a558d696828ebf1d8848d8936f5cade8`
- Commands Run: bounded Auggie attempt with targeted-inspection fallback; complete production/test diff and untracked-installer inspection; focused RED/GREEN cycles; full Python and Node operations suites; affected contracts three times; Black; Bash syntax; Python byte compilation; `git diff --check`; legacy `make test`; live read-only diagnostic toolchain preflight; independent QCHECK with remediation and re-review

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
- Source tests and the diagnostic empty-status simulation do not prove an actual dpkg mutation. The separately authorized pristine Debian 12 ARM64 qualification guest remains mandatory before deleting canonical guest `01KZPVAFAXG3ZNQ649ZBFSYMHJ`.
- Qualification is non-authoritative and must use the exact merged backend SHA, exact frontend SHA, and exact content-addressed schema 2 dependency archive; it cannot advance acceptance state.

### Recommended Tests / Validation
- Merge through one ordinary PR, build and validate the dependency archive on the owned diagnostic guest at the exact merge SHA, then create one disposable pristine qualification guest and require real installation plus dpkg-state verification.
- Only after qualification passes, reverify the preserved canonical failure archive and exact guest mapping, delete the authorized failed guest, provision one fresh canonical guest, and run the nine stages once with one pinned `--as-of-date`.

### Rollout Notes
- No canonical guest mutation, acceptance stage, deployment, activation, or AWS action occurred during source remediation and review.
- Formal g-check disposition: no remaining CRITICAL/HIGH/MEDIUM/LOW findings; source is ready for the standard commit/PR/merge lifecycle and exact-merge qualification gates.

## Exact-merge ARM64 Python closure refresh after PR #180 (2026-08-11)

Goal: clear the exact-merge dependency build's fail-closed Python closure gate without weakening reproducibility, before any qualification or canonical guest action.

- PR #180 merged as `a71bd1edba7935962e207a4e08a6f983539f9fdb`; backend local `main` and `origin/main` were synchronized exactly, with frontend `067b3e22401854f8c6d6db42dc0c5c1872fca6f8` unchanged.
- The first exact-merge dependency build and one observability-only replay both failed before Debian resolution at `FAIL dependency_bundle_python_closure`; no archive was created. The replay log is mode 600 at `/opt/munbon/dependency-build/a71bd1edba79-067b3e224018-44712/build-replay.log` in the owned diagnostic guest.
- A dedicated mode-700 diagnostic derivation at `/opt/munbon/dependency-build/a71bd1edba79-067b3e224018-44712/python-closure-refresh-1` computed all four ARM64 wheel-set digests and counts from the exact source bundle. Its mode-600 summary records counts 84, 96, 67, and 81, unchanged from the committed contract.
- Complete filename comparison against the prior accepted derivation found only: Flow Monitoring `platformdirs 4.11.1 -> 4.11.2` and `virtualenv 21.7.3 -> 21.7.4`; Scheduler and BFF `platformdirs 4.11.1 -> 4.11.2`; ROS/GIS is byte-identical.
- Auggie semantic retrieval was bounded to two seconds and timed out. Targeted fallback inspection covered `python-closures.lock`, the builder's digest/count enforcement, the full-structure test, and manifest input binding.
- Files changed: `ops/control-plan-read-local/python-closures.lock`, `ops/control-plan-read-local/tests/test_local_artifacts.py`, and this Coding Log.
- RED: `python3 -m pytest -q ops/control-plan-read-local/tests/test_local_artifacts.py -k python_closure_lock_content_addresses_all_arm64_wheel_sets` failed because the test's independently derived three new digests disagreed with the stale committed lock, while counts and ROS/GIS remained unchanged.
- GREEN: refreshed only the three changed digests. The focused full-structure test passed, then passed three consecutive identical runs; the unchanged counts and ROS/GIS digest remain explicit assertions.
- Full gates: `421 passed` Python operations tests, `41 passed` Node harness/browser tests, Black, builder Bash syntax, Python byte compilation, and `git diff --check` passed. The pre-existing `pytest-asyncio` warning remains unrelated.
- Primary QCHECK: no findings. The test oracle is the independent ARM64 derivation, not the production lock; requirements, service order, counts, builder logic, and manifest wiring are unchanged. The next exact-merge bundle build remains the fail-closed integration gate.

## Review (2026-08-11 12:04:52 +0700) - working-tree exact-merge ARM64 Python closure refresh

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend-python-closure-refresh-a71`
- Branch: `fix/refresh-python-wheel-closure-a71`
- Scope: working tree based on `a71bd1edba7935962e207a4e08a6f983539f9fdb`
- Commands Run: bounded Auggie attempt with targeted fallback; exact old/new wheel filename comparison; focused RED/GREEN; full Python and Node operations suites; focused contract three times; Black; builder Bash syntax; Python byte compilation; staged name/stat and targeted diff; `git diff --check`

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
- Public registry candidates can drift again before a later build; the aggregate digest gate intentionally fails closed and requires a new reviewed lock rather than silently accepting different bytes.

### Recommended Tests / Validation
- Merge through one ordinary PR, rebuild the complete dependency archive at the exact new merge SHA, and require schema 2 plus all offline dependency validators to pass before qualification.

### Rollout Notes
- No guest creation, canonical mutation, acceptance stage, deployment, activation, or AWS action occurred during this refresh.
- Formal g-check disposition: no remaining CRITICAL/HIGH/MEDIUM/LOW findings; proceed through the standard sequential PR lifecycle.
## Exact-merge bundle and qualification infrastructure boundary (2026-08-11)

- PR #181 merged as `22f6731ca93198269f330ddab6fc6a7c270d3469`; backend `HEAD`, local `main`, and `origin/main` were synchronized exactly. Frontend `HEAD`, local `main`, and `origin/main` remained `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`.
- The complete schema-2 dependency bundle passed diagnostic construction, manifest validation, network-isolated validation, host validation, and cleanup. The mode-600 archive is `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-11-phase-d-22f6731c-dependencies.tar.gz`, size `1608904861`, SHA-256 `fe004f0d1328edc2444940210b145afe4117feaa756bbfe64843a0dd195b4b45`, with 963 indexed artifacts including 470 Debian artifacts.
- Immediately before qualification creation, the predecessor failure archive passed both inner and outer checksum verification. Canonical guest `munbon-control-plan-local` still mapped uniquely to `01KZPVAFAXG3ZNQ649ZBFSYMHJ`; no canonical mutation occurred.
- Two attempts to create the authorized disposable guest `munbon-control-plan-apt-qualification` failed before a guest existed with `make rootfs: download rootfs: stream to file: unexpected EOF`. Inventory after both failures contained only the preserved canonical guest, diagnostic guest, and pre-existing Ubuntu guest.
- Between attempts, OrbStack 2.2.1 reported running, `orbctl doctor` passed, host storage had 135 GiB available, its own HTTPS endpoint transferred successfully, and the live network path reported viable/good. A direct Debian cloud-image transfer reset, while system and environment proxy settings were empty.
- The second identical infrastructure failure ended retrying. `orbctl update --check` reports a signed stable 2.2.2 update, but installing a host virtualization-runtime update can interrupt all existing guests and is outside the guest-specific mutation authorization. Qualification, canonical deletion, fresh canonical provisioning, and the pinned nine-stage run remain pending that narrow infrastructure decision.

## APT real-install qualification and canonical Node-runtime failure (2026-08-11)

Goal: after explicit authorization, repair the OrbStack image-download boundary, prove the schema-2 APT closure through one disposable non-authoritative real dpkg transaction, and only on qualification success replace the exact failed canonical guest and perform the single authorized provisioning attempt.

- The user explicitly authorized installing the stable OrbStack update offered by `orbctl`, including required guest pauses/restarts. The bundled signed Sparkle updater installed OrbStack `2.2.2 (2020200)` from `2.2.1`; all three pre-existing guests returned running with unchanged identities. `orbctl doctor` passed after relaunch.
- A replacement create then succeeded for isolated Debian 12 ARM64 qualification guest `munbon-control-plan-apt-qualification` (`01KZR32KE37W0PSTQ4F8X8EZKB`, 8 GiB, 4 CPU, 40 GiB). OrbStack 2.2.2 `push`/`pull` remained broken for isolated homes, so the exact bundle was transferred through stdin after a five-byte mode-600 probe; guest size and SHA-256 matched `1608904861` and `fe004f0d1328edc2444940210b145afe4117feaa756bbfe64843a0dd195b4b45`.
- Qualification passed: all 963 inner bundle entries verified; the shared installer completed a real APT/dpkg mutation with exit 0; 372 packages were unpacked and configured; every one of 466 exact `Package=Version` specs matched `dpkg-query`; `dpkg --audit` was empty; `apt-get check` passed. Owner, provisioning stage state, acceptance evidence, and evidence-stage state were absent.
- Qualification remained explicitly non-authoritative (`authoritative=false`, `acceptance_evidence=false`). Its mode-600 host archive is `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-11-apt-real-install-qualification-22f6731c.tar.gz`, SHA-256 `1448ebb44ecbe99700ec8fc2222c106f04a613fa14ab6f406d3b4f2fc4a8689f`. Because native pull was broken, a recoverable mode-600 base64 carrier was retained with SHA-256 `f0d99339afca52e22b7def5afec29c498a99a50b847515656b9313dae62afac9`; decoded bytes match the guest archive. The outer index SHA-256 is `25daf5992af148b5e76f61c50c855c9b0c32731be82e9906a27aa4dd6ee20f1e`; every inner and outer entry passed. The disposable guest was then deleted by its uniquely mapped name.
- After qualification passed, backend `HEAD == main == origin/main == 22f6731ca93198269f330ddab6fc6a7c270d3469`, frontend `HEAD == main == origin/main == 067b3e22401854f8c6d6db42dc0c5c1872fca6f8`, the mode-600 bundle digest, both predecessor failure-archive checksum layers, exact failed canonical mapping `munbon-control-plan-local == 01KZPVAFAXG3ZNQ649ZBFSYMHJ`, absent owner/stage state, and zero acceptance files were reverified. Only that authorized guest was permanently deleted; its predecessor failure archive remains preserved.
- The orchestrator created fresh canonical guest `munbon-control-plan-local` (`01KZR3P6V5XA1NYDDH9N68TTXD`) with the prescribed Debian 12 ARM64 isolated shape and transferred all exact inputs. Canonical APT installation completed, proving the original direct-`.deb` parity defect is remediated.
- Provisioning then failed fail-closed before readiness at `phase=node_runtime`, `substep=node-archive`, exit 1, classification `nonretryable-bootstrap`. The sanitized log ends with `/usr/bin/env: ‘node’: No such file or directory` and `FAIL node_runtime_version`. No acceptance stage was started.
- Read-only diagnosis proves a distinct Node-runtime PATH parity defect. `/opt/node-v22.23.1-linux-arm64/bin/node` exists and reports `v22.23.1`; no system `node` exists on the pristine guest PATH; direct execution of the bundled npm launcher exits 127 because its `/usr/bin/env node` shebang cannot resolve Node; the same launcher reports `10.9.8` when `PATH=/opt/node-v22.23.1-linux-arm64/bin:/usr/bin:/bin`. `bootstrap-linux.sh` checks npm without that PATH, while the reused diagnostic builder/validator environment had a system Node and therefore masked this pristine-bootstrap boundary.
- The new guest remains running and evidence-only with failed provisioning state bound to backend `22f6731c...`, frontend `067b3e22...`, and dependency `fe004f0d...`; owner is absent and the acceptance evidence directory contains zero files. The automatically collected mode-600 failure archive is `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-11-phase-d-22f6731c-bootstrap-failure-canonical-attempt-1`; inner and outer checks pass. Its outer-index SHA-256 is `0d4b6061f6da9f02441843c96ff7ecc2531602408479a9e13574e7ca7ff242f4`, and sanitized-log SHA-256 is `e2085dd87a1a2159dd89854f46f8f50d0a0cfc0fff187d5a63e89134324a21f5`.
- Stop condition: the single authorized canonical provisioning attempt is consumed. No repair, retry, stage, deployment, activation, or AWS action occurred after failure. A new TDD/PR lifecycle for the distinct Node PATH parity defect and any later canonical replacement require explicit authorization.

## Node-runtime PATH parity remediation (2026-08-11)

Goal: make dependency build, offline validation, canonical bootstrap, and failure metadata resolve the checksum-bound npm launcher through its sibling bundled Node binary even when pristine Debian exposes no ambient `node` command.

- Work is isolated in `/Users/subhajlimanond/dev/munbon2-backend-node-runtime-path-parity` on `fix/node-runtime-path-parity`, based exactly on `origin/main@22f6731ca93198269f330ddab6fc6a7c270d3469`. The dirty primary Coding Log and two pre-existing untracked pointer backups remain untouched.
- Auggie semantic retrieval was bounded to two seconds and timed out. Targeted fallback inspection covered the Node archive extraction/version checks in `build-dependency-bundle-linux.sh`, `validate-dependency-bundle-linux.sh`, and `bootstrap-linux.sh`, plus failure tool-version capture in `bootstrap-provisioning-state.sh` and the existing artifact tests.
- Locked contract: every bundled npm version probe must be command-scoped to `PATH=${NODE_ROOT}/bin:/usr/bin:/bin` (or lowercase helper equivalent). A global PATH export, system Node installation, symlink, or architecture/public-interface change is out of scope.
- RED 1: `python3 -m pytest -q ops/control-plan-read-local/tests/test_local_artifacts.py::test_node_runtime_version_checks_resolve_bundled_npm_without_ambient_node` failed all three parameters because builder, validator, and bootstrap invoked the npm launcher without a bundled Node PATH.
- GREEN 1: the same parameterized test passed `3 passed`; all three scripts now provide only the command-scoped bundled-first PATH to npm's `/usr/bin/env node` shebang.
- Independent read-only Terra analysis found one evidence-provenance gap: `bootstrap-provisioning-state.sh` captured `npm=unknown` for the same reason. RED 2: `python3 -m pytest -q ops/control-plan-read-local/tests/test_local_artifacts.py::test_bootstrap_failure_metadata_resolves_bundled_npm_without_ambient_node` failed because the helper was unbound.
- GREEN 2: the helper now applies the same command-scoped PATH and the combined focused selection passed `4 passed, 29 deselected`. Bash syntax passed for all four affected shell scripts.
- Files changed: the four shell scripts above, `ops/control-plan-read-local/tests/test_local_artifacts.py`, and this Coding Log. Runtime/public interfaces, dependency versions, archive schema, service configuration, and acceptance contracts are unchanged.
- Focused parity selection passed three consecutive identical runs (`4 passed, 29 deselected` each). The affected provisioning/artifact/orchestration modules passed `116 passed`; the complete operations Python suite passed `425 passed`; and the complete Node operations suite passed `41 passed`.
- Formatting and static gates passed: Black check for the edited Python test, Python byte compilation, Bash syntax for all four edited shell scripts, and `git diff --check`.
- A read-only probe on preserved failed guest `01KZR3P6V5XA1NYDDH9N68TTXD` reproduced the executable contract without mutating it: bundled Node reports `v22.23.1`; npm with ambient `/usr/bin:/bin` exits 127; the identical launcher with bundled-Node-first PATH reports `10.9.8`.
- The root `make test` target returned zero while printing `npm error Missing script: "test"` for `services/sensor-data/vercel-deployment`; because the target does not propagate that service failure, it is recorded as a non-authoritative legacy target rather than passing evidence.

Wiring verification:

| Component | Non-test call site | Runtime registration | Contract evidence |
| --- | --- | --- | --- |
| Bundle construction | `build-dependency-bundle-linux.sh` Node archive version gate | Invoked by the diagnostic bundle build lane | Bundled npm resolves only the just-extracted sibling Node |
| Offline validation | `validate-dependency-bundle-linux.sh` Node archive version gate | Invoked under network isolation during bundle validation | Same fixed Node/npm versions and bundled-first command PATH |
| Canonical provisioning | `bootstrap-linux.sh` `node_runtime/node-archive` gate | Transferred and invoked by `orchestrate.py` | Pristine Debian no longer depends on ambient system Node |
| Failure provenance | `bootstrap-provisioning-state.sh` tool-version capture | Called by bootstrap failure handling | npm version remains observable instead of degrading to `unknown` |

- Primary QCHECK found no implementation or test-contract defect. The change is minimal, command-scoped, preserves existing domain vocabulary, and does not introduce a global PATH or unbound dependency.
- Independent read-only QCHECK returned GO for source delivery with no P0-P2 findings. It recorded one non-blocking P3 test boundary: source assertions prove the four production call sites are wired, while one fresh ARM64 qualification must prove the real npm shebang path before any canonical deletion.

## Review (2026-08-11 22:51:52 +0700) - staged Node-runtime PATH parity remediation

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend-node-runtime-path-parity`
- Branch: `fix/node-runtime-path-parity`
- Scope: six staged files based on `22f6731ca93198269f330ddab6fc6a7c270d3469`
- Commands Run: bounded Auggie attempt with targeted fallback; complete production/test diff; focused RED/GREEN cycles; affected contracts three times; touched-module and complete Python suites; complete Node operations suite; Black; Bash syntax; Python byte compilation; `git diff --check`; non-enforcing legacy `make test`; preserved-guest read-only executable probe; independent QCHECK

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
- The source assertions establish exact production wiring but are not authoritative ARM64 execution evidence. The authorized disposable pristine qualification guest must clear the bundled npm check with no ambient Node before canonical guest `01KZR3P6V5XA1NYDDH9N68TTXD` may be deleted.

### Recommended Tests / Validation
- Merge through one ordinary PR, rebuild and validate the complete dependency archive at the exact merge SHA, then run one disposable non-authoritative Debian 12 ARM64 qualification using the exact archive.
- Only after qualification passes, reverify the preserved failure evidence and exact guest identity, delete the authorized failed canonical guest, provision one fresh canonical guest, and run all nine stages once at one pinned `--as-of-date`.

### Rollout Notes
- Source review did not mutate any guest, acceptance stage, deployment, activation, or AWS resource.
- Formal g-check disposition: no remaining CRITICAL/HIGH/MEDIUM/LOW findings; source is ready for the standard commit/PR/merge lifecycle and exact-merge qualification gate.

## Node-runtime exact-merge qualification and canonical acceptance verdict (2026-08-12)

- PR #182 merged normally as `fd88b9fbadc77e3b1230b359bd08c5264a12b6db`; backend `HEAD == main == origin/main` and frontend `HEAD == main == origin/main == 067b3e22401854f8c6d6db42dc0c5c1872fca6f8`. The two hosted secret-scan jobs contained zero steps and failed at the infrastructure boundary; local gates and formal g-check had no severity findings.
- The first exact-merge dependency build stalled after entering offline validation when the owned diagnostic guest stopped accepting Orb/SSH command sessions. No archive reached the host. After read-only process/control-plane diagnosis, only diagnostic guest `01KZKJMR2PG4Z4X7DYHDYTEX0C` was restarted; its disk, owner marker, and prior evidence remained intact. A bounded rebuild then passed guest construction, network-isolated validation, host validation, and cleanup.
- Exact bundle: `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-12-phase-d-fd88b9fb-dependencies.tar.gz`, size `1608905739`, mode 600, SHA-256 `44e9774b43918a4ab373493f8905b9734af929528d8b7029643128ccbaa49c3d`.
- Disposable non-authoritative qualification guest `munbon-control-plan-node-qualification` (`01KZSB67RWZJC11Q9DDRTQWF83`) matched the Debian 12 ARM64 isolated 8 GiB/4 CPU/40 GiB shape. It verified all 963 inner artifacts, performed the real local APT/dpkg installation, matched all 466 exact package specs, returned empty `dpkg --audit`, and passed `apt-get check`.
- The qualification proved the exact defect boundary: ambient Node was absent; the checksum-bound npm launcher exited 127 when restricted to `/usr/bin:/bin`; the merged bundled-first command PATH returned Node `v22.23.1` and npm `10.9.8`. Owner, provisioning state, and acceptance stage state remained absent. Host archive `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-12-node-runtime-qualification-fd88b9fb.tar.gz` is mode 600 with SHA-256 `218fa7c8613a85e5c2e05268a6c3ac0ccf5511fe27d904fb9b494fb5d66d76b7`; inner and outer checks pass. The disposable guest was deleted only after host verification.
- After qualification passed, the exact old failure archive reverified at both checksum layers with outer-index SHA-256 `0d4b6061f6da9f02441843c96ff7ecc2531602408479a9e13574e7ca7ff242f4`. Failed canonical guest `01KZR3P6V5XA1NYDDH9N68TTXD` still mapped uniquely, remained failed at `node_runtime/node-archive`, had no owner, zero acceptance files, and no stage state. Only then was that authorized guest deleted; its failure archive remains preserved.
- Fresh canonical guest `munbon-control-plan-local` (`01KZSBJAXZGWE9EF60KCR2CWMK`) was created once at the prescribed shape. Provisioning passed, including the remediated Node/npm boundary, and reached ready with exact backend/frontend/dependency bindings, empty evidence, Node `v22.23.1`, npm `10.9.8`, and ready central auth. No bootstrap-failure directory was created.
- The single pinned run used `--as-of-date 2026-08-12`, mapping independently to foundation `2026-W33`, WRITE-UI `2026-R41`, and persist-only `2026-R42`. `LOCAL-BASE-0` passed. `LOCAL-RTA-1` then failed at `ros_0001_dataset_version_parent_failed`; the orchestrated sequence stopped immediately, so stages 3-9 did not run and no write week was consumed.
- Read-only diagnosis found the precise PostgreSQL error: extension control file `/usr/share/postgresql/15/extension/postgis.control` is absent. The dependency root requested and installed only `postgis=3.3.2+dfsg-1+b1`; the exact archive contains no `postgresql-15-postgis-3` package. Bootstrap had already logged the same `CREATE EXTENSION postgis` error but its heredoc lacked `ON_ERROR_STOP`, allowing provisioning to report ready. The RTA ROS migration correctly failed and rolled back its transaction; scheduler migrations reached all 13 entries.
- Failure cleanup left PM2 application processes empty, central auth and infrastructure listeners loopback-only, port 9999 absent, and planning-depth writes dark. Guest evidence contains exactly `LOCAL-BASE-0.json`, `LOCAL-RTA-1-failure.json`, `stage-state.json`, and `SHA256SUMS`; every guest checksum passes and stage state lists only `LOCAL-BASE-0`.
- The standard collector streamed and extracted the files but its finalizer rejects any inventory that is not all nine PASS. The preserved partial failure archive is `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-12-nine-stage-orbstack-fd88b9fb.tar.gz`, mode 600, SHA-256 `686e766ca5a5960b4e601430312778c12f2f8715fca328223ab43e766a196868`; guest-inner and host-outer checksum layers pass, and the outer-index SHA-256 is `d4e87bc597814a83e20d8f31ab39bf06d7d5f4b58e1d1b30c236c908b4731324`.
- Stop condition: the authorized pinned canonical run is consumed and truthfully **1/9 PASS**. The fresh canonical guest is preserved without repair, restart, migration replay, or reprovision. Remediating the newly discovered PostGIS closure plus bootstrap SQL fail-open defect, and any later canonical replacement/run, requires a separate TDD/PR/qualification/deletion authorization.

## PostGIS closure and bootstrap fail-closed remediation authorization (2026-08-12)

- The user granted standing campaign authorization until 9/9 passes or three additional canonical attempts are consumed. It covers TDD remediation and ordinary PR/merge/local-main lifecycle for newly discovered provisioning or acceptance-harness defects; disposable non-authoritative qualification guests; and, only after qualification plus failure-archive verification, deletion and replacement of the uniquely mapped campaign-owned canonical guest followed by one pinned run per attempt.
- Stop boundaries remain production/AWS actions, secrets or credential changes, host software updates, mutations outside campaign-owned guests, public-contract or architectural changes, or exhaustion of the three-attempt ceiling. Every failed guest's evidence must be preserved before deletion.
- Attempt accounting begins from preserved canonical guest `munbon-control-plan-local` (`01KZSBJAXZGWE9EF60KCR2CWMK`) and truthful `1/9 PASS`; zero of three additional canonical attempts have been consumed.
- Auggie semantic retrieval was bounded to two seconds and timed out. Targeted fallback inspection covered the dependency roots/resolver, local-repository installer and schema validation, bootstrap PostgreSQL heredocs, ROS migration failure evidence, and existing artifact tests.

## PostGIS closure and bootstrap fail-closed TDD (2026-08-12 05:24:07 +0700)

- Goal: ensure the checksum-bound Debian 12/PostgreSQL 15 dependency closure installs the PostGIS server extension, and ensure PostgreSQL bootstrap SQL errors cannot advance provisioning to ready with stale failure provenance.
- Worktree ledger: `/Users/subhajlimanond/dev/munbon2-backend-postgis-bootstrap-fail-closed`, branch `fix/postgis-bootstrap-fail-closed`, based on refreshed `origin/main@fd88b9fbadc77e3b1230b359bd08c5264a12b6db`; intended disposition is ordinary PR merge followed by verified removal. The dirty primary Coding Log and all pre-existing worktrees remain preserved.
- Read-only Debian Bookworm ARM64 metadata confirmed `postgis` contains userland tools and merely recommends the omitted server extension, while `postgresql-15-postgis-3` provides the PostgreSQL 15 extension and depends on its scripts package. Repository search found no production consumer of the removed standalone PostGIS CLI tools.
- RED contract: `python3 -m pytest -q ops/control-plan-read-local/tests/test_local_artifacts.py -k 'requests_postgresql_15_postgis_extension_package or postgres_setup_fails_closed_on_sql_errors'` failed three assertions for the expected reasons: the APT roots lacked `postgresql-15-postgis-3`, both SQL heredocs lacked `ON_ERROR_STOP`, and neither had a precise SQL failure substep.
- GREEN implementation: `build-dependency-bundle-linux.sh` replaces the misleading generic `postgis` root with the platform-contract package `postgresql-15-postgis-3`. `bootstrap-linux.sh` adds `postgres-role` and `postgis-extension` substeps and invokes both SQL heredocs with `--set=ON_ERROR_STOP=1`; top-level `set -e` and the existing exit trap therefore write failed provisioning state instead of reporting ready.
- GREEN command: the identical focused selection passed `3 passed, 33 deselected`. The affected selection then passed three consecutive identical runs.
- Files changed: `ops/control-plan-read-local/build-dependency-bundle-linux.sh`, `ops/control-plan-read-local/bootstrap-linux.sh`, `ops/control-plan-read-local/tests/test_local_artifacts.py`, and this Coding Log. No migration, orchestrator, dependency schema, stage suite, public interface, architecture, guest, deployment, activation, secret, or AWS state changed.
- Full gates passed: `428` Python operations tests, `41` Node harness/browser tests, Black check, Bash syntax across the four provisioning/dependency shell programs, Python byte compilation, and `git diff --check`. The existing `pytest-asyncio` loop-scope deprecation warning remains unrelated.

Wiring verification:

| Component | Non-test call site | Registration/config load | Schema/contract match |
| --- | --- | --- | --- |
| Offline Debian closure | `build-dependency-bundle-linux.sh` `APT_ROOTS` passed to empty-status `apt-get --download-only` | Diagnostic bundle builder invoked by `orchestrate.py` | Debian 12/PostgreSQL 15 contract now resolves `postgresql-15-postgis-3` and its exact transitive scripts package into checksum-bound specs |
| Canonical bootstrap SQL | `bootstrap-linux.sh` `postgres_redis` phase | Transferred and invoked by canonical provisioning in `orchestrate.py` | PostgreSQL role and PostGIS/schema heredocs use `ON_ERROR_STOP`; SQL failure triggers the existing fail-closed provisioning-state trap with precise substep |
| ROS migration consumer | `services/ros-gis-integration/migrations/0001_dataset_version_parent.up.sql` | Existing RTA migration runner | Existing `CREATE EXTENSION postgis` consumer remains unchanged and now receives the extension from bootstrap |

- Primary QCHECK: no remaining correctness, security, test, integration, or wiring finding. The exact versioned package intentionally binds to the existing Debian 12/PostgreSQL 15 platform contract; any major-platform upgrade remains a separately reviewed contract change.
- Independent Terra QCHECK originally identified two P1 defects matching RED and one observability gap; all are closed by the production changes and locked tests. Its P2 residual is runtime evidence: source/simulation cannot prove the control file, so exact-merge pristine qualification must assert the package spec, control file, successful extension creation, and fail-closed state before canonical deletion.

## Review (2026-08-12 05:25:03 +0700) - staged PostGIS closure and bootstrap fail-closed remediation

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend-postgis-bootstrap-fail-closed`
- Branch: `fix/postgis-bootstrap-fail-closed`
- Scope: staged working tree based on `fd88b9fbadc77e3b1230b359bd08c5264a12b6db`
- Commands Run: bounded Auggie attempt with targeted fallback; staged name/stat and targeted production/test diffs; Debian package metadata probe; focused RED/GREEN selection; three consecutive affected runs; complete Python and Node operations suites; Black; Bash syntax; Python byte compilation; `git diff --check`; independent Terra QCHECK; wiring trace

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
- `postgresql-15-postgis-3` is intentionally bound to the current Debian 12/PostgreSQL 15 platform contract. The exact-merge bundle build must resolve it and its scripts dependency from the same Bookworm ARM64 repository state.

### Recommended Tests / Validation
- After merge, rebuild and validate the checksum-bound dependency archive at the exact merge SHA.
- On one disposable pristine Debian 12 ARM64 qualification guest, prove the exact package spec exists, `/usr/share/postgresql/15/extension/postgis.control` exists, `CREATE EXTENSION postgis` succeeds, and no owner or acceptance state is created.
- Only after qualification and predecessor failure-archive verification, replace the uniquely mapped canonical guest and run all nine stages once at a pinned date under campaign attempt 1 of 3.

### Rollout Notes
- Formal g-check disposition: no remaining CRITICAL/HIGH/MEDIUM/LOW findings. No migration, stage-suite, public-contract, architecture, secret, host-runtime, deployment, activation, or AWS change is included.
- Source validation is not authoritative acceptance; the preserved canonical guest remains unchanged at truthful `1/9 PASS` pending exact-merge qualification.

## PostGIS exact-merge qualification and canonical attempt 1 of 3 (2026-08-12)

- PR #183 merged through the documented infrastructure exception as `84bb52471fc146437c56dac034b6ebaf80410850`; both hosted secret-scan jobs failed in one second with zero steps. Local `main == origin/main`, exact-SHA post-merge gates passed `428` Python and `41` Node tests plus Black, Bash syntax, and Python byte compilation.
- Exact dependency bundle `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-12-phase-d-84bb5247-dependencies.tar.gz` is size `1616147842`, mode 600, SHA-256 `7e38bffd2be38ffbcca96f89f0efd5b0c0456b5b1daef3ab179cd85aeb6abc8c`; diagnostic construction, network-isolated validation, host validation, and cleanup passed.
- Disposable qualification guest `munbon-control-plan-postgis-qualification` (`01KZSFDAG9HRQ9366CDYANRCZ6`) matched the isolated Debian 12 ARM64 8 GiB/4 CPU/40 GiB shape. It verified `968` bundle artifacts and `471` exact package specs, installed `postgresql-15-postgis-3=3.3.2+dfsg-1+b1` plus scripts, found the PostgreSQL 15 control file, created extension version `3.3.2`, proved forced `ON_ERROR_STOP` failure exits nonzero, returned empty `dpkg --audit`, and passed `apt-get check`. No owner/provisioning/acceptance state was created.
- Qualification evidence archive `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-12-postgis-qualification-84bb5247.tar.gz` is mode 600 with SHA-256 `81ccd4a9d9b72e84790286cfe4c242c968cd7abea2b2006324e4ad596cd444f2`; inner and outer checks passed. The disposable guest was deleted only after host verification.
- The predecessor canonical archive reverified at guest-inner and host-outer layers with archive SHA-256 `686e766ca5a5960b4e601430312778c12f2f8715fca328223ab43e766a196868` and outer-index SHA-256 `d4e87bc597814a83e20d8f31ab39bf06d7d5f4b58e1d1b30c236c908b4731324`. Exact failed guest `01KZSBJAXZGWE9EF60KCR2CWMK` was then deleted by its uniquely mapped name; its archive remains preserved.
- Fresh canonical guest `munbon-control-plan-local` (`01KZSFRFVGHBQA90S6ZPRV1X0R`) provisioned ready with exact backend/frontend/dependency bindings, zero evidence files, no bootstrap-failure artifact, exact PostGIS packages, and extension version `3.3.2` in `munbon_local`.
- The pinned `--as-of-date 2026-08-12` run passed `LOCAL-BASE-0` and failed `LOCAL-RTA-1` at `prometheus_config_failed`; stages 3–9 did not run. Attempt 1 of 3 is consumed and remains truthfully `1/9 PASS`.
- Failure evidence archive `/Users/subhajlimanond/dev/munbon2-backend-external-evidence/2026-08-12-nine-stage-orbstack-84bb5247-attempt-1.tar.gz` is size `3240`, mode 600, SHA-256 `526375909c79af34e5e404dc84497bd609b6ed97093761d5ec1ea20a7944bf90`; guest-inner and host-outer checks passed, and outer-index SHA-256 is `5c5878b01f9fed52484a8b09f0a37d195bdb794cdde7e1085b75eb13d49dbd75`.
- Read-only diagnosis proved the secrets block's `umask 077` persists into monitoring setup. All three `/etc/prometheus/control-plane-*-targets.json` files are root-owned mode 600; `promtool check config` succeeds as root but fails as the actual `munbon` stage user with permission denied. PM2 apps were empty after cleanup, port 9999 was absent, infrastructure listeners remained loopback-only, and no write-stage evidence exists. The canonical guest is preserved without repair or replay.
- The PR #183 helper worktree was clean, its commit reachable from `origin/main`, and its Coding Log byte-identical to the retained main copy; it was removed and worktree metadata pruned. All baseline worktrees, older stashes, and two untracked primary pointer backups remain untouched.

## Prometheus file_sd mode remediation authorization and context (2026-08-12)

- Standing campaign authorization continues with attempt accounting at 1 of 3 consumed. This TDD/PR/qualification/canonical-replacement lifecycle is within scope; production/AWS, secrets changes, host updates, external resources, public contracts, and architecture remain excluded.
- Worktree ledger: `/Users/subhajlimanond/dev/munbon2-backend-prometheus-file-sd-modes`, branch `fix/prometheus-file-sd-modes`, based on refreshed `origin/main@84bb52471fc146437c56dac034b6ebaf80410850`; intended disposition is merge then verified removal.
- Auggie semantic retrieval timed out at the two-second bound. Targeted fallback inspected secret creation and permissions, monitoring file generation, actual stage execution user, `_monitoring_preflight`, failure publication, artifact tests, guest modes, and the exact non-root `promtool` error.

## Prometheus file_sd mode remediation TDD and gates (2026-08-12)

- Root cause: `bootstrap-linux.sh` intentionally enters `umask 077` while creating credentials and never relaxes it. That correctly protects the secrets file and runtime environment, but the later non-secret Prometheus file-SD JSON targets inherited mode 600 and were unreadable by the `munbon` acceptance-stage user.
- RED contract: `test_bootstrap_keeps_secrets_private_and_prometheus_targets_readable` requires the existing secrets and runtime-environment `chmod 600` contracts, requires one exact `chmod 0644` block containing only the central, field, and readiness target JSON paths, and requires that block to occur after all three files are written. It failed because no readable target mode existed.
- GREEN implementation: after writing the three non-secret file-SD targets, bootstrap explicitly sets only those exact paths to mode 0644. It does not restore the global umask or broaden any credential permissions, so secrets remain mode 600 throughout creation and use.
- The focused regression passed after formatting and then passed three consecutive identical repeat runs. The complete operations suites passed `429` Python tests and `41` Node harness/browser tests; changed-file Black, Python byte compilation, Bash syntax, and `git diff --check` passed.
- A broader Black check also reported the unchanged pre-existing `seed-approved-sources.py` would be reformatted. This remediation does not alter that unrelated file; the changed Python test passes Black exactly.
- Files changed: `ops/control-plan-read-local/bootstrap-linux.sh`, `ops/control-plan-read-local/tests/test_local_artifacts.py`, and this Coding Log. No public contract, architecture, credential value, secret mode, orchestrator, stage logic, guest, production/AWS resource, or host software changed.

Wiring verification:

| Component | Non-test call site | Registration/config load | Schema/contract match |
| --- | --- | --- | --- |
| Prometheus file-SD targets | `bootstrap-linux.sh` monitoring phase writes the three JSON files | Existing `infra/monitoring/control-plane-prometheus.yml` file-SD jobs load those exact paths; the acceptance preflight runs `promtool` as `munbon` | Only non-secret target descriptors become world-readable; secret/runtime files remain owner-readable mode 600 |
| Canonical provisioning | `orchestrate.py` transfers and invokes `bootstrap-linux.sh` | Existing ready-state provisioning contract | The change occurs before ownership completion and preserves fail-closed bootstrap behavior |
| Runtime acceptance | Existing LOCAL-RTA-1 monitoring preflight | Existing stage runner defaults to the `munbon` guest user | Non-root `promtool check config` can read the configured target files without gaining access to credentials |

- Primary QCHECK: no remaining correctness, security, test-strength, integration, or wiring finding. Runtime qualification must still prove exact-merge target modes, retained secret mode 600, and successful non-root `promtool` before deleting the preserved canonical failure guest.
- Independent Terra QCHECK: no P0/P1 source finding and GO for source delivery. Its P2 observation is that the repository test is structural rather than a live privilege/mode test; disposition is an explicit required qualification predicate, not an additional source change: prove all three targets are `root:root` mode 0644, runtime env files remain mode 0600, and `runuser -u munbon -- promtool check config ...` exits zero on a disposable exact-merge guest.

## Review (2026-08-12) - staged Prometheus file-SD target mode remediation

### Reviewed
- Repo: `/Users/subhajlimanond/dev/munbon2-backend-prometheus-file-sd-modes`
- Branch: `fix/prometheus-file-sd-modes`
- Scope: staged working tree based on `84bb52471fc146437c56dac034b6ebaf80410850`
- Commands Run: bounded Auggie attempt with targeted fallback; exact guest failure inspection; focused RED/GREEN and three repeats; complete Python and Node operations suites; changed-file Black; Bash syntax; Python byte compilation; `git diff --check`; staged name/stat and targeted diff review; primary and independent QCHECK; wiring trace

### Findings
CRITICAL
- No findings.

HIGH
- No findings.

MEDIUM
- No source finding. Runtime qualification remains required because the source regression is structural: exact-merge evidence must prove the three target modes, retained secret modes, and non-root `promtool` success before canonical deletion.

LOW
- No findings.

### Open Questions / Assumptions
- The three Prometheus file-SD target descriptors are non-secret static loopback endpoints. This is consistent with the checked-in monitoring configuration and the failed guest contents.
- The unchanged pre-existing `seed-approved-sources.py` Black drift is outside this remediation; all changed Python passes Black.

### Recommended Tests / Validation
- Build the dependency archive from the exact merge SHA and validate its checksum and restrictive host mode.
- On one disposable pristine guest, prove the exact three files are `root:root` 0644, runtime env files remain 0600, and `promtool check config` succeeds as `munbon`, without creating owner/provisioning/acceptance state.
- Verify the preserved attempt-1 archive at guest-inner and host-outer layers before replacing only the uniquely mapped campaign canonical guest for attempt 2 of 3.

### Rollout Notes
- Formal g-check disposition: no remaining CRITICAL/HIGH/MEDIUM/LOW source finding. The independent P2 validation boundary is accepted as a mandatory runtime qualification gate and must not be represented as authoritative acceptance.
- No public contract, architecture, secret value/mode, stage logic, deployment, production/AWS resource, or host software change is included.
