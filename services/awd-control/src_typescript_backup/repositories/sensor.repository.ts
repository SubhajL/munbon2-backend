import { getTimescalePool, getPostgresPool } from '../config/database';
import { logger } from '../utils/logger';
import { 
  WaterLevelReading, 
  MoistureReading, 
  GISWaterLevel, 
  SensorStatus,
  FieldSensorConfig 
} from '../types/sensor.types';

export class SensorRepository {
  private timescalePool = getTimescalePool();
  private postgresPool = getPostgresPool();

  /**
   * Get latest water level reading for a field
   * First tries sensor data, then falls back to GIS data
   */
  async getLatestWaterLevel(fieldId: string): Promise<WaterLevelReading | null> {
    try {
      // First, try to get sensor reading from TimescaleDB
      const sensorQuery = `
        SELECT 
          time,
          sensor_id as "sensorId",
          field_id as "fieldId",
          water_level_cm as "waterLevelCm",
          temperature_celsius as temperature,
          humidity_percent as humidity,
          battery_voltage as "batteryVoltage",
          signal_strength as "signalStrength"
        FROM water_level_readings
        WHERE field_id = $1
        ORDER BY time DESC
        LIMIT 1
      `;

      const sensorResult = await this.timescalePool.query(sensorQuery, [fieldId]);
      
      if (sensorResult.rows.length > 0) {
        return {
          ...sensorResult.rows[0],
          source: 'sensor'
        };
      }

      // If no sensor data, try GIS data
      const gisData = await this.getGISWaterLevel(fieldId);
      if (gisData) {
        return {
          time: gisData.measurementDate,
          sensorId: `gis_${gisData.plotId}`,
          fieldId: gisData.fieldId,
          waterLevelCm: gisData.waterHeightCm,
          source: 'gis'
        };
      }

      return null;
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get water level reading');
      throw error;
    }
  }

  /**
   * Get water level readings for a time range
   */
  async getWaterLevelHistory(
    fieldId: string, 
    startTime: Date, 
    endTime: Date
  ): Promise<WaterLevelReading[]> {
    try {
      const query = `
        SELECT 
          time,
          sensor_id as "sensorId",
          field_id as "fieldId",
          water_level_cm as "waterLevelCm",
          temperature_celsius as temperature,
          humidity_percent as humidity,
          battery_voltage as "batteryVoltage",
          signal_strength as "signalStrength"
        FROM water_level_readings
        WHERE field_id = $1 
          AND time >= $2 
          AND time <= $3
        ORDER BY time DESC
      `;

      const result = await this.timescalePool.query(query, [fieldId, startTime, endTime]);
      
      return result.rows.map(row => ({
        ...row,
        source: 'sensor' as const
      }));
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get water level history');
      throw error;
    }
  }

  /**
   * Get latest moisture reading for a field
   */
  async getLatestMoistureReading(fieldId: string): Promise<MoistureReading | null> {
    try {
      const query = `
        SELECT 
          time,
          sensor_id as "sensorId",
          field_id as "fieldId",
          moisture_percent as "moisturePercent",
          depth_cm as depth,
          temperature_celsius as temperature,
          battery_voltage as "batteryVoltage"
        FROM moisture_readings
        WHERE field_id = $1
        ORDER BY time DESC
        LIMIT 1
      `;

      const result = await this.timescalePool.query(query, [fieldId]);
      
      return result.rows.length > 0 ? result.rows[0] : null;
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get moisture reading');
      throw error;
    }
  }

  /**
   * Get moisture readings for a time range
   */
  async getMoistureHistory(
    fieldId: string,
    startTime: Date,
    endTime: Date
  ): Promise<MoistureReading[]> {
    try {
      const query = `
        SELECT 
          time,
          sensor_id as "sensorId",
          field_id as "fieldId",
          moisture_percent as "moisturePercent",
          depth_cm as depth,
          temperature_celsius as temperature,
          battery_voltage as "batteryVoltage"
        FROM moisture_readings
        WHERE field_id = $1 
          AND time >= $2 
          AND time <= $3
        ORDER BY time DESC
      `;

      const result = await this.timescalePool.query(query, [fieldId, startTime, endTime]);
      
      return result.rows;
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get moisture history');
      throw error;
    }
  }

