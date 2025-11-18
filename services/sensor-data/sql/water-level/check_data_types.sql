-- Check data types and constraints for water level tables

SELECT
    column_name,
    data_type,
    numeric_precision,
    numeric_scale,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'water_level_readings'
    AND column_name IN ('level_cm', 'voltage', 'temperature', 'quality_score')
ORDER BY ordinal_position;