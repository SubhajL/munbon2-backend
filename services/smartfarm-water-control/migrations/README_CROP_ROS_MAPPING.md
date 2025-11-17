# Crop ROS Mapping Migration

## Overview

This migration implements a cleaner architecture for handling multiple crop varieties by introducing a static mapping table that translates specific crop types to standardized ROS crop types for Kc (crop coefficient) lookups.

## Problem Statement

Previously, the system had issues with crop-specific Kc lookups:
- **Durian and banana plots** were falling back to default `kc=1.1` because they weren't in `kc_weekly` table
- **Multiple crop varieties** (e.g., different rice or corn types) all needed separate Kc entries
- **No clear separation** between specific crop varieties and standardized crop types used for water demand calculations

## Solution Architecture

### Three-Part Solution

1. **`ros_smartfarm.crop_ros_mapping` table** - Static mapping between specific crop varieties and standardized ROS types
2. **Refactored `ros_smartfarm.kc_weekly`** - Changed from `crop_type` to `ros_type` column
3. **Updated plot configurations** - Real crop variety names instead of generic "rice" or "corn"

### Data Model

```
┌─────────────────────────────────┐
│ plot_configurations             │
│ ─────────────────────────────── │
│ plot_id: SF-U1                  │
│ crop_type: "ทุเรียน กล้วย"      │  ← Specific crop variety
└─────────────┬───────────────────┘
              │
              ↓ lookup
┌─────────────────────────────────┐
│ crop_ros_mapping                │
│ ─────────────────────────────── │
│ crop_type: "ทุเรียน"            │  ← Specific crop
│ ros_type: "durian"              │  ← Standardized ROS type
└─────────────┬───────────────────┘
              │
              ↓ join
┌─────────────────────────────────┐
│ kc_weekly                       │
│ ─────────────────────────────── │
│ ros_type: "durian"              │  ← Standardized type
│ crop_week: 1                    │
│ kc_value: 0.95                  │  ← Crop coefficient
└─────────────────────────────────┘
```

## Crop Mappings

### Current Mappings

| Crop Type (crop_type) | ROS Type (ros_type) | Description |
|----------------------|---------------------|-------------|
| ทุเรียน | durian | Durian |
| กล้วย | banana | Banana |
| ข้าวโพดหวาน | corn | Sweet corn |
| ข้าวโพดข้าวเหนียว | corn | Waxy corn |
| ข้าวโพดเลี้ยงสัตว์ | corn | Field corn |
| ข้าวโพดดำ | corn | Black corn |
| ข้าวโพดฟ้า | corn | Blue corn |
| ข้าวหอมมะลิ 105 | rice | Jasmine rice 105 |
| ข้าวทับทิมชุมแพ | rice | Tub tim chum phae |
| ข้าว กข.(นาดำ) | rice | Traditional wet rice |
| ข้าวหอมมะลิ | rice | Jasmine rice |
| ข้าวเหนียว | rice | Sticky rice |

### Plot Assignments

| Plot ID | Crop Type |
|---------|-----------|
| SF-U1 | ทุเรียน กล้วย |
| SF-U2 | ทุเรียน กล้วย |
| SF-U3 | ว่าง (vacant) |
| SF-U4 | ข้าวโพดหวาน ข้าวโพดข้าวเหนียว |
| SF-U5 | ข้าวโพดเลี้ยงสัตว์ |
| SF-U6 | ข้าวโพดเลี้ยงสัตว์ ข้าวโพดดำ ข้าวโพดฟ้า |
| SF-U7 | ข้าวโพดหวาน |
| SF-L1 | ข้าวหอมมะลิ 105 |
| SF-L2 | ข้าวหอมมะลิ 105 |
| SF-L3 | ข้าวหอมมะลิ 105 |
| SF-L4 | ข้าวทับทิมชุมแพ |
| SF-L5 | ข้าวทับทิมชุมแพ |
| SF-L6 | ข้าวทับทิมชุมแพ |

## Migration Steps

### 1. Run the Migration

```bash
psql -h <host> -U <user> -d <database> -f migrations/002_crop_ros_mapping.sql
```

### 2. Verify the Migration

```sql
-- Check crop_ros_mapping table
SELECT * FROM ros_smartfarm.crop_ros_mapping ORDER BY ros_type, crop_type;

-- Check kc_weekly now uses ros_type
SELECT DISTINCT ros_type FROM ros_smartfarm.kc_weekly;

-- Verify plot configurations updated
SELECT plot_id, crop_type 
FROM water_control_smartfarm.plot_configurations 
WHERE plot_id LIKE 'SF-%' 
ORDER BY plot_id;

-- Test Kc lookup for durian
SELECT * FROM ros_smartfarm.v_kc_with_crop_mapping 
WHERE crop_type = 'ทุเรียน' 
LIMIT 5;
```

