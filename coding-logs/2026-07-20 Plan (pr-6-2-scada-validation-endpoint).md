# PR 6.2 — SCADA validation-only command-intent endpoint + Scheduler service auth

**Status:** Claude plan (pre-synthesis). Second-opinion plan (Opus, substituting for out-of-tokens
Codex) pending; synthesis deltas appended below when it returns.
Deps: PR 6.0 (machine-boundary schemas) ✅, PR 6.1a (SCADA device registry) ✅.
Service: `services/scada-gate-control` (TS 5.3 strict / Express 4 / Node ≥18 / vitest / pg).

## Overview
Give SCADA a durable, authenticated, **validation-only** machine boundary: the scheduler (in a
later PR, 6.3) POSTs a 6.0 `CommandIntent` and gets back a 6.0 `ValidationReceipt`, with **zero
Modbus writes** by construction. Validation is standalone (SCADA has no plan DB): schema (embedded
6.0 Ajv), capability (against the loaded 6.1a snapshot), quantizer-target membership, and
command-window timing. Receipts are content-addressed and idempotent — the same intent replays the
prior receipt; the same idempotency_key with a different body is a conflict. Service-to-service auth
is a cryptographically separate, audience-pinned, short-lived HS256 token.

## Split (PR-by-PR, each with full lifecycle + 2-tier QCHECK)
- **6.2a — foundations (pure, zero I/O):** embedded command-intent v1 schema + drift-guard; pure
  `validateCommandIntent` + `commandIntentContentHash` (+ cross-language golden vector);
  `SchedulerServiceTokenVerifier` / `verifySchedulerServiceToken`. Unit-tested only; no route, no DB.
- **6.2b — endpoint + durable receipts:** `scada_command_intents` receipt repository (pg
  `ensureSchema` + in-memory), `POST /internal/v1/command-intents/validate`, config/index/server
  wiring, and the integration tests (no-Modbus, idempotent replay, conflict, strict service auth).
Seam rationale: 6.2a is I/O-free and fully unit-testable; 6.2b adds persistence + HTTP + wiring.
Mirrors the established "split at the I/O boundary" pattern (4.4a-1/-2/-3, 4.3c-1/-2).

## Reason-code semantics (validation-only, no plan DB) — DECISION
Frozen 6.0 enum: {schema_invalid, capability_mismatch, target_invalid, not_before_violation,
deadline_expired, lineage_mismatch, freshness_failed, idempotency_conflict}. 6.2 emits the subset it
can enforce **standalone**; evaluated in order, first failure wins:
1. `schema_invalid` — embedded command-intent v1 Ajv rejects the body (bad pattern, additional
   property, close/open target invariant, non-UTC instant, …).
2. `idempotency_conflict` — the idempotency_key already has a receipt whose stored
   `intent_content_hash` ≠ this body's hash (checked before capability/target so a replay never
   re-runs validation). Ephemeral (never persisted; the durable first receipt is unchanged).
3. `capability_mismatch` — `capability_release_id` or `capability_hash` ≠ the loaded snapshot's;
   or `canonical_gate_id` is not a key in the snapshot; or `device_id`/`adapter_gate_id` ≠ the
   snapshot's binding for that gate.
4. `target_invalid` — `(target_position_m, target_level)` is not an EXACT member of that device's
   `targets[]` (quantizer membership).
5. `freshness_failed` — window ordering invariant `not_before < deadline` violated
   (`not_before >= deadline` → malformed/empty window; the intent carries no fresh actionable span).
   The JSON schema cannot express this cross-field invariant.
6. `not_before_violation` — `now < not_before` (premature: the actionable window has not opened;
   fail-closed against a mis-timed dispatch — SCADA will not pre-bless a future command).
