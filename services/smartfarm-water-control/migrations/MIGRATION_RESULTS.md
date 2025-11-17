# Migration Execution Results
**Date**: 2025-10-22  
**Database**: munbon_dev @ 43.208.201.191  
**Status**: ✅ SUCCESS

## Migrations Applied

1. ✅ `002_crop_ros_mapping.sql` - Create crop_ros_mapping table and refactor kc_weekly
2. ✅ `002b_fix_crop_ros_mapping.sql` - Fix constraints and add growth_stage column
3. ✅ `003_add_durian_banana_kc_values.sql` - Add Kc values for durian and banana

## Changes Made

### 1. Created `ros_smartfarm.crop_ros_mapping` table
- 15 crop varieties mapped to standardized ROS types
- Supports Thai crop names with full UTF-8 encoding

### 2. Refactored `ros_smartfarm.kc_weekly` table
- Renamed column: `crop_type` → `ros_type`
- Added `growth_stage` column
- Normalized existing data (rice, corn)

### 3. Updated `water_control_smartfarm.plot_configurations`
- Increased `crop_type` column: VARCHAR(20) → VARCHAR(200)
- Removed restrictive CHECK constraint
- Updated all SF plots with actual Thai crop names

### 4. Added Kc Values
- **Durian**: 40 weeks (Kc: 0.95 - 1.20)
- **Banana**: 44 weeks (Kc: 0.50 - 1.10)

### 5. Created Helper Functions & Views
- Function: `ros_smartfarm.get_ros_type(crop_type)` - Auto-extract ROS type
- View: `ros_smartfarm.v_kc_with_crop_mapping` - Easy Kc lookup

## Verification Results

### Kc Lookup Test (Week 5)

| Plot ID | Crop Type | Kc Value | Source |
|---------|-----------|----------|--------|
| SF-U1 | ทุเรียน กล้วย | 0.95 | ✅ FROM DATABASE |
| SF-U2 | ทุเรียน กล้วย | 0.95 | ✅ FROM DATABASE |
| SF-U4 | ข้าวโพดหวาน ข้าวโพดข้าวเหนียว | 1.35 | ✅ FROM DATABASE |
| SF-U5 | ข้าวโพดเลี้ยงสัตว์ | 1.35 | ✅ FROM DATABASE |
| SF-U6 | ข้าวโพดเลี้ยงสัตว์ ข้าวโพดดำ ข้าวโพดฟ้า | 1.35 | ✅ FROM DATABASE |
| SF-U7 | ข้าวโพดหวาน | 1.35 | ✅ FROM DATABASE |
| SF-L1 | ข้าวหอมมะลิ 105 | 1.38 | ✅ FROM DATABASE |
| SF-L2 | ข้าวหอมมะลิ 105 | 1.38 | ✅ FROM DATABASE |
| SF-L3 | ข้าวหอมมะลิ 105 | 1.38 | ✅ FROM DATABASE |
| SF-L4 | ข้าวทับทิมชุมแพ | 1.38 | ✅ FROM DATABASE |
| SF-L5 | ข้าวทับทิมชุมแพ | 1.38 | ✅ FROM DATABASE |
| SF-L6 | ข้าวทับทิมชุมแพ | 1.38 | ✅ FROM DATABASE |
| SF-GH-1 | stevia | 1.1 | ⚠️ DEFAULT (needs Kc data) |
| SF-GH-2 | stevia | 1.1 | ⚠️ DEFAULT (needs Kc data) |
| SF-U3 | ว่าง (vacant) | 1.1 | ⚠️ DEFAULT (vacant plot) |

### Key Improvements

**Before Migration:**
```
SF-U1 (ทุเรียน กล้วย) → crop_type: "durian + banana" → Kc: 1.1 (default fallback)
```

**After Migration:**
```
SF-U1 (ทุเรียน กล้วย) 
  → crop_ros_mapping: "ทุเรียน" → ros_type: "durian"
  → kc_weekly: ros_type="durian", week=5 → Kc: 0.95 ✅
```

## Application Code Integration

The updated code in `timescaleRepository.js` and `waterPlanningService.js` now uses:

```sql
SELECT kc.kc_value 
FROM ros_smartfarm.kc_weekly kc
JOIN ros_smartfarm.crop_ros_mapping crm ON kc.ros_type = crm.ros_type
WHERE crm.crop_type = $1 AND kc.crop_week = $2
```

Multi-crop plots are handled automatically:
1. First try exact match: "ทุเรียน กล้วย"
2. If not found, extract first crop: "ทุเรียน"
3. Look up in mapping table

## Next Steps

### 1. Add Stevia Kc Values
Stevia currently falls back to default 1.1. Add proper values:
```sql
INSERT INTO ros_smartfarm.crop_ros_mapping (crop_type, ros_type, description)
VALUES ('stevia', 'stevia', 'Stevia');

-- Then add weekly Kc values for stevia...
```

### 2. Restart Services
```bash
cd /Users/subhajlimanond/dev/munbon2-backend-smartfarm/services/smartfarm-water-control
npm run dev
```

### 3. Monitor Logs
Check that the new Kc lookup is working correctly in production:
```bash
tail -f logs/smartfarm-water-control.log | grep "kc_value"
```

## Rollback Plan

If needed, rollback is available in the README:
```bash
psql -h 43.208.201.191 -U postgres -d munbon_dev -f migrations/ROLLBACK.sql
```

## Database Objects Created

- `ros_smartfarm.crop_ros_mapping` (table)
- `ros_smartfarm.kc_weekly_backup` (backup table)
- `ros_smartfarm.get_ros_type(VARCHAR)` (function)
- `ros_smartfarm.v_kc_with_crop_mapping` (view)

## Database Objects Modified

- `ros_smartfarm.kc_weekly` (renamed column, added growth_stage)
- `water_control_smartfarm.plot_configurations` (increased crop_type size, removed constraint)
- `water_control_smartfarm.v_plot_configurations_enriched` (recreated view)

## Contact

For questions or issues, contact the development team.

---
**Migration completed successfully on 2025-10-22 at 09:02 UTC**
