-- Real-time smoothing trigger for water level readings
-- Applies Hampel Filter + EMA smoothing to new water level data as it arrives

-- Drop existing trigger and function if they exist
DROP TRIGGER IF EXISTS trigger_smooth_water_level ON water_level_readings;
DROP FUNCTION IF EXISTS fn_smooth_water_level_row();

-- Create the smoothing function
CREATE OR REPLACE FUNCTION fn_smooth_water_level_row()
RETURNS TRIGGER AS $$
DECLARE
    v_window_size INTEGER;
    v_kx NUMERIC;
    v_kv NUMERIC;
    v_alpha NUMERIC;
    v_window_data RECORD;
    v_median NUMERIC;
    v_mad NUMERIC;
    v_is_outlier BOOLEAN;
    v_cleaned_value NUMERIC;
    v_prev_smoothed NUMERIC;
    v_time_gap INTERVAL;
    v_gap_hours NUMERIC;
    v_adjusted_alpha NUMERIC;
    v_smoothed_value NUMERIC;
    v_quality_score NUMERIC;
BEGIN
    -- Skip if level is null
    IF NEW.level_cm IS NULL THEN
        RETURN NEW;
    END IF;

    -- Get smoothing parameters for this sensor (with fallback to wildcard)
    SELECT w, kx, kv, alpha INTO v_window_size, v_kx, v_kv, v_alpha
    FROM smoothing_params
    WHERE sensor_id = NEW.sensor_id
        OR sensor_id = 'AWD-*'
        OR sensor_id = '*'
    ORDER BY
        CASE
            WHEN sensor_id = NEW.sensor_id THEN 1
            WHEN sensor_id = 'AWD-*' THEN 2
            ELSE 3
        END
    LIMIT 1;

    -- Default parameters if not found
    IF v_window_size IS NULL THEN
        v_window_size := 12;
        v_kx := 2.5;
        v_kv := 3.5;
        v_alpha := 0.30;
    END IF;

    -- Get window data (last w readings including current)
    WITH window_data AS (
        SELECT level_cm, time
        FROM (
            SELECT level_cm, time
            FROM water_level_readings
            WHERE sensor_id = NEW.sensor_id
                AND time < NEW.time
                AND level_cm IS NOT NULL
            ORDER BY time DESC
            LIMIT v_window_size - 1
        ) past
        UNION ALL
        SELECT NEW.level_cm as level_cm, NEW.time as time
    ),
    median_calc AS (
        SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY level_cm) as median_value
        FROM window_data
    )
    SELECT
        COUNT(*) as count,
        median_calc.median_value as median,
        PERCENTILE_CONT(0.5) WITHIN GROUP (
            ORDER BY ABS(w.level_cm - median_calc.median_value)
        ) as mad
    INTO v_window_data
    FROM window_data w, median_calc
    GROUP BY median_calc.median_value;

    -- Extract values
    v_median := COALESCE(v_window_data.median, NEW.level_cm);
    v_mad := COALESCE(v_window_data.mad, 0);

    -- Outlier detection using Hampel filter
    v_is_outlier := FALSE;
    IF v_window_data.count >= 3 AND v_mad > 0 THEN
        IF ABS(NEW.level_cm - v_median) > (v_kx * GREATEST(v_mad, 0.5)) THEN
            v_is_outlier := TRUE;
        END IF;
    END IF;

    -- Also mark negative values and extreme values as outliers
    IF NEW.level_cm < 0 OR NEW.level_cm > 200 THEN
        v_is_outlier := TRUE;
    END IF;

    -- Clean the value
    IF v_is_outlier THEN
        v_cleaned_value := GREATEST(v_median, 0); -- Ensure non-negative
    ELSE
        v_cleaned_value := NEW.level_cm;
    END IF;

    -- Get previous smoothed value and calculate time gap
    SELECT
        level_cm,
        NEW.time - time AS time_gap
    INTO
        v_prev_smoothed,
        v_time_gap
    FROM smoothed_water_level_readings
    WHERE sensor_id = NEW.sensor_id
        AND time < NEW.time
    ORDER BY time DESC
    LIMIT 1;

    -- Apply EMA smoothing
    IF v_prev_smoothed IS NULL THEN
        -- First reading for this sensor
        v_smoothed_value := v_cleaned_value;
    ELSE
        -- Adjust alpha based on time gap (reduce weight for large gaps)
        v_gap_hours := EXTRACT(EPOCH FROM v_time_gap) / 3600.0;
        IF v_gap_hours > 1 THEN
            -- Reduce alpha for gaps > 1 hour
            v_adjusted_alpha := v_alpha * EXP(-v_gap_hours / 24.0);
        ELSE
            v_adjusted_alpha := v_alpha;
        END IF;

        -- Apply EMA formula
        v_smoothed_value := v_adjusted_alpha * v_cleaned_value + (1 - v_adjusted_alpha) * v_prev_smoothed;
    END IF;

    -- Calculate quality score
    v_quality_score := CASE
        WHEN v_window_data.count >= v_window_size THEN 100.0
        WHEN v_window_data.count >= v_window_size * 0.75 THEN 90.0
        WHEN v_window_data.count >= v_window_size * 0.5 THEN 80.0
        WHEN v_window_data.count >= 3 THEN 70.0
        ELSE 50.0
    END;

    -- Reduce quality if outlier detected
    IF v_is_outlier THEN
        v_quality_score := v_quality_score * 0.9;
    END IF;

    -- Insert or update smoothed reading
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
    ) VALUES (
        NEW.time,
        NEW.sensor_id,
        ROUND(v_smoothed_value::numeric, 2),
        NEW.voltage,
        NEW.rssi,
        NEW.temperature,
        v_quality_score,
        NEW.location_lat,
        NEW.location_lng
    )
    ON CONFLICT (sensor_id, time) DO UPDATE SET
        level_cm = EXCLUDED.level_cm,
        voltage = EXCLUDED.voltage,
        rssi = EXCLUDED.rssi,
        temperature = EXCLUDED.temperature,
        quality_score = EXCLUDED.quality_score,
        location_lat = EXCLUDED.location_lat,
        location_lng = EXCLUDED.location_lng,
        created_at = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger
CREATE TRIGGER trigger_smooth_water_level
AFTER INSERT ON water_level_readings
FOR EACH ROW
EXECUTE FUNCTION fn_smooth_water_level_row();

-- Verify trigger creation
SELECT
    'Trigger created: ' || trigger_name || ' on table ' || event_object_table AS status
FROM information_schema.triggers
WHERE trigger_name = 'trigger_smooth_water_level';