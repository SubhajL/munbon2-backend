import { Router, Request, Response, NextFunction } from 'express';
import { Logger } from 'pino';
import { TimescaleRepository } from '../repository/timescale.repository';

interface MoistureRoutesOptions {
  repository: TimescaleRepository;
  logger: Logger;
}

export function createMoistureRoutes(options: MoistureRoutesOptions): Router {
  const router = Router();
  const { repository, logger } = options;

  // Get all moisture readings with filters
  router.get('/moisture', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const {
        sensorId,
        start,
        end,
        minMoisture,
        maxMoisture,
        floodStatus,
        page = '1',
        limit = '100',
        sortOrder = 'desc'
      } = req.query;

      const offset = (parseInt(page as string) - 1) * parseInt(limit as string);
      const startTime = new Date(start as string || Date.now() - 24 * 60 * 60 * 1000);
      const endTime = new Date(end as string || Date.now());

      let whereConditions = ['time >= $1', 'time <= $2'];
      let params: any[] = [startTime, endTime];
      let paramIndex = 3;

      if (sensorId) {
        whereConditions.push(`sensor_id = $${paramIndex}`);
        params.push(sensorId);
        paramIndex++;
      }

      if (minMoisture) {
        whereConditions.push(`(moisture_surface_pct >= $${paramIndex} OR moisture_deep_pct >= $${paramIndex})`);
        params.push(parseFloat(minMoisture as string));
        paramIndex++;
      }

      if (maxMoisture) {
        whereConditions.push(`(moisture_surface_pct <= $${paramIndex} OR moisture_deep_pct <= $${paramIndex})`);
        params.push(parseFloat(maxMoisture as string));
        paramIndex++;
      }

      if (floodStatus !== undefined) {
        whereConditions.push(`flood_status = $${paramIndex}`);
        params.push(floodStatus === 'true');
        paramIndex++;
      }

      params.push(parseInt(limit as string));
      params.push(offset);

      const query = `
        SELECT 
          m.*,
          s.sensor_id as sensor_name,
          s.manufacturer
        FROM moisture_readings m
        LEFT JOIN sensor_registry s ON m.sensor_id = s.sensor_id
        WHERE ${whereConditions.join(' AND ')}
        ORDER BY time ${sortOrder}
        LIMIT $${paramIndex} OFFSET $${paramIndex + 1};
      `;

      const countQuery = `
        SELECT COUNT(*) FROM moisture_readings
        WHERE ${whereConditions.join(' AND ')};
      `;

      const [dataResult, countResult] = await Promise.all([
        repository.query(query, params),
        repository.query(countQuery, params.slice(0, -2))
      ]);

      const totalCount = parseInt(countResult.rows[0].count);
      const totalPages = Math.ceil(totalCount / parseInt(limit as string));

      res.json({
        data: dataResult.rows.map(row => ({
          sensorId: row.sensor_id,
          sensorName: row.sensor_name,
          timestamp: row.time,
          moistureSurfacePct: parseFloat(row.moisture_surface_pct),
          moistureDeepPct: parseFloat(row.moisture_deep_pct),
          tempSurfaceC: row.temp_surface_c ? parseFloat(row.temp_surface_c) : null,
          tempDeepC: row.temp_deep_c ? parseFloat(row.temp_deep_c) : null,
          ambientHumidityPct: row.ambient_humidity_pct ? parseFloat(row.ambient_humidity_pct) : null,
          ambientTempC: row.ambient_temp_c ? parseFloat(row.ambient_temp_c) : null,
          floodStatus: row.flood_status,
          voltage: row.voltage ? parseFloat(row.voltage) : null,
          location: row.location_lat && row.location_lng ? {
            lat: parseFloat(row.location_lat),
            lng: parseFloat(row.location_lng)
          } : null,
          qualityScore: parseFloat(row.quality_score)
        })),
        pagination: {
          page: parseInt(page as string),
          limit: parseInt(limit as string),
          total: totalCount,
          totalPages
        },
        filters: {
          startTime,
          endTime,
          sensorId: sensorId || null,
          minMoisture: minMoisture ? parseFloat(minMoisture as string) : null,
          maxMoisture: maxMoisture ? parseFloat(maxMoisture as string) : null,
          floodStatus: floodStatus || null
        }
      });
    } catch (error) {
      logger.error({ error }, 'Failed to get moisture readings');
      next(error);
    }
  });

  // Get aggregated moisture data
  router.get('/moisture/aggregated', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const {
        sensorId,
        start,
        end,
        interval = '1h',
        layer = 'both' // surface, deep, or both
      } = req.query;

      const startTime = new Date(start as string || Date.now() - 7 * 24 * 60 * 60 * 1000);
      const endTime = new Date(end as string || Date.now());

      let whereConditions = ['time >= $2', 'time <= $3'];
      let params: any[] = [interval, startTime, endTime];
      let paramIndex = 4;

      if (sensorId) {
        whereConditions.push(`sensor_id = $${paramIndex}`);
        params.push(sensorId);
      }

      const query = `
        SELECT 
          time_bucket($1::interval, time) AS time,
          sensor_id,
          AVG(moisture_surface_pct) as avg_moisture_surface,
          MIN(moisture_surface_pct) as min_moisture_surface,
          MAX(moisture_surface_pct) as max_moisture_surface,
          STDDEV(moisture_surface_pct) as stddev_moisture_surface,
          AVG(moisture_deep_pct) as avg_moisture_deep,
          MIN(moisture_deep_pct) as min_moisture_deep,
          MAX(moisture_deep_pct) as max_moisture_deep,
          STDDEV(moisture_deep_pct) as stddev_moisture_deep,
          AVG(temp_surface_c) as avg_temp_surface,
          AVG(temp_deep_c) as avg_temp_deep,
          AVG(ambient_temp_c) as avg_ambient_temp,
          AVG(ambient_humidity_pct) as avg_ambient_humidity,
          COUNT(*) as sample_count,
          AVG(quality_score) as avg_quality,
          SUM(CASE WHEN flood_status = true THEN 1 ELSE 0 END) as flood_count
        FROM moisture_readings
        WHERE ${whereConditions.join(' AND ')}
        GROUP BY time_bucket($1::interval, time), sensor_id
        ORDER BY time DESC;
      `;

      const result = await repository.query(query, params);

      res.json({
        aggregation: {
          interval: interval as string,
          layer: layer as string
        },
        timeRange: {
          start: startTime,
          end: endTime
        },
        data: result.rows.map(row => {
          const data: any = {
            time: row.time,
            sensorId: row.sensor_id,
            sampleCount: parseInt(row.sample_count),
            avgQuality: parseFloat(row.avg_quality),
            floodCount: parseInt(row.flood_count),
            temperature: {
              surface: row.avg_temp_surface ? parseFloat(row.avg_temp_surface) : null,
              deep: row.avg_temp_deep ? parseFloat(row.avg_temp_deep) : null,
              ambient: row.avg_ambient_temp ? parseFloat(row.avg_ambient_temp) : null
            },
            ambientHumidity: row.avg_ambient_humidity ? parseFloat(row.avg_ambient_humidity) : null
          };

          if (layer === 'surface' || layer === 'both') {
            data.surface = {
              avg: parseFloat(row.avg_moisture_surface),
              min: parseFloat(row.min_moisture_surface),
              max: parseFloat(row.max_moisture_surface),
              stddev: row.stddev_moisture_surface ? parseFloat(row.stddev_moisture_surface) : null
            };
          }

          if (layer === 'deep' || layer === 'both') {
            data.deep = {
              avg: parseFloat(row.avg_moisture_deep),
              min: parseFloat(row.min_moisture_deep),
              max: parseFloat(row.max_moisture_deep),
              stddev: row.stddev_moisture_deep ? parseFloat(row.stddev_moisture_deep) : null
            };
          }

          return data;
        })
      });
    } catch (error) {
      logger.error({ error }, 'Failed to get aggregated moisture data');
      next(error);
    }
  });

  // Get moisture alerts
  router.get('/moisture/alerts', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const {
        start,
        end,
        alertType = 'all', // low, flood, all
        lowThreshold = '20'
      } = req.query;

      const startTime = new Date(start as string || Date.now() - 24 * 60 * 60 * 1000);
      const endTime = new Date(end as string || Date.now());

      let whereConditions = ['time >= $1', 'time <= $2'];
      const params: any[] = [startTime, endTime, parseFloat(lowThreshold as string)];

      if (alertType === 'low') {
        whereConditions.push('(moisture_surface_pct < $3 OR moisture_deep_pct < $3)');
      } else if (alertType === 'flood') {
        whereConditions.push('flood_status = true');
      } else {
        whereConditions.push('((moisture_surface_pct < $3 OR moisture_deep_pct < $3) OR flood_status = true)');
      }

      const query = `
        WITH alerts AS (
          SELECT 
            m.*,
            s.sensor_id as sensor_name,
            CASE 
              WHEN flood_status = true THEN 'flood'
              WHEN moisture_surface_pct < $3 OR moisture_deep_pct < $3 THEN 'low_moisture'
              ELSE 'normal'
            END as alert_type,
            LEAST(moisture_surface_pct, moisture_deep_pct) as min_moisture
          FROM moisture_readings m
          LEFT JOIN sensor_registry s ON m.sensor_id = s.sensor_id
          WHERE ${whereConditions.join(' AND ')}
        )
        SELECT * FROM alerts
        ORDER BY time DESC;
      `;

      const result = await repository.query(query, params);

      res.json({
        timeRange: {
          start: startTime,
          end: endTime
        },
        thresholds: {
          lowMoisture: parseFloat(lowThreshold as string)
        },
        totalAlerts: result.rows.length,
        alerts: result.rows.map(row => ({
          sensorId: row.sensor_id,
          sensorName: row.sensor_name,
          timestamp: row.time,
          alertType: row.alert_type,
          moistureSurface: parseFloat(row.moisture_surface_pct),
          moistureDeep: parseFloat(row.moisture_deep_pct),
          minMoisture: parseFloat(row.min_moisture),
          floodStatus: row.flood_status,
          location: row.location_lat && row.location_lng ? {
            lat: parseFloat(row.location_lat),
            lng: parseFloat(row.location_lng)
          } : null,
          temperature: {
            surface: row.temp_surface_c ? parseFloat(row.temp_surface_c) : null,
            deep: row.temp_deep_c ? parseFloat(row.temp_deep_c) : null,
            ambient: row.ambient_temp_c ? parseFloat(row.ambient_temp_c) : null
          },
          qualityScore: parseFloat(row.quality_score)
        }))
      });
    } catch (error) {
      logger.error({ error }, 'Failed to get moisture alerts');
      next(error);
    }
  });

  // Get flood history
  router.get('/moisture/flood-history', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const {
        sensorId,
        start,
        end,
        page = '1',
        limit = '50'
      } = req.query;

      const offset = (parseInt(page as string) - 1) * parseInt(limit as string);
      const startTime = new Date(start as string || Date.now() - 30 * 24 * 60 * 60 * 1000);
      const endTime = new Date(end as string || Date.now());

      let whereConditions = ['flood_status = true', 'time >= $1', 'time <= $2'];
      let params: any[] = [startTime, endTime];
      let paramIndex = 3;

      if (sensorId) {
        whereConditions.push(`sensor_id = $${paramIndex}`);
        params.push(sensorId);
        paramIndex++;
      }

      params.push(parseInt(limit as string));
      params.push(offset);

      const query = `
        WITH flood_events AS (
          SELECT 
            m.*,
            s.sensor_id as sensor_name,
            LAG(flood_status) OVER (PARTITION BY m.sensor_id ORDER BY time) as prev_flood_status,
            LEAD(flood_status) OVER (PARTITION BY m.sensor_id ORDER BY time) as next_flood_status
          FROM moisture_readings m
          LEFT JOIN sensor_registry s ON m.sensor_id = s.sensor_id
          WHERE ${whereConditions.join(' AND ')}
        )
        SELECT * FROM flood_events
        ORDER BY time DESC
        LIMIT $${paramIndex} OFFSET $${paramIndex + 1};
      `;

      const countQuery = `
        SELECT COUNT(*) FROM moisture_readings
        WHERE flood_status = true 
          AND time >= $1 
          AND time <= $2
          ${sensorId ? `AND sensor_id = $3` : ''};
      `;

      const [dataResult, countResult] = await Promise.all([
        repository.query(query, params),
        repository.query(countQuery, sensorId ? [startTime, endTime, sensorId] : [startTime, endTime])
      ]);

      const totalCount = parseInt(countResult.rows[0].count);
      const totalPages = Math.ceil(totalCount / parseInt(limit as string));

      res.json({
        data: dataResult.rows.map(row => ({
          sensorId: row.sensor_id,
          sensorName: row.sensor_name,
          timestamp: row.time,
          eventType: !row.prev_flood_status && row.flood_status ? 'start' : 
                     row.prev_flood_status && !row.next_flood_status ? 'end' : 'ongoing',
          moistureSurface: parseFloat(row.moisture_surface_pct),
          moistureDeep: parseFloat(row.moisture_deep_pct),
          location: row.location_lat && row.location_lng ? {
            lat: parseFloat(row.location_lat),
            lng: parseFloat(row.location_lng)
          } : null,
          ambientConditions: {
            temperature: row.ambient_temp_c ? parseFloat(row.ambient_temp_c) : null,
            humidity: row.ambient_humidity_pct ? parseFloat(row.ambient_humidity_pct) : null
          }
        })),
        pagination: {
          page: parseInt(page as string),
          limit: parseInt(limit as string),
          total: totalCount,
          totalPages
        },
        summary: {
          totalFloodEvents: totalCount,
          timeRange: {
            start: startTime,
            end: endTime
          }
        }
      });
    } catch (error) {
      logger.error({ error }, 'Failed to get flood history');
      next(error);
    }
  });

  return router;
}