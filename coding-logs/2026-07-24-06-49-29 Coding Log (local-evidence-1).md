# LOCAL-EVIDENCE-1 Coding Log

Created: 2026-07-24 06:49:29 +07
Authoritative backend baseline: `origin/main` at
`12f46c28dd228456abb72e1b4f6efb2785dcbfa2`
Accepted frontend: `origin/main` at
`fbd4ce4df0bb0476b7cd402ac1a4e180a91a7792`

## Scope contract

Implement, pass, and land `LOCAL-EVIDENCE-1` from the synchronized execution
plan:

- backend/frontend ME-1 byte parity;
- three real bearer-forwarded evidence projections;
- present, absent, unavailable, held, and malformed states;
- exact `/read-only/gates/{id}` link;
- no-command source and browser-request inventory;
- zero product mutation, authority, hold/resume, level, or horn requests;
- final evidence and control-plan feature flags restored `false`.

The run remains isolated to the existing disposable OrbStack guest and takes no
AWS action. Product execution and machine-command gates remain dark.

## Workflow notes

- FE-8 and GO-READ-1 were independently landed before this slice.
- Auggie semantic search is skipped because the available interface cannot
  enforce the required two-second deadline. Direct source inspection is used.

## TDD log

### RED

Command:

`python3 -m pytest -q ops/control-plan-read-local/tests/test_stage_suite.py ops/control-plan-read-local/tests/test_orchestrate.py ops/control-plan-read-local/tests/test_local_artifacts.py`

Expected failures locked the missing fifth stage, evidence-only activation
sequence, environment invariants, byte-parity verifier, append-only evidence
preparation, exact browser proof schema, read-only Gate Operations inventory,
new browser artifact, runbook command, and checksum count. One pre-existing
W2-era test also exposed a stale BFF-009 expectation against the already-merged
BFF-010 runtime contract.

### GREEN

Implemented the fifth progressive stage and corrected the stale migration test.
The focused harness command passes `78` tests; the complete Python harness suite
passes `86` tests and the complete Node harness suite passes `4` tests.

Additional static gates pass:

- Python compilation for the orchestrator and stage runner.
- Bash syntax validation for the guest bootstrap.
- Node syntax validation for the evidence browser.
- Live local source checks prove `17` exact ME-1 files with aggregate SHA-256
  `67bacfee2c975302cf478c1caf2ee9f5991552fcbe0d5a771c09ec96f8192742`.
- Live GO-READ-1 source inventory reports zero command-capable imports and zero
  mutation methods.

## Independent QCHECK

The independent review identified three gaps. All are remediated:

1. The browser request inventory now uses an exact same-origin API allowlist.
   Auth POSTs and the seven expected GET-only plan/version paths are the only
   allowed API requests. Authority, Gate Operations command-level, non-GET
   plan, and unknown API requests are negative-tested and blocked.
2. The real empty intent timeline must visibly state both
   `No command intents are recorded.` and
   `Empty intent history does not claim execution.` The stage result records
   `empty-not-execution`, and the direct projection validator requires zero
   intents for this evidence case.
3. GO-READ-1 source verification now permits only the reviewed static import
   dependencies, requires the `/api/gates/{id}/status` seam, scans both route
   and client for mutation methods, and rejects unknown helper imports.

Post-remediation full gates pass: `86` Python tests, `4` Node tests, Ruff,
Black, Python compilation, Bash syntax, Node syntax, and `git diff --check`.

## Formal g-check

The primary review found two cleanup/dependency risks and remediated both:

- A failed resume append could previously short-circuit the emergency dark
  frontend rebuild. Cleanup now attempts both the resume and the false/false
  rebuild before reporting failure; a focused failure-path test locks that
  ordering.
- The GO-READ-1 dependency allowlist now rejects runtime imports from its
  type-only `./api` dependency as well as unknown, dynamic, and CommonJS
  imports.

Final disposition: no remaining severity findings. The complete post-review
gate is `86` Python tests, `4` Node tests, Ruff, Black, Python compilation,
Bash syntax, Node syntax, and `git diff --check`.

## Exact-SHA runtime attempt 1

Backend `0c71e98edcd77a974102f7c2ebc975eecc193330` and frontend
`fbd4ce4df0bb0476b7cd402ac1a4e180a91a7792` were provisioned cleanly.
`LOCAL-BASE-0`, `LOCAL-RTA-1`, `LOCAL-AC-1`, and `LOCAL-READ-ACT-1` passed.
`LOCAL-EVIDENCE-1` stopped at `evidence_browser_visible_failed`; the healthy
frontend log ruled out a server-start failure.

The browser had logged in without the scoped `redirectAfterLogin` used by the
predecessor read-activation runner. The login page therefore entered the Smart
Water dashboard before the plan-detail navigation, and the dashboard's
unrelated API inventory correctly violated the exact evidence allowlist. The
browser now redirects directly to the accepted plan detail. The stage runner
also propagates only a single validated lowercase browser failure code, keeping
future failure manifests diagnostic without exposing raw stderr.

The fix passes `92` Python tests and `5` Node tests plus Ruff, Black, Python
compilation, Bash syntax, Node syntax, and `git diff --check`. Primary review
also corrected the safe-error prefix to the evidence browser caller and added a
source-level regression test that prevents it from being attached to the
predecessor read browser.

