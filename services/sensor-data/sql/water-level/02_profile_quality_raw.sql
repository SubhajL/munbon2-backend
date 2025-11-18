-- Profile quality of raw water level readings
-- Analyzes 14 days of data for each AWD sensor to establish baseline metrics
-- Metrics include: spike count, null percentage, large jumps, standard deviation

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
raw_data AS (
    SELECT
        sensor_id,
        time,
        level_cm,
        LAG(level_cm) OVER (PARTITION BY sensor_id ORDER BY time) AS prev_level,
        LEAD(level_cm) OVER (PARTITION BY sensor_id ORDER BY time) AS next_level
    FROM water_level_readings
    WHERE time >= NOW() - INTERVAL '14 days'
        AND sensor_id IN (SELECT sensor_id FROM sensor_list)
),
quality_metrics AS (
    SELECT
        sensor_id,
        COUNT(*) AS total_readings,
        COUNT(level_cm) AS non_null_readings,

        -- Null percentage
        ROUND(100.0 * (COUNT(*) - COUNT(level_cm)) / NULLIF(COUNT(*), 0), 2) AS null_percentage,

        -- Basic statistics
        ROUND(AVG(level_cm), 2) AS avg_level,
        ROUND(MIN(level_cm), 2) AS min_level,
        ROUND(MAX(level_cm), 2) AS max_level,
        ROUND(STDDEV(level_cm), 2) AS std_deviation,

        -- Spike detection (values > 200cm)
        COUNT(CASE WHEN level_cm > 200 THEN 1 END) AS spike_count_200,
        COUNT(CASE WHEN level_cm > 150 THEN 1 END) AS spike_count_150,
        COUNT(CASE WHEN level_cm < 0 THEN 1 END) AS negative_count,

        -- Large jumps (>30cm change between consecutive readings)
        COUNT(CASE WHEN ABS(level_cm - prev_level) > 30 THEN 1 END) AS large_jump_count,

        -- Extreme jumps (>50cm change)
        COUNT(CASE WHEN ABS(level_cm - prev_level) > 50 THEN 1 END) AS extreme_jump_count

    FROM raw_data
    GROUP BY sensor_id
),
data_gaps AS (
    SELECT
        sensor_id,
        COUNT(*) AS data_gap_count
    FROM (
        SELECT
            sensor_id,
            time,
            LAG(time) OVER (PARTITION BY sensor_id ORDER BY time) AS prev_time
        FROM water_level_readings
        WHERE time >= NOW() - INTERVAL '14 days'
            AND sensor_id IN (SELECT sensor_id FROM sensor_list)
    ) t
    WHERE time - prev_time > INTERVAL '5 minutes'
    GROUP BY sensor_id
),
percentiles AS (
    SELECT
        sensor_id,
        ROUND(PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY level_cm)::numeric, 2) AS p1,
        ROUND(PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY level_cm)::numeric, 2) AS p5,
        ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY level_cm)::numeric, 2) AS p25,
        ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY level_cm)::numeric, 2) AS p50,
        ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY level_cm)::numeric, 2) AS p75,
        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY level_cm)::numeric, 2) AS p95,
        ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY level_cm)::numeric, 2) AS p99
    FROM raw_data
    WHERE level_cm IS NOT NULL
    GROUP BY sensor_id
)
SELECT
    q.sensor_id,
    q.total_readings,
    q.non_null_readings,
    q.null_percentage || '%' AS null_pct,
    q.avg_level || 'cm' AS avg_level,
    q.min_level || 'cm' AS min_level,
    q.max_level || 'cm' AS max_level,
    q.std_deviation || 'cm' AS std_dev,
    q.spike_count_200 AS spikes_above_200,
    q.spike_count_150 AS spikes_above_150,
    q.negative_count AS negative_values,
    q.large_jump_count AS jumps_30cm,
    q.extreme_jump_count AS jumps_50cm,
    COALESCE(dg.data_gap_count, 0) AS data_gaps,
    ROUND(100.0 * q.spike_count_200 / NULLIF(q.non_null_readings, 0), 2) || '%' AS spike_rate_200,
    ROUND(100.0 * q.large_jump_count / NULLIF(q.non_null_readings, 0), 2) || '%' AS jump_rate_30
