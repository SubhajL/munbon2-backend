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
  password: process.env.DB_PASSWORD || 'P@ssw0rd123!',
  max: 10
});

// Statistics tracking
const stats = {
  moisture: { received: 0, processed: 0, errors: 0 },
  waterLevel: { received: 0, processed: 0, errors: 0 },
  aos: { received: 0, processed: 0, errors: 0 }
};

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

// Helper function to parse body based on content type
const parseRequestBody = (req) => {
  const contentType = req.headers['content-type'] || '';
  let data;
  
  if (contentType.includes('text/plain')) {
    try {
      if (typeof req.body === 'string') {
        data = JSON.parse(req.body);
      } else {
        data = req.body;
      }
    } catch (parseError) {
      throw new Error(`Invalid JSON in text/plain body: ${parseError.message}`);
    }
  } else {
    data = req.body;
  }
  
  return data;
};

// 1. MOISTURE DATA ENDPOINT
app.post('/api/sensor-data/moisture/:token', async (req, res) => {
  stats.moisture.received++;
  
  try {
    const { token } = req.params;
    const data = parseRequestBody(req);

    // Import hardened parsers lazily to avoid top-level require re-ordering
    const {
      sanitizeMoistureSensor,
      formatMoistureSensorId,
      parseNumeric,
    } = require('./utils/moisture-parse');
    
    logger.info({ 
      token, 
      contentType: req.headers['content-type'],
      dataType: typeof data,
      data 
    }, 'Received moisture data via HTTP');
    
    // Validate data
    if (!data || typeof data !== 'object') {
      stats.moisture.errors++;
      res.status(400).json({
        status: 'error',
        message: 'Invalid data format - expected JSON object'
      });
      return;
    }
    
    // Extract sensor data
    const gatewayId = data.gw_id || data.gateway_id || data.sensor_id;
    const sensors = Array.isArray(data.sensor) ? data.sensor : [];
    const timestamp = new Date();
    const lat = parseNumeric(data.gps_lat ?? data.latitude, -90, 90);
    const lng = parseNumeric(data.gps_lng ?? data.longitude, -180, 180);
    
    // Insert data directly to database using correct column names
    for (const sensor of sensors) {
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

      const s = sanitizeMoistureSensor(sensor);
      const sensorId = formatMoistureSensorId(gatewayId, sensor?.sensor_id);

      await dbPool.query(query, [
        timestamp,
        sensorId,
        lat ?? null,
        lng ?? null,
        s.moistureSurfacePct,
        s.moistureDeepPct,
        s.tempSurfaceC,
        s.tempDeepC,
        s.ambientHumidityPct,
        s.ambientTempC,
        s.voltage,
        s.floodStatus,
        0.95
      ]);
    }
    
    stats.moisture.processed++;
    logger.info({ 
      token, 
      gateway_id: gatewayId,
      sensor_count: sensors.length
    }, 'Moisture data saved to database');
    
    res.status(200).json({ status: 'success', message: 'Data received and saved' });
  } catch (error) {
    stats.moisture.errors++;
    logger.error({ error: error.message, stack: error.stack }, 'Failed to process moisture data');
    res.status(500).json({ status: 'error', message: 'Internal server error' });
  }
});

// 2. WATER LEVEL DATA ENDPOINT
app.post('/api/sensor-data/water-level/:token', async (req, res) => {
  stats.waterLevel.received++;
  
  try {
    const { token } = req.params;
    const data = parseRequestBody(req);
    
    logger.info({ 
      token, 
      contentType: req.headers['content-type'],
      dataType: typeof data,
      data 
    }, 'Received water level data via HTTP');
    
    // Validate data
    if (!data || typeof data !== 'object') {
      stats.waterLevel.errors++;
      res.status(400).json({
        status: 'error',
        message: 'Invalid data format - expected JSON object'
      });
      return;
    }
    
    // Extract water level data
    const sensorId = data.sensorId || data.sensor_id;
    const timestamp = data.timestamp ? new Date(data.timestamp) : new Date();
    const levelData = data.data || data;
    const location = data.location || {};
    
    // Insert into water_level_readings table
    const query = `
      INSERT INTO water_level_readings (
        time,
        sensor_id,
        location_lat,
        location_lng,
        level_cm,
        voltage,
        rssi,
        mac_address,
        quality_score
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    `;
    
    await dbPool.query(query, [
      timestamp,
      sensorId,
      location.lat || null,
      location.lng || null,
      levelData.level || null,
      levelData.voltage || null,
      levelData.RSSI || null,
      levelData.macAddress || null,
      1.0
    ]);
    
    stats.waterLevel.processed++;
    logger.info({ 
      token, 
      sensor_id: sensorId,
      level: levelData.level
    }, 'Water level data saved to database');
    
    res.status(200).json({ status: 'success', message: 'Data received and saved' });
  } catch (error) {
    stats.waterLevel.errors++;
    logger.error({ error: error.message, stack: error.stack }, 'Failed to process water level data');
    res.status(500).json({ status: 'error', message: 'Internal server error' });
  }
});

