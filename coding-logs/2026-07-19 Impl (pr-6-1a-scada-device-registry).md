# PR 6.1a — SCADA strict multi-device registry + capability endpoint (impl log)

**Date:** 2026-07-19 · **Base:** main `0e963960` (post-6.0) · **Branch:** `feat/scada-device-registry-6-1a`
**Plan:** `coding-logs/2026-07-19 Plan (pr-6-1a-scada-device-registry).md` (Claude; **Codex plan-tier UNAVAILABLE — quota-blocked until Jul 25th**, killed 2x then explicit usage-limit; adversarial rigor deferred to the mandatory QCHECK). /goal PR 2 of 3 (6.0✅ → 6.1a → 4.3c). Service `services/scada-gate-control` (TS). **Additive: NO dispatcher, NO write/actuation/Modbus path.**

## What shipped
- **`src/domain/capability-hash.ts`** — the FROZEN (PR 6.0) content hash `sha256("munbon:device-capability-snapshot:v1\n" || RFC-8785-JCS(snapshot without capability_hash))` via the `canonicalize` reference lib. Ships a **golden cross-language vector** `contracts/machine-boundary/golden/device-capability-hash.golden.json` (canonical JSON + hash), loaded by the spec, so the future Python producer/verifier (4.3c/6.2) can assert byte-identical JCS + hash. (Placed OUTSIDE `v1/` so the 6.0 conformance roster is undisturbed.)
- **`src/domain/device-registry.ts`** — `loadDeviceCapabilitySnapshot(env)`: reads `SCADA_DEVICE_REGISTRY_PATH`; unset/blank ⇒ empty dark default (`capabilities:{}`, `__empty__`, its own hash = zero machine-capable gates); present-but-unreadable / malformed JSON / not-exactly-`{capability_release_id,capabilities}` / contract-violating ⇒ **THROW**. Assembles `{schema_version:1, …, capability_hash:<computed>}` and validates against the single source-of-truth `contracts/machine-boundary/v1/device-capability-snapshot.schema.json` via the same `Ajv2020 + ajv-formats` as the 6.0 gate (schema found by a `__dirname` walk-up).
- **`src/api/internal-routes.ts`** — `GET /internal/v1/device-capabilities`: authenticated (`requireAuth`), read-only, `Cache-Control: no-store`, serves the startup-loaded snapshot. Mounted at `/internal` in `server.ts`; `ApiDeps` gained `deviceCapabilities`; `index.ts` loads it before `buildServer` (fail-fast on a broken registry).
- `canonicalize@^2` dep. `server.spec.ts` fixed for the new required `deviceCapabilities` dep.

## Gate
scada **218 passed / 21 files** (baseline 201; +17 = 5 hash + 9 registry + 3 endpoint), typecheck + lint + prettier clean; 3× stable; wiring verified (computeCapabilityHash→registry, loadDeviceCapabilitySnapshot→index, buildInternalRouter→server, deviceCapabilities→endpoint — all non-test refs). 6.0 roster test 77 passed (golden outside v1/ undisturbed). Golden hash `dc4f089d…`; empty-snapshot hash `6ec86898…` (both pinned).

## Scope guards honored
Waste Way human routes (`/api/gates/:id/{command-level,horn,status}`, `/api/sites`) + all existing behavior unchanged; NO dispatcher/actuator/Modbus/write path; NO scheduler change. The endpoint is READ-ONLY; the registry is endpoint-free (extra top-level keys + Ajv additionalProperties reject smuggled endpoint keys). 6.2 re-fetches + pins this snapshot with a service token.

## 2-tier QCHECK: Codex quota-blocked (until Jul 25th) → 2× Opus adversarial (breadth code-defect + depth threat-model)

Both tiers ran read-only against the branch. NO CRITICAL. Confirmed clean by both: no
actuation/Modbus/write path; fail-closed (never serves a stale/undefined snapshot);
fail-fast startup real (`index.ts` loads before `listen`; `main().catch → process.exit(1)`);
golden vector is a genuine independent oracle; JWT HS256 pinned. Adjudicated + fixed batch
(all empirically re-verified; 231 tests green, 3× stable, build clean, 6.0 roster 77 green):

1. **[both, HIGH] Golden didn't lock cross-language number canonicalization.** The frozen
   `capability_hash` is only stable if every producer serializes numbers with RFC-8785 / ES6
   `Number.prototype.toString`; a naive Python `json.dumps` producer diverges (2.0→"2.0",
   1e-6→"1e-06", 1e-7→"1e-07", -0.0→"-0.0") → a DIFFERENT hash across languages, and the old
   golden (0.45, 0) never exercised it. **Fix:** added a `number_canonicalization_vectors`
   table to the golden (7 cases, each with the divergent `python_json_dumps`) + a data-driven
   `capability-hash.spec.ts` block asserting every case. Additive — the frozen snapshot +
   `dc4f089d…` hash are UNCHANGED (scheduler roster 77 still green). The Python producer of
   4.3c/6.2 MUST assert the same table.
