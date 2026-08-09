# LOCAL-WRITE-UI-1 failure — root-cause investigation

## Symptom (reproducible, 2 orchestrator runs)
`LOCAL-WRITE-UI-1` fails at gate `browser_verify_submit_affordance_failed`.
Captured browser detail (via a controlled re-arm of the frozen frontend):
`page.waitForFunction: Timeout 35000ms exceeded` — the `readPanelAffordance`
wait for the app's own roster+active planning-depth reads to settle.

## Ruled OUT: the #160 evidence-harness code
Independent Chromium test of `installReadRecorder`'s injection (the exact
`new Function(recordSource)` / `new Function(wrapperSource)` init script from
`run-write-browser.js`) in a real page:
- `window.__planningDepthReads` set (`object`), `window.fetch` wrapped (`true`),
  no injection error. The recorder installs and wraps fetch correctly.

## Established cause: the frozen frontend issues no planning-depth reads
Arming the frozen frontend (`smart-cms-app@067b3e22`, `next start`, WRITE-UI
flags `CONTROL_PLAN_READS=false, WATER_PLANNING_V2=true, SUBMIT_ENABLED=true`),
logging in as the seeded operator, and navigating to the harness route
`WATER_PLANNING_PATH = /smart-water/dashboard`:
- `LOGIN_STATUS=200`
- `NETWORK_PLANNING_RESPONSES=[]`  — the app fires NO roster/active reads
- `RECORDER_READS={}`             — nothing to record (nothing fetched)
- `SUBMIT_BUTTON_COUNT=0`         — the `ส่งแผน` submit control is absent
- Same result with `CONTROL_PLAN_READS=true` — not a control-plan-reads flag toggle.

The harness's `readPanelAffordance` correctly passes the route-200 and
recorder-installed asserts, then times out because the app issues none of the
planning-depth reads it derives the panel policy from.

## Conclusion
The frozen frontend `067b3e22` does not render the planning-depth panel / issue
its roster+active reads on `/smart-water/dashboard` under the WRITE-UI stage's
flag configuration, so the operator submit-affordance never appears. This is a
frontend↔harness integration gap at the frozen candidate — independent of the
backend (#155) and evidence-harness (#160) work landed in this backend SHA
(the recorder is proven functional; the reads simply never fire). The
LOCAL-WRITE-UI-1 stage cannot pass against this frontend candidate as-is.
Tracked as a follow-up issue.