  /**
   * Get water level from GIS/SHAPE data
   */
  async getGISWaterLevel(fieldId: string): Promise<GISWaterLevel | null> {
    try {
      // Query GIS schema for water level measurements
      const query = `
        SELECT 
          field_id as "fieldId",
          plot_id as "plotId",
          water_height_cm as "waterHeightCm",
          crop_height_cm as "cropHeightCm",
          measurement_date as "measurementDate",
          area,
          ST_AsGeoJSON(geometry) as geometry
        FROM gis.water_level_measurements
        WHERE field_id = $1
        ORDER BY measurement_date DESC
        LIMIT 1
      `;

      const result = await this.postgresPool.query(query, [fieldId]);
      
      if (result.rows.length > 0) {
        const row = result.rows[0];
        return {
          ...row,
          geometry: row.geometry ? JSON.parse(row.geometry) : null
        };
      }

      return null;
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get GIS water level');
      // Return null if GIS data is not available
      return null;
    }
  }

  /**
   * Get sensor configuration for a field
   */
  async getFieldSensorConfig(fieldId: string): Promise<FieldSensorConfig> {
    try {
      // Get sensors assigned to the field
      const sensorQuery = `
        SELECT 
          sensor_id,
          sensor_type,
          status
        FROM awd_sensors
        WHERE field_id = $1 AND status = 'active'
      `;

      const sensorResult = await this.postgresPool.query(sensorQuery, [fieldId]);
      
      const waterLevelSensorIds: string[] = [];
      const moistureSensorIds: string[] = [];
      
      sensorResult.rows.forEach(sensor => {
        if (sensor.sensor_type === 'water_level') {
          waterLevelSensorIds.push(sensor.sensor_id);
        } else if (sensor.sensor_type === 'moisture') {
          moistureSensorIds.push(sensor.sensor_id);
        }
      });

      // Get drying cycle info if exists
      const cycleQuery = `
        SELECT 
          drying_start_date,
          drying_day_count
        FROM awd_field_cycles
        WHERE field_id = $1 AND cycle_status = 'drying'
        ORDER BY created_at DESC
        LIMIT 1
      `;

      const cycleResult = await this.postgresPool.query(cycleQuery, [fieldId]);
      
      return {
        fieldId,
        hasWaterLevelSensor: waterLevelSensorIds.length > 0,
        hasMoistureSensor: moistureSensorIds.length > 0,
        waterLevelSensorIds,
        moistureSensorIds,
        useGISFallback: waterLevelSensorIds.length === 0,
        dryingDayCount: cycleResult.rows[0]?.drying_day_count,
        lastDryingStartDate: cycleResult.rows[0]?.drying_start_date
      };
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get field sensor config');
      throw error;
    }
  }

  /**
   * Get sensor status
   */
  async getSensorStatus(sensorId: string): Promise<SensorStatus | null> {
    try {
      const query = `
        SELECT 
          s.sensor_id as "sensorId",
          s.field_id as "fieldId",
          s.sensor_type as type,
          s.last_reading_at as "lastReading",
          s.status = 'active' as "isActive",
          CASE 
            WHEN s.last_reading_at > NOW() - INTERVAL '1 hour' THEN 1.0
            WHEN s.last_reading_at > NOW() - INTERVAL '6 hours' THEN 0.8
            WHEN s.last_reading_at > NOW() - INTERVAL '24 hours' THEN 0.5
            ELSE 0.2
          END as reliability
        FROM awd_sensors s
        WHERE s.sensor_id = $1
      `;

      const result = await this.postgresPool.query(query, [sensorId]);
      
      if (result.rows.length === 0) {
        return null;
      }

      const sensor = result.rows[0];
      
      // Get latest battery level from readings
      let batteryLevel: number | undefined;
      if (sensor.type === 'water_level') {
        const batteryQuery = `
          SELECT battery_voltage
          FROM water_level_readings
          WHERE sensor_id = $1
          ORDER BY time DESC
          LIMIT 1
        `;
        const batteryResult = await this.timescalePool.query(batteryQuery, [sensorId]);
        batteryLevel = batteryResult.rows[0]?.battery_voltage;
      }

      return {
        ...sensor,
        batteryLevel
      };
    } catch (error) {
      logger.error({ error, sensorId }, 'Failed to get sensor status');
      throw error;
    }
  }

  /**
   * Update sensor last reading timestamp
   */
  async updateSensorLastReading(sensorId: string, readingTime: Date): Promise<void> {
    try {
      const query = `
        UPDATE awd_sensors
        SET 
          last_reading_at = $2,
          updated_at = CURRENT_TIMESTAMP
        WHERE sensor_id = $1
      `;

      await this.postgresPool.query(query, [sensorId, readingTime]);
    } catch (error) {
      logger.error({ error, sensorId }, 'Failed to update sensor last reading');
      throw error;
    }
  }
}

export const sensorRepository = new SensorRepository();