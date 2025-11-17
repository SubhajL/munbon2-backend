# Water Demand Calculation System - Complete Documentation

## Overview

The water demand calculation system computes irrigation water requirements for agricultural plots based on FAO-56 methodology, combining evapotranspiration (ET0), crop coefficients (Kc), effective rainfall, and plot-specific parameters.

## Core Formula

```
Gross Water Demand (mm) = (ET0 × Kc) + Percolation
Net Water Demand (mm) = Gross Water Demand - Effective Rainfall
Net Water Demand (m³) = Net Water Demand (mm) × Area (rai) × 1.6
```

### Constants
- **Percolation**: 14 mm/week (for ROS service)
- **Rai to m³ conversion**: 1.6 (1 mm of water on 1 rai = 1.6 m³)

---

## System Architecture

### Services Involved

1. **smartfarm-water-control** - Main orchestrator for smart farm plots
2. **ros** - ROS (Regional Office for the Standard) water demand service
3. **bff-water-planning** - Backend-for-frontend planning service
4. **ros-gis-integration** - GIS integration and spatial calculations

---

## Data Flow

```
┌────────────────┐
│  Plot Request  │
│  (plotId, date)│
└───────┬────────┘
        │
        ↓
┌───────────────────────────────────┐
│ 1. Retrieve Plot Configuration    │
│    - crop_type                     │
│    - planting_date                 │
│    - area_rai                      │
│    - control_mode (AWD/MOISTURE)   │
└───────┬───────────────────────────┘
        │
        ↓
┌───────────────────────────────────┐
│ 2. Calculate Crop Week            │
│    crop_week = (current_date      │
│      - planting_date) / 7 + 1     │
└───────┬───────────────────────────┘
        │
        ↓
┌───────────────────────────────────┐
│ 3. Retrieve ET0 (Evapotranspiration)│
│    Source: ros_smartfarm.eto_weekly│
│    Params: calendar_week, year,    │
│            aos_station, province   │
└───────┬───────────────────────────┘
        │
        ↓
┌───────────────────────────────────┐
│ 4. Retrieve Kc (Crop Coefficient) │
│    Join: crop_ros_mapping +       │
│          kc_weekly                 │
│    Params: crop_type, crop_week   │
└───────┬───────────────────────────┘
        │
        ↓
┌───────────────────────────────────┐
│ 5. Retrieve Effective Rainfall    │
│    Source: weekly_effective_rainfall│
│    Params: zone_id, week, year    │
└───────┬───────────────────────────┘
        │
        ↓
┌───────────────────────────────────┐
│ 6. Calculate Water Demand         │
│    gross_mm = ET0 × Kc            │
│    net_mm = gross_mm - rainfall   │
│    demand_m3 = net_mm × area × 1.6│
└───────┬───────────────────────────┘
        │
        ↓
┌───────────────────────────────────┐
│ 7. Store Result                   │
│    Table: daily_water_demands     │
└───────────────────────────────────┘
```

---

## Component Details

### 1. Plot Configuration Retrieval

**Source**: `water_control_smartfarm.plot_configurations`

**Code**: `waterPlanningService.js:51-79`

```javascript
// Retrieve from database
SELECT planting_date FROM plot_configurations WHERE plot_id = $1
SELECT area_rai FROM v_plot_configurations_enriched WHERE plot_id = $1
```

**Data Retrieved**:
- `planting_date` (DATE) - When the crop was planted
- `area_rai` (DECIMAL) - Plot area in rai (1 rai = 1,600 m²)
- `crop_type` (VARCHAR) - Specific crop variety (e.g., "ทุเรียน กล้วย")

**Example**:
```json
{
  "plotId": "SF-U1",
  "plantingDate": "2025-09-10",
  "areaRai": 2.51,
  "cropType": "ทุเรียน กล้วย"
}
```

---

### 2. Crop Week Calculation

**Code**: `waterPlanningService.js:27-33`

