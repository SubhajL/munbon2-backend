-- Check if smoothing_params table exists and its current content
SELECT
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'smoothing_params'
    ) THEN 'Table smoothing_params EXISTS'
    ELSE 'Table smoothing_params DOES NOT EXIST'
    END AS table_status;

-- If table exists, show its content
SELECT * FROM smoothing_params
WHERE sensor_id LIKE 'AWD-%' OR sensor_id = '*'
ORDER BY sensor_id;