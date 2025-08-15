-- Add area_rai column to agricultural_plots table
ALTER TABLE gis.agricultural_plots 
ADD COLUMN IF NOT EXISTS area_rai NUMERIC(10,2) 
GENERATED ALWAYS AS (area_hectares * 6.25) STORED;

-- Add comment to explain the column
COMMENT ON COLUMN gis.agricultural_plots.area_rai IS 'Area in rai (Thai unit), automatically calculated from hectares (1 hectare = 6.25 rai)';

-- Create index on area_rai for better query performance
CREATE INDEX IF NOT EXISTS idx_agricultural_plots_area_rai ON gis.agricultural_plots(area_rai);

-- Update statistics for query planner
ANALYZE gis.agricultural_plots;