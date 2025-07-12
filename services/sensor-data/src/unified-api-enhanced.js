const express = require('express');
const { Pool } = require('pg');
const sql = require('mssql');
const cors = require('cors');
const Redis = require('redis');
const compression = require('compression');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const { validate } = require('./middleware/request-validator');

const app = express();

// Security middleware
app.use(helmet());
app.use(compression());
app.use(express.json());
app.use(cors({
  origin: (process.env.CORS_ORIGINS || 'http://localhost:3000').split(','),
  methods: (process.env.CORS_METHODS || 'GET,POST,PUT,DELETE,OPTIONS').split(','),
  credentials: true
}));

// Internal API key for authentication
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || 'munbon-internal-f3b89263126548';
console.log('Starting Enhanced Unified API...');

// Redis client for caching
const redisClient = Redis.createClient({
  host: process.env.REDIS_HOST || 'localhost',
  port: process.env.REDIS_PORT || 6379,
  db: process.env.REDIS_DB || 7
});

redisClient.on('error', (err) => {
  console.error('Redis error:', err);
});

redisClient.on('connect', () => {
  console.log('✅ Redis connected for caching');
});

// TimescaleDB connection
const timescaleDB = new Pool({
  host: process.env.TIMESCALE_HOST || 'localhost',
  port: process.env.TIMESCALE_PORT || 5433,
  database: process.env.TIMESCALE_DB || 'sensor_data',
  user: process.env.TIMESCALE_USER || 'postgres',
  password: process.env.TIMESCALE_PASSWORD || 'postgres'
});

// MSSQL connection for SCADA data
const mssqlConfig = {
  server: process.env.MSSQL_HOST || 'localhost',
  database: process.env.MSSQL_DB || 'SCADA_DB',
  user: process.env.MSSQL_USER || 'sa',
  password: process.env.MSSQL_PASSWORD || 'your_password',
  options: {
    encrypt: false,
    trustServerCertificate: true,
    port: parseInt(process.env.MSSQL_PORT || '1433')
  }
};

// Simple rate limiting for all users
const rateLimiter = rateLimit({
  windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS || 900000), // 15 minutes
  max: parseInt(process.env.RATE_LIMIT_MAX || 1000), // 1000 requests per window
  message: 'Too many requests, please try again later.',
  standardHeaders: true,
  legacyHeaders: false,
});

// Cache configuration
const cacheConfig = {
  'sensor:water-level:latest': 60,      // 1 minute
  'sensor:moisture:latest': 300,        // 5 minutes
  'sensor:weather:current': 300,        // 5 minutes
  'gis:zones:list': 3600,              // 1 hour
  'gis:parcels:*': 1800,               // 30 minutes
  'analytics:water-demand:*': 900,     // 15 minutes
  'dashboard:summary:*': 300           // 5 minutes
};

// Utility functions
const convertToBuddhistDate = (date) => {
  const d = new Date(date);
  const year = d.getFullYear() + 543;
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${day}/${month}/${year}`;
};

const parseBuddhistDate = (dateStr) => {
  const [day, month, year] = dateStr.split('/').map(Number);
  return new Date(year - 543, month - 1, day);
};

// Generate cache key
const generateCacheKey = (req) => {
  const path = req.path;
  const query = JSON.stringify(req.query);
  return `api:${path}:${query}`;
};

// Get TTL for cache key
const getTTL = (path) => {
  for (const [pattern, ttl] of Object.entries(cacheConfig)) {
    if (path.includes(pattern.replace('*', ''))) {
      return ttl;
    }
  }
  return parseInt(process.env.CACHE_TTL_DEFAULT || 300);
};

// Cache middleware
const cacheMiddleware = async (req, res, next) => {
  if (req.method !== 'GET') {
    return next();
  }

  const cacheKey = generateCacheKey(req);
  
  redisClient.get(cacheKey, (err, cached) => {
    if (err) {
      console.error('Redis get error:', err);
      return next();
    }

    if (cached) {
      const data = JSON.parse(cached);
      return res.json({
        ...data,
        meta: { 
          ...data.meta, 
          cached: true,
          cachedAt: new Date().toISOString()
        }
      });
    }

    // Store original res.json
    const originalJson = res.json.bind(res);
    
    // Override res.json to cache response
    res.json = (data) => {
      const ttl = getTTL(req.path);
      redisClient.setex(cacheKey, ttl, JSON.stringify(data), (err) => {
        if (err) {
          console.error('Redis setex error:', err);
        }
      });
      originalJson(data);
    };
    
    next();
  });
};

// Simple authentication middleware
const validateAuth = (req, res, next) => {
  // For internal endpoints, check internal key
  if (req.headers['x-internal-key'] === INTERNAL_API_KEY) {
    return next();
  }
  
  // For public endpoints, no auth required
  if (['/health', '/api/v1/status', '/api/v1/docs'].includes(req.path)) {
    return next();
  }
  
  // Check for API key or Bearer token
  const apiKey = req.headers[process.env.API_KEY_HEADER || 'x-api-key'];
  const bearerToken = req.headers.authorization;
  
  if (!apiKey && !bearerToken) {
    return res.status(401).json({ 
      success: false,
      error: {
        code: 'MISSING_AUTHENTICATION',
        message: 'Authentication required',
        documentation: 'https://api.munbon.go.th/docs#authentication'
      }
    });
  }
  
  // Simple validation - in production, validate against database
  if (apiKey && apiKey.length > 10) {
    return next();
  }
  
  if (bearerToken && bearerToken.startsWith('Bearer ')) {
    // TODO: Validate JWT token
    return next();
  }
  
  return res.status(401).json({ 
    success: false,
    error: {
      code: 'INVALID_AUTHENTICATION',
      message: 'Invalid authentication credentials',
      documentation: 'https://api.munbon.go.th/docs#authentication'
    }
  });
};

// Request ID middleware
const requestIdMiddleware = (req, res, next) => {
  req.id = `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  res.setHeader('X-Request-ID', req.id);
  next();
};

