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

## Design boundary

The three present projections and held/unavailable evidence come from real
append-only rows in the disposable local PostgreSQL database and are read
through the authenticated BFF-to-Scheduler path. Missing-plan evidence also
uses the real path. Only the intentionally malformed response is scoped browser
interception, proving frontend decoder isolation without pretending the
producer emitted malformed data. The Gate Operations href is inspected exactly
but never navigated, so its request inventory remains zero.