```javascript
calculateCropWeek(plantingDate, currentDate) {
  const start = new Date(plantingDate);
  const cur = new Date(currentDate);
  const days = Math.floor((cur.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
  if (days < 0) return null;
  return Math.floor(days / 7) + 1;
}
```

**Formula**: 
```
crop_week = floor((current_date - planting_date) / 7) + 1
```

**Example**:
```
Planting Date: 2025-09-10
Current Date:  2025-10-22
Days elapsed:  42 days
Crop Week:     floor(42 / 7) + 1 = 7
```

---

### 3. ET0 (Reference Evapotranspiration) Retrieval

**Source**: `ros_smartfarm.eto_weekly`

**Code**: `timescaleRepository.js:833-841`

```javascript
async getEt0FromRosSmartfarm(calendarWeek, calendarYear, aosStation, province) {
  const q = `
    SELECT eto_value FROM ros_smartfarm.eto_weekly
    WHERE aos_station = $1 AND province = $2 
      AND calendar_week = $3 AND calendar_year = $4
  `;
  const { rows } = await this.pool.query(q, [aosStation, province, calendarWeek, calendarYear]);
  return parseFloat(rows[0].eto_value);
}
```

**Parameters**:
- `aos_station`: 'นครราชสีมา' (Nakhon Ratchasima)
- `province`: 'นครราชสีมา'
- `calendar_week`: ISO week number (1-52)
- `calendar_year`: Year (e.g., 2025)

**Data Structure**:
```sql
TABLE ros_smartfarm.eto_weekly (
  aos_station VARCHAR,
  province VARCHAR,
  calendar_week INT,
  calendar_year INT,
  eto_value DECIMAL  -- mm/week
)
```

**Example Query**:
```sql
SELECT eto_value FROM ros_smartfarm.eto_weekly
WHERE aos_station = 'นครราชสีมา' 
  AND province = 'นครราชสีมา'
  AND calendar_week = 43 
  AND calendar_year = 2025;
-- Returns: 4.5 mm/day → ~31.5 mm/week
```

**Fallback**: If not found, defaults to `4.5 mm/day`

---

### 4. Kc (Crop Coefficient) Retrieval

**Source**: `ros_smartfarm.kc_weekly` + `ros_smartfarm.crop_ros_mapping`

**Code**: `timescaleRepository.js:809-831`

```javascript
async getKcFromRosSmartfarm(cropType, cropWeek) {
  const q = `
    SELECT kc.kc_value 
    FROM ros_smartfarm.kc_weekly kc
    JOIN ros_smartfarm.crop_ros_mapping crm ON kc.ros_type = crm.ros_type
    WHERE crm.crop_type = $1 AND kc.crop_week = $2
    LIMIT 1
  `;
  const { rows } = await this.pool.query(q, [cropType, cropWeek]);
  
  // If not found, try first crop from multi-crop string
  if (!rows.length) {
    const firstCrop = cropType.split(' ')[0];
    if (firstCrop !== cropType) {
      const { rows: retryRows } = await this.pool.query(q, [firstCrop, cropWeek]);
      if (retryRows.length) return parseFloat(retryRows[0].kc_value);
    }
    throw new Error(`kc not found for crop_type "${cropType}" week ${cropWeek}`);
  }
  
  return parseFloat(rows[0].kc_value);
}
```

**Data Flow**:
```
crop_type: "ทุเรียน กล้วย" (from plot_configurations)
    ↓ lookup in crop_ros_mapping
ros_type: "มะม่วง" (mango)
    ↓ lookup in kc_weekly
kc_value: 2.10 (for week 5)
```

**Data Structures**:

