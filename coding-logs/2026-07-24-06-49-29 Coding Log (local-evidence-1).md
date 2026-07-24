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

## Design boundary

The three present projections and held/unavailable evidence come from real
append-only rows in the disposable local PostgreSQL database and are read
through the authenticated BFF-to-Scheduler path. Missing-plan evidence also
uses the real path. Only the intentionally malformed response is scoped browser
interception, proving frontend decoder isolation without pretending the
producer emitted malformed data. The Gate Operations href is inspected exactly
but never navigated, so its request inventory remains zero.
