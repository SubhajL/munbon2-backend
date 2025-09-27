# Water Level Sensor MAC Address Report - CORRECTED
## Date: August 20, 2025

## Issue Found and Fixed
The system was incorrectly generating AWD sensor IDs by converting numeric sensor IDs to hex values instead of using the standard AWD format: **AWD-XXXX where XXXX is the last 4 alphanumeric characters of the MAC address**.

## Fix Applied
Updated the sensor ID extraction logic to prioritize MAC addresses when available, ensuring AWD IDs are correctly derived from the last 4 characters of the MAC address.

## Current Status - All 6 Sensors ACTIVE ✅

### 1. MAC: 16A6AE7B81E9 → AWD-81E9
- **Status**: ✅ ACTIVE (last seen: 0.0 hours ago)
- **Total Records**: 36
- **Date Range**: Jul 1 - Aug 20, 2025

### 2. MAC: 16A6AE7B4ED4 → AWD-4ED4  
- **Status**: ✅ ACTIVE (last seen: 0.1 hours ago)
- **Total Records**: 39
- **Date Range**: Jul 1 - Aug 20, 2025

### 3. MAC: 16186C1FB89D → AWD-B89D
- **Status**: ✅ ACTIVE (last seen: 0.1 hours ago)
- **Total Records**: 21  
- **Date Range**: Aug 10 - Aug 20, 2025

### 4. MAC: 16A6AE7BA4F8 → AWD-A4F8
- **Status**: ✅ ACTIVE (last seen: 0.1 hours ago)
- **Total Records**: 27
- **Date Range**: Aug 10 - Aug 20, 2025

### 5. MAC: 16A6AE7B6D47 → AWD-6D47
- **Status**: ✅ ACTIVE (last seen: 0.1 hours ago)
- **Total Records**: 21
- **Date Range**: Aug 10 - Aug 20, 2025

### 6. MAC: 16A6AE7B558F → AWD-558F
- **Status**: ✅ ACTIVE (last seen: 0.1 hours ago)
- **Total Records**: 35
- **Date Range**: Jul 1 - Aug 20, 2025

## Data Continuity
- **Gap Period**: Aug 12-19 (sensors were sending data with incorrect AWD IDs)
- **Resolution**: System now correctly processes all incoming data with proper AWD-XXXX format
- **Backward Compatibility**: Historical data with wrong AWD IDs remains in database but new data uses correct format

## Technical Details
- Consumer updated to prioritize MAC address for AWD ID generation
- Format: AWD-{last 4 chars of MAC address in uppercase}
- All 6 sensors confirmed receiving and processing data correctly