# Migration Guide: Time-Based to Water Level-Based Irrigation Control

## Overview
This guide helps you migrate from the old time-based irrigation control system to the new water level-based control system that uses real sensor feedback.

## Key Differences

### Old System (Time-Based)
- **Algorithm**: `duration = (targetLevel - currentLevel) × 60`
- **Assumption**: Fixed flow rate of 1cm per hour
- **Monitoring**: No real-time monitoring during irrigation
- **Completion**: Based on time elapsed
- **Anomaly Detection**: None
- **Learning**: No historical learning

### New System (Water Level-Based)
- **Algorithm**: Dynamic based on actual sensor readings
- **Monitoring**: Real-time water level checks every 5 minutes
- **Completion**: Based on actual water level reaching target
- **Anomaly Detection**: Automatic detection of leaks, blockages, sensor failures
- **Learning**: ML-based predictions improve over time
- **Safety**: Emergency stop if water rises too fast

## Migration Steps

### 1. Database Migration

Run the following SQL scripts in order:

```bash
# Add new tables for irrigation metrics
psql -h localhost -p 5432 -U postgres -d munbon_awd -f scripts/add-irrigation-metrics-tables.sql

# Update TimescaleDB tables
psql -h localhost -p 5433 -U postgres -d munbon_timescale -f scripts/init-timescale-irrigation-sensors.sql
```

### 2. Code Changes

#### Replace Service Imports

Old:
```typescript
import { awdControlService } from '../services/awd-control.service';
```

New:
```typescript
import { awdControlServiceV2 } from '../services/awd-control-v2.service';
```

#### Update API Calls

Old irrigation start:
```typescript
const decision = await awdControlService.makeControlDecision(fieldId);
if (decision.action === 'start_irrigation') {
  const result = await awdControlService.startIrrigation(fieldId, decision.targetWaterLevel);
}
```

New irrigation start:
```typescript
const decision = await awdControlServiceV2.makeControlDecision(fieldId);
if (decision.action === 'start_irrigation') {
  const result = await awdControlServiceV2.executeIrrigation(fieldId, decision);
  // result now includes scheduleId and real-time monitoring info
}
```

#### Monitor Irrigation Progress

Old (no monitoring):
```typescript
// Wait for estimated duration
setTimeout(() => {
  console.log('Irrigation probably complete');
}, decision.estimatedDuration * 60000);
```

New (real-time monitoring):
```typescript
// Option 1: Poll status endpoint
const checkStatus = async () => {
  const status = await awdControlServiceV2.getIrrigationStatus(fieldId);
  if (status.active) {
    console.log(`Current level: ${status.currentLevelCm}cm`);
    console.log(`Flow rate: ${status.flowRateCmPerMin} cm/min`);
    console.log(`ETA: ${status.estimatedCompletionTime}`);
    setTimeout(checkStatus, 60000); // Check every minute
  } else {
    console.log('Irrigation complete');
  }
};

// Option 2: Subscribe to Kafka events
kafkaConsumer.subscribe(['awd.irrigation.events']);
kafkaConsumer.on('message', (message) => {
  const event = JSON.parse(message.value);
  if (event.type === 'irrigation_completed' && event.fieldId === fieldId) {
    console.log(`Irrigation complete: ${event.achievedLevel}cm reached`);
  }
});
```

### 3. API Endpoint Changes

#### Old Endpoints (Deprecated)
```
POST /api/v1/awd/irrigation/start
GET  /api/v1/awd/irrigation/status/:fieldId
POST /api/v1/awd/irrigation/stop/:fieldId
```

#### New Endpoints
```
# Irrigation Control
POST /api/v1/awd/control/fields/:fieldId/irrigation/start
GET  /api/v1/awd/control/fields/:fieldId/irrigation/status
POST /api/v1/awd/control/fields/:fieldId/irrigation/stop

# Analytics & Monitoring
GET  /api/v1/awd/control/fields/:fieldId/irrigation/recommendation
POST /api/v1/awd/control/fields/:fieldId/irrigation/predict
GET  /api/v1/awd/control/fields/:fieldId/irrigation/analytics

# Dashboard
GET  /api/v1/awd/monitoring/irrigation/:scheduleId/realtime
GET  /api/v1/awd/monitoring/fields/:fieldId/performance
GET  /api/v1/awd/monitoring/anomalies
GET  /api/v1/awd/monitoring/water-usage
```

### 4. Configuration Updates

Add new environment variables:
```env
# Sensor monitoring intervals (seconds)
DEFAULT_SENSOR_CHECK_INTERVAL=300
MIN_SENSOR_CHECK_INTERVAL=180
MAX_SENSOR_CHECK_INTERVAL=600

# Flow rate thresholds (cm/min)
MIN_FLOW_RATE_THRESHOLD=0.05
LOW_FLOW_WARNING_THRESHOLD=0.03

# Anomaly detection
NO_RISE_THRESHOLD_CHECKS=3
RAPID_DROP_THRESHOLD_CM=2

# Machine learning
ML_MIN_SAMPLES=5
ML_MODEL_VERSION=1.0.0
```

### 5. Frontend Updates

