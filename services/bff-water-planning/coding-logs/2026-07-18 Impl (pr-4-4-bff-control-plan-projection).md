# PR 4.4 — BFF read-only control-plan projection (impl log)

**Date:** 2026-07-18 · **Base:** main `a8896e08` (post-4.3b) · **Branch:** `feat/bff-control-plan-projection`
**Service:** `services/bff-water-planning` only. Plan of record: `coding-logs/2026-07-18 Plan (pr-4-4-...).md`.

## What shipped
Four authenticated, READ-ONLY operator projections over the scheduler's two control-plan GET routes:
- `GET /api/v1/control-plans/{plan_id}/versions/{plan_version}` → full plan detail mirror
- `.../prediction-coverage` → lineage + exact per-member prediction statuses (subset of detail)
- `.../ledger` → full ledger mirror (min/max member bounds preserved, incl. nulls)
- `.../lifecycle-history` → identity + derived lifecycle_state + complete ordered transitions

Strict validated pass-through (`extra="forbid"`, snake_case mirror of the scheduler OUT schemas).
No new status vocabulary, no success booleans, no fabricated delivery numbers. No writes, no list route
(upstream has none), no scheduler/BFF-DB change.

## Files
- **New** `src/schemas/control_plan.py` — strict mirrors (`ControlPlanProjection`, `ControlPlanLedgerProjection`,
  `ControlPlanPredictionCoverage`, `ControlPlanLifecycleHistory` + sub-models). Nullable-but-required fields
  stay required so a dropped field 502s; only `transition_document` is optional (scheduler defaults it).
- **New** `src/api/routes/control_plans.py` — bearer-gated router (`HTTPBearer(auto_error=True)`), 4 GET handlers,
  `get_scheduler_client()`/`get_operator_bearer_token()` DI, `_raise_for_client_error` taxonomy, shared
  `_load_control_plan_projection`/`_load_control_plan_ledger` (client-error→HTTP + strict validation, drift→502).
- **New** `pytest.ini` — `testpaths=tests`, `asyncio_mode=strict` (bare pytest is the gate; root integration
  scripts never collected).
- **New** `tests/unit/test_control_plan_projection.py` — 29 tests (client MockTransport + route DI-override).
- **Modified** `src/clients/scheduler_client.py` — typed fail-closed errors + injectable `transport` +
  `_get_control_plan_document`/`get_control_plan_projection`/`get_control_plan_ledger` (legacy schedule methods
  untouched); removed a pre-existing unused `datetime` import.
- **Modified** `src/clients/__init__.py` — export the 6 new error types.
- **Modified** `src/main.py` — mount `control_plans.router` in the inline REST import block.
- **Modified** `CLAUDE.md` — document the projection surface, error taxonomy, bearer forwarding, no-cache/no-list.

## Error taxonomy (fail-closed; never swallows unlike legacy schedule methods)
200 object→validate→200 · 200 malformed/non-object→502 · 401/403→same status+detail · 404→404+detail ·
503→503+detail · transport/connect→503 (generic) · other 4xx/5xx→502 · schema drift (missing/renamed/retyped
or extra field)→502 · invalid BFF plan_version (≤0)→422 (no scheduler call).

## State preservation (verified by tests)
unavailable → 503, no fabricated coverage body (`test_bff_preserves_unavailable_prediction_status`);
infeasible → optimizer/prediction/member statuses preserved, never coerced to completed;
invalidated → lifecycle_state + invalidation transition/reason/document + `invalidated` ledger row preserved;
stale → `requirements[].source_data_status == "stale"` preserved exactly (snapshot-time source status).

## Gate
`pytest` (bare, via new pytest.ini): **65 passed** ×3 consecutive (no flakiness). pyflakes clean on all new/edited files.
`import main` registers all 4 control-plan routes. Roadmap tests present:
`test_bff_preserves_unavailable_prediction_status`, `test_bff_plan_projection_retains_exact_lineage`.

## QCHECK
2-tier: tier1 Opus 4.8 adversarial reviewer (substitute for the Fable-5-limited workflow verify tier),
tier2 Codex gpt-5.6-sol high.

### Tier 1 — Opus 4.8 adversarial (VERDICT: safe to merge)
No CRITICAL/HIGH/MEDIUM findings. Field-by-field diff of all 15 mirrored models vs the scheduler OUT schemas =
exact (names, types, Literal sets, Optional/required). Subsets built from the VALIDATED detail model (drift 502s
first). Fail-closed taxonomy complete; uncovered statuses (3xx not followed — httpx follow_redirects=False, 204,
500, 200-null, 200-list) all → 502. Lineage round-trip verified byte-identical (hashes, frozen shadow document
incl. bool/key-order, optimizer_result -0.0, datetime Z and +07:00 offsets). Token never logged/cached; missing
bearer → 403 with no scheduler call. Only LOW test-coverage suggestions.
**Applied:** added `test_client_never_logs_the_bearer_token_on_any_error_path` (structlog.capture_logs; stated
security requirement), `test_client_raises_contract_error_on_null_200_body`, `test_bff_preserves_empty_ledger_without_fabrication`.
Suite: 32 (was 29) → full gate **68 passed**.

### Tier 2 — Codex gpt-5.6-sol high (VERDICT: not safe as-is — 2 HIGH, now FIXED)
Two HIGH findings that tier-1 missed (uncorrelated blind spots — the value of the double tier):
- **HIGH-1 identity not verified** (`control_plans.py`): loaders never checked the returned plan_id/plan_version
  match the requested path; an upstream cache/routing defect could return a valid *different* plan served as 200.
  **Fix:** `_verify_identity()` after validation in BOTH loaders → 502 on mismatch. Tests:
  `test_mismatched_plan_id_fails_closed_502`, `test_mismatched_plan_version_fails_closed_502`,
  `test_ledger_mismatched_identity_fails_closed_502`.
- **HIGH-2 `extra="forbid"` ≠ strict types** (`schemas/control_plan.py`): Pydantic lax coercion rewrote
  `plan_version:"3"`→3 and `requirement_version:true`→1, laundering drift into valid-looking lineage.
  **Fix:** strict scalar aliases `StrictInt`/`StrictNumber`/`StrictBool` (BeforeValidators rejecting bool/str-for-int,
  bool/str/non-finite-for-float, non-bool-for-bool) applied to every int/float/bool mirror field; UUID/date/datetime
  still accept JSON strings. Tests: `test_numeric_string_integer_field_fails_closed_502`,
  `test_boolean_integer_field_fails_closed_502`, `test_boolean_for_float_field_fails_closed_502`,
  `test_string_for_float_ledger_bound_fails_closed_502`.
- Codex also noted `black --check` failed → ran black on the 2 new files (control_plans.py, tests); left the
  MODIFIED legacy scheduler_client.py untouched (its black diff is pre-existing legacy-whitespace churn, out of PR scope).

Post-fix gate: **75 passed** ×3 (no flakiness), pyflakes clean, `import main` = 4 control-plan routes. Both HIGH
findings reproduced-then-locked by regression tests (fail without fix). Ready to land.
