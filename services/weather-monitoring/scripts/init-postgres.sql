-- Weather Integration Database Schema
-- For PostgreSQL with PostGIS

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Weather stations table
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
  id BIGSERIAL PRIMARY KEY,
  station_id VARCHAR(50) NOT NULL,
  timestamp TIMESTAMP NOT NULL,
  location_lat DECIMAL(10, 8),
  location_lng DECIMAL(11, 8),
  temperature DECIMAL(5, 2) CHECK (temperature >= -50 AND temperature <= 60),
  humidity DECIMAL(5, 2) CHECK (humidity >= 0 AND humidity <= 100),
  pressure DECIMAL(6, 2) CHECK (pressure >= 870 AND pressure <= 1080),
  wind_speed DECIMAL(5, 2) CHECK (wind_speed >= 0),
  wind_direction DECIMAL(5, 2) CHECK (wind_direction >= 0 AND wind_direction <= 360),
  rainfall DECIMAL(6, 2) CHECK (rainfall >= 0),
  solar_radiation DECIMAL(6, 2) CHECK (solar_radiation >= 0),
  uv_index DECIMAL(3, 1) CHECK (uv_index >= 0 AND uv_index <= 15),
  visibility DECIMAL(5, 2) CHECK (visibility >= 0),
  cloud_cover DECIMAL(5, 2) CHECK (cloud_cover >= 0 AND cloud_cover <= 100),
  dew_point DECIMAL(5, 2),
  feels_like DECIMAL(5, 2),
  source VARCHAR(50),
  quality_score DECIMAL(3, 2) CHECK (quality_score >= 0 AND quality_score <= 1),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Weather forecasts table
CREATE TABLE IF NOT EXISTS weather_forecasts (
  id BIGSERIAL PRIMARY KEY,
  station_id VARCHAR(50),
  location_lat DECIMAL(10, 8) NOT NULL,
  location_lng DECIMAL(11, 8) NOT NULL,
  timestamp TIMESTAMP NOT NULL,
  forecast_time TIMESTAMP NOT NULL,
  temp_min DECIMAL(5, 2),
  temp_max DECIMAL(5, 2),
  temp_avg DECIMAL(5, 2),
  humidity_min DECIMAL(5, 2) CHECK (humidity_min >= 0 AND humidity_min <= 100),
  humidity_max DECIMAL(5, 2) CHECK (humidity_max >= 0 AND humidity_max <= 100),
  humidity_avg DECIMAL(5, 2) CHECK (humidity_avg >= 0 AND humidity_avg <= 100),
  rainfall_amount DECIMAL(6, 2) CHECK (rainfall_amount >= 0),
  rainfall_probability DECIMAL(3, 2) CHECK (rainfall_probability >= 0 AND rainfall_probability <= 1),
  wind_speed DECIMAL(5, 2) CHECK (wind_speed >= 0),
  wind_direction DECIMAL(5, 2) CHECK (wind_direction >= 0 AND wind_direction <= 360),
  cloud_cover DECIMAL(5, 2) CHECK (cloud_cover >= 0 AND cloud_cover <= 100),
  uv_index DECIMAL(3, 1) CHECK (uv_index >= 0 AND uv_index <= 15),
  conditions VARCHAR(50),
  confidence DECIMAL(3, 2) CHECK (confidence >= 0 AND confidence <= 1),
  source VARCHAR(50),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX idx_weather_readings_timestamp ON weather_readings(timestamp DESC);
CREATE INDEX idx_weather_readings_station ON weather_readings(station_id, timestamp DESC);
CREATE INDEX idx_weather_readings_location ON weather_readings(location_lat, location_lng);
CREATE INDEX idx_weather_readings_created ON weather_readings(created_at DESC);

CREATE INDEX idx_weather_forecasts_time ON weather_forecasts(forecast_time);
CREATE INDEX idx_weather_forecasts_location ON weather_forecasts(location_lat, location_lng);
CREATE INDEX idx_weather_forecasts_created ON weather_forecasts(created_at DESC);

CREATE INDEX idx_weather_stations_location ON weather_stations(location_lat, location_lng);
CREATE INDEX idx_weather_stations_active ON weather_stations(is_active);

-- Create spatial indexes using PostGIS
CREATE INDEX idx_weather_readings_geom ON weather_readings USING GIST (ST_MakePoint(location_lng, location_lat));
CREATE INDEX idx_weather_forecasts_geom ON weather_forecasts USING GIST (ST_MakePoint(location_lng, location_lat));
CREATE INDEX idx_weather_stations_geom ON weather_stations USING GIST (ST_MakePoint(location_lng, location_lat));

-- Create update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_weather_stations_updated_at BEFORE UPDATE ON weather_stations
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert sample weather stations
INSERT INTO weather_stations (station_id, name, type, location_lat, location_lng, altitude, source, metadata) VALUES
('VTBD', 'Don Mueang International Airport', 'AERONAUTICAL', 13.9126, 100.6070, 20, 'AOS', '{"iata": "DMK", "icao": "VTBD"}'),
('TMD001', 'Bangkok Metropolis', 'SYNOPTIC', 13.7278, 100.5241, 3, 'TMD', '{"region": "Central", "province": "Bangkok"}'),
('TMD048', 'Nakhon Ratchasima', 'SYNOPTIC', 14.9799, 102.0977, 187, 'TMD', '{"region": "Northeast", "province": "Nakhon Ratchasima"}'),
('CUSTOM001', 'Munbon Project Station 1', 'AGRICULTURAL', 14.5896, 101.3764, 150, 'CUSTOM', '{"project": "Munbon", "zone": 1}'),
('CUSTOM002', 'Munbon Project Station 2', 'AGRICULTURAL', 14.6234, 101.4012, 155, 'CUSTOM', '{"project": "Munbon", "zone": 2}'),
('RAIN001', 'Munbon Rain Gauge 1', 'RAIN_GAUGE', 14.5723, 101.3891, 148, 'CUSTOM', '{"project": "Munbon", "type": "tipping_bucket"}')
ON CONFLICT (station_id) DO NOTHING;

-- Grant permissions (adjust as needed)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO weather_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO weather_user;