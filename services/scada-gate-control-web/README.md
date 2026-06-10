# scada-gate-control-web

Operator web UI for the RID Munbon SCADA gate-control backend
(`services/scada-gate-control`). Next.js 16 (App Router) + Tailwind v4 +
MapLibre GL (via `react-map-gl`, **no Mapbox token**). Dark, data-dense SCADA
HMI styling from a Stitch-generated "Industrial SCADA Interface" design system.

## Status (sliced)

- [x] Slice 4 — Screen 1 Main Map: full-screen MapLibre map, floating system
      status panel (online/stale/offline summary), gate markers coloured by
      status, click-to-open popup with decoded Gate_Level/Door_SW/Horn + a
      "ดูรายละเอียด / ควบคุม" button. Polls `/api/sites` (+ gate status) every 3s.
- [x] Slice 5 — Screen 2 Gate Detail / Control (`/gates/[id]`): header with
      back + connection badge + last-updated, framed gate illustration with 4
      level sensors (current ON/green, click/right-click an OFF level to
      command), confirmation modal (Radix Dialog) showing the raw Modbus
      registers, side panel (Door_SW status-only, Horn เปิด/ปิด, raw level,
      endpoint, Unit ID), role-aware (Viewer controls disabled).
- [x] Slice 6 (login) — real sign-in against `services/auth` via a same-origin
      auth BFF (`/api/auth/login|refresh|logout` route handlers). Access token
      is kept in memory; the refresh token is a same-origin httpOnly cookie
      (`sgc_refresh`, scoped to `/api/auth`). `/login` page + `RequireAuth`
      guard (redirects unauthenticated users with `?next=`), account badge with
      role + log out, silent refresh on mount and on a 401 (coalesced so
      concurrent pollers can't double-spend the rotating refresh token). The
      `NEXT_PUBLIC_DEV_TOKEN` escape hatch still bypasses login for local dev.

## Run

```bash
npm install
npm run dev        # http://localhost:3000
npm test           # vitest (lib + component + axe a11y)
npm run build
```

## Configuration (env)

| Var | Default | Scope | Meaning |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:3030` | client | scada-gate-control backend base URL |
| `AUTH_SERVICE_URL` | `http://localhost:3001` | **server** | `services/auth` base URL the auth BFF proxies to (never exposed to the browser) |
| `NEXT_PUBLIC_DEV_TOKEN` | — | client | dev-only JWT (Bearer); when set, skips the login flow entirely |

`AUTH_SERVICE_URL` is read server-side only (in the `/api/auth/*` route handlers);
do not give it a `NEXT_PUBLIC_` prefix.

## Notes

- Gate coordinates in `src/lib/gates.ts` are **placeholders** — replace with the
  real Waste Way lat/lng (and other Phase-2 gates) when RID provides them.
- Sign in at `/login` with a `services/auth` account; protected screens redirect
  there when unauthenticated. For local dev without the auth service running, set
  `NEXT_PUBLIC_DEV_TOKEN` to a valid access token to bypass login.
- The refresh token lives only in the same-origin httpOnly `sgc_refresh` cookie
  (scoped to `/api/auth`); the access token is held in memory and refreshed
  silently. Run `services/auth` (port 3001) alongside this app for the real flow.
- Token renewal is coalesced within a tab (one in-flight refresh) and serialized
  across tabs via the Web Locks API so the rotating refresh token is never spent
  twice. Browsers without Web Locks fall back to per-tab coalescing only.
- A transient auth-service outage (5xx / network) during renewal keeps the
  current session rather than signing the user out; only a definitive 401 does.
- Storybook and full 4-breakpoint responsive passes were deferred (see Slice 6).
