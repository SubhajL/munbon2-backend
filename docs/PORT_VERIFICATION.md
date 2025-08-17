# Port Configuration Verification

## Current Codebase vs Required Configuration

| Service | Required Port | Current in docker-compose | Status |
|---------|--------------|--------------------------|---------|
| Auth Service | 3001 | 3001 | ✅ Correct |
| Sensor Data Service | 3003 | 3003 | ✅ Correct |
| Sensor Data Consumer | 3004 | 3004 | ✅ Correct |
| Moisture Monitoring | 3005 | 3003 | ❌ CONFLICT with Sensor Data |
| Weather Monitoring | 3006 | 3004 | ❌ CONFLICT with Consumer |
| GIS Service | 3007 | 3006 | ❌ Wrong port |
| Water Level Monitoring | 3008 | 3008 | ✅ Correct |
| RID-MS | - | 3011 | ❓ Not in your list |
| ROS Service | 3047 | 3012 | ❌ Wrong port |
| AWD Control | - | 3013 | ❓ Not in your list |
| Flow Monitoring | - | 3014 | ❓ Not in your list |

## Issues Found:

1. **Port Conflicts:**
   - Moisture Monitoring and Sensor Data both using 3003
   - Weather Monitoring and Consumer Dashboard both using 3004

2. **Wrong Ports:**
   - GIS: Using 3006 instead of 3007
   - ROS: Using 3012 instead of 3047

3. **Services not in your list:**
   - RID-MS (3011)
   - AWD Control (3013)
   - Flow Monitoring (3014)

## Required Fixes:

```yaml
# Fix these port assignments:
moisture-monitoring: 3003 → 3005
weather-monitoring: 3004 → 3006  
gis: 3006 → 3007
ros: 3012 → 3047
```