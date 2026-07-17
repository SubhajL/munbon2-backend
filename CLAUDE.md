# Munbon Irrigation Control System — Backend

## Overview
- **Type**: Polyglot microservices **monorepo** (each service is standalone; there is **no** root workspace, no Turborepo, no pnpm workspace).
- **Stack**: Node.js/TypeScript (~18 services) + Python/FastAPI (~9 services). No Go services are currently implemented despite historical planning docs.
- **Domain**: Automated water control for Thailand's Munbon Irrigation Project — demand planning → scheduling → gate hydraulics → SCADA/Modbus actuation, plus IoT sensor ingestion.
- **Orchestration**: PM2 (`infra/pm2/ecosystem-irrigation.config.js` + per-service `ecosystem*.config.js`); per-service Dockerfiles; deploy to EC2. Databases run as separate containers.
- **Shared code**: `shared/{nodejs,python,typescript-common}`.

**This CLAUDE.md is the authoritative, repo-wide source of development rules.** Active services carry their own `services/<name>/CLAUDE.md` that **extend** these rules with service-specific detail. When a service file and this file disagree, the service file wins *for that service only*.

> Note: the sibling root `AGENTS.md` historically held a generic imported template. Treat **this file** as canonical; `AGENTS.md` should be kept in sync (or reduced to a pointer to this file).

---

## Universal Development Rules

### Code Quality (MUST)
- **MUST** follow TDD: scaffold stub → write a failing test → implement (C-1).
- **MUST** name functions/vars with existing domain vocabulary for consistency (C-2).
- **MUST NOT** commit secrets, API keys, DB passwords, tokens, or production hostnames (see Security).
- **MUST** use Conventional Commits (GH-1): `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, …
- **MUST** make the language's type/lint/test gate pass before opening a PR (see Quality Gates).

### Best Practices (SHOULD)
- **SHOULD** prefer small, composable, testable functions over classes when they suffice (C-3, C-4).
- **SHOULD NOT** add comments except for critical caveats; rely on self-explanatory code (C-7).
- **SHOULD NOT** extract a new function unless it is reused, is the only way to unit-test otherwise-untestable logic, or drastically improves readability (C-9).
- **SHOULD** prefer integration tests over heavy mocking (T-4); unit-test complex algorithms thoroughly (T-5).

### Language-specific
- **TypeScript/Node**: strict mode; `import type { … }` for type-only imports (C-6); prefer branded `type`s for IDs (C-5); default to `type` over `interface` (C-8). Gate: `tsc --noEmit` + `eslint` + `prettier --check` + tests.
- **Python/FastAPI**: type hints on public functions; keep pure hydraulic/domain logic in `core/` free of I/O so it is unit-testable; DB/network access lives in `services/`/`repository/`. Gate: `pytest` (+ `ruff`/`flake8` where configured).

### Anti-Patterns (MUST NOT)
- **MUST NOT** push directly to `main` — branch, PR, admin-merge (see Git Workflow).
- **MUST NOT** introduce a second copy of an existing algorithm (this repo already suffers from divergent duplicate implementations — consolidate, don't fork).
- **MUST NOT** silently hardcode operational constants (levels, capacities, credentials) where real data exists — fail closed and log instead.

---

## Core Commands

There is **no** root build. Operate **per service** from its own directory.

### Node/TypeScript services (npm)
```bash
npm install
npm run dev          # ts-node / nodemon (varies per service)
npm run build        # tsc -> dist/
npm start            # node dist/index.js (or dist/cmd/server/main.js)
npm test             # vitest run  OR  jest  (varies)
npm run lint         # eslint
npx tsc --noEmit     # typecheck (some services expose `npm run typecheck`)
npx prettier --check "src/**/*.ts"
```

### Python services (venv + pytest)
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pytest -v                      # tests (usually tests/unit/test_*.py)
uvicorn src.main:app --reload  # FastAPI dev (path varies per service)
```

### Orchestration / deploy
```bash
pm2 start ecosystem.config.js            # run a service's PM2 config
pm2 start infra/pm2/ecosystem-irrigation.config.js
docker build -t <svc> services/<svc>     # per-service Dockerfile (not all services have one)
```
CI: `.github/workflows/build-and-deploy.yml` is **manual** (`workflow_dispatch`) — it builds/pushes only changed `services/*` to EC2. Most other workflows are `.disabled`.

