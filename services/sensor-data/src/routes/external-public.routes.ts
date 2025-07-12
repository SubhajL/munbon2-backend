import { Router, Request, Response, NextFunction } from 'express';
import { Logger } from 'pino';
import { TimescaleRepository } from '../repository/timescale.repository';

interface RouteOptions {
  repository: TimescaleRepository;
  logger: Logger;
}

export function createExternalPublicRoutes(options: RouteOptions): Router {
  const { repository, logger } = options;
  const router = Router();

  // API key authentication middleware
  const apiKeyAuth = (req: Request, res: Response, next: NextFunction) => {
    const apiKey = req.headers['x-api-key'] as string;
    const validApiKeys = (process.env.EXTERNAL_API_KEYS || '').split(',').filter(k => k);
    
    if (!apiKey || !validApiKeys.includes(apiKey)) {
      return res.status(401).json({ error: 'Invalid API key' });
    }
    
    next();
  };

// Buddhist calendar conversion (BE = CE + 543)
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

// Apply API key authentication to all routes
router.use(apiKeyAuth);

/**
 * @swagger
 * /api/v1/public/water-levels/timeseries:
 *   get:
 *     summary: Get water level time series data for all sensors on specific date
 *     tags: [Public API]
 *     security:
 *       - ApiKeyAuth: []
 *     parameters:
 *       - in: query
 *         name: date
 *         required: true
 *         schema:
 *           type: string
 *         description: Date in Buddhist calendar format (dd/mm/yyyy)
 *         example: "10/06/2568"
 *     responses:
 *       200:
 *         description: Water level time series data
 */
router.get('/water-levels/timeseries', async (req, res, next) => {
  try {
    const { date } = req.query;
    if (!date || typeof date !== 'string') {
      return res.status(400).json({ error: 'Date parameter is required (dd/mm/yyyy in Buddhist calendar)' });
    }

    const targetDate = parseBuddhistDate(date);
    const startTime = new Date(targetDate);
    startTime.setHours(0, 0, 0, 0);
    const endTime = new Date(targetDate);
    endTime.setHours(23, 59, 59, 999);

    const data = await repository.getWaterLevelReadings({
      startTime: startTime.toISOString(),
      endTime: endTime.toISOString()
    });

    // Group by sensor and format response
    const groupedData = data.reduce((acc: any, reading: any) => {
      if (!acc[reading.sensor_id]) {
        acc[reading.sensor_id] = {
          sensor_id: reading.sensor_id,
          sensor_name: reading.name,
          location: reading.location,
          zone: reading.zone,
          date_buddhist: convertToBuddhistDate(targetDate),
          readings: []
        };
      }
      acc[reading.sensor_id].readings.push({
        timestamp: reading.timestamp,
        water_level_m: reading.water_level_m,
        flow_rate_m3s: reading.flow_rate_m3s,
        quality: reading.quality
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
    next(error);
  }
});

/**
 * @swagger
 * /api/v1/public/water-levels/latest:
 *   get:
 *     summary: Get latest water level data for all sensors
 *     tags: [Public API]
 *     security:
 *       - ApiKeyAuth: []
 *     responses:
 *       200:
 *         description: Latest water level readings
 */
router.get('/water-levels/latest', async (req, res, next) => {
  try {
    const sensors = await repository.getSensors({ type: 'water_level', is_active: true });
    
    const latestReadings = await Promise.all(
      sensors.map(async (sensor) => {
        const latest = await repository.getLatestReading(sensor.sensor_id);
        return {
          sensor_id: sensor.sensor_id,
          sensor_name: sensor.name,
          location: sensor.location,
          zone: sensor.zone,
          latest_reading: latest ? {
            timestamp: latest.timestamp,
            timestamp_buddhist: convertToBuddhistDate(new Date(latest.timestamp)),
            water_level_m: latest.water_level_m,
            flow_rate_m3s: latest.flow_rate_m3s,
            quality: latest.quality
          } : null
        };
      })
    );

    res.json({
      data_type: 'water_level',
      request_time: new Date().toISOString(),
      request_time_buddhist: convertToBuddhistDate(new Date()),
      sensor_count: latestReadings.length,
      sensors: latestReadings
    });
  } catch (error) {
    next(error);
  }
});

/**
 * @swagger
 * /api/v1/public/water-levels/statistics:
 *   get:
 *     summary: Get water level statistics for specific date
 *     tags: [Public API]
 *     security:
 *       - ApiKeyAuth: []
 *     parameters:
 *       - in: query
 *         name: date
 *         required: true
 *         schema:
 *           type: string
 *         description: Date in Buddhist calendar format (dd/mm/yyyy)
 */
router.get('/water-levels/statistics', async (req, res, next) => {
  try {
    const { date } = req.query;
    if (!date || typeof date !== 'string') {
      return res.status(400).json({ error: 'Date parameter is required (dd/mm/yyyy in Buddhist calendar)' });
    }

    const targetDate = parseBuddhistDate(date);
    const startTime = new Date(targetDate);
    startTime.setHours(0, 0, 0, 0);
    const endTime = new Date(targetDate);
    endTime.setHours(23, 59, 59, 999);

    const sensors = await repository.getSensors({ type: 'water_level', is_active: true });
    
    const statistics = await Promise.all(
      sensors.map(async (sensor) => {
        const stats = await repository.getSensorStatistics(
          sensor.sensor_id,
          startTime.toISOString(),
          endTime.toISOString()
        );
        return {
          sensor_id: sensor.sensor_id,
          sensor_name: sensor.name,
          location: sensor.location,
          zone: sensor.zone,
          date_buddhist: convertToBuddhistDate(targetDate),
          statistics: stats
        };
      })
    );

    res.json({
      data_type: 'water_level',
      request_date: date,
      sensor_count: statistics.length,
      sensors: statistics.filter(s => s.statistics.count > 0)
    });
  } catch (error) {
    next(error);
  }
});

// Similar endpoints for moisture data
/**
 * @swagger
 * /api/v1/public/moisture/timeseries:
 *   get:
 *     summary: Get moisture time series data for all sensors on specific date
 *     tags: [Public API]
 *     security:
 *       - ApiKeyAuth: []
 *     parameters:
 *       - in: query
 *         name: date
 *         required: true
 *         schema:
 *           type: string
 *         description: Date in Buddhist calendar format (dd/mm/yyyy)
 */
router.get('/moisture/timeseries', async (req, res, next) => {
  try {
    const { date } = req.query;
    if (!date || typeof date !== 'string') {
      return res.status(400).json({ error: 'Date parameter is required (dd/mm/yyyy in Buddhist calendar)' });
    }

    const targetDate = parseBuddhistDate(date);
    const startTime = new Date(targetDate);
    startTime.setHours(0, 0, 0, 0);
    const endTime = new Date(targetDate);
    endTime.setHours(23, 59, 59, 999);

    const data = await repository.getMoistureReadings({
      startTime: startTime.toISOString(),
      endTime: endTime.toISOString()
    });

    // Group by sensor and format response
    const groupedData = data.reduce((acc: any, reading: any) => {
      if (!acc[reading.sensor_id]) {
        acc[reading.sensor_id] = {
          sensor_id: reading.sensor_id,
          sensor_name: reading.name,
          location: reading.location,
          zone: reading.zone,
          date_buddhist: convertToBuddhistDate(targetDate),
          readings: []
        };
      }
      acc[reading.sensor_id].readings.push({
        timestamp: reading.timestamp,
        moisture_percentage: reading.moisture_percentage,
        temperature_celsius: reading.temperature_celsius,
        quality: reading.quality
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
    next(error);
  }
});

/**
 * @swagger
 * /api/v1/public/moisture/latest:
 *   get:
 *     summary: Get latest moisture data for all sensors
 *     tags: [Public API]
 *     security:
 *       - ApiKeyAuth: []
 */
router.get('/moisture/latest', async (req, res, next) => {
  try {
    const sensors = await repository.getSensors({ type: 'moisture', is_active: true });
    
    const latestReadings = await Promise.all(
      sensors.map(async (sensor) => {
        const latest = await repository.getLatestReading(sensor.sensor_id);
        return {
          sensor_id: sensor.sensor_id,
          sensor_name: sensor.name,
          location: sensor.location,
          zone: sensor.zone,
          latest_reading: latest ? {
            timestamp: latest.timestamp,
            timestamp_buddhist: convertToBuddhistDate(new Date(latest.timestamp)),
            moisture_percentage: latest.moisture_percentage,
            temperature_celsius: latest.temperature_celsius,
            quality: latest.quality
          } : null
        };
      })
    );

    res.json({
      data_type: 'moisture',
      request_time: new Date().toISOString(),
      request_time_buddhist: convertToBuddhistDate(new Date()),
      sensor_count: latestReadings.length,
      sensors: latestReadings
    });
  } catch (error) {
    next(error);
  }
});

/**
 * @swagger
 * /api/v1/public/moisture/statistics:
 *   get:
 *     summary: Get moisture statistics for specific date
 *     tags: [Public API]
 *     security:
 *       - ApiKeyAuth: []
 *     parameters:
 *       - in: query
 *         name: date
 *         required: true
 *         schema:
 *           type: string
 *         description: Date in Buddhist calendar format (dd/mm/yyyy)
 */
router.get('/moisture/statistics', async (req, res, next) => {
  try {
    const { date } = req.query;
    if (!date || typeof date !== 'string') {
      return res.status(400).json({ error: 'Date parameter is required (dd/mm/yyyy in Buddhist calendar)' });
    }

    const targetDate = parseBuddhistDate(date);
    const startTime = new Date(targetDate);
    startTime.setHours(0, 0, 0, 0);
    const endTime = new Date(targetDate);
    endTime.setHours(23, 59, 59, 999);

    const sensors = await repository.getSensors({ type: 'moisture', is_active: true });
    
    const statistics = await Promise.all(
      sensors.map(async (sensor) => {
        const stats = await repository.getSensorStatistics(
          sensor.sensor_id,
          startTime.toISOString(),
          endTime.toISOString()
        );
        return {
          sensor_id: sensor.sensor_id,
          sensor_name: sensor.name,
          location: sensor.location,
          zone: sensor.zone,
          date_buddhist: convertToBuddhistDate(targetDate),
          statistics: stats
        };
      })
    );

    res.json({
      data_type: 'moisture',
      request_date: date,
      sensor_count: statistics.length,
      sensors: statistics.filter(s => s.statistics.count > 0)
    });
  } catch (error) {
    next(error);
  }
});

// AOS (meteorological) data endpoints
/**
 * @swagger
 * /api/v1/public/aos/timeseries:
 *   get:
 *     summary: Get AOS meteorological time series data for all stations on specific date
 *     tags: [Public API]
 *     security:
 *       - ApiKeyAuth: []
 *     parameters:
 *       - in: query
 *         name: date
 *         required: true
 *         schema:
 *           type: string
 *         description: Date in Buddhist calendar format (dd/mm/yyyy)
 */
router.get('/aos/timeseries', async (req, res, next) => {
  try {
    const { date } = req.query;
    if (!date || typeof date !== 'string') {
      return res.status(400).json({ error: 'Date parameter is required (dd/mm/yyyy in Buddhist calendar)' });
    }

    const targetDate = parseBuddhistDate(date);
    const startTime = new Date(targetDate);
    startTime.setHours(0, 0, 0, 0);
    const endTime = new Date(targetDate);
    endTime.setHours(23, 59, 59, 999);

    // Query AOS/weather sensor data
    const query = `
      SELECT 
        s.sensor_id,
        s.name,
        s.location,
        s.zone,
        sd.timestamp,
        sd.data
      FROM sensors s
      INNER JOIN sensor_data sd ON s.sensor_id = sd.sensor_id
      WHERE s.type = 'weather'
      AND sd.timestamp >= $1 AND sd.timestamp <= $2
      ORDER BY s.sensor_id, sd.timestamp
    `;

    const result = await repository.query(query, [startTime, endTime]);

    // Group by station
    const groupedData = result.rows.reduce((acc: any, row: any) => {
      if (!acc[row.sensor_id]) {
        acc[row.sensor_id] = {
          station_id: row.sensor_id,
          station_name: row.name,
          location: row.location,
          zone: row.zone,
          date_buddhist: convertToBuddhistDate(targetDate),
          readings: []
        };
      }
      acc[row.sensor_id].readings.push({
        timestamp: row.timestamp,
        rainfall_mm: row.data.rainfall_mm,
        temperature_celsius: row.data.temperature_celsius,
        humidity_percentage: row.data.humidity_percentage,
        wind_speed_ms: row.data.wind_speed_ms,
        wind_direction_degrees: row.data.wind_direction_degrees,
        pressure_hpa: row.data.pressure_hpa
      });
      return acc;
    }, {});

    res.json({
      data_type: 'aos_meteorological',
      request_date: date,
      station_count: Object.keys(groupedData).length,
      stations: Object.values(groupedData)
    });
  } catch (error) {
    next(error);
  }
});

/**
 * @swagger
 * /api/v1/public/aos/latest:
 *   get:
 *     summary: Get latest AOS meteorological data for all stations
 *     tags: [Public API]
 *     security:
 *       - ApiKeyAuth: []
 */
router.get('/aos/latest', async (req, res, next) => {
  try {
    const sensors = await repository.getSensors({ type: 'weather', is_active: true });
    
    const latestReadings = await Promise.all(
      sensors.map(async (sensor) => {
        const query = `
          SELECT timestamp, data
          FROM sensor_data
          WHERE sensor_id = $1
          ORDER BY timestamp DESC
          LIMIT 1
        `;
        const result = await repository.query(query, [sensor.sensor_id]);
        const latest = result.rows[0];
        
        return {
          station_id: sensor.sensor_id,
          station_name: sensor.name,
          location: sensor.location,
          zone: sensor.zone,
          latest_reading: latest ? {
            timestamp: latest.timestamp,
            timestamp_buddhist: convertToBuddhistDate(new Date(latest.timestamp)),
            rainfall_mm: latest.data.rainfall_mm,
            temperature_celsius: latest.data.temperature_celsius,
            humidity_percentage: latest.data.humidity_percentage,
            wind_speed_ms: latest.data.wind_speed_ms,
            wind_direction_degrees: latest.data.wind_direction_degrees,
            pressure_hpa: latest.data.pressure_hpa
          } : null
        };
      })
    );

    res.json({
      data_type: 'aos_meteorological',
      request_time: new Date().toISOString(),
      request_time_buddhist: convertToBuddhistDate(new Date()),
      station_count: latestReadings.length,
      stations: latestReadings
    });
  } catch (error) {
    next(error);
  }
});

/**
 * @swagger
 * /api/v1/public/aos/statistics:
 *   get:
 *     summary: Get AOS meteorological statistics for specific date
 *     tags: [Public API]
 *     security:
 *       - ApiKeyAuth: []
 *     parameters:
 *       - in: query
 *         name: date
 *         required: true
 *         schema:
 *           type: string
 *         description: Date in Buddhist calendar format (dd/mm/yyyy)
 */
router.get('/aos/statistics', async (req, res, next) => {
  try {
    const { date } = req.query;
    if (!date || typeof date !== 'string') {
      return res.status(400).json({ error: 'Date parameter is required (dd/mm/yyyy in Buddhist calendar)' });
    }

    const targetDate = parseBuddhistDate(date);
    const startTime = new Date(targetDate);
    startTime.setHours(0, 0, 0, 0);
    const endTime = new Date(targetDate);
    endTime.setHours(23, 59, 59, 999);

    const sensors = await repository.getSensors({ type: 'weather', is_active: true });
    
    const statistics = await Promise.all(
      sensors.map(async (sensor) => {
        const query = `
          SELECT 
            COUNT(*) as count,
            SUM((data->>'rainfall_mm')::float) as total_rainfall,
            AVG((data->>'temperature_celsius')::float) as avg_temperature,
            MIN((data->>'temperature_celsius')::float) as min_temperature,
            MAX((data->>'temperature_celsius')::float) as max_temperature,
            AVG((data->>'humidity_percentage')::float) as avg_humidity,
            AVG((data->>'wind_speed_ms')::float) as avg_wind_speed,
            AVG((data->>'pressure_hpa')::float) as avg_pressure
          FROM sensor_data
          WHERE sensor_id = $1
          AND timestamp >= $2 AND timestamp <= $3
        `;
        const result = await repository.query(query, [sensor.sensor_id, startTime, endTime]);
        const stats = result.rows[0];
        
        return {
          station_id: sensor.sensor_id,
          station_name: sensor.name,
          location: sensor.location,
          zone: sensor.zone,
          date_buddhist: convertToBuddhistDate(targetDate),
          statistics: {
            reading_count: parseInt(stats.count),
            rainfall_total_mm: stats.total_rainfall || 0,
            temperature: {
              average: stats.avg_temperature,
              min: stats.min_temperature,
              max: stats.max_temperature
            },
            humidity_average: stats.avg_humidity,
            wind_speed_average: stats.avg_wind_speed,
            pressure_average: stats.avg_pressure
          }
        };
      })
    );

    res.json({
      data_type: 'aos_meteorological',
      request_date: date,
      station_count: statistics.length,
      stations: statistics.filter(s => s.statistics.reading_count > 0)
    });
  } catch (error) {
    next(error);
  }
});

  return router;
}