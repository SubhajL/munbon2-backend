-- Sample data for Munbon Irrigation Project
-- This file provides test data for development

-- Insert sample irrigation zones
INSERT INTO gis.irrigation_zones (zone_code, zone_name, zone_type, area_hectares, boundary) VALUES
('Z001', 'Zone 1 - North Munbon', 'primary', 2500.50, ST_GeomFromText('POLYGON((102.15 14.68, 102.18 14.68, 102.18 14.70, 102.15 14.70, 102.15 14.68))', 4326)),
('Z002', 'Zone 2 - Central Munbon', 'primary', 3200.75, ST_GeomFromText('POLYGON((102.18 14.66, 102.21 14.66, 102.21 14.68, 102.18 14.68, 102.18 14.66))', 4326)),
('Z003', 'Zone 3 - South Munbon', 'primary', 2800.25, ST_GeomFromText('POLYGON((102.15 14.64, 102.18 14.64, 102.18 14.66, 102.15 14.66, 102.15 14.64))', 4326)),
('Z001-A', 'Zone 1A - Ban Kham', 'secondary', 450.30, ST_GeomFromText('POLYGON((102.155 14.685, 102.165 14.685, 102.165 14.695, 102.155 14.695, 102.155 14.685))', 4326)),
('Z001-B', 'Zone 1B - Ban Don', 'secondary', 380.20, ST_GeomFromText('POLYGON((102.165 14.685, 102.175 14.685, 102.175 14.695, 102.165 14.695, 102.165 14.685))', 4326));

-- Insert sample canal network
INSERT INTO gis.canal_network (canal_code, canal_name, canal_type, length_meters, width_meters, depth_meters, capacity_cms, geometry) VALUES
('MC-001', 'Main Canal North', 'main', 15000, 20.0, 3.5, 45.0, ST_GeomFromText('LINESTRING(102.15 14.70, 102.18 14.68, 102.21 14.66)', 4326)),
('LC-001', 'Lateral Canal 1', 'lateral', 5000, 10.0, 2.5, 15.0, ST_GeomFromText('LINESTRING(102.16 14.69, 102.16 14.67, 102.16 14.65)', 4326)),
('LC-002', 'Lateral Canal 2', 'lateral', 4500, 8.0, 2.0, 12.0, ST_GeomFromText('LINESTRING(102.17 14.69, 102.17 14.67, 102.17 14.65)', 4326)),
('SL-001', 'Sub-lateral 1A', 'sub-lateral', 2000, 4.0, 1.5, 3.0, ST_GeomFromText('LINESTRING(102.155 14.685, 102.155 14.675, 102.155 14.665)', 4326));

-- Insert sample control structures (gates)
INSERT INTO gis.control_structures (structure_code, structure_name, structure_type, location, elevation_msl, max_discharge_cms, scada_tag, operational_status) VALUES
('G-001', 'Main Gate North', 'gate', ST_GeomFromText('POINT(102.15 14.70)', 4326), 125.5, 45.0, 'SCADA.G001.FLOW', 'active'),
('G-002', 'Lateral Gate 1', 'gate', ST_GeomFromText('POINT(102.16 14.69)', 4326), 124.8, 15.0, 'SCADA.G002.FLOW', 'active'),
('G-003', 'Lateral Gate 2', 'gate', ST_GeomFromText('POINT(102.17 14.69)', 4326), 124.5, 12.0, 'SCADA.G003.FLOW', 'active'),
('W-001', 'Check Weir 1', 'weir', ST_GeomFromText('POINT(102.18 14.68)', 4326), 123.0, 50.0, NULL, 'active'),
('P-001', 'Pump Station 1', 'pump', ST_GeomFromText('POINT(102.155 14.685)', 4326), 122.5, 5.0, 'SCADA.P001.STATUS', 'active');

-- Insert sample sensor locations
INSERT INTO gis.sensor_locations (sensor_code, sensor_name, sensor_type, location, elevation_msl, installation_date, status) VALUES
('WL-001', 'Water Level Sensor - Main North', 'water_level', ST_GeomFromText('POINT(102.15 14.70)', 4326), 125.5, '2024-01-15', 'active'),
('WL-002', 'Water Level Sensor - Lateral 1', 'water_level', ST_GeomFromText('POINT(102.16 14.69)', 4326), 124.8, '2024-01-20', 'active'),
('WQ-001', 'Water Quality Station 1', 'water_quality', ST_GeomFromText('POINT(102.17 14.68)', 4326), 124.0, '2024-02-01', 'active'),
('SM-001', 'Soil Moisture - Zone 1', 'soil_moisture', ST_GeomFromText('POINT(102.156 14.686)', 4326), 126.0, '2024-02-15', 'active'),
('SM-002', 'Soil Moisture - Zone 2', 'soil_moisture', ST_GeomFromText('POINT(102.186 14.666)', 4326), 125.5, '2024-02-15', 'active');

-- Insert sample weather stations
INSERT INTO gis.weather_stations (station_code, station_name, location, elevation_msl, installation_date, data_logger_type, status) VALUES
('WS-001', 'Munbon North Weather Station', ST_GeomFromText('POINT(102.16 14.70)', 4326), 128.0, '2023-12-01', 'Campbell CR1000', 'active'),
('WS-002', 'Munbon South Weather Station', ST_GeomFromText('POINT(102.17 14.65)', 4326), 126.5, '2023-12-15', 'Campbell CR1000', 'active');

-- Insert sample agricultural plots
INSERT INTO gis.agricultural_plots (plot_code, owner_name, area_hectares, crop_type, irrigation_zone_id, geometry, land_use_type, soil_type) VALUES
('PLT-001', 'นายสมชาย ใจดี', 15.5, 'rice', (SELECT id FROM gis.irrigation_zones WHERE zone_code = 'Z001'), 
    ST_GeomFromText('POLYGON((102.156 14.686, 102.158 14.686, 102.158 14.688, 102.156 14.688, 102.156 14.686))', 4326), 'irrigated', 'clay_loam'),
('PLT-002', 'นางสมหญิง รักดี', 12.3, 'rice', (SELECT id FROM gis.irrigation_zones WHERE zone_code = 'Z001'), 
    ST_GeomFromText('POLYGON((102.158 14.686, 102.160 14.686, 102.160 14.688, 102.158 14.688, 102.158 14.686))', 4326), 'irrigated', 'clay_loam'),
('PLT-003', 'นายวิชัย เกษตรกร', 18.7, 'sugarcane', (SELECT id FROM gis.irrigation_zones WHERE zone_code = 'Z002'), 
    ST_GeomFromText('POLYGON((102.186 14.666, 102.188 14.666, 102.188 14.668, 102.186 14.668, 102.186 14.666))', 4326), 'irrigated', 'sandy_loam'),
('PLT-004', 'นางสาวมาลี ขยันทำ', 8.9, 'cassava', (SELECT id FROM gis.irrigation_zones WHERE zone_code = 'Z002'), 
    ST_GeomFromText('POLYGON((102.188 14.666, 102.190 14.666, 102.190 14.668, 102.188 14.668, 102.188 14.666))', 4326), 'rainfed', 'sandy');

-- Verify data insertion
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