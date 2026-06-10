# scada-gate-control Service Context

## Overview

SCADA-like Modbus TCP gate control for RID Munbon Phase 2. Polls field
equipment at the Waste Way site, decodes gate status, and accepts role-gated,
audited control commands. Implements `docs/RID_MUNBON_SCADA_APP_SPEC.md`.

## Architecture

- **Domain core** (`src/domain`): pure, side-effect-free logic — register map,
  gate-level/flow mapping, Modbus value decoders, data quality, command builder,
  write-safety predicate. Fully unit-tested with vitest.
- **Transport** (Slice 2): `modbus-serial` TCP client + 2–5s poll loop +
  in-memory latest-state store with a quality state machine.
- **API** (Slice 3): Express REST (`/api/sites`, `/api/gates/:id/status`,
  `/api/gates/:id/command-level`, `/api/gates/:id/horn`) with JWT auth from
  `services/auth`, RBAC (Viewer/Operator/Admin), and Postgres audit log.

## Modbus register map (Waste Way, addresses used as-is, no -1 offset)

| Point | Address | Kind | Access |
| --- | ---: | --- | --- |
| Gate_Level | 104 | Holding Register | read |
| Door_SW | 16 | Coil | read (status only) |
| Horn | 15 | Coil | read/write |
| Op_gate | 108 | Holding Register | write |
| GateCF | 17 | Coil | write |

Device: `172.16.1.110:502`, unit id 1 (unconfirmed).

## Control behaviour

- Gate command: write HR 108 = target (1..4), then write coil 17 = 1. PLC
  handles confirmation; no GateCF reset needed.
- Horn: write coil 15 = 1 (on) / 0 (off). No confirmation bit.
- Door_SW is status-only in the UI even though writable at the Modbus level.

## Deployment

- PM2 app `scada-gate-control` (`ecosystem.config.js`), runs `dist/index.js`.
- Reachability to the PLC requires the Tailscale `172.16.1.0/24` subnet route via
  `munbon-remote-1`.

## SLOs (target)

- Poll cadence 2–5s; reading age > 10s = stale, > 20s = offline.
- Every write produces an audit record (user, role, gate, command, raw
  address/value, endpoint, unit id, result, timestamp).