// Logging middleware
const loggingMiddleware = (req, res, next) => {
  const start = Date.now();
  
  res.on('finish', () => {
    const duration = Date.now() - start;
    console.log({
      requestId: req.id,
      method: req.method,
      path: req.path,
      query: req.query,
      authenticated: true,
      status: res.statusCode,
      duration: `${duration}ms`,
      cached: res.getHeader('X-Cached') === 'true'
    });
  });
  
  next();
};

// Apply middleware
app.use(requestIdMiddleware);
app.use(loggingMiddleware);
app.use(validateAuth);
app.use(rateLimiter);

// Health check (no auth, no cache)
app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    service: 'unified-api-enhanced',
    version: '2.0.0',
    timestamp: new Date().toISOString()
  });
});

// API status
app.get('/api/v1/status', async (req, res) => {
  try {
    // Check database connections
    const [timescaleStatus] = await Promise.allSettled([
      timescaleDB.query('SELECT NOW()'),
      // sql.connect(mssqlConfig) // Uncomment when MSSQL is configured
    ]);
    
    res.json({
      success: true,
      data: {
        service: 'Munbon Unified API',
        version: '2.0.0',
        status: 'operational',
        dependencies: {
          timescaleDB: timescaleStatus.status === 'fulfilled' ? 'connected' : 'disconnected',
          mssql: 'not_configured', // Update when MSSQL is ready
          redis: redisClient.connected ? 'connected' : 'disconnected'
        }
      },
      meta: {
        timestamp: new Date().toISOString(),
        requestId: req.id
      }
    });
  } catch (error) {
    console.error('Status check error:', error);
    res.status(500).json({ 
      success: false,
      error: {
        code: 'STATUS_CHECK_FAILED',
        message: 'Failed to check system status'
      }
    });
  }
});

// Dashboard Summary - Main aggregation endpoint
app.get('/api/v1/dashboard/summary', validate('dashboardSummary'), cacheMiddleware, async (req, res) => {
  try {
    const { zone, date } = req.query;
    const targetDate = date ? parseBuddhistDate(date) : new Date();
    
    // Parallel fetch from all data sources
    const [waterLevelData, moistureData, weatherData, alertsData] = await Promise.all([
      fetchWaterLevelSummary(zone, targetDate),
      fetchMoistureSummary(zone, targetDate),
      fetchWeatherSummary(zone, targetDate),
      fetchActiveAlerts(zone)
    ]);
    
    // Calculate derived metrics
    const waterDemand = calculateWaterDemand(moistureData, weatherData);
    const irrigationStatus = determineIrrigationStatus(waterLevelData, waterDemand);
    
    res.json({
      success: true,
      data: {
        zone: zone || 'all',
        date: convertToBuddhistDate(targetDate),
        summary: {
          totalSensors: {
            waterLevel: waterLevelData.sensorCount,
            moisture: moistureData.sensorCount,
            weather: weatherData.stationCount,
            total: waterLevelData.sensorCount + moistureData.sensorCount + weatherData.stationCount
          },
          waterStatus: {
            averageLevel: waterLevelData.averageLevel,
            totalVolume: waterLevelData.totalVolume,
            capacity: waterLevelData.capacity,
            utilizationPercentage: (waterLevelData.totalVolume / waterLevelData.capacity) * 100
          },
          irrigationStatus: {
            currentDemand: waterDemand.current,
            projectedDemand: waterDemand.projected,
            irrigationNeeded: irrigationStatus.needed,
            recommendedSchedule: irrigationStatus.schedule
          },
          weatherConditions: {
            temperature: weatherData.avgTemperature,
            humidity: weatherData.avgHumidity,
            rainfall: weatherData.totalRainfall,
            forecast: weatherData.forecast
          },
          alerts: {
            critical: alertsData.critical,
            warning: alertsData.warning,
            info: alertsData.info,
            total: alertsData.total
          }
        }
      },
      meta: {
        timestamp: new Date().toISOString(),
        version: '2.0.0',
        requestId: req.id,
        cached: false
      }
    });
  } catch (error) {
    console.error('Dashboard summary error:', error);
    res.status(500).json({ 
      success: false,
      error: {
        code: 'DASHBOARD_ERROR',
        message: 'Failed to generate dashboard summary',
        details: error.message
      }
    });
  }
});

