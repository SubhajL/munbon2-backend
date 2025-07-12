-- Add properties JSONB column to agricultural_plots table
ALTER TABLE gis.agricultural_plots 
ADD COLUMN IF NOT EXISTS properties JSONB;

-- Add comment separately
COMMENT ON COLUMN gis.agricultural_plots.properties 
IS 'Additional properties including RID attributes, water demand, etc.';

-- Create index on properties for better query performance
CREATE INDEX IF NOT EXISTS idx_agricultural_plots_properties 
ON gis.agricultural_plots USING GIN (properties);

-- Example query to see water demand data after shapefile import:
-- SELECT 
--   plot_code,
--   properties->'ridAttributes'->>'seasonIrrM3PerRai' as water_demand_m3_per_rai,
--   properties->'ridAttributes'->>'age' as plant_age,
--   properties->'ridAttributes'->>'yieldAtMcKgpr' as expected_yield
-- FROM gis.agricultural_plots
-- WHERE properties IS NOT NULL;