-- Check trigger status
SELECT
    trigger_name,
    event_object_table,
    action_timing,
    event_manipulation,
    action_orientation,
    action_statement,
    is_trigger_enabled
FROM information_schema.triggers
WHERE trigger_name = 'trigger_smooth_water_level';

-- Check if function exists
SELECT
    routine_name,
    routine_type,
    data_type
FROM information_schema.routines
WHERE routine_name = 'fn_smooth_water_level_row';