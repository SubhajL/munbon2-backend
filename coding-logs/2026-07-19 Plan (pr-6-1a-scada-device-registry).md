# Plan — PR 6.1a: SCADA strict multi-device registry + capability endpoint

> **Status:** Claude draft (g-planning); Codex gpt-5.6-sol xhigh pending → synthesize. /goal PR 2 of 3 (6.0✅ → 6.1a → 4.3c). Service: `services/scada-gate-control` (TS). Additive: NO dispatcher, NO write/actuation path.

## Overview
Load a strict, content-hashed multi-device registry from `SCADA_DEVICE_REGISTRY_PATH` and expose it read-only at authenticated `GET /internal/v1/device-capabilities`, producing the PR 6.0 `device-capability-snapshot`. Missing/empty path ⇒ empty capabilities map (zero machine-capable gates — dark default). Preserve the existing Waste Way human routes unchanged.

## Registry format + loader
- `SCADA_DEVICE_REGISTRY_PATH` → JSON: `{ "capability_release_id": <id_token>, "capabilities": { "<canonical_gate_id>": { "device_id", "adapter_gate_id", "targets": [{target_position_m, target_level}] } } }` (endpoint-free — no host/port/register/secret; register maps + quantizer come from 6.1b).
- NEW `src/domain/device-registry.ts` — `loadDeviceRegistry(env)`: reads the file, assembles the full snapshot (`schema_version:1` + computed `capability_hash`), validates the RESULT against `contracts/machine-boundary/v1/device-capability-snapshot.schema.json` via the SAME `Ajv2020 + ajv-formats` used in the 6.0 contract spec. **Fail-closed:** unset/empty path ⇒ empty snapshot (`capabilities:{}`, sentinel `capability_release_id`); present-but-invalid/malformed/duplicate/unknown-field ⇒ **throw at startup** (fail-fast, matching the MODBUS_HOST env pattern — never boot SCADA on a broken registry).

## capability_hash (FROZEN by 6.0)
`sha256( "munbon:device-capability-snapshot:v1\n" || JCS(snapshot without capability_hash) )`, lowercase hex. NEW `src/domain/capability-hash.ts` implementing RFC 8785 JCS. **Add `canonicalize@^2` (RFC 8785) dep** rather than a hand-rolled JCS (number serialization is the hazard; our numbers are `target_position_m` 0–1000 finite + integers). Ship a **golden cross-language vector** fixture (`contracts/machine-boundary/v1/fixtures/golden/device-capability-hash.json` = a sample snapshot + its canonical bytes + hash) + a TS test, so 4.3c/6.2 (Python) can assert byte-identical JCS + hash. Determinism test: two loads of the same registry ⇒ same hash.

## Config
- `src/config.ts`: add optional `deviceRegistryPath?: string` to `AppConfig`; `loadConfig` reads `SCADA_DEVICE_REGISTRY_PATH` (undefined when unset).
- Load-once at startup (in `main()`/server wiring); the loaded snapshot is injected into the router deps. Invalid file ⇒ startup throws (fail-fast).

## Endpoint
- `GET /internal/v1/device-capabilities` in a NEW internal router (or `buildRouter` deps): **authenticated** (`requireAuth(verifier)`, Viewer+ may read — read-only capability info; 6.2's scheduler uses a short-lived audience-pinned token later). Returns the snapshot (incl `capability_hash`). Headers: `Cache-Control: no-store`. Always returns a snapshot (empty if none) — no 404. Never leaks file paths/internals in the body (500 → generic).
- Register in `src/api/routes.ts` (`buildRouter`) + wired via `src/api/server.ts` `buildServer`.

## Scope guards
Preserve `/api/sites`, `/gates/:id/status`, `POST /gates/:id/command-level`, `POST /gates/:id/horn` and all existing behavior. NO dispatcher, NO actuator/Modbus/write path, NO scheduler change. The endpoint is READ-ONLY.

## Files
- NEW `src/domain/device-registry.ts` (`loadDeviceRegistry`, snapshot assembly + Ajv validation + fail-closed).
- NEW `src/domain/capability-hash.ts` (`computeCapabilityHash` via JCS).
- NEW `src/api/internal-routes.ts` OR extend `buildRouter` (the GET endpoint).
- `src/config.ts` (env), `src/api/server.ts`/`index.ts` (wire the loaded snapshot).
- `package.json`/lock (`canonicalize`).
- NEW golden vector fixture under `contracts/machine-boundary/v1/fixtures/golden/` (manifest untouched — the golden vector is separate from the v1 conformance corpus, OR added to the manifest as a hashed artifact).
- Tests: `src/domain/device-registry.spec.ts`, `src/domain/capability-hash.spec.ts`, `src/api/internal-routes.spec.ts` (supertest).

## Tests (behavior)
valid registry → snapshot + stable hash; unset path → empty snapshot (zero gates); malformed/invalid registry → startup throws; unknown field / bad gate key → rejected; hash determinism + golden-vector byte match; endpoint 401 unauth; 200 + snapshot authed; `no-store`; empty-default served; existing Waste Way routes unaffected (regression).

## Risks / open decisions
- **JCS cross-language determinism** (the number-serialization hazard) — the golden vector locks it; 4.3c/6.2 must reuse the same algorithm. Confirm `canonicalize` matches Python's future impl (document the exact library/spec).
- Registry load failure posture (fail-fast startup vs serve-empty) — recommend **fail-fast on a present-but-invalid file**, empty only on unset/empty path.
- Endpoint auth role (Viewer+ vs Operator+) — recommend Viewer+ (read-only); 6.2 hardens with a service token.
- Where the golden vector lives (manifest vs a separate golden/ dir) — decide with Codex.
