# Coding Log — LOCAL-WRITE-UI-1 drill session-race fix

## Problem (from the frozen nine-stage acceptance, #165)
LOCAL-WRITE-UI-1 failed reproducibly at browser_verify_submit_affordance_failed.
Proven root cause: the frontend session is in-memory (smart-cms-app
lib/auth/client.ts) and re-established on mount by a silent refresh
(auth-context.tsx) that ROTATES the refresh cookie. loginAndCaptureToken lands
on /smart-water/dashboard (mount refresh R1->R2 in flight); readPanelAffordance
then does an immediate full-page page.goto of the SAME url, whose mount refresh
races the in-flight one on the same rotating token -> one revokes it -> session
permanently signed out -> AuthGuard redirects to /login -> planning reads never
fire -> waitForFunction 35s timeout.

## Fix
loginAndCaptureToken now waits for the first silent refresh (/api/auth/refresh)
to COMPLETE before returning, so subsequent navigations' refreshes are
serialized (no concurrent rotation race).

## Validation
Manual reproduction in the guest (backend up, full proxy env, fresh armed build):
BEFORE the fix the drill failed at verify-submit-affordance; AFTER the fix it
passes verify-submit-affordance and progresses to create-submission (the manual
repro then fails at create_not_201 because the ad-hoc week_key was not seeded —
the real stage supplies a valid week/section). Full end-to-end validation is the
re-frozen nine-stage re-run.
