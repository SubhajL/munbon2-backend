# Testing Water Level-Based Irrigation Control

## Overview
This guide provides comprehensive testing procedures for the water level-based irrigation control system that integrates with SCADA for gate control.

## System Components

### 1. AWD Control Service (Port 3013)
- Water level-based irrigation control
- SCADA gate integration
- Real-time monitoring
- Anomaly detection

### 2. SCADA Database Integration
- Database: `db_scada` on 43.209.22.250
- Table: `tb_gatelevel_command`
- Gate levels: 1=closed, 2-4=open levels

### 3. Flow Monitoring Service (Port 3012)
- Hydraulic calculations
- Gate level determination
- Canal water level monitoring

## Testing Steps

### Step 1: Verify Database Connectivity

```bash
# Test SCADA database connection
PGPASSWORD=P@ssw0rd123! psql -h 43.209.22.250 -U postgres -d db_scada -c "\dt"

# Check gate command table
PGPASSWORD=P@ssw0rd123! psql -h 43.209.22.250 -U postgres -d db_scada -c "\d tb_gatelevel_command"

# List available control sites
PGPASSWORD=P@ssw0rd123! psql -h 43.209.22.250 -U postgres -d db_scada -c "
SELECT stationcode, site_name 
FROM tb_site 
WHERE stationcode IS NOT NULL 
LIMIT 20;"
```

### Step 2: Map Fields to Station Codes

```sql
-- Connect to AWD database
PGPASSWORD=P@ssw0rd123! psql -h 43.209.22.250 -U postgres -d munbon_dev

-- Add field mappings
INSERT INTO awd.field_gate_mapping (field_id, station_code, max_flow_rate)
VALUES 
  ('your-field-uuid-1', 'WWA', 10.0),
  ('your-field-uuid-2', 'WWB', 8.0);

-- Verify mappings
SELECT f.name, fgm.station_code, fgm.max_flow_rate
FROM awd.awd_fields f
JOIN awd.field_gate_mapping fgm ON f.id = fgm.field_id;
```

### Step 3: Start Services

```bash
# Start AWD Control Service
cd /Users/subhajlimanond/dev/munbon2-backend/services/awd-control
npm run dev

# In another terminal, check health
curl http://localhost:3013/health
```

### Step 4: Test Gate Control

#### 4.1 Direct Database Test
```sql
-- Insert test gate command
INSERT INTO tb_gatelevel_command 
(gate_name, gate_level, startdatetime, completestatus)
VALUES ('WWA', 3, NOW(), 0);

-- Check command
SELECT * FROM tb_gatelevel_command 
WHERE gate_name = 'WWA' 
ORDER BY id DESC LIMIT 1;
```

#### 4.2 API Test - Start Irrigation
```bash
# Get auth token first (adjust based on your auth setup)
TOKEN="your-auth-token"
FIELD_ID="your-field-uuid"

# Start irrigation with target water level
curl -X POST http://localhost:3013/api/v1/awd/control/fields/$FIELD_ID/irrigation/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "targetLevelCm": 10,
    "toleranceCm": 1,
    "maxDurationMinutes": 360,
    "sensorCheckIntervalSeconds": 300,
    "minFlowRateCmPerMin": 0.05,
    "emergencyStopLevel": 15
  }'

# Response should include scheduleId
```

#### 4.3 Check Irrigation Status
```bash
# Get current irrigation status
curl http://localhost:3013/api/v1/awd/control/fields/$FIELD_ID/irrigation/status \
  -H "Authorization: Bearer $TOKEN"
```

#### 4.4 Monitor Gate Commands
```sql
-- Watch gate commands being created
PGPASSWORD=P@ssw0rd123! psql -h 43.209.22.250 -U postgres -d db_scada -c "
SELECT id, gate_name, gate_level, 
       startdatetime AT TIME ZONE 'Asia/Bangkok' as start_time,
       CASE completestatus 
         WHEN 0 THEN 'Pending'
         WHEN 1 THEN 'Complete'
       END as status
FROM tb_gatelevel_command 
WHERE startdatetime > NOW() - INTERVAL '1 hour'
ORDER BY id DESC;"
```

