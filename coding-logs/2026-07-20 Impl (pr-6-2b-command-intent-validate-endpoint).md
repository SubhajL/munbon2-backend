# PR 6.2b — command-intent validate endpoint + durable receipts (impl log)

Branch `feat/pr-6-2b-command-intent-validate-endpoint` off `758daaac` (6.2a merged #93).
Second half of PR 6.2: the HTTP endpoint + durable persistence on top of the 6.2a validation
core. Completes PR 6.2 (SCADA validation-only machine boundary).

## Shipped (`services/scada-gate-control`)
- `command-intents/{types,memory-repository,pg-repository}.ts` — durable `scada_command_intents`
  receipt store. `ensureSchema()` DDL (no migration runner in this TS service — the audit repo's
  pattern), status/reason-code CHECKs **built from the frozen 6.0 enum tuples** (can't drift),
  `(status='validation_rejected') = (reason_code IS NOT NULL)` CHECK. Idempotency via
  `idempotency_key` PK + `INSERT … ON CONFLICT DO NOTHING RETURNING` with a re-SELECT on race
  (first writer wins; both callers observe the winner).
- `api/service-auth.ts` — `requireServiceAuth` middleware (null verifier → 503 fail-closed).
- `api/internal-routes.ts` — `POST /internal/v1/command-intents/validate`: service-auth (gates
  BEFORE body parsing) → Ajv (schema_invalid → 422, no receipt) → intentContentHash → idempotency
  lookup (replay 200 / conflict 409, ephemeral, never mutates the stored row) → validateCommandIntent
  → buildValidationReceipt → insertIfAbsent (race-safe) → 200. Holds NO actuator/transport (no Modbus
  path by construction). Ajv compiled once at router build.
- `api/server.ts` — per-router body parsers (/api 2kb inside buildRouter, validate route 8kb; global
  parser removed); error handler honors ONLY body-parser 4xx (`type` present, 400-499) → else 500,
  and logs both 5xx (error) and 4xx (warn) — the /api routes now surface malformed/oversized bodies
  as 400/413 instead of a blanket 500.
- `api/routes.ts` — `ApiDeps` gains `serviceVerifier | null`, `receipts`, `clock`.
- `api/middleware.ts` — shared `extractBearerToken` (used by requireAuth + requireServiceAuth).
- `index.ts` — audit + receipts share one pg pool (`pool.on('error')` so a DB blip logs-and-degrades
  instead of crashing the Modbus/gate-control process); parallel `ensureSchema`; service verifier from
  `config.serviceAuth` (null → dark 503 + warn); injected clock.

## Quality gates
typecheck ✓ · lint ✓ · `npm test` 303 passed + 4 skipped ×3 (no flakiness) · build ✓. The 4 pg
integration tests (env-gated `SCADA_TEST_POSTGRES_URL`) passed on a DISPOSABLE loopback
`postgres:14` (`:55441`, torn down): fresh insert, first-writer-wins, a concurrent race collapsing
to exactly one row, and the CHECK constraint — re-verified after the tuple-derived DDL change.
Named tests all green: `test_validate_route_cannot_reach_actuator` (zero writes across every request
kind + a `@ts-expect-error` compile-time deps-shape guard), `test_duplicate_intent_returns_prior_receipt`,
`test_same_key_different_payload_rejects_conflict`, `test_wrong_audience_or_expired_service_token_rejects`.

## 2-tier QCHECK (Codex out of tokens → tier-2 = Opus 4.8 adversarial, per /goal)
Tier-1 `/code-review high` (16 agents, 0 errors) + tier-2 Opus both ran; **no CRITICAL/HIGH**. Opus
independently stress-tested the ON CONFLICT + re-SELECT SQL at 40 rounds × 24 concurrent inserts
(one winner, one row, all losers see the winner). Fixed:
- **Both tiers (M2 / tier-1 #1):** the body parser ran BEFORE service auth, so an unauthenticated /
  dark-endpoint request with a malformed body returned 400 instead of 401/503 — reordered auth-first;
  regression tests added (malformed+no-token → 401, malformed+dark → 503).
- **Both tiers (M1/L1 + tier-1 #2/#3):** shared pg pool had no `'error'` listener (a DB blip would
  crash the whole process incl. the Modbus loop) → added a logging listener; the error handler
  trusted any sub-500 status and stopped logging 4xx → now honors only body-parser 4xx and logs
  client errors at warn.
- **Tier-2 M3:** DB errors were swallowed by bare `catch {}` → now logged before the 503.
- **Tier-1 #4/#5/#6 (cleanup):** Ajv validator hoisted to router-build; shared `extractBearerToken`
  kills the duplicated Bearer parse; the two independent startup DDLs run via `Promise.all`.
- **Tier-2 L3:** the SQL CHECK enum lists are derived from the TS enum tuples (no hand-copy drift).
- **Refuted/deferred:** test-fixture duplication between specs (acceptable); an architecture-lint
  forbidding transport imports under `api/internal-routes.ts` and back-porting the blank-`sub` trim
  to operator `auth.ts` (documented follow-ups, out of this slice).
