const { Pool } = require('pg');
const sql = require('mssql');
const logger = require('../utils/logger');

class DatabaseConfig {
  constructor() {
    this.timescalePool = null;
    this.mssqlPool = null;
  }

  async initializeTimescaleDB(config) {
    try {
      this.timescalePool = new Pool({
        host: config.host,
        port: config.port,
        database: config.database,
        user: config.user,
        password: config.password,
        max: 10,
        idleTimeoutMillis: 30000,
        connectionTimeoutMillis: 2000
      });

      // Test connection
      const client = await this.timescalePool.connect();
      await client.query('SELECT NOW()');
      client.release();

      logger.info('TimescaleDB connected successfully');

      // Create schemas if they don't exist
      await this.createSchemas();

      return this.timescalePool;
    } catch (error) {
      logger.error({ error }, 'Failed to connect to TimescaleDB');
      throw error;
    }
  }

  async initializeMSSQL(config) {
    try {
      const mssqlConfig = {
        server: config.host,
        port: config.port,
        database: config.database,
        user: config.user,
        password: config.password,
        options: {
          encrypt: false,
          trustServerCertificate: true,
          enableArithAbort: true
        },
        pool: {
          max: 10,
          min: 0,
          idleTimeoutMillis: 30000
        }
      };

      this.mssqlPool = await sql.connect(mssqlConfig);

      logger.info('MSSQL connected successfully');

      return this.mssqlPool;
    } catch (error) {
      logger.error({ error }, 'Failed to connect to MSSQL');
      throw error;
    }
  }

  async createSchemas() {
    const client = await this.timescalePool.connect();

    try {
      // Create schemas
      await client.query(`
        CREATE SCHEMA IF NOT EXISTS ros_gis_smartfarm;
        CREATE SCHEMA IF NOT EXISTS water_control_smartfarm;
      `);

      // Create tables for water planning
      await client.query(`
        CREATE TABLE IF NOT EXISTS ros_gis_smartfarm.daily_water_demands (
          plot_id VARCHAR(50) NOT NULL,
          date DATE NOT NULL,
          demand_m3 DECIMAL(10, 2) NOT NULL,
          crop_type VARCHAR(50),
          growth_stage VARCHAR(50),
          et0 DECIMAL(5, 2),
          kc DECIMAL(4, 2),
          effective_rainfall DECIMAL(10, 2),
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (plot_id, date)
        );

        CREATE TABLE IF NOT EXISTS ros_gis_smartfarm.daily_progress (
          plot_id VARCHAR(50) NOT NULL,
          date DATE NOT NULL,
          planned_demand DECIMAL(10, 2) NOT NULL,
          actual_usage DECIMAL(10, 2) NOT NULL,
          efficiency DECIMAL(4, 2),
          last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (plot_id, date)
        );
      `);

      // Create tables for water control
      await client.query(`
        CREATE TABLE IF NOT EXISTS water_control_smartfarm.control_modes (
          plot_id VARCHAR(50) PRIMARY KEY,
          control_mode TEXT NOT NULL CHECK (control_mode IN ('AWD', 'MOISTURE')),
          updated_at TIMESTAMPTZ DEFAULT NOW(),
          updated_by VARCHAR(100),
          notes TEXT
        );

        CREATE TABLE IF NOT EXISTS water_control_smartfarm.valve_status (
          plot_id VARCHAR(50) NOT NULL,
          valve_name VARCHAR(50) NOT NULL,
          status VARCHAR(10) NOT NULL,
          timestamp TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (plot_id, timestamp)
        );

        CREATE TABLE IF NOT EXISTS water_control_smartfarm.irrigation_cycles (
          id SERIAL PRIMARY KEY,
          plot_id VARCHAR(50) NOT NULL,
          valve_name VARCHAR(50) NOT NULL,
          start_time TIMESTAMPTZ NOT NULL,
          end_time TIMESTAMPTZ,
          volume_liters INTEGER,
          control_mode VARCHAR(20),
          trigger_value DECIMAL(10, 2),
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS water_control_smartfarm.water_balance (
          plot_id VARCHAR(50) NOT NULL,
          valve_name VARCHAR(50) NOT NULL,
          start_time TIMESTAMPTZ NOT NULL,
          end_time TIMESTAMPTZ NOT NULL,
          volume_liters INTEGER NOT NULL,
          control_mode VARCHAR(20),
          trigger_value DECIMAL(10, 2),
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Create alias for water_balance (used by WaterBalanceService)
        CREATE OR REPLACE VIEW water_balance_smartfarm AS
        SELECT * FROM water_control_smartfarm.water_balance;
      `);

      // Convert to hypertables if TimescaleDB extension is available
      try {
        await client.query(`
          SELECT create_hypertable('water_control_smartfarm.valve_status', 'timestamp',
            if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');

          SELECT create_hypertable('water_control_smartfarm.irrigation_cycles', 'start_time',
            if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');
        `);
        logger.info('Hypertables created successfully');
      } catch (err) {
        logger.warn(
          'TimescaleDB extension not available, using regular tables'
        );
      }

      // Create indexes
      await client.query(`
        CREATE INDEX IF NOT EXISTS idx_demands_plot_date
        ON ros_gis_smartfarm.daily_water_demands(plot_id, date DESC);

        CREATE INDEX IF NOT EXISTS idx_progress_plot_date
        ON ros_gis_smartfarm.daily_progress(plot_id, date DESC);

        CREATE INDEX IF NOT EXISTS idx_valve_status_plot
        ON water_control_smartfarm.valve_status(plot_id, timestamp DESC);

        CREATE INDEX IF NOT EXISTS idx_cycles_plot
        ON water_control_smartfarm.irrigation_cycles(plot_id, start_time DESC);
      `);

      // Skip trigger creation - triggers already exist in sensor_data database
      // Triggers are on sensor_data.public.moisture_readings and sensor_data.public.water_level_readings
      // They notify on channel 'sensor_evaluation_needed'

      logger.info('Database schemas and tables verified successfully');
    } catch (error) {
      logger.error({ error }, 'Failed to create schemas');
      throw error;
    } finally {
      client.release();
    }
  }

