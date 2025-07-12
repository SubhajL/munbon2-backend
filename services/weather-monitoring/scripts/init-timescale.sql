-- AOS Weather TimescaleDB Schema
-- For time-series weather data from Aeronautical Observation Stations

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Weather stations table (same structure as PostgreSQL)
CREATE TABLE IF NOT EXISTS weather_stations (
  station_id VARCHAR(50) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  type VARCHAR(50) NOT NULL CHECK (type IN ('SYNOPTIC', 'AUTOMATIC', 'AERONAUTICAL', 'AGRICULTURAL', 'RAIN_GAUGE')),
  location_lat DECIMAL(10, 8) NOT NULL,
  location_lng DECIMAL(11, 8) NOT NULL,
  altitude DECIMAL(10, 2),
  source VARCHAR(50) NOT NULL CHECK (source IN ('TMD', 'AOS', 'OPENWEATHER', 'CUSTOM', 'AGGREGATED')),
  is_active BOOLEAN DEFAULT true,
  metadata JSONB,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Weather readings table
CREATE TABLE IF NOT EXISTS weather_readings (
  time TIMESTAMP NOT NULL,
  station_id VARCHAR(50) NOT NULL,
  location_lat DECIMAL(10, 8),
  location_lng DECIMAL(11, 8),
  temperature DECIMAL(5, 2),
  humidity DECIMAL(5, 2),
  pressure DECIMAL(6, 2),
  wind_speed DECIMAL(5, 2),
  wind_direction DECIMAL(5, 2),
  rainfall DECIMAL(6, 2),
  solar_radiation DECIMAL(6, 2),
  uv_index DECIMAL(3, 1),
  visibility DECIMAL(5, 2),
  cloud_cover DECIMAL(5, 2),
  dew_point DECIMAL(5, 2),
  feels_like DECIMAL(5, 2),
  source VARCHAR(50) DEFAULT 'AOS',
  quality_score DECIMAL(3, 2),
  raw_metar TEXT,
  raw_synop TEXT
);

-- Convert to hypertable
SELECT create_hypertable('weather_readings', 'time', 
  chunk_time_interval => INTERVAL '1 day',
  if_not_exists => TRUE
);

-- Create indexes
CREATE INDEX idx_weather_readings_station_time ON weather_readings(station_id, time DESC);
CREATE INDEX idx_weather_readings_location ON weather_readings(location_lat, location_lng, time DESC);

-- Enable compression (optional - saves disk space)
ALTER TABLE weather_readings SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'station_id',
  timescaledb.compress_orderby = 'time DESC'
);

-- Add compression policy (compress chunks older than 7 days)
SELECT add_compression_policy('weather_readings', INTERVAL '7 days');

-- Create retention policy (keep 2 years of data)
SELECT add_retention_policy('weather_readings', INTERVAL '2 years');

-- Create continuous aggregates for hourly data
CREATE MATERIALIZED VIEW weather_hourly
WITH (timescaledb.continuous) AS
SELECT 
  time_bucket('1 hour', time) AS bucket,
  station_id,
  location_lat,
  location_lng,
  AVG(temperature) as avg_temperature,
  MIN(temperature) as min_temperature,
  MAX(temperature) as max_temperature,
  AVG(humidity) as avg_humidity,
  MIN(humidity) as min_humidity,
  MAX(humidity) as max_humidity,
  AVG(pressure) as avg_pressure,
  SUM(rainfall) as total_rainfall,
  AVG(wind_speed) as avg_wind_speed,
  MAX(wind_speed) as max_wind_speed,
  mode() WITHIN GROUP (ORDER BY wind_direction) as prevailing_wind_direction,
  AVG(solar_radiation) as avg_solar_radiation,
  COUNT(*) as reading_count,
  AVG(quality_score) as avg_quality_score
FROM weather_readings
GROUP BY bucket, station_id, location_lat, location_lng;

