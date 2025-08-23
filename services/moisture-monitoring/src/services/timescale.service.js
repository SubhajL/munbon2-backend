"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TimescaleService = void 0;
const pg_1 = require("pg");
const config_1 = require("../config");
const logger_1 = require("../utils/logger");
class TimescaleService {
    constructor() {
        const poolConfig = {
            host: config_1.config.timescale.host,
            port: config_1.config.timescale.port,
            database: config_1.config.timescale.database,
            user: config_1.config.timescale.user,
            password: config_1.config.timescale.password,
            ssl: config_1.config.timescale.ssl ? { rejectUnauthorized: false } : false,
            max: 20,
            idleTimeoutMillis: 30000,
            connectionTimeoutMillis: 2000,
        };
        this.pool = new pg_1.Pool(poolConfig);
        this.pool.on('error', (err) => {
            logger_1.logger.error({ err }, 'Unexpected error on idle client');
        });
    }
    async getLatestReadings(sensorIds, limit = 100) {
        let query = `
      SELECT 
        sensor_id,
        time as timestamp,
        location_lat,
        location_lng,
        moisture_surface_pct,
        moisture_deep_pct,
        temp_surface_c,
        temp_deep_c,
        ambient_humidity_pct,
        ambient_temp_c,
        flood_status,
        voltage,
        quality_score
      FROM moisture_readings
    `;
        const params = [];
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
            moistureSurfacePct: parseFloat(row.moisture_surface_pct),
            moistureDeepPct: parseFloat(row.moisture_deep_pct),
            tempSurfaceC: parseFloat(row.temp_surface_c),
            tempDeepC: parseFloat(row.temp_deep_c),
            ambientHumidityPct: parseFloat(row.ambient_humidity_pct),
            ambientTempC: parseFloat(row.ambient_temp_c),
            floodStatus: row.flood_status,
            voltage: row.voltage ? parseFloat(row.voltage) : undefined,
            qualityScore: row.quality_score ? parseFloat(row.quality_score) : undefined,
        }));
    }
    async getReadingsByTimeRange(sensorId, startTime, endTime, limit) {
        const query = `
      SELECT 
        sensor_id,
        time as timestamp,
        location_lat,
        location_lng,
        moisture_surface_pct,
        moisture_deep_pct,
        temp_surface_c,
        temp_deep_c,
        ambient_humidity_pct,
        ambient_temp_c,
        flood_status,
        voltage,
        quality_score
      FROM moisture_readings
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
            moistureSurfacePct: parseFloat(row.moisture_surface_pct),
            moistureDeepPct: parseFloat(row.moisture_deep_pct),
            tempSurfaceC: parseFloat(row.temp_surface_c),
            tempDeepC: parseFloat(row.temp_deep_c),
            ambientHumidityPct: parseFloat(row.ambient_humidity_pct),
            ambientTempC: parseFloat(row.ambient_temp_c),
            floodStatus: row.flood_status,
            voltage: row.voltage ? parseFloat(row.voltage) : undefined,
            qualityScore: row.quality_score ? parseFloat(row.quality_score) : undefined,
        }));
    }
    async getAggregatedReadings(sensorId, startTime, endTime, interval) {
        const query = `
      SELECT 
        sensor_id,
        time_bucket($1::interval, time) AS bucket,
        AVG(moisture_surface_pct) as avg_moisture_surface,
        AVG(moisture_deep_pct) as avg_moisture_deep,
        MIN(moisture_surface_pct) as min_moisture_surface,
        MIN(moisture_deep_pct) as min_moisture_deep,
        MAX(moisture_surface_pct) as max_moisture_surface,
        MAX(moisture_deep_pct) as max_moisture_deep,
        AVG(temp_surface_c) as avg_temp_surface,
        AVG(temp_deep_c) as avg_temp_deep,
        AVG(ambient_humidity_pct) as avg_ambient_humidity,
        AVG(ambient_temp_c) as avg_ambient_temp,
        SUM(CASE WHEN flood_status THEN 1 ELSE 0 END) as flood_detected_count,
        COUNT(*) as reading_count
      FROM moisture_readings
      WHERE sensor_id = $2
        AND time >= $3
        AND time <= $4
      GROUP BY sensor_id, bucket
      ORDER BY bucket DESC
    `;
        const result = await this.pool.query(query, [interval, sensorId, startTime, endTime]);
        return result.rows.map(row => ({
            sensorId: row.sensor_id,
            bucket: row.bucket,
            avgMoistureSurface: parseFloat(row.avg_moisture_surface),
            avgMoistureDeep: parseFloat(row.avg_moisture_deep),
            minMoistureSurface: parseFloat(row.min_moisture_surface),
            minMoistureDeep: parseFloat(row.min_moisture_deep),
            maxMoistureSurface: parseFloat(row.max_moisture_surface),
            maxMoistureDeep: parseFloat(row.max_moisture_deep),
            avgTempSurface: parseFloat(row.avg_temp_surface),
            avgTempDeep: parseFloat(row.avg_temp_deep),
            avgAmbientHumidity: parseFloat(row.avg_ambient_humidity),
            avgAmbientTemp: parseFloat(row.avg_ambient_temp),
            floodDetectedCount: parseInt(row.flood_detected_count),
            readingCount: parseInt(row.reading_count),
        }));
    }
    async getActiveSensors() {
        const query = `
      SELECT DISTINCT ON (mr.sensor_id)
        mr.sensor_id,
        sr.metadata->>'gatewayId' as gateway_id,
        sr.location_lat,
        sr.location_lng,
        sr.last_seen,
        sr.is_active,
        sr.metadata,
        mr.time as last_reading_time,
        mr.moisture_surface_pct,
        mr.moisture_deep_pct,
        mr.temp_surface_c,
        mr.temp_deep_c,
        mr.ambient_humidity_pct,
        mr.ambient_temp_c,
        mr.flood_status,
        mr.voltage,
        mr.quality_score
      FROM moisture_readings mr
      INNER JOIN sensor_registry sr ON mr.sensor_id = sr.sensor_id
      WHERE sr.sensor_type = 'moisture'
        AND sr.is_active = true
        AND sr.last_seen > NOW() - INTERVAL '24 hours'
      ORDER BY mr.sensor_id, mr.time DESC
    `;
        const result = await this.pool.query(query);
        return result.rows.map(row => ({
            sensorId: row.sensor_id,
            gatewayId: row.gateway_id || '',
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
                moistureSurfacePct: parseFloat(row.moisture_surface_pct),
                moistureDeepPct: parseFloat(row.moisture_deep_pct),
                tempSurfaceC: parseFloat(row.temp_surface_c),
                tempDeepC: parseFloat(row.temp_deep_c),
                ambientHumidityPct: parseFloat(row.ambient_humidity_pct),
                ambientTempC: parseFloat(row.ambient_temp_c),
                floodStatus: row.flood_status,
                voltage: row.voltage ? parseFloat(row.voltage) : undefined,
                qualityScore: row.quality_score ? parseFloat(row.quality_score) : undefined,
            } : undefined,
        }));
    }
    async getSensorsByLocation(lat, lng, radiusKm) {
        const query = `
      SELECT DISTINCT ON (sr.sensor_id)
        sr.sensor_id,
        sr.metadata->>'gatewayId' as gateway_id,
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
        mr.time as last_reading_time,
        mr.moisture_surface_pct,
        mr.moisture_deep_pct,
        mr.flood_status
      FROM sensor_registry sr
      LEFT JOIN moisture_readings mr ON sr.sensor_id = mr.sensor_id
      WHERE sr.sensor_type = 'moisture'
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
      ORDER BY sr.sensor_id, mr.time DESC
    `;
        const result = await this.pool.query(query, [lat, lng, radiusKm]);
        return result.rows.map(row => ({
            sensorId: row.sensor_id,
            gatewayId: row.gateway_id || '',
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
    async getAnalytics(sensorId, period) {
        const endTime = new Date();
        let startTime;
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
      WITH stats AS (
        SELECT 
          AVG(moisture_surface_pct) as avg_moisture_surface,
          AVG(moisture_deep_pct) as avg_moisture_deep,
          STDDEV(moisture_surface_pct) as stddev_moisture_surface,
          STDDEV(moisture_deep_pct) as stddev_moisture_deep,
          MIN(moisture_surface_pct) as min_moisture_surface,
          MAX(moisture_surface_pct) as max_moisture_surface,
          MIN(moisture_deep_pct) as min_moisture_deep,
          MAX(moisture_deep_pct) as max_moisture_deep,
          SUM(CASE WHEN flood_status THEN 1 ELSE 0 END) as flood_events,
          COUNT(*) as total_readings
        FROM moisture_readings
        WHERE sensor_id = $1
          AND time >= $2
          AND time <= $3
      ),
      expected_readings AS (
        SELECT 
          EXTRACT(EPOCH FROM ($3::timestamp - $2::timestamp)) / 300 as expected_count
      ),
      trend_calc AS (
        SELECT 
          regr_slope(moisture_surface_pct, EXTRACT(EPOCH FROM time)) as surface_slope,
          regr_slope(moisture_deep_pct, EXTRACT(EPOCH FROM time)) as deep_slope,
          regr_r2(moisture_surface_pct, EXTRACT(EPOCH FROM time)) as surface_r2,
          regr_r2(moisture_deep_pct, EXTRACT(EPOCH FROM time)) as deep_r2
        FROM moisture_readings
        WHERE sensor_id = $1
          AND time >= $2
          AND time <= $3
      )
      SELECT 
        s.*,
        e.expected_count,
        t.*
      FROM stats s, expected_readings e, trend_calc t
    `;
        const result = await this.pool.query(query, [sensorId, startTime, endTime]);
        const row = result.rows[0];
        if (!row) {
            throw new Error(`No data found for sensor ${sensorId}`);
        }
        const dataCompleteness = (row.total_readings / row.expected_count) * 100;
        const getSurfaceTrend = () => {
            if (Math.abs(row.surface_slope) < 0.01)
                return 'stable';
            return row.surface_slope > 0 ? 'increasing' : 'decreasing';
        };
        const getDeepTrend = () => {
            if (Math.abs(row.deep_slope) < 0.01)
                return 'stable';
            return row.deep_slope > 0 ? 'increasing' : 'decreasing';
        };
        return {
            sensorId,
            period,
            startTime,
            endTime,
            stats: {
                avgMoistureSurface: parseFloat(row.avg_moisture_surface) || 0,
                avgMoistureDeep: parseFloat(row.avg_moisture_deep) || 0,
                stdDevMoistureSurface: parseFloat(row.stddev_moisture_surface) || 0,
                stdDevMoistureDeep: parseFloat(row.stddev_moisture_deep) || 0,
                minMoistureSurface: parseFloat(row.min_moisture_surface) || 0,
                maxMoistureSurface: parseFloat(row.max_moisture_surface) || 0,
                minMoistureDeep: parseFloat(row.min_moisture_deep) || 0,
                maxMoistureDeep: parseFloat(row.max_moisture_deep) || 0,
                floodEvents: parseInt(row.flood_events) || 0,
                dataCompleteness: Math.min(100, dataCompleteness),
            },
            trends: {
                moistureSurfaceTrend: getSurfaceTrend(),
                moistureDeepTrend: getDeepTrend(),
                trendStrength: Math.max(parseFloat(row.surface_r2) || 0, parseFloat(row.deep_r2) || 0),
            },
        };
    }
    async close() {
        await this.pool.end();
    }
}
exports.TimescaleService = TimescaleService;
//# sourceMappingURL=timescale.service.js.map