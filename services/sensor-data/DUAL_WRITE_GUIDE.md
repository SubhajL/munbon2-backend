# Dual-Write Implementation Guide

## Overview
This guide explains how to enable and use the dual-write feature for sensor data ingestion, which allows writing to both local and EC2 databases simultaneously.

## Configuration

### 1. Environment Variables
Copy the settings from `.env.dual-write` to your `.env.local` file:

```bash
# Enable dual-write feature
ENABLE_DUAL_WRITE=true

# EC2 Database Configuration
EC2_DB_HOST=43.209.22.250
EC2_DB_PORT=5432
EC2_DB_NAME=sensor_data
EC2_DB_USER=postgres
EC2_DB_PASSWORD=P@ssw0rd123!

# EC2 Write Configuration
EC2_WRITE_TIMEOUT=5000      # 5 seconds timeout for EC2 writes
EC2_RETRY_ATTEMPTS=3        # Retry failed writes 3 times
EC2_RETRY_DELAY=1000        # Wait 1 second between retries
```

### 2. Feature Flag
- `ENABLE_DUAL_WRITE=true` - Enables dual-write mode
- `ENABLE_DUAL_WRITE=false` - Local writes only (default)

## Architecture

```
SQS Message → Consumer → DualWriteRepository
                              ├─→ Local TimescaleDB (Primary)
                              └─→ EC2 TimescaleDB (Secondary)
```

### Key Features:
1. **Local First**: Always writes to local database first
2. **EC2 Async**: EC2 writes are async with timeout protection
3. **Retry Logic**: Failed EC2 writes retry up to 3 times
4. **Non-blocking**: EC2 failures don't block local writes
5. **Monitoring**: Logs all write operations and failures

## Testing

### 1. Verify Table Structures
```bash
npx ts-node scripts/verify-table-structures.ts
```

### 2. Test Dual-Write
```bash
# One-time comparison
npx ts-node scripts/test-dual-write.ts

# Continuous monitoring
npx ts-node scripts/test-dual-write.ts --monitor
```

### 3. Enable Dual-Write
```bash
# Add to .env.local
echo "ENABLE_DUAL_WRITE=true" >> .env.local

# Start consumer with dual-write
npm run consumer
```

## Monitoring

### Check Logs
The consumer logs dual-write operations:
- `🔄 Initializing dual-write repository...` - Dual-write enabled
- `📝 Initializing single-write repository...` - Local only
- `Local write successful` - Local write completed
- `EC2 write successful` - EC2 write completed
- `EC2 write failed` - EC2 write failed (with retry info)

### Database Queries
```sql
-- Check recent data on both databases
-- Local (port 5433)
SELECT COUNT(*), MAX(time) FROM water_level_readings WHERE time > NOW() - INTERVAL '1 hour';

-- EC2 (port 5432)
SELECT COUNT(*), MAX(time) FROM water_level_readings WHERE time > NOW() - INTERVAL '1 hour';
```

## Rollback

To disable dual-write:
1. Set `ENABLE_DUAL_WRITE=false` in `.env.local`
2. Restart the consumer service

## Performance Considerations

1. **Network Latency**: EC2 writes add ~50-200ms latency
2. **Connection Pools**: 
   - Local: 20 connections max
   - EC2: 10 connections max
3. **Timeouts**: EC2 writes timeout after 5 seconds
4. **Retries**: Failed writes retry with exponential backoff

## Troubleshooting

### EC2 Connection Failed
- Check EC2 security group allows port 5432
- Verify EC2_DB_PASSWORD is correct
- Test connection: `psql -h 43.209.22.250 -p 5432 -U postgres -d sensor_data`

### Data Inconsistency
- Run `test-dual-write.ts` to compare databases
- Check consumer logs for EC2 write failures
- Verify both databases have same table structures

### High Latency
- Reduce EC2_WRITE_TIMEOUT if needed
- Monitor network connectivity to EC2
- Consider reducing EC2_RETRY_ATTEMPTS

## Migration Plan

### Phase 1: Testing (Current)
- Enable dual-write in development
- Monitor for consistency
- Measure performance impact

### Phase 2: Production Rollout
- Enable dual-write in production
- Monitor for 24-48 hours
- Verify data consistency

### Phase 3: Cutover
- Deploy services to EC2
- Switch to EC2-only writes
- Keep local as backup

## API Changes
No API changes required. The dual-write is transparent to clients.