-- Create continuous aggregates for daily data
CREATE MATERIALIZED VIEW weather_daily
WITH (timescaledb.continuous) AS
SELECT 
  time_bucket('1 day', time) AS bucket,
  station_id,
  location_lat,
  location_lng,
  AVG(temperature) as avg_temperature,
  MIN(temperature) as min_temperature,
  MAX(temperature) as max_temperature,
  AVG(humidity) as avg_humidity,
  MIN(humidity) as min_humidity,
  MAX(humidity) as max_humidity,
  AVG(pressure) as avg_pressure,
  MIN(pressure) as min_pressure,
  MAX(pressure) as max_pressure,
  SUM(rainfall) as total_rainfall,
  AVG(wind_speed) as avg_wind_speed,
  MAX(wind_speed) as max_wind_speed,
  AVG(solar_radiation) as avg_solar_radiation,
  SUM(CASE WHEN solar_radiation > 0 THEN 1 ELSE 0 END) * 
    INTERVAL '1 hour' / COUNT(*) as sunshine_hours,
  COUNT(*) as reading_count,
  AVG(quality_score) as avg_quality_score
FROM weather_readings
GROUP BY bucket, station_id, location_lat, location_lng;

-- Refresh policies for continuous aggregates
SELECT add_continuous_aggregate_policy('weather_hourly',
  start_offset => INTERVAL '3 hours',
  end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '1 hour');

SELECT add_continuous_aggregate_policy('weather_daily',
  start_offset => INTERVAL '3 days',
  end_offset => INTERVAL '1 day',
  schedule_interval => INTERVAL '1 day');

-- Create function to get latest reading per station
CREATE OR REPLACE FUNCTION get_latest_readings()
RETURNS TABLE (
  station_id VARCHAR(50),
  time TIMESTAMP,
  temperature DECIMAL(5, 2),
  humidity DECIMAL(5, 2),
  pressure DECIMAL(6, 2),
  wind_speed DECIMAL(5, 2),
  wind_direction DECIMAL(5, 2),
  rainfall DECIMAL(6, 2)
) AS $$
BEGIN
  RETURN QUERY
  SELECT DISTINCT ON (wr.station_id)
    wr.station_id,
    wr.time,
    wr.temperature,
    wr.humidity,
    wr.pressure,
    wr.wind_speed,
    wr.wind_direction,
    wr.rainfall
  FROM weather_readings wr
  WHERE wr.time > NOW() - INTERVAL '2 hours'
  ORDER BY wr.station_id, wr.time DESC;
END;
$$ LANGUAGE plpgsql;

-- Insert AOS stations
INSERT INTO weather_stations (station_id, name, type, location_lat, location_lng, altitude, source, metadata) VALUES
('VTBD', 'Don Mueang International Airport', 'AERONAUTICAL', 13.9126, 100.6070, 20, 'AOS', '{"iata": "DMK", "icao": "VTBD", "runway": "21L/03R"}'),
('VTBS', 'Suvarnabhumi Airport', 'AERONAUTICAL', 13.6900, 100.7501, 5, 'AOS', '{"iata": "BKK", "icao": "VTBS", "runway": "19L/01R"}'),
('VTBU', 'U-Tapao International Airport', 'AERONAUTICAL', 12.6799, 101.0050, 17, 'AOS', '{"iata": "UTP", "icao": "VTBU", "runway": "18/36"}'),
('VTCC', 'Chiang Mai International Airport', 'AERONAUTICAL', 18.7669, 98.9626, 314, 'AOS', '{"iata": "CNX", "icao": "VTCC", "runway": "18/36"}'),
('VTUD', 'Udon Thani International Airport', 'AERONAUTICAL', 17.3864, 102.7883, 176, 'AOS', '{"iata": "UTH", "icao": "VTUD", "runway": "12/30"}'),
('VTUK', 'Khon Kaen Airport', 'AERONAUTICAL', 16.4666, 102.7838, 164, 'AOS', '{"iata": "KKC", "icao": "VTUK", "runway": "01/19"}'),
('VTUU', 'Ubon Ratchathani Airport', 'AERONAUTICAL', 15.2513, 104.8702, 127, 'AOS', '{"iata": "UBP", "icao": "VTUU", "runway": "05/23"}')
ON CONFLICT (station_id) DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO weather_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO weather_user;