Independent QCHECK reported two low-severity test gaps and no high/medium
findings. Both are closed: `_run_checked` now has nonzero-process tests for
accepted, duplicate, invalid, and secret-bearing stderr, while a Node behavior
test proves the exact plan-detail redirect is stored before credential
submission and rejects a dashboard redirect.

Post-remediation formal g-check disposition: no remaining severity findings.

## Exact-SHA runtime attempt 2

Backend `ab91271f7f780c7911eb336d27909d957f170ace` and the accepted frontend were
reprovisioned from clean disposable state. The first four stages passed again.
`LOCAL-EVIDENCE-1` returned the newly surfaced exact code
`forbidden_product_request_observed`.

The scoped redirect alone did not eliminate a login-page race: both the submit
handler and authentication effect can consume and remove the same redirect
value, allowing the other path to fall back to the Smart Water dashboard during
the harness's post-login 500 ms pause. The harness now proceeds immediately to
the accepted detail route after the 200 response; the refresh cookie preserves
authentication across that navigation. Future inventory stops distinguish an
unexpected allowlist API from an explicitly forbidden control-path request.
The request inventory is explicitly scoped from the post-authentication
plan-detail navigation onward; login uses `noWaitAfter` so the harness can move
to that detail as soon as the 200 response is observed.

Independent QCHECK identified a medium cookie race in that transition: the
login page's mount-time anonymous refresh can return a clearing cookie after
the login response. The harness now registers and requires that bootstrap
refresh's expected 401 before submitting credentials, so its `Set-Cookie`
cleanup is settled before the login issues the valid refresh cookie.

Post-remediation gates remain `92` Python and `5` Node tests with all static
checks green. Primary formal g-check finds no remaining severity findings.

## Exact-SHA runtime attempt 3 — PASS

Backend `8ce28a8a0bfd5a3127a213abdde8d6939cacb123` and frontend
`fbd4ce4df0bb0476b7cd402ac1a4e180a91a7792` were provisioned from clean
disposable state. All five stages passed in order:

- `LOCAL-BASE-0`
- `LOCAL-RTA-1`
- `LOCAL-AC-1`
- `LOCAL-READ-ACT-1`
- `LOCAL-EVIDENCE-1`

The checksum-verified sanitized archive is
`coding-logs/evidence/2026-07-24-local-evidence-main-8ce28a8a/`.
The evidence manifest records 17 exact ME-1 contract files, all three real
bearer projections at 200/no-store, three missing-plan 404s, held and
unavailable durable evidence, visible present/absent/unavailable/held/malformed
cases, zero Gate Operations navigation, zero forbidden or mutation requests,
and a final resumed state. Both frontend flags are false afterward;
`CONTROL_EXECUTION_MODE` remains `disabled`, Scheduler SCADA is unconfigured,
machine commands are unconfigured, and model authority remains non-commandable.
No AWS action occurred.

Archive formal g-check: checksums and redaction scans pass; no severity
findings remain.

## Design boundary

The three present projections and held/unavailable evidence come from real
append-only rows in the disposable local PostgreSQL database and are read
through the authenticated BFF-to-Scheduler path. Missing-plan evidence also
uses the real path. Only the intentionally malformed response is scoped browser
interception, proving frontend decoder isolation without pretending the
producer emitted malformed data. The Gate Operations href is inspected exactly
but never navigated, so its request inventory remains zero.

## GO-READ-1 runtime-boundary prerequisite

Dedicated runtime acceptance exposed three fail-closed gaps before the browser
stage could be credible: the read-only page called SCADA cross-origin even
though SCADA has no CORS surface, a structurally valid response for the wrong
gate was accepted, and a prior successful status remained visible after a
polling failure. The temporary SCADA process also needed an explicit
loopback-only bind.

Tests were added first and failed for each missing behavior. The implementation
now uses a same-origin, server-only, GET-only status proxy; forwards only the
Bearer token to the exact encoded upstream status path; forces `no-store` on
both proxy and SCADA responses; rejects response identities that differ from
the requested gate; removes prior status as soon as a poll fails; and supports
`HTTP_HOST=127.0.0.1` without changing the production default. The proxy exports
no mutation handler and uses the server-only `SCADA_GATE_CONTROL_URL`.

Auggie semantic search was skipped because the available tool exposes no
timeout control and the lifecycle requires a two-second cap. Direct,
scope-bounded source inspection covered the existing proxy, route, config,
startup, and test patterns instead.

Full validation passed three consecutive times: web `187` tests; SCADA `423`
tests with the seven existing Postgres-gated tests skipped. Web and SCADA type
checks, lint, production builds, targeted Prettier checks, staged diff checks,
and exact wiring searches also passed.