```sql
-- Mapping table
TABLE ros_smartfarm.crop_ros_mapping (
  crop_type VARCHAR(100) PRIMARY KEY,  -- Specific variety
  ros_type VARCHAR(50) NOT NULL,       -- Standardized type
  description TEXT
)

-- Kc values table
TABLE ros_smartfarm.kc_weekly (
  ros_type TEXT NOT NULL,
  crop_week INT NOT NULL,
  kc_value DECIMAL NOT NULL,
  growth_stage VARCHAR(50),
  PRIMARY KEY (ros_type, crop_week)
)
```

**Example Query**:
```sql
SELECT kc.kc_value 
FROM ros_smartfarm.kc_weekly kc
JOIN ros_smartfarm.crop_ros_mapping crm ON kc.ros_type = crm.ros_type
WHERE crm.crop_type = 'ทุเรียน' 
  AND kc.crop_week = 5;
-- Returns: 2.10 (mango Kc at week 5)
```

**Multi-Crop Handling**:
- Plot: "ทุเรียน กล้วย" (durian + banana)
- System extracts first crop: "ทุเรียน"
- Uses Kc for durian (mapped to mango)

**Fallback**: If not found, defaults to `1.1`

---

### 5. Effective Rainfall Retrieval

**Source**: `ros_smartfarm.weekly_effective_rainfall`

**Code**: `timescaleRepository.js:843-851`

```javascript
async getEffectiveRainfallFromRosSmartfarm(zoneId, weekNumber, year) {
  const q = `
    SELECT effective_rainfall_mm FROM ros_smartfarm.weekly_effective_rainfall
    WHERE zone_id = $1 AND week_number = $2 AND year = $3
  `;
  const { rows } = await this.pool.query(q, [zoneId, weekNumber, year]);
  if (!rows.length) return 0;
  return parseFloat(rows[0].effective_rainfall_mm);
}
```

**Alternative Source**: `ros.effective_rainfall_monthly`

**Calculation** (from `effective-rainfall.service.js:38-42`):
```javascript
// Monthly → Weekly → Daily conversion
const daysInMonth = getDaysInMonth(month, year);
const dailyEffectiveRainfall = monthlyEffectiveRainfall / daysInMonth;
const weeklyEffectiveRainfall = dailyEffectiveRainfall * 7;
```

**Data Structure**:
```sql
TABLE ros_smartfarm.weekly_effective_rainfall (
  zone_id INT,
  week_number INT,
  year INT,
  effective_rainfall_mm DECIMAL  -- mm/week
)

-- OR alternative monthly source
TABLE ros.effective_rainfall_monthly (
  aos_station VARCHAR,
  province VARCHAR,
  month INT,
  crop_type VARCHAR,  -- 'rice' or 'field_crop'
  effective_rainfall_mm DECIMAL  -- mm/month
)
```

**Crop-Specific Values**:

Different effective rainfall for rice vs field crops:

| Month | Rice (mm) | Field Crop (mm) |
|-------|-----------|-----------------|
| Jan   | 4.6       | 4.6             |
| May   | 152.1     | 67.6            |
| Sep   | 233.2     | 142.6           |

**Fallback**: If not found, defaults to `0`

---

### 6. Water Demand Calculation

**Code**: `waterPlanningService.js:133-135`

```javascript
const grossMm = et0 * kc;
const netMm = Math.max(0, grossMm - (effectiveMm || 0));
const demandM3 = Math.max(0, netMm * areaRai * 1.6);
```

**Step-by-Step Example**:

```javascript
// Input data
const et0 = 4.5;              // mm/day
const kc = 2.10;              // durian at week 5 (mango curve)
const effectiveRainfall = 0;  // mm/week (dry season)
const areaRai = 2.51;         // plot area

// Step 1: Calculate gross demand
const grossMm = 4.5 * 2.10;   // = 9.45 mm/day

// Step 2: Calculate net demand (subtract rainfall)
const netMm = Math.max(0, 9.45 - 0);  // = 9.45 mm/day

// Step 3: Convert to m³
const demandM3 = 9.45 * 2.51 * 1.6;   // = 37.97 m³/day
```

