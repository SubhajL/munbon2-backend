import { Pool, PoolConfig } from 'pg';
import { config } from '../config';
import { logger } from '../utils/logger';
import {
  WaterLevelReading,
  WaterLevelAggregation,
  WaterLevelSensor,
  WaterLevelAnalytics,
} from '../models/water-level.model';

export class TimescaleService {
  private pool: Pool;

  constructor() {
    const poolConfig: PoolConfig = {
      host: config.timescale.host,
      port: config.timescale.port,
      database: config.timescale.database,
      user: config.timescale.user,
      password: config.timescale.password,
      ssl: config.timescale.ssl ? { rejectUnauthorized: false } : false,
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    };
    
    this.pool = new Pool(poolConfig);
    
    this.pool.on('error', (err) => {
      logger.error({ err }, 'Unexpected error on idle client');
    });
  }

  async getLatestReadings(sensorIds?: string[], limit: number = 100): Promise<WaterLevelReading[]> {
    let query = `
      SELECT 
        sensor_id,
        time as timestamp,
        location_lat,
        location_lng,
        level_cm,
        voltage,
        rssi,
        temperature,
        quality_score
      FROM water_level_readings
    `;
    
    const params: any[] = [];
    
    if (sensorIds && sensorIds.length > 0) {
      query += ' WHERE sensor_id = ANY($1)';
      params.push(sensorIds);
    }
    
    query += ' ORDER BY time DESC LIMIT $' + (params.length + 1);
    params.push(limit);
    
    const result = await this.pool.query(query, params);
    
    return result.rows.map(row => ({
      sensorId: row.sensor_id,
      timestamp: row.timestamp,
      location: row.location_lat && row.location_lng ? {
        lat: parseFloat(row.location_lat),
        lng: parseFloat(row.location_lng),
      } : undefined,
      levelCm: parseFloat(row.level_cm),
      voltage: row.voltage ? parseFloat(row.voltage) : undefined,
      rssi: row.rssi ? parseInt(row.rssi) : undefined,
      temperature: row.temperature ? parseFloat(row.temperature) : undefined,
      qualityScore: row.quality_score ? parseFloat(row.quality_score) : undefined,
    }));
  }

  async getReadingsByTimeRange(
    sensorId: string,
    startTime: Date,
    endTime: Date,
    limit?: number
  ): Promise<WaterLevelReading[]> {
    const query = `
      SELECT 
        sensor_id,
        time as timestamp,
        location_lat,
        location_lng,
        level_cm,
        voltage,
        rssi,
        temperature,
        quality_score
      FROM water_level_readings
      WHERE sensor_id = $1 
        AND time >= $2 
        AND time <= $3
      ORDER BY time DESC
      ${limit ? 'LIMIT $4' : ''}
    `;
    
    const params = limit 
      ? [sensorId, startTime, endTime, limit]
      : [sensorId, startTime, endTime];
    
    const result = await this.pool.query(query, params);
    
    return result.rows.map(row => ({
      sensorId: row.sensor_id,
      timestamp: row.timestamp,
      location: row.location_lat && row.location_lng ? {
        lat: parseFloat(row.location_lat),
        lng: parseFloat(row.location_lng),
      } : undefined,
      levelCm: parseFloat(row.level_cm),
      voltage: row.voltage ? parseFloat(row.voltage) : undefined,
      rssi: row.rssi ? parseInt(row.rssi) : undefined,
      temperature: row.temperature ? parseFloat(row.temperature) : undefined,
      qualityScore: row.quality_score ? parseFloat(row.quality_score) : undefined,
    }));
  }

  async getAggregatedReadings(
    sensorId: string,
    startTime: Date,
    endTime: Date,
    interval: string
  ): Promise<WaterLevelAggregation[]> {
    const query = `
      WITH time_series AS (
        SELECT 
          sensor_id,
          time_bucket($1::interval, time) AS bucket,
          level_cm,
          LAG(level_cm) OVER (PARTITION BY sensor_id ORDER BY time) as prev_level,
          EXTRACT(EPOCH FROM time - LAG(time) OVER (PARTITION BY sensor_id ORDER BY time)) / 3600 as hours_diff
        FROM water_level_readings
        WHERE sensor_id = $2
          AND time >= $3
          AND time <= $4
      )
      SELECT 
        sensor_id,
        bucket,
        AVG(level_cm) as avg_level,
        MIN(level_cm) as min_level,
        MAX(level_cm) as max_level,
        STDDEV(level_cm) as stddev_level,
        AVG(CASE 
          WHEN hours_diff > 0 AND hours_diff < 1 
          THEN ABS(level_cm - prev_level) / hours_diff 
          ELSE NULL 
        END) as rate_of_change,
        COUNT(*) as reading_count
      FROM time_series
      GROUP BY sensor_id, bucket
      ORDER BY bucket DESC
    `;
    
    const result = await this.pool.query(query, [interval, sensorId, startTime, endTime]);
    
    return result.rows.map(row => ({
      sensorId: row.sensor_id,
      bucket: row.bucket,
      avgLevel: parseFloat(row.avg_level),
      minLevel: parseFloat(row.min_level),
      maxLevel: parseFloat(row.max_level),
      stdDevLevel: parseFloat(row.stddev_level) || 0,
      rateOfChange: parseFloat(row.rate_of_change) || 0,
      readingCount: parseInt(row.reading_count),
    }));
  }