### 3. Restart Services

After running the migration, restart the smartfarm-water-control service to pick up the new code:

```bash
# If using Docker
docker-compose restart smartfarm-water-control

# If running directly
npm run dev
```

## Application Code Changes

### Before

```javascript
// Direct lookup by crop_type
SELECT kc_value FROM ros_smartfarm.kc_weekly
WHERE crop_type = $1 AND crop_week = $2
```

### After

```javascript
// Lookup via crop_ros_mapping join
SELECT kc.kc_value 
FROM ros_smartfarm.kc_weekly kc
JOIN ros_smartfarm.crop_ros_mapping crm ON kc.ros_type = crm.ros_type
WHERE crm.crop_type = $1 AND kc.crop_week = $2
```

### Multi-Crop Handling

For plots with multiple crops (e.g., "ทุเรียน กล้วย"):
1. First tries exact match: "ทุเรียน กล้วย"
2. If not found, extracts first crop: "ทุเรียน"
3. Looks up the first crop in mapping table

## Adding New Crops

To add a new crop variety:

```sql
-- 1. Add to crop_ros_mapping
INSERT INTO ros_smartfarm.crop_ros_mapping (crop_type, ros_type, description)
VALUES ('มะม่วง', 'mango', 'Mango');

-- 2. Ensure kc_weekly has data for the ros_type
-- If 'mango' doesn't exist in kc_weekly, add it:
INSERT INTO ros_smartfarm.kc_weekly (ros_type, crop_week, kc_value, growth_stage)
VALUES 
  ('mango', 1, 0.50, 'initial'),
  ('mango', 2, 0.60, 'development'),
  -- ... add all weeks
  ('mango', 20, 0.80, 'harvest');
```

## Helper Functions

### `get_ros_type(crop_type)`

Database function to get standardized ros_type from any crop_type:

```sql
SELECT ros_smartfarm.get_ros_type('ทุเรียน');
-- Returns: 'durian'

SELECT ros_smartfarm.get_ros_type('ข้าวโพดหวาน');
-- Returns: 'corn'
```

## Views

### `v_kc_with_crop_mapping`

Convenience view that joins kc_weekly with crop_ros_mapping:

```sql
SELECT * FROM ros_smartfarm.v_kc_with_crop_mapping
WHERE crop_type = 'ทุเรียน' AND crop_week = 5;
```

Returns:
- `crop_type` - Specific variety name
- `ros_type` - Standardized ROS type
- `crop_week` - Week number
- `kc_value` - Crop coefficient
- `growth_stage` - Growth stage name
- `description` - Crop description

## Rollback

If you need to rollback this migration:

```sql
-- 1. Restore kc_weekly from backup
DROP TABLE ros_smartfarm.kc_weekly;
ALTER TABLE ros_smartfarm.kc_weekly_backup RENAME TO kc_weekly;

-- 2. Restore plot configurations (adjust values as needed)
UPDATE water_control_smartfarm.plot_configurations
SET crop_type = 'rice'
WHERE plot_id IN ('SF-L1', 'SF-L2', 'SF-L3', 'SF-L4', 'SF-L5', 'SF-L6');

UPDATE water_control_smartfarm.plot_configurations
SET crop_type = 'corn'
WHERE plot_id IN ('SF-U4', 'SF-U5', 'SF-U6', 'SF-U7');

-- 3. Drop new objects
DROP VIEW ros_smartfarm.v_kc_with_crop_mapping;
DROP FUNCTION ros_smartfarm.get_ros_type(VARCHAR);
DROP TABLE ros_smartfarm.crop_ros_mapping;
```

## Benefits

1. **Accurate Kc values** - Durian and banana now get proper crop coefficients
2. **Maintainability** - Add new varieties without modifying kc_weekly
3. **Flexibility** - Support multiple crops per plot
4. **Clarity** - Clear separation between specific varieties and standardized types
5. **Extensibility** - Easy to add new crop types and varieties

## Testing

After migration, verify that water demand calculations work correctly:

```javascript
// Test durian Kc lookup
const kc = await repo.getKcFromRosSmartfarm('ทุเรียน', 5);
console.log('Durian week 5 Kc:', kc); // Should return proper value, not default 1.1

// Test multi-crop plot
const kc2 = await repo.getKcFromRosSmartfarm('ทุเรียน กล้วย', 5);
console.log('Durian+Banana week 5 Kc:', kc2); // Should extract and use 'ทุเรียน'
```

## Questions?

Contact the development team or refer to:
- `/services/smartfarm-water-control/migrations/002_crop_ros_mapping.sql` - Migration SQL
- `/services/smartfarm-water-control/src/repository/timescaleRepository.js` - Updated code
- `/services/smartfarm-water-control/src/services/waterPlanningService.js` - Updated service