7. `deadline_expired` — `now > deadline` (the window has closed).
- `lineage_mismatch` — **RESERVED, NOT emitted in 6.2.** The frozen 6.0 schema fully validates
  lineage STRUCTURE (all 15 fields, `prediction_identity_version` const 2), and SCADA holds no
  external lineage anchor to compare against until **PR 6.1b** (approved-artifact registry). Adding
  a lineage_mismatch trigger now would be unreachable dead code. Documented explicitly; 6.1b extends
  `validateCommandIntent` to compare lineage against the approved artifact. (Open for review: the
  freshness_failed↔not_before_violation naming split — a one-line swap if the reviewer disagrees.)

## Idempotency × durability × time — DECISION
- `intent_content_hash = sha256(JCS(intent))` using the npm `canonicalize` lib — **byte-reproduces**
  the scheduler's `command_intent_content_hash` (verified golden `3ef5a28c…2804216`; NO domain
  prefix, hashes the full intent). Because the outbox persists a fixed `request_id` per intent, a
  dispatcher retry resends the byte-identical intent → same hash → idempotent replay.
- Validation is evaluated **once**, at first receipt, against the injected clock; the receipt is
  durable and returned verbatim on every replay (even if re-validating "now" would differ). The
  dispatcher contract (6.3) only sends DUE intents within `[not_before, deadline]`, so first
  validation is in-window → accepted → durable. A genuinely expired/premature intent is durably,
  fail-closed rejected — correct and safe. Documented.
- **Persist accepted AND rejected first-time receipts** keyed by idempotency_key (durable decision
  record). idempotency_conflict is the only ephemeral outcome (the key is already owned).
- **INSERT race** (two concurrent first-time requests, same new key): atomic
  `INSERT … ON CONFLICT (idempotency_key) DO NOTHING RETURNING *`; if no row returned, re-`SELECT`
  the winner and apply the replay/conflict rule against ITS stored hash. No lost updates, no
  duplicate rows (idempotency_key is UNIQUE + the immutable-by-convention table).

