import { Router, Request, Response } from 'express';
import { sensorZoneMappingService } from '../services/sensor-zone-mapping.service';
import { waterValidationService } from '../services/water-validation.service';
import { timescalePool, postgisPool } from '../config/database';

const router = Router();

/**
 * Get dashboard overview
 * GET /api/v1/dashboard/overview
 */
router.get('/overview', async (req: Request, res: Response) => {
  try {
    // Get total zones
    const zonesQuery = `
      SELECT COUNT(*) as total_zones,
             COUNT(CASE WHEN zone_type = 'irrigation' THEN 1 END) as irrigation_zones
      FROM gis.irrigation_zones
    `;
    const zonesResult = await postgisPool.query(zonesQuery);

    // Get active sensors
    const sensorsQuery = `
      SELECT 
        COUNT(*) as total_sensors,
        COUNT(CASE WHEN sensor_type = 'water_level' THEN 1 END) as water_level_sensors,
        COUNT(CASE WHEN sensor_type = 'moisture' THEN 1 END) as moisture_sensors,
        COUNT(CASE WHEN last_seen > NOW() - INTERVAL '1 hour' THEN 1 END) as active_sensors
      FROM sensor_registry
      WHERE is_active = true
    `;
    const sensorsResult = await timescalePool.query(sensorsQuery);

    // Get recent readings count
    const readingsQuery = `
      SELECT 
        (SELECT COUNT(*) FROM water_level_readings WHERE time > NOW() - INTERVAL '24 hours') as water_readings_24h,
        (SELECT COUNT(*) FROM moisture_readings WHERE time > NOW() - INTERVAL '24 hours') as moisture_readings_24h
    `;
    const readingsResult = await timescalePool.query(readingsQuery);

    const overview = {
      zones: zonesResult.rows[0],
      sensors: sensorsResult.rows[0],
      recentReadings: readingsResult.rows[0],
      lastUpdated: new Date()
    };

    res.json({ success: true, data: overview });
  } catch (error) {
    console.error('Error getting dashboard overview:', error);
    res.status(500).json({ error: 'Failed to get dashboard overview' });
  }
});

/**
 * Get zone summary with sensor coverage
 * GET /api/v1/dashboard/zone-summary
 */
router.get('/zone-summary', async (req: Request, res: Response) => {
  try {
    const query = `
      WITH zone_sensors AS (
        SELECT 
          z.zone_code,
          z.zone_name,
          z.area_hectares,
          COUNT(DISTINCT sr.sensor_id) as sensor_count,
          COUNT(DISTINCT CASE WHEN sr.sensor_type = 'water_level' THEN sr.sensor_id END) as water_sensors,
          COUNT(DISTINCT CASE WHEN sr.sensor_type = 'moisture' THEN sr.sensor_id END) as moisture_sensors
        FROM gis.irrigation_zones z
        LEFT JOIN sensor_registry sr ON 
          sr.location_lat IS NOT NULL AND 
          sr.location_lng IS NOT NULL AND
          sr.is_active = true AND
          ST_Within(
            ST_SetSRID(ST_MakePoint(sr.location_lng, sr.location_lat), 4326),
            z.boundary
          )
        WHERE z.zone_type = 'irrigation'
        GROUP BY z.zone_code, z.zone_name, z.area_hectares
      )
      SELECT * FROM zone_sensors ORDER BY zone_code
    `;

    const result = await postgisPool.query(query);

    const summary = result.rows.map(row => ({
      ...row,
      area_hectares: parseFloat(row.area_hectares),
      sensor_density: row.sensor_count > 0 
        ? (row.sensor_count / parseFloat(row.area_hectares) * 100).toFixed(2) + ' sensors/100ha'
        : 'No sensors'
    }));

    res.json({ success: true, data: summary });
  } catch (error) {
    console.error('Error getting zone summary:', error);
    res.status(500).json({ error: 'Failed to get zone summary' });
  }
});

/**
 * Get real-time water status across all zones
 * GET /api/v1/dashboard/water-status
 */
router.get('/water-status', async (req: Request, res: Response) => {
  try {
    const { cropType = 'rice', cropWeek = 1 } = req.query;

    // Get all irrigation zones
    const zonesQuery = `
      SELECT zone_code FROM gis.irrigation_zones 
      WHERE zone_type = 'irrigation'
      ORDER BY zone_code
    `;
    const zonesResult = await postgisPool.query(zonesQuery);

    // Validate each zone
    const validations = await Promise.all(
      zonesResult.rows.map(async (zone) => {
        try {
          return await waterValidationService.validateZoneWaterLevel(
            zone.zone_code,
            cropType as string,
            parseInt(cropWeek as string)
          );
        } catch (error) {
          return {
            zoneCode: zone.zone_code,
            validationStatus: 'unknown' as const,
            error: 'Failed to validate'
          };
        }
      })
    );

    // Summary statistics
    const summary = {
      total_zones: validations.length,
      sufficient: validations.filter(v => v.validationStatus === 'sufficient').length,
      deficit: validations.filter(v => v.validationStatus === 'deficit').length,
      excess: validations.filter(v => v.validationStatus === 'excess').length,
      unknown: validations.filter(v => v.validationStatus === 'unknown').length,
      validations
    };

    res.json({ success: true, data: summary });
  } catch (error) {
    console.error('Error getting water status:', error);
    res.status(500).json({ error: 'Failed to get water status' });
  }
});

/**
 * Get sensor distribution map data
 * GET /api/v1/dashboard/sensor-map
 */
router.get('/sensor-map', async (req: Request, res: Response) => {
  try {
    const query = `
      SELECT 
        sensor_id,
        sensor_type,
        location_lat as lat,
        location_lng as lng,
        last_seen,
        CASE 
          WHEN last_seen > NOW() - INTERVAL '1 hour' THEN 'active'
          WHEN last_seen > NOW() - INTERVAL '24 hours' THEN 'inactive'
          ELSE 'offline'
        END as status
      FROM sensor_registry
      WHERE location_lat IS NOT NULL 
        AND location_lng IS NOT NULL
        AND is_active = true
    `;

    const result = await timescalePool.query(query);

    const mapData = result.rows.map(row => ({
      ...row,
      lat: parseFloat(row.lat),
      lng: parseFloat(row.lng)
    }));

    res.json({ success: true, data: mapData });
  } catch (error) {
    console.error('Error getting sensor map data:', error);
    res.status(500).json({ error: 'Failed to get sensor map data' });
  }
});

export default router;