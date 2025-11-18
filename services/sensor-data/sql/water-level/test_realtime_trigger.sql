-- Test real-time smoothing trigger
-- Insert a test reading and verify it gets smoothed automatically

-- First, show recent readings for AWD-6D47
SELECT
    '\n=== RECENT RAW READINGS FOR AWD-6D47 ===' AS header,
    time,
    level_cm,
    quality_score
FROM water_level_readings
WHERE sensor_id = 'AWD-6D47'
ORDER BY time DESC
LIMIT 5;

-- Show recent smoothed readings
SELECT
    '\n=== RECENT SMOOTHED READINGS FOR AWD-6D47 ===' AS header,
    time,
    level_cm,
    quality_score
FROM smoothed_water_level_readings
WHERE sensor_id = 'AWD-6D47'
ORDER BY time DESC
LIMIT 5;

-- Insert a new test reading
INSERT INTO water_level_readings (
    time,
    sensor_id,
    level_cm,
    voltage,
    rssi,
    temperature,
    quality_score,
    location_lat,
    location_lng
) VALUES (
    NOW(),
    'AWD-6D47',
    16.5, -- Reasonable value based on historical data
    3.7,
    -45,
    25.2,
    95.0,
    13.7563,
    100.5014
);

-- Wait a moment and check if it was smoothed
SELECT pg_sleep(0.1);

-- Check if the new reading appears in smoothed table
SELECT
    '\n=== NEW SMOOTHED READING (should appear) ===' AS header,
    time,
    level_cm AS smoothed_level,
    quality_score AS smoothed_quality
FROM smoothed_water_level_readings
WHERE sensor_id = 'AWD-6D47'
    AND time > NOW() - INTERVAL '1 minute'
ORDER BY time DESC
LIMIT 1;

-- Test outlier detection: Insert an extreme value
INSERT INTO water_level_readings (
    time,
    sensor_id,
    level_cm,
    voltage,
    rssi,
    temperature,
    quality_score,
    location_lat,
    location_lng
) VALUES (
    NOW() + INTERVAL '1 second',
    'AWD-6D47',
    250.0, -- Extreme outlier
    3.7,
    -45,
    25.2,
    95.0,
    13.7563,
    100.5014
);

-- Check if outlier was handled
SELECT
    '\n=== OUTLIER HANDLING TEST ===' AS header,
    time,
    level_cm AS smoothed_level,
    quality_score AS smoothed_quality,
    CASE
        WHEN level_cm < 50 THEN 'Outlier filtered successfully'
        ELSE 'WARNING: Outlier not filtered!'
    END AS status
FROM smoothed_water_level_readings
WHERE sensor_id = 'AWD-6D47'
    AND time > NOW() - INTERVAL '1 minute'
ORDER BY time DESC
LIMIT 1;