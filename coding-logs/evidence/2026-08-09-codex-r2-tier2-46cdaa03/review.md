## Findings

No CRITICAL findings.

### HIGH

1. Browser logout and refresh revocation concern different sessions.

The three browser contexts log in and log out through the frontend at [run-write-browser.js:321](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-write-browser.js:321), [run-write-browser.js:656](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-write-browser.js:656), and [run-write-browser.js:722](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-write-browser.js:722), but their refresh cookies are never captured or reused.

Separately, Python creates another direct central-auth session at [run-stage-suite.py:4953](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-stage-suite.py:4953), logs that unrelated token out at [run-stage-suite.py:5058](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-stage-suite.py:5058), then verifies its reuse returns 401 at [run-stage-suite.py:5066](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-stage-suite.py:5066).

Consequently, a frontend logout defect that clears the browser cookie and redirects without revoking that browser session can still PASS: the browser proves navigation, while the independent direct-auth session proves revocation. That does not deliver the combined claim in [the runbook:227](/Users/subhajlimanond/dev/munbon2-backend/docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md:227).

Fix: preserve each browser context’s pre-logout refresh cookie and assert that exact token returns 401 after that context’s logout. Add a negative integration test where cookie clearing/navigation succeeds but upstream revocation is suppressed.

2. Scheduler restoration is attempted, but not guaranteed on the normal-success/restore-failure path.

`_restore_scheduler()` performs one restart/readiness attempt at [run-stage-suite.py:4783](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-stage-suite.py:4783). After successful browser evidence, it is called outside the protected exception block at [run-stage-suite.py:4898](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-stage-suite.py:4898). If that restart or readiness check fails, top-level handling only writes a failure manifest at [run-stage-suite.py:5704](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-stage-suite.py:5704); it performs no final recovery or state verification.

This cannot create a false PASS, but it can leave Scheduler stopped or indeterminate after a failed stage, contradicting “restored on every exit path” at [the runbook:257](/Users/subhajlimanond/dev/munbon2-backend/docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md:257).

Fix: add an outer restoration guard with bounded retry and an independent PM2/readiness final-state check. Record restoration status in the failure manifest. Test the exact sequence “browser succeeds → first restore fails.”

### MEDIUM

3. Body-completion readiness fails open to headers-only observation.

The fetch recorder waits for `response.clone().arrayBuffer()`, but catches any failure and still records the response status at [run-write-browser.js:399](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-write-browser.js:399). A truncated/aborted body can therefore satisfy the read-settle predicate while the application never consumes the response body. In the outage case, the placeholder unavailable banner plus 502 headers and later explicit probes can still pass.

That is weaker than the documented “app’s own reads completing” claim at [the runbook:236](/Users/subhajlimanond/dev/munbon2-backend/docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md:236).

Fix: record a failure sentinel—or do not mark the path settled—when body consumption fails, and reject it. Add a page-level test with a response whose body aborts after headers.

No LOW findings worth reporting.

## Claim verification

| Claim | Result |
|---|---|
| Five former fabrications removed | Yes. `reads_preserved` is explicitly rejected at [run-stage-suite.py:4627](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-stage-suite.py:4627); exact redirect and reload-origin checks replace `safe_redirect` at [run-stage-suite.py:4641](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-stage-suite.py:4641). The receipt now records only real returned fields at [run-write-browser.js:563](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-write-browser.js:563), and conflict evidence contains status only at [run-write-browser.js:627](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-write-browser.js:627). |
| Field-team denial | Delivered. The browser gathers real DOM, read and submit results at [run-write-browser.js:656](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-write-browser.js:656); exact 403s, mutually exclusive banners, absent control and submit 403 are enforced at [run-stage-suite.py:4599](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-stage-suite.py:4599). |
| Real scheduler outage | Delivered for a passing run. PM2 is stopped only after browser readiness and before release at [run-stage-suite.py:4824](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-stage-suite.py:4824); exact read/write 502s and UI state are enforced at [run-stage-suite.py:4623](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-stage-suite.py:4623). The unconditional restoration claim has HIGH-2 above. |
| Logout | Real statuses, actual navigation, and reload-from-protected-path are delivered at [run-write-browser.js:456](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-write-browser.js:456) and [run-stage-suite.py:4641](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-stage-suite.py:4641). Same-browser-session revocation is not delivered—HIGH-1. |
| Readiness not DOM/network-idle | Substantially delivered through application fetch instrumentation and both-path settling at [run-write-browser.js:164](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-write-browser.js:164) and [run-write-browser.js:389](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-write-browser.js:389), subject to MEDIUM-3. |
| Bearer-authenticated fetches | Yes. Captured tokens are attached by `authorizedRequestInit` at [run-write-browser.js:83](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-write-browser.js:83) and used by every raw planning read/write at [run-write-browser.js:295](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/run-write-browser.js:295). The frontend proxy reads only the Authorization header at [upstream-guard.ts:60](/Users/subhajlimanond/dev/smart-cms-app/app/api/smart-water-backend/water-planning/upstream-guard.ts:60). |

## Secrets and hosts

No real secret or static production credential is committed. The field-team password is generated with OpenSSL and written mode 600 at [bootstrap-linux.sh:180](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/bootstrap-linux.sh:180) and [bootstrap-linux.sh:334](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/bootstrap-linux.sh:334). Test credentials are disposable fixtures.

The range does contain three non-loopback public host literals, but only as negative test inputs proving they are blocked at [test_write_browser_inventory.js:193](/Users/subhajlimanond/dev/munbon2-backend/ops/control-plan-read-local/tests/test_write_browser_inventory.js:193). No operational R2 request targets a non-loopback host.

## Verdict

**NO-GO for the acceptance-counting nine-stage run.** The field-team and outage evidence is materially sound, but the logout artifact currently combines two unrelated sessions and therefore overclaims browser-session revocation. Fix HIGH-1 before producing freeze inputs; fix HIGH-2 before relying on cleanup safety.

At runtime, re-verify:

- clean, exact backend and frontend candidate SHAs and installed harness hashes;
- the same browser refresh token returns 401 after logout;
- real 403/502 statuses and browser-rendered state;
- Scheduler is online and `/ready` after every stage outcome;
- frontend and BFF write flags are dark;
- stage-state/checksum continuity and final `SHA256SUMS`;
- no reuse of the historical result at [runbook:266](/Users/subhajlimanond/dev/munbon2-backend/docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md:266).

Validation completed: requested `git show --stat` and full range diff, empty R2 drift check, `git diff --check`, Node 23/23, targeted Python validator tests 35/35 plus artifact test 1/1, Ruff clean, and Python AST parse. The full Python suite was sandbox-blocked because no writable temporary directory exists.

The mandatory `g-check` Coding Log append could not be performed because this workspace is read-only; the current pointer was left unchanged.