  async getActiveSensors(): Promise<WaterLevelSensor[]> {
    const query = `
      SELECT DISTINCT ON (wl.sensor_id)
        wl.sensor_id,
        sr.location_lat,
        sr.location_lng,
        sr.last_seen,
        sr.is_active,
        sr.metadata,
        wl.time as last_reading_time,
        wl.level_cm,
        wl.voltage,
        wl.rssi,
        wl.temperature,
        wl.quality_score
      FROM water_level_readings wl
      INNER JOIN sensor_registry sr ON wl.sensor_id = sr.sensor_id
      WHERE sr.sensor_type = 'water-level'
        AND sr.is_active = true
        AND sr.last_seen > NOW() - INTERVAL '24 hours'
      ORDER BY wl.sensor_id, wl.time DESC
    `;
    
    const result = await this.pool.query(query);
    
    return result.rows.map(row => ({
      sensorId: row.sensor_id,
      location: row.location_lat && row.location_lng ? {
        lat: parseFloat(row.location_lat),
        lng: parseFloat(row.location_lng),
      } : undefined,
      lastSeen: row.last_seen,
      isActive: row.is_active,
      metadata: row.metadata,
      lastReading: row.last_reading_time ? {
        sensorId: row.sensor_id,
        timestamp: row.last_reading_time,
        location: row.location_lat && row.location_lng ? {
          lat: parseFloat(row.location_lat),
          lng: parseFloat(row.location_lng),
        } : undefined,
        levelCm: parseFloat(row.level_cm),
        voltage: row.voltage ? parseFloat(row.voltage) : undefined,
        rssi: row.rssi ? parseInt(row.rssi) : undefined,
        temperature: row.temperature ? parseFloat(row.temperature) : undefined,
        qualityScore: row.quality_score ? parseFloat(row.quality_score) : undefined,
      } : undefined,
    }));
  }

  async getSensorsByLocation(
    lat: number,
    lng: number,
    radiusKm: number
  ): Promise<WaterLevelSensor[]> {
    const query = `
      SELECT DISTINCT ON (sr.sensor_id)
        sr.sensor_id,
        sr.location_lat,
        sr.location_lng,
        sr.last_seen,
        sr.is_active,
        sr.metadata,
        (
          6371 * acos(
            cos(radians($1)) * cos(radians(sr.location_lat)) * 
            cos(radians(sr.location_lng) - radians($2)) + 
            sin(radians($1)) * sin(radians(sr.location_lat))
          )
        ) as distance_km,
        wl.time as last_reading_time,
        wl.level_cm
      FROM sensor_registry sr
      LEFT JOIN water_level_readings wl ON sr.sensor_id = wl.sensor_id
      WHERE sr.sensor_type = 'water-level'
        AND sr.location_lat IS NOT NULL 
        AND sr.location_lng IS NOT NULL
        AND sr.is_active = true
        AND (
          6371 * acos(
            cos(radians($1)) * cos(radians(sr.location_lat)) * 
            cos(radians(sr.location_lng) - radians($2)) + 
            sin(radians($1)) * sin(radians(sr.location_lat))
          )
        ) <= $3
      ORDER BY sr.sensor_id, wl.time DESC
    `;
    
    const result = await this.pool.query(query, [lat, lng, radiusKm]);
    
    return result.rows.map(row => ({
      sensorId: row.sensor_id,
      location: {
        lat: parseFloat(row.location_lat),
        lng: parseFloat(row.location_lng),
      },
      lastSeen: row.last_seen,
      isActive: row.is_active,
      metadata: {
        ...row.metadata,
        distanceKm: parseFloat(row.distance_km),
      },
    }));
  }

