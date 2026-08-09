# Coding Log — #160 R2 write-UI evidence gaps (pre-freeze)

Started: 2026-08-09-08-10-35 (+07). Branch: fix/160-r2-evidence-gaps @ f7727cd4, worktree ../munbon2-backend-155.
Source: genuine Codex Tier-2 review of #153/R2 (coding-logs/evidence/2026-08-09-codex-r2-tier2-46cdaa03/) — NO-GO until HIGH-1/HIGH-2/MED-3 fixed.

## DREP

# DREP — #160: R2 write-UI evidence gaps (pre-freeze)

## §0 Repo Profile
Branch fix/160-r2-evidence-gaps @ origin/main f7727cd4, worktree ../munbon2-backend-155.
Gates (ops harness, from ops/control-plan-read-local): `python3 -m pytest tests/ -q` (baseline 272 passed) · `node --test tests/test_write_browser_inventory.js tests/test_seed_local_operators.js` (baseline 15 passed) · ruff --select F courtesy. No typecheck/build. Coding log: new file + tracked pointer update. Ownership ours/production.
MUST NOTs: repo-wide list; PLUS harness-specific: no secret-shaped keys/bearer/token values in evidence (sanitizer rejects); loopback-only hosts; never weaken an existing validator check; evidence records only what was actually observed.

