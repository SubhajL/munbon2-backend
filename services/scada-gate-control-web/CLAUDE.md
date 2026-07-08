# scada-gate-control-web — SCADA operator UI

**Next.js 16.2.9 / React 19.2.4 / TypeScript** · App Router (`src/app/`) · **Extends [../../CLAUDE.md](../../CLAUDE.md)**

> ⚠️ **This is NOT the Next.js you know.** Next.js **16** has breaking changes vs older versions (and vs most training data) — APIs, conventions, and file structure differ. **Read the relevant guide in `node_modules/next/dist/docs/` before writing any code**, and heed deprecation notices. (This warning is also carried in the service's `AGENTS.md`.)

## Purpose
Operator web UI for `scada-gate-control`: main map, gate detail/control screens, and a `services/auth`-backed login flow. Backend-only slices live in the sibling `scada-gate-control` service.

## Commands
```bash
npm install
npm run dev            # next dev
npm run build          # next build
npm start              # next start
npm test               # vitest run
npm run typecheck      # tsc --noEmit
npm run lint           # eslint
```
Gate before PR: `npm run typecheck && npm run lint && npm test && npm run build`.

## Structure
- `src/app/` — App Router: `api/` (route handlers), `gates/` (map + gate detail/control screens), `login/`, `globals.css`.
- `public/`, `next.config.ts`, `postcss.config.mjs`, `eslint.config.mjs`.

## Tests
Vitest (`npm test`). Add colocated tests alongside components/routes.

## Integration
- Talks to `scada-gate-control` REST API (`/api/gates/:id/status`, `/command-level`, `/horn`) and `services/auth` (login → JWT used against the backend).

## Gotchas / Watch-outs
- Next.js 16 + React 19 — **verify APIs against `node_modules/next/dist/docs/`**, don't assume older-Next behavior (async params, caching defaults, etc.).
- The frontend slices (map / gate detail / hardening / e2e) are **partially implemented** — confirm what exists before extending.
- `CLAUDE.md` (this file) and `AGENTS.md` coexist; keep the Next-16 warning in sync across both.
