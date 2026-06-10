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
- [ ] Slice 5 — Screen 2 Gate Detail / Control (`/gates/[id]`).

## Run

```bash
npm install
npm run dev        # http://localhost:3000
npm test           # vitest (lib + component + axe a11y)
npm run build
```

## Configuration (env, all `NEXT_PUBLIC_`)

| Var | Default | Meaning |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:3030` | backend base URL |
| `NEXT_PUBLIC_DEV_TOKEN` | — | dev-only JWT (Bearer) until a login flow lands |

## Notes

- Gate coordinates in `src/lib/gates.ts` are **placeholders** — replace with the
  real Waste Way lat/lng (and other Phase-2 gates) when RID provides them.
- All endpoints require auth (Viewer can read); set `NEXT_PUBLIC_DEV_TOKEN` to a
  valid access token from `services/auth` for local development, or the panel
  shows the API-unreachable error state.
- Storybook and full 4-breakpoint responsive passes were deferred (see Slice 6).
