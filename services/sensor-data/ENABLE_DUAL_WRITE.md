# Quick Start: Enable Dual-Write

## 1. Add EC2 credentials to your .env.local
```bash
# Add these lines to .env.local
ENABLE_DUAL_WRITE=true
EC2_DB_HOST=43.209.22.250
EC2_DB_PORT=5432
EC2_DB_NAME=sensor_data
EC2_DB_USER=postgres
EC2_DB_PASSWORD=P@ssw0rd123!
EC2_WRITE_TIMEOUT=5000
EC2_RETRY_ATTEMPTS=3
EC2_RETRY_DELAY=1000
```

## 2. Restart the consumer
```bash
# Stop current consumer (Ctrl+C)
# Start with dual-write enabled
npm run consumer
```

## 3. Monitor logs
Look for: `🔄 Initializing dual-write repository...`

## 4. Verify dual-write is working
```bash
npx ts-node scripts/test-dual-write.ts --monitor
```

## To Disable
Set `ENABLE_DUAL_WRITE=false` and restart consumer.