## Review (2026-07-24 08:51:20 +07) - GO-READ runtime boundary

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-go-read-runtime-fix`
- Branch: `fix/go-read-runtime-boundary`
- Scope: staged working tree based on `f328c4f6331d6f1e8d859fc052ea4b51892b688d`
- Commands Run: staged name/stat/targeted diffs; `git diff --staged --check`; focused Vitest RED/GREEN; full service tests three times; service type checks, lint, builds, targeted Prettier checks; exact route/config/wiring searches

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

- This prerequisite intentionally does not claim browser acceptance. The
  dedicated isolated stage must still prove real login, direct navigation,
  repeated status polling, outage behavior, zero mutation requests, and hard
  cleanup.
- `HTTP_HOST` retains `0.0.0.0` as the backward-compatible default. The
  acceptance harness must explicitly set `127.0.0.1`.

### Recommended Tests / Validation

- Run the dedicated GO-READ browser stage against the exact merged main SHA
  with real Auth, SCADA, and Gate Web processes and no intercepted status
  responses.
- Exercise signed-out, successful offline snapshot, unknown-gate, and
  post-success SCADA-outage states while inventorying every request.

### Rollout Notes

- No execution flag, authority setting, machine-command permission, AWS
  resource, or persistent runtime configuration changes.
- The new proxy is read-only and server-side. Existing command-capable pages
  retain their prior public API-base behavior and are outside this prerequisite
  scope.

## Independent QCHECK (2026-07-24 08:54:24 +07)

Terra reported no critical or high defects. It identified two medium residuals:
the dedicated browser/process acceptance remained to be built, and a malformed
server-only SCADA URL failed closed at first request rather than producing a
deploy-time diagnostic. It also identified low test gaps for upstream status
propagation and real loopback binding.

The proxy suite now explicitly proves fixed `503`/`no-store` behavior with zero
upstream requests for a credential-bearing/path-bearing malformed URL, and
proves exact `401` and `404` upstream status/body propagation. Focused web tests
are `20/20`, with typecheck and lint green. The runtime-only findings are the
scope of the next dedicated stage: it must validate the configured URL before
launch, prove actual `127.0.0.1` sockets, exercise real navigation and outage
behavior, inventory requests, and verify cleanup. No product-code severity
finding remains open in this prerequisite.

## GO-READ-1 dedicated local acceptance implementation

The sixth local stage is implemented on exact prerequisite main
`c4b266f59fca549b09837a85dc30a4da746e224d`. Tests were written first for stage
ordering and state binding, harness provisioning, runtime-environment
sanitization, exact loopback listeners, direct status semantics, browser result
shape, request classification, login ordering, outage coordination, checksum
indexing, and failure-path restoration. The initial RED run produced ten Python
failures and a missing Node module; later review-specific RED runs reproduced
blank authority-environment acceptance, incomplete offline observation checks,
permissive request queries and mutations, absent restoration wiring, and
unrecorded external requests.

`LOCAL-GO-READ-1` now builds and gates SCADA and Gate Web, starts both as
temporary production processes on `127.0.0.1`, proves the actual process
environment and sockets, holds readiness for 300 seconds, exercises real
operator-authenticated known and unknown direct SCADA reads, and launches real
Chromium through the same-origin read-only proxy. The browser requires three
successful status responses, zero action controls, a 404 unknown-gate state,
and a 503/no-store stale-data-clearing state after the runner terminates SCADA.
Only explicit auth posts, three documents, Next static assets, framework RSC
reads, and two exact query-free status GETs are allowed; every other attempted
request is recorded and rejected.

SCADA authority, approved-bundle, registry, lineage-anchor, and service-auth
configuration is removed from the inherited environment rather than assigned
blank values. Cleanup and restoration verification runs on success and on
readiness/browser/outage failure. Failure manifests preserve the primary gate
code and include a sanitized restoration result. Final state requires no
temporary listeners, unchanged PM2 identity, ready central Auth, unchanged dark
contract, both Smart CMS flags false, and no AWS action.

Independent QCHECK found four material gaps in the first implementation:
blank artifact environment variables that prevented SCADA startup, an ignored
behavioral Node test, a non-exact browser allowlist, and absent failure-path
restoration proof. Follow-up review found that blocked external traffic was not
inventoried. All findings were reproduced, remediated, and regression-tested.
The force-added Node test is present in the staged index. Final independent
QCHECK verdict: no remaining actionable findings.

Final validation passed three consecutive times: `100` Python tests, `5` Node
tests, Ruff, Black, Python compilation, Bash syntax, Node syntax, and staged
diff validation. This implementation does not yet claim runtime acceptance;
that requires the exact merged-main six-stage run and checksum-verified browser
evidence.

## Review (2026-07-24 09:45:51 +07) - GO-READ-1 acceptance harness

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-go-read-1-acceptance`
- Branch: `feature/go-read-1-local-acceptance`
- Scope: staged acceptance harness and runbook based on
  `c4b266f59fca549b09837a85dc30a4da746e224d`
- Commands Run: staged name/stat/targeted diffs; focused RED/GREEN Pytest and
  Node tests; full harness suites three times; Ruff; Black; Python compilation;
  Bash and Node syntax; staged diff checks; independent Terra QCHECK

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

- This review covers implementation correctness, not an unexecuted acceptance
  claim. Exact-main runtime evidence remains mandatory after merge.
- Framework `_rsc` requests are accepted only for the two allowlisted gate
  documents and only as a single non-empty query parameter.

### Recommended Tests / Validation

- Merge the harness, provision the exact merged backend SHA and accepted
  frontend SHA into the isolated OrbStack guest, and run all six stages in
  order from disposable state.
- Inspect both screenshots, verify every checksum, scan the collected archive
  for credential-shaped material, and rerun final dark/listener/source checks.

### Rollout Notes

- No production deploy, AWS access, execution enablement, machine-command
  permission, or authority configuration is part of this slice.
