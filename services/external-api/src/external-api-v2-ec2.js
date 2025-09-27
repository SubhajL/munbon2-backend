const express = require('express');
const { Pool } = require('pg');
const moment = require('moment');
require('dotenv').config();

const app = express();

// Database connection to EC2
const dbPool = new Pool({
  host: process.env.DB_HOST || '43.208.201.191',
  port: parseInt(process.env.DB_PORT || '5432'),
  database: process.env.DB_NAME || 'sensor_data',
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || '__ROTATED_DB_PASSWORD__',
  max: 10
});

// Valid API Keys (matching External API V2.0 spec)
const VALID_API_KEYS = {
  'rid-ms-prod-key1': 'RID Main System',
  'tmd-weather-key2': 'Thai Meteorological Department',
  'university-key3': 'University Research'
};

// Active water level sensors (from spec)
const ACTIVE_WATER_LEVEL_SENSORS = [
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

// ====================
// WATER LEVEL ENDPOINTS
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
        AND time > NOW() - INTERVAL '24 hours'
      ORDER BY sensor_id, time DESC
    `;
    
    const result = await dbPool.query(query, [ACTIVE_WATER_LEVEL_SENSORS]);
    
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
        zone: "Zone1", // Would need zone mapping table
        latest_reading: {
          timestamp: row.time.toISOString(),
          timestamp_buddhist: toBuddhistDate(row.time),
          water_level_m: row.level_cm ? (row.level_cm / 100).toFixed(2) : 0,
          flow_rate_m3s: 0, // No flow meters as per spec
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
    
    const result = await dbPool.query(query, [ACTIVE_WATER_LEVEL_SENSORS, startDate, endDate]);
    
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
    
    const result = await dbPool.query(query, [ACTIVE_WATER_LEVEL_SENSORS, startDate, endDate]);
    
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
// MOISTURE ENDPOINTS
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
    
    const result = await dbPool.query(query);
    
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
    
    const result = await dbPool.query(query, [startDate, endDate]);
    
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
    
    const result = await dbPool.query(query, [startDate, endDate]);
    
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
// AOS WEATHER ENDPOINTS
// ====================

// GET /public/aos/latest
app.get('/api/v1/public/aos/latest', authenticateApiKey, async (req, res) => {
  try {
    const query = `
      SELECT DISTINCT ON (station_id) 
        time, station_id, rainfall_mm, temperature_c, humidity_pct,
        wind_speed_ms, wind_direction_deg, pressure_hpa,
        location_lat, location_lng
      FROM aos_weather_data
      WHERE time > NOW() - INTERVAL '24 hours'
      ORDER BY station_id, time DESC
      LIMIT 3
    `;
    
    const result = await dbPool.query(query);
    
    const response = {
      data_type: "aos_meteorological",
      request_time: new Date().toISOString(),
      request_time_buddhist: toBuddhistDate(new Date()),
      station_count: result.rows.length,
      stations: result.rows.map((row, index) => ({
        station_id: row.station_id,
        station_name: `AOS Station ${index + 1}`,
        location: {
          latitude: parseFloat(row.location_lat) || 0,
          longitude: parseFloat(row.location_lng) || 0
        },
        zone: "Zone1",
        latest_reading: {
          timestamp: row.time.toISOString(),
          timestamp_buddhist: toBuddhistDate(row.time),
          rainfall_mm: parseFloat(row.rainfall_mm) || 0,
          temperature_celsius: parseFloat(row.temperature_c) || 0,
          humidity_percentage: parseFloat(row.humidity_pct) || 0,
          wind_speed_ms: parseFloat(row.wind_speed_ms) || 0,
          wind_direction_degrees: parseFloat(row.wind_direction_deg) || 0,
          pressure_hpa: parseFloat(row.pressure_hpa) || 0
        }
      }))
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching latest AOS data:', error);
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
    
    const targetDate = fromBuddhistDate(date);
    const startDate = new Date(targetDate);
    startDate.setHours(0, 0, 0, 0);
    const endDate = new Date(targetDate);
    endDate.setHours(23, 59, 59, 999);
    
    const query = `
      SELECT time, station_id, rainfall_mm, temperature_c, humidity_pct,
             wind_speed_ms, wind_direction_deg, pressure_hpa,
             location_lat, location_lng
      FROM aos_weather_data
      WHERE time >= $1 AND time <= $2
      ORDER BY station_id, time ASC
    `;
    
    const result = await dbPool.query(query, [startDate, endDate]);
    
    // Group by station_id
    const stationData = {};
    result.rows.forEach((row, index) => {
      if (!stationData[row.station_id]) {
        stationData[row.station_id] = {
          station_id: row.station_id,
          station_name: `AOS Station ${Object.keys(stationData).length + 1}`,
          location: {
            latitude: parseFloat(row.location_lat) || 0,
            longitude: parseFloat(row.location_lng) || 0
          },
          zone: "Zone1",
          date_buddhist: date,
          readings: []
        };
      }
      
      stationData[row.station_id].readings.push({
        timestamp: row.time.toISOString(),
        rainfall_mm: parseFloat(row.rainfall_mm) || 0,
        temperature_celsius: parseFloat(row.temperature_c) || 0,
        humidity_percentage: parseFloat(row.humidity_pct) || 0,
        wind_speed_ms: parseFloat(row.wind_speed_ms) || 0,
        wind_direction_degrees: parseFloat(row.wind_direction_deg) || 0,
        pressure_hpa: parseFloat(row.pressure_hpa) || 0
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
    console.error('Error fetching AOS timeseries:', error);
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
    
    const targetDate = fromBuddhistDate(date);
    const startDate = new Date(targetDate);
    startDate.setHours(0, 0, 0, 0);
    const endDate = new Date(targetDate);
    endDate.setHours(23, 59, 59, 999);
    
    const query = `
      SELECT 
        station_id,
        COUNT(*) as count,
        SUM(rainfall_mm) as total_rainfall,
        MIN(temperature_c) as min_temp,
        MAX(temperature_c) as max_temp,
        AVG(temperature_c) as avg_temp,
        AVG(humidity_pct) as avg_humidity,
        AVG(wind_speed_ms) as avg_wind_speed,
        MIN(location_lat) as lat,
        MIN(location_lng) as lng
      FROM aos_weather_data
      WHERE time >= $1 AND time <= $2
      GROUP BY station_id
    `;
    
    const result = await dbPool.query(query, [startDate, endDate]);
    
    const response = {
      data_type: "aos_meteorological",
      request_date: date,
      station_count: result.rows.length,
      stations: result.rows.map((row, index) => ({
        station_id: row.station_id,
        station_name: `AOS Station ${index + 1}`,
        location: {
          latitude: parseFloat(row.lat) || 0,
          longitude: parseFloat(row.lng) || 0
        },
        zone: "Zone1",
        date_buddhist: date,
        statistics: {
          count: parseInt(row.count),
          total_rainfall_mm: parseFloat(row.total_rainfall).toFixed(2),
          temperature: {
            min: parseFloat(row.min_temp).toFixed(2),
            max: parseFloat(row.max_temp).toFixed(2),
            avg: parseFloat(row.avg_temp).toFixed(2)
          },
          avg_humidity: parseFloat(row.avg_humidity).toFixed(2),
          avg_wind_speed: parseFloat(row.avg_wind_speed).toFixed(2)
        }
      }))
    };
    
    res.json(response);
  } catch (error) {
    console.error('Error fetching AOS statistics:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

// Health check
app.get('/health', async (req, res) => {
  try {
    await dbPool.query('SELECT 1');
    res.status(200).json({ 
      status: 'healthy',
      service: 'external-api-v2-ec2',
      database: 'connected',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    res.status(503).json({ 
      status: 'unhealthy',
      service: 'external-api-v2-ec2',
      database: 'disconnected',
      error: error.message
    });
  }
});

// Root endpoint
app.get('/', (req, res) => {
  res.status(200).json({
    service: 'Munbon External API V2.0 (EC2 Implementation)',
    version: '2.0.0',
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

const PORT = parseInt(process.env.PORT || '8080');

app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 External API V2.0 (EC2) listening on port ${PORT}`);
  console.log(`📍 Base URL: http://43.208.201.191:${PORT}/api/v1`);
  console.log(`🔑 API Key required: X-API-Key header`);
});