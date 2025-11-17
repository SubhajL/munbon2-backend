-- Test real-time smoothing trigger with correct data types
-- quality_score is NUMERIC(3,2) so max value is 9.99, not 95.0

-- Insert a new normal reading
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
    16.5, -- Normal value
    3.70,
    -45,
    25.20,
    1.00, -- quality_score max is 9.99
    13.7563,
    100.5014
);

-- Check if it was smoothed
SELECT
    'Normal reading test:' AS test,
    time,
    level_cm AS smoothed_level,
    quality_score AS smoothed_quality
FROM smoothed_water_level_readings
WHERE sensor_id = 'AWD-6D47'
    AND time >= NOW() - INTERVAL '10 seconds'
ORDER BY time DESC
LIMIT 1;

-- Test outlier: Insert an extreme value
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
    250.00, -- Extreme outlier
    3.70,
    -45,
    25.20,
    1.00,
    13.7563,
    100.5014
);

-- Check outlier handling
SELECT
    'Outlier test:' AS test,
    time,
    level_cm AS smoothed_level,
    quality_score AS smoothed_quality,
    CASE
        WHEN level_cm < 50 THEN '✓ Outlier filtered'
        ELSE '✗ Outlier NOT filtered!'
    END AS result
FROM smoothed_water_level_readings
WHERE sensor_id = 'AWD-6D47'
    AND time >= NOW() - INTERVAL '10 seconds'
ORDER BY time DESC
LIMIT 1;

-- Test negative value
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
    NOW() + INTERVAL '2 seconds',
    'AWD-B89D',
    -5.00, -- Negative value
    3.70,
    -45,
    25.20,
    1.00,
    13.7563,
    100.5014
);

-- Check negative value handling
SELECT
    'Negative value test:' AS test,
    time,
    level_cm AS smoothed_level,
    quality_score AS smoothed_quality,
    CASE
        WHEN level_cm >= 0 THEN '✓ Negative corrected'
        ELSE '✗ Negative NOT corrected!'
    END AS result
FROM smoothed_water_level_readings
WHERE sensor_id = 'AWD-B89D'
    AND time >= NOW() - INTERVAL '10 seconds'
ORDER BY time DESC
LIMIT 1;