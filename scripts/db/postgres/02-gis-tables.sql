-- GIS Schema Tables for Munbon Irrigation Project

-- Irrigation zones with spatial boundaries
CREATE TABLE IF NOT EXISTS gis.irrigation_zones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    zone_code VARCHAR(50) UNIQUE NOT NULL,
    zone_name VARCHAR(255) NOT NULL,
    zone_type VARCHAR(50) NOT NULL CHECK (zone_type IN ('primary', 'secondary', 'tertiary')),
    area_hectares DECIMAL(10,2),
    boundary GEOMETRY(POLYGON, 4326) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create spatial index
CREATE INDEX idx_irrigation_zones_boundary ON gis.irrigation_zones USING GIST (boundary);

-- Canal network
CREATE TABLE IF NOT EXISTS gis.canal_network (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canal_code VARCHAR(50) UNIQUE NOT NULL,
    canal_name VARCHAR(255) NOT NULL,
    canal_type VARCHAR(50) NOT NULL CHECK (canal_type IN ('main', 'lateral', 'sub-lateral', 'field')),
    length_meters DECIMAL(10,2),
    width_meters DECIMAL(10,2),
    depth_meters DECIMAL(10,2),
    capacity_cms DECIMAL(10,3), -- cubic meters per second
    geometry GEOMETRY(LINESTRING, 4326) NOT NULL,
    upstream_node_id UUID,
    downstream_node_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_canal_network_geometry ON gis.canal_network USING GIST (geometry);

-- Water control structures (gates, weirs, etc.)
CREATE TABLE IF NOT EXISTS gis.control_structures (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    structure_code VARCHAR(50) UNIQUE NOT NULL,
    structure_name VARCHAR(255) NOT NULL,
    structure_type VARCHAR(50) NOT NULL CHECK (structure_type IN ('gate', 'weir', 'pump', 'reservoir', 'check')),
    canal_id UUID REFERENCES gis.canal_network(id),
    location GEOMETRY(POINT, 4326) NOT NULL,
    elevation_msl DECIMAL(10,3), -- meters above sea level
    max_discharge_cms DECIMAL(10,3),
    scada_tag VARCHAR(100),
    operational_status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_control_structures_location ON gis.control_structures USING GIST (location);
CREATE INDEX idx_control_structures_scada_tag ON gis.control_structures(scada_tag) WHERE scada_tag IS NOT NULL;

-- Agricultural plots
CREATE TABLE IF NOT EXISTS gis.agricultural_plots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plot_code VARCHAR(50) UNIQUE NOT NULL,
    farmer_id VARCHAR(50),
    zone_id UUID REFERENCES gis.irrigation_zones(id),
    area_hectares DECIMAL(10,2),
    boundary GEOMETRY(POLYGON, 4326) NOT NULL,
    current_crop_type VARCHAR(100),
    planting_date DATE,
    expected_harvest_date DATE,
    soil_type VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agricultural_plots_boundary ON gis.agricultural_plots USING GIST (boundary);
CREATE INDEX idx_agricultural_plots_zone_id ON gis.agricultural_plots(zone_id);

-- Sensor locations (can be mobile)
CREATE TABLE IF NOT EXISTS gis.sensor_locations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sensor_id VARCHAR(100) NOT NULL,
    location GEOMETRY(POINT, 4326) NOT NULL,
    elevation_msl DECIMAL(10,3),
    installation_date DATE,
    last_update TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_mobile BOOLEAN DEFAULT FALSE,
    zone_id UUID REFERENCES gis.irrigation_zones(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sensor_locations_location ON gis.sensor_locations USING GIST (location);
CREATE INDEX idx_sensor_locations_sensor_id ON gis.sensor_locations(sensor_id);

-- Weather stations
CREATE TABLE IF NOT EXISTS gis.weather_stations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    station_code VARCHAR(50) UNIQUE NOT NULL,
    station_name VARCHAR(255) NOT NULL,
    location GEOMETRY(POINT, 4326) NOT NULL,
    elevation_msl DECIMAL(10,3),
    station_type VARCHAR(50),
    data_source VARCHAR(100), -- 'TMD', 'Local', etc.
    external_id VARCHAR(100), -- ID in external system
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_weather_stations_location ON gis.weather_stations USING GIST (location);

-- Create triggers for updated_at columns
CREATE TRIGGER update_irrigation_zones_modtime 
    BEFORE UPDATE ON gis.irrigation_zones 
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_canal_network_modtime 
    BEFORE UPDATE ON gis.canal_network 
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_control_structures_modtime 
    BEFORE UPDATE ON gis.control_structures 
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_agricultural_plots_modtime 
    BEFORE UPDATE ON gis.agricultural_plots 
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_weather_stations_modtime 
    BEFORE UPDATE ON gis.weather_stations 
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Grant permissions
GRANT SELECT ON ALL TABLES IN SCHEMA gis TO munbon_reader;
GRANT ALL ON ALL TABLES IN SCHEMA gis TO munbon_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA gis TO munbon_app;