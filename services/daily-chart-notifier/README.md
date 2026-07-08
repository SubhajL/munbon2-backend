# Daily Chart Notifier

Automated daily email notification service that captures dashboard screenshots and sends them with PM2 logs.

## Features

- Daily scheduled job at 1:00 PM Bangkok time
- Captures full-page screenshots of:
  - Moisture sensor monitoring dashboard
  - Water level monitoring dashboard
- Fetches last 24 hours of PM2 logs from EC2 via SSH
- Sends email with screenshots and logs attached

## Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

**Required Variables:**

| Variable | Description |
|----------|-------------|
| `SMTP_USER` | Gmail address |
| `SMTP_PASS` | Gmail App Password (not regular password) |
| `EMAIL_TO` | Recipient email address |
| `SSH_HOST` | EC2 instance IP |
| `SSH_KEY_PATH` | Path to SSH private key |
| `DASHBOARD_MOISTURE_URL` | URL to moisture dashboard |
| `DASHBOARD_WATER_LEVEL_URL` | URL to water level dashboard |
| `PM2_LOG_PATH` | Path to PM2 log file on EC2 |

### 3. Gmail App Password

To use Gmail SMTP, you need an App Password:

1. Enable 2-Factor Authentication on your Google account
2. Go to Security → 2-Step Verification → App passwords
3. Generate a new app password for "Mail"
4. Use this password for `SMTP_PASS`

### 4. Build

```bash
npm run build
```

## Running

### Development (with immediate execution)

```bash
RUN_IMMEDIATELY=true npm run dev
```

### Production (with PM2)

```bash
npm run build
pm2 start ecosystem.config.js
```

### Manual Trigger

```bash
RUN_IMMEDIATELY=true npm start
```

## Testing

```bash
npm test              # Run all tests
npm run test:watch    # Watch mode
npm run test:coverage # Coverage report
```

## Schedule

The job runs daily at 1:00 PM Bangkok time (UTC+7).

Cron expression: `0 13 * * *`

## Architecture

```
src/
├── index.ts         # Entry point + scheduler
├── config.ts        # Environment configuration
├── types.ts         # TypeScript types
├── runner.ts        # Job orchestration
├── screenshot.ts    # Puppeteer screenshot capture
├── log-fetcher.ts   # SSH log fetching
├── email.ts         # Nodemailer email sending
└── utils/
    ├── logger.ts    # Pino logger
    ├── time.ts      # Timezone utilities
    └── temp.ts      # Temp directory management
```

## Troubleshooting

### Puppeteer Issues on EC2

Install Chrome dependencies:

```bash
sudo apt-get update
sudo apt-get install -y chromium-browser
```

### SSH Connection Failed

- Verify SSH key permissions: `chmod 600 /path/to/key.pem`
- Ensure EC2 security group allows SSH from your IP
- Test SSH manually: `ssh -i /path/to/key.pem ubuntu@43.208.201.191`

### Gmail SMTP Error

- Ensure you're using an App Password, not your regular password
- Check that "Less secure app access" is not required (App Password bypasses this)
