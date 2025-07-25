import { Pool } from 'pg';
import { logger } from '../utils/logger';

let postgresPool: Pool;
let timescalePool: Pool;

export const connectDatabases = async (): Promise<void> => {
  try {
    // PostgreSQL connection for configuration data
    postgresPool = new Pool({
      host: process.env.POSTGRES_HOST || 'localhost',
      port: parseInt(process.env.POSTGRES_PORT || '5432'),
      database: process.env.POSTGRES_DB || 'munbon_awd',
      user: process.env.POSTGRES_USER || 'postgres',
      password: process.env.POSTGRES_PASSWORD || 'postgres',
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    });

    // Test PostgreSQL connection
    await postgresPool.query('SELECT NOW()');
    logger.info('PostgreSQL connected successfully');

    // TimescaleDB connection for time-series data
    timescalePool = new Pool({
      host: process.env.TIMESCALE_HOST || 'localhost',
      port: parseInt(process.env.TIMESCALE_PORT || '5433'),
      database: process.env.TIMESCALE_DB || 'munbon_timeseries',
      user: process.env.TIMESCALE_USER || 'postgres',
      password: process.env.TIMESCALE_PASSWORD || 'postgres',
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    });

    // Test TimescaleDB connection
    await timescalePool.query('SELECT NOW()');
    logger.info('TimescaleDB connected successfully');

    // Initialize database schema
    await initializeSchema();
  } catch (error) {
    logger.error(error, 'Failed to connect to databases');
    throw error;
  }
};

export const getPostgresPool = (): Pool => {
  if (!postgresPool) {
    throw new Error('PostgreSQL pool not initialized');
  }
  return postgresPool;
};

export const getTimescalePool = (): Pool => {
  if (!timescalePool) {
    throw new Error('TimescaleDB pool not initialized');
  }
  return timescalePool;
};

