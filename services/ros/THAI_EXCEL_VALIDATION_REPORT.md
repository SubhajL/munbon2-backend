# Thai Excel Data Validation Report

## Summary
Successfully extracted and validated data from Thai ROS Excel file: `คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm`

## Key Corrections Made

### 1. ETo Data Extraction
- **Previous Error**: Extracted from row 71 (เกาะสมุย)
- **Corrected**: Now extracting from row 38 (นครราชสีมา)
- **Impact**: All monthly ETo values were wrong

### 2. Kc Data Extraction
- **Previous Error**: Treated crops as rows (rows 7, 8, 12)
- **Corrected**: Crops are in columns:
  - Column B: Rice (ข้าว กข.(นาดำ))
  - Column F: Corn (ข้าวโพดเลี้ยงสัตว์)
  - Column X: Sugarcane (อ้อย)
- **Impact**: All Kc values were wrong

## Validated Calculations

### Test Case 1: Rice Week 5 in May (100 rai)
- Monthly ETo: 145.08 mm ✅
- Weekly ETo: 36.27 mm ✅
- Kc Value: 1.38 ✅
- Water Demand: 64.05 mm ✅
- Volume: 10,248 m³ ✅

### Test Case 2: Rice Week 1 in January (100 rai)
- Monthly ETo: 104.91 mm ✅
- Weekly ETo: 26.23 mm ✅
- Kc Value: 1.03 ✅
- Water Demand: 41.01 mm ✅
- Volume: 6,562 m³ ✅

### Test Case 3: Corn Week 7 in July (500 rai)
- Monthly ETo: 132.53 mm ✅
- Weekly ETo: 33.13 mm ✅
- Kc Value: 1.61 ✅
- Water Demand: 67.34 mm ✅
- Volume: 53,875 m³ ✅

### Test Case 4: Sugarcane Week 10 in October (1000 rai)
- Monthly ETo: 117.65 mm ✅
- Weekly ETo: 29.41 mm ✅
- Kc Value: 1.13 ✅
- Water Demand: 47.24 mm ✅
- Volume: 75,578 m³ ✅

## Formula Verification
```
Water Demand (mm) = (Weekly ETo × Kc) + Percolation
Volume (m³) = Water Demand (mm) × Area (rai) × 1.6
```

Where:
- Weekly ETo = Monthly ETo ÷ 4
- Percolation = 14 mm/week (fixed)
- Conversion factor = 1.6 (rai to m³)

## Database Tables Updated

### ros.eto_monthly
- Station: นครราชสีมา
- 12 monthly values from row 38 of ETo worksheet

### ros.kc_weekly
- Rice: 13 weeks of data from column B
- Corn: 14 weeks of data from column F
- Sugarcane: 44 weeks of data from column X

## API Endpoints Working
- `POST /api/v1/ros/demand/calculate` - Calculate water demand for specific week
- `POST /api/v1/ros/demand/seasonal` - Calculate seasonal water demand

## Validation Status
✅ **ALL TESTS PASSED** - ROS service calculations now match Thai Excel exactly