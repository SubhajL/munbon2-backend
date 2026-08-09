You are the genuine Codex Tier-2 reviewer for an already-landed change. Context: the
R2 remediation (PR #153, squash commit 46cdaa03740e1a19badf7eea04bfb8ef3a3f4663,
parent 45bb5433) was reviewed over 7 rounds by claude-opus-5-0 SUBSTITUTING for
Codex (quota-blocked at the time). The recorded caveat: "That is an uncorrelated
CONTEXT, not a different model family. A real Codex round is recommended before the
nine-stage run." YOU are that real Codex round. Your model family is independent of
both the implementer (Claude) and the substitute reviewer (Opus) — hunt specifically
for what a same-family reviewer plausibly missed.

Scope: the EXACT landed range. Run:
  git show --stat 46cdaa03
  git diff 45bb5433 46cdaa03
Drift status (verified by the orchestrator, and you should spot-check it):
`git diff 46cdaa03 HEAD -- ops/control-plan-read-local/ docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md .gitignore` is EMPTY —
the working tree's copies of every R2 file are byte-identical to the landed range,
so you may cite current file:line.

The R2 commit claims (verify each against the code, do not take them on faith):
1. Five untruthful evidence claims REMOVED (reads_preserved, unconditional
   safe_redirect, retry/client-id comparison of two always-None fields, a
   conflict_result.detail key the proxy never returns, a self-fulfilling logout
   redirect that waited for /login then recorded /login).
2. The replacement drills now prove: seeded field_team user DENIED (roster 403,
   active 403, submit control not rendered, denial banner, no successful write);
   a REAL scheduler outage (pm2 stop, restored on every exit path) → both reads
   502, control not rendered, no write; logout returns a real status, lands on
   /login on navigation AND reload, refresh token revoked.
3. Readiness is neither network quiescence nor any DOM element (the upstream-
   unavailable banner renders from the not-requested placeholder).
4. Happy-path fetches previously sent cookies only while the proxy reads only the
   Authorization header (per the commit, a proof the merged stage never executed) —
   confirm the R2 code now authenticates its fetches correctly.

Questions:
0. Does the landed code actually deliver each claim above? Cite file:line.
1. Any remaining self-fulfilling evidence, fail-open path, or claim the artifacts
   assert but the drills do not prove? (This is the R2 failure class — hunt it.)
2. Any CRITICAL/HIGH defect the 7 Opus rounds missed (they found 2 CRITICAL,
   5 HIGH, 13 MEDIUM — 3 of the defects were introduced by fixes to earlier
   findings, so look hard at the FIX sites)?
3. Any secret, non-loopback host, or credential in the landed range?
4. Would the evidence files this produces be trustworthy inputs to a nine-stage
   acceptance freeze — what, if anything, must be re-verified at run time?
Report findings as CRITICAL/HIGH/MEDIUM/LOW with file:line, then a clear verdict:
does this landed range support proceeding to the nine-stage acceptance run?