- Runtime processes are temporary and loopback-only. The accepted PM2 process
  set is neither changed nor saved by this stage.

## Exact-main runtime attempt 1 and evidence-source unblock

Backend `383406d2ca1657ae3463041381c1ac851b0fb6b8` and the accepted frontend were
provisioned from disposable state. `LOCAL-BASE-0`, `LOCAL-RTA-1`,
`LOCAL-AC-1`, and `LOCAL-READ-ACT-1` passed. `LOCAL-EVIDENCE-1` stopped at
`read_only_gate_source_invalid`, so `LOCAL-GO-READ-1` did not start.

The source guard still required the legacy direct `/api/gates/` browser path,
while the accepted runtime prerequisite correctly moved the client to the
same-origin `/api/read-only/gates/` proxy. A focused test reproduced the
failure. The guard now requires the same-origin path and explicitly rejects any
legacy direct path, including a source that contains both paths as a fallback.

Final validation passed three consecutive times: `100` Python tests, Ruff,
Black, Python compilation, and diff checks. Independent QCHECK's both-path
fallback finding was reproduced and closed; final verdict is clean.

## Review (2026-07-24 10:00:36 +07) - evidence source boundary

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-go-read-evidence-fix`
- Branch: `fix/go-read-evidence-source-boundary`
- Scope: two-file staged fix based on
  `383406d2ca1657ae3463041381c1ac851b0fb6b8`
- Commands Run: exact failure manifest inspection; focused RED/GREEN test;
  actual-source invocation; full harness tests three times; Ruff; Black; Python
  compilation; diff checks; independent Terra QCHECK

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

- The failed attempt is not reusable because acceptance evidence is
  release-SHA-bound. All six stages must run again after this fix merges.

### Recommended Tests / Validation

- Reprovision the exact new merged-main SHA and rerun the complete six-stage
  sequence from disposable state.

### Rollout Notes

- This changes only a fail-closed source verifier and its tests. Runtime
  services, flags, authority, commands, and AWS remain untouched.

## Exact-main runtime attempt 2 and refused-Modbus cleanup

Backend `a31bdd4a4d87c440f0bb2cf14bf640f3c886981a` and the accepted frontend were
reprovisioned from disposable state. The first five stages passed.
`LOCAL-GO-READ-1` completed its build and stability work but stopped at
`go_read_status_result_not_accepted`. Its failure manifest proved complete
restoration: no temporary listener, unchanged PM2 identity, ready Auth, both
frontend flags false, and the full dark contract unchanged.

A guest-local diagnostic reproduced the exact API response without exposing
credentials: the gate was correctly offline/red with null observations, but
the aggregate and point `lastError` values remained null after minutes. The
real `modbus-serial` TCP client emits its close event when connection is
refused; the transport then called `close()` and awaited a callback registered
after that event, leaving the controller's first poll unresolved.

A real refused-TCP test was added first and failed at its two-second cleanup
deadline. `ModbusClientLike` now exposes the library's abortive `destroy()`
operation, and failed connect/read/write cleanup uses it before the next retry.
The regression now rejects in about 70 ms and the existing lifecycle tests
prove failed clients are destroyed and replaced.

Final validation passed three consecutive times: `424` SCADA tests with the
seven existing Postgres-gated skips, `100` harness tests, SCADA typecheck, lint,
production build, Prettier, and diff checks. Independent QCHECK found no
actionable issue.

## Review (2026-07-24 10:22:24 +07) - Modbus refused-connect cleanup

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-go-read-modbus-fix`
- Branch: `fix/go-read-modbus-connect-cleanup`
- Scope: SCADA transport and colocated test based on
  `a31bdd4a4d87c440f0bb2cf14bf640f3c886981a`
- Commands Run: sanitized failure-manifest inspection; guest-local direct API
  diagnostic; focused RED/GREEN Vitest; full SCADA and harness suites three
  times; typecheck; lint; build; Prettier; diff checks; independent Terra
  QCHECK

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

- Exact-main acceptance must restart from provisioning after this product fix;
  the failed predecessor-SHA evidence is not reusable.

### Recommended Tests / Validation

- Rerun all six stages and require the real offline response to contain the
  refused-connection error before starting Chromium.
- Confirm the browser's live, unknown-gate, and post-SCADA-stop outage states,
  then verify restoration and archive checksums.

### Rollout Notes

- This changes only failed-socket cleanup. It does not enable command routes,
  service auth, approved authority, machine commands, or AWS access.

## Exact-main runtime attempt 3 and browser alert scope

Backend `fcd55fa40afbe5ba9c3ac29bd0e9d9f5e63ed178` and the accepted frontend were
reprovisioned from disposable state. The first five stages passed.
`LOCAL-GO-READ-1` cleared the fixed direct-status validation and stopped at
`go_read_browser_unknown_gate_failed`. The failure manifest again proved full
restoration and an unchanged dark contract.

A request-level Playwright diagnostic proved that the unknown gate returned
`404/no-store`, the intended unavailable alert was visible, and no data list
remained. Next.js also injects an empty route-announcer with `role="alert"`, so
the page-wide Playwright locator had two matches and failed strictness.
Unknown-gate and outage waits now target `main [role="alert"]`, excluding the
framework announcer while retaining the product-state assertion.

