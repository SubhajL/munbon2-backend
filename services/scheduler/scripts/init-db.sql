-- Scheduler Service Database Schema
-- Creates tables for weekly scheduling and field operations

-- Create scheduler schema
CREATE SCHEMA IF NOT EXISTS scheduler;

-- Weekly schedules table
CREATE TABLE IF NOT EXISTS scheduler.weekly_schedules (
    id SERIAL PRIMARY KEY,
    week VARCHAR(8) NOT NULL UNIQUE, -- Format: YYYY-Wnn
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP WITH TIME ZONE,
    approved_by VARCHAR(100),
    total_volume_m3 DECIMAL(10, 2),
    total_operations INTEGER DEFAULT 0,
    optimization_score DECIMAL(5, 2),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Schedule operations (individual gate adjustments)
CREATE TABLE IF NOT EXISTS scheduler.schedule_operations (
    id SERIAL PRIMARY KEY,
    schedule_id INTEGER REFERENCES scheduler.weekly_schedules(id) ON DELETE CASCADE,
    gate_id VARCHAR(50) NOT NULL,
    day_of_week VARCHAR(10) NOT NULL,
    scheduled_time TIMESTAMP WITH TIME ZONE NOT NULL,
    team_assigned VARCHAR(50),
    action VARCHAR(20) NOT NULL, -- open, close, adjust
    current_opening_m DECIMAL(5, 2),
    target_opening_m DECIMAL(5, 2) NOT NULL,
    priority INTEGER DEFAULT 5,
    estimated_duration_minutes INTEGER DEFAULT 30,
    location_lat DECIMAL(10, 6),
    location_lon DECIMAL(10, 6),
    physical_markers TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    completed_at TIMESTAMP WITH TIME ZONE,
    actual_opening_m DECIMAL(5, 2),
    notes TEXT,
    photo_urls JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Water demands aggregated by week
CREATE TABLE IF NOT EXISTS scheduler.weekly_demands (
    id SERIAL PRIMARY KEY,
    week VARCHAR(8) NOT NULL,
    section_id VARCHAR(50) NOT NULL,
    zone INTEGER NOT NULL,
    demand_m3 DECIMAL(10, 2) NOT NULL,
    crop_type VARCHAR(50),
    growth_stage VARCHAR(50),
    priority INTEGER DEFAULT 5,
    delivery_window_start TIMESTAMP WITH TIME ZONE,
    delivery_window_end TIMESTAMP WITH TIME ZONE,
    delivery_point VARCHAR(100),
    status VARCHAR(20) DEFAULT 'pending',
    allocated_m3 DECIMAL(10, 2) DEFAULT 0,
    deficit_m3 DECIMAL(10, 2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(week, section_id)
);

-- Field teams
CREATE TABLE IF NOT EXISTS scheduler.field_teams (
    id SERIAL PRIMARY KEY,
    team_code VARCHAR(50) UNIQUE NOT NULL,
    team_name VARCHAR(100) NOT NULL,
    leader_name VARCHAR(100),
    leader_phone VARCHAR(20),
    members INTEGER DEFAULT 2,
    available_days VARCHAR(50) DEFAULT 'Tuesday,Thursday',
    max_gates_per_day INTEGER DEFAULT 20,
    current_location_lat DECIMAL(10, 6),
    current_location_lon DECIMAL(10, 6),
    last_location_update TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Team assignments history
CREATE TABLE IF NOT EXISTS scheduler.team_assignments (
    id SERIAL PRIMARY KEY,
    team_id INTEGER REFERENCES scheduler.field_teams(id),
    operation_id INTEGER REFERENCES scheduler.schedule_operations(id),
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    travel_distance_km DECIMAL(6, 2),
    travel_time_minutes INTEGER,
    sequence_order INTEGER,
    status VARCHAR(20) DEFAULT 'assigned'
);

-- Weather adjustments log
CREATE TABLE IF NOT EXISTS scheduler.weather_adjustments (
    id SERIAL PRIMARY KEY,
    week VARCHAR(8) NOT NULL,
    adjustment_type VARCHAR(50),
    factor DECIMAL(5, 3) DEFAULT 1.0,
    rainfall_forecast_mm DECIMAL(6, 2),
    temperature_forecast_c DECIMAL(4, 1),
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Optimization runs history
CREATE TABLE IF NOT EXISTS scheduler.optimization_runs (
    id SERIAL PRIMARY KEY,
    schedule_id INTEGER REFERENCES scheduler.weekly_schedules(id),
    run_type VARCHAR(50),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    initial_score DECIMAL(5, 2),
    final_score DECIMAL(5, 2),
    iterations INTEGER,
    constraints_satisfied BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create indexes
CREATE INDEX idx_schedule_operations_gate_id ON scheduler.schedule_operations(gate_id);
CREATE INDEX idx_schedule_operations_schedule_id ON scheduler.schedule_operations(schedule_id);
CREATE INDEX idx_schedule_operations_status ON scheduler.schedule_operations(status);
CREATE INDEX idx_weekly_demands_week ON scheduler.weekly_demands(week);
CREATE INDEX idx_weekly_demands_section ON scheduler.weekly_demands(section_id);
CREATE INDEX idx_team_assignments_team ON scheduler.team_assignments(team_id);
CREATE INDEX idx_team_assignments_operation ON scheduler.team_assignments(operation_id);

-- Create update timestamp trigger
CREATE OR REPLACE FUNCTION scheduler.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to all tables with updated_at
CREATE TRIGGER update_weekly_schedules_updated_at BEFORE UPDATE ON scheduler.weekly_schedules
    FOR EACH ROW EXECUTE FUNCTION scheduler.update_updated_at_column();

CREATE TRIGGER update_schedule_operations_updated_at BEFORE UPDATE ON scheduler.schedule_operations
    FOR EACH ROW EXECUTE FUNCTION scheduler.update_updated_at_column();

CREATE TRIGGER update_weekly_demands_updated_at BEFORE UPDATE ON scheduler.weekly_demands
    FOR EACH ROW EXECUTE FUNCTION scheduler.update_updated_at_column();

CREATE TRIGGER update_field_teams_updated_at BEFORE UPDATE ON scheduler.field_teams
    FOR EACH ROW EXECUTE FUNCTION scheduler.update_updated_at_column();

-- Insert default field teams
INSERT INTO scheduler.field_teams (team_code, team_name, leader_name, leader_phone) VALUES
    ('Team_A', 'Field Team Alpha', 'Somchai Jaidee', '+66812345678'),
    ('Team_B', 'Field Team Bravo', 'Prasert Suksri', '+66823456789')
ON CONFLICT (team_code) DO NOTHING;

-- Grant permissions (adjust as needed)
GRANT ALL ON SCHEMA scheduler TO postgres;
GRANT ALL ON ALL TABLES IN SCHEMA scheduler TO postgres;
GRANT ALL ON ALL SEQUENCES IN SCHEMA scheduler TO postgres;