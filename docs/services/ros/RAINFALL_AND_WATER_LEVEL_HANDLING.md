# Effective Rainfall and Water Level Handling in ROS Service

## Overview

The ROS service handles effective rainfall and water level as **optional parameters** that affect the net water demand calculation but not the gross water demand.

## 1. Effective Rainfall

### What is Effective Rainfall?
- **Definition**: The portion of rainfall that is actually available for crop use
- **Formula**: `Effective Rainfall = Total Rainfall × Efficiency Factor`
- **Default Efficiency Factor**: 0.8 (80%)

### How ROS Handles Effective Rainfall

#### Option 1: Client Provides Value
```json
POST /api/v1/ros/demand/calculate
{
  "areaId": "PLOT-123",
  "cropType": "rice",
  "cropWeek": 5,
  "areaRai": 100,
  "effectiveRainfall": 10  // mm - provided directly
}
```

#### Option 2: ROS Fetches from Database
If `effectiveRainfall` is not provided:
1. ROS calculates the week start date from `calendarWeek` and `calendarYear`
2. Calls `rainfallService.getWeeklyEffectiveRainfall()`
3. Checks for rainfall data in this order:
   - Manual rainfall data from database
   - Weather service API data (if configured)
   - Returns 0 if no data available

### Data Sources for Rainfall

#### 1. Manual Entry
```sql
-- Data stored in rainfall_data table
INSERT INTO rainfall_data (
  area_id, 
  date, 
  rainfall_mm, 
  effective_rainfall_mm, 
  source
) VALUES ('PLOT-123', '2025-05-01', 12.5, 10.0, 'manual');
```

#### 2. Weather Service API
```typescript
// Currently returns null - placeholder for future integration
// Would connect to Thai Meteorological Department API
private async getWeatherServiceRainfall(areaId: string, date: Date)
```

#### 3. Import Historical Data
```typescript
POST /api/v1/ros/rainfall/import
{
  "data": [
    {
      "areaId": "PLOT-123",
      "date": "2025-05-01",
      "rainfallMm": 12.5
    }
  ],
  "efficiencyFactor": 0.8  // Optional, default 0.8
}
```

### Weekly Effective Rainfall Calculation
```typescript
// For each day of the week
for (let i = 0; i < 7; i++) {
  dailyRainfall = getRainfallForDay(date + i);
  totalRainfall += dailyRainfall;
}
// Apply efficiency factor to weekly total
effectiveRainfall = totalRainfall * 0.8;
```

## 2. Water Level

### What is Water Level?
- **Definition**: Current water level measurement in meters
- **Reference**: Can be relative to local datum or mean sea level
- **Usage**: Informational - does NOT affect water demand calculations

### How ROS Handles Water Level

#### Option 1: Client Provides Value
```json
POST /api/v1/ros/demand/calculate
{
  "areaId": "PLOT-123",
  "cropType": "rice",
  "cropWeek": 5,
  "areaRai": 100,
  "waterLevel": 220  // meters - provided directly
}
```

#### Option 2: ROS Fetches from Database
If `waterLevel` is not provided:
1. Calls `waterLevelService.getCurrentWaterLevel()`
2. Gets the most recent water level measurement
3. Returns null if no data available

### Data Sources for Water Level

#### 1. Manual Measurement
```typescript
POST /api/v1/ros/water-level/save
{
  "areaId": "PLOT-123",
  "measurementDate": "2025-05-01",
  "measurementTime": "08:00:00",
  "waterLevelM": 220.5,
  "source": "manual"
}
```

#### 2. Sensor Data
```typescript
// Import from IoT sensors
POST /api/v1/ros/water-level/import
{
  "data": [
    {
      "sensorId": "WL-001",
      "areaId": "PLOT-123",
      "timestamp": "2025-05-01T08:00:00Z",
      "waterLevel": 220.5
    }
  ]
}
```

#### 3. SCADA Integration
```typescript
// Data from SCADA system
{
  "source": "scada",
  "sensorId": "SCADA-GATE-01"
}
```

## 3. Net Water Demand Calculation

### Formula
```
Net Water Demand = Gross Water Demand - Effective Rainfall
```

### Implementation
```typescript
// Gross water demand calculation (always calculated)
cropWaterDemandMm = (weeklyETo × kcValue) + percolation;

// Net water demand (only if rainfall data available)
if (effectiveRainfall !== undefined) {
  netWaterDemandMm = Math.max(0, cropWaterDemandMm - effectiveRainfall);
  netWaterDemandM3 = netWaterDemandMm × areaRai × 1.6;
}
```

### Example Calculation
```
Given:
- Gross Water Demand: 64.05 mm
- Effective Rainfall: 10 mm

Net Water Demand = 64.05 - 10 = 54.05 mm
Volume = 54.05 × 100 rai × 1.6 = 8,648 m³
```

## 4. Important Notes

### Water Level
- **Informational Only**: Water level does NOT affect water demand calculations
- **Use Cases**: 
  - Monitoring reservoir levels
  - Triggering alerts when below critical threshold
  - Historical tracking and reporting

### Effective Rainfall
- **Reduces Net Demand**: Directly subtracted from gross water demand
- **Cannot Be Negative**: `Math.max(0, demand - rainfall)`
- **Weekly Aggregation**: Sum of daily rainfall × efficiency factor

### Missing Data Handling
- **No Rainfall Data**: Returns gross water demand (no reduction)
- **No Water Level**: Returns null (no impact on calculations)
- **Both Missing**: Still calculates gross water demand successfully

## 5. API Response Examples

### With All Parameters
```json
{
  "cropWaterDemandMm": 64.05,      // Gross demand
  "cropWaterDemandM3": 10248.42,    // Gross volume
  "effectiveRainfall": 10,          // Provided/fetched
  "waterLevel": 220,                // Provided/fetched
  "netWaterDemandMm": 54.05,        // Net demand
  "netWaterDemandM3": 8648.42       // Net volume
}
```

### Without Rainfall/Water Level
```json
{
  "cropWaterDemandMm": 64.05,      // Gross demand
  "cropWaterDemandM3": 10248.42,    // Gross volume
  "effectiveRainfall": 0,           // No data
  "waterLevel": null,               // No data
  "netWaterDemandMm": 64.05,        // Same as gross
  "netWaterDemandM3": 10248.42      // Same as gross
}
```

## 6. Database Schema

### Rainfall Data Table
```sql
CREATE TABLE rainfall_data (
  id SERIAL PRIMARY KEY,
  area_id VARCHAR(100) NOT NULL,
  date DATE NOT NULL,
  rainfall_mm DECIMAL(10,2) NOT NULL,
  effective_rainfall_mm DECIMAL(10,2),
  source VARCHAR(50),
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(area_id, date)
);
```

### Water Level Data Table
```sql
CREATE TABLE water_level_data (
  id SERIAL PRIMARY KEY,
  area_id VARCHAR(100) NOT NULL,
  measurement_date DATE NOT NULL,
  measurement_time TIME,
  water_level_m DECIMAL(10,2) NOT NULL,
  reference_level VARCHAR(50),
  source VARCHAR(50),
  sensor_id VARCHAR(100),
  created_at TIMESTAMP DEFAULT NOW()
);
```

## Summary

1. **Both parameters are optional** - ROS can calculate water demand without them
2. **Effective rainfall** reduces net water demand when available
3. **Water level** is stored but doesn't affect calculations
4. **Data can come from**: manual entry, sensors, weather API, or be provided by client
5. **Missing data** is handled gracefully with appropriate defaults