// 3. AOS WEATHER DATA ENDPOINT
app.post('/api/sensor-data/aos/:token', async (req, res) => {
  stats.aos.received++;
  
  try {
    const { token } = req.params;
    const data = parseRequestBody(req);
    
    logger.info({ 
      token, 
      contentType: req.headers['content-type'],
      dataType: typeof data,
      data 
    }, 'Received AOS weather data via HTTP');
    
    // Validate data
    if (!data || typeof data !== 'object') {
      stats.aos.errors++;
      res.status(400).json({
        status: 'error',
        message: 'Invalid data format - expected JSON object'
      });
      return;
    }
    
    // Extract AOS data
    const stationId = data.station_id || data.stationId;
    const timestamp = data.timestamp ? new Date(data.timestamp) : new Date();
    const location = data.location || {};
    const readings = data.readings || data.data || data;
    
    // Insert into aos_weather_data table
    const query = `
      INSERT INTO aos_weather_data (
        time,
        station_id,
        location_lat,
        location_lng,
        rainfall_mm,
        temperature_c,
        humidity_pct,
        wind_speed_ms,
        wind_direction_deg,
        pressure_hpa,
        solar_radiation_wm2,
        evapotranspiration_mm,
        quality_score
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
    `;
    
    await dbPool.query(query, [
      timestamp,
      stationId,
      location.lat || location.latitude || null,
      location.lng || location.longitude || null,
      readings.rainfall || readings.rainfall_mm || 0,
      readings.temperature || readings.temperature_celsius || null,
      readings.humidity || readings.humidity_percentage || null,
      readings.wind_speed || readings.wind_speed_ms || null,
      readings.wind_direction || readings.wind_direction_degrees || null,
      readings.pressure || readings.pressure_hpa || null,
      readings.solar_radiation || readings.solar_radiation_wm2 || null,
      readings.evapotranspiration || readings.evapotranspiration_mm || null,
      1.0
    ]);
    
    stats.aos.processed++;
    logger.info({ 
      token, 
      station_id: stationId,
      temperature: readings.temperature,
      rainfall: readings.rainfall
    }, 'AOS weather data saved to database');
    
    res.status(200).json({ status: 'success', message: 'Data received and saved' });
  } catch (error) {
    stats.aos.errors++;
    logger.error({ error: error.message, stack: error.stack }, 'Failed to process AOS data');
    res.status(500).json({ status: 'error', message: 'Internal server error' });
  }
});

// Statistics endpoint
app.get('/api/stats', (req, res) => {
  res.status(200).json({
    service: 'Unified Sensor Data Ingestion',
    version: '2.0.0',
    uptime: process.uptime(),
    timestamp: new Date().toISOString(),
    statistics: stats
  });
});

// Health check
app.get('/health', async (req, res) => {
  try {
    // Test database connection
    await dbPool.query('SELECT 1');
    res.status(200).json({ 
      status: 'healthy',
      service: 'unified-sensor-endpoint',
      database: 'connected',
      timestamp: new Date().toISOString(),
      ec2_ip: '43.208.201.191',
      features: {
        textPlainSupport: true,
        jsonSupport: true,
        moistureEndpoint: true,
        waterLevelEndpoint: true,
        aosEndpoint: true
      }
    });
  } catch (error) {
    res.status(503).json({ 
      status: 'unhealthy',
      service: 'unified-sensor-endpoint',
      database: 'disconnected',
      error: error.message
    });
  }
});

// Root endpoint for testing
app.get('/', (req, res) => {
  res.status(200).json({ 
    service: 'Munbon Unified Sensor Data Ingestion',
    version: '2.0.0',
    features: {
      acceptsTextPlain: true,
      acceptsJson: true
    },
    endpoints: {
      health: '/health',
      stats: '/api/stats',
      moisture: '/api/sensor-data/moisture/:token',
      waterLevel: '/api/sensor-data/water-level/:token',
      aos: '/api/sensor-data/aos/:token'
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
  logger.info(`🚀 Unified Sensor HTTP server (v2.0.0) listening on port ${PORT}`);
  logger.info(`📡 Moisture endpoint: http://43.208.201.191:${PORT}/api/sensor-data/moisture/:token`);
  logger.info(`💧 Water Level endpoint: http://43.208.201.191:${PORT}/api/sensor-data/water-level/:token`);
  logger.info(`🌤️  AOS Weather endpoint: http://43.208.201.191:${PORT}/api/sensor-data/aos/:token`);
  logger.info(`📊 Statistics: http://43.208.201.191:${PORT}/api/stats`);
  logger.info(`🏥 Health check: http://43.208.201.191:${PORT}/health`);
  logger.info(`💾 Database: ${process.env.DB_HOST || '43.208.201.191'}:${process.env.DB_PORT || '5432'}`);
  logger.info(`✅ Accepts Content-Type: text/plain and application/json`);
});