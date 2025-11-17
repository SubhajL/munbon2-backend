-- Simple test of real-time smoothing trigger

-- Insert test data and check results
DO $$
DECLARE
    v_test_time TIMESTAMPTZ;
    v_smoothed_count INTEGER;
    v_smoothed_level NUMERIC;
    v_quality NUMERIC;
BEGIN
    -- Test 1: Normal reading
    v_test_time := NOW();

    INSERT INTO water_level_readings (
        time, sensor_id, level_cm, voltage, rssi, temperature, quality_score, location_lat, location_lng
    ) VALUES (
        v_test_time, 'AWD-6D47', 16.50, 3.70, -45, 25.20, 1.00, 13.7563, 100.5014
    );

    -- Check if smoothed
    SELECT COUNT(*), MAX(level_cm), MAX(quality_score)
    INTO v_smoothed_count, v_smoothed_level, v_quality
    FROM smoothed_water_level_readings
    WHERE sensor_id = 'AWD-6D47' AND time = v_test_time;

    RAISE NOTICE 'Test 1 - Normal reading: count=%, level=%, quality=%',
        v_smoothed_count, v_smoothed_level, v_quality;

    -- Test 2: Extreme value (should be filtered)
    v_test_time := NOW() + INTERVAL '1 second';

    INSERT INTO water_level_readings (
        time, sensor_id, level_cm, voltage, rssi, temperature, quality_score, location_lat, location_lng
    ) VALUES (
        v_test_time, 'AWD-6D47', 250.00, 3.70, -45, 25.20, 1.00, 13.7563, 100.5014
    );

    SELECT level_cm, quality_score
    INTO v_smoothed_level, v_quality
    FROM smoothed_water_level_readings
    WHERE sensor_id = 'AWD-6D47' AND time = v_test_time;

    RAISE NOTICE 'Test 2 - Outlier (250cm): smoothed_level=% (should be < 50), quality=%',
        v_smoothed_level, v_quality;

    -- Test 3: Negative value (should be corrected to >= 0)
    v_test_time := NOW() + INTERVAL '2 seconds';

    INSERT INTO water_level_readings (
        time, sensor_id, level_cm, voltage, rssi, temperature, quality_score, location_lat, location_lng
    ) VALUES (
        v_test_time, 'AWD-B89D', -5.00, 3.70, -45, 25.20, 1.00, 13.7563, 100.5014
    );

    SELECT level_cm, quality_score
    INTO v_smoothed_level, v_quality
    FROM smoothed_water_level_readings
    WHERE sensor_id = 'AWD-B89D' AND time = v_test_time;

    RAISE NOTICE 'Test 3 - Negative value (-5cm): smoothed_level=% (should be >= 0), quality=%',
        v_smoothed_level, v_quality;

    -- Summary
    RAISE NOTICE '';
    RAISE NOTICE 'Real-time smoothing trigger tests completed!';
    RAISE NOTICE 'Check NOTICE messages above for results.';
END $$;

-- Show summary of recent smoothed readings
SELECT
    'Recent smoothed readings (last 5):' AS info,
    sensor_id,
    COUNT(*) as count,
    MIN(level_cm) as min_level,
    MAX(level_cm) as max_level,
    AVG(quality_score) as avg_quality
FROM smoothed_water_level_readings
WHERE time > NOW() - INTERVAL '1 minute'
GROUP BY sensor_id
ORDER BY sensor_id;