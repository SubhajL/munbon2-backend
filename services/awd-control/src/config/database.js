"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.closeDatabases = exports.executeQuery = exports.getTimescalePool = exports.getPostgresPool = exports.connectDatabases = exports.buildTimescaleConfig = exports.buildPostgresConfig = void 0;
const pg_1 = require("pg");
const logger_1 = require("../utils/logger");
let postgresPool;
let timescalePool;
const POSTGRES_SCHEMA = process.env.POSTGRES_SCHEMA || 'awd';
const TIMESCALE_SCHEMA = process.env.TIMESCALE_SCHEMA || 'public';
const DEFAULT_PORT = 5432;
const DEFAULT_POOL_OPTIONS = Object.freeze({
    max: 20,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 2000,
});
const TRUE_VALUES = new Set(['true', '1', 'yes', 'require']);
const ensureConnectionString = (envKey) => {
    const raw = process.env[envKey];
    if (!raw || !raw.trim()) {
        throw new Error(`${envKey} must be set`);
    }
    return raw.trim();
};
const parseDatabaseUrl = (envKey) => {
    const raw = ensureConnectionString(envKey);
    let parsed;
    try {
        parsed = new URL(raw);
    }
    catch (error) {
        throw new Error(`Invalid ${envKey}: ${(error && error.message) || 'unknown error'}`);
    }
    const host = parsed.hostname;
    const port = parsed.port ? parseInt(parsed.port, 10) : DEFAULT_PORT;
    const database = parsed.pathname ? parsed.pathname.replace(/^\//, '') : '';
    if (!host || !database) {
        throw new Error(`${envKey} must include host and database name`);
    }
    return {
        host,
        port,
        database,
        user: parsed.username ? decodeURIComponent(parsed.username) : undefined,
        password: parsed.password ? decodeURIComponent(parsed.password) : undefined,
    };
};
const buildPostgresConfig = () => {
    const base = parseDatabaseUrl('POSTGRES_URL');
    return Object.assign(Object.assign({}, DEFAULT_POOL_OPTIONS), base);
};
exports.buildPostgresConfig = buildPostgresConfig;
const buildTimescaleConfig = () => {
    const base = parseDatabaseUrl('TIMESCALE_URL');
    const config = Object.assign(Object.assign({}, DEFAULT_POOL_OPTIONS), base);
    const sslFlag = process.env.TIMESCALE_SSL;
    if (sslFlag && TRUE_VALUES.has(sslFlag.toLowerCase())) {
        config.ssl = { rejectUnauthorized: false };
    }
    return config;
};
exports.buildTimescaleConfig = buildTimescaleConfig;
const logConnectionAttempt = (target, config) => {
    var _a;
    logger_1.logger.info({
        target,
        host: config.host,
        port: config.port,
        database: config.database,
        schema: target === 'postgres' ? POSTGRES_SCHEMA : TIMESCALE_SCHEMA,
        ssl: Boolean(config.ssl),
        user: (_a = config.user) !== null && _a !== void 0 ? _a : undefined,
        hasPassword: typeof config.password === 'string' && config.password.length > 0,
    }, `Connecting to ${target} database`);
};
const connectDatabases = async () => {
    try {
        const postgresConfig = buildPostgresConfig();
        logConnectionAttempt('postgres', postgresConfig);
        postgresPool = new pg_1.Pool(postgresConfig);
        await postgresPool.query(`SET search_path TO ${POSTGRES_SCHEMA}, public`);
        await postgresPool.query('SELECT NOW()');
        logger_1.logger.info(`PostgreSQL connected successfully with schema: ${POSTGRES_SCHEMA}`);
        const timescaleConfig = buildTimescaleConfig();
        logConnectionAttempt('timescale', timescaleConfig);
        timescalePool = new pg_1.Pool(timescaleConfig);
        await timescalePool.query(`SET search_path TO ${TIMESCALE_SCHEMA}, public`);
        await timescalePool.query('SELECT NOW()');
        logger_1.logger.info(`TimescaleDB connected successfully with schema: ${TIMESCALE_SCHEMA}`);
        await initializeSchema();
    }
    catch (error) {
        logger_1.logger.error(error, 'Failed to connect to databases');
        throw error;
    }
};
exports.connectDatabases = connectDatabases;
const getPostgresPool = () => {
    if (!postgresPool) {
        throw new Error('PostgreSQL pool not initialized');
    }
    return postgresPool;
};
exports.getPostgresPool = getPostgresPool;
const getTimescalePool = () => {
    if (!timescalePool) {
        throw new Error('TimescaleDB pool not initialized');
    }
    return timescalePool;
};
exports.getTimescalePool = getTimescalePool;
const initializeSchema = async () => {
    try {
        await postgresPool.query(`CREATE SCHEMA IF NOT EXISTS ${POSTGRES_SCHEMA}`);
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
        logger_1.logger.info('Database schema initialized successfully');
    }
    catch (error) {
        logger_1.logger.error(error, 'Failed to initialize database schema');
        throw error;
    }
};
const executeQuery = async (pool, query, params, schema) => {
    const client = await pool.connect();
    try {
        if (schema) {
            await client.query(`SET search_path TO ${schema}, public`);
        }
        const result = await client.query(query, params);
        return result;
    }
    finally {
        client.release();
    }
};
exports.executeQuery = executeQuery;
const closeDatabases = async () => {
    if (postgresPool) {
        await postgresPool.end();
        logger_1.logger.info('PostgreSQL connection closed');
    }
    if (timescalePool) {
        await timescalePool.end();
        logger_1.logger.info('TimescaleDB connection closed');
    }
};
exports.closeDatabases = closeDatabases;
//# sourceMappingURL=database.js.map
