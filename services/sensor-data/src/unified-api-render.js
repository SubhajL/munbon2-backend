const express = require('express');
const { Pool } = require('pg');
const sql = require('mssql');
const cors = require('cors');

const app = express();
app.use(express.json());
app.use(cors());

// Use Render's PostgreSQL as TimescaleDB replacement
const timescaleDB = new Pool({
  connectionString: process.env.DATABASE_URL || 
    `postgresql://${process.env.TIMESCALE_USER}:${process.env.TIMESCALE_PASSWORD}@${process.env.TIMESCALE_HOST}:${process.env.TIMESCALE_PORT}/${process.env.TIMESCALE_DB}`,
  ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false
});

// Copy the rest from unified-api-v2.js but use the Pool above

// MSSQL connection (SCADA data) - AOS weather station data
const mssqlConfig = {
  server: process.env.MSSQL_HOST || 'moonup.hopto.org',
  database: process.env.MSSQL_DB || 'db_scada',
  user: process.env.MSSQL_USER || 'sa',
  password: process.env.MSSQL_PASSWORD || 'bangkok1234',
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
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'unified-api-v2' });
});

// Water Level Endpoints
app.get('/api/v1/sensors/water-level/latest', async (req, res) => {
  try {
    const query = `
      SELECT 
        sr.sensor_id,
        COALESCE(sr.metadata->>'name', sr.sensor_id) as sensor_name,
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
        COALESCE(sr.metadata->>'name', sr.sensor_id) as name,
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
          location: {
            latitude: row.location_lat,
            longitude: row.location_lng
          },
          zone: row.zone,
          date_buddhist: date,
          readings: []
        };
      }
      acc[row.sensor_id].readings.push({
        timestamp: row.timestamp,
        water_level_m: parseFloat(row.water_level_m) || 0,
        flow_rate_m3s: parseFloat(row.flow_rate_m3s) || 0,
        quality: parseFloat(row.quality) || 100
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
        sr.sensor_id,
        COALESCE(sr.metadata->>'name', sr.sensor_id) as sensor_name,
        sr.location_lat,
        sr.location_lng,
        COALESCE(sr.metadata->>'zone', 'Zone1') as zone,
        mr.time as timestamp,
        COALESCE(mr.moisture_surface_pct, mr.moisture_deep_pct) as moisture_percentage,
        COALESCE(mr.temp_surface_c, mr.ambient_temp_c) as temperature_celsius,
        COALESCE(mr.quality_score, 100) as quality
      FROM sensor_registry sr
      LEFT JOIN LATERAL (
        SELECT time, moisture_surface_pct, moisture_deep_pct, 
               temp_surface_c, ambient_temp_c, quality_score
        FROM moisture_readings
        WHERE sensor_id = sr.sensor_id
        ORDER BY time DESC
        LIMIT 1
      ) mr ON true
      WHERE sr.sensor_type = 'moisture' AND sr.is_active = true
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
        sr.sensor_id,
        COALESCE(sr.metadata->>'name', sr.sensor_id) as name,
        sr.location_lat,
        sr.location_lng,
        COALESCE(sr.metadata->>'zone', 'Zone1') as zone,
        mr.time as timestamp,
        COALESCE(mr.moisture_surface_pct, mr.moisture_deep_pct) as moisture_percentage,
        COALESCE(mr.temp_surface_c, mr.ambient_temp_c) as temperature_celsius,
        COALESCE(mr.quality_score, 100) as quality
      FROM sensor_registry sr
      INNER JOIN moisture_readings mr ON sr.sensor_id = mr.sensor_id
      WHERE sr.sensor_type = 'moisture' 
        AND sr.is_active = true
        AND mr.time >= $1 
        AND mr.time <= $2
      ORDER BY sr.sensor_id, mr.time
    `;
    
    const result = await timescaleDB.query(query, [startTime, endTime]);
    
    // Group by sensor
    const groupedData = result.rows.reduce((acc, row) => {
      if (!acc[row.sensor_id]) {
        acc[row.sensor_id] = {
          sensor_id: row.sensor_id,
          sensor_name: row.name,
          location: {
            latitude: row.location_lat,
            longitude: row.location_lng
          },
          zone: row.zone,
          date_buddhist: date,
          readings: []
        };
      }
      acc[row.sensor_id].readings.push({
        timestamp: row.timestamp,
        moisture_percentage: parseFloat(row.moisture_percentage) || 0,
        temperature_celsius: parseFloat(row.temperature_celsius) || 0,
        quality: parseFloat(row.quality) || 100
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

// AOS/Weather endpoints (from MSSQL SCADA data)
app.get('/api/v1/sensors/aos/latest', async (req, res) => {
  let pool;
  try {
    // Connect to MSSQL
    pool = await sql.connect(mssqlConfig);
    
    // Query to get latest AOS data from tb_aos table
    const query = `
      SELECT TOP 1
        id,
        data_datetime,
        battery,
        windspeed,
        windmax,
        raingauge,
        temp,
        winddirect,
        solar
      FROM tb_aos
      ORDER BY data_datetime DESC
    `;
    
    const result = await pool.request().query(query);
    
    if (result.recordset.length === 0) {
      return res.json({
        data_type: 'aos_meteorological',
        request_time: new Date().toISOString(),
        request_time_buddhist: convertToBuddhistDate(new Date()),
        station_count: 0,
        stations: []
      });
    }
    
    const row = result.recordset[0];
    
    // Create single station response (modify if multiple stations exist)
    const stations = [{
      station_id: 'AOS001',
      station_name: 'Munbon AOS Weather Station',
      location: {
        latitude: 14.3754,  // Default coordinates for Munbon area
        longitude: 102.8756
      },
      zone: 'Zone1',
      latest_reading: {
        timestamp: row.data_datetime,
        timestamp_buddhist: convertToBuddhistDate(row.data_datetime),
        rainfall_mm: parseFloat(row.raingauge) || 0,
        temperature_celsius: parseFloat(row.temp) || 0,
        humidity_percentage: 0, // Not available in this table
        wind_speed_ms: parseFloat(row.windspeed) || 0,
        wind_max_ms: parseFloat(row.windmax) || 0,
        wind_direction_degrees: parseFloat(row.winddirect) || 0,
        solar_radiation_wm2: parseFloat(row.solar) || 0,
        battery_voltage: parseFloat(row.battery) || 0,
        pressure_hpa: 0 // Not available in this table
      }
    }];
    
    const response = {
      data_type: 'aos_meteorological',
      request_time: new Date().toISOString(),
      request_time_buddhist: convertToBuddhistDate(new Date()),
      station_count: stations.length,
      stations: stations
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching AOS data from MSSQL:', error);
    res.status(500).json({ error: 'Database error' });
  } finally {
    if (pool) {
      await pool.close();
    }
  }
});

// AOS Time Series endpoint (from MSSQL)
app.get('/api/v1/sensors/aos/timeseries', async (req, res) => {
  let pool;
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
    
    // Connect to MSSQL
    pool = await sql.connect(mssqlConfig);
    
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
      FROM tb_aos
      WHERE data_datetime >= @startTime AND data_datetime <= @endTime
      ORDER BY data_datetime
    `;
    
    const result = await pool.request()
      .input('startTime', sql.DateTime, startTime)
      .input('endTime', sql.DateTime, endTime)
      .query(query);
    
    // Group all readings for the single station
    const readings = result.recordset.map(row => ({
      timestamp: row.data_datetime,
      rainfall_mm: parseFloat(row.raingauge) || 0,
      temperature_celsius: parseFloat(row.temp) || 0,
      humidity_percentage: 0, // Not available
      wind_speed_ms: parseFloat(row.windspeed) || 0,
      wind_max_ms: parseFloat(row.windmax) || 0,
      wind_direction_degrees: parseFloat(row.winddirect) || 0,
      solar_radiation_wm2: parseFloat(row.solar) || 0,
      battery_voltage: parseFloat(row.battery) || 0,
      pressure_hpa: 0 // Not available
    }));
    
    const stations = readings.length > 0 ? [{
      station_id: 'AOS001',
      station_name: 'Munbon AOS Weather Station',
      location: {
        latitude: 14.3754,
        longitude: 102.8756
      },
      zone: 'Zone1',
      date_buddhist: date,
      readings: readings
    }] : [];
    
    const response = {
      data_type: 'aos_meteorological',
      request_date: date,
      station_count: stations.length,
      stations: stations
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching AOS timeseries from MSSQL:', error);
    res.status(500).json({ error: 'Database error' });
  } finally {
    if (pool) {
      await pool.close();
    }
  }
});

// AOS Statistics endpoint (from MSSQL)
app.get('/api/v1/sensors/aos/statistics', async (req, res) => {
  let pool;
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
    
    // Connect to MSSQL
    pool = await sql.connect(mssqlConfig);
    
    const query = `
      SELECT 
        COUNT(*) as count,
        MIN(battery) as min_battery, MAX(battery) as max_battery, AVG(battery) as avg_battery,
        MIN(windspeed) as min_windspeed, MAX(windspeed) as max_windspeed, AVG(windspeed) as avg_windspeed, STDEV(windspeed) as stddev_windspeed,
        MIN(windmax) as min_windmax, MAX(windmax) as max_windmax, AVG(windmax) as avg_windmax,
        MIN(raingauge) as min_rain, MAX(raingauge) as max_rain, AVG(raingauge) as avg_rain, SUM(raingauge) as total_rain,
        MIN(temp) as min_temp, MAX(temp) as max_temp, AVG(temp) as avg_temp, STDEV(temp) as stddev_temp,
        MIN(winddirect) as min_winddir, MAX(winddirect) as max_winddir, AVG(winddirect) as avg_winddir,
        MIN(solar) as min_solar, MAX(solar) as max_solar, AVG(solar) as avg_solar, STDEV(solar) as stddev_solar
      FROM tb_aos
      WHERE data_datetime >= @startTime AND data_datetime <= @endTime
    `;
    
    const result = await pool.request()
      .input('startTime', sql.DateTime, startTime)
      .input('endTime', sql.DateTime, endTime)
      .query(query);
    
    if (result.recordset.length === 0 || result.recordset[0].count === 0) {
      return res.json({
        data_type: 'aos_meteorological',
        request_date: date,
        station_count: 0,
        stations: []
      });
    }
    
    const row = result.recordset[0];
    
    const stations = [{
      station_id: 'AOS001',
      station_name: 'Munbon AOS Weather Station',
      location: {
        latitude: 14.3754,
        longitude: 102.8756
      },
      zone: 'Zone1',
      date_buddhist: date,
      statistics: {
        reading_count: parseInt(row.count) || 0,
        rainfall: {
          min: parseFloat(row.min_rain) || 0,
          max: parseFloat(row.max_rain) || 0,
          avg: parseFloat(row.avg_rain) || 0,
          total: parseFloat(row.total_rain) || 0
        },
        temperature: {
          min: parseFloat(row.min_temp) || 0,
          max: parseFloat(row.max_temp) || 0,
          avg: parseFloat(row.avg_temp) || 0,
          stddev: parseFloat(row.stddev_temp) || 0
        },
        wind_speed: {
          min: parseFloat(row.min_windspeed) || 0,
          max: parseFloat(row.max_windspeed) || 0,
          avg: parseFloat(row.avg_windspeed) || 0,
          stddev: parseFloat(row.stddev_windspeed) || 0,
          max_gust: parseFloat(row.max_windmax) || 0
        },
        wind_direction: {
          min: parseFloat(row.min_winddir) || 0,
          max: parseFloat(row.max_winddir) || 0,
          avg: parseFloat(row.avg_winddir) || 0
        },
        solar_radiation: {
          min: parseFloat(row.min_solar) || 0,
          max: parseFloat(row.max_solar) || 0,
          avg: parseFloat(row.avg_solar) || 0,
          stddev: parseFloat(row.stddev_solar) || 0
        },
        battery: {
          min: parseFloat(row.min_battery) || 0,
          max: parseFloat(row.max_battery) || 0,
          avg: parseFloat(row.avg_battery) || 0
        }
      }
    }];
    
    const response = {
      data_type: 'aos_meteorological',
      request_date: date,
      station_count: stations.length,
      stations: stations
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching AOS statistics from MSSQL:', error);
    res.status(500).json({ error: 'Database error' });
  } finally {
    if (pool) {
      await pool.close();
    }
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
        COALESCE(sr.metadata->>'name', sr.sensor_id) as name,
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
      WHERE sr.sensor_type = 'water_level' AND sr.is_active = true
      GROUP BY sr.sensor_id, sr.metadata, sr.location_lat, sr.location_lng
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

// Error handler
app.use((err, req, res, next) => {
  console.error('Error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Unified API V2 running on port ${PORT}`);
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

// Test MSSQL connection on startup
sql.connect(mssqlConfig).then(pool => {
  console.log('✅ MSSQL connected to db_scada at moonup.hopto.org');
  // Close the test connection
  pool.close();
}).catch(err => {
  console.error('MSSQL connection error:', err);
  console.log('Note: AOS endpoints will not work without MSSQL connection');
});