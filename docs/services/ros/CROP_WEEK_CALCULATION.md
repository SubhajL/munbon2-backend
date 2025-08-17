# Crop Week Calculation in ROS Service

## Current Implementation

### 1. **Crop Week Must Be Provided**
Currently, the main water demand calculation endpoint requires `cropWeek` to be explicitly provided:

```json
POST /api/v1/ros/demand/calculate
{
  "areaId": "PLOT-123",
  "areaType": "project", 
  "cropType": "rice",
  "cropWeek": 5,  // <-- Must be provided
  "calendarWeek": 19,
  "calendarYear": 2025,
  "areaRai": 100
}
```

### 2. **Two Ways to Use the Service**

#### Option A: Frontend/Client Calculates Crop Week
The frontend or calling service can:
1. Get planting date from PostGIS database
2. Calculate current crop week
3. Call ROS API with the calculated crop week

#### Option B: Use Helper Endpoints
New endpoints can calculate crop week from planting date:

```json
POST /api/v1/ros/demand/crop-week/current
{
  "plantingDate": "2025-01-01"
}
// Returns: { cropWeek: 28, calendarWeek: 28, calendarYear: 2025 }
```

### 3. **Seasonal Calculation**
The seasonal endpoint automatically calculates all crop weeks from planting date:

```json
POST /api/v1/ros/demand/seasonal
{
  "areaId": "PLOT-123",
  "areaType": "project",
  "areaRai": 100,
  "cropType": "rice",
  "plantingDate": "2025-01-01",  // <-- Only planting date needed
  "includeRainfall": false
}
```

This will automatically calculate water demand for weeks 1-16 (for rice).

## Data Flow Options

### Option 1: PostGIS → Frontend → ROS
```
1. PostGIS stores: plot_id, crop_type, area_rai, planting_date
2. Frontend queries PostGIS for plot data
3. Frontend calculates: crop_week = (current_date - planting_date) / 7 + 1
4. Frontend calls ROS API with calculated crop_week
```

### Option 2: PostGIS → ROS Direct
```
1. PostGIS stores: plot_id, crop_type, area_rai, planting_date
2. ROS receives plot_id
3. ROS queries PostGIS for planting_date (would need GIS service integration)
4. ROS calculates crop_week internally
```

### Option 3: Hybrid Approach (Recommended)
```
1. PostGIS stores: plot_id, crop_type, area_rai, planting_date
2. Client provides either:
   - crop_week directly (if known)
   - planting_date (ROS calculates crop_week)
3. ROS validates crop_week is within valid range for crop type
```

## Helper Functions Available

### Calculate Current Crop Week
```typescript
POST /api/v1/ros/demand/crop-week/current
{
  "plantingDate": "2025-01-01",
  "currentDate": "2025-07-10"  // Optional, defaults to today
}
```

### Calculate Crop Weeks for Multiple Plots
```typescript
POST /api/v1/ros/demand/crop-week/plots
{
  "plots": [
    { "plotId": "PLOT-1", "plantingDate": "2025-01-01" },
    { "plotId": "PLOT-2", "plantingDate": "2025-02-15" }
  ]
}
```

### Estimate Planting Date from Crop Week
```typescript
POST /api/v1/ros/demand/crop-week/planting-date
{
  "cropWeek": 10,
  "currentDate": "2025-07-10"  // Optional
}
```

## Validation Rules

1. **Rice**: Maximum 16 weeks (~4 months)
2. **Corn**: Maximum 14 weeks (~3.5 months)  
3. **Sugarcane**: Maximum 52 weeks (~12 months)

## Example Integration

### With Known Planting Date
```javascript
// 1. Get planting date from PostGIS
const plotData = await gisService.getPlotData('PLOT-123');
// Returns: { plotId, cropType: 'rice', areaRai: 100, plantingDate: '2025-01-01' }

// 2. Calculate crop week
const cropWeekInfo = await rosService.calculateCropWeek(plotData.plantingDate);
// Returns: { cropWeek: 28, calendarWeek: 28, calendarYear: 2025 }

// 3. Calculate water demand
const waterDemand = await rosService.calculateWaterDemand({
  areaId: plotData.plotId,
  areaType: 'plot',
  cropType: plotData.cropType,
  areaRai: plotData.areaRai,
  cropWeek: cropWeekInfo.cropWeek,
  calendarWeek: cropWeekInfo.calendarWeek,
  calendarYear: cropWeekInfo.calendarYear
});
```

### With Direct Calculation
```javascript
// Get seasonal water demand directly with planting date
const seasonalDemand = await rosService.calculateSeasonalWaterDemand({
  areaId: 'PLOT-123',
  areaType: 'plot',
  areaRai: 100,
  cropType: 'rice',
  plantingDate: '2025-01-01'
});
// Returns water demand for all weeks from planting to harvest
```

## Summary

- **Current State**: Crop week must be provided to the ROS service
- **Calculation**: Can be done by frontend, GIS service, or ROS helper endpoints
- **Flexibility**: Service accepts either crop week directly or planting date for seasonal calculations
- **Integration**: PostGIS stores planting dates, but crop week calculation happens outside the core water demand calculation