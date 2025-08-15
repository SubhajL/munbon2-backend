-- Create a view for area summary by zone
CREATE OR REPLACE VIEW gis.v_area_summary_by_zone AS
SELECT 
  z.zone_code,
  z.zone_name,
  COUNT(p.id) as plot_count,
  ROUND(SUM(p.area_hectares)::numeric, 2) as total_hectares,
  ROUND(SUM(p.area_rai)::numeric, 2) as total_rai,
  ROUND(AVG(p.area_hectares)::numeric, 2) as avg_hectares,
  ROUND(AVG(p.area_rai)::numeric, 2) as avg_rai,
  ROUND(MIN(p.area_hectares)::numeric, 2) as min_hectares,
  ROUND(MIN(p.area_rai)::numeric, 2) as min_rai,
  ROUND(MAX(p.area_hectares)::numeric, 2) as max_hectares,
  ROUND(MAX(p.area_rai)::numeric, 2) as max_rai
FROM gis.agricultural_plots p
LEFT JOIN gis.irrigation_zones z ON p.zone_id = z.id
GROUP BY z.id, z.zone_code, z.zone_name
ORDER BY z.zone_code;

-- Create a view for area distribution
CREATE OR REPLACE VIEW gis.v_area_distribution AS
WITH categorized_plots AS (
  SELECT 
    area_hectares,
    area_rai,
    CASE 
      WHEN area_rai < 1 THEN '< 1 rai'
      WHEN area_rai < 5 THEN '1-5 rai'
      WHEN area_rai < 10 THEN '5-10 rai'
      WHEN area_rai < 20 THEN '10-20 rai'
      WHEN area_rai < 50 THEN '20-50 rai'
      WHEN area_rai < 100 THEN '50-100 rai'
      ELSE '> 100 rai'
    END as size_range,
    CASE 
      WHEN area_rai < 1 THEN 1
      WHEN area_rai < 5 THEN 2
      WHEN area_rai < 10 THEN 3
      WHEN area_rai < 20 THEN 4
      WHEN area_rai < 50 THEN 5
      WHEN area_rai < 100 THEN 6
      ELSE 7
    END as sort_order
  FROM gis.agricultural_plots
)
SELECT 
  size_range,
  COUNT(*) as plot_count,
  ROUND(SUM(area_hectares)::numeric, 2) as total_hectares,
  ROUND(SUM(area_rai)::numeric, 2) as total_rai,
  ROUND((COUNT(*) * 100.0 / SUM(COUNT(*)) OVER ())::numeric, 2) as percentage
FROM categorized_plots
GROUP BY size_range, sort_order
ORDER BY sort_order;

COMMENT ON VIEW gis.v_area_summary_by_zone IS 'Summary of agricultural plot areas by irrigation zone in both hectares and rai';
COMMENT ON VIEW gis.v_area_distribution IS 'Distribution of agricultural plots by size ranges in rai';