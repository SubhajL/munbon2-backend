# Plot Planting Date Management API

## Overview
The Plot Planting Date Management API allows you to manage planting dates for individual plots or groups of plots. This includes updating planting dates, tracking crop schedules, and monitoring crop status throughout the growing season.

**Base URL**: `http://localhost:3047/api/v1/ros/plot-planting`

## Database Schema Updates

### Added to `ros.plots` table:
- `current_planting_date` (DATE) - Current/active planting date
- `current_crop_type` (VARCHAR(50)) - Current crop being grown
- `current_crop_status` (VARCHAR(20)) - Status: 'active', 'harvested', 'fallow', 'planned'

### Existing `ros.plot_crop_schedule` table:
- Tracks multiple seasons/years per plot
- Maintains planting history
- Supports future planning

### New View: `ros.v_plots_current_crop`
- Combines plot info with current crop details
- Calculates current crop week
- Shows water demand information

## Endpoints

### 1. Update Planting Date for Single Plot

Update the planting date and crop information for an individual plot.

```http
PUT /plot/:plotId/planting-date
Content-Type: application/json

{
  "plantingDate": "2024-08-01",
  "cropType": "rice",
  "season": "wet",
  "status": "active"
}
```

**Parameters:**
- `plotId` (path): Plot identifier
- `plantingDate`: ISO date string
- `cropType`: "rice", "corn", or "sugarcane"
- `season` (optional): "wet" or "dry"
- `status` (optional): "planned" or "active"

**Response:**
```json
{
  "success": true,
  "data": {
    "plot_id": "PLOT-123",
    "current_planting_date": "2024-08-01",
    "current_crop_type": "rice",
    "current_crop_status": "active"
  },
  "message": "Planting date updated for plot PLOT-123"
}
```

### 2. Batch Update Planting Dates

Update planting dates for multiple plots simultaneously.

```http
POST /plots/batch-update-planting-dates
Content-Type: application/json

{
  "plotIds": ["PLOT-123", "PLOT-124", "PLOT-125"],
  "plantingDate": "2024-08-01",
  "cropType": "rice",
  "season": "wet",
  "status": "active"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "updatedPlots": 3,
    "totalRequested": 3
  },
  "message": "Updated planting dates for 3 plots"
}
```

### 3. Get Plots by Planting Date Range

Retrieve plots planted within a specific date range.

```http
GET /plots/by-planting-date?startDate=2024-07-01&endDate=2024-08-31&zoneId=zone_1
```

**Query Parameters:**
- `startDate` (required): Start of date range
- `endDate` (required): End of date range
- `zoneId` (optional): Filter by zone

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "plotId": "PLOT-123",
      "plotCode": "P-Z1-S1-001",
      "areaRai": 25.5,
      "currentPlantingDate": "2024-07-14",
      "currentCropType": "rice",
      "currentCropStatus": "active",
      "currentCropWeek": 5,
      "expectedHarvestDate": "2024-11-03"
    }
  ],
  "count": 150
}
```

### 4. Get Upcoming Planting Schedules

View planned plantings for the next N days.

```http
GET /plots/upcoming-plantings?daysAhead=30
```

**Query Parameters:**
- `daysAhead` (optional): Number of days to look ahead (default: 30)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "plotId": "PLOT-456",
      "cropType": "corn",
      "plantingDate": "2024-12-01",
      "expectedHarvestDate": "2025-03-01",
      "season": "dry",
      "status": "planned"
    }
  ],
  "count": 25
}
```

### 5. Update Crop Status

Change the status of a crop (e.g., mark as harvested).

```http
PUT /plot/:plotId/crop-status
Content-Type: application/json

{
  "status": "harvested"
}
```

**Status Options:**
- `active`: Currently growing
- `harvested`: Crop has been harvested
- `fallow`: Field is resting
- `planned`: Future planting scheduled

### 6. Get Plots Ready for Harvest

Find plots approaching their harvest date.

```http
GET /plots/ready-for-harvest?daysWindow=7
```

**Query Parameters:**
- `daysWindow` (optional): Days to look ahead (default: 7)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "plotId": "PLOT-789",
      "currentCropWeek": 16,
      "expectedHarvestDate": "2024-08-05",
      "totalWaterDemandM3": 41714,
      "totalNetWaterDemandM3": 31697
    }
  ],
  "count": 45,
  "message": "Found 45 plots ready for harvest within 7 days"
}
```

### 7. Get Planting Statistics by Zone

Summary statistics of planting dates and crop status by zone.

```http
GET /plots/planting-stats-by-zone
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "zone": "zone_1",
      "total_plots": 2945,
      "planted_plots": 2945,
      "earliest_planting": "2024-07-14",
      "latest_planting": "2024-07-14",
      "crop_types": 1,
      "active_crops": 2945,
      "total_area_rai": 8137.00
    }
  ],
  "summary": {
    "totalZones": 6,
    "totalPlots": 15069,
    "totalPlanted": 15069
  }
}
```

## Features

### Automatic Water Demand Recalculation
- When planting dates are updated, water demand is automatically recalculated
- Batch updates trigger background recalculation

### Crop Schedule Management
- Tracks multiple seasons per plot
- Maintains historical planting data
- Supports future planning

### Status Tracking
- Monitor crop progress from planting to harvest
- Track fallow periods
- Plan future plantings

## Usage Examples

### Example 1: Staggered Planting by Zone
```bash
# Update zone 1 to plant on August 1
curl -X POST http://localhost:3047/api/v1/ros/plot-planting/plots/batch-update-planting-dates \
  -H "Content-Type: application/json" \
  -d '{
    "plotIds": ["PLOT-001", "PLOT-002", "PLOT-003"],
    "plantingDate": "2024-08-01",
    "cropType": "rice",
    "season": "wet"
  }'
```

### Example 2: Mark Plots as Harvested
```bash
# Update crop status after harvest
curl -X PUT http://localhost:3047/api/v1/ros/plot-planting/plot/PLOT-123/crop-status \
  -H "Content-Type: application/json" \
  -d '{"status": "harvested"}'
```

### Example 3: Plan Next Season
```bash
# Check which plots are ready for next planting
curl http://localhost:3047/api/v1/ros/plot-planting/plots/by-planting-date?startDate=2024-01-01&endDate=2024-12-31
```

## Notes

1. **Water Demand Integration**: Updating planting dates automatically triggers water demand recalculation
2. **Harvest Calculation**: Expected harvest dates are calculated based on crop type (Rice: 16 weeks, Others: 14 weeks)
3. **Season Detection**: System can auto-detect season based on planting month
4. **Historical Tracking**: All changes are tracked in the plot_crop_schedule table