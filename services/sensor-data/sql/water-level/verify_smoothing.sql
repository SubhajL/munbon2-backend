-- Verify water level smoothing results
SELECT
    '\n=== SMOOTHING RESULTS SUMMARY ===' AS header;

-- Overall statistics
SELECT
    COUNT(*) AS total_smoothed_rows,
    COUNT(DISTINCT sensor_id) AS sensors_smoothed,
    ROUND(AVG(level_cm), 2) AS avg_level,
    ROUND(AVG(quality_score), 1) AS avg_quality_score,
    MIN(time)::date AS earliest_date,
    MAX(time)::date AS latest_date
FROM smoothed_water_level_readings;

-- Per-sensor comparison
SELECT
    '\n=== PER-SENSOR COMPARISON ===' AS header;

WITH comparison AS (
    SELECT
        sensor_id,
        'raw' AS source,
        COUNT(*) AS readings,
        ROUND(AVG(level_cm), 2) AS avg_level,
        ROUND(STDDEV(level_cm), 2) AS std_dev,
        COUNT(CASE WHEN level_cm < 0 THEN 1 END) AS negative_count
    FROM water_level_readings
    WHERE time >= NOW() - INTERVAL '14 days'
        AND sensor_id LIKE 'AWD-%'
    GROUP BY sensor_id

    UNION ALL

    SELECT
        sensor_id,
        'smoothed' AS source,
        COUNT(*) AS readings,
        ROUND(AVG(level_cm), 2) AS avg_level,
        ROUND(STDDEV(level_cm), 2) AS std_dev,
        COUNT(CASE WHEN level_cm < 0 THEN 1 END) AS negative_count
    FROM smoothed_water_level_readings
    WHERE time >= NOW() - INTERVAL '14 days'
        AND sensor_id LIKE 'AWD-%'
    GROUP BY sensor_id
)
SELECT
    sensor_id,
    MAX(CASE WHEN source = 'raw' THEN readings END) AS raw_count,
    MAX(CASE WHEN source = 'smoothed' THEN readings END) AS smoothed_count,
    MAX(CASE WHEN source = 'raw' THEN avg_level END) AS raw_avg,
    MAX(CASE WHEN source = 'smoothed' THEN avg_level END) AS smoothed_avg,
    MAX(CASE WHEN source = 'raw' THEN std_dev END) AS raw_stddev,
    MAX(CASE WHEN source = 'smoothed' THEN std_dev END) AS smoothed_stddev,
    ROUND(100.0 * (
        MAX(CASE WHEN source = 'raw' THEN std_dev END) -
        MAX(CASE WHEN source = 'smoothed' THEN std_dev END)
    ) / NULLIF(MAX(CASE WHEN source = 'raw' THEN std_dev END), 0), 1) AS stddev_reduction_pct,
    MAX(CASE WHEN source = 'raw' THEN negative_count END) AS raw_negatives,
    MAX(CASE WHEN source = 'smoothed' THEN negative_count END) AS smoothed_negatives
FROM comparison
GROUP BY sensor_id
ORDER BY sensor_id;

-- Sample of smoothed values
SELECT
    '\n=== SAMPLE SMOOTHED VALUES ===' AS header;

SELECT
    sensor_id,
    time,
    level_cm,
    quality_score
FROM smoothed_water_level_readings
WHERE sensor_id = 'AWD-B89D'  -- The sensor with negative values
ORDER BY time DESC
LIMIT 10;