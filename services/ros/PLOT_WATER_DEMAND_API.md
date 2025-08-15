# Plot Water Demand API Documentation

## Overview
The Plot Water Demand API provides endpoints for calculating irrigation water requirements at the individual plot (parcel) level. This API supports both single plot and batch calculations, with full integration of land preparation water and effective rainfall.

**Base URL**: `http://localhost:3047/api/v1/ros/plot-demand`

## Endpoints

### 1. Calculate Water Demand for Single Plot

Calculate seasonal water demand for an individual agricultural plot.

```http
POST /plot/:plotId/calculate
Content-Type: application/json

{
  "cropType": "rice",
  "plantingDate": "2024-05-01",
  "includeRainfall": true,
  "includeLandPreparation": true
}
```

**Parameters:**
- `plotId` (path): Unique plot identifier
- `cropType`: Type of crop ("rice", "corn", "sugarcane")
- `plantingDate`: ISO date string for planting date
- `includeRainfall`: Boolean to include effective rainfall (default: true)
- `includeLandPreparation`: Boolean to include land prep water (default: true)

**Response:**
```json
{
  "success": true,
  "data": {
    "areaId": "PLOT-123",
    "areaType": "plot",
    "areaRai": 25.5,
    "cropType": "rice",
    "totalCropWeeks": 16,
    "plantingDate": "2024-05-01",
    "harvestDate": "2024-08-21",
    "totalWaterDemandMm": 1022.5,
    "totalWaterDemandM3": 41,714,
    "landPreparationMm": 100,
    "landPreparationM3": 4,080,
    "totalEffectiveRainfall": 245.6,
    "totalNetWaterDemandMm": 776.9,
    "totalNetWaterDemandM3": 31,697,
    "weeklyDetails": [
      {
        "cropWeek": 0,
        "cropWaterDemandMm": 100,
        "cropWaterDemandM3": 4080,
        "description": "Land preparation"
      },
      {
        "cropWeek": 1,
        "cropWaterDemandMm": 56.9,
        "effectiveRainfall": 5.2,
        "netWaterDemandMm": 51.7
      }
      // ... more weeks
    ]
  }
}
```

### 2. Batch Calculate for Multiple Plots

Calculate water demand for multiple plots simultaneously.

```http
POST /plots/batch-calculate
Content-Type: application/json

{
  "plotIds": ["PLOT-123", "PLOT-124", "PLOT-125"],
  "cropType": "rice",
  "plantingDate": "2024-05-01",
  "includeRainfall": true,
  "includeLandPreparation": true
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "PLOT-123": { /* full seasonal result */ },
    "PLOT-124": { /* full seasonal result */ },
    "PLOT-125": { /* full seasonal result */ }
  },
  "summary": {
    "totalPlots": 3,
    "successfulCalculations": 3,
    "failedCalculations": 0
  }
}
```

### 3. Get Plots by Area

Retrieve all plots within a zone or section.

```http
GET /plots/by-area/:areaType/:areaId
```

**Parameters:**
- `areaType`: Either "zone" or "section"
- `areaId`: ID of the zone or section

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "plotId": "PLOT-123",
      "plotCode": "P-Z1-S1-001",
      "areaRai": 25.5,
      "parentSectionId": "Z1-S1",
      "parentZoneId": "Z1"
    }
    // ... more plots
  ],
  "count": 45
}
```

### 4. Get Plot Information

Retrieve details for a specific plot.

```http
GET /plot/:plotId
```

**Response:**
```json
{
  "success": true,
  "data": {
    "plotId": "PLOT-123",
    "plotCode": "P-Z1-S1-001",
    "areaRai": 25.5,
    "parentSectionId": "Z1-S1",
    "parentZoneId": "Z1",
    "aosStation": "นครราชสีมา",
    "province": "นครราชสีมา"
  }
}
```

### 5. Get Historical Water Demand

Retrieve past water demand calculations for a plot.

```http
GET /plot/:plotId/history?startYear=2022&endYear=2024
```

**Query Parameters:**
- `startYear`: Optional start year filter
- `endYear`: Optional end year filter

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "year": 2023,
      "season": "wet",
      "cropType": "rice",
      "totalWaterDemandM3": 41714,
      "totalNetWaterDemandM3": 31697
    }
    // ... more records
  ],
  "count": 3
}
```