  async createSmartFarmNotifyTriggers(client) {
    try {
      // Drop existing triggers and function for idempotency
      await client.query(`
        DROP TRIGGER IF EXISTS trigger_notify_moisture_reading
        ON water_control_smartfarm.moisture_readings;

        DROP TRIGGER IF EXISTS trigger_notify_water_level_reading
        ON water_control_smartfarm.water_level_readings;

        DROP FUNCTION IF EXISTS smartfarm_notify_reading();
      `);

      // Create the notify function
      await client.query(`
        CREATE OR REPLACE FUNCTION smartfarm_notify_reading()
        RETURNS TRIGGER AS $$
        DECLARE
          payload JSON;
        BEGIN
          payload := json_build_object(
            'sensor_id', NEW.sensor_id,
            'sensor_type', TG_ARGV[0],
            'timestamp', NEW.timestamp
          );

          PERFORM pg_notify('smartfarm_readings', payload::text);

          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
      `);

      // Create trigger on moisture_readings (in public schema) - skip if exists
      await client.query(`
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trigger_notify_moisture_reading') THEN
            CREATE TRIGGER trigger_notify_moisture_reading
            AFTER INSERT ON public.moisture_readings
            FOR EACH ROW
            EXECUTE FUNCTION smartfarm_notify_reading('moisture');
          END IF;
        END$$;
      `);

      // Create trigger on water_level_readings (in public schema) - skip if exists
      await client.query(`
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trigger_notify_water_level_reading') THEN
            CREATE TRIGGER trigger_notify_water_level_reading
            AFTER INSERT ON public.water_level_readings
            FOR EACH ROW
            EXECUTE FUNCTION smartfarm_notify_reading('water-level');
          END IF;
        END$$;
      `);

      logger.info('Smart farm notification triggers created successfully');
    } catch (error) {
      logger.error({ error }, 'Failed to create notification triggers');
      throw error;
    }
  }

  async close() {
    if (this.timescalePool) {
      await this.timescalePool.end();
    }
    if (this.mssqlPool) {
      await this.mssqlPool.close();
    }
  }
}

module.exports = { DatabaseConfig };
