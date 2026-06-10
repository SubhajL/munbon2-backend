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
- [ ] Slice 2 — Modbus transport + poll loop (modbus-serial + simulator tests)
- [ ] Slice 3 — REST API + auth/RBAC + audit log
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

| Var | Default | Meaning |
| --- | --- | --- |
| `LOG_LEVEL` | `info` | pino log level |
| `TZ` | `Asia/Bangkok` | timezone |
| `PORT` | `3030` | HTTP API port (Slice 3) |
| `MODBUS_HOST` | `172.16.1.110` | PLC address (via Tailscale subnet route) |
| `MODBUS_PORT` | `502` | Modbus TCP port |
| `MODBUS_UNIT_ID` | `1` | Modbus unit id (unconfirmed — vendor to confirm) |
| `MODBUS_POLL_INTERVAL_MS` | `3000` | poll cadence (spec: 2–5s) |
| `MODBUS_STALE_AFTER_MS` | `10000` | reading age -> `stale` |
| `MODBUS_OFFLINE_AFTER_MS` | `20000` | reading age -> `offline` |
| `JWT_SECRET` / `JWT_ISSUER` / `JWT_AUDIENCE` | — | verify tokens from `services/auth` |
| `DATABASE_URL` | — | Postgres for audit log |

## Device connectivity

The PLC at `172.16.1.110:502` sits on the on-site LAN. From a dev machine it is
reachable only when the Tailscale node `munbon-remote-1` advertises the
`172.16.1.0/24` subnet route and it is approved (plus IP-forwarding on that
node). Until then, the Modbus layer is exercised against an in-process Modbus
TCP simulator (Slice 2); `npm run probe` will validate the real device once the
route is live.
