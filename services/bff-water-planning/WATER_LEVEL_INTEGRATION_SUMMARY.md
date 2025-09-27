# Water Level Integration Summary

## Overview
Successfully integrated water level data into the BFF Water Planning service's weekly water demand calculations. The system now automatically adjusts water demands based on actual field water levels from sensors and manual readings.

## Database Schema

### New Tables Created
1. **ros_gis.water_level_thresholds** - Defines optimal/warning/critical levels for each section
2. **ros_gis.manual_water_level_readings** - Stores field volunteer measurements  
3. **ros_gis.sensor_water_levels** - Stores automated sensor readings
4. **ros_gis.water_level_aggregations** - Daily aggregated water levels by section
5. **ros_gis.water_level_demand_adjustments** - Tracks demand adjustments applied

### Updated Tables
- **ros_gis.weekly_water_demands** - Added columns:
  - `water_level_m` - Current water level
  - `water_level_status` - Status category (OPTIMAL, WARNING_LOW, etc.)
  - `water_level_adjustment_applied` - Boolean flag

- **ros_gis.crop_season_weekly_progress** - Added columns:
  - `avg_water_level_m` - Average water level for the week
  - `water_stress_days` - Cumulative days with low water
  - `water_level_status` - Current status

## Water Level Thresholds & Adjustments

| Water Level | Status | Adjustment Factor | Description |
|-------------|--------|-------------------|-------------|
| < 0.02m | CRITICAL_LOW | 0.30x | Severe water stress, reduce demand by 70% |
| 0.02-0.05m | WARNING_LOW | 0.50-0.70x | Low water, reduce demand proportionally |
| 0.05-0.10m | OPTIMAL | 0.70-1.00x | Normal operations |
| 0.10-0.15m | WARNING_HIGH | 1.00-1.10x | Slightly increase drainage |
| 0.15-0.20m | CRITICAL_HIGH | 1.10-1.20x | Risk of flooding, increase drainage |
| > 0.20m | ABOVE_CRITICAL | 1.20x | Maximum drainage needed |

## Implementation Details

### Weekly Calculation Flow (weekly_demand_calculator_v2.py)

1. **Get Last Week's Adjustments** (`_get_last_week_sensor_adjustments`)
   - Queries water level aggregations for previous week
   - Calculates adjustment factors using database function
   - Stores current week levels for reporting

2. **Apply Adjustments** (`_process_sections_from_gis`)
   - Retrieves adjustment factors for each section
   - Applies to gross demand calculations
   - Stores both original and adjusted demands

3. **Store with Water Level Info** (`_store_weekly_demand`)
   - Adds current water level to demand records
   - Sets water level status
   - Flags if adjustment was applied

4. **Update Season Progress** (`_update_season_progress`)
   - Updates crop progress with water levels
   - Tracks cumulative water stress days
   - Aggregates to zone and munbon levels

### Database Function
`ros_gis.calculate_water_adjustment_factor()` - Calculates demand adjustment based on current water level and thresholds using a graduated scale.

## Current Status by Zone

Based on sample data populated:
- Zone 1: 0.077m (86% demand) - Slightly below optimal
- Zone 2: 0.100m (98% demand) - Optimal  
- Zone 3: 0.060m (76% demand) - Low water conditions
- Zone 4: 0.119m (104% demand) - Above optimal
- Zone 5: 0.044m (66% demand) - Critical low
- Zone 6: 0.090m (94% demand) - Near optimal

## Testing

Created test scripts:
- `scripts/create_water_level_tables.sql` - Schema setup
- `scripts/populate_water_level_thresholds.py` - Standard thresholds
- `scripts/populate_sample_water_levels_simple.py` - Sample data
- `scripts/test_water_level_simple.py` - Integration verification

## Next Steps

1. **Connect to Real Sensor Data**
   - Integrate with sensor-data service for live readings
   - Set up daily aggregation job

2. **Historical Analysis**
   - Backfill water level data from existing sources
   - Analyze correlation with yield data

3. **Alert System**
   - Notify when sections enter critical zones
   - Weekly summary of water stress areas

4. **Dashboard Integration**
   - Add water level status to BFF responses
   - Create visualization endpoints

## API Impact

Weekly demand responses now include:
```json
{
  "area_id": "01-02-03-04",
  "gross_demand_m3": 50000,
  "adjusted_demand_m3": 43000,
  "sensor_adjustment_factor": 0.86,
  "water_level_m": 0.077,
  "water_level_status": "OPTIMAL",
  "water_level_adjustment_applied": true
}
```

This enables the dashboard to show both theoretical and adjusted demands based on actual field conditions.