-- Update ros.plots with correct zone and section assignments based on sub_member

-- First, let's check what we imported
SELECT 'Imported data summary:' as info;
SELECT COUNT(*) as total_records,
       COUNT(DISTINCT sub_member) as unique_sub_members,
       MIN(sub_member) as min_sub_member,
       MAX(sub_member) as max_sub_member
FROM ros.plots_temp;

-- Show distribution by sub_member
SELECT 'Distribution by sub_member:' as info;
SELECT sub_member, COUNT(*) as count 
FROM ros.plots_temp 
GROUP BY sub_member 
ORDER BY sub_member
LIMIT 20;

-- Update ros.plots with correct zone and section assignments
UPDATE ros.plots p
SET parent_zone_id = CASE 
        WHEN t.sub_member IS NOT NULL 
        THEN 'zone_' || ((t.sub_member - 1) / 3 + 1)
        ELSE 'zone_1'
    END,
    parent_section_id = CASE 
        WHEN t.sub_member IS NOT NULL 
        THEN 'section_' || ((t.sub_member - 1) / 10 + 1)
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

-- Show sample of updated data
SELECT 'Sample updated data:' as info;
SELECT plot_id, area_rai, parent_zone_id, parent_section_id
FROM ros.plots
WHERE parent_zone_id != 'zone_1'
LIMIT 10;