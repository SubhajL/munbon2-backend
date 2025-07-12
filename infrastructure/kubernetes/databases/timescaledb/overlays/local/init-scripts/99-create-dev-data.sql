\c sensor_data;

-- Insert sample sensors for development
INSERT INTO sensor.sensors (sensor_id, sensor_type, location, region, zone, metadata) VALUES
-- Moisture sensors
('MS001', 'moisture', ST_GeogFromText('POINT(100.5342 13.7279)'), 'North', 'Zone-1', '{"depth": "30cm", "soil_type": "clay"}'),
('MS002', 'moisture', ST_GeogFromText('POINT(100.5456 13.7356)'), 'North', 'Zone-1', '{"depth": "30cm", "soil_type": "loam"}'),
('MS003', 'moisture', ST_GeogFromText('POINT(100.5234 13.7189)'), 'North', 'Zone-2', '{"depth": "60cm", "soil_type": "clay"}'),
-- Water level sensors
('WL001', 'water_level', ST_GeogFromText('POINT(100.5123 13.7234)'), 'North', 'Main-Canal', '{"type": "ultrasonic", "range": "0-10m"}'),
('WL002', 'water_level', ST_GeogFromText('POINT(100.5234 13.7345)'), 'North', 'Distribution-1', '{"type": "pressure", "range": "0-5m"}'),
-- Weather stations
('WS001', 'weather', ST_GeogFromText('POINT(100.5345 13.7256)'), 'North', 'Station-1', '{"model": "Davis Vantage Pro2"}'),
-- Flow meters
('FL001', 'flow', ST_GeogFromText('POINT(100.5432 13.7298)'), 'North', 'Gate-1', '{"type": "electromagnetic", "diameter": "200mm"}'),
('FL002', 'flow', ST_GeogFromText('POINT(100.5321 13.7187)'), 'North', 'Gate-2', '{"type": "electromagnetic", "diameter": "150mm"}')
ON CONFLICT (sensor_id) DO NOTHING;

-- Generate sample data for the last 7 days
-- Moisture readings
INSERT INTO sensor.moisture_readings (time, sensor_id, moisture_percentage, temperature, conductivity)
SELECT 
  time,
  sensor_id,
  20 + (random() * 60),  -- 20-80% moisture
  20 + (random() * 15),  -- 20-35°C temperature
  0.5 + (random() * 2.5) -- 0.5-3.0 dS/m conductivity
FROM 
  generate_series(NOW() - INTERVAL '7 days', NOW(), INTERVAL '1 hour') AS time,
  (SELECT sensor_id FROM sensor.sensors WHERE sensor_type = 'moisture') AS sensors(sensor_id);

-- Water level readings
INSERT INTO sensor.water_level_readings (time, sensor_id, water_level_m, flow_rate_m3s, temperature)
SELECT 
  time,
  sensor_id,
  2 + (random() * 3),     -- 2-5m water level
  0.5 + (random() * 1.5), -- 0.5-2 m³/s flow rate
  25 + (random() * 5)     -- 25-30°C temperature
FROM 
  generate_series(NOW() - INTERVAL '7 days', NOW(), INTERVAL '15 minutes') AS time,
  (SELECT sensor_id FROM sensor.sensors WHERE sensor_type = 'water_level') AS sensors(sensor_id);

-- Weather readings
INSERT INTO sensor.weather_readings (time, sensor_id, temperature, humidity, pressure, wind_speed, rainfall_mm, solar_radiation)
SELECT 
  time,
  sensor_id,
  20 + (random() * 20),    -- 20-40°C temperature
  40 + (random() * 50),    -- 40-90% humidity
  1000 + (random() * 30),  -- 1000-1030 hPa pressure
  random() * 10,           -- 0-10 m/s wind speed
  CASE WHEN random() > 0.8 THEN random() * 20 ELSE 0 END, -- Occasional rainfall
  CASE 
    WHEN EXTRACT(hour FROM time) BETWEEN 6 AND 18 
    THEN 100 + (random() * 900)  -- 100-1000 W/m² during day
    ELSE 0 
  END -- Solar radiation
FROM 
  generate_series(NOW() - INTERVAL '7 days', NOW(), INTERVAL '30 minutes') AS time,
  (SELECT sensor_id FROM sensor.sensors WHERE sensor_type = 'weather') AS sensors(sensor_id);

-- Flow readings
INSERT INTO sensor.flow_readings (time, sensor_id, flow_rate_m3s, total_volume_m3, pressure_kpa)
SELECT 
  time,
  sensor_id,
  0.3 + (random() * 1.2),   -- 0.3-1.5 m³/s flow rate
  SUM(0.3 + (random() * 1.2)) OVER (PARTITION BY sensor_id ORDER BY time) * 900, -- Cumulative volume
  200 + (random() * 100)    -- 200-300 kPa pressure
FROM 
  generate_series(NOW() - INTERVAL '7 days', NOW(), INTERVAL '5 minutes') AS time,
  (SELECT sensor_id FROM sensor.sensors WHERE sensor_type = 'flow') AS sensors(sensor_id);

-- Create some sample alerts
INSERT INTO sensor.alerts (time, sensor_id, alert_type, severity, threshold_value, actual_value, message)
VALUES
(NOW() - INTERVAL '2 hours', 'MS001', 'low_moisture', 'warning', 30, 25, 'Moisture level below threshold'),
(NOW() - INTERVAL '1 hour', 'WL001', 'high_level', 'critical', 4.5, 4.8, 'Water level critically high'),
(NOW() - INTERVAL '30 minutes', 'FL001', 'no_flow', 'warning', 0.1, 0, 'No flow detected');

-- Refresh continuous aggregates with sample data
CALL refresh_continuous_aggregate('aggregates.readings_5min', NOW() - INTERVAL '7 days', NOW());
CALL refresh_continuous_aggregate('aggregates.readings_hourly', NOW() - INTERVAL '7 days', NOW());
CALL refresh_continuous_aggregate('aggregates.moisture_hourly', NOW() - INTERVAL '7 days', NOW());
CALL refresh_continuous_aggregate('aggregates.water_level_hourly', NOW() - INTERVAL '7 days', NOW());