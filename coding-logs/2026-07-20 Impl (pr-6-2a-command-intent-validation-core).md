# PR 6.2a — command-intent validation core + Scheduler service auth (impl log)

Branch `feat/pr-6-2a-command-intent-validation-core` off `763924f0`. First of a 2-PR split
of PR 6.2 (SCADA validation-only machine-boundary endpoint). 6.2a = the pure, I/O-free
validation core + the service-token verifier; 6.2b wires them into `POST
/internal/v1/command-intents/validate` + the durable `scada_command_intents` receipt table.
Plan: `coding-logs/2026-07-20 Plan (pr-6-2-scada-validation-endpoint).md`.

## Shipped (`services/scada-gate-control`)
- `domain/command-intent.schema.ts` + `validation-receipt.schema.ts` — the 6.0 JSON Schemas
  EMBEDDED as TS consts (dist deploy ships no repo-root `contracts/`), each drift-guarded
  (`toEqual`) against the on-disk source of truth.
- `domain/intent-content-hash.ts` — `intentContentHash = sha256(JCS(intent))`, NO domain
  prefix. Byte-reproduces the scheduler's Python `command_intent_content_hash`; three golden
  cross-language vectors pinned (shadow `3ef5a28c…`, close `27640179…`, operator-approved
  `04d65b76…`), each recomputed from `core.canonical_json.canonicalize` on the Python side.
- `domain/command-intent-validation.ts` — pure `validateCommandIntent(intent, snapshot, now)`
  (freshness → capability → target → window → deadline), `compileCommandIntentValidator`,
  `buildValidationReceipt` (self-checks every emitted receipt against the receipt schema),
  `formatUtcInstant`, and strict `parseUtcInstant`. Reason codes: freshness_failed = stale
  capability release/hash pin; capability_mismatch = absent gate or device/adapter mismatch
  (own-property lookup, prototype-pollution safe); target_invalid = position not an exact member
  (canonical-number-string compare, mirroring the scheduler's `capability_member`) or level
  mismatch; not_before_violation = malformed/inverted window; deadline_expired = now > deadline
  (frozen once). `lineage_mismatch` RESERVED for 6.1b (no dead code).
- `api/service-auth.ts` — `verifySchedulerServiceToken` / `SchedulerServiceTokenVerifier`:
  dedicated HS256 secret (separate from operator `JWT_SECRET`), audience-pinned,
  `type:'service'`, non-blank `sub`, present `exp`, `maxAge` (blank → 5m, fail closed).
- `config.ts` — `serviceAuth` block (reuses `SchedulerServiceTokenConfig`; `null` when the
  dedicated secret is unset → 6.2b endpoint fails closed 503; malformed `maxAge` → ConfigError).
- `domain/canonical-hash.ts` (`sha256OfCanonicalJson`) + `domain/machine-boundary-ajv.ts`
  (`newMachineBoundaryAjv`) — shared primitives; `capability-hash.ts`, `intent-content-hash.ts`,
  `device-registry.ts`, and the two validators all delegate (no forked implementations).
- `package.json` — `ajv`/`ajv-formats` moved to `dependencies` (they are runtime imports; fixes
  a latent 6.1a `npm ci --omit=dev` boot crash). Guarded by `runtime-deps.spec.ts`.

## Quality gates
typecheck ✓ · lint ✓ · `npm test` 287 passed ×3 (no flakiness) · build ✓ · capability golden
`dc4f089d…` unchanged after the shared-helper refactor (device-registry 13 + capability-hash 12
still green). Public API is intentionally caller-less in 6.2a (wired by 6.2b — the established
land-foundations-one-PR-ahead pattern; cf. 6.0 types, 4.3c-1 `verify_activation_freeze`).

## 2-tier QCHECK (Codex out of tokens → tier-2 = Opus 4.8 adversarial, per /goal)
Tier-1 `/code-review high` (12 agents, 0 errors) and tier-2 Opus both ran; **no CRITICAL/HIGH**.
- **CONFIRMED by BOTH tiers (correctness):** `Date.parse` silently rolled calendar-impossible but
  regex-valid instants forward (`2026-02-30`→Mar-2; `2026-04-31`; `2026-02-29` in a non-leap year
  all pass the 6.0 pattern), so a malformed intent could be `validation_accepted` on a window it
  never declared. FIXED: `parseUtcInstant` round-trips the parsed epoch through UTC getters and
  returns null on mismatch → `not_before_violation`. Regression tests added (validator + parser).
- **BOTH tiers (fail-open in an auth primitive):** `maxAge: config.maxAge ?? '5m'` only guarded
  `undefined`; a blank/garbage `maxAge` made jsonwebtoken skip its max-age check. FIXED at two
  layers: the verifier treats blank as 5m, and `loadConfig` rejects a malformed duration
  (ConfigError). Tests added for both.
- **Tier-1 cleanup (CLAUDE.md "don't fork an implementation"):** Ajv factory was triplicated and
  the canonicalize+sha256 plumbing forked — consolidated into `newMachineBoundaryAjv` and
  `sha256OfCanonicalJson`; `config.serviceAuth` now reuses `SchedulerServiceTokenConfig`.
- **Tier-2 LOW/nits:** `positionsEqual` finiteness guard (fail closed, no throw-in-`find`);
  no-`exp`-token rejection test; extra golden vectors; clarifying comments on the
  not_before_violation dual-meaning and the receipt echoing the intent's own capability_hash.
- **Refuted:** `interface ServiceTokenVerifier` vs C-8 — kept (matches existing `auth.ts`
  `TokenVerifier`). **Deferred (documented):** back-port the blank-`sub` trim guard to operator
  `auth.ts` (out of this slice).
