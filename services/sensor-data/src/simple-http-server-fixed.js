const express = require('express');
const { Pool } = require('pg');
const pino = require('pino');
require('dotenv').config();

const app = express();

// Configure body parsers - order matters!
// First, parse text/plain as text
app.use(express.text({ type: 'text/plain', limit: '10mb' }));
// Then parse application/json
app.use(express.json({ limit: '10mb' }));

const logger = pino({
  transport: {
    target: 'pino-pretty',
    options: { colorize: true }
  }
});

// Database connection to EC2
const dbPool = new Pool({
  host: process.env.DB_HOST || '43.208.201.191',
  port: parseInt(process.env.DB_PORT || '5432'),
  database: process.env.DB_NAME || 'sensor_data',
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || '__ROTATED_DB_PASSWORD__',
  max: 10
});

// Middleware to log all incoming requests
app.use((req, res, next) => {
  logger.info({
    method: req.method,
    url: req.url,
    headers: req.headers,
    bodyType: typeof req.body,
    bodyLength: req.body ? (typeof req.body === 'string' ? req.body.length : JSON.stringify(req.body).length) : 0
  }, 'Incoming request');
  next();
});

// Simple HTTP endpoint for moisture data - writes directly to DB
app.post('/api/sensor-data/moisture/:token', async (req, res) => {
  try {
    const { token } = req.params;
    const contentType = req.headers['content-type'] || '';
    let data;
    
    // Handle different content types
    if (contentType.includes('text/plain')) {
      // Parse text body as JSON
      try {
        if (typeof req.body === 'string') {
          data = JSON.parse(req.body);
          logger.info({ 
            contentType,
            originalBodyType: typeof req.body,
            parsedSuccessfully: true 
          }, 'Parsed text/plain as JSON');
        } else {
          // Shouldn't happen with text/plain, but handle it
          data = req.body;
        }
      } catch (parseError) {
        logger.error({ 
          parseError: parseError.message, 
          body: req.body,
          contentType
        }, 'Failed to parse text/plain body as JSON');
        res.status(400).json({
          status: 'error',
          message: 'Invalid JSON in request body',
          error: parseError.message
        });
        return;
      }
    } else {
      // For application/json or other types, use body as-is
      data = req.body;
    }
    
    logger.info({ 
      token, 
      contentType,
      dataType: typeof data,
      data 
    }, 'Received moisture data via HTTP');
    
    // Validate data
    if (!data || typeof data !== 'object') {
      res.status(400).json({
        status: 'error',
        message: 'Invalid data format - expected JSON object'
      });
      return;
    }
    
    // Extract sensor data
    const gatewayId = data.gw_id || data.gateway_id || data.sensor_id;
    const sensors = data.sensor || [];
    const timestamp = new Date();
    const lat = parseFloat(data.gps_lat || data.latitude) || null;
    const lng = parseFloat(data.gps_lng || data.longitude) || null;
    
    // Insert data directly to database using correct column names
    for (const sensor of sensors) {
      // Skip sensors with invalid sensor_id formats (like timestamps)
      if (!sensor.sensor_id || sensor.sensor_id.includes(':')) {
        logger.warn({ 
          sensor_id: sensor.sensor_id,
          gateway_id: gatewayId 
        }, 'Skipping sensor with invalid sensor_id format');
        continue;
      }
      
      const query = `
        INSERT INTO moisture_readings (
          time,
          sensor_id,
          location_lat,
          location_lng,
          moisture_surface_pct,
          moisture_deep_pct,
          temp_surface_c,
          temp_deep_c,
          ambient_humidity_pct,
          ambient_temp_c,
          voltage,
          flood_status,
          quality_score
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
      `;
      
      // Helper function to safely parse numeric values with validation
      const parseNumeric = (value, min = null, max = null) => {
        if (value === null || value === undefined || value === '') return null;
        const parsed = parseFloat(value);
        if (isNaN(parsed)) return null;
        if (min !== null && parsed < min) return null;
        if (max !== null && parsed > max) return null;
        return parsed;
      };
      
      try {
        // Prepare values with proper validation
        const moistureSurface = parseNumeric(sensor.humid_hi, 0, 100);
        const moistureDeep = parseNumeric(sensor.humid_low, 0, 100);
        const tempSurface = parseNumeric(sensor.temp_hi, -50, 100);
        const tempDeep = parseNumeric(sensor.temp_low, -50, 100);
        const ambientHumidity = parseNumeric(sensor.amb_humid, 0, 100);
        const ambientTemp = parseNumeric(sensor.amb_temp, -50, 100);
        
        // Battery voltage: convert from 400-range to voltage (e.g., 408 -> 4.08V)
        // But cap at 9.99 if database has NUMERIC(3,2) constraint
        let voltage = null;
        if (sensor.sensor_batt) {
          const battValue = parseNumeric(sensor.sensor_batt);
          if (battValue) {
            voltage = Math.min(battValue / 100, 9.99);
          }
        }
        
        await dbPool.query(query, [
          timestamp,
          gatewayId.padStart(4, '0') + '-' + (sensor.sensor_id || '').padStart(4, '0'),
          lat,
          lng,
          moistureSurface,
          moistureDeep,
          tempSurface,
          tempDeep,
          ambientHumidity,
          ambientTemp,
          voltage,
          sensor.flood === 'yes',
          0.95
        ]);
      } catch (dbError) {
        logger.error({ 
          error: dbError.message,
          sensor_id: sensor.sensor_id,
          gateway_id: gatewayId,
          values: {
            humid_hi: sensor.humid_hi,
            humid_low: sensor.humid_low,
            temp_hi: sensor.temp_hi,
            temp_low: sensor.temp_low,
            sensor_batt: sensor.sensor_batt
          }
        }, 'Failed to insert sensor data');
      }
    }
    
    logger.info({ 
      token, 
      gateway_id: gatewayId,
      sensor_count: sensors.length,
      sample_sensor: sensors[0] ? {
        sensor_id: sensors[0].sensor_id,
        humid_hi: sensors[0].humid_hi,
        humid_low: sensors[0].humid_low,
        temp_hi: sensors[0].temp_hi,
        temp_low: sensors[0].temp_low,
        sensor_batt: sensors[0].sensor_batt
      } : null
    }, 'Wrote to database successfully');
    
    res.status(200).json({ status: 'success', message: 'Data received and saved' });
  } catch (error) {
    logger.error({ error: error.message, stack: error.stack }, 'Failed to process moisture data');
    res.status(500).json({ status: 'error', message: 'Internal server error' });
  }
});