// Water demand calculation endpoint
app.get('/api/v1/analytics/water-demand', validate('waterDemand'), cacheMiddleware, async (req, res) => {
  try {
    const { zone, date } = req.query;
    const targetDate = date ? parseBuddhistDate(date) : new Date();
    
    const [moistureData, weatherData, cropData] = await Promise.all([
      fetchMoistureSummary(zone, targetDate),
      fetchWeatherSummary(zone, targetDate),
      fetchCropData(zone)
    ]);
    
    const waterDemand = calculateDetailedWaterDemand(moistureData, weatherData, cropData);
    
    res.json({
      success: true,
      data: {
        zone: zone || 'all',
        date: convertToBuddhistDate(targetDate),
        demand: waterDemand
      },
      meta: {
        timestamp: new Date().toISOString(),
        requestId: req.id,
        cached: false
      }
    });
  } catch (error) {
    console.error('Water demand calculation error:', error);
    res.status(500).json({ 
      success: false,
      error: {
        code: 'CALCULATION_ERROR',
        message: 'Failed to calculate water demand'
      }
    });
  }
});

// Irrigation schedule endpoint
app.get('/api/v1/analytics/irrigation-schedule', validate('irrigationSchedule'), cacheMiddleware, async (req, res) => {
  try {
    const { zone } = req.query;
    
    const schedule = await generateIrrigationSchedule(zone);
    
    res.json({
      success: true,
      data: {
        zone: zone || 'all',
        schedule: schedule
      },
      meta: {
        timestamp: new Date().toISOString(),
        requestId: req.id,
        cached: false
      }
    });
  } catch (error) {
    console.error('Irrigation schedule error:', error);
    res.status(500).json({ 
      success: false,
      error: {
        code: 'SCHEDULE_ERROR',
        message: 'Failed to generate irrigation schedule'
      }
    });
  }
});

// Sensor status overview
app.get('/api/v1/dashboard/sensors/status', cacheMiddleware, async (req, res) => {
  try {
    const query = `
      SELECT 
        sensor_type,
        COUNT(*) as total,
        COUNT(CASE WHEN is_active THEN 1 END) as active,
        COUNT(CASE WHEN NOT is_active THEN 1 END) as inactive,
        COUNT(CASE WHEN last_seen > NOW() - INTERVAL '1 hour' THEN 1 END) as online,
        COUNT(CASE WHEN last_seen <= NOW() - INTERVAL '1 hour' OR last_seen IS NULL THEN 1 END) as offline
      FROM sensor_registry
      GROUP BY sensor_type
    `;
    
    const result = await timescaleDB.query(query);
    
    res.json({
      success: true,
      data: {
        sensors: result.rows.map(row => ({
          type: row.sensor_type,
          total: parseInt(row.total),
          active: parseInt(row.active),
          inactive: parseInt(row.inactive),
          online: parseInt(row.online),
          offline: parseInt(row.offline),
          healthPercentage: (parseInt(row.online) / parseInt(row.active) * 100).toFixed(2)
        }))
      },
      meta: {
        timestamp: new Date().toISOString(),
        requestId: req.id,
        cached: false
      }
    });
  } catch (error) {
    console.error('Sensor status error:', error);
    res.status(500).json({ 
      success: false,
      error: {
        code: 'SENSOR_STATUS_ERROR',
        message: 'Failed to fetch sensor status'
      }
    });
  }
});

