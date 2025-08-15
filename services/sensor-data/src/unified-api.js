const express = require('express');
const { Pool } = require('pg');
const sql = require('mssql');
const cors = require('cors');

const app = express();
app.use(express.json());
app.use(cors());

// Internal API key for Lambda authentication
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || 'munbon-internal-f3b89263126548';
console.log('Starting Unified API...');
console.log('Internal API Key:', INTERNAL_API_KEY);

// TimescaleDB connection (sensor data)
const timescaleDB = new Pool({
  host: process.env.TIMESCALE_HOST || 'localhost',
  port: process.env.TIMESCALE_PORT || 5433,
  database: process.env.TIMESCALE_DB || 'sensor_data',
  user: process.env.TIMESCALE_USER || 'postgres',
  password: process.env.TIMESCALE_PASSWORD || 'postgres'
});

// MSSQL connection (SCADA data) - Update these with your actual SCADA DB details
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

// Middleware for internal API key validation
app.use((req, res, next) => {
  const apiKey = req.headers['x-internal-key'];
  if (apiKey !== INTERNAL_API_KEY) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
});

// Buddhist calendar conversion
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

// Health check
app.get('/health', async (req, res) => {
  try {
    // Check TimescaleDB connection
    const tsResult = await timescaleDB.query('SELECT 1');
    const timescaleStatus = tsResult ? 'connected' : 'disconnected';
    
    // Check MSSQL connection (optional, might fail if not configured)
    let mssqlStatus = 'not_configured';
    try {
      const pool = await sql.connect(mssqlConfig);
      await pool.request().query('SELECT 1');
      mssqlStatus = 'connected';
      pool.close();
    } catch (err) {
      mssqlStatus = 'disconnected';
    }
    
    res.json({ 
      status: 'healthy', 
      service: 'unified-api',
      databases: {
        timescale: timescaleStatus,
        mssql: mssqlStatus
      },
      uptime: process.uptime(),
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    res.status(503).json({ 
      status: 'unhealthy', 
      service: 'unified-api',
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

// Water Level Endpoints
app.get('/api/v1/sensors/water-level/latest', async (req, res) => {
  try {
    const query = `
      SELECT 
        sr.sensor_id,
        sr.sensor_id as sensor_name,
        sr.location_lat,
        sr.location_lng,
        COALESCE(sr.metadata->>'zone', 'Zone1') as zone,
        wl.time as timestamp,
        wl.level_cm / 100.0 as water_level_m,
        0 as flow_rate_m3s,
        COALESCE(wl.quality_score, 100) as quality
      FROM sensor_registry sr
      LEFT JOIN LATERAL (
        SELECT time, level_cm, quality_score
        FROM water_level_readings
        WHERE sensor_id = sr.sensor_id
        ORDER BY time DESC
        LIMIT 1
      ) wl ON true
      WHERE sr.sensor_type = 'water_level' AND sr.is_active = true
    `;
    
    const result = await timescaleDB.query(query);
    
    const response = {
      data_type: 'water_level',
      request_time: new Date().toISOString(),
      request_time_buddhist: convertToBuddhistDate(new Date()),
      sensor_count: result.rows.length,
      sensors: result.rows.map(row => ({
        sensor_id: row.sensor_id,
        sensor_name: row.sensor_name,
        location: {
          latitude: row.location_lat,
          longitude: row.location_lng
        },
        zone: row.zone,
        latest_reading: row.timestamp ? {
          timestamp: row.timestamp,
          timestamp_buddhist: convertToBuddhistDate(row.timestamp),
          water_level_m: parseFloat(row.water_level_m) || 0,
          flow_rate_m3s: parseFloat(row.flow_rate_m3s) || 0,
          quality: parseFloat(row.quality) || 100
        } : null
      }))
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching water level data:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

app.get('/api/v1/sensors/water-level/timeseries', async (req, res) => {
  try {
    const { date } = req.query;
    if (!date) {
      return res.status(400).json({ error: 'Date parameter required' });
    }
    
    const targetDate = parseBuddhistDate(date);
    const startTime = new Date(targetDate);
    startTime.setHours(0, 0, 0, 0);
    const endTime = new Date(targetDate);
    endTime.setHours(23, 59, 59, 999);
    
    const query = `
      SELECT 
        sr.sensor_id,
        sr.sensor_id as name,
        sr.location_lat,
        sr.location_lng,
        COALESCE(sr.metadata->>'zone', 'Zone1') as zone,
        wl.time as timestamp,
        wl.level_cm / 100.0 as water_level_m,
        0 as flow_rate_m3s,
        COALESCE(wl.quality_score, 100) as quality
      FROM sensor_registry sr
      INNER JOIN water_level_readings wl ON sr.sensor_id = wl.sensor_id
      WHERE sr.sensor_type = 'water_level' 
        AND sr.is_active = true
        AND wl.time >= $1 
        AND wl.time <= $2
      ORDER BY sr.sensor_id, wl.time
    `;
    
    const result = await timescaleDB.query(query, [startTime, endTime]);
    
    // Group by sensor
    const groupedData = result.rows.reduce((acc, row) => {
      if (!acc[row.sensor_id]) {
        acc[row.sensor_id] = {
          sensor_id: row.sensor_id,
          sensor_name: row.name,
          location: row.location,
          zone: row.zone,
          date_buddhist: date,
          readings: []
        };
      }
      acc[row.sensor_id].readings.push({
        timestamp: row.timestamp,
        water_level_m: parseFloat(row.water_level_m) || 0,
        flow_rate_m3s: parseFloat(row.flow_rate_m3s) || 0,
        quality: row.quality || 100
      });
      return acc;
    }, {});
    
    res.json({
      data_type: 'water_level',
      request_date: date,
      sensor_count: Object.keys(groupedData).length,
      sensors: Object.values(groupedData)
    });
  } catch (error) {
    console.error('Error fetching water level timeseries:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

// Moisture Endpoints
app.get('/api/v1/sensors/moisture/latest', async (req, res) => {
  try {
    const query = `
      SELECT 
        mr.sensor_id,
        mr.sensor_id as sensor_name,
        COALESCE(sr.location_lat, mr.location_lat) as location_lat,
        COALESCE(sr.location_lng, mr.location_lng) as location_lng,
        COALESCE(sr.metadata->>'zone', 'Zone1') as zone,
        mr.time as timestamp,
        mr.moisture_surface_pct as moisture_percentage,
        mr.temp_surface_c as temperature_celsius,
        COALESCE(mr.quality_score, 100) as quality
      FROM (
        SELECT DISTINCT ON (sensor_id) 
          sensor_id, time, location_lat, location_lng,
          moisture_surface_pct, temp_surface_c, quality_score
        FROM moisture_readings
        ORDER BY sensor_id, time DESC
      ) mr
      LEFT JOIN sensor_registry sr ON mr.sensor_id = sr.sensor_id
    `;
    
    const result = await timescaleDB.query(query);
    
    const response = {
      data_type: 'moisture',
      request_time: new Date().toISOString(),
      request_time_buddhist: convertToBuddhistDate(new Date()),
      sensor_count: result.rows.length,
      sensors: result.rows.map(row => ({
        sensor_id: row.sensor_id,
        sensor_name: row.sensor_name,
        location: {
          latitude: row.location_lat,
          longitude: row.location_lng
        },
        zone: row.zone,
        latest_reading: row.timestamp ? {
          timestamp: row.timestamp,
          timestamp_buddhist: convertToBuddhistDate(row.timestamp),
          moisture_percentage: parseFloat(row.moisture_percentage) || 0,
          temperature_celsius: parseFloat(row.temperature_celsius) || 0,
          quality: parseFloat(row.quality) || 100
        } : null
      }))
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching moisture data:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

app.get('/api/v1/sensors/moisture/timeseries', async (req, res) => {
  try {
    const { date } = req.query;
    if (!date) {
      return res.status(400).json({ error: 'Date parameter required' });
    }
    
    const targetDate = parseBuddhistDate(date);
    const startTime = new Date(targetDate);
    startTime.setHours(0, 0, 0, 0);
    const endTime = new Date(targetDate);
    endTime.setHours(23, 59, 59, 999);
    
    const query = `
      SELECT 
        mr.sensor_id,
        COALESCE(sr.metadata->>'name', mr.sensor_id) as name,
        mr.location_lat,
        mr.location_lng,
        COALESCE(sr.metadata->>'zone', 'Zone1') as zone,
        mr.time as timestamp,
        mr.moisture_surface_pct as moisture_percentage,
        mr.temp_surface_c as temperature_celsius,
        COALESCE(mr.quality_score, 100) as quality
      FROM moisture_readings mr
      LEFT JOIN sensor_registry sr ON mr.sensor_id = sr.sensor_id
      WHERE mr.time >= $1 
        AND mr.time <= $2
      ORDER BY mr.sensor_id, mr.time
    `;
    
    const result = await timescaleDB.query(query, [startTime, endTime]);
    
    // Group by sensor
    const groupedData = result.rows.reduce((acc, row) => {
      if (!acc[row.sensor_id]) {
        acc[row.sensor_id] = {
          sensor_id: row.sensor_id,
          sensor_name: row.name,
          location: row.location,
          zone: row.zone,
          date_buddhist: date,
          readings: []
        };
      }
      acc[row.sensor_id].readings.push({
        timestamp: row.timestamp,
        moisture_percentage: parseFloat(row.moisture_percentage) || 0,
        temperature_celsius: parseFloat(row.temperature_celsius) || 0,
        quality: row.quality || 100
      });
      return acc;
    }, {});
    
    res.json({
      data_type: 'moisture',
      request_date: date,
      sensor_count: Object.keys(groupedData).length,
      sensors: Object.values(groupedData)
    });
  } catch (error) {
    console.error('Error fetching moisture timeseries:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

// AOS/Weather endpoints (can integrate with MSSQL if SCADA has weather data)
app.get('/api/v1/sensors/aos/latest', async (req, res) => {
  try {
    // This could come from TimescaleDB or MSSQL depending on your setup
    const query = `
      SELECT 
        s.sensor_id as station_id,
        s.name as station_name,
        s.location,
        s.zone,
        sr.time as timestamp,
        sr.data
      FROM sensors s
      LEFT JOIN LATERAL (
        SELECT time, data
        FROM sensor_readings
        WHERE sensor_id = s.sensor_id
        ORDER BY time DESC
        LIMIT 1
      ) sr ON true
      WHERE s.type = 'weather' AND s.is_active = true
    `;
    
    const result = await timescaleDB.query(query);
    
    const response = {
      data_type: 'aos_meteorological',
      request_time: new Date().toISOString(),
      request_time_buddhist: convertToBuddhistDate(new Date()),
      station_count: result.rows.length,
      stations: result.rows.map(row => ({
        station_id: row.station_id,
        station_name: row.station_name,
        location: row.location,
        zone: row.zone,
        latest_reading: row.timestamp ? {
          timestamp: row.timestamp,
          timestamp_buddhist: convertToBuddhistDate(row.timestamp),
          rainfall_mm: row.data?.rainfall_mm || 0,
          temperature_celsius: row.data?.temperature_celsius || 0,
          humidity_percentage: row.data?.humidity_percentage || 0,
          wind_speed_ms: row.data?.wind_speed_ms || 0,
          wind_direction_degrees: row.data?.wind_direction_degrees || 0,
          pressure_hpa: row.data?.pressure_hpa || 0
        } : null
      }))
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching AOS data:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

// Statistics endpoints
app.get('/api/v1/sensors/water-level/statistics', async (req, res) => {
  try {
    const { date } = req.query;
    if (!date) {
      return res.status(400).json({ error: 'Date parameter required' });
    }
    
    const targetDate = parseBuddhistDate(date);
    const startTime = new Date(targetDate);
    startTime.setHours(0, 0, 0, 0);
    const endTime = new Date(targetDate);
    endTime.setHours(23, 59, 59, 999);
    
    const query = `
      SELECT 
        sr.sensor_id,
        sr.sensor_id as name,
        sr.location_lat,
        sr.location_lng,
        COALESCE(sr.metadata->>'zone', 'Zone1') as zone,
        COUNT(wl.*) as count,
        MIN(wl.level_cm / 100.0) as min,
        MAX(wl.level_cm / 100.0) as max,
        AVG(wl.level_cm / 100.0) as avg,
        STDDEV(wl.level_cm / 100.0) as stddev
      FROM sensor_registry sr
      LEFT JOIN water_level_readings wl ON sr.sensor_id = wl.sensor_id
        AND wl.time >= $1 AND wl.time <= $2
      WHERE sr.sensor_type = 'water_level' 
        AND sr.is_active = true
      GROUP BY sr.sensor_id, sr.location_lat, sr.location_lng, sr.metadata->>'zone'
    `;
    
    const result = await timescaleDB.query(query, [startTime, endTime]);
    
    res.json({
      data_type: 'water_level',
      request_date: date,
      sensor_count: result.rows.length,
      sensors: result.rows.map(row => ({
        sensor_id: row.sensor_id,
        sensor_name: row.name,
        location: {
          latitude: row.location_lat,
          longitude: row.location_lng
        },
        zone: row.zone,
        date_buddhist: date,
        statistics: {
          count: parseInt(row.count) || 0,
          min: parseFloat(row.min) || 0,
          max: parseFloat(row.max) || 0,
          avg: parseFloat(row.avg) || 0,
          stddev: parseFloat(row.stddev) || 0
        }
      })).filter(s => s.statistics.count > 0)
    });
  } catch (error) {
    console.error('Error fetching statistics:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

// Similar statistics endpoints for moisture and AOS...

// Error handler
app.use((err, req, res, next) => {
  console.error('Error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Unified API running on port ${PORT}`);
  console.log(`Internal API Key: ${INTERNAL_API_KEY}`);
  console.log('Ready to receive requests from Lambda via Cloudflare tunnel');
});

// Test database connections
timescaleDB.query('SELECT NOW()', (err, res) => {
  if (err) {
    console.error('TimescaleDB connection error:', err);
  } else {
    console.log('✅ TimescaleDB connected:', res.rows[0].now);
  }
});

// Uncomment and configure when you have MSSQL details
// sql.connect(mssqlConfig).then(() => {
//   console.log('✅ MSSQL connected');
// }).catch(err => {
//   console.error('MSSQL connection error:', err);
// });