## §1 Goal / Non-Goals
Close the three Codex-R2-review findings (#160) so the nine-stage freeze candidate carries truthful LOCAL-WRITE-UI-1 evidence: per-browser-context logout revocation proof, guaranteed-and-reported scheduler restoration, and a fail-closed read-settle predicate.
Non-Goals: no auth-service or smart-cms-app changes; no orchestrate.py or other-stage changes; keep the Python direct-session refresh probe (auxiliary, distinct evidence); no new CLI/env surface; no runbook rewrites beyond the two claim sentences the fixes make true.

## §2 Requirements
- R1: run-write-browser.js captures each context's own `refreshToken` cookie (context.cookies(); frontend sets it via hardenRefreshCookie on login, clears on logout) BEFORE that context's logout, and AFTER logout POSTs {refreshToken:value} via Node fetch to http://127.0.0.1:3005/api/v1/auth/refresh, recording ONLY the integer status: field_team_result.refresh_reuse_status; logout_result.refresh_reuse_status (primary); logout_result.second_context_refresh_reuse_status.
- R2: validate_write_browser_result raises ValueError unless all three refresh_reuse_status fields are exactly 401 (missing key, None, 200, 403 all reject).
- R3: _run_write_browser restores the scheduler through a bounded guarded helper on BOTH exit paths (retry ≤3 with backoff; readiness verification per attempt); the report dict {"attempts", "restored", "failed_gate"} is attached as `.restoration` to the raised StageGateError (existing manifest writer persists it — same channel as _go_read_restoration_guard); success-path restore failure raises StageGateError("write_ui_scheduler_restore_failed") — the stage FAILS.
- R4: recordPlanningRead(reads, url, status, paths, origin, bodySettled=true) does NOT record when bodySettled is false; the injected fetch wrapper passes false when clone().arrayBuffer() fails for an on-path read → the read stays unrecorded → existing waitForFunction timeout fails the drill (fail closed).
- R5: no token value appears in evidence — new fields are ints only.

## §3 Change Contract
| ID | Path | Action | Anchor |
|----|------|--------|--------|
| F1 | ops/control-plan-read-local/run-write-browser.js | MODIFY | logoutContext L321 (add contextRefreshCookie + refreshReuseStatus beside it); field-team block L668–689 (capture→logout→probe→record); logout block L722–733 (both contexts); recordPlanningRead L380–388 (bodySettled param); installReadRecorder wrapper L397–423 (pass flag) |
| F2 | ops/control-plan-read-local/run-stage-suite.py | MODIFY | validate_write_browser_result field-team L~4620 + logout L~4643 (require 401×3); NEW _restore_scheduler_guarded after _restore_scheduler L4783; _run_write_browser L4895–4928 (both exits guarded + .restoration) |
| F3 | ops/control-plan-read-local/tests/test_stage_suite.py | MODIFY | _write_browser_evidence fixture (~L2700) += 3 fields; new tests after L2856 block; guard tests near L3276 idiom |
| F4 | ops/control-plan-read-local/tests/test_write_browser_inventory.js | MODIFY | recordPlanningRead cases |
| F5 | docs/operations/CONTROL_PLAN_ALL_STAGES_LOCAL_ACCEPTANCE.md | MODIFY | logout claim sentence ~L227; restore claim sentence ~L257 |

## §4 Function Contracts
FN1 contextRefreshCookie(context) -> Promise<string> — context.cookies(); find name=="refreshToken" non-empty value; throw Error("refresh_cookie_not_captured") if absent. HttpOnly cookies ARE returned by context.cookies().
FN2 refreshReuseStatus(refreshValue) -> Promise<number> — Node global fetch POST JSON {refreshToken} to const AUTH_REFRESH_URL="http://127.0.0.1:3005/api/v1/auth/refresh" (mirrors suite's hardcoded loopback); returns res.status; network error propagates (drill fails loudly). Never logs/records the value.
FN3 recordPlanningRead(reads, url, status, paths, origin, bodySettled = true) — when false: return reads unchanged (no record). Default true keeps existing callers/tests valid.
FN4 _restore_scheduler_guarded(attempts: int = 3, backoff_seconds: float = 5.0) -> dict — loops _restore_scheduler() catching Exception per attempt; sleeps backoff between; returns {"attempts": n_used, "restored": bool, "failed_gate": str|None}; NEVER raises.
FN5 validate_write_browser_result — adds: field_team["refresh_reuse_status"]==401; logout["refresh_reuse_status"]==401; logout["second_context_refresh_reuse_status"]==401 (each else raise ValueError).
FN6 _run_write_browser — except path: report=_restore_scheduler_guarded(); if not report["restored"]: combined-code StageGateError (existing naming) with .restoration=report; else re-raise primary with .restoration=report. Success path: report=_restore_scheduler_guarded(); if not restored: raise StageGateError("write_ui_scheduler_restore_failed") with .restoration=report.

## §5 Test Plan (all in F3 unless noted)
T1 test_validate_write_browser_result_rejects_missing_refresh_reuse — parametrize field∈{field_team_result.refresh_reuse_status, logout_result.refresh_reuse_status, logout_result.second_context_refresh_reuse_status}; del from fixture → pytest.raises(ValueError). RED: DID NOT RAISE (validator ignores fields today).
T2 test_validate_write_browser_result_rejects_unrevoked_refresh_reuse — parametrize same fields set to 200 (also one case 403) → ValueError. This IS the negative "cookie cleared+redirect fine but revocation suppressed" test. RED: DID NOT RAISE.
T3 existing accept test with fixture += {401,401,401} stays green (regression).
T4 test_restore_scheduler_guarded_retries_then_reports_success — monkeypatch _restore_scheduler fail-once-then-succeed; assert report == {"attempts":2,"restored":True,"failed_gate":None}. RED: AttributeError (absent).
T5 test_restore_scheduler_guarded_reports_failure_after_bounded_attempts — always-raise; assert {"attempts":3,"restored":False,"failed_gate":<str>}; no raise; monkeypatch time.sleep. RED: AttributeError.
T6 test_run_write_browser_success_path_fails_closed_when_restore_fails — monkeypatch _drive_write_browser→{}, _restore_scheduler_guarded→{"restored":False,...}; pytest.raises(StageGateError, match="write_ui_scheduler_restore_failed"); excinfo.value.restoration is the report. RED: AttributeError on guarded name.
T7 test_run_write_browser_failure_path_attaches_restoration_report — fake _drive_write_browser sets state["scheduler_stopped"]=True then raises StageGateError("evidence_bad"); guarded→{"restored":True,...}; assert raised error is the primary code and .restoration==report. RED: AttributeError.
T8 (F4, node) recordPlanningRead with bodySettled=false leaves reads unchanged for an on-path URL. RED: extra arg ignored today → records → assert fails.
T9 (F4, node) bodySettled omitted/true records (back-compat pin; passes pre-change).
Runtime-only proof: the real per-context 401s and the guarded restore in anger are exercised at the actual LOCAL-WRITE-UI-1 run (item 3); unit level proves the validator/guard contracts (fail-closed shape), consistent with the R2 pattern (validator tests + reviewed JS).

## §6 Traceability
R1 → F1: field-team block (capture before logoutContext L~676; probe+record after) + logout block (capture both before L~723-724 logoutContext calls; probe+record after) | T1–T3 shape-side | S1
R2 → FN5 raises at the two validator sections | T1,T2 | S1
R3 → FN6 both exits call _restore_scheduler_guarded + setattr(.restoration); manifest writer already persists (run-stage-suite.py main(), `restoration = getattr(...)`) | T4–T7 | S1
R4 → installReadRecorder wrapper bodySettled=false branch → FN3 early return | T8,T9 | S1
R5 → FN1/FN2 record status ints only | T3 (fixture shape) | S1

## §7 Wiring
recordPlanningRead already exported + imported by F4 tests (signature extension, default arg). New JS helpers module-internal, called from require.main block (runtime path). _restore_scheduler_guarded called from _run_write_browser (both exits). Validator additions inside already-wired validate_write_browser_result (called at _drive_write_browser return L~4869). No new env/config.

## §8 Slice Plan
S1 = F1–F5, T1–T9. Owner: Claude (Q0 fires: claim/token trust — logout-revocation evidence IS an auth-trust boundary, and the harness is the acceptance trust anchor). No delegation. Oracle: T1–T9 RED→GREEN, pytest 272→280+ green ×3, node 15→17+ green, ruff F clean.

## §9 Risks
- Frontend cookie name drift → contextRefreshCookie throws at runtime → stage fails loudly (fail closed, correct).
- Auth service unreachable from Node fetch → refreshReuseStatus throws → drill fails loudly (correct; suite already depends on loopback 3005).
- Guarded restore masks a genuinely dead pm2 → report says restored=False and the stage FAILS; nothing is masked.
- recordPlanningRead default-arg keeps old behavior for all other callers (only one injected call site).
Rollback: revert the PR; no schema/state.

## §10 Do-Not-Touch
ops/control-plan-read-local/{orchestrate.py, bootstrap-linux.sh, seed-*.js, seed-approved-sources.py, run-evidence-browser.js, run-go-read-browser.js, run-read-browser.js, run-ros-manual-producer.sh, local-ac1.py, systemd/}, tests/test_local_artifacts.py, tests/test_seed_local_operators.js, ops/control-plan-read-runtime/**, services/**, .github/**, all other docs. Allowed: F1–F5 + new coding log + .codex/coding-log.current.

## Codex adversarial plan review (gpt-5.6-sol xhigh) — synthesis
Verdict NO-GO as drafted; every finding verified and dispositioned:
1. ACCEPT (blocker) cookie name is `smart_cms_refresh` NOT `refreshToken`
   (smart-cms-app lib/auth/server.ts:5; hardenRefreshCookie re-wraps the upstream
   refreshToken VALUE — so the cookie's value IS the central-auth token). FN1
   corrected; verified at source.
2. ACCEPT (blocker) FN2 must send Content-Type: application/json (services/auth
   uses express.json(); string body without header → not parsed).
3. ACCEPT validator raises StageGateError("write_browser_result_not_accepted")
   via its except-idiom, not ValueError — T1/T2 expectations corrected (idiom
   verified at test_stage_suite.py:2744).
4. ACCEPT (self-caught pre-review, convergent) projection must echo the three
   refresh_reuse fields or evidence silently drops them.
5. ACCEPT bodySettled becomes a REQUIRED param (default-true was fail-open);
   wrapper extracted as exported factory (makePlanningFetchWrapper) injected by
   source — the SAME unit-tested code runs in-page (existing recordPlanningRead
   pattern); T8 rewritten as a genuine aborted-body test: fake Response whose
   clone().arrayBuffer() rejects → read NOT recorded. Artifact-test string pin
   ("await response.clone().arrayBuffer()") retained by the factory.
6. ACCEPT guard needs an INDEPENDENT final-state check: new
   _verify_scheduler_restoration() (pm2 state + readiness, NO restart) decides
   `restored` regardless of attempt outcomes (covers restart-timeout-but-
   actually-up); _restore_scheduler_guarded wraps its WHOLE body in try
   (genuinely no-raise for Exception).
7. ACCEPT stub-first ordering (repo C-1): scaffold the guarded helper stub so
   RED is behavioral, not AttributeError; fixture gains fields BEFORE T1 deletes
   them (RED = validator DID-NOT-RAISE, not KeyError).
8. ACCEPT add T6b (browser-success → first restore fails → retry succeeds →
   stage PASSES and result carries scheduler_restoration report) and T10
   end-to-end manifest test mirroring test_stage_suite.py:928 (restoration in
   failure JSON through main(), sanitizer-clean). Success path now records
   result["scheduler_restoration"].
9. ACCEPT main() attribute-transfer gap: unexpected_* wrapper drops
   .restoration — transfer it when wrapping non-StageGateError primaries.
10. REJECT "dirty worktree" — the coding log + tracked pointer update ARE the
    repo's per-PR convention (#155/#157 precedent), not stray state.
11. PARTIAL "required suppression test": a full-stack clear-without-revoke
    harness is out of proportion; the load-bearing chain is (a) capture code
    reads THIS context's jar (reviewed), (b) raw status recorded, (c) validator
    REQUIRES 401 (suppression VALUE case unit-tested: 200/403/None reject),
    (d) real 401s proven at the actual stage run. Recorded honestly.
12. ACCEPT runbook wording phrased as gate ENFORCEMENT (not run-completion)
    claims; lands in the same commit as the enforcement.
Confirmed-correct plan facts (per reviewer): HttpOnly cookies visible to
context.cookies(); cookies not port-scoped; Node 22 global fetch; field names
sanitizer-safe; all logoutContext call sites listed.

## g2-coding — implementation record
Stop line: NONE — Q0 fires (auth-evidence/claim trust; the harness is the
acceptance trust anchor). All code Claude-authored; TDD per unit, fixture-first
and stub-first per synthesis.

Unit A (R2 validator+projection): fixture += 3 fields; 13 new tests
(missing×3, unrevoked 200/403/None ×3 fields, projection echo) RED
(DID-NOT-RAISE / projection KeyError) → validator checks + projection → GREEN
285.
Unit B (R3 guard): stubs scaffolded (C-1) → 7 tests RED (NotImplementedError /
missing behavior): guarded retry-success, bounded failure, restored-despite-
command-error (independent verification decides), success-path fail-closed,
combined browser-success→first-restore-fails→retry-succeeds (evidence carries
scheduler_restoration), failure-path .restoration attach, end-to-end
unexpected_* manifest transfer (mirrors go-read :928) → implemented
_verify_scheduler_restoration (pm2 jlist + readiness, NO restart),
_restore_scheduler_guarded (whole-body try, never raises), _run_write_browser
both exits, main() attribute transfer → GREEN. Pre-existing write-browser fakes
taught pm2 jlist state (shared installer: online; fails-closed + keeps-primary
overrides: stopped — each scenario's true pm2 state); fails-closed test
strengthened to match="scheduler_restore_failed".
Unit C/D (R1 capture+probe, R4 wrapper): artifact-test string pins
(smart_cms_refresh, refresh_reuse_status, contextRefreshCookie,
makePlanningFetchWrapper) + 4 node tests RED → implemented: strict
bodySettled!==true no-record contract; makePlanningFetchWrapper extracted
(SAME source injected in-page via toString — no second copy; retains the
"await response.clone().arrayBuffer()" artifact pin); contextRefreshCookie
(smart_cms_refresh per lib/auth/server.ts:5) + refreshReuseStatus (JSON header,
status only) wired at all three logout call sites → GREEN.
NOTE §10 amendment: tests/test_local_artifacts.py was DNT in the draft DREP;
modified STRENGTHENING-ONLY (added required strings) — recorded, not silent.
F5 runbook: logout row (per-context own-credential 401, direct-auth probe
demoted to corroboration), outage row + restore paragraph (bounded guarded
restart, report into evidence/manifest) — enforcement phrasing, lands with the
enforcement.
Gates (Claude-run): pytest 292 ×3 (baseline 272, +20); node 19 ×3 (baseline 15,
+4); ruff F clean (1 F841 fixed); node --check OK. Diff audit: F1–F5 +
test_local_artifacts.py + log + pointer only.

## g2-qcheck round 1 (framing: contract-correctness) — launched both tiers

### Round 1 — Tier 2 (codex gpt-5.6-sol xhigh) result
NO CRITICAL; 1 HIGH + 4 MEDIUM + weak-test notes. Reviewer did real work
(file:line, empirical injections, Playwright docs cite; node 19 + targeted
pytest 19 run in its sandbox). Dispositions:
- HIGH sanitizer accepts api_key / embedded bearer → DEFERRED w/ owner: both
  claims empirically CONFIRMED by me, both PRE-EXISTING sanitizer scope (list
  never had "key"; bearer check always prefix-only); this diff adds verified
  integer fields only. Naive fix breaks week_key/project_key. Filed issue #162
  (word-boundary sensitive-key policy + embedded-bearer regex, own PR).
- MEDIUM 401.0 (float) accepted → FIXED (TDD): _is_strict_401 (int, not bool,
  == 401) at all three checks; negative params extended with 401.0/"401"/True
  (3 RED, rest already-rejected).
- MEDIUM taxonomy (KeyboardInterrupt/SystemExit escape the guard) → FIXED by
  narrowing the DECLARED guarantee (docstring: interrupt-class propagates BY
  DESIGN — operator abort outranks evidence completeness, mirroring main()'s
  own except Exception boundary). No behavior change.
- MEDIUM raw str(exception) can leak creds / trip sanitizer and silently drop
  the manifest → FIXED (TDD): _safe_error_code (StageGateError codes verbatim,
  else unexpected_<Type>); RED test injects credential-shaped text.
- MEDIUM R1 has no load-bearing behavioral test → FIXED (TDD):
  proveContextLogout seam (capture THIS context → ITS logout → probe THAT
  value) used at all three call sites; node tests pin ordering + payload
  identity + capture-failure short-circuit (2 RED); artifact pin added.
Weak-test notes: body-settle test strengthened (deferred body promise; reads
inspected BEFORE resolution — kills record-at-headers); backoff now asserted
(sleeps == [2.5, 2.5]); _verify_scheduler_restoration direct tests (jlist+
readiness, NEVER restart; stopped → raises). Projection literal-vs-copied →
REJECTED w/ reason: the validator admits only 401, so a literal and a copy are
observationally identical at green; the projection code copies (reviewed), and
the anti-fabrication comment governs.
Gates after fixes: pytest 305 ×1 (3× pending round close), node 21, ruff F
clean, node --check OK.

### Round 1 — Tier 1 (/code-review high, wf_6c185cf1-a77, 24 agents, 0 errored) result
2 CONFIRMED correctness + 4 PLAUSIBLE + 3 CONFIRMED cleanups (1 dropped at cap).
De-dup: free-text failed_gate found by BOTH tiers (fixed once, two witnesses).
Dispositions:
- CONFIRMED guard's Exception-only catch lets Ctrl-C during the multi-minute
  restore replace the primary finding AND bypass main()'s manifest writer →
  FIXED (supersedes my round-1-Tier-2 docstring-narrowing disposition, which
  Tier 1's concrete scenario invalidated): outer catch widened to BaseException
  with the reasoning documented; RED test literally killed the pytest run via
  the escaping KeyboardInterrupt before the fix — the defect demonstrated
  itself. Gate-code extraction unified through _safe_error_code (annotation
  widened to BaseException).
- CONFIRMED refreshReuseStatus fetch unbounded → wedged auth misdiagnosed as
  write_browser_outage_timeout → FIXED: AbortSignal.timeout(15000) + artifact
  pin.
- PLAUSIBLE no positive control on the captured cookie → PARTIAL FIX with
  evidence: central auth refresh ROTATES + revokes (auth.service.js
  refreshAccessToken: tokenEntity.revoke('Token refresh')), so ANY liveness
  probe destroys the credential it checks — the reviewer's suggested pre-logout
  200-probe is impossible here. Implemented the strongest non-destructive
  control: assertRefreshShaped (3-segment JWT, payload.type=="refresh") in
  contextRefreshCookie, node-tested against the real wrong-capture modes
  (access-type token, base64-re-wrapped value, opaque blob, truncated, empty).
  RESIDUAL recorded honestly: a silent app-side refresh rotating the token in
  the ms between capture and logout stays undetectable without a
  non-destructive introspection endpoint (noted for future auth work).
  Test-case lesson: my first "percent-encoded" case was a no-op on base64url
  JWTs — RED caught my own flawed test.
- PLAUSIBLE second-context 401 not isolated (same-user family revocation) →
  REJECTED with evidence: logout revokes ONLY the presented token row
  (auth.service.js logout: findOne({where:{token}}) → token.revoke), so the
  first logout cannot kill the second context's credential; the suggested
  between-logouts liveness probe is destructive (rotation).
- PLAUSIBLE fail-closed inversion (truthful 502 with truncated body now fails
  the drill) → REJECTED as designed: that inversion IS #160's required
  behavior; a loud, re-runnable drill failure is the accepted cost of deleting
  the headers-as-reads fabrication channel.
- PLAUSIBLE new-Function injection surface untested + sentinel-before-install →
  FIXED: round-trip node test rebuilds BOTH sources via new Function out of
  module scope (a future module-const capture now fails the unit suite, not an
  opaque in-page 35s timeout); init script sets the __planningDepthReads
  sentinel only AFTER a successful wrapper install so
  read_recorder_not_installed detects a failed rebuild.
- CONFIRMED cleanup free-text failed_gate → already fixed (Tier-2 convergent).
- CONFIRMED cleanup combined gate code unpinned (re.search substring) → FIXED:
  full-equality assert on
  write_browser_result_not_accepted_and_scheduler_restore_failed.
- CONFIRMED cleanup off-path body test near-vacuous → FIXED: clone-call
  tracking asserts the paths gate runs BEFORE clone (cloneCalls == 0).
- Dropped-at-cap AUTH_REFRESH_URL duplication → noted; single definition in JS,
  suite's Python constant is a separate runtime (accepted).
Gates after round-1 fixes (both tiers): pytest 306, node 23, ruff F clean,
node --check OK.

### Round 2 launched (adversarial framing) — both tiers on remediated tree

### Round 2 results (adversarial) — Tier 2 codex + Tier 1 workflow wf_d0ada1e7-6fd (21 agents) + Tier 2 (bzgj9g9q4)
Both tiers converged: my round-1 restoration-guard rework introduced real
regressions (the review loop WORKING). De-duplicated dispositions:
- CONFIRMED (BOTH tiers) primary interrupt bypasses main()'s manifest → FIXED
  (TDD): main() catches BaseException, writes the manifest (restoration
  transferred), then RE-RAISES interrupt-class with its own exit semantics /
  returns 1 for Exception. RED test literally failed (no manifest) before the fix.
- CONFIRMED (Tier 1) proveContextLogout skipped logout on capture failure →
  sessions left un-revoked server-side (a regression I introduced) → FIXED (TDD):
  logout now ALWAYS fires (capture failure contained, surfaced AFTER logout);
  test rewritten to require logout-on-capture-failure.
- CONFIRMED (Tier 1) success-path interrupt converted to a fake
  scheduler_restore_failed + minutes of finally work → FIXED: _restore_scheduler_
  guarded reverted to Exception-only (interrupts PROPAGATE); _run_write_browser
  preserves the primary finding when an interrupt fires DURING a failure-path
  restore, and lets a success-path interrupt propagate cleanly (never a fake FAIL).
- CONFIRMED (Tier 1) verify gate-code dropped when both restart+verify fail →
  FIXED: the independent final-state verification is now AUTHORITATIVE on failure
  (its code wins); test updated (was expecting the restart code).
- PLAUSIBLE (Tier 1) _verify_scheduler_restoration races pm2 respawn → FIXED:
  readiness is polled FIRST (up to _wait_json's budget), THEN pm2 confirms online
  — a "restarting" snapshot no longer produces a false FAIL.
- HIGH (Tier 2) NODE_OPTIONS/preload inheritance can fabricate a 401 without
  central auth → FIXED (TDD): _write_browser_environment scrubs NODE_OPTIONS +
  NODE_REPL_EXTERNAL_MODULE from the child env; test + artifact pin.
- HIGH (Tier 2) capture accepts a mis-scoped/duplicate cookie → FIXED:
  contextRefreshCookie requires EXACTLY one applicable smart_cms_refresh cookie
  (refresh_cookie_ambiguous otherwise); node tests for single/duplicate/none.
- HIGH (Tier 2) already-revoked-before-capture passes as logout-proof → PARTIAL
  FIX + DEFER: the ambiguity half is closed above; the deep causality residual
  (prove logout CAUSED revocation, ruling out pre-revocation) needs auth-registry
  introspection or an auth-service logout that distinguishes already-inactive —
  both out of #160 scope / DNT (auth service). In the normal drill the captured
  cookie is the live current token (rotation updates the cookie), so the
  counterexample is not reachable by the drill flow; recorded honestly as a
  residual for future auth work.
- CONFIRMED cleanup (#8) strict-status only on 401 fields → FIXED: generalized
  _is_strict_status/_is_strict_status_in applied across the whole validator
  (float 403.0/502.0/201.0/409.0 lookalikes now rejected; RED test).
- CONFIRMED cleanup (#9) runbook "corroboration only" contradicts a hard-failing
  direct-auth probe → FIXED (both probes enforced); restore/interrupt paragraph
  made coherent with the new semantics.
- CONFIRMED cleanup (#7) divergent twin restoration guards → DEFERRED: filed
  issue #163 (unify go-read + write-ui guards); bodies legitimately differ, a
  refactor best done as its own change (write-ui guard now correct + test-locked).
- Cleanup (#10) double readiness wait → ACCEPTED/noted: verify owns the
  authoritative readiness poll; _restore_scheduler's wait is now cheap
  belt-and-suspenders (~instant when healthy).
- MEDIUM vacuous-at-wiring notes → strengthened where cheap: contextRefreshCookie
  wired through its real export (ambiguity/shape tests hit the real fn); new
  Function round-trip test rebuilds BOTH sources out of module scope; off-path
  clone-gate asserts clone is never called; the deep probe-integration
  (real fetch URL/body/signal) and full _run_write_browser→main end-to-end stay
  covered at the real stage run (accepted R2 pattern).
Gates after round-2 fixes: pytest 313 ×3, node 26 ×3, ruff F clean, node --check OK.

### Round 3 launched (merged-artifact framing) — both tiers on remediated tree

### Round 3 — Tier 2 (codex gpt-5.6-sol xhigh, merged-artifact) result
2 new MEDIUM, both FIXED (TDD); no above-LOW incoherence; reviewer verified all
nine normal SystemExit paths, Exception manifests, restoration authority,
combined-code, and the success-path scheduler_restoration shape checked out.
- MEDIUM _reject_passive_contradiction still used == for the 6 panel/observed
  status fields (my strict-status generalization missed this helper) → FIXED:
  now _is_strict_status for panel_roster/panel_active/observed; 6-field
  parameterized RED test (403.0/502.0 lookalikes rejected).
- MEDIUM LOCAL-RTA-1 _stop_runtime() ran BEFORE the manifest write in the
  widened BaseException handler; a pm2 shutdown TimeoutExpired would mask the
  interrupt and suppress the manifest → FIXED: teardown contained (try/except),
  so the manifest is written and the interrupt propagates; RED test
  (teardown TimeoutExpired + KeyboardInterrupt → manifest present, interrupt
  re-raised).
Gates after fixes: pytest 320, node 26, ruff F clean.

### Round 3 — Tier 1 (workflow wf_ad6a0ba0-488, 20 agents) result — the SIMPLIFICATION round
Verdict: my round-2 interrupt handling was over-engineered and created worse
evidence-integrity problems than it solved. The right fix was to SIMPLIFY back
toward the codebase's original correct behavior. 10 findings, dispositions:
- CONFIRMED main() BaseException widening stamps a FAIL manifest even after a
  stage wrote its PASS manifest → permanent PASS+FAIL contradiction → FIXED by
  REVERTING main() to `except Exception`: an operator interrupt propagates with
  standard semantics and writes NO manifest (the pre-widening baseline the
  reviewer identifies as correct). New test: interrupt propagates, no manifest.
- CONFIRMED failure-path interrupt containment hardcoded {attempts:0,
  restored:false} → misstated real pm2 activity → FIXED by removing the
  containment gymnastics entirely.
- CONFIRMED failure-path containment consumed Ctrl-C into minutes of teardown →
  FIXED: _run_write_browser now `except Exception` (real failures: restore +
  attach + name-both) + `except BaseException` (interrupt: bounded best-effort
  single restore, contained, propagate — no report, no manifest).
- CONFIRMED runbook contradicted code both directions → REWRITTEN to the
  simplified reality (Exception→manifest+restore+report; interrupt→best-effort
  restore, propagate, no manifest).
- CONFIRMED proveContextLogout discarded the capture (root) diagnosis when logout
  ALSO threw → FIXED: capture error wins over a logout transport error; node test.
- CONFIRMED (cleanup) verify readiness-first-then-pm2 order asserted nowhere
  (separate lists) → FIXED: single ordered event list; mutation-verified (swap
  order → test fails).
- CONFIRMED (cleanup) interrupt restoration attachment unpinned → MOOT after the
  simplification (interrupts attach nothing / write no manifest); the
  Exception-path attachment stays pinned by the failure-path test.
- PLAUSIBLE strict-401 refresh oracle runs inside the outage window → REJECTED
  with reason: the probe targets CENTRAL AUTH (127.0.0.1:3005), which the
  scheduler outage (`pm2 stop scheduler`) does not affect; and AbortSignal.timeout
  makes a degraded auth fail LOUDLY (transport throw → subprocess fail), not a
  silently-recorded non-401. Logout must be last (after outage probes need the
  live operator session), so the ordering is structural.
- CONFIRMED (cleanup) named JS diagnostic codes never reached the manifest
  (collapsed to write_browser_failed) → FIXED: the browser now prints a clean
  code token (code-shaped err.message surfaces directly; else the checkpoint
  code) with the human detail on a separate non-extracted line; Python tests pin
  the extraction contract.
- CONFIRMED (cleanup) 3 tests hardcoded /tmp/does-not-matter → FIXED (tmp_path).
Gates after round-3 fixes: pytest 321 ×3, node 27 ×3, ruff F clean, node --check.
Net: the diff is now SMALLER and simpler than after round 2 — the interrupt
machinery is gone, replaced by the codebase's original propagate-and-best-effort
-restore behavior, with the genuine #160 HIGH-2 fix (bounded guarded restore +
authoritative independent verify) intact.

### Round 4 launched (fresh contract-correctness on the simplified tree) — both tiers

### Round 4 results (fresh contract on simplified tree) — Tier 1 wf_4b191352-68f (15 agents) + Tier 2 (q160-4)
6 findings; 3 CONFIRMED were regressions from my OWN round-3 fixes (the review
loop catching my simplification's rough edges):
- CONFIRMED second operator context never logged out when the primary's proof
  throws → leaked session → FIXED (TDD): new proveBothOperatorLogouts helper runs
  BOTH proofs (both logout POSTs fire) then surfaces the first error; node test
  pins both-logouts-on-first-failure.
- CONFIRMED browser failure-code promoted a non-Error throw to a bogus
  "undefined" gate → FIXED: browserFailureCode guards typeof message==="string".
- CONFIRMED hyphenated checkpoint fallback (browser_create-submission_failed)
  rejected by the extractor's [a-z0-9_] grammar → collapsed to generic → FIXED:
  browserFailureCode underscores non-alnum; node test asserts every checkpoint
  code satisfies the Python grammar. (Both #9-round-3 and these are now one
  extracted, tested browserFailureCode helper — no second copy.)
- PLAUSIBLE main() swallowed _stop_runtime() teardown failure → orphaned
  processes, no signal → FIXED (TDD): the teardown error is CONTAINED (still
  can't mask the primary) AND recorded as manifest `teardown_error`; RED test.
- PLAUSIBLE NODE_OPTIONS wholesale strip drops benign flags → REJECTED with
  reasoning + comment: evidence-integrity harness fails closed on the injection
  vector; the launcher needs no inherited NODE_OPTIONS (sets NODE_PATH/
  PLAYWRIGHT_BROWSERS_PATH explicitly); any legitimate flag must be set
  explicitly, not inherited.
- CONFIRMED (cleanup) duplicated unexpected_<Type> fallback → FIXED: main() now
  uses _safe_error_code (single definition).
Also pre-emptively fixed a stale _restore_scheduler_guarded docstring the round-3
revert left referencing the removed manifest-then-propagate path.
Gates after round-4 fixes: pytest 322, node 29, ruff F clean, node --check OK.

### Round 5 launched (merged-artifact confirmation) — both tiers

### Round 5 results (confirmation) — Tier 2 codex CLEAN + Tier 1 wf_e945a7d4-fa3 (8 agents, 1 finding)
Tier 2: no new defects above LOW (both operator proofs run w/ correct error
precedence; field-team logout attempted after capture failure; all checkpoint
names → extractor-valid codes; teardown_error/restoration independent; no vacuous
test). Tier 1: 1 PLAUSIBLE, FIXED (matters because item 3 RUNS this harness):
- _verify_scheduler_restoration rejected unless EVERY pm2 'scheduler' entry was
  online, so a stale stopped duplicate would false-FAIL a healthy success-path
  stage → FIXED (TDD): now requires AT LEAST ONE online 'scheduler' entry
  (readiness already proves serving); single-stopped still rejects
  (mutation-verified), online passes, stale-duplicate-beside-online passes.
Tier 1 also REFUTED its own field-team-precondition candidate (the seeded
field_team context does carry the smart_cms_refresh cookie).
Gates after round-5 fix: pytest 323 ×3, node 29 ×3, ruff F clean, node --check OK.

### Round 6 launched (final dry-check on the tolerance fix) — both tiers

### Round 6 — DRY (both tiers)
Tier 1 (wf_37bf31e0-df7, 4 finders): ZERO candidates. Tier 2 (codex xhigh): [].
Loop-until-dry satisfied: a full both-tier round surfaced nothing above LOW.

## Final summary (Phase 8)
- Stop line: NONE (Q0 — auth-evidence/claim trust; acceptance trust anchor). 100%
  Claude-authored; no delegate.
- Scope delivered (#160): per-context own-cookie logout-revocation proof;
  bounded guarded scheduler restoration with an authoritative independent verify;
  fail-closed read-settle. Plus the review-driven hardening: NODE_OPTIONS scrub,
  cookie-ambiguity refusal, strict-status generalization, coherent + SIMPLE
  operator-interrupt semantics (interrupts propagate, best-effort restore, no
  manifest — reverted from the round-2 over-engineering), both-operator-logout
  guarantee, extractor-valid browser failure codes, teardown-error recording,
  stale-duplicate-tolerant pm2 verify.
- QCHECK: 6 both-tier rounds (contract → adversarial → merged-artifact →
  fresh-eyes → confirmation → dry). Reviewers independent of the Claude
  implementer (Tier 1 /code-review high multi-agent; Tier 2 codex gpt-5.6-sol
  xhigh). ~40 findings across rounds; ALL CRITICAL/HIGH fixed; the notable arc:
  round 2 both tiers found round-1 fixes had MOVED holes; round 3 found round-2's
  interrupt machinery was over-engineered → REVERTED to the codebase's original,
  shrinking the diff; round 4 caught 3 regressions from that revert; rounds 5-6
  converged to dry. Every finding dispositioned with file:line or design/source
  citation; deferrals filed as #162 (sanitizer), #163 (guard unification).
- TDD: every behaviour RED-proven; boundary pins mutation-verified
  (\d→[0-9], > →>=, prefix comparison, verify-order swap, online-required guard).
- Final gates (exact tree): pytest 323 ×3, node 29 ×3 (disposable-free unit
  level), ruff --select F clean, node --check clean, workflow YAML parses.
- Local vs hosted evidence SEPARATED (E6 billing lock; recorded on the PR).