  async getAnalytics(
    sensorId: string,
    period: string
  ): Promise<WaterLevelAnalytics> {
    const endTime = new Date();
    let startTime: Date;
    
    switch (period) {
      case '1h':
        startTime = new Date(endTime.getTime() - 60 * 60 * 1000);
        break;
      case '1d':
        startTime = new Date(endTime.getTime() - 24 * 60 * 60 * 1000);
        break;
      case '7d':
        startTime = new Date(endTime.getTime() - 7 * 24 * 60 * 60 * 1000);
        break;
      case '30d':
        startTime = new Date(endTime.getTime() - 30 * 24 * 60 * 60 * 1000);
        break;
      default:
        throw new Error(`Invalid period: ${period}`);
    }
    
    const query = `
      WITH readings AS (
        SELECT 
          time,
          level_cm,
          LAG(level_cm) OVER (ORDER BY time) as prev_level,
          EXTRACT(EPOCH FROM time - LAG(time) OVER (ORDER BY time)) / 3600 as hours_diff
        FROM water_level_readings
        WHERE sensor_id = $1
          AND time >= $2
          AND time <= $3
        ORDER BY time
      ),
      stats AS (
        SELECT 
          AVG(level_cm) as avg_level,
          STDDEV(level_cm) as stddev_level,
          MIN(level_cm) as min_level,
          MAX(level_cm) as max_level,
          MAX(level_cm) - MIN(level_cm) as total_change,
          COUNT(*) as total_readings,
          COUNT(CASE 
            WHEN ABS(level_cm - prev_level) > 2 AND hours_diff < 1 
            THEN 1 
          END) as anomaly_count
        FROM readings
      ),
      rate_changes AS (
        SELECT 
          AVG(CASE 
            WHEN hours_diff > 0 AND hours_diff < 1 
            THEN ABS(level_cm - prev_level) / hours_diff 
            ELSE NULL 
          END) as avg_rate_of_change,
          MAX(CASE 
            WHEN hours_diff > 0 AND hours_diff < 1 
            THEN ABS(level_cm - prev_level) / hours_diff 
            ELSE NULL 
          END) as max_rate_of_change
        FROM readings
      ),
      expected_readings AS (
        SELECT 
          EXTRACT(EPOCH FROM ($3::timestamp - $2::timestamp)) / 300 as expected_count
      ),
      trend_calc AS (
        SELECT 
          regr_slope(level_cm, EXTRACT(EPOCH FROM time)) as level_slope,
          regr_r2(level_cm, EXTRACT(EPOCH FROM time)) as level_r2
        FROM readings
      )
      SELECT 
        s.*,
        rc.avg_rate_of_change,
        rc.max_rate_of_change,
        e.expected_count,
        t.level_slope,
        t.level_r2
      FROM stats s, rate_changes rc, expected_readings e, trend_calc t
    `;
    
    const result = await this.pool.query(query, [sensorId, startTime, endTime]);
    const row = result.rows[0];
    
    if (!row) {
      throw new Error(`No data found for sensor ${sensorId}`);
    }
    
    const dataCompleteness = (row.total_readings / row.expected_count) * 100;
    
    const getLevelTrend = () => {
      if (Math.abs(row.level_slope) < 0.001) return 'stable';
      return row.level_slope > 0 ? 'increasing' : 'decreasing';
    };
    
    return {
      sensorId,
      period,
      startTime,
      endTime,
      stats: {
        avgLevel: parseFloat(row.avg_level) || 0,
        stdDevLevel: parseFloat(row.stddev_level) || 0,
        minLevel: parseFloat(row.min_level) || 0,
        maxLevel: parseFloat(row.max_level) || 0,
        totalChange: parseFloat(row.total_change) || 0,
        avgRateOfChange: parseFloat(row.avg_rate_of_change) || 0,
        maxRateOfChange: parseFloat(row.max_rate_of_change) || 0,
        dataCompleteness: Math.min(100, dataCompleteness),
        anomalyCount: parseInt(row.anomaly_count) || 0,
      },
      trends: {
        levelTrend: getLevelTrend(),
        trendStrength: parseFloat(row.level_r2) || 0,
      },
    };
  }

  async getRateOfChange(
    sensorId: string,
    minutes: number = 60
  ): Promise<number> {
    const query = `
      WITH recent_readings AS (
        SELECT 
          time,
          level_cm,
          FIRST_VALUE(level_cm) OVER (ORDER BY time DESC) as latest_level,
          FIRST_VALUE(time) OVER (ORDER BY time DESC) as latest_time,
          LAST_VALUE(level_cm) OVER (ORDER BY time DESC ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) as oldest_level,
          LAST_VALUE(time) OVER (ORDER BY time DESC ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) as oldest_time
        FROM water_level_readings
        WHERE sensor_id = $1
          AND time > NOW() - INTERVAL '${minutes} minutes'
        LIMIT 1
      )
      SELECT 
        (latest_level - oldest_level) / (EXTRACT(EPOCH FROM latest_time - oldest_time) / 3600) as rate_cm_per_hour
      FROM recent_readings
    `;
    
    const result = await this.pool.query(query, [sensorId]);
    return result.rows[0]?.rate_cm_per_hour || 0;
  }

  async close(): Promise<void> {
    await this.pool.end();
  }
}