Final validation passed three consecutive times: `100` Python tests, `5` Node
behavior tests, Ruff, Black, Node syntax, and diff checks. Independent QCHECK
found no actionable issue.

## Review (2026-07-24 10:43:54 +07) - GO-READ browser alert scope

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-go-read-alert-fix`
- Branch: `fix/go-read-browser-alert-scope`
- Scope: browser runner and source regression based on
  `fcd55fa40afbe5ba9c3ac29bd0e9d9f5e63ed178`
- Commands Run: failure-manifest and screenshot inspection; request-level
  Playwright diagnostic; focused RED/GREEN Pytest; full Python and Node suites
  three times; Ruff; Black; Node syntax; diff checks; independent Terra QCHECK

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

- Acceptance evidence remains unclaimed. The exact merged-main SHA must be
  provisioned and all six stages rerun.

### Recommended Tests / Validation

- Require both the unknown-gate and post-SCADA-stop main alerts, verify no data
  list remains, and inspect both screenshots after a complete PASS.

### Rollout Notes

- This is a locator-scope correction only. Runtime configuration, flags,
  authority, machine commands, and AWS remain unchanged.

## Exact-main runtime attempt 4 and root RSC prefetch

Backend `77d7f17aa6e5331e0acc16d919cb629e67fce32a` and the accepted frontend were
reprovisioned from disposable state. The first five stages passed.
`LOCAL-GO-READ-1` produced both live and outage screenshots and stopped at the
explicit `forbidden_product_request_observed` inventory gate. Restoration was
fully verified and the dark contract remained unchanged.

The prior request trace identified the single natural unallowlisted request:
Next.js prefetches the `GateDetailHeader` back link as `GET /?_rsc=<value>`.
The allowlist now admits only same-origin `GET /` with exactly one nonempty
`_rsc` parameter. Bare root, extra query parameters, non-GET methods, external
origins, and direct SCADA remain rejected and inventoried.

Final validation passed three consecutive times: `100` Python tests, `5` Node
behavior tests, Ruff, Node syntax, and diff checks. Independent QCHECK found no
actionable issue.

## Review (2026-07-24 11:03:39 +07) - GO-READ root RSC prefetch

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-go-read-rsc-fix`
- Branch: `fix/go-read-root-rsc-prefetch`
- Scope: exact browser request classifier and Node behavior test based on
  `77d7f17aa6e5331e0acc16d919cb629e67fce32a`
- Commands Run: exact failure-manifest inspection; request-trace disposition;
  focused RED/GREEN Node test; full Python and Node suites three times; Ruff;
  Node syntax; diff checks; independent Terra QCHECK

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

- The next exact-main run must still prove the inventory is empty and complete
  all six stages before evidence is accepted.

### Recommended Tests / Validation

- Rerun all six stages from clean provisioning and require zero unallowlisted,
  mutation, forbidden-control, and direct-SCADA browser requests.

### Rollout Notes

- The exception is limited to Next's read-only framework prefetch. It adds no
  API, write method, authority, command permission, or AWS action.

## Exact-main runtime attempt 5 and signed-out login RSC boundary

Backend `b46b1f4da5803ee9ce6ade12c93f48afa347d107` and the accepted frontend were
reprovisioned from disposable state. The first five stages passed.
`LOCAL-GO-READ-1` produced both screenshots and stopped at
`forbidden_product_request_observed`. Failure restoration was fully verified:
the temporary listeners were gone, PM2 identity and auth readiness were
unchanged, all frontend activation flags were false, execution and machine
commands remained disabled, and service authority remained dark.

A full authenticated request trace proved that the live, unknown-gate,
restored-live, and outage browser phases contained only allowed requests. A
separate signed-out trace then identified the sole remaining request: Next.js
uses `GET /login?next=<allowlisted-gate-path>&_rsc=<nonempty>` while redirecting
the protected read-only gate detail to login.

The request classifier now admits only same-origin `GET` for that exact
two-parameter login RSC shape. The `next` value must already be one of the
explicit read-only document paths and `_rsc` must be nonempty. HEAD, empty RSC,
unknown destinations, and extra query parameters remain rejected.

Validation passed three consecutive times: `100` Python tests, `10` Node tests
including all `5` scoped browser-inventory tests, Ruff, Node syntax, and diff
checks. Independent Terra QCHECK found no actionable issue.

## Review (2026-07-24 11:30:38 +07) - GO-READ signed-out login RSC boundary

### Reviewed

- Repo:
  `/Users/subhajlimanond/dev/munbon2-backend-go-read-signedout-fix`
- Branch: `fix/go-read-signed-out-rsc-boundary`
- Scope: exact signed-out login RSC request-classifier allowance and regression
  tests based on `b46b1f4da5803ee9ce6ade12c93f48afa347d107`
- Commands Run: exact failure-manifest inspection; authenticated and signed-out
  request traces; focused RED/GREEN Node test; full Python and Node suites three
  times; Ruff; Node syntax; diff checks; independent Terra QCHECK

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

- Acceptance evidence remains unclaimed until the exact merged-main SHA is
  provisioned and all six stages complete.

### Recommended Tests / Validation

- Rerun the complete six-stage acceptance from clean provisioning and require
  an empty forbidden, unallowlisted, mutation, and direct-SCADA browser
  inventory.

### Rollout Notes