const initializeSchema = async (): Promise<void> => {
  try {
    // Create tables in PostgreSQL
    await postgresPool.query(`
      CREATE TABLE IF NOT EXISTS awd_fields (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        field_code VARCHAR(50) UNIQUE NOT NULL,
        field_name VARCHAR(100) NOT NULL,
        zone_id INTEGER NOT NULL,
        area_hectares DECIMAL(10, 2) NOT NULL,
        soil_type VARCHAR(50),
        awd_enabled BOOLEAN DEFAULT true,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );

      CREATE TABLE IF NOT EXISTS awd_configurations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        field_id UUID REFERENCES awd_fields(id) UNIQUE,
        planting_method VARCHAR(20) DEFAULT 'direct-seeded',
        start_date TIMESTAMP NOT NULL,
        current_week INTEGER DEFAULT 0,
        current_phase VARCHAR(20) DEFAULT 'preparation',
        target_water_level INTEGER DEFAULT 0,
        drying_depth_cm INTEGER DEFAULT 15,
        safe_awd_depth_cm INTEGER DEFAULT 10,
        emergency_threshold_cm INTEGER DEFAULT 25,
        growth_stage VARCHAR(50) DEFAULT 'vegetative',
        irrigation_duration_minutes INTEGER DEFAULT 120,
        priority_level INTEGER DEFAULT 5,
        active BOOLEAN DEFAULT true,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );

      CREATE TABLE IF NOT EXISTS awd_sensors (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        sensor_id VARCHAR(50) UNIQUE NOT NULL,
        field_id UUID REFERENCES awd_fields(id),
        sensor_type VARCHAR(50) NOT NULL,
        mac_address VARCHAR(17),
        calibration_offset DECIMAL(5, 2) DEFAULT 0,
        last_reading_at TIMESTAMP,
        status VARCHAR(20) DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );

      CREATE TABLE IF NOT EXISTS irrigation_schedules (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        field_id UUID REFERENCES awd_fields(id),
        scheduled_start TIMESTAMP NOT NULL,
        scheduled_end TIMESTAMP NOT NULL,
        actual_start TIMESTAMP,
        actual_end TIMESTAMP,
        water_volume_liters DECIMAL(12, 2),
        status VARCHAR(20) DEFAULT 'pending',
        created_by VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );

      CREATE TABLE IF NOT EXISTS awd_field_cycles (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        field_id UUID REFERENCES awd_fields(id),
        cycle_type VARCHAR(20) NOT NULL, -- 'wetting' or 'drying'
        cycle_status VARCHAR(20) NOT NULL, -- 'active', 'completed'
        drying_start_date TIMESTAMP,
        drying_day_count INTEGER,
        target_water_level DECIMAL(6, 2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );

      -- Create GIS schema if not exists
      CREATE SCHEMA IF NOT EXISTS gis;
      
      -- Water level measurements from GIS/SHAPE data
      CREATE TABLE IF NOT EXISTS gis.water_level_measurements (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        field_id UUID NOT NULL,
        plot_id VARCHAR(50),
        water_height_cm DECIMAL(6, 2),
        crop_height_cm DECIMAL(6, 2),
        measurement_date TIMESTAMP,
        area DECIMAL(10, 2),
        geometry GEOMETRY(Polygon, 4326),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
      
      -- Field attributes from GIS/SHAPE data
      CREATE TABLE IF NOT EXISTS gis.field_attributes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        field_id UUID NOT NULL UNIQUE,
        planting_method VARCHAR(20),
        crop_type VARCHAR(50),
        variety VARCHAR(100),
        planting_date DATE,
        expected_harvest_date DATE,
        area_hectares DECIMAL(10, 2),
        geometry GEOMETRY(Polygon, 4326),
        metadata JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
    `);

    // Create hypertables in TimescaleDB
    await timescalePool.query(`
      CREATE TABLE IF NOT EXISTS awd_sensor_readings (
        time TIMESTAMPTZ NOT NULL,
        sensor_id VARCHAR(50) NOT NULL,
        field_id UUID NOT NULL,
        water_level_cm DECIMAL(6, 2),
        temperature_celsius DECIMAL(5, 2),
        humidity_percent DECIMAL(5, 2),
        battery_voltage DECIMAL(4, 2),
        signal_strength INTEGER,
        PRIMARY KEY (time, sensor_id)
      );

      SELECT create_hypertable('awd_sensor_readings', 'time', 
        if_not_exists => TRUE,
        chunk_time_interval => INTERVAL '1 day'
      );

      CREATE TABLE IF NOT EXISTS irrigation_events (
        time TIMESTAMPTZ NOT NULL,
        field_id UUID NOT NULL,
        event_type VARCHAR(50) NOT NULL,
        water_level_before_cm DECIMAL(6, 2),
        water_level_after_cm DECIMAL(6, 2),
        duration_minutes INTEGER,
        water_volume_liters DECIMAL(12, 2),
        gate_ids TEXT[],
        PRIMARY KEY (time, field_id)
      );

      SELECT create_hypertable('irrigation_events', 'time',
        if_not_exists => TRUE,
        chunk_time_interval => INTERVAL '7 days'
      );

      CREATE TABLE IF NOT EXISTS water_level_readings (
        time TIMESTAMPTZ NOT NULL,
        sensor_id VARCHAR(50) NOT NULL,
        field_id UUID NOT NULL,
        water_level_cm DECIMAL(6, 2),
        temperature_celsius DECIMAL(5, 2),
        humidity_percent DECIMAL(5, 2),
        battery_voltage DECIMAL(4, 2),
        signal_strength INTEGER,
        PRIMARY KEY (time, sensor_id)
      );

      SELECT create_hypertable('water_level_readings', 'time',
        if_not_exists => TRUE,
        chunk_time_interval => INTERVAL '1 day'
      );

      CREATE TABLE IF NOT EXISTS moisture_readings (
        time TIMESTAMPTZ NOT NULL,
        sensor_id VARCHAR(50) NOT NULL,
        field_id UUID NOT NULL,
        moisture_percent DECIMAL(5, 2),
        depth_cm DECIMAL(5, 2),
        temperature_celsius DECIMAL(5, 2),
        battery_voltage DECIMAL(4, 2),
        PRIMARY KEY (time, sensor_id)
      );

      SELECT create_hypertable('moisture_readings', 'time',
        if_not_exists => TRUE,
        chunk_time_interval => INTERVAL '1 day'
      );
    `);

    logger.info('Database schema initialized successfully');
  } catch (error) {
    logger.error(error, 'Failed to initialize database schema');
    throw error;
  }
};

export const closeDatabases = async (): Promise<void> => {
  if (postgresPool) {
    await postgresPool.end();
    logger.info('PostgreSQL connection closed');
  }
  if (timescalePool) {
    await timescalePool.end();
    logger.info('TimescaleDB connection closed');
  }
};