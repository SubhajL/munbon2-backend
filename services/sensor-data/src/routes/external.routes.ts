import { Router, Request, Response, NextFunction } from 'express';
import { Logger } from 'pino';
import { TimescaleRepository } from '../repository/timescale.repository';

interface ExternalRoutesOptions {
  repository: TimescaleRepository;
  logger: Logger;
}

export function createExternalRoutes(options: ExternalRoutesOptions): Router {
  const router = Router();
  const { repository, logger } = options;

  // RID-MS Integration endpoint - Get all sensor data in standardized format
  router.get('/rid-ms/sensors', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const {
        type,
        start,
        end,
        format = 'json'
      } = req.query;

      // Validate API key for external access
      const apiKey = req.headers['x-api-key'];
      if (!apiKey || apiKey !== process.env.RID_MS_API_KEY) {
        res.status(401).json({ error: 'Unauthorized - Invalid API key' });
        return;
      }

      const startTime = new Date(start as string || Date.now() - 24 * 60 * 60 * 1000);
      const endTime = new Date(end as string || Date.now());

      let whereConditions = ['s.is_active = true'];
      const params: any[] = [];

      if (type) {
        whereConditions.push(`s.sensor_type = $${params.length + 1}`);
        params.push(type);
      }

      const query = `
        SELECT 
          s.sensor_id,
          s.sensor_type,
          s.sensor_id as name,
          s.manufacturer,
          s.location_lat,
          s.location_lng,
          s.last_seen,
          s.metadata,
          (
            SELECT json_build_object(
              'total', COUNT(*),
              'lastReading', MAX(time),
              'firstReading', MIN(time)
            )
            FROM sensor_readings r 
            WHERE r.sensor_id = s.sensor_id 
              AND r.time >= $${params.length + 1} 
              AND r.time <= $${params.length + 2}
          ) as reading_stats
        FROM sensor_registry s
        WHERE ${whereConditions.join(' AND ')}
        ORDER BY s.sensor_id;
      `;

      params.push(startTime, endTime);

      const result = await repository.query(query, params);

      const responseData = {
        metadata: {
          requestTime: new Date().toISOString(),
          timeRange: {
            start: startTime.toISOString(),
            end: endTime.toISOString()
          },
          totalSensors: result.rows.length,
          format: 'RID-MS-v1.0'
        },
        sensors: result.rows.map(row => ({
          id: row.sensor_id,
          type: row.sensor_type,
          name: row.name || row.sensor_id,
          manufacturer: row.manufacturer,
          location: row.location_lat && row.location_lng ? {
            type: 'Point',
            coordinates: [parseFloat(row.location_lng), parseFloat(row.location_lat)]
          } : null,
          lastSeen: row.last_seen,
          statistics: row.reading_stats,
          metadata: row.metadata
        }))
      };

      if (format === 'csv') {
        // Convert to CSV format for compatibility
        const csv = convertToCSV(responseData.sensors);
        res.setHeader('Content-Type', 'text/csv');
        res.setHeader('Content-Disposition', 'attachment; filename=sensors.csv');
        res.send(csv);
      } else {
        res.json(responseData);
      }
    } catch (error) {
      logger.error({ error }, 'Failed to get RID-MS sensor data');
      next(error);
    }
  });

  // RID-MS Integration endpoint - Get sensor readings
  router.get('/rid-ms/readings', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const {
        sensorId,
        type,
        start,
        end,
        interval = '1h',
        format = 'json'
      } = req.query;

      // Validate API key
      const apiKey = req.headers['x-api-key'];
      if (!apiKey || apiKey !== process.env.RID_MS_API_KEY) {
        res.status(401).json({ error: 'Unauthorized - Invalid API key' });
        return;
      }

      const startTime = new Date(start as string || Date.now() - 7 * 24 * 60 * 60 * 1000);
      const endTime = new Date(end as string || Date.now());

      let whereConditions = ['time >= $2', 'time <= $3'];
      const params: any[] = [interval, startTime, endTime];
      let paramIndex = 4;

      if (sensorId) {
        whereConditions.push(`sensor_id = $${paramIndex}`);
        params.push(sensorId);
        paramIndex++;
      }

      if (type) {
        whereConditions.push(`sensor_type = $${paramIndex}`);
        params.push(type);
        paramIndex++;
      }

      // Aggregated query for RID-MS format
      const query = `
        WITH aggregated_data AS (
          SELECT 
            time_bucket($1::interval, time) AS time_bucket,
            sensor_id,
            sensor_type,
            location_lat,
            location_lng,
            AVG(CASE 
              WHEN sensor_type = 'water-level' THEN (value->>'level')::numeric
              WHEN sensor_type = 'moisture' THEN (value->>'humid_hi')::numeric
              ELSE NULL
            END) as primary_value,
            AVG(CASE 
              WHEN sensor_type = 'moisture' THEN (value->>'humid_low')::numeric
              ELSE NULL
            END) as secondary_value,
            AVG(quality_score) as avg_quality,
            COUNT(*) as sample_count
          FROM sensor_readings
          WHERE ${whereConditions.join(' AND ')}
          GROUP BY time_bucket, sensor_id, sensor_type, location_lat, location_lng
        )
        SELECT 
          ad.*,
          s.sensor_id as sensor_name,
          s.manufacturer
        FROM aggregated_data ad
        LEFT JOIN sensor_registry s ON ad.sensor_id = s.sensor_id
        ORDER BY time_bucket DESC, sensor_id;
      `;

      const result = await repository.query(query, params);

      const responseData = {
        metadata: {
          requestTime: new Date().toISOString(),
          timeRange: {
            start: startTime.toISOString(),
            end: endTime.toISOString()
          },
          aggregation: {
            interval: interval as string,
            method: 'average'
          },
          totalRecords: result.rows.length
        },
        readings: result.rows.map(row => {
          const reading: any = {
            timestamp: row.time_bucket,
            sensorId: row.sensor_id,
            sensorName: row.sensor_name,
            sensorType: row.sensor_type,
            location: row.location_lat && row.location_lng ? {
              type: 'Point',
              coordinates: [parseFloat(row.location_lng), parseFloat(row.location_lat)]
            } : null,
            sampleCount: parseInt(row.sample_count),
            qualityScore: parseFloat(row.avg_quality)
          };

          if (row.sensor_type === 'water-level') {
            reading.waterLevelCm = row.primary_value ? parseFloat(row.primary_value) : null;
          } else if (row.sensor_type === 'moisture') {
            reading.moistureSurfacePct = row.primary_value ? parseFloat(row.primary_value) : null;
            reading.moistureDeepPct = row.secondary_value ? parseFloat(row.secondary_value) : null;
          }

          return reading;
        })
      };

      if (format === 'csv') {
        const csv = convertReadingsToCSV(responseData.readings);
        res.setHeader('Content-Type', 'text/csv');
        res.setHeader('Content-Disposition', 'attachment; filename=readings.csv');
        res.send(csv);
      } else {
        res.json(responseData);
      }
    } catch (error) {
      logger.error({ error }, 'Failed to get RID-MS readings');
      next(error);
    }
  });

  // RID-MS Integration endpoint - Get spatial data for water demand analysis
  router.get('/rid-ms/spatial', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const {
        bounds, // Format: minLng,minLat,maxLng,maxLat
        type,
        includeReadings = 'false'
      } = req.query;

      // Validate API key
      const apiKey = req.headers['x-api-key'];
      if (!apiKey || apiKey !== process.env.RID_MS_API_KEY) {
        res.status(401).json({ error: 'Unauthorized - Invalid API key' });
        return;
      }

      let whereConditions = ['s.location_lat IS NOT NULL', 's.location_lng IS NOT NULL', 's.is_active = true'];
      const params: any[] = [];

      if (bounds) {
        const [minLng, minLat, maxLng, maxLat] = (bounds as string).split(',').map(parseFloat);
        whereConditions.push(`s.location_lat >= $${params.length + 1}`);
        whereConditions.push(`s.location_lat <= $${params.length + 2}`);
        whereConditions.push(`s.location_lng >= $${params.length + 3}`);
        whereConditions.push(`s.location_lng <= $${params.length + 4}`);
        params.push(minLat, maxLat, minLng, maxLng);
      }

      if (type) {
        whereConditions.push(`s.sensor_type = $${params.length + 1}`);
        params.push(type);
      }

      const query = `
        SELECT 
          s.*,
          ${includeReadings === 'true' ? `
          (
            SELECT json_agg(json_build_object(
              'time', r.time,
              'value', CASE 
                WHEN s.sensor_type = 'water-level' THEN (r.value->>'level')::numeric
                WHEN s.sensor_type = 'moisture' THEN (r.value->>'humid_hi')::numeric
                ELSE NULL
              END,
              'quality', r.quality_score
            ) ORDER BY r.time DESC)
            FROM (
              SELECT * FROM sensor_readings sr 
              WHERE sr.sensor_id = s.sensor_id 
              ORDER BY time DESC 
              LIMIT 10
            ) r
          ) as recent_readings,
          ` : ''}
          ST_AsGeoJSON(ST_MakePoint(s.location_lng, s.location_lat))::json as geojson
        FROM sensor_registry s
        WHERE ${whereConditions.join(' AND ')};
      `;

      const result = await repository.query(query, params);

      // Format as GeoJSON FeatureCollection
      const geoJsonResponse = {
        type: 'FeatureCollection',
        metadata: {
          requestTime: new Date().toISOString(),
          totalFeatures: result.rows.length,
          bounds: bounds || 'all'
        },
        features: result.rows.map(row => ({
          type: 'Feature',
          id: row.sensor_id,
          geometry: row.geojson,
          properties: {
            sensorId: row.sensor_id,
            sensorType: row.sensor_type,
            name: row.name || row.sensor_id,
            manufacturer: row.manufacturer,
            lastSeen: row.last_seen,
            isActive: row.is_active,
            metadata: row.metadata,
            recentReadings: includeReadings === 'true' ? row.recent_readings : undefined
          }
        }))
      };

      res.json(geoJsonResponse);
    } catch (error) {
      logger.error({ error }, 'Failed to get RID-MS spatial data');
      next(error);
    }
  });

  // Webhook endpoint for RID-MS to register for data updates
  router.post('/rid-ms/webhooks', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const apiKey = req.headers['x-api-key'];
      if (!apiKey || apiKey !== process.env.RID_MS_API_KEY) {
        res.status(401).json({ error: 'Unauthorized - Invalid API key' });
        return;
      }

      const { url, events, filters } = req.body;

      // TODO: Implement webhook registration logic
      // This would typically store the webhook configuration in a database
      // and trigger notifications when matching events occur

      logger.info({
        webhook: { url, events, filters }
      }, 'RID-MS webhook registered');

      res.json({
        webhookId: `webhook_${Date.now()}`,
        url,
        events,
        filters,
        status: 'active',
        createdAt: new Date().toISOString()
      });
    } catch (error) {
      logger.error({ error }, 'Failed to register RID-MS webhook');
      next(error);
    }
  });

  return router;
}