### `scada_command_intents` table (repository-owned `ensureSchema`, matching `PostgresAuditRepository`)
The service has no migration runner; the audit repo's `ensureSchema()` (CREATE TABLE IF NOT EXISTS)
is the established durable-schema pattern. "Migration-owned" is honored by a single idempotent DDL
owned by the repository and run once at startup. Columns:
`idempotency_key TEXT PRIMARY KEY`, `intent_id UUID NOT NULL`, `correlation_id UUID NOT NULL`,
`request_id TEXT NOT NULL`, `intent_content_hash CHAR(64) NOT NULL`, `capability_hash CHAR(64) NOT NULL`,
`receipt_id UUID NOT NULL`, `status TEXT NOT NULL CHECK (status IN ('validation_accepted','validation_rejected'))`,
`reason_code TEXT NULL CHECK (reason_code IS NULL OR reason_code IN (<8 codes>))`,
`validated_at TIMESTAMPTZ NOT NULL`, `receipt_document_text TEXT NOT NULL` (the exact canonical
receipt JSON → byte-identical replay), `intent_document_text TEXT NOT NULL` (received intent, for
conflict forensics/audit), `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
CHECK: accepted ⇒ reason_code NULL; rejected ⇒ reason_code NOT NULL (mirrors the receipt schema).

## Service auth — DECISION
Dedicated, cryptographically separate HS256 secret (NOT the operator `JWT_SECRET`). Env (all read in
`config.ts`): `SCHEDULER_SERVICE_JWT_SECRET` (no default), `SCHEDULER_SERVICE_JWT_ISSUER`
(default `munbon-scheduler`), `SCHEDULER_SERVICE_JWT_AUDIENCE` (default `munbon-scada-command-validation`),
`SCHEDULER_SERVICE_JWT_MAX_AGE` (default `5m`). `verifySchedulerServiceToken` pins: HS256 only,
issuer, audience, `type === 'service'` (discriminator distinct from operator `type:'access'`), a
non-empty `sub`, and `maxAge`. Fail-closed: if `SCHEDULER_SERVICE_JWT_SECRET` is unset, the validate
route responds **503** (service auth not configured — never validate without service auth) and logs a
startup warning; the rest of SCADA still boots. This keeps a leaked operator secret from forging
service tokens and vice-versa, and makes the internal command surface dark until explicitly keyed.

## HTTP status mapping
- **200** — a receipt was formed (validation_accepted OR validation_rejected on
  capability/target/window grounds); idempotent replay returns the stored receipt (with its status).
- **409** — idempotency_conflict (rejected receipt, reason=idempotency_conflict; ephemeral).
- **422** — schema_invalid (rejected receipt echoing valid identity fields; ephemeral, not persisted).
- **400** — unparseable/oversized JSON, or identity fields so malformed a receipt can't be formed.
- **401** — service-token invalid/expired/wrong-audience/wrong-type.
- **503** — service auth unconfigured, or DB/internal error ("transport/internal errors are service
  failures, not receipts").
Every emitted receipt is self-checked against the embedded validation-receipt v1 schema before send.

## No-Modbus guarantee (by construction + proven)
The validate route's deps are `{ serviceVerifier, deviceCapabilities, receipts, clock }` ONLY — it
holds no `CommandService`, `GateController`, or transport reference, so it structurally cannot write
Modbus. `test_validate_route_cannot_reach_actuator` builds the FULL app with a transport/actuator
write-spy, POSTs a valid accepted intent, and asserts (a) accepted receipt returned, (b) receipt is
durably stored, (c) the write-spy was never called.

## Files to change
### 6.2a
- `src/domain/command-intent.schema.ts` (NEW) — embedded command-intent v1 JSON Schema (`as const`),
  mirror of `contracts/machine-boundary/v1/command-intent.schema.json` (dist ships no `contracts/`).
- `src/domain/command-intent.schema.spec.ts` (NEW) — drift-guard: deep-equals the on-disk contract.
- `src/domain/validation-receipt.schema.ts` (NEW) — embedded validation-receipt v1 schema (for the
  emit-time self-check) + `.spec.ts` drift-guard.
- `src/domain/command-intent-validation.ts` (NEW) — pure: `commandIntentContentHash(intent)`;
  `validateCommandIntent(intent, snapshot, nowMs) → { status, reason_code }` (capability/target/
  window checks); `buildValidationReceipt(...)`; Ajv validator factory over the embedded schema.
- `src/domain/command-intent-validation.spec.ts` (NEW) — unit tests incl. the golden hash vector.
- `src/api/service-auth.ts` (NEW) — `SchedulerServiceTokenVerifier` + `verifySchedulerServiceToken`,
  `ServiceAuthError`, `ServiceCaller` type; `.spec.ts`.
### 6.2b
- `src/receipts/types.ts` (NEW) — `ValidationReceiptRecord`, `CommandIntentReceiptRepository`
  (`getByIdempotencyKey`, `record` → `{ outcome: 'stored'|'existing', record }` for race handling).
- `src/receipts/pg-repository.ts` (NEW) — Postgres impl + `ensureSchema()` (the DDL above).
- `src/receipts/memory-repository.ts` (NEW) — in-memory impl (same atomic-first-writer semantics).
- `src/receipts/*.spec.ts` (NEW).
- `src/api/command-intent-routes.ts` (NEW) OR extend `internal-routes.ts` — the POST validate route +
  its own `express.json({ limit: '8kb' })`. (Decision: extend `buildInternalRouter` to keep /internal
  cohesive; it gains `serviceVerifier`, `receipts`, `clock` deps.)
- `src/api/server.ts` (EDIT) — remove the global 2kb json parser; scope parsers per router (/api keeps
  2kb inside `buildRouter`; the validate route gets 8kb). Preserves existing /api behavior exactly.
- `src/api/routes.ts` (EDIT) — `router.use(express.json({ limit: '2kb' }))`; extend `ApiDeps`.
- `src/config.ts` (EDIT) — add `serviceAuth` block.
- `src/index.ts` (EDIT) — build the receipt repo from the shared pg pool (reuse the audit pool),
  build `SchedulerServiceTokenVerifier` when the secret is set, pass `clock`, wire the deps.
- `services/scada-gate-control/package.json` (EDIT) — move `ajv` + `ajv-formats` from
  devDependencies to dependencies (device-registry imports them at RUNTIME today — latent 6.1a
  packaging bug that a `--production` install would break; 6.2 doubles down on runtime Ajv).
- `services/scada-gate-control/CLAUDE.md` (EDIT) — document the new internal endpoint + envs.

## Wiring verification
| Component | Entry point (runtime caller) | Registration | Schema/table |
|---|---|---|---|
| `command-intent.schema.ts` | Ajv compile in `command-intent-validation.ts` | import | N/A (drift-guarded vs contracts/) |
| `validateCommandIntent` | validate route handler | called in `buildInternalRouter` POST handler | reads loaded snapshot |
| `verifySchedulerServiceToken` | validate route handler (before body) | `buildInternalRouter` | N/A |
| `PostgresCommandIntentReceiptRepository` | `recordValidationReceipt`/`getByIdempotencyKey` in route | built in `index.ts` from pool; `ensureSchema()` at startup | `scada_command_intents` |
| `POST /internal/v1/command-intents/validate` | scheduler dispatcher (6.3) | `buildInternalRouter` mounted at `/internal` in `server.ts` | receipt table |
| service-auth config | `loadConfig()` | `index.ts` builds verifier when secret set | N/A |

## Test coverage (named + additional)
6.2a: `commandIntentContentHash` matches golden `3ef5a28c…` (cross-lang parity) · content hash is
stable across key-order-permuted input · embedded schema equals on-disk contract (drift) · each
reason code fires on its trigger and no other · accepted intent yields reason_code null · service
verifier: valid service token → caller; `test_wrong_audience_or_expired_service_token_rejects`
(wrong audience, expired, wrong type, wrong secret each → ServiceAuthError).
6.2b: `test_validate_route_cannot_reach_actuator` (no-write + durable accepted) ·
`test_duplicate_intent_returns_prior_receipt` (byte-identical replay → same receipt, one row) ·
`test_same_key_different_payload_rejects_conflict` (409 idempotency_conflict, stored row unchanged) ·
capability/target/window rejections each persist a rejected receipt + replay it · concurrent
first-time INSERT race → single row, both callers see the same receipt · 503 when service secret
unset · repository `ensureSchema` idempotent (run twice).

## Quality gate (each sub-PR, from the service dir)
`npm run typecheck && npm run lint && npm test` (vitest). Postgres repo tests: prefer an env-gated
DISPOSABLE loopback container (never the user's real DB); the memory repo covers logic in bare CI.

## Risks / rollback
- Cross-language hash drift → locked by the golden vector + the drift-guard specs.
- Body-parser rewrite could change /api behavior → server.spec.ts (no limit test) must stay green;
  /api keeps its exact 2kb cap.
- `ajv` dep move is additive; revert = move back. All new files are additive; route is dark until
  `SCHEDULER_SERVICE_JWT_SECRET` is set → safe to ship behind the external trust cutover.

---
## Synthesis / second-opinion deltas (Opus, Codex out of tokens)
The independent plan converged on: the split, `lineage_mismatch` reserved, no-domain-prefix content
hash (golden `3ef5a28c…`, new helper — NOT reusing `computeCapabilityHash`), ajv→dependencies,
`ensureSchema` (no migration runner), dedicated service secret, `INSERT … ON CONFLICT DO NOTHING
RETURNING`, `receipt_document` TEXT for byte-identical replay, 200 for accepted AND merit-rejected,
no-Modbus-by-construction. **Deltas ADOPTED from the second opinion (they improve the plan):**
1. **Reason-code remap (better reasoned):**
   - `freshness_failed` = `intent.capability_release_id !== snapshot.capability_release_id` OR
     `intent.capability_hash !== snapshot.capability_hash` (the intent pinned a capability release
     SCADA no longer serves — stale). In the DARK default (empty snapshot) EVERY real intent fails
     here → clean, testable dark-default behavior.
   - `capability_mismatch` = gate absent from `snapshot.capabilities` OR `device_id`/`adapter_gate_id`
     disagree with the snapshot binding.
   - `target_invalid` = no snapshot target whose position matches by **canonical-number string**
     (`canonicalize(pos)`, mirroring the scheduler's `capability_member` — NOT float `==`) OR the
     matched target's `target_level` differs.
   - `not_before_violation` = window ordering `not_before_ms > deadline_ms` (inverted/empty window),
     field-only, no clock. **DROP my earlier "reject when now < not_before"** — a validation-only
     endpoint must NOT reject a legitimately future-dated shadow intent (it never acts).
   - `deadline_expired` = `deadline_ms < now` evaluated ONCE at first receipt and FROZEN (replays
     return the stored verdict; known limitation documented).
   Order: freshness → capability → target → window → deadline. Each independently test-reachable.
   (Reviewer sign-off flagged: freshness=release-pin vs telemetry-staleness is a judgment call.)
2. **`schema_invalid` → HTTP 422 with the reason in the error body and NO receipt persisted** — a
   malformed intent cannot mint a trustworthy keyable receipt; don't echo identity from an untrusted
   body. (Replaces my "422 + echoed receipt".)
3. **Compile-time no-Modbus guard:** a `@ts-expect-error` test asserting an actuator/`commandService`
   does not type-check into the machine-boundary route factory (excess-property check) — makes
   "no Modbus" a TYPE property, on top of the runtime write-spy assertion.
4. **Drop `intent_document_text` column** — the `intent_content_hash` is the sole replay/conflict
   arbiter; keep only `receipt_document`. Table CHECK: `(status='validation_rejected') = (reason_code
   IS NOT NULL)`.
5. Service audience default → `munbon-scada-machine-boundary`; `ServicePrincipal { subject }`, no role
   mapping; unconfigured secret → route still MOUNTED but every call 503 (503 ≠ 404 "route missing").
**Deltas where I keep my approach (noted):**
- **Split seam:** 6.2a = the full pure validation core (embedded command-intent + receipt schemas +
  drift-guards, `intentContentHash`, `compileCommandIntentValidator`, `validateCommandIntent`,
  `buildValidationReceipt`) **plus** service-auth; 6.2b = receipt repo + route + config/index/server
  wiring + integration tests. (The second opinion put only service-auth in 6.2a; the balanced
  pure-core/IO seam keeps both halves reviewable and each independently green. `ajv`→`dependencies`
  moves in 6.2a since the validator factory is its first correctly-placed runtime user. Landing pure
  logic one PR ahead of its caller is the established pattern — cf. 6.0 types, 4.3c-1
  `verify_activation_freeze`.)
- **Body parser:** router-scoped parsers (remove the global 2kb; `/api` keeps 2kb inside
  `buildRouter`; the validate route gets `express.json({ limit: '8kb' })`) — the minified shadow
  intent is 1647 B but max-length ids can exceed 2 kb, so the route needs its own limit; `server.spec`
  has no limit assertion, so this is safe.
**Final `scada_command_intents` columns:** `idempotency_key TEXT PRIMARY KEY`, `intent_id UUID`,
`correlation_id UUID`, `request_id TEXT`, `intent_content_hash CHAR(64)`, `capability_hash CHAR(64)`,
`receipt_id UUID`, `status TEXT CHECK(...)`, `reason_code TEXT`, `validated_at TIMESTAMPTZ`,
`receipt_document TEXT`, `created_at TIMESTAMPTZ DEFAULT now()`, `CHECK((status='validation_rejected')
= (reason_code IS NOT NULL))`. Persisted: first accepted/merit-rejected receipt. Ephemeral:
schema_invalid(422), idempotency_conflict(409), DB/internal(503).