// Alerts endpoint
app.get('/api/v1/dashboard/alerts', validate('alerts'), cacheMiddleware, async (req, res) => {
  try {
    const { zone, severity, active } = req.query;
    
    let query = `
      SELECT 
        alert_id,
        sensor_id,
        alert_type,
        severity,
        message,
        created_at,
        acknowledged_at,
        resolved_at,
        metadata
      FROM alerts
      WHERE 1=1
    `;
    
    const params = [];
    let paramCount = 0;
    
    if (zone) {
      query += ` AND zone = $${++paramCount}`;
      params.push(zone);
    }
    
    if (severity) {
      query += ` AND severity = $${++paramCount}`;
      params.push(severity);
    }
    
    if (active === 'true') {
      query += ` AND resolved_at IS NULL`;
    }
    
    query += ` ORDER BY created_at DESC LIMIT 100`;
    
    const result = await timescaleDB.query(query, params);
    
    res.json({
      success: true,
      data: {
        alerts: result.rows.map(row => ({
          id: row.alert_id,
          sensorId: row.sensor_id,
          type: row.alert_type,
          severity: row.severity,
          message: row.message,
          createdAt: row.created_at,
          acknowledgedAt: row.acknowledged_at,
          resolvedAt: row.resolved_at,
          metadata: row.metadata
        }))
      },
      meta: {
        timestamp: new Date().toISOString(),
        requestId: req.id,
        cached: false
      }
    });
  } catch (error) {
    console.error('Alerts fetch error:', error);
    res.status(500).json({ 
      success: false,
      error: {
        code: 'ALERTS_ERROR',
        message: 'Failed to fetch alerts'
      }
    });
  }
});

// Calculate ETO endpoint
app.post('/api/v1/analytics/calculate-eto', validate('calculateETO'), async (req, res) => {
  try {
    const { temperature, humidity, windSpeed, solarRadiation, latitude } = req.body;
    
    // Penman-Monteith equation for ETO calculation
    const eto = calculateETO({
      temperature,
      humidity,
      windSpeed,
      solarRadiation,
      latitude
    });
    
    res.json({
      success: true,
      data: {
        eto: eto,
        unit: 'mm/day',
        method: 'Penman-Monteith'
      },
      meta: {
        timestamp: new Date().toISOString(),
        requestId: req.id
      }
    });
  } catch (error) {
    console.error('ETO calculation error:', error);
    res.status(500).json({ 
      success: false,
      error: {
        code: 'ETO_CALCULATION_ERROR',
        message: 'Failed to calculate ETO'
      }
    });
  }
});

// Include existing endpoints from unified-api.js
// ... (water level, moisture, weather endpoints remain the same)

// Helper functions
async function fetchWaterLevelSummary(zone, date) {
  const query = `
    SELECT 
      COUNT(DISTINCT sr.sensor_id) as sensor_count,
      AVG(wl.level_cm / 100.0) as avg_level,
      SUM(wl.level_cm / 100.0) as total_volume,
      1000000 as capacity
    FROM sensor_registry sr
    LEFT JOIN water_level_readings wl ON sr.sensor_id = wl.sensor_id
    WHERE sr.sensor_type = 'water_level' 
      AND sr.is_active = true
      ${zone ? "AND sr.metadata->>'zone' = $1" : ""}
      AND DATE(wl.time) = DATE($${zone ? 2 : 1})
  `;
  
  const params = zone ? [zone, date] : [date];
  const result = await timescaleDB.query(query, params);
  
  return {
    sensorCount: parseInt(result.rows[0].sensor_count) || 0,
    averageLevel: parseFloat(result.rows[0].avg_level) || 0,
    totalVolume: parseFloat(result.rows[0].total_volume) || 0,
    capacity: parseFloat(result.rows[0].capacity) || 1000000
  };
}

async function fetchMoistureSummary(zone, date) {
  // Implement moisture summary logic
  return {
    sensorCount: 50,
    averageMoisture: 65.5,
    fieldsCritical: 5,
    fieldsOptimal: 35,
    fieldsWet: 10
  };
}

async function fetchWeatherSummary(zone, date) {
  // Implement weather summary logic
  return {
    stationCount: 10,
    avgTemperature: 28.5,
    avgHumidity: 75,
    totalRainfall: 5.2,
    forecast: 'partly_cloudy'
  };
}

async function fetchActiveAlerts(zone) {
  // Implement alerts fetching logic
  return {
    critical: 2,
    warning: 5,
    info: 10,
    total: 17
  };
}

