-- Verify RID Plan data import
-- Run this script in PostgreSQL to check the imported data

-- Check total count of RID Plan parcels
SELECT COUNT(*) as total_rid_parcels
FROM gis.agricultural_plots
WHERE properties->>'uploadId' LIKE 'ridplan-%';

-- Check distribution by amphoe
SELECT 
    properties->'location'->>'amphoe' as amphoe,
    COUNT(*) as parcel_count,
    SUM(area_hectares * 6.25) as total_area_rai,
    AVG(area_hectares * 6.25) as avg_area_rai
FROM gis.agricultural_plots
WHERE properties->>'uploadId' LIKE 'ridplan-%'
GROUP BY properties->'location'->>'amphoe'
ORDER BY parcel_count DESC
LIMIT 10;

-- Check sample parcel data
SELECT 
    id,
    plot_code,
    area_hectares * 6.25 as area_rai,
    current_crop_type,
    properties->'location'->>'amphoe' as amphoe,
    properties->'location'->>'tambon' as tambon,
    properties->'ridAttributes'->>'yieldAtMcKgpr' as yield_kg_per_rai,
    properties->'ridAttributes'->>'seasonIrrM3PerRai' as water_m3_per_rai,
    ST_AsText(ST_Centroid(boundary)) as centroid
FROM gis.agricultural_plots
WHERE properties->>'uploadId' LIKE 'ridplan-%'
LIMIT 5;

-- Check geometry types and validity
SELECT 
    ST_GeometryType(boundary) as geom_type,
    COUNT(*) as count,
    SUM(CASE WHEN ST_IsValid(boundary) THEN 1 ELSE 0 END) as valid_count,
    SUM(CASE WHEN NOT ST_IsValid(boundary) THEN 1 ELSE 0 END) as invalid_count
FROM gis.agricultural_plots
WHERE properties->>'uploadId' LIKE 'ridplan-%'
GROUP BY ST_GeometryType(boundary);

-- Calculate total water demand
SELECT 
    SUM(
        CAST(properties->'ridAttributes'->>'seasonIrrM3PerRai' AS FLOAT) * 
        area_hectares * 6.25
    ) / 1000000 as total_water_demand_million_m3,
    SUM(area_hectares * 6.25) as total_area_rai,
    AVG(CAST(properties->'ridAttributes'->>'seasonIrrM3PerRai' AS FLOAT)) as avg_water_per_rai
FROM gis.agricultural_plots
WHERE properties->>'uploadId' LIKE 'ridplan-%'
    AND properties->'ridAttributes'->>'seasonIrrM3PerRai' IS NOT NULL;

-- Check crop type distribution
SELECT 
    COALESCE(properties->'ridAttributes'->>'plantId', current_crop_type) as crop_type,
    COUNT(*) as parcel_count,
    SUM(area_hectares * 6.25) as total_area_rai
FROM gis.agricultural_plots
WHERE properties->>'uploadId' LIKE 'ridplan-%'
GROUP BY COALESCE(properties->'ridAttributes'->>'plantId', current_crop_type)
ORDER BY parcel_count DESC;