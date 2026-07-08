# scada-gate-control

SCADA-like Modbus TCP gate control service for the RID Munbon Phase 2 project
(ระบบควบคุมประตูระบายน้ำ มูลบน เฟส 2). First controlled site: **Waste Way**.

Implements the backend half of `docs/RID_MUNBON_SCADA_APP_SPEC.md`: poll field
equipment over Modbus TCP, expose decoded gate status, and accept safe,
role-gated, audited control commands.

## Status (sliced delivery)

- [x] Slice 0 — service scaffold (TS, vitest, pino, lint/format)
- [x] Slice 1 — Modbus domain core (pure logic: register map, level/flow
      mapping, boolean decoders, quality, command builder, write-safety)
- [x] Slice 2 — Modbus transport + poll loop (modbus-serial client w/ reconnect + connect timeout, in-process simulator, pure poll/state quality machine)
- [x] Slice 3 — REST API (`/api/sites`, `/api/gates/:id/status`,
      `/command-level`, `/horn`) + JWT auth from `services/auth` + RBAC +
      safety-gated command service + audit log (Postgres / in-memory)
- [ ] Slice 4 — Frontend main map
- [ ] Slice 5 — Frontend gate detail / control
- [ ] Slice 6 — Hardening (settings, real coords/image, e2e)

## Layout

```
src/
  domain/            # Slice 1 — pure, fully unit-tested, no I/O
    registers.ts     #   Modbus register map (addresses used as-is, no -1 offset)
    gate-level.ts    #   level 1..4 <-> Thai label / technical label / flow rate
    quality.ts       #   ok | stale | offline | modbus_exception | decode_error
    decode.ts        #   raw Modbus values -> domain values (decode_error on bad data)
    command.ts       #   operator intent -> concrete Modbus writes
    write-safety.ts  #   pre-write checklist predicate
  utils/logger.ts    # pino logger
  index.ts           # entry point (transport + API added in later slices)
```

## Commands

```bash
npm install
npm test            # vitest run (Slice 1 domain unit tests)
npm run typecheck   # tsc --noEmit
npm run lint
npm run build       # tsc -> dist/
npm run dev         # ts-node src/index.ts
```

## Configuration (env)

`.env.example` is intentionally omitted (blocked by a local secret-protection
hook). Set these in your `.env`:

| Var                                           | Default                      | Meaning                                                              |
| --------------------------------------------- | ---------------------------- | -------------------------------------------------------------------- |
| `LOG_LEVEL`                                   | `info`                       | pino log level                                                       |
| `TZ`                                          | `Asia/Bangkok`               | timezone                                                             |
| `PORT`                                        | `3030`                       | HTTP API port (Slice 3)                                              |
| `MODBUS_HOST`                                 | **required**                 | PLC address (no default — fails fast if unset; see note below)       |
| `MODBUS_PORT`                                 | `502`                        | Modbus TCP port                                                      |
| `MODBUS_UNIT_ID`                              | `1`                          | Modbus unit id (unconfirmed — vendor to confirm)                     |
| `MODBUS_POLL_INTERVAL_MS`                     | `3000`                       | poll cadence; must be `2000`–`5000` (spec: 2–5s)                     |
| `MODBUS_TIMEOUT_MS`                           | `2000`                       | connect + request timeout (unreachable → offline within this)        |
| `MODBUS_STALE_AFTER_MS`                       | `10000`                      | reading age -> `stale`                                               |
| `MODBUS_OFFLINE_AFTER_MS`                     | `20000`                      | reading age -> `offline`                                             |
| `JWT_SECRET`                                  | **required**                 | shared HS256 secret to verify `services/auth` access tokens          |
| `JWT_ISSUER` / `JWT_AUDIENCE`                 | `munbon-auth` / `munbon-api` | expected token issuer/audience                                       |
| `DATABASE_URL`                                | **required**\*               | Postgres for the durable audit log                                   |
| `ALLOW_IN_MEMORY_AUDIT`                       | `false`                      | \*dev-only: allow a non-persistent audit sink with no `DATABASE_URL` |
| `COMMAND_RATE_MAX` / `COMMAND_RATE_WINDOW_MS` | `30` / `60000`               | per-user+gate command rate limit                                     |

## Device connectivity

The PLC is at **`172.16.1.103:502`** (confirmed — this supersedes the
`172.16.1.110` written in the spec doc). Set `MODBUS_HOST=172.16.1.103` for
production; there is no default, so an unset host fails fast. From a dev machine
the PLC is reachable only when the Tailscale node
`munbon-remote-1` advertises the `172.16.1.0/24` subnet route and it is approved
(plus IP-forwarding on that node). Until then, the Modbus layer is exercised
against an in-process Modbus TCP simulator (Slice 2); `npm run probe` validates
the real device once the route is live.

## API

| Method | Path                           | Role           | Notes                                   |
| ------ | ------------------------------ | -------------- | --------------------------------------- |
| GET    | `/health`                      | —              | liveness                                |
| GET    | `/api/sites`                   | any authed     | site summary + connection colour        |
| GET    | `/api/gates/:id/status`        | any authed     | full decoded snapshot + endpoint        |
| POST   | `/api/gates/:id/command-level` | operator/admin | `{ targetValue: 1-4, confirmed: true }` |
| POST   | `/api/gates/:id/horn`          | operator/admin | `{ enabled: bool, confirmed: true }`    |

Writes pass the Slice-1 safety planner: `403` role denied, `409` stale/offline
data, `400` unconfirmed/invalid target, `202` accepted (`pending` true until the
read-back shows the device reached the target). Every attempt is audited.

### Auth / RBAC (confirm with RID before go-live)

Tokens are `services/auth` HS256 access tokens (`JWT_SECRET` must match). The
token carries role **names** only; they map to app roles in `src/api/auth.ts`:

| App role | auth role names (default)  | Can                                  |
| -------- | -------------------------- | ------------------------------------ |
| Admin    | `super_admin`, `rid_admin` | read + command + (settings, Slice 6) |
| Operator | `zone_manager`             | read + command gate/horn             |
| Viewer   | everything else            | read only                            |

**This mapping is a policy decision — confirm the role-to-privilege table with
RID.** It is centralised in `DEFAULT_ROLE_MAPPING`.