### Step 5: Test Monitoring

#### 5.1 Simulate Water Level Changes
```bash
# If using test sensors, update water level readings
# This depends on your sensor setup
```

#### 5.2 Check Monitoring Logs
```bash
# View service logs
docker logs awd-control-service -f

# Or if running locally
# Check console output for monitoring updates every 5 minutes
```

#### 5.3 Verify Anomaly Detection
```bash
# Check for anomalies in database
PGPASSWORD=P@ssw0rd123! psql -h 43.209.22.250 -U postgres -d munbon_dev -c "
SELECT * FROM awd.irrigation_anomalies 
WHERE detected_at > NOW() - INTERVAL '1 hour'
ORDER BY detected_at DESC;"
```

### Step 6: Test Stop Irrigation

```bash
# Stop irrigation
curl -X POST http://localhost:3013/api/v1/awd/control/fields/$FIELD_ID/irrigation/stop \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Testing complete"
  }'

# Verify gate close command
PGPASSWORD=P@ssw0rd123! psql -h 43.209.22.250 -U postgres -d db_scada -c "
SELECT * FROM tb_gatelevel_command 
WHERE gate_name = 'WWA' 
  AND gate_level = 1 
ORDER BY id DESC LIMIT 1;"
```

## Integration Testing Checklist

### Pre-requisites
- [ ] SCADA database accessible
- [ ] AWD database migrations applied
- [ ] Fields mapped to station codes
- [ ] Water level sensors configured
- [ ] Flow Monitoring Service URL configured

### Functionality Tests
- [ ] Service starts without errors
- [ ] Can connect to both databases
- [ ] API endpoints respond correctly
- [ ] Gate commands written to SCADA database
- [ ] Gate level calculation works
- [ ] Water level monitoring active
- [ ] Anomaly detection triggers
- [ ] Irrigation completion logic works
- [ ] Emergency stop functions

### Integration Points
- [ ] SCADA database writes successful
- [ ] Flow Monitoring Service callable
- [ ] Kafka events published
- [ ] Redis status tracking works
- [ ] Sensor data retrieval works

## Troubleshooting

### Common Issues

1. **Cannot connect to SCADA database**
   - Check network connectivity to 43.209.22.250
   - Verify credentials in .env file
   - Ensure firewall allows connection

2. **Gate commands not appearing**
   - Verify field has station code mapping
   - Check SCADA database permissions
   - Review service logs for errors

3. **Flow Monitoring Service errors**
   - Ensure service is running on port 3012
   - Check SERVICE_AUTH_TOKEN is configured
   - Verify FLOW_MONITORING_URL in .env

4. **No water level readings**
   - Check sensor configuration
   - Verify TimescaleDB connection
   - Ensure sensors are mapped to fields

## Performance Monitoring

```bash
# Monitor gate command throughput
PGPASSWORD=P@ssw0rd123! psql -h 43.209.22.250 -U postgres -d db_scada -c "
SELECT 
  DATE_TRUNC('hour', startdatetime) as hour,
  COUNT(*) as commands,
  SUM(CASE WHEN completestatus = 1 THEN 1 ELSE 0 END) as completed
FROM tb_gatelevel_command
WHERE startdatetime > NOW() - INTERVAL '24 hours'
GROUP BY 1
ORDER BY 1 DESC;"

# Check irrigation performance
PGPASSWORD=P@ssw0rd123! psql -h 43.209.22.250 -U postgres -d munbon_dev -c "
SELECT 
  field_id,
  AVG(total_duration_minutes) as avg_duration,
  AVG(water_volume_liters) as avg_volume,
  AVG(efficiency_score) as avg_efficiency
FROM awd.irrigation_performance
WHERE start_time > NOW() - INTERVAL '7 days'
GROUP BY field_id;"
```

## Next Steps

1. **Production Deployment**
   - Configure production database connections
   - Set up monitoring and alerting
   - Implement backup strategies

2. **Advanced Features**
   - Multi-gate coordination
   - Predictive control based on ML
   - Weather-based adjustments

3. **Integration Testing**
   - Full end-to-end testing with real gates
   - Load testing with multiple fields
   - Failure scenario testing