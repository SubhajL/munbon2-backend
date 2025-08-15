-- Initialize database for Gravity Optimizer Service

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Create schema
CREATE SCHEMA IF NOT EXISTS gravity;

-- Hydraulic nodes table
CREATE TABLE IF NOT EXISTS gravity.hydraulic_nodes (
    node_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    elevation DECIMAL(10,2) NOT NULL,
    location GEOMETRY(Point, 4326) NOT NULL,
    water_demand DECIMAL(10,2) DEFAULT 0,
    priority INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create spatial index
CREATE INDEX idx_nodes_location ON gravity.hydraulic_nodes USING GIST(location);

-- Channels table
CREATE TABLE IF NOT EXISTS gravity.channels (
    channel_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    channel_type VARCHAR(20) NOT NULL CHECK (channel_type IN ('main', 'lateral', 'sublateral', 'field')),
    upstream_gate_id VARCHAR(50),
    total_length DECIMAL(10,2) NOT NULL,
    avg_bed_slope DECIMAL(10,6) NOT NULL,
    capacity DECIMAL(10,2) NOT NULL,
    geometry GEOMETRY(LineString, 4326) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create spatial index
CREATE INDEX idx_channels_geometry ON gravity.channels USING GIST(geometry);

-- Channel sections table
CREATE TABLE IF NOT EXISTS gravity.channel_sections (
    section_id VARCHAR(50) PRIMARY KEY,
    channel_id VARCHAR(50) REFERENCES gravity.channels(channel_id),
    start_elevation DECIMAL(10,2) NOT NULL,
    end_elevation DECIMAL(10,2) NOT NULL,
    length DECIMAL(10,2) NOT NULL,
    bed_width DECIMAL(10,2) NOT NULL,
    side_slope DECIMAL(5,2) DEFAULT 1.5,
    manning_n DECIMAL(5,3) DEFAULT 0.025,
    max_depth DECIMAL(10,2) NOT NULL,
    section_order INTEGER NOT NULL,
    geometry GEOMETRY(LineString, 4326) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Gates table
CREATE TABLE IF NOT EXISTS gravity.gates (
    gate_id VARCHAR(50) PRIMARY KEY,
    gate_type VARCHAR(20) NOT NULL CHECK (gate_type IN ('automated', 'manual')),
    location GEOMETRY(Point, 4326) NOT NULL,
    elevation DECIMAL(10,2) NOT NULL,
    max_opening DECIMAL(5,2) NOT NULL,
    current_opening DECIMAL(5,2) DEFAULT 0,
    upstream_channel_id VARCHAR(50) REFERENCES gravity.channels(channel_id),
    downstream_channel_id VARCHAR(50) REFERENCES gravity.channels(channel_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create spatial index
CREATE INDEX idx_gates_location ON gravity.gates USING GIST(location);

-- Zone boundaries table
CREATE TABLE IF NOT EXISTS gravity.zones (
    zone_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    min_elevation DECIMAL(10,2) NOT NULL,
    max_elevation DECIMAL(10,2) NOT NULL,
    area_hectares DECIMAL(10,2),
    boundary GEOMETRY(Polygon, 4326) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create spatial index
CREATE INDEX idx_zones_boundary ON gravity.zones USING GIST(boundary);

-- Optimization results table
CREATE TABLE IF NOT EXISTS gravity.optimization_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id VARCHAR(100) UNIQUE NOT NULL,
    objective VARCHAR(50) NOT NULL,
    source_water_level DECIMAL(10,2),
    total_delivery_time DECIMAL(10,2),
    overall_efficiency DECIMAL(5,4),
    result_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_optimization_created ON gravity.optimization_results(created_at DESC);

-- Gate settings history table
CREATE TABLE IF NOT EXISTS gravity.gate_settings_history (
    id SERIAL PRIMARY KEY,
    gate_id VARCHAR(50) REFERENCES gravity.gates(gate_id),
    opening_ratio DECIMAL(5,4) NOT NULL,
    flow_rate DECIMAL(10,2),
    upstream_head DECIMAL(10,2),
    downstream_head DECIMAL(10,2),
    optimization_id UUID REFERENCES gravity.optimization_results(result_id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_gate_history_timestamp ON gravity.gate_settings_history(timestamp DESC);

-- Energy recovery sites table
CREATE TABLE IF NOT EXISTS gravity.energy_recovery_sites (
    site_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id VARCHAR(100) NOT NULL,
    channel_id VARCHAR(50) REFERENCES gravity.channels(channel_id),
    location GEOMETRY(Point, 4326) NOT NULL,
    available_head DECIMAL(10,2) NOT NULL,
    avg_flow_rate DECIMAL(10,2) NOT NULL,
    potential_power_kw DECIMAL(10,2) NOT NULL,
    annual_energy_mwh DECIMAL(10,2),
    feasibility VARCHAR(50),
    estimated_cost DECIMAL(15,2),
    payback_years DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample data for testing
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority)
VALUES 
    ('source', 'Main Source', 221.0, ST_SetSRID(ST_MakePoint(101.0, 14.0), 4326), 0, 1),
    ('zone_1_node', 'Zone 1 Distribution', 219.0, ST_SetSRID(ST_MakePoint(101.01, 14.01), 4326), 20.0, 1),
    ('zone_2_node', 'Zone 2 Distribution', 218.0, ST_SetSRID(ST_MakePoint(101.02, 14.02), 4326), 20.0, 1),
    ('zone_3_node', 'Zone 3 Distribution', 217.0, ST_SetSRID(ST_MakePoint(101.03, 14.03), 4326), 20.0, 2),
    ('zone_4_node', 'Zone 4 Distribution', 216.0, ST_SetSRID(ST_MakePoint(101.04, 14.04), 4326), 20.0, 2),
    ('zone_5_node', 'Zone 5 Distribution', 215.0, ST_SetSRID(ST_MakePoint(101.05, 14.05), 4326), 20.0, 3),
    ('zone_6_node', 'Zone 6 Distribution', 215.0, ST_SetSRID(ST_MakePoint(101.06, 14.06), 4326), 20.0, 3)
ON CONFLICT DO NOTHING;

-- Insert sample zones
INSERT INTO gravity.zones (zone_id, name, min_elevation, max_elevation, area_hectares, boundary)
VALUES 
    ('zone_1', 'Zone 1', 218.0, 219.0, 500, ST_SetSRID(ST_MakePolygon(ST_MakeLine(ARRAY[
        ST_MakePoint(101.005, 14.005), ST_MakePoint(101.015, 14.005),
        ST_MakePoint(101.015, 14.015), ST_MakePoint(101.005, 14.015),
        ST_MakePoint(101.005, 14.005)])), 4326)),
    ('zone_2', 'Zone 2', 217.0, 218.0, 450, ST_SetSRID(ST_MakePolygon(ST_MakeLine(ARRAY[
        ST_MakePoint(101.015, 14.015), ST_MakePoint(101.025, 14.015),
        ST_MakePoint(101.025, 14.025), ST_MakePoint(101.015, 14.025),
        ST_MakePoint(101.015, 14.015)])), 4326))
ON CONFLICT DO NOTHING;

-- Create function to update timestamps
CREATE OR REPLACE FUNCTION gravity.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_nodes_updated_at BEFORE UPDATE ON gravity.hydraulic_nodes
    FOR EACH ROW EXECUTE FUNCTION gravity.update_updated_at_column();

CREATE TRIGGER update_channels_updated_at BEFORE UPDATE ON gravity.channels
    FOR EACH ROW EXECUTE FUNCTION gravity.update_updated_at_column();

CREATE TRIGGER update_gates_updated_at BEFORE UPDATE ON gravity.gates
    FOR EACH ROW EXECUTE FUNCTION gravity.update_updated_at_column();

CREATE TRIGGER update_energy_sites_updated_at BEFORE UPDATE ON gravity.energy_recovery_sites
    FOR EACH ROW EXECUTE FUNCTION gravity.update_updated_at_column();

-- Grant permissions
GRANT ALL ON SCHEMA gravity TO postgres;
GRANT ALL ON ALL TABLES IN SCHEMA gravity TO postgres;
GRANT ALL ON ALL SEQUENCES IN SCHEMA gravity TO postgres;