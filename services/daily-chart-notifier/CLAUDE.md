# daily-chart-notifier — scheduled dashboard report

**TypeScript 5.3 (strict) / Node 18+** · Entry: `src/index.ts` (node-cron scheduler) · **Extends [../../CLAUDE.md](../../CLAUDE.md)** · `@munbon/daily-chart-notifier` (PROPRIETARY)

## Purpose
Runs daily (13:00 Asia/Bangkok): captures Puppeteer full-page screenshots of the moisture + water-level dashboards, fetches ~24h of PM2 logs from EC2 over SSH, and delivers a report. **No HTTP server** (background scheduler only).

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
- 🚨 **`src/` and committed `dist/` are OUT OF SYNC.** `src/` is the **email/nodemailer** implementation; the committed `dist/` is a **Telegram** build (`dist/telegram.js`, requires `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`). There is **no `src/telegram.ts`** — running `npm run build` (`tsc`) will **overwrite the Telegram dist with the email version**. The email→telegram refactor is mid-flight (parked as a git stash). Decide the target channel before building/deploying.
- `dev` uses `ts-node` but **`ts-node` is not in devDependencies** — `npm run dev` fails unless it's installed.
- No `.eslintrc`/`.prettierrc` (CLI defaults); no Dockerfile (PM2 `ecosystem.config.js`).
- Hardcoded: cron schedule, viewport, 3s render wait, EC2 IP/paths in `.env.example` (`43.208.201.191`, key `th-lab01.pem`).
- Telegram path relies on Node18 globals (`fetch`/`FormData`/`Blob`) — no HTTP-client dep.
