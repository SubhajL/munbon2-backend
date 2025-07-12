# Excel Data Validation for ROS Service

## Overview

This document describes the validation data extracted from the Thai Excel file `คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm` for validating the ROS (Reference Evapotranspiration Optimization Service) calculations.

## Data Sources

### 1. ETo Data (Evapotranspiration Reference)
- **Location**: Nakhon Ratchasima (นครราชสีมา)
- **Annual Average**: 124.25 mm
- **Monthly Values** (mm):
  ```
  January:   104.91
  February:  114.39
  March:     148.61
  April:     152.45
  May:       145.08
  June:      131.31
  July:      132.53
  August:    124.16
  September: 114.01
  October:   117.65
  November:  105.34
  December:  100.61
  ```

### 2. Kc Data (Crop Coefficients)
The Excel file contains Kc values for 34 different crops with weekly resolution (52 weeks).

#### Rice (ข้าว กข.(นาดำ)) - Key Crop
- **Average Kc**: 1.239
- **Max Kc**: 1.500
- **Min Kc**: 0.000
- **Growth Duration**: 13 weeks
- **Growth Stages**:
  - Initial: Weeks 12-13 (Kc = 0.94)
  - Development: Weeks 1-3 (Kc = 1.03-1.12)
  - Mid-season: Weeks 4-11 (Kc = 1.29-1.23)

#### Other Notable Crops
- **ข้าวขาวดอกมะลิ105** (Jasmine Rice 105): Avg Kc = 1.307, Max = 1.640
- **ข้าวโพดเลี้ยงสัตว์** (Feed Corn): Avg Kc = 1.188, Max = 1.630
- **อ้อย** (Sugarcane): Avg Kc = 1.007, Max = 1.560
- **มะม่วง** (Mango): Avg Kc = 1.926, Max = 2.530

### 3. System Parameters
- **Province**: นครราชสีมา (Nakhon Ratchasima)
- **Seepage Rate**: 14.0 mm/week
- **Main Rice Area**: 45,731 rai

## Calculated Values for Validation

### Water Requirements for Rice (May planting)
Based on the Excel data, the expected water requirements are:

1. **Daily ETo (May)**: 4.68 mm/day
2. **Average ETc**: 5.80 mm/day (ETo × Average Kc)
3. **Maximum ETc**: 7.02 mm/day (ETo × Max Kc)
4. **Weekly ETc**: 40.60 mm/week
5. **Total Weekly Requirement** (with seepage): 54.60 mm/week
6. **Water Volume**:
   - Weekly: 3,994,883 m³
   - Daily: 570,698 m³

## Validation Scripts

Three Python scripts have been created for data extraction and validation:

1. **extract_excel_data.py**: Extracts data from the Excel file
2. **validate_ros_calculations.py**: Validates calculations against Excel data
3. **test_ros_api.py**: Tests ROS API endpoints

## API Endpoints to Validate

The ROS service should provide these endpoints with matching results:

```bash
# 1. Get ETo data
GET /api/eto/nakhon-ratchasima

# 2. Get Kc data
GET /api/kc/rice

# 3. Calculate ETc
POST /api/etc/calculate
{
  "location": "nakhon-ratchasima",
  "cropType": "rice",
  "plantingDate": "2025-05-01",
  "area": 45731
}

# 4. Calculate water requirements
POST /api/water-requirements
{
  "cropType": "rice",
  "area": 45731,
  "location": "nakhon-ratchasima",
  "plantingDate": "2025-05-01",
  "includeSeepage": true
}
```

## Expected API Responses

### ETo Response
```json
{
  "location": "nakhon-ratchasima",
  "monthly": {
    "january": 104.91,
    "may": 145.08,
    ...
  },
  "annual_average": 124.25
}
```

### Kc Response
```json
{
  "cropType": "rice",
  "growth_stages": {
    "initial": { "duration_weeks": 2, "kc": 0.94 },
    "development": { "duration_weeks": 3, "kc": 1.03 },
    "mid_season": { "duration_weeks": 8, "kc": 1.29 },
    "late_season": { "duration_weeks": 0, "kc": 0 }
  },
  "average_kc": 1.239,
  "max_kc": 1.500
}
```

### Water Requirements Response
```json
{
  "cropType": "rice",
  "area_rai": 45731,
  "etc_mm_per_day": 5.80,
  "weekly_requirement_mm": 54.60,
  "water_volume": {
    "weekly_m3": 3994883,
    "daily_m3": 570698
  }
}
```

## Validation Criteria

The ROS service calculations should match the Excel data within these tolerances:
- ETo values: ±2%
- Kc values: Exact match (same lookup table)
- ETc calculations: ±3%
- Water volume: ±5%

## Files Generated

1. **excel_extracted_data.json**: Summary of extracted data
2. **kc_detailed_data.json**: Complete Kc values for all crops
3. **ros_validation_summary.json**: Key values for quick validation

## Usage

1. Run extraction: `python3 extract_excel_data.py`
2. Run validation: `python3 validate_ros_calculations.py`
3. Test API: `python3 test_ros_api.py` (requires ROS service running)

## Notes

- The Excel file uses Thai Buddhist calendar year 2568 (2025 CE)
- All area measurements are in rai (1 rai = 1,600 m²)
- Water depth measurements are in millimeters (mm)
- The seepage rate of 14 mm/week is a significant factor in total water requirements