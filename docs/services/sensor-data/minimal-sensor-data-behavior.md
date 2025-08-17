# Minimal Sensor Data Behavior

## Summary
When moisture sensor data has a **non-zero sensor_id but missing sensor values**, the data **WILL BE SAVED** to `moisture_readings` table.

## Code Analysis

### 1. HTTP Endpoint Validation
- Only checks for empty payload or missing gateway ID
- Does NOT validate individual sensor fields

### 2. Consumer Processing (sqs-processor.ts)
```typescript
// Line 208-210: Only skips if sensor_id is empty or missing
if (!sensorData.sensor_id || sensorData.sensor_id === '') {
  logger.debug({ gatewayId }, 'Skipping empty sensor data');
  continue;
}
```

### 3. Data Handling (sqs-processor-helpers.ts)
```typescript
// Lines 68-69, 91-92: Missing values default to 0
humid_hi: parseFloat(sensorData.humid_hi) || 0,
humid_low: parseFloat(sensorData.humid_low) || 0,
```

### 4. Quality Score Calculation
```typescript
// Lines 117-118: Penalizes missing/zero values
if (isNaN(humidHi) || humidHi === 0) score -= 0.3;
if (isNaN(humidLow) || humidLow === 0) score -= 0.3;
```

## Tested Behavior

### Input Data
```json
{
  "gw_id": "0003",
  "sensor": [{
    "sensor_id": "0D",
    "sensor_date": "2025/08/01",
    "sensor_utc": "15:00:00"
    // No humid_hi, humid_low, temp values, etc.
  }]
}
```

### Result in moisture_readings
| Field | Value |
|-------|-------|
| sensor_id | 0003-0D |
| moisture_surface_pct | 0.00 |
| moisture_deep_pct | 0.00 |
| quality_score | 0.00 |

### Result in sensor_readings (raw data)
```json
{
  "humid_hi": 0,
  "humid_low": 0,
  "temp_hi": null,
  "temp_low": null,
  "amb_temp": null,
  "amb_humid": null,
  "sensor_batt": null
}
```

## Implications

1. **Data Integrity**: Sensors sending only sensor_id will create records with 0% moisture
2. **Quality Tracking**: Quality score correctly identifies poor data (0.00)
3. **No Data Loss**: All sensor transmissions are recorded, even if incomplete
4. **Potential Issues**: Could create misleading "0% moisture" readings if sensors malfunction

## Recommendation
Consider adding validation to skip sensors with no meaningful data (all values missing) to avoid false zero readings in the database.