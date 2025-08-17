# Effective Rainfall Implementation Update

## Overview

The current implementation uses a fixed 0.8 efficiency factor on raw rainfall data. However, the Thai Excel sheet provides pre-calculated monthly effective rainfall values that are crop-specific. This document outlines the changes needed to align with the Excel methodology.

## Key Changes

### 1. Monthly Effective Rainfall Values

The Excel sheet "ฝนใช้การรายวัน" provides monthly effective rainfall in mm:

#### Rice Effective Rainfall (Column C)
| Month | Thai | Value (mm) | Weekly (mm) |
|-------|------|-----------|-------------|
| 1 | มค. | 4.6 | 1.15 |
| 2 | กพ. | 20.5 | 5.13 |
| 3 | มีค. | 41.6 | 10.40 |
| 4 | เมย. | 65.8 | 16.45 |
| 5 | พค. | 152.1 | 38.03 |
| 6 | มิย. | 104.5 | 26.13 |
| 7 | กค. | 122.5 | 30.63 |
| 8 | สค. | 128.0 | 32.00 |
| 9 | กย. | 233.2 | 58.30 |
| 10 | ตค. | 152.1 | 38.03 |
| 11 | พย. | 31.0 | 7.75 |
| 12 | ธค. | 3.6 | 0.90 |
| **Total** | | **1,059.5** | |

#### Field Crops Effective Rainfall (Column H)
| Month | Thai | Value (mm) | Weekly (mm) |
|-------|------|-----------|-------------|
| 1 | มค. | 4.6 | 1.15 |
| 2 | กพ. | 16.5 | 4.13 |
| 3 | มีค. | 31.3 | 7.83 |
| 4 | เมย. | 42.3 | 10.58 |
| 5 | พค. | 67.6 | 16.90 |
| 6 | มิย. | 46.5 | 11.63 |
| 7 | กค. | 74.5 | 18.63 |
| 8 | สค. | 89.3 | 22.33 |
| 9 | กย. | 142.6 | 35.65 |
| 10 | ตค. | 81.8 | 20.45 |
| 11 | พย. | 21.4 | 5.35 |
| 12 | ธค. | 3.6 | 0.90 |
| **Total** | | **622.0** | |

### 2. Implementation Differences

#### Current Implementation (rainfall.service.ts)
```typescript
// Fixed efficiency factor for all crops
efficiencyFactor = 0.8

// Applied to raw rainfall
effectiveRainfall = totalRainfall * 0.8
```

#### New Implementation (effective-rainfall.service.ts)
```typescript
// Crop-specific monthly values from Excel
if (cropType === 'rice') {
  effectiveRainfall = riceMonthlyValue / 4  // Convert to weekly
} else {
  effectiveRainfall = fieldCropMonthlyValue / 4
}
```

### 3. Database Schema Addition

```sql
CREATE TABLE ros.effective_rainfall_monthly (
    id SERIAL PRIMARY KEY,
    aos_station VARCHAR(100),
    province VARCHAR(100),
    month INTEGER,
    crop_type VARCHAR(50), -- 'rice' or 'field_crop'
    effective_rainfall_mm DECIMAL(10,2),
    UNIQUE(aos_station, province, month, crop_type)
);
```

## Migration Steps

### Step 1: Run Database Migration
```bash
cd services/ros
psql -h localhost -p 5434 -U postgres -d munbon_ros -f scripts/add-effective-rainfall-table.sql
```

### Step 2: Update Water Demand Service

Replace the rainfall service call in `water-demand.service.ts`:

```typescript
// OLD CODE:
effectiveRainfall = await rainfallService.getWeeklyEffectiveRainfall(
  input.areaId,
  weekStartDate
);

// NEW CODE:
import { effectiveRainfallService } from './effective-rainfall.service';

const effectiveRainfallData = await effectiveRainfallService.getEffectiveRainfall(
  input.cropType,
  input.calendarWeek,
  input.calendarYear
);
effectiveRainfall = effectiveRainfallData.weeklyEffectiveRainfall;
```

### Step 3: Update Types

Add to `types/index.ts`:
```typescript
export type CropCategory = 'rice' | 'field_crop';
```

## Benefits of This Approach

1. **Accuracy**: Uses official Thai agricultural data instead of generic efficiency factor
2. **Crop-Specific**: Recognizes that rice fields handle rainfall differently than upland crops
3. **Consistency**: Matches the Excel calculations exactly
4. **Seasonal Variation**: Monthly values capture seasonal rainfall patterns

## Testing

### Verify Rice Calculation
```bash
# May (Month 5) - Rice
# Monthly: 152.1 mm
# Weekly: 152.1 / 4 = 38.03 mm

curl -X POST http://localhost:3047/api/v1/ros/demand/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "areaId": "PLOT-123",
    "cropType": "rice",
    "cropWeek": 5,
    "calendarWeek": 20,
    "calendarYear": 2025,
    "areaRai": 100,
    "areaType": "plot"
  }'
```

### Verify Field Crop Calculation
```bash
# May (Month 5) - Sugarcane
# Monthly: 67.6 mm
# Weekly: 67.6 / 4 = 16.90 mm

curl -X POST http://localhost:3047/api/v1/ros/demand/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "areaId": "PLOT-456",
    "cropType": "sugarcane",
    "cropWeek": 5,
    "calendarWeek": 20,
    "calendarYear": 2025,
    "areaRai": 100,
    "areaType": "plot"
  }'
```

## Notes

1. The Excel uses pre-calculated effective rainfall, not raw rainfall with efficiency factors
2. Field crops (corn, sugarcane) generally have lower effective rainfall than rice
3. Peak effective rainfall occurs during rainy season (May-October)
4. The system will fall back to hardcoded values if database is unavailable