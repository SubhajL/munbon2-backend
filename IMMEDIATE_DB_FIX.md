# IMMEDIATE DATABASE CONNECTION FIX - Quick Start

## 🚨 Emergency Steps (Do Now)

### Step 1: Check Current Connection Status

```bash
# Set your AWS RDS credentials
export TIMESCALE_HOST="your-aws-rds-endpoint.rds.amazonaws.com"
export TIMESCALE_USER="postgres"
export TIMESCALE_PASSWORD="your-password"

# Check current connections
./scripts/check-db-connections.sh munbon_dev
```

### Step 2: Kill Idle Connections (If Maxed Out)

```bash
# Review what will be killed first
./scripts/kill-idle-connections.sh 10 munbon_dev
# This will ask for confirmation before proceeding
```

### Step 3: Update Production Environment Files

Update the following `.env` files on your production servers:

**services/bff-water-planning/.env**
```bash
DB_POOL_MIN_SIZE=2
DB_POOL_MAX_SIZE=5
```

**services/gis/.env** (if not using environment variables)
```bash
DB_POOL_SIZE=5
```

### Step 4: Restart Services

```bash
# Restart bff-water-planning
pm2 restart bff-water-planning

# Restart gis service
pm2 restart gis

# Restart smartfarm-water-control
pm2 restart smartfarm-water-control
```

### Step 5: Monitor Connections

```bash
# Watch in real-time
watch -n 5 './scripts/check-db-connections.sh munbon_dev'
```

## 📊 What Changed

### Connection Pool Reductions
- **bff-water-planning:** 20 → 5 connections (75% reduction)
- **gis:** 20 → 5 connections (75% reduction)
- **smartfarm-water-control:** 10 → 5 connections (50% reduction)

### Added Features
- Connection recycling every 1 hour
- Statement timeout: 60 seconds
- Idle transaction timeout: 5 minutes
- Application name tracking

## 🔧 AWS RDS Configuration (Do Within 24 Hours)

### Increase max_connections

```bash
# List your parameter groups
./scripts/increase-rds-max-connections.sh

# Set max_connections to 200
./scripts/increase-rds-max-connections.sh 200 your-parameter-group-name
```

### Apply Additional Parameters

Create `rds-parameters.json`:
```json
[
  {
    "ParameterName": "max_connections",
    "ParameterValue": "200",
    "ApplyMethod": "immediate"
  },
  {
    "ParameterName": "idle_in_transaction_session_timeout",
    "ParameterValue": "300000",
    "ApplyMethod": "immediate"
  },
  {
    "ParameterName": "statement_timeout",
    "ParameterValue": "60000",
    "ApplyMethod": "immediate"
  },
  {
    "ParameterName": "log_connections",
    "ParameterValue": "1",
    "ApplyMethod": "immediate"
  },
  {
    "ParameterName": "log_disconnections",
    "ParameterValue": "1",
    "ApplyMethod": "immediate"
  }
]
```

Then apply:
```bash
aws rds modify-db-parameter-group \
  --db-parameter-group-name your-parameter-group \
  --parameters file://rds-parameters.json
```

## ✅ Verification Checklist

- [ ] Checked current connection count
- [ ] Killed idle connections (if needed)
- [ ] Updated production `.env` files
- [ ] Restarted affected services
- [ ] Verified services are running
- [ ] Connection count is below 50% of max
- [ ] Increased RDS max_connections to 200
- [ ] Applied additional RDS parameters
- [ ] Set up monitoring/alerts

## 📝 Files Modified

```
✅ services/bff-water-planning/.env.example
✅ services/bff-water-planning/src/db/database_manager.py
✅ services/gis/src/config/index.js
✅ services/smartfarm-water-control/src/config/database.js
✅ scripts/check-db-connections.sh (new)
✅ scripts/kill-idle-connections.sh (new)
✅ scripts/increase-rds-max-connections.sh (new)
✅ docs/DB_CONNECTION_FIXES.md (new)
```

## 🔍 Monitoring

### Quick Check Command
```bash
psql -h "$TIMESCALE_HOST" -U postgres -d munbon_dev -c "
SELECT 
  count(*) as connections,
  (SELECT setting FROM pg_settings WHERE name='max_connections') as max,
  round(count(*)::numeric / (SELECT setting::numeric FROM pg_settings WHERE name='max_connections') * 100, 1) as pct
FROM pg_stat_activity 
WHERE datname = 'munbon_dev';"
```

### By Application
```bash
psql -h "$TIMESCALE_HOST" -U postgres -d munbon_dev -c "
SELECT application_name, count(*) 
FROM pg_stat_activity 
WHERE datname = 'munbon_dev' 
GROUP BY application_name;"
```

## 🆘 Troubleshooting

### Still hitting max_connections?
1. Check which services are consuming most: `./scripts/check-db-connections.sh`
2. Look for connection leaks in specific apps
3. Consider deploying PgBouncer (see docs/DB_CONNECTION_FIXES.md)

### Services won't start?
1. Check logs: `pm2 logs service-name`
2. Verify environment variables are set
3. Test database connectivity manually

### Performance issues?
1. Pool sizes may be too small for workload
2. Gradually increase by 1-2 connections per service
3. Monitor query queue times

## 📚 Full Documentation

See `docs/DB_CONNECTION_FIXES.md` for:
- Detailed analysis
- Long-term solutions
- Best practices
- Troubleshooting guide

---

**Priority:** 🚨 CRITICAL  
**Time to complete:** 15-30 minutes  
**Impact:** Immediate relief from connection exhaustion