2. **[both, MED] Prototype-pollution gate keys.** The v1 schema keys gates by `id_token`
   (`^[!-~]+$`), which Ajv ACCEPTS `__proto__`/`constructor`/`prototype` for; from `JSON.parse`
   these are own-enumerable keys whose value only reads back via a descriptor (verified). **Fix:**
   `device-registry.ts` rejects reserved gate keys BEFORE any value access (`/reserved property
   name/`).
3. **[both, MED] Endpoint/secret smuggled into an id VALUE.** `device_id:"tcp://admin:secret@…"`
   passes `^[!-~]+$`. **Fix:** loader rejects `://` or `@` in `capability_release_id`, gate keys,
   `device_id`, `adapter_gate_id` (`/must not embed a transport endpoint or credential/`).
   Value-level projection defense beyond what a shape schema can prove.
4. **[both, MED] Endpoint readable by any authenticated role (incl. Viewer/guest).** This is a
   service-to-service surface (scheduler carries an operator/service token). **Fix:** new
   `requireRole('operator')` middleware after `requireAuth`; endpoint now 401 (no token) / 403
   (viewer) / 200 (operator+admin). ROLE_RANK viewer<operator<admin.
5. **[both, MED] Runtime dependency on repo-root `contracts/` bricks a dist-only deploy.**
   `snapshotValidator()` walked `__dirname` up to repo-root `contracts/`; PM2 ships only `dist/`,
   so even the empty dark default couldn't boot. **Fix:** embedded the schema as
   `device-capability-snapshot.schema.ts` (const), compiled at runtime with NO disk read; a
   drift-guard spec asserts it `toEqual` the on-disk v1 source of truth (runs in CI where
   `contracts/` is present).
6. **[threat-model, MED] `target_position_m` max 1000 m vs a real ~2 m gate.** The 1000 m bound
   is the FROZEN 6.0 engine-safety finite bound, NOT a physical gate max; a real per-gate max
   needs 6.1b register maps / 7.2 geometry and would re-touch the frozen contract. **Documented**
   as 6.1b/7.2 responsibility; no change here.
7. **[LOW] Test rigor + size cap.** Bare `.toThrow()` → specific `/message/` matchers per
   CLAUDE.md Writing-Tests #3; added a 1 MiB raw-byte size cap before `JSON.parse`
   (`/exceeds the 1 MiB cap/`). Duplicate-JSON-key last-wins is inherent to `JSON.parse`
   (documented, no custom parser); case-variant gate ids are case-sensitive by design.

**Fix-delta re-QCHECK (Opus, focused):** NO CRITICAL/HIGH. Fixes 1/3/4/6/7 confirmed SOUND with
independent oracles — recomputed `capability_hash` still `dc4f089d…` (table is inert to the hash),
CPython `json.dumps` divergences match every `python_json_dumps` entry, prototype-pollution
rejection reachable BEFORE any value access (canonicalize/Ajv never see the hostile key), Ajv
strict compiles the embedded const, role-gate ordering correct (401/403/200), no actuation/write
path, all fail-closed guarantees intact. Two residual items:
- **LOW (fixed):** the 1 MiB cap ran AFTER `readFileSync` loaded the whole file, so it never
  bounded peak memory. Moved to a `statSync(path).size` PRE-read check (`device-registry.ts`) —
  the guard now does what its comment claims. Size-cap + missing-file tests still green.
- **INFORMATIONAL (no change):** `@`/`://` hygiene is percent-encode-bypassable, but such a string
  is non-functional as an endpoint and unicode lookalikes are already excluded by the ASCII-only
  `^[!-~]+$` schema pattern; the registry path is operator/deploy-owned config, so this is a
  best-effort tripwire, not a trust boundary.

Post-fix: 231/231 × 3 stable, typecheck/lint/build clean.

## Final gate
scada **231 passed / 22 files** (baseline 201 → +30; +1 file = `device-capability-snapshot.schema.spec.ts`), typecheck + lint + prettier + build clean, 3× stable. Wiring: `requireRole`→internal-routes, `DEVICE_CAPABILITY_SNAPSHOT_SCHEMA_V1`→device-registry (both non-test). 6.0 scheduler roster 77 passed; frozen `capability_hash` unchanged.
