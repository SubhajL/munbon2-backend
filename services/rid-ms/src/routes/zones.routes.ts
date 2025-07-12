import { Router } from 'express';
import { param, query, validationResult } from 'express-validator';
import { ZonesController } from '../controllers/zones.controller';
import { asyncHandler } from '../middleware/async-handler';

const router = Router();
const controller = new ZonesController();

// GET /api/v1/zones - List all zones with summary
router.get(
  '/',
  [
    query('includeStats').optional().isBoolean().toBoolean(),
  ],
  asyncHandler(controller.listZones)
);

// GET /api/v1/zones/:zone/parcels - Get all parcels in a zone
router.get(
  '/:zone/parcels',
  [
    param('zone').notEmpty().isString().trim(),
    query('cropType').optional().isString().trim(),
    query('waterDemandMethod').optional().isIn(['RID-MS', 'ROS', 'AWD']),
    query('limit').optional().isInt({ min: 1, max: 1000 }).toInt(),
    query('offset').optional().isInt({ min: 0 }).toInt(),
  ],
  asyncHandler(controller.getZoneParcels)
);

// GET /api/v1/zones/:zone/summary - Get zone summary
router.get(
  '/:zone/summary',
  [
    param('zone').notEmpty().isString().trim(),
    query('date').optional().isISO8601(),
  ],
  asyncHandler(controller.getZoneSummary)
);

// GET /api/v1/zones/:zone/geojson - Export zone as GeoJSON
router.get(
  '/:zone/geojson',
  [
    param('zone').notEmpty().isString().trim(),
    query('includeWaterDemand').optional().isBoolean().toBoolean(),
    query('simplify').optional().isBoolean().toBoolean(),
    query('precision').optional().isInt({ min: 0, max: 10 }).toInt(),
  ],
  asyncHandler(controller.getZoneGeoJSON)
);

// GET /api/v1/zones/:zone/changes - Get zone changes over time
router.get(
  '/:zone/changes',
  [
    param('zone').notEmpty().isString().trim(),
    query('startDate').notEmpty().isISO8601(),
    query('endDate').notEmpty().isISO8601(),
  ],
  asyncHandler(controller.getZoneChanges)
);

export const zonesRoutes = router;