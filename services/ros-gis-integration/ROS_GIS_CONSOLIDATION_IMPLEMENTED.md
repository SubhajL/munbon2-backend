# ROS-GIS Consolidation - Implementation Complete

## Overview
Successfully implemented the consolidation of ROS water demand calculations into the GIS database, creating a unified data source for all water demand information.

## What Was Implemented

### 1. Database Schema (GIS Service)
Created `gis.ros_water_demands` table to store time-series ROS calculations:
- Links to parcels via foreign key
- Stores complete calculation details (crop info, water demands, etc.)
- Includes indexes for performance
- Created views for latest demands and weekly summaries

**Migration**: `/services/gis/migrations/004_add_ros_water_demands.sql`

### 2. GIS API Endpoints
Added new REST endpoints in GIS service (`/services/gis/src/routes/ros-demands.ts`):

#### Store ROS Calculations
- `POST /api/v1/ros-demands` - Single demand calculation
- `POST /api/v1/ros-demands/bulk` - Bulk insert (recommended)

#### Query Consolidated Data
- `GET /api/v1/ros-demands` - Query with filters (section, week, year, etc.)
- `GET /api/v1/ros-demands/summary` - Weekly aggregated summaries
- `GET /api/v1/ros-demands/comparison` - Compare ROS vs RID Plan

### 3. ROS Sync Service
Created `RosSyncService` that:
- Fetches calculations from ROS service
- Transforms data to GIS format
- Pushes to GIS database via bulk API
- Runs periodically (every hour by default)

### 4. Integration Updates
Modified `IntegrationClient` to include:
- `push_ros_calculations_to_gis()` - Push calculations to GIS
- `get_consolidated_demands()` - Get demands from GIS (single source)

### 5. Sync Management Endpoints
Added REST endpoints in ROS-GIS Integration service:
- `POST /api/v1/sync/trigger` - Manual sync trigger
- `GET /api/v1/sync/status` - Current sync status
- `POST /api/v1/sync/start` - Start periodic sync
- `POST /api/v1/sync/stop` - Stop periodic sync

## Data Flow

### Before (Two Sources)
```
ROS Service → ROS-GIS Integration ← GIS Service
     ↓                                    ↓
  ROS DB                              GIS DB
```

### After (Single Source)
```
ROS Service → Sync Service → GIS DB ← GIS Service
                                ↓
                       ROS-GIS Integration
                       (queries GIS only)
```

## Key Benefits Achieved

1. **Single Source of Truth**: All water demands (RID Plan + ROS calculations) in GIS database
2. **Historical Tracking**: Time-series data stored for trend analysis
3. **Spatial Integration**: ROS calculations linked to parcel geometries
4. **Performance**: Reduced API calls, better query performance
5. **Comparison**: Easy comparison between planned (RID) and calculated (ROS) demands

## Example Usage

### 1. Sync ROS Calculations
```bash
# Trigger manual sync for all sections
curl -X POST http://localhost:3022/api/v1/sync/trigger

# Sync specific sections
curl -X POST http://localhost:3022/api/v1/sync/trigger \
  -H "Content-Type: application/json" \
  -d '["section_1_A", "section_2_B"]'
```

### 2. Query Consolidated Demands from GIS
```bash
# Get latest ROS calculations for a section
curl "http://localhost:3007/api/v1/ros-demands?sectionId=section_1_A&latest=true"

# Get weekly summary
curl "http://localhost:3007/api/v1/ros-demands/summary?year=2024&week=18"

# Compare ROS vs RID Plan
curl "http://localhost:3007/api/v1/ros-demands/comparison?amphoe=พิมาย&week=18&year=2024"
```

### 3. GraphQL Query (Unified Data)
```graphql
query GetSectionDemands {
  sectionDemands(sectionIds: ["section_1_A", "section_2_B"]) {
    sectionId
    areaRai
    cropType
    growthStage
    netDemandM3
    hasRosCalculation
    ridPlanDemandM3
    demandDifferenceM3
  }
}
```

## Configuration

### Environment Variables
```bash
# Disable mock server to enable sync
USE_MOCK_SERVER=false

# Sync interval (seconds)
ROS_SYNC_INTERVAL=3600  # 1 hour
```

### Automatic Sync
The sync service starts automatically when:
1. ROS-GIS Integration service starts
2. `USE_MOCK_SERVER=false`

## Database Query Examples

### Get Latest Demands with Geometry
```sql
SELECT 
    l.section_id,
    l.crop_type,
    l.growth_stage,
    l.area_rai,
    l.net_demand_m3,
    l.amphoe,
    l.tambon,
    ST_AsGeoJSON(l.geometry) as geometry
FROM gis.latest_ros_demands l
WHERE l.amphoe = 'พิมาย';
```

### Weekly Comparison
```sql
SELECT 
    amphoe,
    SUM(CASE WHEN crop_type = 'rice' THEN net_demand_m3 ELSE 0 END) as rice_demand,
    SUM(CASE WHEN crop_type = 'sugarcane' THEN net_demand_m3 ELSE 0 END) as sugarcane_demand,
    SUM(net_demand_m3) as total_demand
FROM gis.ros_water_demands
WHERE calendar_week = 18 AND calendar_year = 2024
GROUP BY amphoe
ORDER BY total_demand DESC;
```

## Next Steps

1. **Authentication**: Implement proper JWT auth between services
2. **Error Handling**: Add retry logic for failed syncs
3. **Monitoring**: Add metrics for sync performance
4. **Optimization**: Consider batch processing for large datasets
5. **Archival**: Implement data retention policy (e.g., keep 2 years)