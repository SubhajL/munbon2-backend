import { Router, Request, Response, NextFunction } from 'express';
import { Logger } from 'pino';
import { TimescaleRepository } from '../repository/timescale.repository';
import { SensorDataService } from '../services/sensor-data.service';

interface SensorRoutesOptions {
  repository: TimescaleRepository;
  sensorDataService: SensorDataService;
  logger: Logger;
}

export function createSensorRoutes(options: SensorRoutesOptions): Router {
  const router = Router();
  const { repository, sensorDataService, logger } = options;

  /**
   * @swagger
   * /api/v1/sensors:
   *   get:
   *     summary: Get all sensors with pagination
   *     tags: [Sensors]
   *     parameters:
   *       - in: query
   *         name: page
   *         schema:
   *           type: integer
   *           default: 1
   *         description: Page number
   *       - in: query
   *         name: limit
   *         schema:
   *           type: integer
   *           default: 20
   *         description: Number of items per page
   *       - in: query
   *         name: type
   *         schema:
   *           type: string
   *           enum: [water-level, moisture]
   *         description: Filter by sensor type
   *       - in: query
   *         name: active
   *         schema:
   *           type: boolean
   *         description: Filter by active status
   *       - in: query
   *         name: sortBy
   *         schema:
   *           type: string
   *           default: last_seen
   *         description: Sort field
   *       - in: query
   *         name: sortOrder
   *         schema:
   *           type: string
   *           enum: [asc, desc]
   *           default: desc
   *         description: Sort order
   *     responses:
   *       200:
   *         description: List of sensors
   *         content:
   *           application/json:
   *             schema:
   *               type: object
   *               properties:
   *                 data:
   *                   type: array
   *                   items:
   *                     $ref: '#/components/schemas/Sensor'
   *                 pagination:
   *                   $ref: '#/components/schemas/Pagination'
   *       500:
   *         description: Internal server error
   *         content:
   *           application/json:
   *             schema:
   *               $ref: '#/components/schemas/Error'
   */
  router.get('/sensors', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { 
        page = '1', 
        limit = '20', 
        type,
        active,
        sortBy = 'last_seen',
        sortOrder = 'desc'
      } = req.query;

      const offset = (parseInt(page as string) - 1) * parseInt(limit as string);
      
      const query = `
        SELECT 
          s.*,
          (SELECT COUNT(*) FROM sensor_readings r WHERE r.sensor_id = s.sensor_id) as total_readings,
          (SELECT MAX(time) FROM sensor_readings r WHERE r.sensor_id = s.sensor_id) as last_reading
        FROM sensor_registry s
        WHERE 1=1
          ${type ? `AND sensor_type = $3` : ''}
          ${active !== undefined ? `AND is_active = $${type ? 4 : 3}` : ''}
        ORDER BY ${sortBy} ${sortOrder}
        LIMIT $1 OFFSET $2;
      `;

      const countQuery = `
        SELECT COUNT(*) FROM sensor_registry s
        WHERE 1=1
          ${type ? `AND sensor_type = $1` : ''}
          ${active !== undefined ? `AND is_active = $${type ? 2 : 1}` : ''};
      `;

      const params: any[] = [parseInt(limit as string), offset];
      const countParams: any[] = [];
      
      if (type) {
        params.push(type as string);
        countParams.push(type as string);
      }
      if (active !== undefined) {
        params.push(active === 'true');
        countParams.push(active === 'true');
      }

      const [sensorsResult, countResult] = await Promise.all([
        repository.query(query, params),
        repository.query(countQuery, countParams)
      ]);

      const totalCount = parseInt(countResult.rows[0].count);
      const totalPages = Math.ceil(totalCount / parseInt(limit as string));

      res.json({
        data: sensorsResult.rows.map(formatSensorResponse),
        pagination: {
          page: parseInt(page as string),
          limit: parseInt(limit as string),
          total: totalCount,
          totalPages
        }
      });
    } catch (error) {
      logger.error({ error }, 'Failed to get sensors');
      next(error);
    }
  });

  // Get sensor by ID
  router.get('/sensors/:sensorId', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { sensorId } = req.params;
      
      const query = `
        SELECT 
          s.*,
          (SELECT COUNT(*) FROM sensor_readings r WHERE r.sensor_id = s.sensor_id) as total_readings,
          (SELECT MAX(time) FROM sensor_readings r WHERE r.sensor_id = s.sensor_id) as last_reading
        FROM sensor_registry s
        WHERE sensor_id = $1;
      `;
      
      const result = await repository.query(query, [sensorId]);
      
      if (result.rows.length === 0) {
        res.status(404).json({ error: 'Sensor not found' });
        return;
      }

      res.json({
        data: formatSensorResponse(result.rows[0])
      });
    } catch (error) {
      logger.error({ error }, 'Failed to get sensor');
      next(error);
    }
  });

  // Get sensor readings with time range and aggregation
  router.get('/sensors/:sensorId/readings', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { sensorId } = req.params;
      const { 
        start,
        end,
        aggregation,
        interval = '1h',
        limit = '1000'
      } = req.query;

      const startTime = new Date(start as string || Date.now() - 24 * 60 * 60 * 1000);
      const endTime = new Date(end as string || Date.now());

      if (aggregation) {
        // Aggregated data
        const query = `
          SELECT 
            time_bucket($1::interval, time) AS time,
            sensor_id,
            sensor_type,
            AVG((value->>'level')::numeric) as avg_level,
            MIN((value->>'level')::numeric) as min_level,
            MAX((value->>'level')::numeric) as max_level,
            AVG((value->>'humid_hi')::numeric) as avg_moisture_surface,
            AVG((value->>'humid_low')::numeric) as avg_moisture_deep,
            COUNT(*) as sample_count,
            AVG(quality_score) as avg_quality
          FROM sensor_readings
          WHERE sensor_id = $2 
            AND time >= $3 
            AND time <= $4
          GROUP BY time_bucket($1::interval, time), sensor_id, sensor_type
          ORDER BY time DESC
          LIMIT $5;
        `;
        
        const result = await repository.query(query, [
          interval,
          sensorId,
          startTime,
          endTime,
          parseInt(limit as string)
        ]);

        res.json({
          sensorId,
          startTime,
          endTime,
          aggregation: {
            method: aggregation,
            interval
          },
          data: result.rows
        });
      } else {
        // Raw data
        const data = await sensorDataService.getSensorData(
          sensorId,
          startTime,
          endTime
        );

        res.json({
          sensorId,
          startTime,
          endTime,
          count: data.length,
          data: data.slice(0, parseInt(limit as string))
        });
      }
    } catch (error) {
      logger.error({ error }, 'Failed to get sensor readings');
      next(error);
    }
  });

  // Get latest reading for a sensor
  router.get('/sensors/:sensorId/latest', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { sensorId } = req.params;
      
      // Get sensor info
      const sensorQuery = `
        SELECT * FROM sensor_registry WHERE sensor_id = $1;
      `;
      
      const sensorResult = await repository.query(sensorQuery, [sensorId]);
      
      if (sensorResult.rows.length === 0) {
        res.status(404).json({ error: 'Sensor not found' });
        return;
      }

      const sensor = sensorResult.rows[0];
      let latestReading = null;

      // Get type-specific latest reading
      if (sensor.sensor_type === 'water-level') {
        const query = `
          SELECT * FROM water_level_readings 
          WHERE sensor_id = $1 
          ORDER BY time DESC 
          LIMIT 1;
        `;
        const result = await repository.query(query, [sensorId]);
        if (result.rows.length > 0) {
          latestReading = {
            type: 'water-level',
            timestamp: result.rows[0].time,
            level: result.rows[0].level_cm,
            voltage: result.rows[0].voltage,
            rssi: result.rows[0].rssi,
            qualityScore: result.rows[0].quality_score
          };
        }
      } else if (sensor.sensor_type === 'moisture') {
        const query = `
          SELECT * FROM moisture_readings 
          WHERE sensor_id = $1 
          ORDER BY time DESC 
          LIMIT 1;
        `;
        const result = await repository.query(query, [sensorId]);
        if (result.rows.length > 0) {
          latestReading = {
            type: 'moisture',
            timestamp: result.rows[0].time,
            moistureSurface: result.rows[0].moisture_surface_pct,
            moistureDeep: result.rows[0].moisture_deep_pct,
            tempSurface: result.rows[0].temp_surface_c,
            tempDeep: result.rows[0].temp_deep_c,
            ambientHumidity: result.rows[0].ambient_humidity_pct,
            ambientTemp: result.rows[0].ambient_temp_c,
            floodStatus: result.rows[0].flood_status,
            voltage: result.rows[0].voltage,
            qualityScore: result.rows[0].quality_score
          };
        }
      }

      // Fallback to generic sensor_readings if no specific reading found
      if (!latestReading) {
        const query = `
          SELECT * FROM sensor_readings 
          WHERE sensor_id = $1 
          ORDER BY time DESC 
          LIMIT 1;
        `;
        const result = await repository.query(query, [sensorId]);
        if (result.rows.length > 0) {
          latestReading = {
            type: sensor.sensor_type,
            timestamp: result.rows[0].time,
            data: result.rows[0].value,
            qualityScore: result.rows[0].quality_score
          };
        }
      }

      res.json({
        sensor: formatSensorResponse(sensor),
        latestReading
      });
    } catch (error) {
      logger.error({ error }, 'Failed to get latest reading');
      next(error);
    }
  });

  // Get statistics for a sensor
  router.get('/sensors/:sensorId/statistics', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { sensorId } = req.params;
      const { period = '7d' } = req.query;

      const periodMap: Record<string, string> = {
        '1h': '1 hour',
        '24h': '24 hours',
        '7d': '7 days',
        '30d': '30 days',
        '90d': '90 days'
      };

      const intervalStr = periodMap[period as string] || '7 days';

      const query = `
        WITH sensor_data AS (
          SELECT 
            sensor_type,
            value,
            quality_score,
            time
          FROM sensor_readings
          WHERE sensor_id = $1
            AND time >= NOW() - INTERVAL '${intervalStr}'
        )
        SELECT 
          sensor_type,
          COUNT(*) as total_readings,
          AVG(quality_score) as avg_quality_score,
          MIN(time) as first_reading,
          MAX(time) as last_reading,
          -- Water level statistics
          AVG((value->>'level')::numeric) as avg_water_level,
          MIN((value->>'level')::numeric) as min_water_level,
          MAX((value->>'level')::numeric) as max_water_level,
          STDDEV((value->>'level')::numeric) as stddev_water_level,
          -- Moisture statistics
          AVG((value->>'humid_hi')::numeric) as avg_moisture_surface,
          AVG((value->>'humid_low')::numeric) as avg_moisture_deep,
          MIN((value->>'humid_hi')::numeric) as min_moisture_surface,
          MAX((value->>'humid_hi')::numeric) as max_moisture_surface,
          MIN((value->>'humid_low')::numeric) as min_moisture_deep,
          MAX((value->>'humid_low')::numeric) as max_moisture_deep
        FROM sensor_data
        GROUP BY sensor_type;
      `;

      const result = await repository.query(query, [sensorId]);

      if (result.rows.length === 0) {
        res.status(404).json({ error: 'No data found for sensor' });
        return;
      }

      const stats = result.rows[0];
      const response: any = {
        sensorId,
        period: period as string,
        totalReadings: parseInt(stats.total_readings),
        avgQualityScore: parseFloat(stats.avg_quality_score),
        firstReading: stats.first_reading,
        lastReading: stats.last_reading
      };

      if (stats.sensor_type === 'water-level') {
        response.waterLevel = {
          average: parseFloat(stats.avg_water_level),
          minimum: parseFloat(stats.min_water_level),
          maximum: parseFloat(stats.max_water_level),
          standardDeviation: parseFloat(stats.stddev_water_level)
        };
      } else if (stats.sensor_type === 'moisture') {
        response.moisture = {
          surface: {
            average: parseFloat(stats.avg_moisture_surface),
            minimum: parseFloat(stats.min_moisture_surface),
            maximum: parseFloat(stats.max_moisture_surface)
          },
          deep: {
            average: parseFloat(stats.avg_moisture_deep),
            minimum: parseFloat(stats.min_moisture_deep),
            maximum: parseFloat(stats.max_moisture_deep)
          }
        };
      }

      res.json(response);
    } catch (error) {
      logger.error({ error }, 'Failed to get sensor statistics');
      next(error);
    }
  });

  // Update sensor configuration
  router.patch('/sensors/:sensorId', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { sensorId } = req.params;
      const { 
        name,
        description,
        metadata,
        isActive
      } = req.body;

      const updates = [];
      const params = [sensorId];
      let paramIndex = 2;

      if (name !== undefined) {
        updates.push(`name = $${paramIndex}`);
        params.push(name);
        paramIndex++;
      }

      if (description !== undefined) {
        updates.push(`description = $${paramIndex}`);
        params.push(description);
        paramIndex++;
      }

      if (metadata !== undefined) {
        updates.push(`metadata = metadata || $${paramIndex}`);
        params.push(metadata);
        paramIndex++;
      }

      if (isActive !== undefined) {
        updates.push(`is_active = $${paramIndex}`);
        params.push(isActive);
        paramIndex++;
      }

      if (updates.length === 0) {
        res.status(400).json({ error: 'No updates provided' });
        return;
      }

      const query = `
        UPDATE sensor_registry
        SET ${updates.join(', ')}, updated_at = CURRENT_TIMESTAMP
        WHERE sensor_id = $1
        RETURNING *;
      `;

      const result = await repository.query(query, params);

      if (result.rows.length === 0) {
        res.status(404).json({ error: 'Sensor not found' });
        return;
      }

      res.json({
        data: formatSensorResponse(result.rows[0])
      });
    } catch (error) {
      logger.error({ error }, 'Failed to update sensor');
      next(error);
    }
  });

  return router;
}

function formatSensorResponse(row: any): any {
  return {
    id: row.sensor_id,
    type: row.sensor_type,
    name: row.name,
    description: row.description,
    manufacturer: row.manufacturer,
    location: row.location_lat && row.location_lng ? {
      lat: parseFloat(row.location_lat),
      lng: parseFloat(row.location_lng)
    } : null,
    isActive: row.is_active,
    lastSeen: row.last_seen,
    metadata: row.metadata,
    totalReadings: row.total_readings ? parseInt(row.total_readings) : 0,
    lastReading: row.last_reading,
    createdAt: row.created_at,
    updatedAt: row.updated_at
  };
}