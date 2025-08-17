# ROS-GIS Data Consolidation Proposal

## Overview
This proposal outlines how to consolidate ROS water demand calculations into the GIS database alongside RID Plan data.

## Current State

### GIS Service (Port 3007)
- Stores static RID Plan parcels with pre-calculated water demands
- Fields include: `seasonIrrM3PerRai`, `wpet`, `wprod`, `yieldAtMcKgpr`
- Data imported from GeoPackage files

### ROS Service (Port 3047)
- Calculates dynamic water demands based on:
  - Current crop stage (from calendar)
  - Weather conditions (ETo)
  - Crop coefficients (Kc)
- Provides week-by-week water requirements

## Proposed Database Schema

### Option 1: Extend Existing Parcel Table
Add ROS calculation fields to the existing `parcels` table:

```sql
ALTER TABLE gis.parcels ADD COLUMN ros_current_demand_m3 NUMERIC;
ALTER TABLE gis.parcels ADD COLUMN ros_weekly_demand_m3 NUMERIC;
ALTER TABLE gis.parcels ADD COLUMN ros_crop_stage VARCHAR(50);
ALTER TABLE gis.parcels ADD COLUMN ros_calculation_date TIMESTAMP;
ALTER TABLE gis.parcels ADD COLUMN ros_kc_factor NUMERIC;
ALTER TABLE gis.parcels ADD COLUMN ros_et0_mm NUMERIC;
```

### Option 2: Create Separate ROS Demands Table (Recommended)
Create a new table to store time-series ROS calculations:

```sql
CREATE TABLE gis.ros_water_demands (
    id SERIAL PRIMARY KEY,
    parcel_id UUID REFERENCES gis.parcels(id),
    section_id VARCHAR(50),
    calculation_date TIMESTAMP NOT NULL,
    calendar_week INTEGER NOT NULL,
    calendar_year INTEGER NOT NULL,
    
    -- Crop information
    crop_type VARCHAR(50),
    crop_week INTEGER,
    growth_stage VARCHAR(50),
    planting_date DATE,
    harvest_date DATE,
    
    -- Water demand calculation
    area_rai NUMERIC NOT NULL,
    et0_mm NUMERIC,
    kc_factor NUMERIC,
    percolation_mm NUMERIC DEFAULT 14,
    
    -- Results
    gross_demand_mm NUMERIC,
    gross_demand_m3 NUMERIC,
    effective_rainfall_mm NUMERIC,
    net_demand_mm NUMERIC,
    net_demand_m3 NUMERIC,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_parcel_week (parcel_id, calendar_week, calendar_year),
    INDEX idx_section_date (section_id, calculation_date)
);
```

## Benefits of Consolidation

1. **Unified Querying**
   ```sql
   -- Compare RID Plan vs ROS calculations
   SELECT 
       p.plot_code,
       p.area_rai,
       p.season_irr_m3_per_rai * p.area_rai as rid_plan_demand,
       r.net_demand_m3 as ros_calculated_demand,
       (r.net_demand_m3 - (p.season_irr_m3_per_rai * p.area_rai)) as difference
   FROM gis.parcels p
   LEFT JOIN gis.ros_water_demands r ON p.id = r.parcel_id
   WHERE r.calendar_week = 18 AND r.calendar_year = 2024;
   ```

2. **Historical Analysis**
   ```sql
   -- Track demand changes over time
   SELECT 
       section_id,
       calendar_week,
       AVG(net_demand_m3) as avg_demand,
       MIN(net_demand_m3) as min_demand,
       MAX(net_demand_m3) as max_demand
   FROM gis.ros_water_demands
   WHERE calendar_year = 2024
   GROUP BY section_id, calendar_week
   ORDER BY section_id, calendar_week;
   ```

3. **Spatial Analysis**
   ```sql
   -- Aggregate demands by geographic area
   SELECT 
       p.amphoe,
       p.tambon,
       SUM(r.net_demand_m3) as total_demand_m3,
       COUNT(DISTINCT p.id) as parcel_count
   FROM gis.parcels p
   JOIN gis.ros_water_demands r ON p.id = r.parcel_id
   WHERE r.calendar_week = EXTRACT(WEEK FROM CURRENT_DATE)
   GROUP BY p.amphoe, p.tambon;
   ```

## Implementation Steps

1. **Create Database Schema**
   - Add `ros_water_demands` table to GIS database
   - Create appropriate indexes for performance

2. **Modify ROS Service**
   - Add endpoint to push calculations to GIS database
   - Or create a sync job that runs periodically

3. **Update GIS Service**
   - Add API endpoints to query ROS demand data
   - Extend existing parcel queries to include ROS calculations

4. **Modify ROS-GIS Integration**
   - Query consolidated data from GIS instead of calling both services
   - Reduces network calls and improves performance

## Data Flow

```
Current Flow:
ROS Service → ROS-GIS Integration ← GIS Service
     ↓                                    ↓
  ROS DB                              GIS DB

Proposed Flow:
ROS Service → GIS DB ← GIS Service
                 ↓
         ROS-GIS Integration
         (queries GIS only)
```

## Migration Strategy

1. **Phase 1**: Create new schema without breaking existing functionality
2. **Phase 2**: Start writing ROS calculations to GIS DB (dual write)
3. **Phase 3**: Update ROS-GIS Integration to read from GIS DB
4. **Phase 4**: Deprecate direct ROS API calls for water demands

## Considerations

1. **Data Volume**: Weekly calculations for ~15,000 parcels = ~780,000 records/year
2. **Performance**: Need proper indexing and potentially partitioning by year
3. **Sync Frequency**: Real-time vs batch updates (recommend hourly batch)
4. **Data Retention**: Keep 2-3 years of historical data, archive older

## Conclusion

Consolidating ROS calculations into the GIS database will:
- Simplify the architecture
- Enable better analysis and reporting
- Improve query performance
- Provide a complete picture of water demands (planned vs calculated)
- Support historical tracking and machine learning