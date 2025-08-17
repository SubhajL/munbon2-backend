#!/bin/bash

# Setup schemas on EC2 PostgreSQL for consolidated database
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# EC2 Database Configuration
EC2_HOST="${EC2_HOST:-43.208.201.191}"
EC2_PORT="5432"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

echo -e "${BLUE}=== Setting up EC2 PostgreSQL Schemas ===${NC}"

# Create AWD schema in munbon_dev
echo -e "${YELLOW}Creating AWD schema in munbon_dev...${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev << EOF
-- Create AWD schema for AWD Control Service
CREATE SCHEMA IF NOT EXISTS awd;
GRANT ALL ON SCHEMA awd TO postgres;
GRANT USAGE ON SCHEMA awd TO postgres;
GRANT CREATE ON SCHEMA awd TO postgres;

-- Ensure all other schemas exist and have proper permissions
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS gis;
CREATE SCHEMA IF NOT EXISTS ros;
CREATE SCHEMA IF NOT EXISTS config;

GRANT ALL ON SCHEMA auth TO postgres;
GRANT ALL ON SCHEMA gis TO postgres;
GRANT ALL ON SCHEMA ros TO postgres;
GRANT ALL ON SCHEMA config TO postgres;

-- List all schemas
\dn
EOF

# Verify TimescaleDB in sensor_data
echo -e "\n${YELLOW}Verifying TimescaleDB in sensor_data...${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data << EOF
-- Ensure TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- List extensions
\dx

-- List schemas
\dn
EOF

# Create tables for AWD service if needed
echo -e "\n${YELLOW}Creating AWD tables if needed...${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev << EOF
SET search_path TO awd;

-- AWD Configuration Tables
CREATE TABLE IF NOT EXISTS awd_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    field_name VARCHAR(255) NOT NULL,
    field_code VARCHAR(100) UNIQUE NOT NULL,
    area_hectares DECIMAL(10,2),
    location GEOMETRY(Point, 4326),
    zone_id UUID,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS awd_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    field_id UUID REFERENCES awd_fields(id),
    water_level_min DECIMAL(5,2),
    water_level_max DECIMAL(5,2),
    irrigation_threshold DECIMAL(5,2),
    drainage_threshold DECIMAL(5,2),
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS irrigation_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    field_id UUID REFERENCES awd_fields(id),
    scheduled_date DATE,
    scheduled_time TIME,
    duration_minutes INTEGER,
    water_amount_mm DECIMAL(5,2),
    status VARCHAR(50) DEFAULT 'scheduled',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_awd_fields_location ON awd_fields USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_awd_fields_zone ON awd_fields(zone_id);
CREATE INDEX IF NOT EXISTS idx_awd_config_field ON awd_configurations(field_id);
CREATE INDEX IF NOT EXISTS idx_irrigation_field_date ON irrigation_schedules(field_id, scheduled_date);

-- List tables in AWD schema
\dt awd.*
EOF

# Show final summary
echo -e "\n${GREEN}=== Schema Setup Complete ===${NC}"
echo -e "${BLUE}Database schemas on EC2:${NC}"

PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev -t -c "
SELECT 'munbon_dev schemas:' as info
UNION ALL
SELECT '  - ' || nspname 
FROM pg_namespace 
WHERE nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
ORDER BY 1;"

PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -t -c "
SELECT 'sensor_data schemas:' as info
UNION ALL
SELECT '  - ' || nspname 
FROM pg_namespace 
WHERE nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', '_timescaledb_catalog', '_timescaledb_internal', '_timescaledb_config', '_timescaledb_cache')
ORDER BY 1;"

echo -e "\n${GREEN}Ready for service deployment!${NC}"