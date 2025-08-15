-- Script to update water_level_readings sensor IDs to AWD-XXXX format
-- This only updates the water_level_readings table

BEGIN;

-- Create temporary mapping table from sensor_readings
CREATE TEMP TABLE sensor_id_mapping AS
WITH mac_mappings AS (
  SELECT DISTINCT 
    sensor_id as old_sensor_id,
    value->>'macAddress' as mac_address,
    'AWD-' || UPPER(RIGHT(value->>'macAddress', 4)) as new_sensor_id
  FROM sensor_readings
  WHERE sensor_type = 'water-level' 
    AND sensor_id NOT LIKE 'AWD-%'
    AND value->>'macAddress' IS NOT NULL
)
SELECT 
  old_sensor_id,
  mac_address,
  new_sensor_id,
  ROW_NUMBER() OVER (PARTITION BY old_sensor_id ORDER BY mac_address) as rn
FROM mac_mappings;

-- Show the mapping for verification
SELECT COUNT(*) as total_unique_sensors FROM sensor_id_mapping WHERE rn = 1;
SELECT * FROM sensor_id_mapping WHERE rn = 1 ORDER BY old_sensor_id LIMIT 10;

-- Count records before update
SELECT COUNT(*) as records_before_update FROM water_level_readings WHERE sensor_id NOT LIKE 'AWD-%';

-- Disable foreign key constraint temporarily
ALTER TABLE water_level_readings DROP CONSTRAINT water_level_readings_sensor_id_fkey;

-- Update water_level_readings
UPDATE water_level_readings wlr
SET sensor_id = sm.new_sensor_id
FROM sensor_id_mapping sm
WHERE wlr.sensor_id = sm.old_sensor_id
  AND sm.rn = 1;

-- Re-enable foreign key constraint (but don't enforce it yet)
ALTER TABLE water_level_readings ADD CONSTRAINT water_level_readings_sensor_id_fkey 
  FOREIGN KEY (sensor_id) REFERENCES sensor_registry(sensor_id) NOT VALID;

-- Show results
SELECT COUNT(*) as records_updated FROM water_level_readings WHERE sensor_id LIKE 'AWD-%';

-- Show sample of updated records
SELECT sensor_id, level_cm, time 
FROM water_level_readings 
WHERE sensor_id LIKE 'AWD-%' 
ORDER BY time DESC 
LIMIT 20;

-- Show distinct sensor IDs after update
SELECT DISTINCT sensor_id 
FROM water_level_readings 
ORDER BY sensor_id 
LIMIT 30;

COMMIT;