-- Import parcels from agricultural_plots to ros.plots table
-- with zone/section assignment based on sub_member field

-- Create ros schema if not exists
CREATE SCHEMA IF NOT EXISTS ros;

-- Create plots table if not exists
CREATE TABLE IF NOT EXISTS ros.plots (
    id SERIAL PRIMARY KEY,
    plot_id VARCHAR(50) UNIQUE NOT NULL,
    plot_code VARCHAR(50),
    area_rai DECIMAL(10,2) NOT NULL,
    geometry GEOMETRY(Polygon, 32648),
    parent_section_id VARCHAR(50),
    parent_zone_id VARCHAR(50),
    aos_station VARCHAR(100) DEFAULT 'นครราชสีมา',
    province VARCHAR(100) DEFAULT 'นครราชสีมา',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_plots_geometry ON ros.plots USING GIST(geometry);
CREATE INDEX IF NOT EXISTS idx_plots_parent_section ON ros.plots(parent_section_id);
CREATE INDEX IF NOT EXISTS idx_plots_parent_zone ON ros.plots(parent_zone_id);

-- Show source data summary
SELECT 'Source data summary:' as info;
SELECT COUNT(*) as total_parcels,
       COUNT(DISTINCT (properties->>'ridAttributes')::jsonb->>'subMember') as unique_sub_members,
       MIN(area_rai) as min_area_rai,
       MAX(area_rai) as max_area_rai,
       SUM(area_rai) as total_area_rai
FROM gis.agricultural_plots;

-- Show sample data
SELECT 'Sample source data:' as info;
SELECT plot_code,
       area_rai,
       (properties->>'ridAttributes')::jsonb->>'subMember' as sub_member,
       ST_GeometryType(boundary) as geom_type
FROM gis.agricultural_plots
LIMIT 5;

-- Clear existing data
TRUNCATE TABLE ros.plots RESTART IDENTITY CASCADE;

-- Copy data from agricultural_plots to ros.plots
INSERT INTO ros.plots (
    plot_id,
    plot_code,
    area_rai,
    geometry,
    parent_section_id,
    parent_zone_id,
    aos_station,
    province
)
SELECT 
    plot_code as plot_id,
    plot_code,
    area_rai,
    ST_Transform(boundary, 32648) as geometry,  -- Transform from 4326 to 32648
    CASE 
        WHEN (properties->>'ridAttributes')::jsonb->>'subMember' IS NOT NULL 
        THEN 'section_' || (((properties->>'ridAttributes')::jsonb->>'subMember')::int - 1) / 10 + 1
        ELSE 'section_1'
    END as parent_section_id,
    CASE 
        WHEN (properties->>'ridAttributes')::jsonb->>'subMember' IS NOT NULL 
        THEN 'zone_' || (((properties->>'ridAttributes')::jsonb->>'subMember')::int - 1) / 3 + 1
        ELSE 'zone_1'
    END as parent_zone_id,
    'นครราชสีมา' as aos_station,
    'นครราชสีมา' as province
FROM gis.agricultural_plots
WHERE plot_code IS NOT NULL
  AND boundary IS NOT NULL
  AND area_rai IS NOT NULL
ON CONFLICT (plot_id) DO UPDATE SET
    plot_code = EXCLUDED.plot_code,
    area_rai = EXCLUDED.area_rai,
    geometry = EXCLUDED.geometry,
    parent_section_id = EXCLUDED.parent_section_id,
    parent_zone_id = EXCLUDED.parent_zone_id,
    updated_at = NOW();

-- Show results
SELECT 'Import results:' as info;
SELECT COUNT(*) as total_imported FROM ros.plots;

SELECT 'Parcels by zone:' as info;
SELECT parent_zone_id, COUNT(*) as count 
FROM ros.plots 
GROUP BY parent_zone_id 
ORDER BY parent_zone_id;

SELECT 'Parcels by section:' as info;
SELECT parent_section_id, COUNT(*) as count 
FROM ros.plots 
GROUP BY parent_section_id 
ORDER BY parent_section_id;

SELECT 'Area summary:' as info;
SELECT 
    COUNT(*) as total_plots,
    ROUND(SUM(area_rai)::numeric, 2) as total_rai,
    ROUND(AVG(area_rai)::numeric, 2) as avg_rai,
    ROUND(MIN(area_rai)::numeric, 2) as min_rai,
    ROUND(MAX(area_rai)::numeric, 2) as max_rai
FROM ros.plots;