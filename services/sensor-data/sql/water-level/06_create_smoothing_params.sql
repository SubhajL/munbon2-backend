-- Add smoothing parameters for water level sensors (AWD-*)
-- These parameters are tuned for water level data which has different characteristics than moisture

-- First, check if we need to adjust the wildcard default for AWD sensors
-- Water level data needs slightly more aggressive smoothing based on our analysis

-- Insert specific parameters for AWD sensors
-- Using the existing upsert function that was created for moisture sensors
DO $$
BEGIN
    -- AWD sensors generally need more aggressive smoothing than moisture sensors
    -- Based on our baseline analysis:
    -- - AWD-B89D has high variance (stddev 7.19)
    -- - AWD-4ED4 and AWD-558F have moderate variance (stddev ~3.5-4)
    -- - Other sensors are relatively stable

    -- High variance sensor - more aggressive smoothing
    PERFORM upsert_smoothing_params('AWD-B89D', 15, 2.5, 3.5, 0.35);

    -- Moderate variance sensors
    PERFORM upsert_smoothing_params('AWD-4ED4', 12, 2.5, 3.5, 0.30);
    PERFORM upsert_smoothing_params('AWD-558F', 12, 2.5, 3.5, 0.30);
    PERFORM upsert_smoothing_params('AWD-6D47', 12, 3.0, 4.0, 0.25);

    -- Stable sensors - light smoothing
    PERFORM upsert_smoothing_params('AWD-9950', 10, 3.0, 4.0, 0.20);
    PERFORM upsert_smoothing_params('AWD-A4F8', 8, 3.5, 4.5, 0.15);

    -- Update wildcard default specifically for AWD pattern if needed
    -- This will be used for any new AWD sensors not explicitly configured
    PERFORM upsert_smoothing_params('AWD-*', 12, 2.5, 3.5, 0.30);

END $$;

-- Verify the parameters were set
SELECT
    sensor_id,
    w AS window_size,
    kx AS hampel_kx,
    kv AS hampel_kv,
    alpha AS ema_alpha,
    updated_at
FROM smoothing_params
WHERE sensor_id LIKE 'AWD-%' OR sensor_id = 'AWD-*'
ORDER BY
    CASE
        WHEN sensor_id = 'AWD-*' THEN 1  -- Wildcard first
        ELSE 0
    END,
    sensor_id;

-- Summary of parameter meanings:
-- w: Window size for median calculation (higher = more context)
-- kx: Hampel filter constant for outlier detection (lower = more aggressive)
-- kv: Hampel filter constant for time-scaled detection (lower = more aggressive)
-- alpha: EMA smoothing factor (higher = more weight on new values, less smoothing)