import { Client, Pool, PoolConfig } from 'pg';
import { 
  SensorReading, 
  WaterLevelReading, 
  MoistureReading,
  SensorRegistry,
  SensorLocationHistory,
  SensorType
} from '../models/sensor.model';
import { toUTCTimestamp } from '../utils/timezone-fix';

export class TimescaleRepository {
  private pool: Pool;
  
  // Get a client for transaction support
  async getClient() {
    return this.pool.connect();
  }
  
  // Execute queries within a transaction
  async executeInTransaction<T>(
    callback: (client: any) => Promise<T>
  ): Promise<T> {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      const result = await callback(client);
      await client.query('COMMIT');
      return result;
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }
  
  private config: PoolConfig;

  constructor(config: PoolConfig) {
    this.config = {
      ...config,
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    };
    this.pool = new Pool(this.config);
  }

  async initialize(): Promise<void> {
    const client = await this.pool.connect();
    try {
      // Enable extensions
      // PostGIS removed due to disk space constraints - using lat/lng columns instead
      await client.query('CREATE EXTENSION IF NOT EXISTS timescaledb;');

      // Create tables
      await this.createTables(client as any);
      
      // Create hypertables - handle existing ones gracefully
      try {
        await this.createHypertables(client as any);
      } catch (error: any) {
        // Ignore errors about existing hypertables or triggers
        if (!error.message?.includes('already a hypertable') && 
            !error.message?.includes('already exists') &&
            error.code !== '42710') { // trigger already exists error code
          console.warn('Hypertable creation warning:', error.message);
        }
      }
      
      // Create indexes
      await this.createIndexes(client as any);
      
    } catch (error: any) {
      // Don't fail initialization for existing object errors
      if (error.code === '42710') { // trigger already exists
        console.log('Database objects already exist, continuing...');
      } else {
        throw error;
      }
    } finally {
      client.release();
    }
  }

  private async createTables(client: Client): Promise<void> {
    // Sensor registry
    await client.query(`
      CREATE TABLE IF NOT EXISTS sensor_registry (
        sensor_id VARCHAR(255) PRIMARY KEY,
        sensor_type VARCHAR(50) NOT NULL,
        manufacturer VARCHAR(100),
        model VARCHAR(100),
        installation_date TIMESTAMP,
        last_seen TIMESTAMP NOT NULL,
        location_lat DOUBLE PRECISION,
        location_lng DOUBLE PRECISION,
        metadata JSONB,
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
    `);

    // Generic sensor readings
    await client.query(`
      CREATE TABLE IF NOT EXISTS sensor_readings (
        time TIMESTAMP NOT NULL,
        sensor_id VARCHAR(255) NOT NULL,
        sensor_type VARCHAR(50) NOT NULL,
        location_lat DOUBLE PRECISION,
        location_lng DOUBLE PRECISION,
        value JSONB NOT NULL,
        metadata JSONB,
        quality_score NUMERIC(3,2),
        FOREIGN KEY (sensor_id) REFERENCES sensor_registry(sensor_id)
      );
    `);

    // Water level readings
    await client.query(`
      CREATE TABLE IF NOT EXISTS water_level_readings (
        time TIMESTAMP NOT NULL,
        sensor_id VARCHAR(255) NOT NULL,
        location_lat DOUBLE PRECISION,
        location_lng DOUBLE PRECISION,
        level_cm NUMERIC(5,2) NOT NULL,
        voltage NUMERIC(4,2),
        rssi INTEGER,
        temperature NUMERIC(4,2),
        quality_score NUMERIC(3,2),
        FOREIGN KEY (sensor_id) REFERENCES sensor_registry(sensor_id)
      );
    `);

    // Moisture readings
    await client.query(`
      CREATE TABLE IF NOT EXISTS moisture_readings (
        time TIMESTAMP NOT NULL,
        sensor_id VARCHAR(255) NOT NULL,
        location_lat DOUBLE PRECISION,
        location_lng DOUBLE PRECISION,
        moisture_surface_pct NUMERIC(5,2),
        moisture_deep_pct NUMERIC(5,2),
        temp_surface_c NUMERIC(4,2),
        temp_deep_c NUMERIC(4,2),
        ambient_humidity_pct NUMERIC(5,2),
        ambient_temp_c NUMERIC(4,2),
        flood_status BOOLEAN,
        voltage NUMERIC(4,2),
        quality_score NUMERIC(3,2),
        FOREIGN KEY (sensor_id) REFERENCES sensor_registry(sensor_id)
      );
    `);

    // Location history
    await client.query(`
      CREATE TABLE IF NOT EXISTS sensor_location_history (
        sensor_id VARCHAR(255) NOT NULL,
        time TIMESTAMP NOT NULL,
        location_lat DOUBLE PRECISION NOT NULL,
        location_lng DOUBLE PRECISION NOT NULL,
        accuracy NUMERIC(5,2),
        reason VARCHAR(255),
        FOREIGN KEY (sensor_id) REFERENCES sensor_registry(sensor_id)
      );
    `);

    // Calibration data
    await client.query(`
      CREATE TABLE IF NOT EXISTS sensor_calibrations (
        sensor_id VARCHAR(255) NOT NULL,
        calibration_type VARCHAR(50) NOT NULL,
        calibration_data JSONB NOT NULL,
        applied_at TIMESTAMP NOT NULL,
        expires_at TIMESTAMP,
        FOREIGN KEY (sensor_id) REFERENCES sensor_registry(sensor_id),
        PRIMARY KEY (sensor_id, calibration_type)
      );
    `);
  }

