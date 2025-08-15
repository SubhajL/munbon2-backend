-- Update ros.plots with correct zone and section assignments based on sub_member

-- First check the data type of sub_member
SELECT 'Data type check:' as info;
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_schema = 'ros' AND table_name = 'plots_temp' AND column_name = 'sub_member';

-- Update ros.plots with correct zone and section assignments
UPDATE ros.plots p
SET parent_zone_id = CASE 
        WHEN t.sub_member IS NOT NULL 
        THEN 'zone_' || ((t.sub_member::INTEGER - 1) / 3 + 1)
        ELSE 'zone_1'
    END,
    parent_section_id = CASE 
        WHEN t.sub_member IS NOT NULL 
        THEN 'section_' || ((t.sub_member::INTEGER - 1) / 10 + 1)
        ELSE 'section_1'
    END,
    updated_at = NOW()
FROM ros.plots_temp t
WHERE p.plot_id = t.parcel_seq;

-- Verify the update
SELECT 'Updated zone distribution:' as info;
SELECT parent_zone_id, COUNT(*) as count 
FROM ros.plots 
GROUP BY parent_zone_id 
ORDER BY parent_zone_id;

SELECT 'Updated section distribution:' as info;
SELECT parent_section_id, COUNT(*) as count 
FROM ros.plots 
GROUP BY parent_section_id 
ORDER BY parent_section_id;

-- Show zone assignment logic verification
SELECT 'Zone assignment verification:' as info;
SELECT DISTINCT 
    sub_member,
    'zone_' || ((sub_member::INTEGER - 1) / 3 + 1) as calculated_zone,
    'section_' || ((sub_member::INTEGER - 1) / 10 + 1) as calculated_section
FROM ros.plots_temp
WHERE sub_member IS NOT NULL
ORDER BY sub_member;

-- Show sample of updated data
SELECT 'Sample updated data:' as info;
SELECT p.plot_id, p.area_rai, p.parent_zone_id, p.parent_section_id, t.sub_member
FROM ros.plots p
JOIN ros.plots_temp t ON p.plot_id = t.parcel_seq
WHERE p.parent_zone_id != 'zone_1'
LIMIT 10;