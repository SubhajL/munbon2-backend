#!/bin/bash

# Setup scheduler schema on EC2 PostgreSQL
echo "Setting up scheduler schema on EC2 PostgreSQL..."

# EC2 PostgreSQL credentials
EC2_HOST="43.209.22.250"
EC2_PORT="5432"
EC2_USER="postgres"
EC2_PASSWORD='P@ssw0rd123!'
EC2_DB="munbon_dev"

# Export password for psql
export PGPASSWORD="${EC2_PASSWORD}"

# Test connection first
echo "Testing connection to EC2 PostgreSQL..."
psql -h ${EC2_HOST} -p ${EC2_PORT} -U ${EC2_USER} -d ${EC2_DB} -c "SELECT version();" || {
    echo "❌ Failed to connect to EC2 PostgreSQL"
    echo "Please check credentials and network connectivity"
    exit 1
}

echo "✅ Connection successful"

# Create schema
echo "Creating scheduler schema..."
psql -h ${EC2_HOST} -p ${EC2_PORT} -U ${EC2_USER} -d ${EC2_DB} <<EOF
-- Create scheduler schema
CREATE SCHEMA IF NOT EXISTS scheduler;

-- Set search path
SET search_path TO scheduler, public;

-- Create tables
CREATE TABLE IF NOT EXISTS scheduler.weekly_schedules (
    id SERIAL PRIMARY KEY,
    week VARCHAR(10) NOT NULL UNIQUE,
    status VARCHAR(20) DEFAULT 'draft',
    total_volume_m3 DECIMAL(10,2),
    optimization_score DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_by VARCHAR(100),
    approved_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scheduler.schedule_operations (
    id SERIAL PRIMARY KEY,
    schedule_id INTEGER REFERENCES scheduler.weekly_schedules(id),
    gate_id VARCHAR(50) NOT NULL,
    action VARCHAR(20) NOT NULL,
    target_opening_m DECIMAL(4,2),
    scheduled_time TIMESTAMP NOT NULL,
    team_assigned VARCHAR(20),
    status VARCHAR(20) DEFAULT 'pending',
    actual_opening_m DECIMAL(4,2),
    completed_at TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS scheduler.weekly_demands (
    id SERIAL PRIMARY KEY,
    week VARCHAR(10) NOT NULL,
    section_demands JSONB,
    total_demand_m3 DECIMAL(10,2),
    status VARCHAR(20) DEFAULT 'submitted',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scheduler.field_teams (
    id SERIAL PRIMARY KEY,
    team_code VARCHAR(20) UNIQUE NOT NULL,
    team_name VARCHAR(100),
    leader_name VARCHAR(100),
    phone_number VARCHAR(20),
    current_lat DECIMAL(10,6),
    current_lon DECIMAL(10,6),
    is_active BOOLEAN DEFAULT true,
    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scheduler.team_assignments (
    id SERIAL PRIMARY KEY,
    team_code VARCHAR(20) REFERENCES scheduler.field_teams(team_code),
    operation_id INTEGER REFERENCES scheduler.schedule_operations(id),
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'assigned',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    actual_lat DECIMAL(10,6),
    actual_lon DECIMAL(10,6)
);

CREATE TABLE IF NOT EXISTS scheduler.weather_adjustments (
    id SERIAL PRIMARY KEY,
    week VARCHAR(10),
    adjustment_factor DECIMAL(3,2),
    rainfall_mm DECIMAL(6,2),
    temperature_avg DECIMAL(4,1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scheduler.optimization_runs (
    id SERIAL PRIMARY KEY,
    week VARCHAR(10),
    algorithm VARCHAR(50),
    objective_value DECIMAL(10,2),
    runtime_seconds DECIMAL(6,2),
    parameters JSONB,
    results JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_schedules_week ON scheduler.weekly_schedules(week);
CREATE INDEX IF NOT EXISTS idx_operations_schedule ON scheduler.schedule_operations(schedule_id);
CREATE INDEX IF NOT EXISTS idx_operations_time ON scheduler.schedule_operations(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_teams_active ON scheduler.field_teams(is_active);
CREATE INDEX IF NOT EXISTS idx_assignments_status ON scheduler.team_assignments(status);

-- Insert default teams
INSERT INTO scheduler.field_teams (team_code, team_name, leader_name, phone_number, is_active)
VALUES 
    ('Team_A', 'Field Team Alpha', 'Somchai Jaidee', '081-234-5678', true),
    ('Team_B', 'Field Team Bravo', 'Prasert Suksri', '081-345-6789', true)
ON CONFLICT (team_code) DO NOTHING;

-- Create update trigger
CREATE OR REPLACE FUNCTION scheduler.update_modified_column()
RETURNS TRIGGER AS \$\$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
\$\$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_weekly_schedules_modtime ON scheduler.weekly_schedules;
CREATE TRIGGER update_weekly_schedules_modtime 
    BEFORE UPDATE ON scheduler.weekly_schedules 
    FOR EACH ROW EXECUTE FUNCTION scheduler.update_modified_column();

-- Verify setup
SELECT 
    'Tables created' as status,
    COUNT(*) as table_count 
FROM information_schema.tables 
WHERE table_schema = 'scheduler';

SELECT 
    'Teams inserted' as status,
    COUNT(*) as team_count 
FROM scheduler.field_teams;
EOF

echo "✅ Schema setup complete!"

# Unset password
unset PGPASSWORD