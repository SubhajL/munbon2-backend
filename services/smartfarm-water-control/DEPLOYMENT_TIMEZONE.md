# Timezone Conversion Deployment Guide

## ✅ Pre-Deployment Checklist

- [x] Code committed and pushed to `feature/smartfarm-debug`
- [x] All tests passing (16 timezone tests + 4 valve command tests)
- [x] Test script created (`test-timezone-conversion.js`)
- [ ] Merge to main branch (or deploy from feature branch)
- [ ] SSH access to production server confirmed

## 🚀 Deployment Steps

### Step 1: Connect to Production Server

```bash
# Replace with your actual server details
ssh user@production-server

# Navigate to application directory
cd /path/to/munbon2-backend-smartfarm/services/smartfarm-water-control
```

### Step 2: Backup Current Code

```bash
# Create backup of current version
git branch backup-before-timezone-$(date +%Y%m%d-%H%M%S)
```

### Step 3: Pull Latest Changes

```bash
# Pull the timezone conversion changes
git fetch origin
git checkout feature/smartfarm-debug  # or main if merged
git pull origin feature/smartfarm-debug
```

### Step 4: Install Dependencies (if needed)

```bash
npm install
```

### Step 5: Update Environment Variables

Check `.env` file has TIMEZONE set (optional, defaults to Asia/Bangkok):

```bash
# Add to .env if not present
echo "TIMEZONE=Asia/Bangkok" >> .env
```

### Step 6: Test the Conversion Locally on Server

```bash
# Run test script to verify timezone conversion
node test-timezone-conversion.js

# Expected output should show:
# UTC: 2025-10-28T08:23:48Z → Local: 2025-10-28 15:23:48
# Offset verification: +7 hours
```

### Step 7: Run Unit Tests

```bash
# Verify all tests pass
npm test -- src/utils/__tests__/timezone.spec.js
npm test -- src/services/__tests__/valveCommandService.spec.js
```

### Step 8: Restart the Service

```bash
# Option A: If using PM2
pm2 restart smartfarm-water-control

# Option B: If using systemd
sudo systemctl restart smartfarm-water-control

# Option C: If using nodemon/manual
# Kill existing process and restart
pkill -f "node.*smartfarm-water-control"
npm start

# Option D: If using worker script
pkill -f "listen-worker"
npm run worker
```

### Step 9: Verify Service is Running

```bash
# Check process is running
ps aux | grep smartfarm

# Check logs for startup
tail -f logs/smartfarm-water-control.log  # adjust path as needed

# Or if using PM2
pm2 logs smartfarm-water-control
```

### Step 10: Monitor First Valve Command

Watch for the next valve command to be inserted into MSSQL:

```sql
-- Connect to MSSQL db_scada database
SELECT TOP 5
  id,
  valve_name,
  valve_level,
  startdatetime,
  DATEADD(hour, -7, startdatetime) as utc_equivalent
FROM tb_valve_command_v2_test
ORDER BY id DESC;
```

**Expected result:** 
- `startdatetime` should now be ~7 hours ahead of UTC
- Example: If current UTC is `09:00:00`, `startdatetime` should show `16:00:00`

## ✅ Post-Deployment Verification

- [ ] Service started successfully
- [ ] No errors in logs
- [ ] First valve command shows local time (UTC+7)
- [ ] Application logs show correct timestamps
- [ ] No disruption to existing functionality

## 🔄 Rollback Plan (if needed)

If something goes wrong:

```bash
# Stop the service
pm2 stop smartfarm-water-control
# or
sudo systemctl stop smartfarm-water-control

# Revert to backup branch
git checkout backup-before-timezone-*

# Restart service
pm2 start smartfarm-water-control
# or
sudo systemctl start smartfarm-water-control
```

## 📊 Monitoring

After deployment, monitor for 24 hours:

1. Check valve command timestamps in MSSQL are consistently UTC+7
2. Verify no timezone-related errors in application logs
3. Confirm SCADA system receives and processes commands correctly
4. Check water control operations are functioning normally

## 🆘 Troubleshooting

### Issue: Timestamps still showing UTC

**Cause:** Old code still running or service not restarted

**Solution:**
```bash
# Verify correct code version
grep "convertUTCToLocalTime" src/services/valveCommandService.js

# Force kill and restart
pkill -9 -f smartfarm
npm start
```

### Issue: "Cannot find module './utils/timezone'"

**Cause:** New files not deployed

**Solution:**
```bash
# Verify files exist
ls -la src/utils/timezone.js
ls -la src/utils/__tests__/timezone.spec.js

# Re-pull if missing
git pull --force
```

### Issue: Wrong offset (not +7 hours)

**Cause:** TIMEZONE env variable set incorrectly

**Solution:**
```bash
# Check current setting
grep TIMEZONE .env

# Should be: TIMEZONE=Asia/Bangkok
# If different, fix and restart
```

## 📝 Notes

- **Breaking Change:** This is a breaking change. New timestamps will be in local time.
- **Data Migration:** Old UTC timestamps in MSSQL remain unchanged. No migration needed.
- **Backwards Compatibility:** None provided. All new inserts use local time.
- **Testing:** Test script available at `test-timezone-conversion.js`