### Quality Gates (run before every PR, from the service dir)
- **Node**: `npx tsc --noEmit && npm run lint && npm test`
- **Python**: `pytest`

---

## Project Structure

```
munbon2-backend/
├── services/                      # 48 microservices (each standalone)
│   ├── flow-monitoring/           # Python/FastAPI — gate hydraulics, demand→gate control  → services/flow-monitoring/CLAUDE.md
│   ├── scada-gate-control/        # TS/Express — Modbus TCP gate actuation + audit         → services/scada-gate-control/CLAUDE.md
│   ├── scada-gate-control-web/    # Next.js 16 — SCADA operator UI                          → services/scada-gate-control-web/CLAUDE.md
│   ├── sensor-data/               # TS — IoT ingestion (SQS→TimescaleDB) + chart APIs       → services/sensor-data/CLAUDE.md
│   ├── daily-chart-notifier/      # TS — scheduled screenshot + notification                → services/daily-chart-notifier/CLAUDE.md
│   ├── bff-water-planning/        # Python — water-planning BFF                              → services/bff-water-planning/CLAUDE.md
│   ├── ros-gis-integration/       # Python — ROS/Excel demand → ros_gis pipeline            → services/ros-gis-integration/CLAUDE.md
│   └── … (41 more, older/less active)
├── shared/{nodejs,python,typescript-common}/   # shared libs
├── infra/pm2/                     # PM2 ecosystem configs
├── .github/workflows/             # CI (mostly manual/disabled)
├── docs/                          # documentation (git-ignored by a blanket docs/ rule — see .gitignore)
└── CLAUDE.md                      # this file
```

**Active services** (recent commits; have their own CLAUDE.md): flow-monitoring, scada-gate-control(-web), sensor-data, daily-chart-notifier, bff-water-planning, ros-gis-integration. The remaining ~41 are dormant/experimental — verify before relying on them.

---

## Quick Find
```bash
# A service's entry point
ls services/<svc>/src/index.ts services/<svc>/src/cmd/server/main.ts services/<svc>/src/main.py 2>/dev/null
# Node endpoints
rg -n "router\.(get|post|put|delete)|app\.(get|post)" services/<svc>/src
# FastAPI endpoints
rg -n "@(app|router)\.(get|post|put|delete)" services/<svc>/src
# Find duplicate/divergent implementations before adding a new one
rg -n "def <name>|function <name>|class <Name>" services/<svc>
```

---

## Security & Secrets (MUST)
This repo has a **history of committed production credentials** (the README documents a credential-cleaning event and mandates re-clone + `.env` rotation). Known live issues include hardcoded DB passwords / hosts / API keys in `services/bff-water-planning/scripts/` and `services/sensor-data/` committed files.

- **MUST NOT** commit credentials, tokens, production hostnames/IPs. Use `.env` (git-ignored) from each service's `.env.example`.
- **MUST** move any discovered hardcoded secret to env/secret-manager and flag it for rotation — do not just relocate it.
- **SHOULD** treat any credential ever committed as compromised → rotate.
- Before committing, scan the diff for secrets (a secret-scanning CI gate is a P0 remediation item).

---

## Git Workflow
- These local folders are **git worktrees of one repo** (`github.com/SubhajL/munbon2-backend`). `main` is the canonical branch.
- Branch from `main`: `fix/<id>-<slug>`, `feat/<slug>`, `docs/<slug>`.
- **Conventional Commits** (GH-1). One logical change per PR; keep PRs atomic and reviewable.
- Flow: **branch → push → open PR → admin merges to `origin/main` → land local `main` (`git switch main && git pull --ff-only`)**.
- **MUST NOT** `git push origin main` directly or force-push shared branches without explicit approval.
- Never `git reset --hard` a worktree that holds uncommitted work.

---

## Testing (MANDATORY — from project principles)
1. **No skipped tests, no "simpler"/"more flexible" substitute tests.** Implement the agreed test plan exactly.
2. **No mock data for integration paths.** Use real data/connections; if a dependency must be set up manually (DB, creds, fixtures), **stop and ask the user to provide it** — do not fabricate.
3. **Auto-fix → re-test loop** until the plan passes, without violating (1) and (2).

Pyramid: ~70% unit, ~20% integration, ~10% e2e. Write tests first for critical logic. Prefer real containers (Testcontainers) / real DBs over mocks. See the **Writing Tests Best Practices** checklist below.

---

