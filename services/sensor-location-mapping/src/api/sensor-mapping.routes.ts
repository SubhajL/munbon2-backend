import { Router, Request, Response } from 'express';
import { sensorZoneMappingService } from '../services/sensor-zone-mapping.service';
import { waterValidationService } from '../services/water-validation.service';

const router = Router();

/**
 * Map a sensor to its zone/section
 * POST /api/v1/sensors/map-location
 */
router.post('/sensors/map-location', async (req: Request, res: Response) => {
  try {
    const { sensorId, lat, lng } = req.body;
    
    if (!sensorId || !lat || !lng) {
      return res.status(400).json({ 
        error: 'Missing required fields: sensorId, lat, lng' 
      });
    }

    const mapping = await sensorZoneMappingService.mapSensorToZone(
      sensorId, 
      { lat, lng }
    );

    res.json({ success: true, data: mapping });
  } catch (error) {
    console.error('Error mapping sensor:', error);
    res.status(500).json({ error: 'Failed to map sensor location' });
  }
});

/**
 * Get all sensors in a zone with latest readings
 * GET /api/v1/zones/:zoneCode/sensors
 */
router.get('/zones/:zoneCode/sensors', async (req: Request, res: Response) => {
  try {
    const { zoneCode } = req.params;
    const zoneStatus = await sensorZoneMappingService.getSensorsByZone(zoneCode);
    res.json({ success: true, data: zoneStatus });
  } catch (error) {
    console.error('Error getting zone sensors:', error);
    res.status(500).json({ error: 'Failed to get zone sensor data' });
  }
});

/**
 * Get sensors by section/irrigation block
 * GET /api/v1/sections/:sectionCode/sensors
 */
router.get('/sections/:sectionCode/sensors', async (req: Request, res: Response) => {
  try {
    const { sectionCode } = req.params;
    const sectionStatus = await sensorZoneMappingService.getSensorsBySection(sectionCode);
    res.json({ success: true, data: sectionStatus });
  } catch (error) {
    console.error('Error getting section sensors:', error);
    res.status(500).json({ error: 'Failed to get section sensor data' });
  }
});

/**
 * Validate water levels for a zone
 * POST /api/v1/zones/:zoneCode/validate-water
 */
router.post('/zones/:zoneCode/validate-water', async (req: Request, res: Response) => {
  try {
    const { zoneCode } = req.params;
    const { cropType, cropWeek } = req.body;

    if (!cropType || !cropWeek) {
      return res.status(400).json({ 
        error: 'Missing required fields: cropType, cropWeek' 
      });
    }

    const validation = await waterValidationService.validateZoneWaterLevel(
      zoneCode,
      cropType,
      cropWeek
    );

    res.json({ success: true, data: validation });
  } catch (error) {
    console.error('Error validating water level:', error);
    res.status(500).json({ error: 'Failed to validate water levels' });
  }
});

/**
 * Get zones requiring attention
 * GET /api/v1/zones/requiring-attention
 */
router.get('/zones/requiring-attention', async (req: Request, res: Response) => {
  try {
    const { cropType, cropWeek } = req.query;

    if (!cropType || !cropWeek) {
      return res.status(400).json({ 
        error: 'Missing required query params: cropType, cropWeek' 
      });
    }

    const zones = await waterValidationService.getZonesRequiringAttention(
      cropType as string,
      parseInt(cropWeek as string)
    );

    res.json({ success: true, data: zones });
  } catch (error) {
    console.error('Error getting zones requiring attention:', error);
    res.status(500).json({ error: 'Failed to get zones requiring attention' });
  }
});

/**
 * Update sensor location
 * PUT /api/v1/sensors/:sensorId/location
 */
router.put('/sensors/:sensorId/location', async (req: Request, res: Response) => {
  try {
    const { sensorId } = req.params;
    const { lat, lng } = req.body;

    if (!lat || !lng) {
      return res.status(400).json({ 
        error: 'Missing required fields: lat, lng' 
      });
    }

    const mapping = await sensorZoneMappingService.updateSensorLocation(
      sensorId,
      { lat, lng }
    );

    res.json({ success: true, data: mapping });
  } catch (error) {
    console.error('Error updating sensor location:', error);
    res.status(500).json({ error: 'Failed to update sensor location' });
  }
});

/**
 * Get recent sensor readings
 * GET /api/v1/sensors/:sensorId/readings
 */
router.get('/sensors/:sensorId/readings', async (req: Request, res: Response) => {
  try {
    const { sensorId } = req.params;
    const { hours = 24 } = req.query;

    const readings = await sensorZoneMappingService.getRecentSensorData(
      sensorId,
      parseInt(hours as string)
    );

    res.json({ success: true, data: readings });
  } catch (error) {
    console.error('Error getting sensor readings:', error);
    res.status(500).json({ error: 'Failed to get sensor readings' });
  }
});

/**
 * Validate multiple zones
 * POST /api/v1/zones/validate-multiple
 */
router.post('/zones/validate-multiple', async (req: Request, res: Response) => {
  try {
    const { zoneCodes, cropType, cropWeek } = req.body;

    if (!zoneCodes || !Array.isArray(zoneCodes) || !cropType || !cropWeek) {
      return res.status(400).json({ 
        error: 'Missing required fields: zoneCodes (array), cropType, cropWeek' 
      });
    }

    const validations = await waterValidationService.validateMultipleZones(
      zoneCodes,
      cropType,
      cropWeek
    );

    res.json({ success: true, data: validations });
  } catch (error) {
    console.error('Error validating multiple zones:', error);
    res.status(500).json({ error: 'Failed to validate multiple zones' });
  }
});

export default router;