-- Backfill smoothed water level data for the last 14 days
-- Uses Hampel Filter + EMA (Exponential Moving Average) algorithm
-- Adjusted for water level data which has less noise than moisture sensors

-- Clear existing smoothed data for clean backfill
TRUNCATE TABLE smoothed_water_level_readings;

-- Multi-stage CTE pipeline for smoothing
WITH RECURSIVE sensor_list AS (
    SELECT unnest(ARRAY[
        'AWD-6D47',
        'AWD-9950',
        'AWD-B89D',
        'AWD-558F',
        'AWD-4ED4',
        'AWD-A4F8'
    ]) AS sensor_id
),
-- Stage 1: Fetch raw data with time windows
raw_data AS (
    SELECT
        time,
        sensor_id,
        level_cm,
        voltage,
        rssi,
        temperature,
        location_lat,
        location_lng,
        -- Add row numbers for ordering
        ROW_NUMBER() OVER (PARTITION BY sensor_id ORDER BY time) AS row_num
    FROM water_level_readings
    WHERE time >= NOW() - INTERVAL '14 days'
        AND sensor_id IN (SELECT sensor_id FROM sensor_list)
    ORDER BY sensor_id, time
),
-- Stage 2: Build rolling windows with LAG/LEAD
windowed_data AS (
    SELECT
        *,
        -- Previous values (up to 6)
        LAG(level_cm, 1) OVER (PARTITION BY sensor_id ORDER BY time) AS lag1,
        LAG(level_cm, 2) OVER (PARTITION BY sensor_id ORDER BY time) AS lag2,
        LAG(level_cm, 3) OVER (PARTITION BY sensor_id ORDER BY time) AS lag3,
        LAG(level_cm, 4) OVER (PARTITION BY sensor_id ORDER BY time) AS lag4,
        LAG(level_cm, 5) OVER (PARTITION BY sensor_id ORDER BY time) AS lag5,
        LAG(level_cm, 6) OVER (PARTITION BY sensor_id ORDER BY time) AS lag6,
        -- Next values (up to 6)
        LEAD(level_cm, 1) OVER (PARTITION BY sensor_id ORDER BY time) AS lead1,
        LEAD(level_cm, 2) OVER (PARTITION BY sensor_id ORDER BY time) AS lead2,
        LEAD(level_cm, 3) OVER (PARTITION BY sensor_id ORDER BY time) AS lead3,
        LEAD(level_cm, 4) OVER (PARTITION BY sensor_id ORDER BY time) AS lead4,
        LEAD(level_cm, 5) OVER (PARTITION BY sensor_id ORDER BY time) AS lead5,
        LEAD(level_cm, 6) OVER (PARTITION BY sensor_id ORDER BY time) AS lead6
    FROM raw_data
),
-- Stage 3: Calculate rolling median from window
median_calc AS (
    SELECT
        *,
        -- Create array of non-null values in window
        (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY val)
         FROM unnest(ARRAY[
            lag6, lag5, lag4, lag3, lag2, lag1,
            level_cm,
            lead1, lead2, lead3, lead4, lead5, lead6
         ]) AS val
         WHERE val IS NOT NULL
        ) AS window_median,
        -- Count non-null values in window
        (SELECT COUNT(*)
         FROM unnest(ARRAY[
            lag6, lag5, lag4, lag3, lag2, lag1,
            level_cm,
            lead1, lead2, lead3, lead4, lead5, lead6
         ]) AS val
         WHERE val IS NOT NULL
        ) AS window_count
    FROM windowed_data
),
-- Stage 4: Calculate MAD (Median Absolute Deviation)
mad_calc AS (
    SELECT
        *,
        -- Calculate MAD for the window
        (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ABS(val - window_median))
         FROM unnest(ARRAY[
            lag6, lag5, lag4, lag3, lag2, lag1,
            level_cm,
            lead1, lead2, lead3, lead4, lead5, lead6
         ]) AS val
         WHERE val IS NOT NULL
        ) AS mad
    FROM median_calc
),
-- Stage 5: Detect outliers via Hampel filter
outlier_detection AS (
    SELECT
        *,
        -- Hampel filter with kx = 2.5 (less aggressive for cleaner data)
        CASE
            WHEN level_cm IS NULL THEN true
            WHEN window_count < 3 THEN false  -- Not enough data
            WHEN mad = 0 THEN false  -- No variance
            WHEN ABS(level_cm - window_median) > (2.5 * GREATEST(mad, 0.5)) THEN true
            WHEN level_cm < 0 THEN true  -- Negative values are outliers
            ELSE false
        END AS is_outlier,
        -- Quality score based on window data availability
        CASE
            WHEN window_count >= 10 THEN 100.0
            WHEN window_count >= 7 THEN 90.0
            WHEN window_count >= 5 THEN 80.0
            WHEN window_count >= 3 THEN 70.0
            ELSE 50.0
        END AS quality_score
    FROM mad_calc
),
-- Stage 6: Replace outliers with median
cleaned_data AS (
    SELECT
        time,
        sensor_id,
        -- Replace outliers and negative values
        CASE
            WHEN is_outlier AND window_median IS NOT NULL THEN
                GREATEST(window_median, 0)  -- Ensure non-negative
            WHEN level_cm < 0 THEN
                COALESCE(window_median, 0)  -- Replace negative with median or 0
            ELSE level_cm
        END AS cleaned_level_cm,
        voltage,
        rssi,
        temperature,
        location_lat,
        location_lng,
        quality_score,
        row_num
    FROM outlier_detection
),
-- Stage 7: Apply recursive EMA (Exponential Moving Average)
ema_smooth AS (
    -- Initial row for each sensor
    SELECT
        time,
        sensor_id,
        cleaned_level_cm AS smoothed_level_cm,
        voltage,
        rssi,
        temperature,
        location_lat,
        location_lng,
        quality_score,
        row_num
    FROM cleaned_data
    WHERE row_num = 1

    UNION ALL

    -- Recursive case: apply EMA
    SELECT
        c.time,
        c.sensor_id,
        -- EMA formula with alpha = 0.3 (moderate smoothing)
        CASE
            WHEN c.cleaned_level_cm IS NULL THEN e.smoothed_level_cm
            ELSE (0.3 * c.cleaned_level_cm + 0.7 * e.smoothed_level_cm)
        END AS smoothed_level_cm,
        c.voltage,
        c.rssi,
        c.temperature,
        c.location_lat,
        c.location_lng,
        c.quality_score,
        c.row_num
    FROM cleaned_data c
    INNER JOIN ema_smooth e ON
        c.sensor_id = e.sensor_id AND
        c.row_num = e.row_num + 1
)
-- Stage 8: Insert smoothed data
INSERT INTO smoothed_water_level_readings (
    time,
    sensor_id,
    level_cm,
    voltage,
    rssi,
    temperature,
    quality_score,
    location_lat,
    location_lng
)
SELECT
    time,
    sensor_id,
    ROUND(smoothed_level_cm::numeric, 2),
    voltage,
    rssi,
    temperature,
    quality_score,
    location_lat,
    location_lng
FROM ema_smooth
ON CONFLICT (sensor_id, time) DO UPDATE SET
    level_cm = EXCLUDED.level_cm,
    voltage = EXCLUDED.voltage,
    rssi = EXCLUDED.rssi,
    temperature = EXCLUDED.temperature,
    quality_score = EXCLUDED.quality_score,
    location_lat = EXCLUDED.location_lat,
    location_lng = EXCLUDED.location_lng,
    created_at = NOW();

-- Report summary statistics
WITH summary AS (
    SELECT
        COUNT(*) AS total_rows,
        COUNT(DISTINCT sensor_id) AS sensors,
        MIN(time) AS earliest,
        MAX(time) AS latest,
        ROUND(AVG(level_cm), 2) AS avg_level,
        ROUND(AVG(quality_score), 1) AS avg_quality
    FROM smoothed_water_level_readings
)
SELECT
    'Backfill completed: ' || total_rows || ' rows smoothed across ' ||
    sensors || ' sensors from ' ||
    TO_CHAR(earliest, 'YYYY-MM-DD') || ' to ' ||
    TO_CHAR(latest, 'YYYY-MM-DD') ||
    ' (avg level: ' || avg_level || 'cm, avg quality: ' || avg_quality || ')'
    AS result
FROM summary;