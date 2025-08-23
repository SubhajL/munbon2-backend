"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DatabaseService = void 0;
const pg_1 = require("pg");
const config_1 = require("../config");
const logger_1 = require("../utils/logger");
const weather_model_1 = require("../models/weather.model");
class DatabaseService {
    constructor() {
        // TimescaleDB connection for AOS data (Task 54)
        const timescaleConfig = {
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
        // PostgreSQL connection for weather integration data (Task 27, 45)
        const postgresConfig = {
            host: config_1.config.postgres.host,
            port: config_1.config.postgres.port,
            database: config_1.config.postgres.database,
            user: config_1.config.postgres.user,
            password: config_1.config.postgres.password,
            ssl: config_1.config.postgres.ssl ? { rejectUnauthorized: false } : false,
            max: 20,
            idleTimeoutMillis: 30000,
            connectionTimeoutMillis: 2000,
        };
        this.timescalePool = new pg_1.Pool(timescaleConfig);
        this.postgresPool = new pg_1.Pool(postgresConfig);
        this.timescalePool.on('error', (err) => {
            logger_1.logger.error({ err }, 'Unexpected error on TimescaleDB idle client');
        });
        this.postgresPool.on('error', (err) => {
            logger_1.logger.error({ err }, 'Unexpected error on PostgreSQL idle client');
        });
    }
    async getCurrentWeather(location, stationIds) {
        let query = `
      WITH latest_readings AS (
        SELECT DISTINCT ON (station_id)
          station_id,
          timestamp,
          location_lat,
          location_lng,
          temperature,
          humidity,
          pressure,
          wind_speed,
          wind_direction,
          rainfall,
          solar_radiation,
          uv_index,
          visibility,
          cloud_cover,
          dew_point,
          feels_like,
          source,
          quality_score
        FROM weather_readings
        WHERE timestamp > NOW() - INTERVAL '2 hours'
    `;
        const params = [];
        if (stationIds && stationIds.length > 0) {
            query += ` AND station_id = ANY($1)`;
            params.push(stationIds);
        }
        query += ` ORDER BY station_id, timestamp DESC
      )
      SELECT * FROM latest_readings
    `;
        if (location && !stationIds) {
            // Add location-based filtering
            const paramIndex = params.length + 1;
            query += ` WHERE (
        6371 * acos(
          cos(radians($${paramIndex})) * cos(radians(location_lat)) * 
          cos(radians(location_lng) - radians($${paramIndex + 1})) + 
          sin(radians($${paramIndex})) * sin(radians(location_lat))
        )
      ) <= 50`; // Within 50km
            params.push(location.lat, location.lng);
        }
        query += ` ORDER BY timestamp DESC`;
        // Try TimescaleDB first (AOS data)
        try {
            const result = await this.timescalePool.query(query, params);
            const readings = this.mapToWeatherReadings(result.rows, weather_model_1.WeatherDataSource.AOS);
            // If we have data, return it
            if (readings.length > 0) {
                return readings;
            }
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to query TimescaleDB');
        }
        // Fallback to PostgreSQL (other weather sources)
        try {
            const result = await this.postgresPool.query(query, params);
            return this.mapToWeatherReadings(result.rows, weather_model_1.WeatherDataSource.TMD);
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to query PostgreSQL');
            return [];
        }
    }
    async getHistoricalWeather(startTime, endTime, location, stationIds) {
        let query = `
      SELECT 
        station_id,
        timestamp,
        location_lat,
        location_lng,
        temperature,
        humidity,
        pressure,
        wind_speed,
        wind_direction,
        rainfall,
        solar_radiation,
        uv_index,
        visibility,
        cloud_cover,
        dew_point,
        feels_like,
        source,
        quality_score
      FROM weather_readings
      WHERE timestamp >= $1 AND timestamp <= $2
    `;
        const params = [startTime, endTime];
        if (stationIds && stationIds.length > 0) {
            query += ` AND station_id = ANY($3)`;
            params.push(stationIds);
        }
        if (location && !stationIds) {
            const paramIndex = params.length + 1;
            query += ` AND (
        6371 * acos(
          cos(radians($${paramIndex})) * cos(radians(location_lat)) * 
          cos(radians(location_lng) - radians($${paramIndex + 1})) + 
          sin(radians($${paramIndex})) * sin(radians(location_lat))
        )
      ) <= 50`;
            params.push(location.lat, location.lng);
        }
        query += ` ORDER BY timestamp DESC LIMIT 10000`;
        const readings = [];
        // Query both databases
        try {
            const [timescaleResult, postgresResult] = await Promise.all([
                this.timescalePool.query(query, params),
                this.postgresPool.query(query, params),
            ]);
            readings.push(...this.mapToWeatherReadings(timescaleResult.rows, weather_model_1.WeatherDataSource.AOS), ...this.mapToWeatherReadings(postgresResult.rows, weather_model_1.WeatherDataSource.TMD));
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to query historical weather');
        }
        // Sort by timestamp and remove duplicates
        return readings
            .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
            .filter((reading, index, self) => index === self.findIndex(r => r.stationId === reading.stationId &&
            r.timestamp.getTime() === reading.timestamp.getTime()));
    }
    async getAggregatedWeather(startTime, endTime, interval, location, stationId) {
        const query = `
      SELECT 
        time_bucket($1::interval, timestamp) AS bucket,
        station_id,
        AVG(temperature) as avg_temperature,
        MIN(temperature) as min_temperature,
        MAX(temperature) as max_temperature,
        AVG(humidity) as avg_humidity,
        AVG(pressure) as avg_pressure,
        SUM(rainfall) as total_rainfall,
        AVG(wind_speed) as avg_wind_speed,
        AVG(solar_radiation) as avg_solar_radiation,
        COUNT(*) as reading_count
      FROM weather_readings
      WHERE timestamp >= $2 AND timestamp <= $3
      ${stationId ? 'AND station_id = $4' : ''}
      ${location && !stationId ? `AND (
        6371 * acos(
          cos(radians($4)) * cos(radians(location_lat)) * 
          cos(radians(location_lng) - radians($5)) + 
          sin(radians($4)) * sin(radians(location_lat))
        )
      ) <= 50` : ''}
      GROUP BY bucket, station_id
      ORDER BY bucket DESC
    `;
        const params = [interval, startTime, endTime];
        if (stationId) {
            params.push(stationId);
        }
        else if (location) {
            params.push(location.lat, location.lng);
        }
        try {
            // Query both databases and merge results
            const [timescaleResult, postgresResult] = await Promise.all([
                this.timescalePool.query(query, params),
                this.postgresPool.query(query, params),
            ]);
            return [...timescaleResult.rows, ...postgresResult.rows];
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get aggregated weather');
            return [];
        }
    }
    async getWeatherStations(active) {
        const query = `
      SELECT DISTINCT ON (s.station_id)
        s.station_id,
        s.name,
        s.type,
        s.location_lat,
        s.location_lng,
        s.altitude,
        s.source,
        s.is_active,
        s.metadata,
        r.timestamp as last_reading_time,
        r.temperature,
        r.humidity,
        r.rainfall,
        r.wind_speed
      FROM weather_stations s
      LEFT JOIN weather_readings r ON s.station_id = r.station_id
      ${active !== undefined ? 'WHERE s.is_active = $1' : ''}
      ORDER BY s.station_id, r.timestamp DESC
    `;
        const params = active !== undefined ? [active] : [];
        const stations = [];
        try {
            // Query both databases
            const [timescaleResult, postgresResult] = await Promise.all([
                this.timescalePool.query(query, params),
                this.postgresPool.query(query, params),
            ]);
            stations.push(...this.mapToWeatherStations(timescaleResult.rows, weather_model_1.WeatherDataSource.AOS), ...this.mapToWeatherStations(postgresResult.rows, weather_model_1.WeatherDataSource.TMD));
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get weather stations');
        }
        return stations;
    }
    async getWeatherForecasts(location, days = 7) {
        const query = `
      SELECT 
        station_id,
        location_lat,
        location_lng,
        timestamp,
        forecast_time,
        temp_min,
        temp_max,
        temp_avg,
        humidity_min,
        humidity_max,
        humidity_avg,
        rainfall_amount,
        rainfall_probability,
        wind_speed,
        wind_direction,
        cloud_cover,
        uv_index,
        conditions,
        confidence,
        source
      FROM weather_forecasts
      WHERE forecast_time >= NOW() 
        AND forecast_time <= NOW() + INTERVAL '${days} days'
        AND (
          6371 * acos(
            cos(radians($1)) * cos(radians(location_lat)) * 
            cos(radians(location_lng) - radians($2)) + 
            sin(radians($1)) * sin(radians(location_lat))
          )
        ) <= 50
      ORDER BY forecast_time ASC
    `;
        try {
            // Forecasts are typically in PostgreSQL (from external APIs)
            const result = await this.postgresPool.query(query, [location.lat, location.lng]);
            return this.mapToWeatherForecasts(result.rows);
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get weather forecasts');
            return [];
        }
    }
    mapToWeatherReadings(rows, defaultSource) {
        return rows.map(row => ({
            stationId: row.station_id,
            timestamp: row.timestamp,
            location: row.location_lat && row.location_lng ? {
                lat: parseFloat(row.location_lat),
                lng: parseFloat(row.location_lng),
            } : undefined,
            temperature: row.temperature ? parseFloat(row.temperature) : undefined,
            humidity: row.humidity ? parseFloat(row.humidity) : undefined,
            pressure: row.pressure ? parseFloat(row.pressure) : undefined,
            windSpeed: row.wind_speed ? parseFloat(row.wind_speed) : undefined,
            windDirection: row.wind_direction ? parseFloat(row.wind_direction) : undefined,
            rainfall: row.rainfall ? parseFloat(row.rainfall) : undefined,
            solarRadiation: row.solar_radiation ? parseFloat(row.solar_radiation) : undefined,
            uvIndex: row.uv_index ? parseFloat(row.uv_index) : undefined,
            visibility: row.visibility ? parseFloat(row.visibility) : undefined,
            cloudCover: row.cloud_cover ? parseFloat(row.cloud_cover) : undefined,
            dewPoint: row.dew_point ? parseFloat(row.dew_point) : undefined,
            feelsLike: row.feels_like ? parseFloat(row.feels_like) : undefined,
            source: row.source || defaultSource,
            qualityScore: row.quality_score ? parseFloat(row.quality_score) : undefined,
        }));
    }
    mapToWeatherStations(rows, defaultSource) {
        return rows.map(row => ({
            stationId: row.station_id,
            name: row.name,
            type: row.type,
            location: {
                lat: parseFloat(row.location_lat),
                lng: parseFloat(row.location_lng),
                altitude: row.altitude ? parseFloat(row.altitude) : undefined,
            },
            source: row.source || defaultSource,
            isActive: row.is_active,
            lastSeen: row.last_reading_time || new Date(),
            metadata: row.metadata,
            lastReading: row.last_reading_time ? {
                stationId: row.station_id,
                timestamp: row.last_reading_time,
                temperature: row.temperature ? parseFloat(row.temperature) : undefined,
                humidity: row.humidity ? parseFloat(row.humidity) : undefined,
                rainfall: row.rainfall ? parseFloat(row.rainfall) : undefined,
                windSpeed: row.wind_speed ? parseFloat(row.wind_speed) : undefined,
                source: row.source || defaultSource,
            } : undefined,
        }));
    }
    mapToWeatherForecasts(rows) {
        return rows.map(row => ({
            stationId: row.station_id,
            location: {
                lat: parseFloat(row.location_lat),
                lng: parseFloat(row.location_lng),
            },
            timestamp: row.timestamp,
            forecastTime: row.forecast_time,
            temperature: {
                min: parseFloat(row.temp_min),
                max: parseFloat(row.temp_max),
                avg: parseFloat(row.temp_avg),
            },
            humidity: {
                min: parseFloat(row.humidity_min),
                max: parseFloat(row.humidity_max),
                avg: parseFloat(row.humidity_avg),
            },
            rainfall: {
                amount: parseFloat(row.rainfall_amount),
                probability: parseFloat(row.rainfall_probability),
            },
            windSpeed: parseFloat(row.wind_speed),
            windDirection: parseFloat(row.wind_direction),
            cloudCover: parseFloat(row.cloud_cover),
            uvIndex: parseFloat(row.uv_index),
            conditions: row.conditions,
            confidence: parseFloat(row.confidence),
            source: row.source,
        }));
    }
    async close() {
        await Promise.all([
            this.timescalePool.end(),
            this.postgresPool.end(),
        ]);
    }
}
exports.DatabaseService = DatabaseService;
//# sourceMappingURL=database.service.js.map