### 6. Get Current Week Demand

Get water demand for all active plots in the current week.

```http
GET /plots/current-week?week=20&year=2024
```

**Query Parameters:**
- `week`: Week number (1-53), defaults to current week
- `year`: Year, defaults to current year

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "plotId": "PLOT-123",
      "cropType": "rice",
      "cropWeek": 5,
      "cropWaterDemandM3": 2321,
      "netWaterDemandM3": 1894,
      "parentZoneId": "Z1"
    }
    // ... more plots
  ],
  "summary": {
    "totalPlots": 150,
    "totalWaterDemandM3": 348150,
    "totalNetWaterDemandM3": 284100,
    "byZone": {
      "Z1": 94700,
      "Z2": 85600,
      "Z3": 103800
    }
  }
}
```

### 7. Calculate Zone Aggregate Demand

Calculate total water demand for all plots in a zone.

```http
POST /zone/:zoneId/calculate
Content-Type: application/json

{
  "cropType": "rice",
  "plantingDate": "2024-05-01",
  "includeRainfall": true,
  "includeLandPreparation": true
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "zoneId": "Z1",
    "totalPlots": 45,
    "totalAreaRai": 1147.5,
    "cropType": "rice",
    "totalWaterDemandM3": 1877046,
    "totalNetWaterDemandM3": 1433874,
    "totalLandPreparationM3": 183600,
    "averagePerPlot": {
      "waterDemandM3": 41712,
      "netWaterDemandM3": 31864
    },
    "plotDetails": {
      "PLOT-123": { /* seasonal details */ },
      "PLOT-124": { /* seasonal details */ }
      // ... all plots
    }
  }
}
```

## Key Features

### 1. Land Preparation Water
- Automatically included for week 0 (before planting)
- Rice: 100 mm/season
- Corn/Sugarcane: 50 mm/season

### 2. Effective Rainfall
- Crop-specific rainfall effectiveness
- Rice fields utilize more rainfall than upland crops
- Automatically fetched from database if not provided

### 3. Calculation Components
- **Gross Water Demand** = (Weekly ETo × Kc) + Percolation
- **Net Water Demand** = Gross Demand - Effective Rainfall
- **Total Seasonal** = Land Preparation + Sum of all weeks

### 4. Database Storage
- All calculations are saved for historical tracking
- Weekly breakdowns stored in `plot_water_demand_weekly`
- Seasonal summaries in `plot_water_demand_seasonal`

## Error Handling

Common errors:
- `404`: Plot not found
- `400`: Invalid crop type or date format
- `500`: Database or calculation error

## Usage Examples

### Example 1: Calculate for New Rice Planting
```bash
curl -X POST http://localhost:3047/api/v1/ros/plot-demand/plot/PLOT-123/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "cropType": "rice",
    "plantingDate": "2024-05-01",
    "includeRainfall": true,
    "includeLandPreparation": true
  }'
```

### Example 2: Zone-wide Planning
```bash
# Get all plots in zone
curl http://localhost:3047/api/v1/ros/plot-demand/plots/by-area/zone/Z1

# Calculate water demand for entire zone
curl -X POST http://localhost:3047/api/v1/ros/plot-demand/zone/Z1/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "cropType": "rice",
    "plantingDate": "2024-05-01"
  }'
```

### Example 3: Weekly Monitoring
```bash
# Check current week water requirements
curl http://localhost:3047/api/v1/ros/plot-demand/plots/current-week
```

## Notes

1. **Plot IDs**: Must match imported shapefile parcel IDs
2. **Spatial Data**: Stored as PostGIS geometry (EPSG:32648)
3. **Performance**: Batch operations process 10 plots in parallel
4. **Hierarchy**: Plots → Sections → Zones → Project