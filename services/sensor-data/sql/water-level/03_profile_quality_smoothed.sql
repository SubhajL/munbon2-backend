-- Profile quality of smoothed water level readings
-- Compares against raw baseline to quantify improvements

WITH sensor_list AS (
    SELECT unnest(ARRAY[
        'AWD-6D47',
        'AWD-9950',
        'AWD-B89D',
        'AWD-558F',
        'AWD-4ED4',
        'AWD-A4F8'
    ]) AS sensor_id
),
smoothed_data AS (
    SELECT
        sensor_id,
        time,
        level_cm,
        quality_score,
        LAG(level_cm) OVER (PARTITION BY sensor_id ORDER BY time) AS prev_level
    FROM smoothed_water_level_readings
    WHERE time >= NOW() - INTERVAL '14 days'
        AND sensor_id IN (SELECT sensor_id FROM sensor_list)
),
quality_metrics AS (
    SELECT
        sensor_id,
        COUNT(*) AS total_readings,
        COUNT(level_cm) AS non_null_readings,

        -- Basic statistics
        ROUND(AVG(level_cm), 2) AS avg_level,
        ROUND(MIN(level_cm), 2) AS min_level,
        ROUND(MAX(level_cm), 2) AS max_level,
        ROUND(STDDEV(level_cm), 2) AS std_deviation,

        -- Quality metrics (should all be 0 after smoothing)
        COUNT(CASE WHEN level_cm > 200 THEN 1 END) AS spike_count_200,
        COUNT(CASE WHEN level_cm > 150 THEN 1 END) AS spike_count_150,
        COUNT(CASE WHEN level_cm < 0 THEN 1 END) AS negative_count,

        -- Jump analysis
        COUNT(CASE WHEN ABS(level_cm - prev_level) > 30 THEN 1 END) AS large_jump_count,
        COUNT(CASE WHEN ABS(level_cm - prev_level) > 50 THEN 1 END) AS extreme_jump_count,

        -- Quality score analysis
        ROUND(AVG(quality_score), 1) AS avg_quality_score,
        MIN(quality_score) AS min_quality_score,
        MAX(quality_score) AS max_quality_score

    FROM smoothed_data
    GROUP BY sensor_id
)
SELECT
    '\n=== SMOOTHED DATA QUALITY METRICS ===' AS header,
    q.sensor_id,
    q.total_readings,
    q.avg_level || 'cm' AS avg_level,
    q.min_level || 'cm' AS min_level,
    q.max_level || 'cm' AS max_level,
    q.std_deviation || 'cm' AS std_dev,
    q.negative_count,
    q.spike_count_150 AS spikes_above_150,
    q.large_jump_count AS jumps_30cm,
    q.avg_quality_score,
    q.min_quality_score || '-' || q.max_quality_score AS quality_range
FROM quality_metrics q
ORDER BY q.sensor_id;

-- Compare raw vs smoothed metrics
WITH raw_jumps AS (
    SELECT
        sensor_id,
        COUNT(*) AS jump_count
    FROM (
        SELECT
            sensor_id,
            level_cm,
            LAG(level_cm) OVER (PARTITION BY sensor_id ORDER BY time) AS prev_level
        FROM water_level_readings
        WHERE time >= NOW() - INTERVAL '14 days'
            AND sensor_id LIKE 'AWD-%'
    ) t
    WHERE ABS(level_cm - prev_level) > 30
    GROUP BY sensor_id
),
smoothed_jumps AS (
    SELECT
        sensor_id,
        COUNT(*) AS jump_count
    FROM (
        SELECT
            sensor_id,
            level_cm,
            LAG(level_cm) OVER (PARTITION BY sensor_id ORDER BY time) AS prev_level
        FROM smoothed_water_level_readings
        WHERE time >= NOW() - INTERVAL '14 days'
            AND sensor_id LIKE 'AWD-%'
    ) t
    WHERE ABS(level_cm - prev_level) > 30
    GROUP BY sensor_id
),
comparison AS (
    SELECT
        'raw' AS source,
        r.sensor_id,
        COUNT(*) AS readings,
        ROUND(STDDEV(r.level_cm), 2) AS std_dev,
        COUNT(CASE WHEN r.level_cm < 0 THEN 1 END) AS negatives,
        COUNT(CASE WHEN r.level_cm > 150 THEN 1 END) AS spikes,
        COALESCE(j.jump_count, 0) AS jumps
    FROM water_level_readings r
    LEFT JOIN raw_jumps j ON r.sensor_id = j.sensor_id
    WHERE r.time >= NOW() - INTERVAL '14 days'
        AND r.sensor_id LIKE 'AWD-%'
    GROUP BY r.sensor_id, j.jump_count

    UNION ALL

    SELECT
        'smoothed' AS source,
        s.sensor_id,
        COUNT(*) AS readings,
        ROUND(STDDEV(s.level_cm), 2) AS std_dev,
        COUNT(CASE WHEN s.level_cm < 0 THEN 1 END) AS negatives,
        COUNT(CASE WHEN s.level_cm > 150 THEN 1 END) AS spikes,
        COALESCE(j.jump_count, 0) AS jumps
    FROM smoothed_water_level_readings s
    LEFT JOIN smoothed_jumps j ON s.sensor_id = j.sensor_id
    WHERE s.time >= NOW() - INTERVAL '14 days'
        AND s.sensor_id LIKE 'AWD-%'
    GROUP BY s.sensor_id, j.jump_count
)
SELECT
    '\n\n=== IMPROVEMENT SUMMARY ===' AS header,
    sensor_id,
    MAX(CASE WHEN source = 'raw' THEN std_dev END) || ' → ' ||
    MAX(CASE WHEN source = 'smoothed' THEN std_dev END) AS stddev_change,
    ROUND(100.0 * (
        MAX(CASE WHEN source = 'raw' THEN std_dev END) -
        MAX(CASE WHEN source = 'smoothed' THEN std_dev END)
    ) / NULLIF(MAX(CASE WHEN source = 'raw' THEN std_dev END), 0), 1) || '%' AS stddev_reduction,
    MAX(CASE WHEN source = 'raw' THEN negatives END) || ' → ' ||
    MAX(CASE WHEN source = 'smoothed' THEN negatives END) AS negative_change,
    MAX(CASE WHEN source = 'raw' THEN spikes END) || ' → ' ||
    MAX(CASE WHEN source = 'smoothed' THEN spikes END) AS spike_change,
    MAX(CASE WHEN source = 'raw' THEN jumps END) || ' → ' ||
    MAX(CASE WHEN source = 'smoothed' THEN jumps END) AS jump_change
FROM comparison
GROUP BY sensor_id
ORDER BY sensor_id;

-- Overall improvement statistics
SELECT
    '\n\n=== OVERALL IMPROVEMENTS ===' AS summary,
    COUNT(DISTINCT sensor_id) || ' sensors processed' AS sensors,
    SUM(CASE WHEN level_cm < 0 THEN 1 ELSE 0 END) || ' negative values remaining (should be 0)' AS negatives_check,
    ROUND(AVG(quality_score), 1) || ' average quality score' AS avg_quality,
    COUNT(*) || ' total smoothed readings' AS total_readings
FROM smoothed_water_level_readings
WHERE time >= NOW() - INTERVAL '14 days'
    AND sensor_id LIKE 'AWD-%';