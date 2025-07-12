-- Fixed sample data matching actual table schemas

-- First check what we already have
SELECT 'Already loaded - Irrigation Zones' as status, COUNT(*) as count FROM gis.irrigation_zones WHERE COUNT(*) > 0
UNION ALL
SELECT 'Already loaded - Canal Network', COUNT(*) FROM gis.canal_network WHERE COUNT(*) > 0
UNION ALL
SELECT 'Already loaded - Control Structures', COUNT(*) FROM gis.control_structures WHERE COUNT(*) > 0;

-- Insert sample sensor locations (using correct column names)
INSERT INTO gis.sensor_locations (sensor_id, location, elevation_msl, installation_date, is_mobile, zone_id) 
SELECT 
    'WL-001', 
    ST_GeomFromText('POINT(102.15 14.70)', 4326), 
    125.5, 
    '2024-01-15'::date, 
    false,
    (SELECT id FROM gis.irrigation_zones WHERE zone_code = 'Z001' LIMIT 1)
WHERE NOT EXISTS (SELECT 1 FROM gis.sensor_locations WHERE sensor_id = 'WL-001');

INSERT INTO gis.sensor_locations (sensor_id, location, elevation_msl, installation_date, is_mobile, zone_id) VALUES
('WL-002', ST_GeomFromText('POINT(102.16 14.69)', 4326), 124.8, '2024-01-20', false, (SELECT id FROM gis.irrigation_zones WHERE zone_code = 'Z001' LIMIT 1)),
('WQ-001', ST_GeomFromText('POINT(102.17 14.68)', 4326), 124.0, '2024-02-01', false, (SELECT id FROM gis.irrigation_zones WHERE zone_code = 'Z002' LIMIT 1)),
('SM-001', ST_GeomFromText('POINT(102.156 14.686)', 4326), 126.0, '2024-02-15', true, (SELECT id FROM gis.irrigation_zones WHERE zone_code = 'Z001' LIMIT 1)),
('SM-002', ST_GeomFromText('POINT(102.186 14.666)', 4326), 125.5, '2024-02-15', true, (SELECT id FROM gis.irrigation_zones WHERE zone_code = 'Z002' LIMIT 1))
ON CONFLICT (sensor_id) DO NOTHING;

-- Check weather_stations structure and insert if columns exist
DO $$
BEGIN
    -- Insert weather stations if table has expected columns
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'gis' 
        AND table_name = 'weather_stations' 
        AND column_name = 'station_id'
    ) THEN
        INSERT INTO gis.weather_stations (station_id, location, elevation_msl) VALUES
        ('WS-001', ST_GeomFromText('POINT(102.16 14.70)', 4326), 128.0),
        ('WS-002', ST_GeomFromText('POINT(102.17 14.65)', 4326), 126.5)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Check agricultural_plots structure
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_schema = 'gis' 
AND table_name = 'agricultural_plots'
ORDER BY ordinal_position;

-- Insert agricultural plots using actual column names
INSERT INTO gis.agricultural_plots (plot_id, farmer_id, area_hectares, zone_id, geometry)
SELECT 
    'PLT-001',
    '00000000-0000-0000-0000-000000000001'::uuid, -- placeholder farmer_id
    15.5,
    (SELECT id FROM gis.irrigation_zones WHERE zone_code = 'Z001' LIMIT 1),
    ST_GeomFromText('POLYGON((102.156 14.686, 102.158 14.686, 102.158 14.688, 102.156 14.688, 102.156 14.686))', 4326)
WHERE EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_schema = 'gis' 
    AND table_name = 'agricultural_plots' 
    AND column_name = 'plot_id'
)
ON CONFLICT DO NOTHING;

-- Final count verification
SELECT 'Irrigation Zones' as table_name, COUNT(*) as count FROM gis.irrigation_zones
UNION ALL
SELECT 'Canal Network', COUNT(*) FROM gis.canal_network
UNION ALL
SELECT 'Control Structures', COUNT(*) FROM gis.control_structures
UNION ALL
SELECT 'Sensor Locations', COUNT(*) FROM gis.sensor_locations
UNION ALL
SELECT 'Weather Stations', COUNT(*) FROM gis.weather_stations
UNION ALL
SELECT 'Agricultural Plots', COUNT(*) FROM gis.agricultural_plots;