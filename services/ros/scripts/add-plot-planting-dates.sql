-- Add planting date columns to plots table
ALTER TABLE ros.plots 
ADD COLUMN IF NOT EXISTS current_planting_date DATE,
ADD COLUMN IF NOT EXISTS current_crop_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS current_crop_status VARCHAR(20) DEFAULT 'active';

-- Add index for planting dates
CREATE INDEX IF NOT EXISTS idx_plots_planting_date ON ros.plots(current_planting_date);
CREATE INDEX IF NOT EXISTS idx_plots_crop_status ON ros.plots(current_crop_status);

-- Update plots with current planting data from seasonal calculations
UPDATE ros.plots p
SET 
    current_planting_date = '2024-07-14',
    current_crop_type = 'rice',
    current_crop_status = 'active'
WHERE EXISTS (
    SELECT 1 
    FROM ros.plot_water_demand_seasonal pwd
    WHERE pwd.plot_id = p.plot_id 
    AND pwd.planting_date = '2024-07-14'
);

-- Populate plot_crop_schedule table with current season data
INSERT INTO ros.plot_crop_schedule (
    plot_id,
    crop_type,
    planting_date,
    expected_harvest_date,
    season,
    year,
    status
)
SELECT 
    p.plot_id,
    'rice' as crop_type,
    '2024-07-14'::date as planting_date,
    '2024-11-03'::date as expected_harvest_date, -- 16 weeks after planting
    'wet' as season,
    2024 as year,
    'active' as status
FROM ros.plots p
WHERE NOT EXISTS (
    SELECT 1 
    FROM ros.plot_crop_schedule pcs
    WHERE pcs.plot_id = p.plot_id 
    AND pcs.year = 2024 
    AND pcs.season = 'wet'
)
ORDER BY p.plot_id;

-- Create a view for easy access to current crop information
CREATE OR REPLACE VIEW ros.v_plots_current_crop AS
SELECT 
    p.plot_id,
    p.plot_code,
    p.area_rai,
    p.parent_zone_id,
    p.parent_section_id,
    p.current_planting_date,
    p.current_crop_type,
    p.current_crop_status,
    pwd.total_water_demand_m3,
    pwd.total_net_water_demand_m3,
    pwd.land_preparation_m3,
    CASE 
        WHEN p.current_planting_date IS NOT NULL THEN
            EXTRACT(WEEK FROM AGE(CURRENT_DATE, p.current_planting_date))::INTEGER + 1
        ELSE NULL
    END as current_crop_week,
    CASE 
        WHEN p.current_planting_date IS NOT NULL THEN
            p.current_planting_date + INTERVAL '16 weeks'
        ELSE NULL
    END as expected_harvest_date
FROM ros.plots p
LEFT JOIN ros.plot_water_demand_seasonal pwd ON 
    pwd.plot_id = p.plot_id 
    AND pwd.planting_date = p.current_planting_date
    AND pwd.crop_type = p.current_crop_type;

-- Summary of updates
SELECT 
    COUNT(*) as total_plots,
    COUNT(current_planting_date) as plots_with_planting_date,
    COUNT(DISTINCT current_crop_type) as crop_types,
    MIN(current_planting_date) as earliest_planting,
    MAX(current_planting_date) as latest_planting
FROM ros.plots;