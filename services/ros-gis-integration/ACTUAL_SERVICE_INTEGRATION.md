# ROS-GIS Integration - Actual Service Integration

## Overview
This document describes the integration with actual ROS and GIS services, replacing the mock data implementation.

## Key Changes Made

### 1. Service Port Corrections
- **ROS Service**: Port 3047 (was incorrectly 3041)
- **GIS Service**: Port 3007 (correct port for GIS service)
- Updated in `src/config/settings.py`

### 2. Mock Server Disabled
- Changed `use_mock_server` from `True` to `False` in settings
- Service now queries actual ROS and GIS endpoints

### 3. Area Unit Conversion
**All areas are now in rai (ไร่) units** as requested:
- 1 hectare = 6.25 rai
- Updated throughout the codebase:
  - `area_hectares` → `area_rai`
  - `total_area_hectares` → `total_area_rai`
  - Rainfall reduction: 10m³/hectare → 1.6m³/rai

### 4. ROS Integration (`get_crop_requirements`)
Now retrieves actual data from ROS service:
- Fetches area information from `/api/v1/ros/areas/{area_id}`
- Gets crop calendar from `/api/v1/ros/calendar/area/{area_id}`
- Determines active crops based on current date
- Calculates growth stage from planting date
- Returns real crop type and growth stage (not mocked)

### 5. GIS Integration (`get_section_boundaries`)
Now retrieves actual data from GIS service:
- Queries RID Plan parcels from `/api/v1/rid-plan/parcels`
- Maps sections to amphoe (district) names
- Aggregates parcel areas (already in rai from GIS)
- Returns actual boundaries and parcel counts

## Data Sources

### Crop Type and Growth Stage
From ROS Service crop calendar:
```python
# Active crop determined by:
planting_date <= current_date <= harvest_date

# Growth stage calculated from:
crop_week = (days_since_planting // 7) + 1

# Growth stages for rice:
- Weeks 1-3: seedling
- Weeks 4-7: tillering
- Weeks 8-11: flowering
- Weeks 12-16: maturity
```

### Area Data
From GIS Service RID Plan parcels:
- Already stored in rai units
- No conversion needed from GIS
- Example: `"areaRai": 10` (direct from GIS)

## Zone-to-Amphoe Mapping
Currently hardcoded in `integration_client.py`:
```python
amphoe_map = {
    1: "เมืองนครราชสีมา",
    2: "พิมาย",
    3: "ปากช่อง",
    4: "สีคิ้ว",
    5: "สูงเนิน",
    6: "ขามทะเลสอ"
}
```

## Testing
Run `test_actual_services.py` to verify:
1. ROS service returns real crop data
2. GIS service returns real parcel data
3. All areas are in rai units

## Environment Variables
Ensure these are set correctly:
```bash
ROS_SERVICE_URL=http://localhost:3047
GIS_SERVICE_URL=http://localhost:3007
USE_MOCK_SERVER=false
```

## Next Steps
1. Implement proper JWT authentication for GIS service
2. Add configuration for zone-to-amphoe mapping
3. Implement proper geometry merging for section boundaries
4. Add caching for frequently accessed data