## Available Tools & Permissions
- Standard bash (`rg`, `git`, `gh`, `node`/`npm`, `python`/`pytest`, `pm2`, `docker`).
- MCP servers configured this environment: Auggie (semantic code search), Codex (planning/review), Ref, Exa, others. **Note:** external AI aids (Auggie, Codex) may hit quota/usage limits — have a local fallback (the QCHECK checklists below, `/code-review`).
- ✅ Read/write code, run tests/linters/typecheckers. ❌ Edit `.env`/secrets, force-push, drop DBs, `git push origin main` — **ask first**.

---

## Specialized Context (subdirectory CLAUDE.md)
When working inside a service, read its file first:
- [services/flow-monitoring/CLAUDE.md](services/flow-monitoring/CLAUDE.md) — Python hydraulics / gate-flow / P0 remediation
- [services/scada-gate-control/CLAUDE.md](services/scada-gate-control/CLAUDE.md) — Modbus TCP actuation
- [services/scada-gate-control-web/CLAUDE.md](services/scada-gate-control-web/CLAUDE.md) — Next.js 16 operator UI
- [services/sensor-data/CLAUDE.md](services/sensor-data/CLAUDE.md) — IoT ingestion + chart APIs
- [services/daily-chart-notifier/CLAUDE.md](services/daily-chart-notifier/CLAUDE.md) — scheduled notifier
- [services/bff-water-planning/CLAUDE.md](services/bff-water-planning/CLAUDE.md) — water-planning BFF
- [services/ros-gis-integration/CLAUDE.md](services/ros-gis-integration/CLAUDE.md) — demand pipeline
- [services/scheduler/CLAUDE.md](services/scheduler/CLAUDE.md) — weekly scheduling / PR 4.2 foundation

---

## Writing Functions Best Practices
When evaluating whether a function is good, use this checklist:
1. Can you *honestly* follow what it does on one read? If yes, stop.
2. Is cyclomatic complexity high (many nested branches)? Then it's probably sketchy.
3. Would a standard data structure/algorithm (parser, tree, stack/queue) make it simpler and more robust?
4. Any unused parameters?
5. Any unnecessary type casts that could move to the arguments?
6. Is it testable without mocking core infra (DB/redis/network)? If not, can it be covered by an integration test?
7. Any hidden untested dependencies that could be factored into arguments?
8. Brainstorm 3 better names; is the current one the best and consistent with the codebase?

Do NOT extract a function unless: it's reused, it's the only way to unit-test otherwise-untestable logic, or the original is extremely hard to follow.

## Writing Tests Best Practices
1. Parameterize inputs; never embed unexplained literals like `42`/`"foo"`.
2. No test that can't fail for a real defect; no trivial asserts (`expect(2).toBe(2)`).
3. Test description must state exactly what the final `expect` verifies.
4. Compare to independent, pre-computed expectations or domain properties — never to the function's own output as oracle.
5. Follow the same lint/type/style rules as prod code.
6. Express invariants/axioms (commutativity, idempotence, round-trip) where practical.
7. Group unit tests under the function name.
8. Use `expect.any(...)` for variable ids.
9. Strong assertions over weak (`toEqual(1)` not `toBeGreaterThanOrEqual(1)`).
10. Test edge cases, realistic input, unexpected input, and boundaries.
11. Don't test conditions already caught by the type checker.

---

## Shortcuts
Invoke by typing the keyword.

### QNEW
> Understand all BEST PRACTICES in CLAUDE.md. Your code SHOULD ALWAYS follow them. Understand and follow the service's CLAUDE.md architecture.

### QPLAN
> Analyze similar parts of the codebase and check your plan is consistent with it, introduces minimal changes, and reuses existing code.

### QCODE
> Implement your plan and make new tests pass. Run the full test suite. Run the formatter and the type/lint gate.

### QCHECK
> You are a SKEPTICAL senior engineer. For every MAJOR change, run: (1) Writing Functions Best Practices, (2) Writing Tests Best Practices, (3) Implementation Best Practices. *(This is Codex-independent — run it directly.)*

### QCHECKF
> Skeptical review of every MAJOR function added/edited against Writing Functions Best Practices.

### QCHECKT
> Skeptical review of every MAJOR test added/edited against Writing Tests Best Practices.

### QUX
> As a human UX tester, output a prioritized list of scenarios to test for the feature you implemented.

### QGIT
> Stage all changes, commit with a Conventional Commits message, and push. (Do NOT push to `main`; open a PR.)