**With Percolation** (ROS service adds percolation):

```javascript
// From water-demand.service.js:29
const PERCOLATION_MM_PER_WEEK = 14;
const cropWaterDemandMm = (weeklyETo * kcValue) + PERCOLATION_MM_PER_WEEK;

// Weekly calculation example
const weeklyETo = 31.5;       // mm/week (4.5 mm/day × 7)
const kcValue = 2.10;
const percolation = 14;       // mm/week

const grossWeeklyMm = (31.5 * 2.10) + 14;  // = 80.15 mm/week
const grossWeeklyM3 = 80.15 * 2.51 * 1.6;  // = 321.88 m³/week
```

---

## Complete Calculation Example

### Scenario: Durian Plot SF-U1 on 2025-10-22

**Step 1: Retrieve Plot Configuration**
```sql
SELECT * FROM water_control_smartfarm.plot_configurations 
WHERE plot_id = 'SF-U1';
```
Result:
```json
{
  "plotId": "SF-U1",
  "cropType": "ทุเรียน กล้วย",
  "plantingDate": "2025-09-10",
  "controlMode": "-"
}
```

**Step 2: Get Plot Area**
```sql
SELECT area_rai FROM v_plot_configurations_enriched 
WHERE plot_id = 'SF-U1';
```
Result: `2.51 rai`

**Step 3: Calculate Crop Week**
```javascript
cropWeek = floor((2025-10-22 - 2025-09-10) / 7) + 1
         = floor(42 / 7) + 1
         = 7
```

**Step 4: Get Calendar Week**
```javascript
calendarWeek = 43 (ISO week number for Oct 22, 2025)
calendarYear = 2025
```

**Step 5: Retrieve ET0**
```sql
SELECT eto_value FROM ros_smartfarm.eto_weekly
WHERE aos_station = 'นครราชสีมา' 
  AND calendar_week = 43 
  AND calendar_year = 2025;
```
Result: `4.5 mm/day`

**Step 6: Retrieve Kc**
```sql
SELECT kc.kc_value 
FROM ros_smartfarm.kc_weekly kc
JOIN ros_smartfarm.crop_ros_mapping crm ON kc.ros_type = crm.ros_type
WHERE crm.crop_type = 'ทุเรียน' 
  AND kc.crop_week = 7;
```
Mapping: ทุเรียน → มะม่วง (mango)  
Result: `2.10` (mango Kc at week 7)

**Step 7: Retrieve Effective Rainfall**
```sql
SELECT effective_rainfall_mm 
FROM ros_smartfarm.weekly_effective_rainfall
WHERE zone_id = 1 
  AND week_number = 43 
  AND year = 2025;
```
Result: `0 mm` (dry season)

**Step 8: Calculate Water Demand**
```javascript
// Daily calculation
grossMm = 4.5 * 2.10 = 9.45 mm/day
netMm = max(0, 9.45 - 0) = 9.45 mm/day
demandM3 = 9.45 * 2.51 * 1.6 = 37.97 m³/day

// Weekly calculation (with percolation)
weeklyEto = 4.5 * 7 = 31.5 mm/week
grossWeeklyMm = (31.5 * 2.10) + 14 = 80.15 mm/week
netWeeklyMm = max(0, 80.15 - 0) = 80.15 mm/week
demandWeeklyM3 = 80.15 * 2.51 * 1.6 = 321.88 m³/week
```

**Final Result**:
```json
{
  "plotId": "SF-U1",
  "date": "2025-10-22",
  "cropType": "ทุเรียน กล้วย",
  "cropWeek": 7,
  "demandCubicMeters": 37.97,
  "et0": 4.5,
  "kc": 2.10,
  "effectiveRainfall": 0,
  "growthStage": "development"
}
```

---

## Database Tables Summary

