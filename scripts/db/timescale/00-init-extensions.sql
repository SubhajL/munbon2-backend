-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create sensor_data database if not exists
SELECT 'CREATE DATABASE sensor_data'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sensor_data')\gexec

\c sensor_data;

-- Enable extensions in sensor_data database
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;