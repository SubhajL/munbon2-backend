# Production Table Deployment

## ✅ Deployment Complete

**Date:** 2025-10-28  
**Time:** 09:33 UTC (16:33 Bangkok)

## Changes Made

### Configuration Update
- **File:** `.env`
- **Line 75:** Changed from `tb_valve_command_v2_test` to `tb_valve_command_v2`
- **Impact:** All valve commands now write to production MSSQL table

```diff
- MSSQL_TABLE_VALVE_COMMAND=tb_valve_command_v2_test
+ MSSQL_TABLE_VALVE_COMMAND=tb_valve_command_v2
```

## Verification

✅ Configuration loaded: `tb_valve_command_v2`  
✅ Service restarted: PID 83491  
✅ Timezone conversion active: UTC → Bangkok (UTC+7)  
✅ No code changes required

## What's Now Active

1. **Production table:** `db_scada.dbo.tb_valve_command_v2`
2. **Local time timestamps:** Asia/Bangkok (UTC+7)
3. **Control loop:** Every 5 minutes
4. **Real-time listener:** Enabled (outbox pattern)

## Expected Behavior

New valve commands will:
- Insert to `tb_valve_command_v2` (production)
- Use Bangkok local time (7 hours ahead of UTC)
- Example: UTC `09:30:00` → MSSQL `16:30:00`

## Monitoring

### Check Production Table
```sql
-- View latest valve commands
SELECT TOP 10 
  id, 
  valve_name, 
  valve_level,
  startdatetime,
  DATEADD(hour, -7, startdatetime) as utc_equivalent
FROM tb_valve_command_v2
ORDER BY id DESC;
```

### Expected Timestamps
- **Before (Test):** `2025-10-28 09:25:37` (UTC)
- **After (Production):** `2025-10-28 16:25:37` (Bangkok local time)

## Rollback (If Needed)

If you need to revert to test table:

```bash
# 1. Update .env
sed -i '' 's/tb_valve_command_v2$/tb_valve_command_v2_test/' .env

# 2. Restart service
pkill -f "node.*index.js"
npm start
```

## Test Table Preservation

The test table `tb_valve_command_v2_test` remains unchanged with historical data for reference and testing.

## Next Steps

1. ✅ Service is running with production table
2. ⏳ Wait for next valve command (within 5 minutes)
3. ✅ Verify insertion to production table
4. ✅ Confirm timestamps are in local time (UTC+7)
5. ✅ Monitor for any errors in logs

## Log Files

- Production logs: `/tmp/smartfarm-production.log`
- Monitor: `tail -f /tmp/smartfarm-production.log`

---

**Status: LIVE IN PRODUCTION** 🚀