  private async createHypertables(client: Client): Promise<void> {
    // Convert to hypertables
    const tables = [
      { name: 'sensor_readings', interval: '1 day' },
      { name: 'water_level_readings', interval: '1 day' },
      { name: 'moisture_readings', interval: '1 day' },
      { name: 'sensor_location_history', interval: '7 days' }
    ];

    for (const table of tables) {
      await client.query(`
        SELECT create_hypertable('${table.name}', 'time', 
          if_not_exists => TRUE,
          chunk_time_interval => INTERVAL '${table.interval}'
        );
      `);
    }
  }

  private async createIndexes(client: Client): Promise<void> {
    // Sensor readings indexes
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_time 
      ON sensor_readings (sensor_id, time DESC);
    `);
    
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_sensor_readings_location 
      ON sensor_readings (location_lat, location_lng);
    `);

    // Water level indexes
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_water_level_sensor_time 
      ON water_level_readings (sensor_id, time DESC);
    `);

    // Moisture indexes
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_moisture_sensor_time 
      ON moisture_readings (sensor_id, time DESC);
    `);

    // Location history indexes
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_location_history_sensor_time 
      ON sensor_location_history (sensor_id, time DESC);
    `);
    
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_location_history_lat 
      ON sensor_location_history (location_lat);
    `);
    
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_location_history_lng 
      ON sensor_location_history (location_lng);
    `);
  }

  async saveSensorReading(reading: SensorReading): Promise<void> {
    const query = `
      INSERT INTO sensor_readings (time, sensor_id, sensor_type, location_lat, location_lng, value, metadata, quality_score)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8);
    `;
    
    await this.pool.query(query, [
      toUTCTimestamp(reading.timestamp),  // Convert to UTC timestamp string
      reading.sensorId,
      reading.sensorType,
      reading.location?.lat || null,
      reading.location?.lng || null,
      reading.data || {},
      reading.metadata || {},
      reading.qualityScore || 0.95
    ]);
  }

  async saveWaterLevelReading(reading: WaterLevelReading): Promise<void> {
    const query = `
      INSERT INTO water_level_readings 
      (time, sensor_id, location_lat, location_lng, level_cm, voltage, rssi, temperature, quality_score)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);
    `;
    
    await this.pool.query(query, [
      toUTCTimestamp(reading.timestamp),  // Convert to UTC timestamp string
      reading.sensorId,
      reading.location?.lat || null,
      reading.location?.lng || null,
      reading.levelCm,
      reading.voltage,
      reading.rssi,
      reading.temperature,
      reading.qualityScore
    ]);
  }

  async saveMoistureReading(reading: MoistureReading): Promise<void> {
    const query = `
      INSERT INTO moisture_readings 
      (time, sensor_id, location_lat, location_lng, moisture_surface_pct, moisture_deep_pct,
       temp_surface_c, temp_deep_c, ambient_humidity_pct, ambient_temp_c,
       flood_status, voltage, quality_score)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13);
    `;
    
    await this.pool.query(query, [
      toUTCTimestamp(reading.timestamp),  // Convert to UTC timestamp string
      reading.sensorId,
      reading.location?.lat || null,
      reading.location?.lng || null,
      reading.moistureSurfacePct,
      reading.moistureDeepPct,
      reading.tempSurfaceC,
      reading.tempDeepC,
      reading.ambientHumidityPct,
      reading.ambientTempC,
      reading.floodStatus,
      reading.voltage,
      reading.qualityScore
    ]);
  }

  async updateSensorRegistry(sensor: Partial<SensorRegistry>): Promise<void> {
    const query = `
      INSERT INTO sensor_registry (sensor_id, sensor_type, manufacturer, location_lat, location_lng, last_seen, metadata)
      VALUES ($1, $2, $3, $4, $5, $6, $7)
      ON CONFLICT (sensor_id) 
      DO UPDATE SET 
        location_lat = $4,
        location_lng = $5,
        last_seen = $6,
        metadata = sensor_registry.metadata || $7,
        updated_at = CURRENT_TIMESTAMP;
    `;
    
    await this.pool.query(query, [
      sensor.sensorId,
      sensor.sensorType,
      sensor.manufacturer || (sensor.sensorType === SensorType.WATER_LEVEL ? 'RID-R' : 'M2M'),
      sensor.currentLocation?.lat || null,
      sensor.currentLocation?.lng || null,
      sensor.lastSeen ? toUTCTimestamp(sensor.lastSeen) : null,  // Convert to UTC timestamp string
      sensor.metadata || {}
    ]);
  }

  async addLocationHistory(history: SensorLocationHistory): Promise<void> {
    const query = `
      INSERT INTO sensor_location_history (sensor_id, time, location_lat, location_lng, accuracy, reason)
      VALUES ($1, $2, $3, $4, $5, $6);
    `;
    
    await this.pool.query(query, [
      history.sensorId,
      history.timestamp,
      history.location.lat,
      history.location.lng,
      history.accuracy,
      history.reason
    ]);
  }

  async getSensorReadings(
    sensorId: string, 
    startTime: Date, 
    endTime: Date,
    aggregation?: string
  ): Promise<any[]> {
    let query: string;
    
    if (aggregation) {
      // Time-based aggregation
      query = `
        SELECT 
          time_bucket('${aggregation}', time) AS bucket,
          sensor_id,
          sensor_type,
          AVG((value->>'level')::numeric) as avg_value,
          MIN((value->>'level')::numeric) as min_value,
          MAX((value->>'level')::numeric) as max_value,
          COUNT(*) as count
        FROM sensor_readings
        WHERE sensor_id = $1 
          AND time >= $2 
          AND time <= $3
        GROUP BY bucket, sensor_id, sensor_type
        ORDER BY bucket DESC;
      `;
    } else {
      // Raw data
      query = `
        SELECT * FROM sensor_readings
        WHERE sensor_id = $1 
          AND time >= $2 
          AND time <= $3
        ORDER BY time DESC;
      `;
    }
    
    const result = await this.pool.query(query, [sensorId, startTime, endTime]);
    return result.rows;
  }

  async getActiveSensors(): Promise<any[]> {
    const query = `
      SELECT 
        s.*,
        (SELECT COUNT(*) FROM sensor_readings r WHERE r.sensor_id = s.sensor_id 
         AND r.time > NOW() - INTERVAL '1 hour') as recent_readings
      FROM sensor_registry s
      WHERE is_active = true
        AND last_seen > NOW() - INTERVAL '24 hours'
      ORDER BY last_seen DESC;
    `;
    
    const result = await this.pool.query(query);
    return result.rows.map(row => ({
      ...row,
      location: row.location_lat && row.location_lng ? {
        lat: row.location_lat,
        lng: row.location_lng
      } : null
    }));
  }

  async getSensorsByLocation(lat: number, lng: number, radiusKm: number): Promise<any[]> {
    // Using Haversine formula for distance calculation
    const query = `
      SELECT 
        s.*,
        (
          6371 * acos(
            cos(radians($1)) * cos(radians(s.location_lat)) * 
            cos(radians(s.location_lng) - radians($2)) + 
            sin(radians($1)) * sin(radians(s.location_lat))
          )
        ) as distance_km
      FROM sensor_registry s
      WHERE s.location_lat IS NOT NULL 
        AND s.location_lng IS NOT NULL
        AND (
          6371 * acos(
            cos(radians($1)) * cos(radians(s.location_lat)) * 
            cos(radians(s.location_lng) - radians($2)) + 
            sin(radians($1)) * sin(radians(s.location_lat))
          )
        ) <= $3
        AND is_active = true
      ORDER BY distance_km;
    `;
    
    const result = await this.pool.query(query, [lat, lng, radiusKm]);
    return result.rows.map(row => ({
      ...row,
      location: row.location_lat && row.location_lng ? {
        lat: row.location_lat,
        lng: row.location_lng
      } : null
    }));
  }

  async query(text: string, params?: any[]): Promise<any> {
    return this.pool.query(text, params);
  }

  async close(): Promise<void> {
    await this.pool.end();
  }
}