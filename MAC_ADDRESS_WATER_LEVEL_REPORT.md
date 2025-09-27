# Water Level Sensor MAC Address Report
## Analysis Period: Last 2 Weeks (Aug 6-20, 2025)

## Summary
All 6 MAC addresses from the image are present in the system and have been sending data, but there's an important pattern: **each MAC address has been associated with 2 different AWD sensor IDs**.

## Detailed Findings

### 1. MAC Address: 16A6AE7B81E9
- **Original Sensor ID**: AWD-81E9 (last seen: Aug 11, 2025)
- **Current Sensor ID**: AWD-7990 (active today: Aug 20, 2025)
- **Total Records (14 days)**: 21
- **Status**: ✅ Active (sending data today)

### 2. MAC Address: 16A6AE7B4ED4
- **Original Sensor ID**: AWD-4ED4 (last seen: Aug 11, 2025)
- **Current Sensor ID**: AWD-BE64 (active today: Aug 20, 2025)
- **Total Records (14 days)**: 24
- **Status**: ✅ Active (sending data today)

### 3. MAC Address: 16186C1FB89D
- **Original Sensor ID**: AWD-B89D (last seen: Aug 11, 2025)
- **Current Sensor ID**: AWD-411D (active today: Aug 20, 2025)
- **Total Records (14 days)**: 21
- **Status**: ✅ Active (sending data today)

### 4. MAC Address: 16A6AE7BA4F8
- **Original Sensor ID**: AWD-A4F8 (last seen: Aug 15, 2025)
- **Current Sensor ID**: AWD-0258 (active today: Aug 20, 2025)
- **Total Records (14 days)**: 27
- **Status**: ✅ Active (sending data today)

### 5. MAC Address: 16A6AE7B6D47
- **Original Sensor ID**: AWD-6D47 (last seen: Aug 11, 2025)
- **Current Sensor ID**: AWD-B7BB (active today: Aug 20, 2025)
- **Total Records (14 days)**: 21
- **Status**: ✅ Active (sending data today)

### 6. MAC Address: 16A6AE7B558F
- **Original Sensor ID**: AWD-558F (last seen: Aug 11, 2025)
- **Current Sensor ID**: AWD-D977 (active today: Aug 20, 2025)
- **Total Records (14 days)**: 23
- **Status**: ✅ Active (sending data today)

## Data Pattern
- **Aug 10-11**: All sensors active with original AWD IDs (6-12 records/day)
- **Aug 12-19**: No data received (possible maintenance/offline period)
- **Aug 20 (today)**: All sensors active with NEW AWD IDs (3-6 records so far)

## Technical Details
- All MAC addresses confirmed in:
  - ✅ Database (sensor_registry and water_level_readings)
  - ✅ Consumer logs (recent activity today)
  - ✅ SQS processing (messages being processed)

## Recommendation
The sensor ID change pattern suggests these sensors may have been reset or reconfigured around Aug 12-19. The system is correctly receiving and processing data from all 6 MAC addresses, but they are now using different AWD identifiers than before.