- The exception is limited to Next's signed-out read-only navigation. It adds
  no API, write method, authority, machine-command permission, or AWS action.

## GO-READ-1 exact-main acceptance and recovery (2026-07-26 09:42:44 +07)

### Goal

Complete the dedicated GO-READ runtime/browser acceptance on the exact merged
backend and accepted frontend, preserve fail-closed runtime defaults, collect
checksum-bound evidence, and archive the result separately from product code.

### Recovery and changes

- A transport interruption cut off the first clean attempt during the
  `LOCAL-EVIDENCE-1` rollback build. Its failure manifest recorded
  `frontend_dark_rollback_failed`; an exact dark rebuild then passed.
- Retrying only the interrupted stage correctly failed
  `evidence_browser_present_held_failed` because the first attempt had already
  appended held/resumed evidence to the disposable database.
- The guest was therefore reprovisioned from clean source bundles and a reset
  database. The full six-stage run was moved into a detached session so chat
  transport loss could not signal the acceptance processes.
- `docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md` now records the
  exact six-stage PASS, runtime/browser boundary, final dark gates, archive
  location, and aggregate checksum.
- `coding-logs/evidence/2026-07-26-go-read-main-d47db8e3/` contains the six
  stage manifests, stage state, live and outage screenshots, and
  `SHA256SUMS`.

### TDD and runtime evidence

- No product or harness code changed in this archival unit, so no new
  test-first RED/GREEN cycle applies. The signed-out RSC production fix was
  already developed RED/GREEN and landed in PR #136.
- Runtime RED:
  `python3 ops/control-plan-read-local/orchestrate.py run-stage --stage
  LOCAL-EVIDENCE-1 ...` failed after the interrupted partial run with
  `evidence_browser_present_held_failed`, proving partial-stage evidence is not
  reusable.
- Runtime GREEN:
  `python3 ops/control-plan-read-local/orchestrate.py run-all --release-sha
  d47db8e3e61219ac6ff791a7b2e6642c5ae2cf70 --frontend-sha
  fbd4ce4df0bb0476b7cd402ac1a4e180a91a7792
  --accept-later-origin-main` passed all six stages after clean provisioning.
- `LOCAL-GO-READ-1` ran SCADA and Gate Web tests, typechecks, lints, and
  production builds; both temporary services held loopback readiness for 300
  seconds over 61 samples.
- Chromium proved signed-out redirect, login 200, four authenticated live
  responses, known-gate 200/no-store, unknown-gate 404/no-store, post-SCADA
  outage 503/no-store, the outage alert, and stale observation removal.
- Browser inventory recorded zero direct-SCADA requests, zero forbidden
  product requests, zero product mutations, and zero action controls.
- `shasum -a 256 -c SHA256SUMS` passed for every collected manifest and
  screenshot. The SHA-256 of the checksum index is
  `ab1a19dd4fdc45954569448fdca4db2ede5b208457a2f2cf7c09414a37cde16c`.

### Wiring verification

- `orchestrate.py run-all` invoked `LOCAL-GO-READ-1` only after the five
  predecessor manifests passed.
- `run-stage-suite.py` started the exact built SCADA and Gate Web entry points,
  then invoked the tracked `run-go-read-browser.js`.
- Stage state binds the completed sequence to backend
  `d47db8e3e61219ac6ff791a7b2e6642c5ae2cf70`, frontend
  `fbd4ce4df0bb0476b7cd402ac1a4e180a91a7792`, and every installed harness
  hash.

### Safety and residual scope

- Cleanup removed ports 3030, 9998, 9999, and 65534; PM2 identity was
  unchanged and central auth remained ready.
- Final control-plan reads, evidence reads, Water Planning V2, and submit flags
  are false. Scheduler execution is disabled, model release is not
  commandable, machine commands are not configured, and service auth remains
  dark.
- No AWS action occurred.
- This acceptance authorizes the local read-only result only. It does not
  authorize write UI, command authority, machine execution, or AWS promotion.
- Auggie was skipped because the available interface could not enforce the
  required two-second timeout; the recovery used exact manifests, source
  inspection, and runtime evidence.

## Review (2026-07-26 09:44:35 +07) - GO-READ-1 final evidence archive

### Reviewed

- Repo: `/Users/subhajlimanond/dev/munbon2-backend-go-read-archive`
- Branch: `ops/archive-go-read-1-20260726`
- Scope: staged evidence archive, exact-main runbook result, and acceptance-log
  summary based on `d47db8e3e61219ac6ff791a7b2e6642c5ae2cf70`
- Commands Run: staged status/stat/check; collected and guest checksum
  verification; JSON identity and stage-order audit; targeted RTA, Evidence,
  GO-READ browser, cleanup, activation-gate, and dark-contract inspection;
  original-resolution inspection of both screenshots; listener audit

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

- GitHub Actions may again be unable to start because of the existing account
  billing lock. Any such zero-step result must be distinguished from local
  acceptance and documented before merge.

### Recommended Tests / Validation

- Require the archival PR to contain exactly the ten collected files plus the
  runbook and coding-log changes.
- Reverify all checksum entries after commit and confirm the PR merge commit is
  landed on both `origin/main` and local `main`.

### Rollout Notes

- The evidence is local-only and SHA-bound. All read/write/authority gates
  remain dark, machine execution remains disabled, and no AWS action is
  authorized or performed.