// Helper function to convert to CSV
function convertToCSV(data: any[]): string {
  if (data.length === 0) return '';
  
  const headers = ['sensor_id', 'sensor_type', 'name', 'manufacturer', 'latitude', 'longitude', 'last_seen'];
  const rows = data.map(item => [
    item.id,
    item.type,
    item.name,
    item.manufacturer,
    item.location ? item.location.coordinates[1] : '',
    item.location ? item.location.coordinates[0] : '',
    item.lastSeen
  ]);

  return [
    headers.join(','),
    ...rows.map(row => row.map(val => `"${val || ''}"`).join(','))
  ].join('\n');
}

function convertReadingsToCSV(data: any[]): string {
  if (data.length === 0) return '';
  
  const headers = ['timestamp', 'sensor_id', 'sensor_name', 'sensor_type', 'latitude', 'longitude', 'value', 'quality_score'];
  const rows = data.map(item => [
    item.timestamp,
    item.sensorId,
    item.sensorName,
    item.sensorType,
    item.location ? item.location.coordinates[1] : '',
    item.location ? item.location.coordinates[0] : '',
    item.waterLevelCm || item.moistureSurfacePct || '',
    item.qualityScore
  ]);

  return [
    headers.join(','),
    ...rows.map(row => row.map(val => `"${val || ''}"`).join(','))
  ].join('\n');
}