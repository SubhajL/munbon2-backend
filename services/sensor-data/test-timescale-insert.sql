-- Test inserting moisture sensor data into TimescaleDB
-- This simulates what the consumer would do after receiving data from SQS

-- First, ensure we're in the correct database
\c munbon_timescale;

-- Insert sensor metadata if not exists
INSERT INTO sensor.sensors (
    sensor_id,
    sensor_type,
    location_lat,
    location_lng,
    region,
    zone,
    metadata
) VALUES (
    'munbon-m2m-00001',
    'moisture',
    13.7563,
    100.5018,
    'Munbon',
    'Zone 1',
    '{"manufacturer": "M2M", "model": "Soil Moisture Sensor", "gateway_id": "00001"}'::jsonb
) ON CONFLICT (sensor_id) DO UPDATE
SET 
    location_lat = EXCLUDED.location_lat,
    location_lng = EXCLUDED.location_lng,
    updated_at = NOW();

-- Insert moisture reading (top soil moisture)
INSERT INTO sensor.readings (
    time,
    sensor_id,
    value,
    unit,
    quality_score,
    raw_data
) VALUES (
    NOW(),
    'munbon-m2m-00001',
    45.0,  -- humid_hi (top soil moisture)
    '%',
    95,
    '{"type": "top_soil_moisture", "temp": 28.5, "battery": 395}'::jsonb
);

-- Insert moisture reading (bottom soil moisture)
INSERT INTO sensor.readings (
    time,
    sensor_id,
    value,
    unit,
    quality_score,
    raw_data
) VALUES (
    NOW(),
    'munbon-m2m-00001',
    58.0,  -- humid_low (bottom soil moisture)
    '%',
    95,
    '{"type": "bottom_soil_moisture", "temp": 27.0, "battery": 395}'::jsonb
);

-- Query to verify data was inserted
SELECT 
    s.sensor_id,
    s.sensor_type,
    s.location_lat,
    s.location_lng,
    r.time,
    r.value,
    r.unit,
    r.raw_data->>'type' as measurement_type
FROM sensor.sensors s
JOIN sensor.readings r ON s.sensor_id = r.sensor_id
WHERE s.sensor_id = 'munbon-m2m-00001'
ORDER BY r.time DESC
LIMIT 4;