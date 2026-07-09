const express = require('express');
const { Pool } = require('pg');
const sql = require('mssql');
const moment = require('moment');
require('dotenv').config();

const app = express();

// PostgreSQL connection for TimescaleDB (water level & moisture)
const pgPool = new Pool({
  host: process.env.DB_HOST || '43.208.201.191',
  port: parseInt(process.env.DB_PORT || '5432'),
  database: process.env.DB_NAME || 'sensor_data',
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || (() => { throw new Error('DB_PASSWORD env var is required (hardcoded default removed; SEC remediation)'); })(),
  max: 10
});

// MSSQL connection for SCADA database (AOS data)
const mssqlConfig = {
  user: process.env.MSSQL_USER || 'sa',
  password: process.env.MSSQL_PASSWORD || 'P@ssw0rd',
  server: process.env.MSSQL_SERVER || 'moonup.hopto.org',
  database: process.env.MSSQL_DATABASE || 'db_scada',
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

// Valid API Keys (matching External API V2.0 spec)
const VALID_API_KEYS = {
  'rid-ms-prod-key1': 'RID Main System',
  'tmd-weather-key2': 'Thai Meteorological Department',
  'university-key3': 'University Research'
};

// Active water level sensors (updated based on actual data)
const ACTIVE_WATER_LEVEL_SENSORS = [
  'AWD-B89D', 'AWD-6D47', 'AWD-A4F8',
  'AWD-B75A', 'AWD-B6B5', 'AWD-B8A4', 
  'AWD-B33B', 'AWD-B7E6', 'AWD-B9BE'
];

// API Key authentication middleware
const authenticateApiKey = (req, res, next) => {
  const apiKey = req.headers['x-api-key'];
  
  if (!apiKey || !VALID_API_KEYS[apiKey]) {
    return res.status(401).json({ error: 'Invalid API key' });
  }
  
  req.apiKeyOwner = VALID_API_KEYS[apiKey];
  next();
};

// Helper function to convert to Buddhist calendar
const toBuddhistDate = (date) => {
  const m = moment(date);
  const buddhistYear = m.year() + 543;
  return m.format(`DD/MM/${buddhistYear}`);
};

// Helper function to parse Buddhist date to JS Date
const fromBuddhistDate = (buddhistDateStr) => {
  const [day, month, yearBE] = buddhistDateStr.split('/');
  const yearCE = parseInt(yearBE) - 543;
  return new Date(yearCE, parseInt(month) - 1, parseInt(day));
};

// Initialize MSSQL connection pool
let mssqlPool = null;

async function getMssqlPool() {
  if (!mssqlPool) {
    try {
      mssqlPool = await sql.connect(mssqlConfig);
      console.log('Connected to MSSQL SCADA database');
    } catch (err) {
      console.error('MSSQL connection error:', err);
      throw err;
    }
  }
  return mssqlPool;
}

// ====================
// WATER LEVEL ENDPOINTS (TimescaleDB)
// ====================

// GET /public/water-levels/latest
app.get('/api/v1/public/water-levels/latest', authenticateApiKey, async (req, res) => {
  try {
    const query = `
      SELECT DISTINCT ON (sensor_id) 
        time, sensor_id, level_cm, voltage, rssi, 
        location_lat, location_lng, quality_score
      FROM water_level_readings
      WHERE sensor_id = ANY($1)
        AND time > (NOW() AT TIME ZONE 'UTC') - INTERVAL '24 hours'
      ORDER BY sensor_id, time DESC
    `;
    
    const result = await pgPool.query(query, [ACTIVE_WATER_LEVEL_SENSORS]);
    
    const response = {
      data_type: "water_level",
      request_time: new Date().toISOString(),
      request_time_buddhist: toBuddhistDate(new Date()),
      sensor_count: result.rows.length,
      sensors: result.rows.map(row => ({
        sensor_id: row.sensor_id,
        sensor_name: row.sensor_id,
        location: {
          latitude: parseFloat(row.location_lat) || 0,
          longitude: parseFloat(row.location_lng) || 0
        },
        zone: "Zone1",
        latest_reading: {
          timestamp: row.time.toISOString(),
          timestamp_buddhist: toBuddhistDate(row.time),
          water_level_m: row.level_cm ? (row.level_cm / 100).toFixed(2) : 0,
          flow_rate_m3s: 0,
          quality: Math.round((row.quality_score || 1) * 100)
        }
      }))
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching latest water levels:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

// GET /public/water-levels/timeseries
app.get('/api/v1/public/water-levels/timeseries', authenticateApiKey, async (req, res) => {
  try {
    const { date } = req.query;
    
    if (!date) {
      return res.status(400).json({ error: 'Date parameter required' });
    }
    
    const targetDate = fromBuddhistDate(date);
    const startDate = new Date(targetDate);
    startDate.setHours(0, 0, 0, 0);
    const endDate = new Date(targetDate);
    endDate.setHours(23, 59, 59, 999);
    
    const query = `
      SELECT time, sensor_id, level_cm, voltage, rssi, 
             location_lat, location_lng, quality_score
      FROM water_level_readings
      WHERE sensor_id = ANY($1)
        AND time >= $2 AND time <= $3
      ORDER BY sensor_id, time ASC
    `;
    
    const result = await pgPool.query(query, [ACTIVE_WATER_LEVEL_SENSORS, startDate, endDate]);
    
    // Group by sensor_id
    const sensorData = {};
    result.rows.forEach(row => {
      if (!sensorData[row.sensor_id]) {
        sensorData[row.sensor_id] = {
          sensor_id: row.sensor_id,
          sensor_name: row.sensor_id,
          location: {
            latitude: parseFloat(row.location_lat) || 0,
            longitude: parseFloat(row.location_lng) || 0
          },
          zone: "Zone1",
          date_buddhist: date,
          readings: []
        };
      }
      
      sensorData[row.sensor_id].readings.push({
        timestamp: row.time.toISOString(),
        water_level_m: row.level_cm ? (row.level_cm / 100).toFixed(2) : 0,
        flow_rate_m3s: 0,
        quality: Math.round((row.quality_score || 1) * 100)
      });
    });
    
    const response = {
      data_type: "water_level",
      request_date: date,
      sensor_count: Object.keys(sensorData).length,
      sensors: Object.values(sensorData)
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching water level timeseries:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

// GET /public/water-levels/statistics
app.get('/api/v1/public/water-levels/statistics', authenticateApiKey, async (req, res) => {
  try {
    const { date } = req.query;
    
    if (!date) {
      return res.status(400).json({ error: 'Date parameter required' });
    }
    
    const targetDate = fromBuddhistDate(date);
    const startDate = new Date(targetDate);
    startDate.setHours(0, 0, 0, 0);
    const endDate = new Date(targetDate);
    endDate.setHours(23, 59, 59, 999);
    
    const query = `
      SELECT 
        sensor_id,
        COUNT(*) as count,
        MIN(level_cm/100.0) as min_level,
        MAX(level_cm/100.0) as max_level,
        AVG(level_cm/100.0) as avg_level,
        STDDEV(level_cm/100.0) as stddev_level,
        MIN(location_lat) as lat,
        MIN(location_lng) as lng
      FROM water_level_readings
      WHERE sensor_id = ANY($1)
        AND time >= $2 AND time <= $3
      GROUP BY sensor_id
    `;
    
    const result = await pgPool.query(query, [ACTIVE_WATER_LEVEL_SENSORS, startDate, endDate]);
    
    const response = {
      data_type: "water_level",
      request_date: date,
      sensor_count: result.rows.length,
      sensors: result.rows.map(row => ({
        sensor_id: row.sensor_id,
        sensor_name: row.sensor_id,
        location: {
          latitude: parseFloat(row.lat) || 0,
          longitude: parseFloat(row.lng) || 0
        },
        zone: "Zone1",
        date_buddhist: date,
        statistics: {
          count: parseInt(row.count),
          min: parseFloat(row.min_level).toFixed(2),
          max: parseFloat(row.max_level).toFixed(2),
          avg: parseFloat(row.avg_level).toFixed(2),
          stddev: parseFloat(row.stddev_level || 0).toFixed(2)
        }
      }))
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching water level statistics:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

// ====================
// MOISTURE ENDPOINTS (TimescaleDB)
// ====================

// GET /public/moisture/latest
app.get('/api/v1/public/moisture/latest', authenticateApiKey, async (req, res) => {
  try {
    const query = `
      SELECT DISTINCT ON (sensor_id) 
        time, sensor_id, moisture_surface_pct, moisture_deep_pct,
        temp_surface_c, temp_deep_c, location_lat, location_lng, quality_score
      FROM moisture_readings
      WHERE time > NOW() - INTERVAL '24 hours'
      ORDER BY sensor_id, time DESC
      LIMIT 10
    `;
    
    const result = await pgPool.query(query);
    
    const response = {
      data_type: "moisture",
      request_time: new Date().toISOString(),
      request_time_buddhist: toBuddhistDate(new Date()),
      sensor_count: result.rows.length,
      sensors: result.rows.map((row, index) => ({
        sensor_id: row.sensor_id,
        sensor_name: `Moisture Sensor ${index + 1}`,
        location: {
          latitude: parseFloat(row.location_lat) || 0,
          longitude: parseFloat(row.location_lng) || 0
        },
        zone: "Zone1",
        latest_reading: {
          timestamp: row.time.toISOString(),
          timestamp_buddhist: toBuddhistDate(row.time),
          moisture_percentage: parseFloat(row.moisture_surface_pct) || 0,
          temperature_celsius: parseFloat(row.temp_surface_c) || 0,
          quality: Math.round((row.quality_score || 1) * 100)
        }
      }))
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching latest moisture:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

// GET /public/moisture/timeseries
app.get('/api/v1/public/moisture/timeseries', authenticateApiKey, async (req, res) => {
  try {
    const { date } = req.query;
    
    if (!date) {
      return res.status(400).json({ error: 'Date parameter required' });
    }
    
    const targetDate = fromBuddhistDate(date);
    const startDate = new Date(targetDate);
    startDate.setHours(0, 0, 0, 0);
    const endDate = new Date(targetDate);
    endDate.setHours(23, 59, 59, 999);
    
    const query = `
      SELECT time, sensor_id, moisture_surface_pct, moisture_deep_pct,
             temp_surface_c, temp_deep_c, location_lat, location_lng, quality_score
      FROM moisture_readings
      WHERE time >= $1 AND time <= $2
      ORDER BY sensor_id, time ASC
    `;
    
    const result = await pgPool.query(query, [startDate, endDate]);
    
    // Group by sensor_id
    const sensorData = {};
    result.rows.forEach((row, index) => {
      if (!sensorData[row.sensor_id]) {
        sensorData[row.sensor_id] = {
          sensor_id: row.sensor_id,
          sensor_name: `Moisture Sensor ${Object.keys(sensorData).length + 1}`,
          location: {
            latitude: parseFloat(row.location_lat) || 0,
            longitude: parseFloat(row.location_lng) || 0
          },
          zone: "Zone1",
          date_buddhist: date,
          readings: []
        };
      }
      
      sensorData[row.sensor_id].readings.push({
        timestamp: row.time.toISOString(),
        moisture_percentage: parseFloat(row.moisture_surface_pct) || 0,
        temperature_celsius: parseFloat(row.temp_surface_c) || 0,
        quality: Math.round((row.quality_score || 1) * 100)
      });
    });
    
    const response = {
      data_type: "moisture",
      request_date: date,
      sensor_count: Object.keys(sensorData).length,
      sensors: Object.values(sensorData)
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching moisture timeseries:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

// GET /public/moisture/statistics
app.get('/api/v1/public/moisture/statistics', authenticateApiKey, async (req, res) => {
  try {
    const { date } = req.query;
    
    if (!date) {
      return res.status(400).json({ error: 'Date parameter required' });
    }
    
    const targetDate = fromBuddhistDate(date);
    const startDate = new Date(targetDate);
    startDate.setHours(0, 0, 0, 0);
    const endDate = new Date(targetDate);
    endDate.setHours(23, 59, 59, 999);
    
    const query = `
      SELECT 
        sensor_id,
        COUNT(*) as count,
        MIN(moisture_surface_pct) as min_moisture,
        MAX(moisture_surface_pct) as max_moisture,
        AVG(moisture_surface_pct) as avg_moisture,
        STDDEV(moisture_surface_pct) as stddev_moisture,
        MIN(location_lat) as lat,
        MIN(location_lng) as lng
      FROM moisture_readings
      WHERE time >= $1 AND time <= $2
      GROUP BY sensor_id
    `;
    
    const result = await pgPool.query(query, [startDate, endDate]);
    
    const response = {
      data_type: "moisture",
      request_date: date,
      sensor_count: result.rows.length,
      sensors: result.rows.map((row, index) => ({
        sensor_id: row.sensor_id,
        sensor_name: `Moisture Sensor ${index + 1}`,
        location: {
          latitude: parseFloat(row.lat) || 0,
          longitude: parseFloat(row.lng) || 0
        },
        zone: "Zone1",
        date_buddhist: date,
        statistics: {
          count: parseInt(row.count),
          min: parseFloat(row.min_moisture).toFixed(2),
          max: parseFloat(row.max_moisture).toFixed(2),
          avg: parseFloat(row.avg_moisture).toFixed(2),
          stddev: parseFloat(row.stddev_moisture || 0).toFixed(2)
        }
      }))
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching moisture statistics:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

// ====================
// AOS WEATHER ENDPOINTS (MSSQL SCADA)
// ====================

// GET /public/aos/latest
app.get('/api/v1/public/aos/latest', authenticateApiKey, async (req, res) => {
  try {
    const pool = await getMssqlPool();
    
    // Query for latest AOS data from SCADA database
    // Based on the actual tb_aos table structure: id, data_datetime, battery, windspeed, windmax, raingauge, temp, winddirect, solar
    const query = `
      SELECT TOP 3 
        id,
        data_datetime,
        battery,
        windspeed,
        windmax,
        raingauge,
        temp,
        winddirect,
        solar
      FROM dbo.tb_aos
      WHERE data_datetime > DATEADD(day, -7, GETDATE())
      ORDER BY data_datetime DESC
    `;
    
    const result = await pool.request().query(query);
    
    const response = {
      data_type: "aos_meteorological",
      request_time: new Date().toISOString(),
      request_time_buddhist: toBuddhistDate(new Date()),
      station_count: result.recordset.length,
      stations: result.recordset.map((row, index) => ({
        station_id: `AOS-${row.id || index + 1}`,
        station_name: `AOS Station ${row.id || index + 1}`,
        location: {
          latitude: 0, // Would need location mapping
          longitude: 0
        },
        zone: "Zone1",
        latest_reading: {
          timestamp: row.data_datetime.toISOString(),
          timestamp_buddhist: toBuddhistDate(row.data_datetime),
          rainfall_mm: parseFloat(row.raingauge) || 0,
          temperature_celsius: parseFloat(row.temp) || 0,
          humidity_percentage: 0, // Not available in tb_aos
          wind_speed_ms: parseFloat(row.windspeed) || 0,
          wind_max_ms: parseFloat(row.windmax) || 0,
          wind_direction_degrees: parseFloat(row.winddirect) || 0,
          pressure_hpa: 0, // Not available in tb_aos
          solar_radiation_wm2: parseFloat(row.solar) || 0,
          battery_voltage: parseFloat(row.battery) || 0,
          evapotranspiration_mm: 0 // Not available in tb_aos
        }
      }))
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching latest AOS data from SCADA:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

// GET /public/aos/timeseries
app.get('/api/v1/public/aos/timeseries', authenticateApiKey, async (req, res) => {
  try {
    const { date } = req.query;
    
    if (!date) {
      return res.status(400).json({ error: 'Date parameter required' });
    }
    
    const pool = await getMssqlPool();
    const targetDate = fromBuddhistDate(date);
    
    const query = `
      SELECT 
        id,
        data_datetime,
        battery,
        windspeed,
        windmax,
        raingauge,
        temp,
        winddirect,
        solar
      FROM dbo.tb_aos
      WHERE CAST(data_datetime AS DATE) = @date
      ORDER BY id, data_datetime ASC
    `;
    
    const result = await pool.request()
      .input('date', sql.Date, targetDate)
      .query(query);
    
    // Group by site_ID
    const stationData = {};
    result.recordset.forEach((row, index) => {
      const stationId = `AOS-${row.id || index + 1}`;
      
      if (!stationData[stationId]) {
        stationData[stationId] = {
          station_id: stationId,
          station_name: `AOS Station ${row.id || index + 1}`,
          location: {
            latitude: 0,
            longitude: 0
          },
          zone: "Zone1",
          date_buddhist: date,
          readings: []
        };
      }
      
      stationData[stationId].readings.push({
        timestamp: row.data_datetime.toISOString(),
        rainfall_mm: parseFloat(row.raingauge) || 0,
        temperature_celsius: parseFloat(row.temp) || 0,
        humidity_percentage: 0, // Not available in tb_aos
        wind_speed_ms: parseFloat(row.windspeed) || 0,
        wind_max_ms: parseFloat(row.windmax) || 0,
        wind_direction_degrees: parseFloat(row.winddirect) || 0,
        pressure_hpa: 0, // Not available in tb_aos
        solar_radiation_wm2: parseFloat(row.solar) || 0,
        battery_voltage: parseFloat(row.battery) || 0,
        evapotranspiration_mm: 0 // Not available in tb_aos
      });
    });
    
    const response = {
      data_type: "aos_meteorological",
      request_date: date,
      station_count: Object.keys(stationData).length,
      stations: Object.values(stationData)
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching AOS timeseries from SCADA:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

// GET /public/aos/statistics
app.get('/api/v1/public/aos/statistics', authenticateApiKey, async (req, res) => {
  try {
    const { date } = req.query;
    
    if (!date) {
      return res.status(400).json({ error: 'Date parameter required' });
    }
    
    const pool = await getMssqlPool();
    const targetDate = fromBuddhistDate(date);
    
    const query = `
      SELECT 
        id,
        COUNT(*) as count,
        SUM(raingauge) as total_rainfall,
        MIN(temp) as min_temp,
        MAX(temp) as max_temp,
        AVG(temp) as avg_temp,
        AVG(windspeed) as avg_wind_speed,
        MAX(windmax) as max_wind_speed,
        AVG(solar) as avg_solar,
        AVG(battery) as avg_battery
      FROM dbo.tb_aos
      WHERE CAST(data_datetime AS DATE) = @date
      GROUP BY id
    `;
    
    const result = await pool.request()
      .input('date', sql.Date, targetDate)
      .query(query);
    
    const response = {
      data_type: "aos_meteorological",
      request_date: date,
      station_count: result.recordset.length,
      stations: result.recordset.map((row, index) => {
        const stationId = `AOS-${row.id || index + 1}`;
        return {
          station_id: stationId,
          station_name: `AOS Station ${row.id || index + 1}`,
          location: {
            latitude: 0,
            longitude: 0
          },
          zone: "Zone1",
          date_buddhist: date,
          statistics: {
            count: parseInt(row.count),
            total_rainfall_mm: parseFloat(row.total_rainfall || 0).toFixed(2),
            temperature: {
              min: parseFloat(row.min_temp || 0).toFixed(2),
              max: parseFloat(row.max_temp || 0).toFixed(2),
              avg: parseFloat(row.avg_temp || 0).toFixed(2)
            },
            avg_humidity: "0.00", // Not available in tb_aos
            avg_wind_speed: parseFloat(row.avg_wind_speed || 0).toFixed(2),
            max_wind_speed: parseFloat(row.max_wind_speed || 0).toFixed(2),
            avg_solar_radiation: parseFloat(row.avg_solar || 0).toFixed(2),
            avg_battery_voltage: parseFloat(row.avg_battery || 0).toFixed(2),
            avg_et0: "0.00" // Not available in tb_aos
          }
        };
      })
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching AOS statistics from SCADA:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

// Health check
app.get('/health', async (req, res) => {
  try {
    // Check PostgreSQL
    await pgPool.query('SELECT 1');
    
    // Check MSSQL
    const pool = await getMssqlPool();
    await pool.request().query('SELECT 1');
    
    res.status(200).json({ 
      status: 'healthy',
      service: 'external-api-v2-multi-db',
      databases: {
        timescaledb: 'connected',
        scada_mssql: 'connected'
      },
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    res.status(503).json({ 
      status: 'unhealthy',
      service: 'external-api-v2-multi-db',
      error: error.message
    });
  }
});

// Root endpoint
app.get('/', (req, res) => {
  res.status(200).json({
    service: 'Munbon External API V2.0 (Multi-DB Implementation)',
    version: '2.0.0',
    databases: {
      timescaledb: 'Water Level & Moisture data',
      scada_mssql: 'AOS Weather data from moonup.hopto.org'
    },
    endpoints: {
      waterLevel: {
        latest: '/api/v1/public/water-levels/latest',
        timeseries: '/api/v1/public/water-levels/timeseries?date=DD/MM/YYYY',
        statistics: '/api/v1/public/water-levels/statistics?date=DD/MM/YYYY'
      },
      moisture: {
        latest: '/api/v1/public/moisture/latest',
        timeseries: '/api/v1/public/moisture/timeseries?date=DD/MM/YYYY',
        statistics: '/api/v1/public/moisture/statistics?date=DD/MM/YYYY'
      },
      aos: {
        latest: '/api/v1/public/aos/latest',
        timeseries: '/api/v1/public/aos/timeseries?date=DD/MM/YYYY',
        statistics: '/api/v1/public/aos/statistics?date=DD/MM/YYYY'
      }
    },
    authentication: 'Required: X-API-Key header',
    dateFormat: 'Buddhist calendar (DD/MM/YYYY where YYYY = CE + 543)'
  });
});

const PORT = parseInt(process.env.PORT || '8081');

app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 External API V2.0 (Multi-DB) listening on port ${PORT}`);
  console.log(`📍 Base URL: http://43.208.201.191:${PORT}/api/v1`);
  console.log(`🔑 API Key required: X-API-Key header`);
  console.log(`💾 TimescaleDB: Water Level & Moisture data`);
  console.log(`💾 SCADA MSSQL: AOS Weather data from moonup.hopto.org`);
});