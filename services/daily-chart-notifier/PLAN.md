# Daily Chart Screenshot + Email Notification Service

## Overview

A TypeScript service that runs daily at 1:00 PM Bangkok time to:
1. Capture full-page screenshots of moisture and water level dashboards
2. Fetch last 24 hours of PM2 logs from EC2 via SSH
3. Send email with screenshots + logs to configured recipient

## Configuration (Environment Variables)

```env
# SMTP (Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=subhaj.limanond@gmail.com
SMTP_PASS=<app-password>
EMAIL_TO=subhaj.limanond@gmail.com
EMAIL_FROM=Munbon Daily Report <subhaj.limanond@gmail.com>

# SSH to EC2
SSH_HOST=43.208.201.191
SSH_USER=ubuntu
SSH_PORT=22
SSH_KEY_PATH=/path/to/key.pem

# Dashboard URLs
DASHBOARD_MOISTURE_URL=http://localhost:8080/frontend-moisture-graphs.html
DASHBOARD_WATER_LEVEL_URL=http://localhost:8080/frontend-water-level-graphs.html

# PM2 Log Path on EC2
PM2_LOG_PATH=~/.pm2/logs/moisture-sensor-out.log

# Timezone
TZ=Asia/Bangkok
```

## Files to Create

```
services/daily-chart-notifier/
├── package.json
├── tsconfig.json
├── ecosystem.config.js          # PM2 config
├── .env.example
├── README.md
├── src/
│   ├── index.ts                 # Entry point + scheduler
│   ├── config.ts                # Environment validation
│   ├── config.spec.ts           # Config tests
│   ├── types.ts                 # Type definitions
│   ├── screenshot.ts            # Puppeteer screenshot capture
│   ├── screenshot.spec.ts       # Screenshot tests
│   ├── log-fetcher.ts           # SSH log fetching
│   ├── log-fetcher.spec.ts      # Log fetcher tests
│   ├── email.ts                 # Nodemailer email sender
│   ├── email.spec.ts            # Email tests
│   ├── runner.ts                # Job orchestration
│   ├── runner.spec.ts           # Runner tests
│   └── utils/
│       ├── logger.ts            # Pino logger
│       ├── time.ts              # Bangkok timezone helpers
│       └── temp.ts              # Temp directory management
└── test/
    └── integration/
        └── full-flow.spec.ts    # Integration test (mocked external)
```

## Dependencies

```json
{
  "dependencies": {
    "node-cron": "^3.0.3",
    "nodemailer": "^6.9.7",
    "puppeteer": "^21.6.1",
    "ssh2": "^1.15.0",
    "date-fns": "^3.0.6",
    "date-fns-tz": "^2.0.0",
    "dotenv": "^16.3.1",
    "pino": "^8.16.2"
  },
  "devDependencies": {
    "@types/node": "^20.10.5",
    "@types/node-cron": "^3.0.11",
    "@types/nodemailer": "^6.4.14",
    "@types/ssh2": "^1.11.18",
    "typescript": "^5.3.3",
    "vitest": "^1.1.0"
  }
}
```

## Function Specifications

### `loadConfig()` - `src/config.ts`
Reads and validates environment variables. Returns a strongly-typed config object or throws on missing/invalid values. Provides sensible defaults for SMTP host/port.

### `captureScreenshots(urls: string[], outputDir: string)` - `src/screenshot.ts`
Launches headless Chromium via Puppeteer with `--no-sandbox` flags. Visits each URL, waits for network idle + 3s for charts to render, captures full-page PNG screenshots. Returns array of file paths. Closes browser on completion or error.

### `fetchPm2Logs(config: Config, since: Date)` - `src/log-fetcher.ts`
Connects to EC2 via SSH using key file. Executes command to extract log entries from last 24 hours (using `awk` with timestamp filtering or `tail` fallback). Returns log content as string. Handles connection errors gracefully.