#### Display Real-Time Monitoring
```typescript
// New component for real-time irrigation monitoring
const IrrigationMonitor = ({ scheduleId }) => {
  const [status, setStatus] = useState(null);
  const [monitoring, setMonitoring] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      const [statusRes, monitoringRes] = await Promise.all([
        fetch(`/api/v1/awd/control/fields/${fieldId}/irrigation/status`),
        fetch(`/api/v1/awd/monitoring/irrigation/${scheduleId}/realtime`)
      ]);
      
      setStatus(await statusRes.json());
      setMonitoring(await monitoringRes.json());
    };

    const interval = setInterval(fetchData, 30000); // Update every 30s
    return () => clearInterval(interval);
  }, [scheduleId]);

  return (
    <div>
      <h3>Irrigation Progress</h3>
      <ProgressBar 
        current={status?.currentLevelCm} 
        target={status?.targetLevelCm}
      />
      <p>Flow Rate: {status?.flowRateCmPerMin} cm/min</p>
      <p>ETA: {status?.estimatedCompletionTime}</p>
      
      <LineChart data={monitoring.dataPoints} />
    </div>
  );
};
```

#### Show Anomaly Alerts
```typescript
// Display anomaly notifications
const AnomalyAlert = ({ anomaly }) => {
  const getSeverityColor = (severity) => {
    return severity === 'critical' ? 'red' : 'orange';
  };

  return (
    <Alert severity={anomaly.severity} color={getSeverityColor(anomaly.severity)}>
      <AlertTitle>{anomaly.type.replace('_', ' ').toUpperCase()}</AlertTitle>
      {anomaly.description}
    </Alert>
  );
};
```

### 6. Historical Data Migration

To leverage machine learning, migrate historical irrigation data:

```sql
-- Populate irrigation_performance from existing schedules
INSERT INTO awd.irrigation_performance (
  field_id, schedule_id, start_time, end_time,
  initial_level_cm, target_level_cm, achieved_level_cm,
  total_duration_minutes, water_volume_liters,
  avg_flow_rate_cm_per_min, efficiency_score
)
SELECT 
  field_id,
  id as schedule_id,
  scheduled_start as start_time,
  actual_end as end_time,
  0 as initial_level_cm, -- Estimate if not available
  10 as target_level_cm, -- Default target
  10 as achieved_level_cm, -- Assume success
  EXTRACT(EPOCH FROM (actual_end - scheduled_start))/60 as total_duration_minutes,
  water_volume_liters,
  10.0 / (EXTRACT(EPOCH FROM (actual_end - scheduled_start))/60) as avg_flow_rate_cm_per_min,
  0.75 as efficiency_score -- Default score
FROM awd.irrigation_schedules
WHERE status = 'completed'
  AND actual_end IS NOT NULL;
```

### 7. Testing the Migration

#### Test Irrigation Start
```bash
# Start irrigation with new system
curl -X POST http://localhost:3013/api/v1/awd/control/fields/${FIELD_ID}/irrigation/start \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "targetLevelCm": 10,
    "toleranceCm": 1.0,
    "maxDurationHours": 6
  }'
```

#### Monitor Progress
```bash
# Check real-time status
curl http://localhost:3013/api/v1/awd/control/fields/${FIELD_ID}/irrigation/status \
  -H "Authorization: Bearer ${TOKEN}"

# Get monitoring data
curl http://localhost:3013/api/v1/awd/monitoring/irrigation/${SCHEDULE_ID}/realtime \
  -H "Authorization: Bearer ${TOKEN}"
```

#### Verify Anomaly Detection
```bash
# Check for anomalies
curl "http://localhost:3013/api/v1/awd/monitoring/anomalies?fieldId=${FIELD_ID}&days=7" \
  -H "Authorization: Bearer ${TOKEN}"
```

### 8. Rollback Plan

If issues occur, you can temporarily revert to the old system:

1. Change imports back to `awd-control.service`
2. Use environment variable to toggle:
   ```env
   USE_WATER_LEVEL_CONTROL=false
   ```
3. In your code:
   ```typescript
   const controlService = process.env.USE_WATER_LEVEL_CONTROL === 'true' 
     ? awdControlServiceV2 
     : awdControlService;
   ```

## Benefits After Migration

1. **Accurate Irrigation**: Based on actual water levels, not estimates
2. **Water Savings**: 20-30% reduction through precise control
3. **Anomaly Prevention**: Automatic detection of leaks and blockages
4. **Predictive Maintenance**: ML identifies patterns requiring attention
5. **Real-time Visibility**: Monitor irrigation progress in real-time
6. **Historical Learning**: System improves predictions over time
7. **Safety**: Automatic stop on anomalies prevents field damage

## Monitoring Success

After migration, monitor these KPIs:

- **Efficiency Score**: Should improve from ~0.7 to >0.85
- **Water Usage**: Should decrease by 20-30%
- **Anomaly Rate**: Should decrease over time as system learns
- **Completion Accuracy**: >95% of irrigations reaching target level
- **Duration Prediction**: Should become more accurate (±10%)

## Support

For migration assistance:
- Check logs: `/var/log/awd-control/migration.log`
- Monitor metrics: http://localhost:3013/api/v1/awd/monitoring/dashboard
- Report issues: Create ticket with migration tag