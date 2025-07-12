# Effective Rainfall Implementation - Complete

## Summary

Successfully updated the ROS service to use Excel-based effective rainfall values instead of a fixed 0.8 efficiency factor.

## Changes Made

### 1. Database Migration
- Created `ros.effective_rainfall_monthly` table
- Imported monthly effective rainfall data from Thai Excel sheet
- Data includes crop-specific values (rice vs field crops)

### 2. New Service
- Created `effective-rainfall.service.ts` 
- Implements crop-specific effective rainfall lookup
- Automatically categorizes crops as rice or field crops
- Converts monthly values to weekly (divide by 4)

### 3. Updated Water Demand Service
- Replaced `rainfallService.getWeeklyEffectiveRainfall()` calls
- Now uses `effectiveRainfallService.getEffectiveRainfall()`
- Passes crop type for correct rainfall values

### 4. Schema Fixes
- Fixed table references to include `ros.` schema prefix
- Updated water level and rainfall services

## Test Results

### Rice (May, Week 20)
- Monthly effective rainfall: 152.1 mm
- Weekly effective rainfall: 38.03 mm
- Gross water demand: 64.05 mm
- Net water demand: 26.03 mm (after rainfall)

### Sugarcane (May, Week 20)
- Monthly effective rainfall: 67.6 mm
- Weekly effective rainfall: 16.90 mm  
- Gross water demand: 37.58 mm
- Net water demand: 20.68 mm (after rainfall)

### Key Finding
Rice fields receive 125% more effective rainfall than field crops (21.13 mm/week difference in May)

## Annual Totals
- Rice: 1,059.5 mm/year (20.38 mm/week average)
- Field Crops: 622.0 mm/year (11.96 mm/week average)

## API Usage

The water demand API automatically uses the correct effective rainfall:

```bash
curl -X POST http://localhost:3047/api/v1/ros/demand/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "areaId": "PLOT-123",
    "cropType": "rice",     # Automatically gets rice rainfall
    "cropWeek": 5,
    "calendarWeek": 20,
    "calendarYear": 2025,
    "areaRai": 100,
    "areaType": "FTO"
  }'
```

## Files Modified
1. `/src/services/water-demand.service.ts` - Updated to use new service
2. `/src/services/effective-rainfall.service.ts` - New service created
3. `/src/services/water-level.service.ts` - Fixed schema references
4. `/src/services/rainfall.service.ts` - Fixed schema references
5. `/scripts/add-effective-rainfall-table.sql` - Database migration

## Next Steps
- The system now matches the Thai Excel calculations exactly
- No further changes needed for effective rainfall
- Original rainfall service remains for raw rainfall data if needed