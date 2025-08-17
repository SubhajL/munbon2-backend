# Health Monitor Service

A comprehensive health monitoring service for the Munbon permanent tunnel and Unified API.

## Features

- **Real-time Monitoring**: Checks health of services every 5 minutes
- **Auto-restart**: Automatically restarts failed services via PM2
- **Web Dashboard**: Visual dashboard at http://localhost:3002
- **REST API**: Programmatic access to health status
- **Logging**: Detailed logs of all health checks and actions
- **Alerts**: Optional email and webhook notifications

## Services Monitored

1. **Cloudflare Tunnel** (munbon-api)
   - URL: https://munbon-api.beautifyai.io
   - Checks tunnel connectivity
   - Auto-restarts via PM2 if down

2. **Unified API**
   - URL: http://localhost:3000
   - Checks API health endpoint
   - Auto-restarts via PM2 if down

## Quick Start

```bash
# Start the health monitor
pm2 start pm2-health-monitor.json

# View the dashboard
open http://localhost:3002

# Check status via API
curl http://localhost:3002/status
```

## API Endpoints

- `GET /` - Web dashboard
- `GET /health` - Health monitor service health
- `GET /status` - Current status of monitored services
- `GET /logs` - Recent log entries
- `POST /check` - Trigger immediate health check
- `GET /config` - View current configuration

## Configuration

Edit `config/health-monitor.json`:

```json
{
  "checkInterval": 300000,      // 5 minutes
  "maxRetries": 3,
  "retryDelay": 30000,          // 30 seconds
  "email": {
    "enabled": false,
    "smtp": { ... },
    "to": "admin@example.com"
  },
  "webhook": {
    "enabled": false,
    "url": "https://hooks.slack.com/..."
  }
}
```

## PM2 Management

```bash
# View logs
pm2 logs health-monitor

# Restart
pm2 restart health-monitor

# Stop
pm2 stop health-monitor

# Remove
pm2 delete health-monitor
```

## Files

- `src/health-monitor.js` - Core monitoring logic
- `src/health-monitor-api.js` - REST API and dashboard
- `pm2-health-monitor.json` - PM2 configuration
- `config/health-monitor.json` - Service configuration
- `logs/health-monitor.log` - Health check logs

## Status Response Example

```json
{
  "timestamp": "2025-07-10T05:00:25.931Z",
  "services": {
    "tunnel": {
      "status": "up",
      "url": "https://munbon-api.beautifyai.io",
      "failureCount": 0
    },
    "api": {
      "status": "up",
      "url": "http://localhost:3000",
      "failureCount": 0
    }
  }
}
```

## Troubleshooting

### Port Already in Use
Default port is 3002. Change in PM2 config if needed:
```json
"env": {
  "HEALTH_MONITOR_PORT": "3003"
}
```

### Services Not Restarting
Ensure PM2 has permission to restart services:
```bash
pm2 list  # Check if services are managed by PM2
```

### False Positives
The monitor checks for HTTP 200, 401, or 404 responses. 401/404 still indicate the service is running.