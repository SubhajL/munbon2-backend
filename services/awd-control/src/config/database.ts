import { Pool } from 'pg';
import { logger } from '../utils/logger';

let postgresPool: Pool;
let timescalePool: Pool;

// Schema configuration
const POSTGRES_SCHEMA = process.env.POSTGRES_SCHEMA || 'awd';
const TIMESCALE_SCHEMA = process.env.TIMESCALE_SCHEMA || 'public';

export const connectDatabases = async (): Promise<void> => {
  try {
    // PostgreSQL connection for configuration data
    postgresPool = new Pool({
      host: process.env.POSTGRES_HOST || 'localhost',
      port: parseInt(process.env.POSTGRES_PORT || '5432'),
      database: process.env.POSTGRES_DB || 'munbon_dev',
      user: process.env.POSTGRES_USER || 'postgres',
      password: process.env.POSTGRES_PASSWORD || 'postgres',
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    });

    // Set search path for PostgreSQL
    await postgresPool.query(`SET search_path TO ${POSTGRES_SCHEMA}, public`);
    
    // Test PostgreSQL connection
    await postgresPool.query('SELECT NOW()');
    logger.info(`PostgreSQL connected successfully with schema: ${POSTGRES_SCHEMA}`);

    // TimescaleDB connection for time-series data
    timescalePool = new Pool({
      host: process.env.TIMESCALE_HOST || 'localhost',
      port: parseInt(process.env.TIMESCALE_PORT || '5432'),
      database: process.env.TIMESCALE_DB || 'sensor_data',
      user: process.env.TIMESCALE_USER || 'postgres',
      password: process.env.TIMESCALE_PASSWORD || 'postgres',
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    });

    // Set search path for TimescaleDB
    await timescalePool.query(`SET search_path TO ${TIMESCALE_SCHEMA}, public`);
    
    // Test TimescaleDB connection
    await timescalePool.query('SELECT NOW()');
    logger.info(`TimescaleDB connected successfully with schema: ${TIMESCALE_SCHEMA}`);

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
    // Create schema if not exists
    await postgresPool.query(`CREATE SCHEMA IF NOT EXISTS ${POSTGRES_SCHEMA}`);
    
    // Create tables in PostgreSQL with schema prefix
    await postgresPool.query(`
      -- Set search path for this session
      SET search_path TO ${POSTGRES_SCHEMA}, public;
      
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
    `);

    // Create AWD-specific tables in TimescaleDB
    await timescalePool.query(`
      -- Set search path for this session
      SET search_path TO ${TIMESCALE_SCHEMA}, public;
      
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
    `);

    logger.info('Database schema initialized successfully');
  } catch (error) {
    logger.error(error, 'Failed to initialize database schema');
    throw error;
  }
};

// Helper function to execute queries with schema context
export const executeQuery = async (
  pool: Pool,
  query: string,
  params?: any[],
  schema?: string
): Promise<any> => {
  const client = await pool.connect();
  try {
    // Set schema search path if provided
    if (schema) {
      await client.query(`SET search_path TO ${schema}, public`);
    }
    
    const result = await client.query(query, params);
    return result;
  } finally {
    client.release();
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