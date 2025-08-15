-- Script to update all water level sensor IDs to AWD-XXXX format based on MAC addresses
-- This script creates a mapping table and updates all references

BEGIN;

-- Create temporary mapping table
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
SELECT COUNT(*) as total_mappings FROM sensor_id_mapping WHERE rn = 1;
SELECT * FROM sensor_id_mapping WHERE rn = 1 ORDER BY old_sensor_id LIMIT 20;

-- Disable foreign key checks temporarily
ALTER TABLE water_level_readings DROP CONSTRAINT water_level_readings_sensor_id_fkey;
ALTER TABLE sensor_readings DROP CONSTRAINT sensor_readings_sensor_id_fkey;
ALTER TABLE location_history DROP CONSTRAINT location_history_sensor_id_fkey;
ALTER TABLE moisture_readings DROP CONSTRAINT moisture_readings_sensor_id_fkey;

-- Update sensor_registry first
UPDATE sensor_registry sr
SET sensor_id = sm.new_sensor_id
FROM sensor_id_mapping sm
WHERE sr.sensor_id = sm.old_sensor_id
  AND sm.rn = 1
  AND sr.sensor_type = 'water-level';

-- Update water_level_readings
UPDATE water_level_readings wlr
SET sensor_id = sm.new_sensor_id
FROM sensor_id_mapping sm
WHERE wlr.sensor_id = sm.old_sensor_id
  AND sm.rn = 1;

-- Update sensor_readings
UPDATE sensor_readings sr
SET sensor_id = sm.new_sensor_id
FROM sensor_id_mapping sm
WHERE sr.sensor_id = sm.old_sensor_id
  AND sm.rn = 1
  AND sr.sensor_type = 'water-level';

-- Update location_history if any water level sensors have location history
UPDATE location_history lh
SET sensor_id = sm.new_sensor_id
FROM sensor_id_mapping sm
WHERE lh.sensor_id = sm.old_sensor_id
  AND sm.rn = 1;

-- Re-enable foreign key constraints
ALTER TABLE water_level_readings ADD CONSTRAINT water_level_readings_sensor_id_fkey 
  FOREIGN KEY (sensor_id) REFERENCES sensor_registry(sensor_id);
ALTER TABLE sensor_readings ADD CONSTRAINT sensor_readings_sensor_id_fkey 
  FOREIGN KEY (sensor_id) REFERENCES sensor_registry(sensor_id);
ALTER TABLE location_history ADD CONSTRAINT location_history_sensor_id_fkey 
  FOREIGN KEY (sensor_id) REFERENCES sensor_registry(sensor_id);
ALTER TABLE moisture_readings ADD CONSTRAINT moisture_readings_sensor_id_fkey 
  FOREIGN KEY (sensor_id) REFERENCES sensor_registry(sensor_id);

-- Show results
SELECT 'Updated sensor_registry:' as table_name, COUNT(*) as records_updated 
FROM sensor_registry 
WHERE sensor_id LIKE 'AWD-%' AND sensor_type = 'water-level'
UNION ALL
SELECT 'Updated water_level_readings:', COUNT(*) 
FROM water_level_readings 
WHERE sensor_id LIKE 'AWD-%'
UNION ALL
SELECT 'Updated sensor_readings:', COUNT(*) 
FROM sensor_readings 
WHERE sensor_id LIKE 'AWD-%' AND sensor_type = 'water-level';

-- Show sample of updated records
SELECT sensor_id, level_cm, time 
FROM water_level_readings 
WHERE sensor_id LIKE 'AWD-%' 
ORDER BY time DESC 
LIMIT 10;

COMMIT;