// Health check
app.get('/health', async (req, res) => {
  try {
    // Test database connection
    await dbPool.query('SELECT 1');
    res.status(200).json({ 
      status: 'healthy',
      service: 'moisture-http-endpoint',
      database: 'connected',
      timestamp: new Date().toISOString(),
      ec2_ip: '43.208.201.191',
      features: {
        textPlainSupport: true,
        jsonSupport: true
      }
    });
  } catch (error) {
    res.status(503).json({ 
      status: 'unhealthy',
      service: 'moisture-http-endpoint',
      database: 'disconnected',
      error: error.message
    });
  }
});

// Root endpoint for testing
app.get('/', (req, res) => {
  res.status(200).json({ 
    service: 'Munbon Moisture Data Ingestion',
    version: '1.1.0',
    features: {
      acceptsTextPlain: true,
      acceptsJson: true
    },
    endpoints: {
      health: '/health',
      moisture: '/api/sensor-data/moisture/:token'
    },
    database: {
      host: process.env.DB_HOST || '43.208.201.191',
      port: process.env.DB_PORT || '5432',
      database: process.env.DB_NAME || 'sensor_data'
    }
  });
});

const PORT = parseInt(process.env.HTTP_PORT || '8080');

app.listen(PORT, '0.0.0.0', () => {
  logger.info(`🚀 Moisture HTTP server (v1.1.0) listening on port ${PORT}`);
  logger.info(`📡 Moisture endpoint: http://43.208.201.191:${PORT}/api/sensor-data/moisture/munbon-m2m-moisture`);
  logger.info(`🏥 Health check: http://43.208.201.191:${PORT}/health`);
  logger.info(`💾 Database: ${process.env.DB_HOST || '43.208.201.191'}:${process.env.DB_PORT || '5432'}`);
  logger.info(`✅ Accepts Content-Type: text/plain and application/json`);
});