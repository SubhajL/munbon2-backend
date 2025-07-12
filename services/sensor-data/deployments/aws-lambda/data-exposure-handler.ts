import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import { Pool } from 'pg';
import { createLogger } from './utils/logger';

const logger = createLogger('data-exposure');

// Initialize PostgreSQL connection pool
const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '5433'),
  database: process.env.DB_NAME || 'sensor_data',
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres',
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

// Buddhist calendar conversion
const convertToBuddhistDate = (date: Date): string => {
  const year = date.getFullYear() + 543;
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${day}/${month}/${year}`;
};

const parseBuddhistDate = (dateStr: string): Date => {
  const [day, month, year] = dateStr.split('/').map(Number);
  return new Date(year - 543, month - 1, day);
};

// API Key validation
const validateApiKey = (apiKey: string | undefined): boolean => {
  if (!apiKey) return false;
  const validApiKeys = (process.env.EXTERNAL_API_KEYS || '').split(',').filter(k => k);
  return validApiKeys.includes(apiKey);
};

// CORS headers
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type,X-API-Key',
  'Access-Control-Allow-Methods': 'GET,OPTIONS',
};

// Response helper
const createResponse = (statusCode: number, body: any): APIGatewayProxyResult => ({
  statusCode,
  headers: {
    'Content-Type': 'application/json',
    ...corsHeaders,
  },
  body: JSON.stringify(body),
});

// Water Level Latest Handler
export const waterLevelLatest = async (
  event: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> => {
  try {
    // Validate API Key
    const apiKey = event.headers['X-API-Key'] || event.headers['x-api-key'];
    if (!validateApiKey(apiKey)) {
      return createResponse(401, { error: 'Invalid API key' });
    }

    // Query latest water level data
    const query = `
      SELECT 
        sensor_id,
        sensor_name,
        zone,
        ST_X(location) as longitude,
        ST_Y(location) as latitude,
        timestamp,
        water_level_m,
        flow_rate_m3s,
        quality
      FROM water_levels wl
      INNER JOIN (
        SELECT sensor_id, MAX(timestamp) as max_time
        FROM water_levels
        WHERE timestamp > NOW() - INTERVAL '24 hours'
        GROUP BY sensor_id
      ) latest ON wl.sensor_id = latest.sensor_id AND wl.timestamp = latest.max_time
      ORDER BY sensor_id
    `;

    const result = await pool.query(query);
    
    const response = {
      data_type: 'water_level',
      request_time: new Date().toISOString(),
      request_time_buddhist: convertToBuddhistDate(new Date()),
      sensor_count: result.rows.length,
      sensors: result.rows.map(row => ({
        sensor_id: row.sensor_id,
        sensor_name: row.sensor_name,
        location: {
          longitude: row.longitude,
          latitude: row.latitude,
        },
        zone: row.zone,
        latest_reading: {
          timestamp: row.timestamp,
          timestamp_buddhist: convertToBuddhistDate(new Date(row.timestamp)),
          water_level_m: parseFloat(row.water_level_m),
          flow_rate_m3s: parseFloat(row.flow_rate_m3s),
          quality: parseInt(row.quality),
        },
      })),
    };

    return createResponse(200, response);
  } catch (error) {
    logger.error('Error fetching water level data:', error);
    return createResponse(500, { 
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
};

// Water Level Time Series Handler
export const waterLevelTimeseries = async (
  event: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> => {
  try {
    // Validate API Key
    const apiKey = event.headers['X-API-Key'] || event.headers['x-api-key'];
    if (!validateApiKey(apiKey)) {
      return createResponse(401, { error: 'Invalid API key' });
    }

    // Get date parameter
    const dateParam = event.queryStringParameters?.date;
    if (!dateParam) {
      return createResponse(400, { 
        error: 'Date parameter is required (dd/mm/yyyy in Buddhist calendar)' 
      });
    }

    const date = parseBuddhistDate(dateParam);
    const startDate = new Date(date);
    startDate.setHours(0, 0, 0, 0);
    const endDate = new Date(date);
    endDate.setHours(23, 59, 59, 999);

    // Query time series data
    const query = `
      SELECT 
        sensor_id,
        sensor_name,
        zone,
        ST_X(location) as longitude,
        ST_Y(location) as latitude,
        timestamp,
        water_level_m,
        flow_rate_m3s,
        quality
      FROM water_levels
      WHERE timestamp >= $1 AND timestamp <= $2
      ORDER BY sensor_id, timestamp
    `;

    const result = await pool.query(query, [startDate, endDate]);
    
    // Group by sensor
    const sensorData = new Map();
    result.rows.forEach(row => {
      if (!sensorData.has(row.sensor_id)) {
        sensorData.set(row.sensor_id, {
          sensor_id: row.sensor_id,
          sensor_name: row.sensor_name,
          location: {
            longitude: row.longitude,
            latitude: row.latitude,
          },
          zone: row.zone,
          date_buddhist: dateParam,
          readings: [],
        });
      }
      
      sensorData.get(row.sensor_id).readings.push({
        timestamp: row.timestamp,
        water_level_m: parseFloat(row.water_level_m),
        flow_rate_m3s: parseFloat(row.flow_rate_m3s),
        quality: parseInt(row.quality),
      });
    });

    const response = {
      data_type: 'water_level',
      request_date: dateParam,
      sensor_count: sensorData.size,
      sensors: Array.from(sensorData.values()),
    };

    return createResponse(200, response);
  } catch (error) {
    logger.error('Error fetching water level timeseries:', error);
    return createResponse(500, { 
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
};

// Moisture Latest Handler
export const moistureLatest = async (
  event: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> => {
  try {
    // Validate API Key
    const apiKey = event.headers['X-API-Key'] || event.headers['x-api-key'];
    if (!validateApiKey(apiKey)) {
      return createResponse(401, { error: 'Invalid API key' });
    }

    // Query latest moisture data
    const query = `
      SELECT 
        sensor_id,
        sensor_name,
        zone,
        ST_X(location) as longitude,
        ST_Y(location) as latitude,
        timestamp,
        moisture_percentage,
        temperature_celsius,
        quality
      FROM moisture_readings mr
      INNER JOIN (
        SELECT sensor_id, MAX(timestamp) as max_time
        FROM moisture_readings
        WHERE timestamp > NOW() - INTERVAL '24 hours'
        GROUP BY sensor_id
      ) latest ON mr.sensor_id = latest.sensor_id AND mr.timestamp = latest.max_time
      ORDER BY sensor_id
    `;

    const result = await pool.query(query);
    
    const response = {
      data_type: 'moisture',
      request_time: new Date().toISOString(),
      request_time_buddhist: convertToBuddhistDate(new Date()),
      sensor_count: result.rows.length,
      sensors: result.rows.map(row => ({
        sensor_id: row.sensor_id,
        sensor_name: row.sensor_name,
        location: {
          longitude: row.longitude,
          latitude: row.latitude,
        },
        zone: row.zone,
        latest_reading: {
          timestamp: row.timestamp,
          timestamp_buddhist: convertToBuddhistDate(new Date(row.timestamp)),
          moisture_percentage: parseFloat(row.moisture_percentage),
          temperature_celsius: parseFloat(row.temperature_celsius),
          quality: parseInt(row.quality),
        },
      })),
    };

    return createResponse(200, response);
  } catch (error) {
    logger.error('Error fetching moisture data:', error);
    return createResponse(500, { 
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
};

// AOS Latest Handler
export const aosLatest = async (
  event: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> => {
  try {
    // Validate API Key
    const apiKey = event.headers['X-API-Key'] || event.headers['x-api-key'];
    if (!validateApiKey(apiKey)) {
      return createResponse(401, { error: 'Invalid API key' });
    }

    // Query latest AOS data
    const query = `
      SELECT 
        station_id,
        station_name,
        zone,
        ST_X(location) as longitude,
        ST_Y(location) as latitude,
        timestamp,
        rainfall_mm,
        temperature_celsius,
        humidity_percentage,
        wind_speed_ms,
        wind_direction_degrees,
        pressure_hpa
      FROM aos_readings ar
      INNER JOIN (
        SELECT station_id, MAX(timestamp) as max_time
        FROM aos_readings
        WHERE timestamp > NOW() - INTERVAL '24 hours'
        GROUP BY station_id
      ) latest ON ar.station_id = latest.station_id AND ar.timestamp = latest.max_time
      ORDER BY station_id
    `;

    const result = await pool.query(query);
    
    const response = {
      data_type: 'aos_meteorological',
      request_time: new Date().toISOString(),
      request_time_buddhist: convertToBuddhistDate(new Date()),
      station_count: result.rows.length,
      stations: result.rows.map(row => ({
        station_id: row.station_id,
        station_name: row.station_name,
        location: {
          longitude: row.longitude,
          latitude: row.latitude,
        },
        zone: row.zone,
        latest_reading: {
          timestamp: row.timestamp,
          timestamp_buddhist: convertToBuddhistDate(new Date(row.timestamp)),
          rainfall_mm: parseFloat(row.rainfall_mm),
          temperature_celsius: parseFloat(row.temperature_celsius),
          humidity_percentage: parseFloat(row.humidity_percentage),
          wind_speed_ms: parseFloat(row.wind_speed_ms),
          wind_direction_degrees: parseFloat(row.wind_direction_degrees),
          pressure_hpa: parseFloat(row.pressure_hpa),
        },
      })),
    };

    return createResponse(200, response);
  } catch (error) {
    logger.error('Error fetching AOS data:', error);
    return createResponse(500, { 
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
};

// Statistics Handler (example for water levels)
export const waterLevelStatistics = async (
  event: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> => {
  try {
    // Validate API Key
    const apiKey = event.headers['X-API-Key'] || event.headers['x-api-key'];
    if (!validateApiKey(apiKey)) {
      return createResponse(401, { error: 'Invalid API key' });
    }

    // Get date parameter
    const dateParam = event.queryStringParameters?.date;
    if (!dateParam) {
      return createResponse(400, { 
        error: 'Date parameter is required (dd/mm/yyyy in Buddhist calendar)' 
      });
    }

    const date = parseBuddhistDate(dateParam);
    const startDate = new Date(date);
    startDate.setHours(0, 0, 0, 0);
    const endDate = new Date(date);
    endDate.setHours(23, 59, 59, 999);

    // Query statistics
    const query = `
      SELECT 
        sensor_id,
        sensor_name,
        zone,
        ST_X(location) as longitude,
        ST_Y(location) as latitude,
        COUNT(*) as count,
        MIN(water_level_m) as min,
        MAX(water_level_m) as max,
        AVG(water_level_m) as avg,
        STDDEV(water_level_m) as stddev
      FROM water_levels
      WHERE timestamp >= $1 AND timestamp <= $2
      GROUP BY sensor_id, sensor_name, zone, location
      ORDER BY sensor_id
    `;

    const result = await pool.query(query, [startDate, endDate]);
    
    const response = {
      data_type: 'water_level',
      request_date: dateParam,
      sensor_count: result.rows.length,
      sensors: result.rows.map(row => ({
        sensor_id: row.sensor_id,
        sensor_name: row.sensor_name,
        location: {
          longitude: row.longitude,
          latitude: row.latitude,
        },
        zone: row.zone,
        date_buddhist: dateParam,
        statistics: {
          count: parseInt(row.count),
          min: parseFloat(row.min),
          max: parseFloat(row.max),
          avg: parseFloat(row.avg),
          stddev: parseFloat(row.stddev),
        },
      })),
    };

    return createResponse(200, response);
  } catch (error) {
    logger.error('Error fetching water level statistics:', error);
    return createResponse(500, { 
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
};