## Implementation (2026-07-27 11:23:35 +07) - V5 hybrid section-area authority

### Scope and authority

- Branch: `feature/v5-section-area-overlay`
- Base: `3becd0a080393ddb75895a61de3c3269e5e121c7`
- Pinned source: `SCADA Section Detailed Information 2026-07-24 V5.0 SL.xlsx`
  with SHA-256
  `bebf10a6b2b4ada2daac0615a453f38d374d9c84fcdc8d4d74983fc682589416`.
- The effective section master uses V5 Excel Sheet1 rows for sections 03-34
  and retains `gis.zone` areas for RMC/4L-RMC sections 35-43. The exact totals
  are 40,120 + 5,084 = 45,204 rai across 41 sections.
- This is an immutable `ros_gis` dataset overlay. It does not mutate the
  source `gis.zone` table or any remote GIS.

### Test-first implementation and wiring

- RED tests first rejected the old 47,385-rai GIS-only roster, missing Excel
  provenance, shifted tail areas, missing geometry projection, malformed
  manifests, and the local acceptance fixture's synthetic equal-area split.
- `requirement_sources.json` now records each approved Excel row, canal,
  start/end chainage, and area for sections 03-34, plus exact GIS-area pins for
  sections 35-43.
- The ROS source loader keeps GIS identity and geometry, applies the authority
  split fail closed, hashes raw GIS plus effective rows and authority metadata,
  and writes geometry through `ST_GeomFromEWKB` into immutable history.
- The BFF planning-depth roster now reads the active
  `ros_gis.sections_current` projection and requires 41 sections totaling
  45,204 rai.
- LOCAL-AC source seeding now uses the exact hybrid roster and validates the
  same duplicate, field, chainage, positivity, coverage, and total invariants
  as production.
- `docs/operations/V5_HYBRID_SECTION_MASTER_ACTIVATION.md` records the
  shared-database prerequisite, manual-only activation, read-only acceptance
  queries, rollback boundary, and hydraulic scope boundary.

### Source and no-shift evidence

- The workbook checksum test reads the tracked XLSX package directly and
  compares all 32 approved Sheet1 source rows against the manifest across
  section number (C), canal (B), chainage span (D), and area (Q).
- Exact regression locks include section 21 = 38R-LMC 1+720-3+000 = 503 rai,
  section 22 = 1R-38R-LMC 0+000-4+200 = 1,907 rai, and section 27 =
  38R-LMC 3+000-4+500 = 139 rai.
- A disposable PostGIS integration test exercised the real
  `ST_Multi`/EWKB/history/current-view path and returned 41 MULTIPOLYGON rows
  totaling 45,204 rai.
- A separate disposable PostGIS BFF test applied the actual ROS
  `0001_dataset_version_parent` migration and proved that the BFF reads only
  the active dataset, ignores a superseded roster, and fails closed with no
  active dataset.

### Validation

- Three consecutive full runs passed:
  - ros-gis-integration: 204 passed, 3 environment-gated skips per run.
  - bff-water-planning: 247 passed, 8 environment-gated skips per run.
  - local control-plan harness: 109 passed per run.
- Disposable PostGIS gates passed:
  - ROS requirement integration: 2 passed with migrations 0001-0003.
  - BFF planning-depth integration: 7 passed against the actual ROS view.
- Black 23.11.0, Ruff, JSON parsing, and `git diff --check` passed.
- Every disposable database and role was exact-name checked before creation
  and removed after the gate.

### Independent QCHECK disposition

- Remediated: exact workbook-to-manifest proof, real active-dataset view test,
  local/production manifest parity, canonical crosswalk channel retention,
  fail-closed manifest-domain errors, and real PostGIS geometry evidence.
- Accepted scope boundary: flow-monitoring hydraulic artifacts remain pinned
  to V3. V5 has text-typed `q_max` cells that the existing fail-closed
  generator rejects. V5 sill/FSL/calibration activation needs a separate
  generator/artifact/runtime lifecycle and is not represented as complete.
- Auggie semantic search returned HTTP 402, so exploration used exact-string
  search and direct source reads.
- The spreadsheet artifact runtime could not import `@oai/artifact-tool`;
  workbook authority was therefore verified by checksum and direct OOXML
  regression tests rather than an edited spreadsheet artifact.

### Safety

- No deployment, remote database write, GIS mutation, AWS action, or runtime
  flag change occurred.
- Execution remains disabled, machine commands remain false, command authority
  remains dark, and all activation is still manual and separately gated.

## Review (2026-07-27 11:26:33 +07) - V5 hybrid section-area authority

### Reviewed

- Repo:
  `/Users/subhajlimanond/dev/munbon2-backend-v5-section-area-overlay`
- Branch: `feature/v5-section-area-overlay`
- Scope: complete staged tree for the V5 workbook pin, hybrid section-master
  authority, ROS immutable activation, BFF roster projection, local acceptance
  fixture, tests, and activation runbook.
- Commands run: staged status/stat/check; complete staged source, manifest,
  test, and runbook inspection; XLSX checksum verification; Black 23.11.0;
  Ruff; three repeated full pytest gates; disposable ROS and BFF PostGIS
  integration gates.

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

- The user-confirmed scope is the versioned section-area overlay: Excel
  sections 03-34 and GIS sections 35-43. No remote `gis.zone` mutation is
  authorized.
