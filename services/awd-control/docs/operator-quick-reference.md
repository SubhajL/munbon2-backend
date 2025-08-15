# AWD Control Operator Quick Reference

## System Overview
- **NO PUMPS** - System uses gate control only
- Water level sensors monitor field conditions
- Gates automatically adjust based on targets
- 5-minute monitoring intervals

## Gate Control Levels
| Level | Status | Typical Use |
|-------|--------|-------------|
| 1 | Closed | Stop irrigation |
| 2 | Level 1 | Light flow (3-5 m³/s) |
| 3 | Level 2 | Normal flow (6-8 m³/s) |
| 4 | Level 3 | Heavy flow (9-12 m³/s) |

## Common Operations

### Start Irrigation
```bash
curl -X POST http://localhost:3013/api/v1/awd/control/fields/{fieldId}/irrigation/start \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "targetLevelCm": 10,
    "targetFlowRate": 7.5
  }'
```

### Check Status
```bash
curl http://localhost:3013/api/v1/awd/control/fields/{fieldId}/irrigation/status \
  -H "Authorization: Bearer {token}"
```

### Emergency Stop
```bash
curl -X POST http://localhost:3013/api/v1/awd/control/fields/{fieldId}/irrigation/stop \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Emergency stop"}'
```

## Monitoring Commands

### Check Gate Commands
```sql
-- Recent gate commands
SELECT id, gate_name, gate_level, 
       startdatetime AT TIME ZONE 'Asia/Bangkok' as time,
       CASE completestatus 
         WHEN 0 THEN 'Pending'
         WHEN 1 THEN 'Complete'
       END as status
FROM tb_gatelevel_command 
ORDER BY id DESC LIMIT 10;
```

### View Active Irrigations
```bash
curl http://localhost:3013/api/v1/awd/control/irrigation/active \
  -H "Authorization: Bearer {token}"
```

### Check Anomalies
```bash
curl http://localhost:3013/api/v1/awd/control/anomalies/recent \
  -H "Authorization: Bearer {token}"
```

## Anomaly Types
- **low_flow** - Flow rate too slow (Warning)
- **no_rise** - Water not rising after 15 min (Critical)
- **rapid_drop** - Possible leak detected (Critical)
- **sensor_failure** - Cannot read sensors (Critical)
- **overflow_risk** - Level exceeding target (Critical)

## Emergency Procedures

### 1. Sensor Failure
- System continues with last known values
- Manual gate control may be needed
- Check sensor connections

### 2. No Water Rise
- Check canal water availability
- Verify gate actually opened
- Look for blockages

### 3. Rapid Water Drop
- Stop irrigation immediately
- Check for field breaches
- Inspect distribution channels

### 4. Gate Not Responding
- Check SCADA system status
- Verify command in database
- Use manual override if available

## Database Checks

### Verify Gate Mapping
```sql
SELECT f.name, fgm.station_code 
FROM awd.awd_fields f
LEFT JOIN awd.field_gate_mapping fgm ON f.id = fgm.field_id;
```

### Check Irrigation History
```sql
SELECT 
  field_id,
  scheduled_start,
  actual_end,
  target_level_cm,
  final_level_cm,
  status
FROM awd.irrigation_schedules
WHERE scheduled_start > NOW() - INTERVAL '24 hours'
ORDER BY scheduled_start DESC;
```

### Monitor Performance
```sql
SELECT 
  DATE(start_time) as date,
  COUNT(*) as irrigations,
  AVG(efficiency_score) as avg_efficiency
FROM awd.irrigation_performance
WHERE start_time > NOW() - INTERVAL '7 days'
GROUP BY 1
ORDER BY 1 DESC;
```

## Service Health

### Check Service Status
```bash
# Health check
curl http://localhost:3013/health

# Detailed status
curl http://localhost:3013/api/v1/awd/control/system/status \
  -H "Authorization: Bearer {token}"
```

### View Logs
```bash
# If using PM2
pm2 logs awd-control

# If using Docker
docker logs awd-control-service -f --tail 100

# Direct log file
tail -f /var/log/awd-control/app.log
```

## Contact Information
- **System Admin**: [Your contact]
- **SCADA Support**: [SCADA team contact]
- **Emergency**: [24/7 contact]

## Important Notes
1. System monitors every 5 minutes
2. Gates may take 5-10 minutes to fully open/close
3. Always verify critical commands in SCADA
4. Keep field-to-gate mappings updated
5. NO PUMP CONTROLS - gates only