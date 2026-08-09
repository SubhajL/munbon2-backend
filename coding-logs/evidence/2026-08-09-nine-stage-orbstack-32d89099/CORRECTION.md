# CORRECTION to ROOT-CAUSE-INVESTIGATION.md — the frozen frontend WORKS

The original `ROOT-CAUSE-INVESTIGATION.md` in this directory concluded that the
frozen frontend `067b3e22` "does not render the planning-depth panel / issue its
roster+active reads." **That conclusion is wrong.** It was produced from
contaminated manual reproductions and must not be relied upon.

## Why the original investigation was invalid
The manual re-arms were run after the OrbStack guest had been restarted, which
left the PM2 backend (bff/scheduler/ros-gis/flow-monitoring) **down**, and the
manual `next start` invocations were **missing the frontend's server-side proxy
env** (`CENTRAL_AUTH_URL`, `WATER_PLANNING_BFF_URL`, `API_SERVER`,
`PLANNING_DEPTH_*`). The frontend therefore returned 503/401 and bounced to
`/login`, rendering nothing — an artifact of the broken test setup, not the
frontend.

## Corrected finding (backend up, full proxy env, fresh armed build)
Logging in as the seeded operator and landing on `/smart-water/dashboard` (the
login redirect target), session held in memory:
- **both planning reads fire at HTTP 200** (`planning-depth-roster`,
  `planning-depth-submissions/active`);
- **the `ส่งแผน` submit control renders** (`SUBMIT_BUTTON_COUNT=1`).

The frozen frontend `067b3e22` is **functional**.

## Actual root cause of the LOCAL-WRITE-UI-1 failure
The frontend session is **in-memory only** (`smart-cms-app lib/auth/client.ts:53`,
`let session = null`; no localStorage/cookie), and `middleware.ts` does not
server-gate `/smart-water`. The harness drill's `readPanelAffordance`
(`ops/control-plan-read-local/run-write-browser.js`) reaches the panel with a
full-page `page.goto(WATER_PLANNING_PATH, {waitUntil:"domcontentloaded"})`. That
reload **drops the in-memory session** → AuthGuard redirects to `/login` → the
login page issues no planning reads → `page.waitForFunction` times out (35s) →
`browser_verify_submit_affordance_failed`.

This is a **harness-drill ↔ frontend-session-design incompatibility** (the #153/R2
review already noted the WRITE-UI stage "was never executed"). It is NOT a defect
in #155/#160/#161, and NOT the frozen frontend being broken.

## Consequence for the acceptance
The nine-stage acceptance cannot reach a passing WRITE-UI with the frozen
candidate as-is: the fix belongs to the WRITE-UI drill (read the affordance on the
post-login page / drive phases via client-side navigation instead of full-page
`goto`, or persist the session), which is a backend-candidate change and thus a
re-freeze-and-re-run, out of scope for this frozen run. Tracked as #165
(retitled to a harness-drill bug).