FROM quality_metrics q
JOIN percentiles p ON q.sensor_id = p.sensor_id
LEFT JOIN data_gaps dg ON q.sensor_id = dg.sensor_id
ORDER BY q.sensor_id;

-- Detailed percentile analysis
WITH sensor_list AS (
    SELECT unnest(ARRAY[
        'AWD-6D47',
        'AWD-9950',
        'AWD-B89D',
        'AWD-558F',
        'AWD-4ED4',
        'AWD-A4F8'
    ]) AS sensor_id
)
SELECT
    '\n' || '=== PERCENTILE ANALYSIS ===' AS header,
    NULL::text AS sensor_id,
    NULL::numeric AS p1,
    NULL::numeric AS p5,
    NULL::numeric AS p25,
    NULL::numeric AS p50,
    NULL::numeric AS p75,
    NULL::numeric AS p95,
    NULL::numeric AS p99
FROM generate_series(1,1)
UNION ALL
SELECT
    NULL,
    sensor_id,
    ROUND(PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY level_cm)::numeric, 2) AS p1,
    ROUND(PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY level_cm)::numeric, 2) AS p5,
    ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY level_cm)::numeric, 2) AS p25,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY level_cm)::numeric, 2) AS p50,
    ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY level_cm)::numeric, 2) AS p75,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY level_cm)::numeric, 2) AS p95,
    ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY level_cm)::numeric, 2) AS p99
FROM water_level_readings
WHERE time >= NOW() - INTERVAL '14 days'
    AND sensor_id IN (SELECT sensor_id FROM sensor_list)
    AND level_cm IS NOT NULL
GROUP BY sensor_id
ORDER BY sensor_id NULLS FIRST;

-- Sample of extreme values for inspection
WITH sensor_list AS (
    SELECT unnest(ARRAY[
        'AWD-6D47',
        'AWD-9950',
        'AWD-B89D',
        'AWD-558F',
        'AWD-4ED4',
        'AWD-A4F8'
    ]) AS sensor_id
)
SELECT
    '\n' || '=== SAMPLE EXTREME VALUES (TOP 5 PER SENSOR) ===' AS header,
    NULL::text AS sensor_id,
    NULL::timestamptz AS time,
    NULL::numeric AS level_cm,
    NULL::text AS issue_type
FROM generate_series(1,1)
UNION ALL
(
    SELECT
        NULL,
        sensor_id,
        time,
        level_cm,
        CASE
            WHEN level_cm > 200 THEN 'Spike > 200cm'
            WHEN level_cm < 0 THEN 'Negative value'
            WHEN ABS(level_cm - LAG(level_cm) OVER (PARTITION BY sensor_id ORDER BY time)) > 50 THEN 'Jump > 50cm'
            ELSE 'High value'
        END AS issue_type
    FROM water_level_readings
    WHERE time >= NOW() - INTERVAL '14 days'
        AND sensor_id IN (SELECT sensor_id FROM sensor_list)
        AND (level_cm > 150 OR level_cm < 0)
    ORDER BY level_cm DESC
    LIMIT 30
)
ORDER BY header DESC NULLS LAST, sensor_id, time;

-- Summary statistics
WITH sensor_list AS (
    SELECT unnest(ARRAY[
        'AWD-6D47',
        'AWD-9950',
        'AWD-B89D',
        'AWD-558F',
        'AWD-4ED4',
        'AWD-A4F8'
    ]) AS sensor_id
)
SELECT
    '\n' || '=== OVERALL SUMMARY ===' AS summary,
    COUNT(DISTINCT sensor_id) || ' sensors analyzed' AS sensors,
    COUNT(*) || ' total readings' AS readings,
    ROUND(100.0 * COUNT(CASE WHEN level_cm > 200 THEN 1 END) / COUNT(*), 2) || '% spike rate (>200cm)' AS spike_rate,
    ROUND(AVG(level_cm), 2) || 'cm overall average' AS avg_level
FROM water_level_readings
WHERE time >= NOW() - INTERVAL '14 days'
    AND sensor_id IN (SELECT sensor_id FROM sensor_list);