# ROS-GIS Consolidation Setup Guide

This guide provides step-by-step instructions to set up and verify the ROS-GIS consolidation.

## Prerequisites

1. All services must be running:
   - ROS Service on port 3047
   - GIS Service on port 3007
   - ROS-GIS Integration Service on port 3022

2. PostgreSQL database must be accessible

## Step 1: Execute Database Migration

Run the migration to create the necessary tables and views:

```bash
cd services/gis/scripts
./run-ros-migration.sh
```

This creates:
- `gis.ros_water_demands` table
- `gis.latest_ros_demands` view
- `gis.weekly_demand_summary` materialized view

If you need to run manually:
```bash
psql -U postgres -d munbon -f ../migrations/004_add_ros_water_demands.sql
```

## Step 2: Restart GIS Service

The GIS service needs to be restarted to load the new routes:

```bash
# Stop the service
pm2 stop gis-service

# Start it again
cd services/gis
npm start
# or
pm2 start ecosystem.config.js --only gis-service
```

## Step 3: Configure ROS-GIS Integration

Set environment variables:

```bash
export USE_MOCK_SERVER=false
export ROS_SERVICE_URL=http://localhost:3047
export GIS_SERVICE_URL=http://localhost:3007
```

## Step 4: Start ROS-GIS Integration Service

```bash
cd services/ros-gis-integration
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

## Step 5: Trigger Initial Sync

Manually trigger a sync to populate the database:

```bash
# Sync all sections
curl -X POST http://localhost:3022/api/v1/sync/trigger

# Or sync specific sections
curl -X POST http://localhost:3022/api/v1/sync/trigger \
  -H "Content-Type: application/json" \
  -d '["section_1_A", "section_2_B"]'
```

## Step 6: Verify Integration

Run the integration test:

```bash
cd services/ros-gis-integration
python3 test_full_integration.py
```

## Step 7: Query Consolidated Data

### Via GIS REST API

```bash
# Get latest ROS calculations
curl "http://localhost:3007/api/v1/ros-demands?latest=true" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get weekly summary
curl "http://localhost:3007/api/v1/ros-demands/summary?year=2024&week=18" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Compare ROS vs RID Plan
curl "http://localhost:3007/api/v1/ros-demands/comparison?week=18&year=2024" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Via GraphQL (ROS-GIS Integration)

```graphql
query {
  consolidatedDemands(
    sectionIds: ["section_1_A", "section_2_B"]
    week: 18
    year: 2024
  ) {
    sectionId
    cropType
    growthStage
    areaRai
    netDemandM3
    hasRosCalculation
  }
}
```

## Monitoring

### Check Sync Status
```bash
curl http://localhost:3022/api/v1/sync/status
```

### View Database
```sql
-- Check latest demands
SELECT * FROM gis.latest_ros_demands LIMIT 10;

-- Check weekly summary
SELECT * FROM gis.weekly_demand_summary 
WHERE calendar_year = 2024 AND calendar_week = 18;

-- Compare with RID Plan
SELECT 
    p.plot_code,
    p.area_hectares * 6.25 as area_rai,
    rwd.net_demand_m3 as ros_demand,
    p.properties->'ridAttributes'->>'seasonIrrM3PerRai' as rid_plan_per_rai
FROM gis.agricultural_plots p
LEFT JOIN gis.ros_water_demands rwd ON p.id = rwd.parcel_id
WHERE rwd.calendar_week = 18 AND rwd.calendar_year = 2024
LIMIT 10;
```

## Troubleshooting

### Migration Failed
- Check PostgreSQL connection settings
- Ensure GIS schema exists
- Check user permissions

### No Data After Sync
- Verify ROS service has data for the sections
- Check ROS-GIS Integration logs for errors
- Ensure sections exist in both ROS and GIS databases

### GIS Routes Not Working
- Ensure GIS service was restarted after adding routes
- Check that ros-demands-v2.ts is imported in index.ts
- Verify authentication is working

### Sync Not Running
- Check `USE_MOCK_SERVER=false` is set
- Verify all service URLs are correct
- Check network connectivity between services

## Architecture Summary

```
Before:
ROS Service → ROS-GIS Integration ← GIS Service
     ↓                                    ↓
  ROS DB                              GIS DB

After:
ROS Service → Sync → GIS DB ← GIS Service
                        ↓
               ROS-GIS Integration
               (queries GIS only)
```

## Benefits Achieved

1. **Single Source of Truth**: All water demands in GIS database
2. **Spatial Integration**: ROS calculations linked to parcel geometries
3. **Historical Tracking**: Time-series data preserved
4. **Performance**: Reduced cross-service API calls
5. **Analysis**: Easy comparison between RID Plan and ROS calculations