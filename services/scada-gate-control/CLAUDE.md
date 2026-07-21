# scada-gate-control — Modbus TCP gate actuation

**TypeScript 5.3 (strict) / Express 4 / Node ≥18** · Entry: `src/index.ts` (`main()` → transport → poll loop → Express) · **Extends [../../CLAUDE.md](../../CLAUDE.md)**

## Purpose

Polls a field PLC over **Modbus TCP**, exposes decoded gate status via REST, and accepts safety-gated, role-based, audited control commands (gate level 1-4, horn). First site: "Waste Way".

## Commands

```bash
npm install
npm run dev            # ts-node src/index.ts
npm run build          # tsc -> dist/
npm start              # node dist/index.js
npm test               # vitest run (colocated *.spec.ts)
npm run typecheck      # tsc --noEmit
npm run lint           # eslint src --ext .ts
```

Gate before PR: `npm run typecheck && npm run lint && npm test`.

## Structure (`src/`)

- `domain/` — **pure, I/O-free, fully unit-tested core**: `registers.ts` (Modbus map), `gate-level.ts` (level↔label↔flow), `quality.ts`, `decode.ts`, `command.ts`, `write-safety.ts`, `plan.ts`.
- `transport/` — `modbus-serial-transport.ts` (real Modbus **TCP** via `connectTCP`), `simulator.ts` (in-process sim), `mutex.ts`.
- `state/` — `gate-controller.ts` (poll loop + snapshot), `freshness.ts` (stale/offline thresholds).
- `api/` — `server.ts` (`buildServer`), `routes.ts`, `auth.ts` (JWT HS256), `middleware.ts` (`requireAuth`), `rate-limit.ts`.
- `services/command-service.ts`; `audit/` (`pg-repository.ts` Postgres, `memory-repository.ts` dev).

## Tests

Vitest, colocated `*.spec.ts` (`include: src/**/*.spec.ts`); API tests use `supertest`. Run `npm test`.

## Config / Ports / Env

- HTTP `PORT`=3030. Modbus: `MODBUS_HOST` (**required, fail-fast, no default**), `MODBUS_PORT`=502, `MODBUS_UNIT_ID`=1 (vendor-unconfirmed), poll interval 3000ms (validated 2000-5000).
- Auth: `JWT_SECRET` (required), `JWT_ISSUER`/`JWT_AUDIENCE`; HS256 pinned. Audit DB: `DATABASE_URL` (Postgres) unless `ALLOW_IN_MEMORY_AUDIT=true`.
- PLC at `172.16.1.103:502` (README-confirmed; reachable in dev only via Tailscale `munbon-remote-1`).

## Integration

- Field PLC (Modbus TCP), sibling `services/auth` (shared `JWT_SECRET`, roles → Viewer/Operator/Admin), Postgres audit log. REST: `GET /health`, `GET /api/sites`, `GET /api/gates/:id/status`, `POST /api/gates/:id/command-level`, `POST /api/gates/:id/horn`.
- **Machine boundary (PR 6.1a/6.2, service-to-service):** `GET /internal/v1/device-capabilities` (operator token, PR 6.1a) and `POST /internal/v1/command-intents/validate` (PR 6.2). The validate endpoint is **validation-only** — it holds no actuator/transport, so it cannot write Modbus; it returns a durable idempotent 6.0 `ValidationReceipt` from `scada_command_intents` (repo-owned `ensureSchema`, shares the audit pool). Service auth is a **dedicated** HS256 token (`SCHEDULER_SERVICE_JWT_SECRET`, NOT the operator `JWT_SECRET`): audience-pinned (`SCHEDULER_SERVICE_JWT_AUDIENCE`, default `munbon-scada-machine-boundary`), issuer `SCHEDULER_SERVICE_JWT_ISSUER` (default `munbon-scheduler`), `type:'service'`, `SCHEDULER_SERVICE_JWT_MAX_AGE` (default `5m`). Unset secret → endpoint is DARK (503), rest of SCADA boots normally. `intent_content_hash = sha256(JCS(intent))` must byte-match the scheduler's `command_intent_content_hash`.
- **Approved field artifact + lineage anchor (PR 6.1b, D6/RID-gated):** `src/domain/approved-field-artifact.ts` is a PURE, OFFLINE generator/validator (no runtime wiring, no Modbus). `buildDeviceRegistryArtifact()` projects a rich approved artifact (canonical gate + device/adapter + register/unit + quantizer + readback + evidence + approval + `approved_lineage_anchor`) down to the exact endpoint-free `{capability_release_id, capabilities}` doc that `SCADA_DEVICE_REGISTRY_PATH` (6.1a) consumes, byte-exact; `validateApprovedRegistryCoverage()` fail-closed-asserts exact approved-gate scope + monotone/bijective quantizer + readback round-trip. **D6 is unavailable** → only a loudly-labeled non-field-approved EXAMPLE fixture is committed; the real artifact stays external. The reserved `lineage_mismatch` reason is now wired into `validateCommandIntent` as **dark-by-default**: `SCADA_APPROVED_LINEAGE_ANCHOR_PATH` (a small JSON `{model_release_id, model_release_content_hash, engine_descriptor_content_hash}` — the approved commandable-release identity, stable across plan versions) → the check rejects an intent whose lineage isn't the approved release, ordered AFTER the 6.2 device checks and BEFORE window/deadline. Unset (default) → the check is a no-op (6.2-identical). A set-but-broken anchor fails fast at startup (opting in is deliberate — never silently disabled).

## Gotchas / Watch-outs

- Package is `modbus-serial` but usage is **Modbus TCP**, not serial.
- `npm run probe` is **BROKEN** — points to `src/scripts/probe-device.ts` which doesn't exist.
- No `.env.example` (intentionally blocked by a local secret hook); no Dockerfile — deploys via PM2 (`ecosystem.config.js`, `dist/index.js`).
- Backend-only: frontend slices (map, gate-detail UI, e2e) live in `scada-gate-control-web` and are partially unimplemented.
- Role→privilege mapping is hardcoded in `DEFAULT_ROLE_MAPPING` — "confirm with RID before go-live".
- **6.1b lineage anchor — arming is a trust-cutover, rotate the receipt store (QCHECK deploy note):** a 6.2 `ValidationReceipt` is frozen at first validation under the then-current anchor policy (idempotent replay returns it verbatim). A receipt minted while the anchor was DARK will replay as `validation_accepted` even after arming, so an intent validated during the dark window is NOT re-checked. Therefore arming `SCADA_APPROVED_LINEAGE_ANCHOR_PATH` must be paired with rotating/clearing the `scada_command_intents` receipt store (or done at the external trust cutover on a fresh store). `SCADA_APPROVED_LINEAGE_ANCHOR_PATH` set-but-blank FAILS FAST (never runs dark) — UNSET it to disable deliberately.
- **7.3a rich D6 runtime bundle:** `SCADA_APPROVED_FIELD_BUNDLE_PATH` is the single runtime source for the device capability snapshot and lineage anchor. A configured bundle is capped, schema-validated, rejected if it carries the committed example marker, checked against the exact configured pilot gate, and verified for distinct command/readback registers, monotone/bijective quantizers, and unambiguous readback round trips. Legacy split registry/anchor paths cannot accompany it. `ALLOW_MACHINE_COMMANDS=true` requires this rich bundle; unset while dark retains the legacy/empty behavior. Arming remains a trust cutover and still requires rotating the receipt store.