### Input Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `plot_configurations` | Plot metadata | plot_id, crop_type, planting_date |
| `v_plot_configurations_enriched` | Plot with area | plot_id, area_rai |
| `crop_ros_mapping` | Crop variety → ROS type | crop_type, ros_type |
| `kc_weekly` | Crop coefficients | ros_type, crop_week, kc_value |
| `eto_weekly` | Evapotranspiration | aos_station, calendar_week, eto_value |
| `weekly_effective_rainfall` | Rainfall data | zone_id, week_number, effective_rainfall_mm |

### Output Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `daily_water_demands` | Calculated demands | plot_id, date, demand_m3, et0, kc |
| `daily_progress` | Actual vs planned | plot_id, date, planned_demand, actual_usage, efficiency |

---

## Service Entry Points

### 1. smartfarm-water-control Service

**File**: `src/services/waterPlanningService.js`

**Method**: `calculateDailyDemand(plotId, date)`

**Usage**:
```javascript
const demand = await waterPlanningService.calculateDailyDemand('SF-U1', new Date('2025-10-22'));
```

### 2. ROS Service

**File**: `src/services/water-demand.service.js`

**Method**: `calculateWaterDemand(input)`

**Usage**:
```javascript
const demand = await waterDemandService.calculateWaterDemand({
  areaId: 'SF-U1',
  cropType: 'ทุเรียน',
  areaType: 'plot',
  areaRai: 2.51,
  cropWeek: 7,
  calendarWeek: 43,
  calendarYear: 2025
});
```

---

## Error Handling & Fallbacks

### Missing Data Fallbacks

| Data | Default Value | Reason |
|------|---------------|--------|
| ET0 | 4.5 mm/day | Average for Nakhon Ratchasima |
| Kc | 1.1 | Mid-range value for most crops |
| Effective Rainfall | 0 mm | Conservative (no rainfall reduction) |
| Percolation | 14 mm/week | Standard for paddy rice |

### Multi-Crop Plot Handling

When a plot has multiple crops (e.g., "ทุเรียน กล้วย"):
1. Try exact match first
2. Extract first crop: "ทุเรียน"
3. Look up Kc for first crop
4. Fallback to default if not found

---

## Key Conversion Factors

| Conversion | Value | Notes |
|------------|-------|-------|
| 1 rai | 1,600 m² | Thai land area unit |
| 1 mm/rai | 1.6 m³ | Water volume conversion |
| Monthly → Weekly ET0 | / 4 | Approximate weekly from monthly |
| Monthly → Daily Rainfall | / days_in_month | Exact daily from monthly |

---

## Performance Optimizations

### Caching

**Code**: `waterPlanningService.js:14, 153-159`

```javascript
this.demandCache = new Map();
const cacheKey = `${plotId}-${date.toISOString().split('T')[0]}`;

if (this.demandCache.has(cacheKey)) {
  return this.demandCache.get(cacheKey);
}
```

Caches calculated demands in memory by `plotId-date` key.

### Batch Processing

**Code**: `waterPlanningService.js:267-287`

```javascript
async calculateAllPlotsDemand(date) {
  const demands = [];
  for (const plotConfig of this.plotConfigs) {
    const demand = await this.calculateDailyDemand(plotConfig.plotId, date);
    demands.push(demand);
  }
  return demands;
}
```

Processes all plots in sequence (could be parallelized).

---

## Future Enhancements

1. **Real-time rainfall integration** - Use actual weather data instead of historical averages
2. **Soil moisture adjustments** - Factor in current soil moisture levels
3. **Water level adjustments** - Reduce demand if plot water level is adequate
4. **AWD (Alternate Wetting and Drying)** - Implement water-saving irrigation schedules
5. **Machine learning** - Predict optimal irrigation timing based on patterns

---

## References

- FAO-56: Crop Evapotranspiration Guidelines
- คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm - Source Excel with Kc values
- Thai ROS (Regional Office for the Standard) methodology

---

**Last Updated**: 2025-10-22  
**Version**: 1.0
