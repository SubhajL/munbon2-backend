-- Connect to munbon_dev and create missing schemas
\c munbon_dev

-- Create AWD schema for AWD Control Service
CREATE SCHEMA IF NOT EXISTS awd;
GRANT ALL ON SCHEMA awd TO postgres;

-- Ensure all schemas exist
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS gis;
CREATE SCHEMA IF NOT EXISTS ros;
CREATE SCHEMA IF NOT EXISTS config;

-- Grant permissions
GRANT ALL ON SCHEMA auth TO postgres;
GRANT ALL ON SCHEMA gis TO postgres;
GRANT ALL ON SCHEMA ros TO postgres;
GRANT ALL ON SCHEMA config TO postgres;

-- List all schemas
\dn

-- Connect to sensor_data and ensure TimescaleDB
\c sensor_data

-- Ensure TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- List extensions
\dx
