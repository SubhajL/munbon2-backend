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
