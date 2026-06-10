# RID Munbon SCADA Gate Control — Handoff

Status snapshot for continuing in a new session. Spec:
`docs/RID_MUNBON_SCADA_APP_SPEC.md`.

## Where things live

- **Git worktree:** `/Users/subhajlimanond/dev/munbon2-backend-scada`
  (branch `feat/scada-gate-control`, off `main`). The main checkout
  `/Users/subhajlimanond/dev/munbon2-backend` stays on `feat/daily-chart-notifier`
  (unrelated WIP — do not disturb).
- **Branch is pushed**; **draft PR #5**:
  https://github.com/SubhajL/munbon2-backend/pull/5
- **Backend:** `services/scada-gate-control` (TS, Express, Modbus).
- **Frontend:** `services/scada-gate-control-web` (Next.js 16, Tailwind v4, MapLibre).
- Commits: `a77c616` (S0+1), `2a58482` (S2), `046956b` (S3), `a4abbe2` (S4),
  `05681a4` (S5).

## Confirmed decisions

- In-repo new service (not the OPC-UA `services/scada` stub, not the DB-proxy
  `services/scada-integration`).
- Frontend: Next.js + Tailwind + **MapLibre** (`react-map-gl`, no Mapbox token).
- Auth: verify `services/auth` HS256 JWTs; map role names → viewer/operator/admin.
- **`MODBUS_HOST = 172.16.1.103:502`** (user-confirmed; supersedes the spec
  doc's `172.16.1.110`). Host is a REQUIRED env (no default).
- Modbus dev/CI uses an in-process simulator; real device reachable only once
  Tailscale node `munbon-remote-1` advertises the `172.16.1.0/24` subnet route
  (currently NOT reachable from dev).
- UI visuals generated via **Stitch** (project `26448023776838783`): Screen 1
  `de596536547b43f58b09f1cfa23c36c2`, Screen 2 `5b633d15ad0f48ed9f49738d0a1eaebd`,
  blueprint gate illustration `a89bc43704ea4deeafb5f531192510d9`. Design system
  asset `fe20ddc8c723401ebaf4ae16d10cb6bb` ("Industrial SCADA Interface").

## Done (Slices 0–5) — all functional scope complete

### Backend `services/scada-gate-control` (195 tests, vitest)

- **Domain (`src/domain`)** — pure: `registers` (no -1 offset), `gate-level`
  (1–4 ↔ Thai/technical/flow), `quality` (ok/stale/offline/modbus_exception/
  decode_error + worseQuality/markerColor), `decode`, `command` (HR108=target
  then coil17=1; horn coil15), `write-safety` (auth+role+quality+confirmed+
  target∈{1..4}), `plan` (safety-gated planner — the only sanctioned actuation
  builder).
- **State/transport (`src/state`, `src/transport`)** — `Mutex` serializes ALL
  Modbus access; `GateController` (was GatePoller) owns transport+queue+store,
  poll loop + `executeWrites` (writes + read-back atomically, partial-write
  tracking); `ModbusSerialTransport` (modbus-serial, reconnect + connect
  timeout); in-process `simulator` (ServerTCP); `store` (latest-state +
  freshness ok→stale→offline by age).
- **API (`src/api`)** — Express: `GET /api/sites`, `GET /api/gates/:id/status`,
  `POST /api/gates/:id/command-level`, `POST /api/gates/:id/horn`, `/health`.
  `JwtTokenVerifier` (HS256, issuer/audience/type=access, maxAge+exp), RBAC
  middleware, zod validation, deny-reason→HTTP map, sliding-window rate limit,
  generic 500.
- **CommandService (`src/services`)** — safety plan → atomic execute → audit
  EVERY attempt → pending via read-back.
- **Audit (`src/audit`)** — repo interface + in-memory + Postgres (+schema);
  startup REQUIRES `DATABASE_URL` unless `ALLOW_IN_MEMORY_AUDIT=true`.
- Two adversarial Codex QCHECK passes; all CRITICAL/HIGH/MEDIUM/LOW fixed.
- Config in README; `npm run probe` = one-shot real-device check.

### Frontend `services/scada-gate-control-web` (50 tests, vitest + RTL + jest-axe)

- `src/lib`: `api` (typed client), `status`, `format`, `control` (Screen-2 text
  builders), `role` (UI RBAC mirror), `gates` (PLACEHOLDER coords), `utils`.
- `src/hooks/usePolling` (stale-while-error).
- Screen 1 (`src/app/page.tsx`): MapView (markers + popup), SystemPanel,
  ConnectionSummary, StatusPill, GatePopupCard. Polls `/api/sites` + status 3s.
- Screen 2 (`src/app/gates/[id]/page.tsx`): GateDetailHeader + ConnectionBadge,
  LevelSensors (4 levels, current ON, click/right-click OFF to command),
  ConfirmCommandModal (Radix Dialog, shows raw Op_gate/GateCF), SidePanel
  (Door_SW status-only, Horn buttons, raw level, endpoint, Unit ID), role-aware.

## How to run / test

Backend:

```bash
cd services/scada-gate-control && npm install
npm test            # 195 tests
npm run typecheck && npm run lint && npm run build
# run locally (uses in-memory audit + dev flag; points at a local simulator):
MODBUS_HOST=127.0.0.1 MODBUS_PORT=1 JWT_SECRET=dev ALLOW_IN_MEMORY_AUDIT=true PORT=3030 node dist/index.js
```

Frontend:

```bash
cd services/scada-gate-control-web && npm install
npm test            # 50 tests (incl. jest-axe)
npm run build && npm run dev    # http://localhost:3000
# needs a backend + a token: set NEXT_PUBLIC_API_BASE_URL, NEXT_PUBLIC_DEV_TOKEN
```

## Quality-gate workflow used (follow it)

Per slice: TDD (stub→test→impl), then typecheck + lint + prettier + build +
tests ×3 (flakiness) + wiring grep, then **QCHECK** (user runs Codex manually —
MCP too slow — paste findings; fix CRITICAL/HIGH/MEDIUM/LOW), then local commit.
Backend uses strict TS + vitest + colocated `*.spec.ts`; frontend uses Stitch
for visuals (translate tokens → shadcn/Tailwind, never raw HTML).

## Hard gotchas

- Local hook `protect-files.sh` BLOCKS writing any `.env*` (incl. `.env.example`)
  — ask the user; document env in README instead.
- `UserPromptSubmit` hook injects a mandatory "skill activation" preamble every
  turn — evaluate skills first.
- Web app: MapLibre/MapView is NOT unit-tested (WebGL/jsdom) — covered by build.
- Don't run Graphite (`gt`) — repo uses plain git + `gh`.

## Left to do — Slice 6 (hardening) ONLY

Ordered by value:

1. **Login flow** — replace `NEXT_PUBLIC_DEV_TOKEN` shim with a real sign-in
   against `services/auth` (store/refresh JWT). Until then the UI needs a token.
2. **Real Waste Way lat/lng** + real gate image — update
   `web/src/lib/gates.ts` (GATE_COORDS placeholder `101.9,14.9`) and swap the
   blueprint placeholder for the Stitch illustration `a89bc43704...` (or a real
   site photo). Spec open question.
3. **Admin settings** — configurable Modbus Unit ID / register map (spec open
   question: confirm Unit ID with vendor); multi-gate support (`/api/sites`
   already returns a list; add more `GATE_COORDS` + register maps).
4. **Confirm the role→privilege mapping with RID** (`DEFAULT_ROLE_MAPPING` in
   both backend `src/api/auth.ts` and web `src/lib/role.ts`).
5. **Real-device validation** over Tailscale once the `172.16.1.0/24` route is
   up (`npm run probe`, then careful live read; writes with extreme care).
6. **Deferred earlier:** Storybook stories + 4-breakpoint responsive passes; add
   web e2e (Playwright) + a11y route tests.
7. **Ops:** register backend in `pm2-ecosystem.config.js`; CI for both services;
   `DATABASE_URL` provisioning for the durable audit log; deploy the web app.
8. Mark PR #5 ready for review when satisfied.

## Open questions from the spec (still pending real-world input)

- Real Modbus Unit ID (default 1, unconfirmed).
- Real Waste Way lat/lng + additional Phase-2 gate locations + their register maps.
- Real gate image.