### `sendEmail(config: Config, attachments: Attachment[])` - `src/email.ts`
Creates nodemailer transporter with Gmail SMTP settings. Composes email with:
- Subject: "Munbon Daily Report - {date}"
- Body: HTML summary with timestamp (Bangkok time)
- Attachments: Screenshots + log file
Sends to configured recipient. Logs success/failure.

### `runDailyJob(config: Config)` - `src/runner.ts`
Orchestrates the full workflow:
1. Create temp workspace
2. Capture screenshots (both dashboards)
3. Fetch PM2 logs from EC2
4. Build and send email
5. Cleanup temp files (always, even on error)
Returns success/failure status with error details.

### `scheduleDailyJob()` - `src/index.ts`
Registers node-cron job at `0 13 * * *` with timezone `Asia/Bangkok`. Exposes manual trigger for testing. Logs job registration and execution times.

## Test Specifications

### `config.spec.ts`
- `loadConfig throws on missing SMTP_PASS` - validates required env
- `loadConfig returns defaults for SMTP_HOST/PORT` - default values work
- `loadConfig parses all env vars correctly` - full config object shape

### `screenshot.spec.ts`
- `captureScreenshots launches browser once for multiple URLs` - efficiency
- `captureScreenshots saves PNG files to output directory` - file creation
- `captureScreenshots throws on navigation failure` - error handling
- `captureScreenshots waits for network idle before capture` - chart rendering

### `log-fetcher.spec.ts`
- `fetchPm2Logs connects with SSH key from config` - SSH auth
- `fetchPm2Logs extracts logs from last 24 hours` - time filtering
- `fetchPm2Logs handles SSH connection errors` - error propagation
- `fetchPm2Logs returns empty string for no matching logs` - edge case

### `email.spec.ts`
- `sendEmail uses Gmail SMTP settings` - transporter config
- `sendEmail attaches provided files` - attachment handling
- `sendEmail includes Bangkok timestamp in subject` - formatting
- `sendEmail throws on SMTP failure` - error handling

### `runner.spec.ts`
- `runDailyJob executes steps in correct order` - orchestration
- `runDailyJob cleans up temp files on success` - cleanup
- `runDailyJob cleans up temp files on error` - cleanup guarantee
- `runDailyJob surfaces errors with context` - error reporting

## Implementation Order (TDD)

### Phase 1: Foundation
1. **config.ts** - Write `config.spec.ts`, implement `loadConfig()`
2. **utils/time.ts** - Bangkok timezone helpers
3. **utils/temp.ts** - Temp directory creation/cleanup
4. **utils/logger.ts** - Pino logger setup

### Phase 2: Core Modules
5. **screenshot.ts** - Write `screenshot.spec.ts`, implement with Puppeteer
6. **log-fetcher.ts** - Write `log-fetcher.spec.ts`, implement with ssh2
7. **email.ts** - Write `email.spec.ts`, implement with nodemailer

### Phase 3: Orchestration
8. **runner.ts** - Write `runner.spec.ts`, implement orchestration
9. **index.ts** - Wire scheduler + entry point

### Phase 4: Deployment
10. **ecosystem.config.js** - PM2 configuration
11. **.env.example** - Environment template
12. **README.md** - Documentation

## PM2 Configuration

```javascript
// ecosystem.config.js
module.exports = {
  apps: [{
    name: 'daily-chart-notifier',
    script: 'dist/index.js',
    cwd: __dirname,
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '256M',
    env: {
      NODE_ENV: 'production',
      TZ: 'Asia/Bangkok'
    },
    // Cron handled internally by node-cron, not PM2 cron
  }]
};
```

## Notes

- **Puppeteer on EC2**: May need to install Chrome dependencies (`apt-get install chromium-browser`)
- **SSH Key**: Must be readable by the service user
- **Gmail App Password**: Required for SMTP (not regular password)
- **Temp Files**: Stored in OS temp dir, cleaned after each run
- **Error Handling**: All errors logged with context, email failure doesn't crash service