- V5 hydraulic values are not activated by this change. The generator's
  text-typed `q_max` incompatibility and regenerated hydraulic artifacts remain
  a separate lifecycle.
- Production activation remains pending and must follow the tracked runbook
  only after the ROS and BFF local `POSTGRES_URL` targets are confirmed equal.

### Recommended Tests / Validation

- Require PR checks to start and complete when GitHub billing permits; if they
  run zero steps, report the external block separately from the passing local
  evidence.
- At activation time, verify one active `section_master`, 41 current rows,
  45,204 rai, and the section 21/22/35/43 spot values before accepting BFF
  planning-depth writes.
- Treat V5 sill/FSL/`q_max` generator support as a new test-first task with
  independently regenerated artifact and runtime evidence.

### Rollout Notes

- The change is data-authority and read/write-input plumbing only. It performs
  no deployment, remote GIS update, AWS action, machine command, or command
  authority change.
- Control execution remains disabled and all operational gates remain dark.

## 2026-07-28 16:53:26 +07 - V5 pre-hydraulic local acceptance

### Goal

- Reproduce the complete six-stage local read-only acceptance against backend
  `0793d7b18bbcf2877f1226f46ca027a24910c13a` and frontend
  `fbd4ce4df0bb0476b7cd402ac1a4e180a91a7792` before starting the separately
  scoped V5 hydraulic PR.
- Preserve the primary checkout's user-owned untracked logs/evidence by using
  the detached
  `/Users/subhajlimanond/dev/munbon2-backend-v5-acceptance` worktree.

### What changed

- Added the sanitized ten-file acceptance archive under
  `coding-logs/evidence/2026-07-28-v5-pre-hydraulic-0793d7b1/`.
- No product code, runtime configuration, database state, activation flag, AWS
  resource, or deployment target changed.

### TDD evidence

- No RED run applies because this coherent unit only provisions the existing
  exact-SHA harness, executes acceptance, and archives generated evidence; it
  does not change product behavior.
- Acceptance command that passed:
  `python3 ops/control-plan-read-local/orchestrate.py run-all --release-sha 0793d7b18bbcf2877f1226f46ca027a24910c13a --frontend-sha fbd4ce4df0bb0476b7cd402ac1a4e180a91a7792 --accept-later-origin-main`.

### Commands and results

- `git fetch origin` - passed.
- `git worktree add --detach ../munbon2-backend-v5-acceptance 0793d7b18bbcf2877f1226f46ca027a24910c13a`
  - passed; primary worktree remained untouched.
- `python3 ops/control-plan-read-local/orchestrate.py provision --release-sha 0793d7b18bbcf2877f1226f46ca027a24910c13a --frontend-sha fbd4ce4df0bb0476b7cd402ac1a4e180a91a7792 --accept-later-origin-main`
  - passed exact backend/frontend bundle verification and guest bootstrap.
- The full `run-all` command above passed, in order:
  `LOCAL-BASE-0`, `LOCAL-RTA-1`, `LOCAL-AC-1`, `LOCAL-READ-ACT-1`,
  `LOCAL-EVIDENCE-1`, and `LOCAL-GO-READ-1`.
- `python3 ops/control-plan-read-local/orchestrate.py collect --release-sha 0793d7b18bbcf2877f1226f46ca027a24910c13a --frontend-sha fbd4ce4df0bb0476b7cd402ac1a4e180a91a7792 --accept-later-origin-main --evidence-dir coding-logs/evidence/2026-07-28-v5-pre-hydraulic-0793d7b1`
  - passed evidence streaming and extraction.
- `(cd coding-logs/evidence/2026-07-28-v5-pre-hydraulic-0793d7b1 && shasum -a 256 -c SHA256SUMS)`
  - all nine indexed artifacts passed.
- `shasum -a 256 SHA256SUMS`
  - index digest
    `b03300018ecc59ac876f55edfb445129eb27fb74b1f4de361280b162ba2537b1`.
- Independent JSON contract checks passed: ten exact files, all six verdicts
  `PASS`, exact ordered stage state, final cleanup verified, all final gates
  dark, `aws_actions=false`, and no secret-shaped value keys.
- Both screenshots were visually inspected:
  - live: Waste Way read-only/offline state, null observations, no command
    controls;
  - outage: gate-status-unavailable state with no stale values or controls.

### Independent evidence review

- Result: PASS with no contract or safety finding.
- The reviewer independently repeated checksum verification, confirmed all
  nine installed harness hashes against the exact clean checkout, checked the
  intentional backend/frontend field-shape differences, and verified browser,
  cleanup, listener, PM2, Auth, dark-contract, no-mutation, and no-AWS evidence.
- Residual risk: `SHA256SUMS` is not independently signed and does not checksum
  itself. The archive therefore preserves its aggregate digest above and will
  bind it to a Git commit and PR.

### Safety and follow-up

- This archive proves local read-only acceptance only. It is not AWS,
  deployment, command-authority, or dev-database activation evidence.
- Actual V5 dev activation remains separately authorized by
  `docs/operations/V5_HYBRID_SECTION_MASTER_ACTIVATION.md`.
- Next: archive this evidence through its own PR/merge/local-main lifecycle,
  then branch the V5 hydraulic TDD change from the refreshed merged `main`.
