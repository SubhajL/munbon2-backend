-- Create sensors table
CREATE TABLE IF NOT EXISTS sensors (
    sensor_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100),
    type VARCHAR(50),
    location JSONB,
    zone VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create sensor_readings table with TimescaleDB hypertable
CREATE TABLE IF NOT EXISTS sensor_readings (
    time TIMESTAMPTZ NOT NULL,
    sensor_id VARCHAR(50) NOT NULL,
    data JSONB,
    quality INTEGER DEFAULT 100,
    FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
);

-- Create hypertable if TimescaleDB is available
SELECT create_hypertable('sensor_readings', 'time', if_not_exists => TRUE);

-- Insert sample sensors
INSERT INTO sensors (sensor_id, name, type, location, zone) VALUES
('WL001', 'Water Level Station 1', 'water_level', '{"lat": 14.3754, "lng": 102.8756}', 'Zone1'),
('WL002', 'Water Level Station 2', 'water_level', '{"lat": 14.3854, "lng": 102.8856}', 'Zone1'),
('MS001', 'Moisture Sensor 1', 'moisture', '{"lat": 14.3654, "lng": 102.8656}', 'Zone2'),
('MS002', 'Moisture Sensor 2', 'moisture', '{"lat": 14.3554, "lng": 102.8556}', 'Zone2'),
('WS001', 'Weather Station 1', 'weather', '{"lat": 14.3954, "lng": 102.8956}', 'Zone1')
ON CONFLICT (sensor_id) DO NOTHING;

-- Insert sample readings
INSERT INTO sensor_readings (time, sensor_id, data, quality) VALUES
(NOW() - INTERVAL '1 hour', 'WL001', '{"water_level_m": 2.5, "flow_rate_m3s": 1.2}', 95),
(NOW() - INTERVAL '30 minutes', 'WL001', '{"water_level_m": 2.6, "flow_rate_m3s": 1.3}', 98),
(NOW(), 'WL001', '{"water_level_m": 2.7, "flow_rate_m3s": 1.4}', 100),
(NOW() - INTERVAL '1 hour', 'WL002', '{"water_level_m": 3.1, "flow_rate_m3s": 2.1}', 96),
(NOW(), 'WL002', '{"water_level_m": 3.2, "flow_rate_m3s": 2.2}', 99),
(NOW() - INTERVAL '1 hour', 'MS001', '{"moisture_percentage": 65.5, "temperature_celsius": 28.3}', 97),
(NOW(), 'MS001', '{"moisture_percentage": 68.2, "temperature_celsius": 27.8}', 100),
(NOW() - INTERVAL '1 hour', 'MS002', '{"moisture_percentage": 71.3, "temperature_celsius": 28.1}', 95),
(NOW(), 'MS002', '{"moisture_percentage": 72.8, "temperature_celsius": 27.5}', 98),
(NOW() - INTERVAL '1 hour', 'WS001', '{"rainfall_mm": 0, "temperature_celsius": 29.5, "humidity_percentage": 75, "wind_speed_ms": 3.2, "wind_direction_degrees": 180, "pressure_hpa": 1010}', 99),
(NOW(), 'WS001', '{"rainfall_mm": 0.5, "temperature_celsius": 28.8, "humidity_percentage": 78, "wind_speed_ms": 2.8, "wind_direction_degrees": 175, "pressure_hpa": 1011}', 100);