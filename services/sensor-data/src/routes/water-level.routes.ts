import { Router, Request, Response, NextFunction } from 'express';
import { Logger } from 'pino';
import { TimescaleRepository } from '../repository/timescale.repository';

interface WaterLevelRoutesOptions {
  repository: TimescaleRepository;
  logger: Logger;
}

export function createWaterLevelRoutes(options: WaterLevelRoutesOptions): Router {
  const router = Router();
  const { repository, logger } = options;

  // Get all water level readings with filters
  router.get('/water-levels', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const {
        sensorId,
        start,
        end,
        minLevel,
        maxLevel,
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

      if (minLevel) {
        whereConditions.push(`level_cm >= $${paramIndex}`);
        params.push(parseFloat(minLevel as string));
        paramIndex++;
      }

      if (maxLevel) {
        whereConditions.push(`level_cm <= $${paramIndex}`);
        params.push(parseFloat(maxLevel as string));
        paramIndex++;
      }

      params.push(parseInt(limit as string));
      params.push(offset);

      const query = `
        SELECT 
          w.*,
          s.sensor_id as sensor_name,
          s.manufacturer
        FROM water_level_readings w
        LEFT JOIN sensor_registry s ON w.sensor_id = s.sensor_id
        WHERE ${whereConditions.join(' AND ')}
        ORDER BY time ${sortOrder}
        LIMIT $${paramIndex} OFFSET $${paramIndex + 1};
      `;

      const countQuery = `
        SELECT COUNT(*) FROM water_level_readings
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
          levelCm: parseFloat(row.level_cm),
          voltage: row.voltage ? parseFloat(row.voltage) : null,
          rssi: row.rssi,
          temperature: row.temperature ? parseFloat(row.temperature) : null,
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
          minLevel: minLevel ? parseFloat(minLevel as string) : null,
          maxLevel: maxLevel ? parseFloat(maxLevel as string) : null
        }
      });
    } catch (error) {
      logger.error({ error }, 'Failed to get water level readings');
      next(error);
    }
  });

  // Get aggregated water level data
  router.get('/water-levels/aggregated', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const {
        sensorId,
        start,
        end,
        interval = '1h',
        aggregation = 'avg'
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

      const aggregationFunctions: Record<string, string> = {
        avg: 'AVG(level_cm)',
        min: 'MIN(level_cm)',
        max: 'MAX(level_cm)',
        sum: 'SUM(level_cm)',
        count: 'COUNT(*)'
      };

      const aggFunc = aggregationFunctions[aggregation as string] || 'AVG(level_cm)';

      const query = `
        SELECT 
          time_bucket($1::interval, time) AS time,
          sensor_id,
          ${aggFunc} as value,
          COUNT(*) as sample_count,
          AVG(quality_score) as avg_quality,
          MIN(level_cm) as min_level,
          MAX(level_cm) as max_level,
          STDDEV(level_cm) as stddev_level,
          AVG(voltage) as avg_voltage
        FROM water_level_readings
        WHERE ${whereConditions.join(' AND ')}
        GROUP BY time_bucket($1::interval, time), sensor_id
        ORDER BY time DESC;
      `;

      const result = await repository.query(query, params);

      res.json({
        aggregation: {
          method: aggregation as string,
          interval: interval as string
        },
        timeRange: {
          start: startTime,
          end: endTime
        },
        data: result.rows.map(row => ({
          time: row.time,
          sensorId: row.sensor_id,
          value: parseFloat(row.value),
          sampleCount: parseInt(row.sample_count),
          avgQuality: parseFloat(row.avg_quality),
          statistics: {
            min: parseFloat(row.min_level),
            max: parseFloat(row.max_level),
            stddev: row.stddev_level ? parseFloat(row.stddev_level) : null,
            avgVoltage: row.avg_voltage ? parseFloat(row.avg_voltage) : null
          }
        }))
      });
    } catch (error) {
      logger.error({ error }, 'Failed to get aggregated water level data');
      next(error);
    }
  });

  // Get water level alerts/anomalies
  router.get('/water-levels/alerts', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const {
        start,
        end,
        severity,
        highThreshold = '25',
        lowThreshold = '5'
      } = req.query;

      const startTime = new Date(start as string || Date.now() - 24 * 60 * 60 * 1000);
      const endTime = new Date(end as string || Date.now());

      const query = `
        WITH alerts AS (
          SELECT 
            w.*,
            s.sensor_id as sensor_name,
            CASE 
              WHEN w.level_cm > $3 THEN 'high'
              WHEN w.level_cm < $4 THEN 'low'
              ELSE 'normal'
            END as alert_type,
            CASE 
              WHEN w.level_cm > $3 THEN w.level_cm - $3
              WHEN w.level_cm < $4 THEN $4 - w.level_cm
              ELSE 0
            END as deviation
          FROM water_level_readings w
          LEFT JOIN sensor_registry s ON w.sensor_id = s.sensor_id
          WHERE w.time >= $1 
            AND w.time <= $2
            AND (w.level_cm > $3 OR w.level_cm < $4)
        )
        SELECT * FROM alerts
        ${severity ? `WHERE alert_type = $5` : ''}
        ORDER BY time DESC;
      `;

      const params: any[] = [
        startTime,
        endTime,
        parseFloat(highThreshold as string),
        parseFloat(lowThreshold as string)
      ];

      if (severity) {
        params.push(severity as string);
      }

      const result = await repository.query(query, params);

      res.json({
        timeRange: {
          start: startTime,
          end: endTime
        },
        thresholds: {
          high: parseFloat(highThreshold as string),
          low: parseFloat(lowThreshold as string)
        },
        totalAlerts: result.rows.length,
        alerts: result.rows.map(row => ({
          sensorId: row.sensor_id,
          sensorName: row.sensor_name,
          timestamp: row.time,
          levelCm: parseFloat(row.level_cm),
          alertType: row.alert_type,
          deviation: parseFloat(row.deviation),
          location: row.location_lat && row.location_lng ? {
            lat: parseFloat(row.location_lat),
            lng: parseFloat(row.location_lng)
          } : null,
          voltage: row.voltage ? parseFloat(row.voltage) : null,
          rssi: row.rssi,
          qualityScore: parseFloat(row.quality_score)
        }))
      });
    } catch (error) {
      logger.error({ error }, 'Failed to get water level alerts');
      next(error);
    }
  });

  // Get water level comparison between sensors
  router.get('/water-levels/comparison', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const {
        sensorIds,
        start,
        end,
        interval = '1h'
      } = req.query;

      if (!sensorIds) {
        res.status(400).json({ error: 'sensorIds parameter is required' });
        return;
      }

      const sensorIdArray = (sensorIds as string).split(',');
      const startTime = new Date(start as string || Date.now() - 24 * 60 * 60 * 1000);
      const endTime = new Date(end as string || Date.now());

      const query = `
        SELECT 
          time_bucket($1::interval, time) AS time,
          sensor_id,
          AVG(level_cm) as avg_level,
          MIN(level_cm) as min_level,
          MAX(level_cm) as max_level,
          COUNT(*) as sample_count
        FROM water_level_readings
        WHERE sensor_id = ANY($2)
          AND time >= $3
          AND time <= $4
        GROUP BY time_bucket($1::interval, time), sensor_id
        ORDER BY time DESC, sensor_id;
      `;

      const result = await repository.query(query, [
        interval,
        sensorIdArray,
        startTime,
        endTime
      ]);

      // Group by time for easier comparison
      const dataByTime = new Map<string, any>();
      
      result.rows.forEach(row => {
        const timeKey = row.time.toISOString();
        if (!dataByTime.has(timeKey)) {
          dataByTime.set(timeKey, {
            time: row.time,
            sensors: {}
          });
        }
        
        dataByTime.get(timeKey).sensors[row.sensor_id] = {
          avgLevel: parseFloat(row.avg_level),
          minLevel: parseFloat(row.min_level),
          maxLevel: parseFloat(row.max_level),
          sampleCount: parseInt(row.sample_count)
        };
      });

      res.json({
        timeRange: {
          start: startTime,
          end: endTime
        },
        interval: interval as string,
        sensorIds: sensorIdArray,
        data: Array.from(dataByTime.values())
      });
    } catch (error) {
      logger.error({ error }, 'Failed to get water level comparison');
      next(error);
    }
  });

  return router;
}