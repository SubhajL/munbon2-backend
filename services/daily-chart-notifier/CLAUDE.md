# daily-chart-notifier — scheduled dashboard report

**TypeScript 5.3 (strict) / Node 18+** · Entry: `src/index.ts` (node-cron scheduler) · **Extends [../../CLAUDE.md](../../CLAUDE.md)** · `@munbon/daily-chart-notifier` (PROPRIETARY)

## Purpose
Current status: [Development completion register](../../docs/development/DEVELOPMENT_COMPLETION_REGISTER.md). Tracked TypeScript email is the source-of-truth channel, explicitly approved on 2026-11-02.

Schedules daily (13:00 Asia/Bangkok): captures Puppeteer screenshots, fetches a bounded PM2 line tail over SSH, and builds an email report. The intended last-24-hour window is **not yet enforced/proven** by that line tail; P04 owns truthful time-window/coverage semantics. **No HTTP server** (background scheduler only). No real notification is authorized by source work.

## Commands
```bash
npm install
RUN_IMMEDIATELY=true npm run dev   # ts-node src/index.ts, run once now
npm run build                      # tsc -> dist/   ⚠️ see dist gotcha below
npm start                          # node dist/index.js
npm test                           # vitest run (colocated *.spec.ts)
npm run type-check                 # tsc --noEmit
npm run lint                       # eslint src --ext .ts
```

## Structure (`src/`)
`index.ts` (cron `0 13 * * *`), `config.ts` (`loadConfig`, `ConfigError`), `runner.ts` (`runDailyJob`), `screenshot.ts` (Puppeteer 1920x1080 full-page), `log-fetcher.ts` (ssh2 `tail`, path-traversal guard), `email.ts` (nodemailer), `utils/{logger,time,temp}.ts` (Bangkok TZ, temp workspace).

## Tests
Vitest (`vitest.config.ts`, `include: src/**/*.spec.ts`, v8 coverage); colocated `*.spec.ts`. Run `npm test`.

## Config / Env
- Required: `SMTP_USER`, `SMTP_PASS`, `EMAIL_TO`, `SSH_HOST`, `SSH_USER`, `SSH_KEY_PATH`, `DASHBOARD_MOISTURE_URL`, `DASHBOARD_WATER_LEVEL_URL`, `PM2_LOG_PATH`.
- Defaults: `SMTP_HOST`=smtp.gmail.com, `SMTP_PORT`=587, `SSH_PORT`=22, `TZ`=Asia/Bangkok, `RUN_IMMEDIATELY`=false.

## Gotchas / Watch-outs
- **Artifact/source drift:** tracked `src/` implements email/nodemailer; this machine has an **ignored local** Telegram build, not tracked output, and no tracked `src/telegram.ts`. Preserve that local artifact separately before any later clean build. Do not copy compiled Telegram code into source, manipulate stashes, or adopt a hidden fallback. P03 must make tests/start/PM2 consume one reproducible email build from a clean checkout; output files are not a second source of truth.
- `dev` uses `ts-node` but **`ts-node` is not in devDependencies** — `npm run dev` fails unless it's installed.
- No `.eslintrc`/`.prettierrc` (CLI defaults); no Dockerfile (PM2 `ecosystem.config.js`).
- Hardcoded: cron schedule, viewport, 3s render wait, EC2 IP/paths in `.env.example` (`43.208.201.191`, key `th-lab01.pem`).
- The ignored local Telegram artifact is not part of the supported email runtime; do not infer a tracked runtime dependency or channel requirement from it.
