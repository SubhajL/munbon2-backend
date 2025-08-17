# Water Demand Calculation Guide - ROS Service

## Overview
The ROS (Reservoir Operation System) service calculates irrigation water demand using the FAO-56 Penman-Monteith method, which is the international standard for calculating crop water requirements.

## Core Formula

```
Net Water Demand = Crop Water Demand - Effective Rainfall

Where:
Crop Water Demand (mm) = (Weekly ETo × Kc) + Percolation
Crop Water Demand (m³) = Crop Water Demand (mm) × Area (rai) × 1.6
```

## Key Components

### 1. ETo (Reference Evapotranspiration)
- **Definition**: The evapotranspiration rate from a reference surface (well-watered grass)
- **Units**: mm/month (converted to mm/week for calculations)
- **Source**: Monthly data from Thai Meteorological Department stations
- **Calculation**: Weekly ETo = Monthly ETo ÷ 4

### 2. Kc (Crop Coefficient)
- **Definition**: Ratio of crop evapotranspiration to reference evapotranspiration
- **Varies by**: Crop type and growth stage
- **Source**: FAO-56 tables adapted for Thai conditions
- **Examples**:
  - Rice initial stage: 1.05
  - Rice mid-season: 1.20
  - Sugarcane mid-season: 1.25

### 3. Percolation
- **Definition**: Water loss through deep percolation below root zone
- **Value**: 14 mm/week (standard for clay soils in Thailand)
- **Note**: May vary based on soil type

### 4. Effective Rainfall
- **Definition**: Portion of rainfall that contributes to crop water needs
- **Calculation**: Based on soil moisture retention and runoff
- **Source**: Weather stations or rainfall models

### 5. Area Conversion
- **Factor**: 1.6 m³/rai/mm
- **Explanation**: 1 rai = 1,600 m², 1 mm = 0.001 m

## Calculation Steps

### Step 1: Get Monthly ETo
```sql
SELECT eto_value 
FROM ros.eto_monthly 
WHERE aos_station = 'นครราชสีมา' 
  AND month = 5; -- May
-- Result: 156.0 mm/month
```

### Step 2: Calculate Weekly ETo
```javascript
weeklyETo = monthlyETo / 4
// 156.0 / 4 = 39.0 mm/week
```

### Step 3: Get Crop Coefficient (Kc)
```sql
SELECT kc_value 
FROM ros.kc_weekly 
WHERE crop_type = 'rice' 
  AND crop_week = 5;
-- Result: 1.10
```

### Step 4: Calculate Crop Water Demand
```javascript
cropWaterDemandMm = (weeklyETo × kcValue) + percolation
// (39.0 × 1.10) + 14 = 56.9 mm/week

cropWaterDemandM3 = cropWaterDemandMm × areaRai × 1.6
// 56.9 × 1000 × 1.6 = 91,040 m³/week
```

### Step 5: Calculate Net Water Demand (if rainfall data available)
```javascript
netWaterDemandMm = cropWaterDemandMm - effectiveRainfall
// 56.9 - 5.2 = 51.7 mm/week

netWaterDemandM3 = netWaterDemandMm × areaRai × 1.6
// 51.7 × 1000 × 1.6 = 82,720 m³/week
```

## API Usage Examples

### 1. Calculate Water Demand for Single Week
```bash
curl -X POST http://localhost:3047/api/v1/ros/demand/calculate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "areaId": "Z1-S1",
    "areaType": "section",
    "areaRai": 1000,
    "cropType": "rice",
    "cropWeek": 5,
    "calendarWeek": 18,
    "calendarYear": 2024
  }'
```

### 2. Calculate Seasonal Water Demand
```bash
curl -X POST http://localhost:3047/api/v1/ros/demand/seasonal \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "areaId": "Z1-S1",
    "areaType": "section", 
    "areaRai": 1000,
    "cropType": "rice",
    "plantingDate": "2024-05-01",
    "includeRainfall": true
  }'
```

## Database Schema

### Key Tables
1. **ros.eto_monthly** - Monthly ETo values by station
2. **ros.kc_weekly** - Weekly Kc values by crop type
3. **ros.water_demand_calculations** - Historical calculations
4. **ros.effective_rainfall** - Rainfall effectiveness factors
5. **ros.areas** - Area hierarchy and information

### Example Query for Complete Calculation
```sql
WITH calculation AS (
  SELECT 
    a.area_id,
    a.total_area_rai,
    e.eto_value / 4 as weekly_eto,
    k.kc_value,
    14 as percolation,
    ((e.eto_value / 4) * k.kc_value + 14) as crop_demand_mm
  FROM ros.areas a
  JOIN ros.eto_monthly e ON e.aos_station = a.aos_station
  JOIN ros.kc_weekly k ON k.crop_type = 'rice' AND k.crop_week = 5
  WHERE a.area_id = 'Z1-S1'
    AND e.month = 5
)
SELECT 
  *,
  crop_demand_mm * total_area_rai * 1.6 as crop_demand_m3
FROM calculation;
```

## Crop-Specific Considerations

### Rice (16 weeks)
- Initial stage (1-4 weeks): Kc = 1.05
- Development (5-8 weeks): Kc = 1.10-1.20
- Mid-season (9-12 weeks): Kc = 1.20
- Late season (13-16 weeks): Kc = 0.90-1.15

### Sugarcane (52 weeks)
- Initial stage (1-8 weeks): Kc = 0.40-0.60
- Development (9-20 weeks): Kc = 0.60-1.25
- Mid-season (21-40 weeks): Kc = 1.25
- Late season (41-52 weeks): Kc = 0.75-1.00

### Corn (16 weeks)
- Initial stage (1-3 weeks): Kc = 0.30-0.50
- Development (4-8 weeks): Kc = 0.50-1.20
- Mid-season (9-13 weeks): Kc = 1.20
- Late season (14-16 weeks): Kc = 0.60-0.90

## Integration with Other Services

### Weather Service Integration
```javascript
// Get current rainfall data
const rainfallData = await weatherService.getRainfall(areaId, date);
const effectiveRainfall = rainfallData.amount * 0.8; // 80% effectiveness
```

### GIS Service Integration
```javascript
// Get parcel information
const parcelInfo = await gisService.getParcel(parcelId);
const areaRai = parcelInfo.area_rai;
```

### Water Level Service Integration
```javascript
// Get current water level
const waterLevel = await waterLevelService.getCurrentLevel(areaId);
```

## Best Practices

1. **Cache ETo Values**: Monthly ETo changes slowly, cache for performance
2. **Validate Inputs**: Ensure crop week is within valid range for crop type
3. **Handle Missing Data**: Use defaults or interpolation for missing values
4. **Consider Soil Type**: Adjust percolation based on local soil conditions
5. **Safety Margins**: Add 10-15% safety margin for critical periods
6. **Update Regularly**: Recalculate when rainfall or conditions change

## Error Handling

Common errors and solutions:
- **No ETo data**: Use nearest station or historical average
- **Invalid crop week**: Check against crop duration limits
- **Missing rainfall**: Calculate gross demand without reduction
- **Negative net demand**: Set to zero (no irrigation needed)

## References
- FAO Irrigation and Drainage Paper No. 56
- Royal Irrigation Department Guidelines
- Thai Meteorological Department Standards