-- Add water demand per rai columns to plot_water_demand_weekly table
-- These columns will store water demand values normalized per rai for easier comparison

SET search_path TO ros, public;

-- Add crop_water_demand_m3_per_rai column
ALTER TABLE ros.plot_water_demand_weekly 
ADD COLUMN IF NOT EXISTS crop_water_demand_m3_per_rai DECIMAL(15,2);

-- Add net_water_demand_m3_per_rai column  
ALTER TABLE ros.plot_water_demand_weekly
ADD COLUMN IF NOT EXISTS net_water_demand_m3_per_rai DECIMAL(15,2);

-- Add comments for the new columns
COMMENT ON COLUMN ros.plot_water_demand_weekly.crop_water_demand_m3_per_rai 
    IS 'Crop water demand in cubic meters per rai (m³/rai)';

COMMENT ON COLUMN ros.plot_water_demand_weekly.net_water_demand_m3_per_rai 
    IS 'Net water demand after rainfall in cubic meters per rai (m³/rai)';

-- Update existing records to calculate per rai values
UPDATE ros.plot_water_demand_weekly
SET 
    crop_water_demand_m3_per_rai = CASE 
        WHEN area_rai > 0 THEN crop_water_demand_m3 / area_rai
        ELSE NULL
    END,
    net_water_demand_m3_per_rai = CASE
        WHEN area_rai > 0 THEN net_water_demand_m3 / area_rai  
        ELSE NULL
    END
WHERE crop_water_demand_m3_per_rai IS NULL 
   OR net_water_demand_m3_per_rai IS NULL;

-- Create index on the new columns for better query performance
CREATE INDEX IF NOT EXISTS idx_plot_water_demand_weekly_per_rai 
ON ros.plot_water_demand_weekly(crop_water_demand_m3_per_rai, net_water_demand_m3_per_rai);

-- Verify the changes
SELECT 
    column_name,
    data_type,
    numeric_precision,
    numeric_scale,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'ros' 
  AND table_name = 'plot_water_demand_weekly'
  AND column_name IN ('crop_water_demand_m3_per_rai', 'net_water_demand_m3_per_rai')
ORDER BY ordinal_position;

-- Show sample data with the new columns
SELECT 
    plot_id,
    crop_type,
    crop_week,
    area_rai,
    crop_water_demand_m3,
    crop_water_demand_m3_per_rai,
    net_water_demand_m3,
    net_water_demand_m3_per_rai
FROM ros.plot_water_demand_weekly
WHERE area_rai > 0
LIMIT 5;