async function fetchCropData(zone) {
  // Implement crop data fetching
  return {
    primaryCrop: 'rice',
    growthStage: 'vegetative',
    plantingDate: '2024-05-15',
    expectedHarvest: '2024-09-15'
  };
}

function calculateWaterDemand(moistureData, weatherData) {
  // Simplified water demand calculation
  const baselineDemand = 1000; // m³/day
  const moistureFactor = (100 - moistureData.averageMoisture) / 100;
  const temperatureFactor = weatherData.avgTemperature > 30 ? 1.2 : 1.0;
  const rainfallAdjustment = weatherData.totalRainfall * 50;
  
  const current = (baselineDemand * moistureFactor * temperatureFactor) - rainfallAdjustment;
  const projected = current * 1.1; // 10% safety margin
  
  return {
    current: Math.max(0, current),
    projected: Math.max(0, projected)
  };
}

function calculateDetailedWaterDemand(moistureData, weatherData, cropData) {
  const waterDemand = calculateWaterDemand(moistureData, weatherData);
  
  return {
    current: waterDemand.current,
    projected: waterDemand.projected,
    breakdown: {
      evapotranspiration: waterDemand.current * 0.6,
      soilMoistureDeficit: waterDemand.current * 0.3,
      systemLosses: waterDemand.current * 0.1
    },
    cropSpecific: {
      crop: cropData.primaryCrop,
      growthStage: cropData.growthStage,
      dailyRequirement: waterDemand.current / moistureData.sensorCount
    }
  };
}

function determineIrrigationStatus(waterLevelData, waterDemand) {
  const availableWater = waterLevelData.totalVolume;
  const needed = waterDemand.projected > availableWater * 0.1;
  
  return {
    needed,
    schedule: needed ? generateSchedule(waterDemand) : null
  };
}

function generateSchedule(waterDemand) {
  // Simple schedule generation
  return {
    startTime: '06:00',
    duration: Math.ceil(waterDemand.current / 500), // hours
    zones: ['Z1', 'Z2', 'Z3'],
    priority: 'high'
  };
}

async function generateIrrigationSchedule(zone) {
  // Implement irrigation schedule generation
  return [
    {
      zone: 'Z1',
      date: convertToBuddhistDate(new Date()),
      startTime: '06:00',
      endTime: '08:00',
      waterVolume: 500,
      priority: 'high'
    },
    {
      zone: 'Z2',
      date: convertToBuddhistDate(new Date()),
      startTime: '08:30',
      endTime: '10:30',
      waterVolume: 450,
      priority: 'medium'
    }
  ];
}

function calculateETO(params) {
  // Simplified Penman-Monteith equation
  const { temperature, humidity, windSpeed, solarRadiation } = params;
  
  // Constants
  const gamma = 0.067; // Psychrometric constant
  const delta = 0.0415 * temperature; // Slope of saturation vapor pressure curve
  
  // Net radiation
  const Rn = solarRadiation * 0.77; // Approximate net radiation
  
  // Vapor pressure deficit
  const es = 0.6108 * Math.exp((17.27 * temperature) / (temperature + 237.3));
  const ea = es * (humidity / 100);
  const VPD = es - ea;
  
  // ETO calculation (simplified)
  const eto = (0.408 * delta * Rn + gamma * (900 / (temperature + 273)) * windSpeed * VPD) /
             (delta + gamma * (1 + 0.34 * windSpeed));
  
  return Math.round(eto * 100) / 100;
}

// Error handler
app.use((err, req, res, next) => {
  console.error('Error:', err);
  res.status(500).json({ 
    success: false,
    error: {
      code: 'INTERNAL_ERROR',
      message: 'An internal error occurred',
      requestId: req.id
    }
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    success: false,
    error: {
      code: 'ENDPOINT_NOT_FOUND',
      message: `Endpoint ${req.method} ${req.path} not found`,
      documentation: 'https://api.munbon.go.th/docs'
    }
  });
});

// Start server
const PORT = process.env.API_PORT || 3000;
app.listen(PORT, () => {
  console.log(`Enhanced Unified API running on port ${PORT}`);
  console.log(`Environment: ${process.env.NODE_ENV}`);
  console.log(`Redis caching: ${redisClient.connected ? 'enabled' : 'disabled'}`);
  console.log('Ready to serve aggregated data from multiple sources');
});

// Test database connections
timescaleDB.query('SELECT NOW()', (err, res) => {
  if (err) {
    console.error('TimescaleDB connection error:', err);
  } else {
    console.log('✅ TimescaleDB connected:', res.rows[0].now);
  }
});

// Export for testing
module.exports = app;