import { Router } from 'express';
import { query, body, validationResult } from 'express-validator';
import { ExportController } from '../controllers/export.controller';
import { asyncHandler } from '../middleware/async-handler';

const router = Router();
const controller = new ExportController();

// GET /api/v1/export/parcels/geojson - Export parcels as GeoJSON
router.get(
  '/parcels/geojson',
  [
    query('zone').optional().isString().trim(),
    query('cropType').optional().isString().trim(),
    query('waterDemandMethod').optional().isIn(['RID-MS', 'ROS', 'AWD']),
    query('includeWaterDemand').optional().isBoolean().toBoolean(),
    query('limit').optional().isInt({ min: 1, max: 10000 }).toInt(),
    query('simplify').optional().isBoolean().toBoolean(),
    query('precision').optional().isInt({ min: 0, max: 10 }).toInt(),
  ],
  asyncHandler(controller.exportParcelsGeoJSON)
);

// GET /api/v1/export/zones/geojson - Export zones as GeoJSON
router.get(
  '/zones/geojson',
  [
    query('includeStats').optional().isBoolean().toBoolean(),
    query('includeWaterDemand').optional().isBoolean().toBoolean(),
  ],
  asyncHandler(controller.exportZonesGeoJSON)
);

// GET /api/v1/export/water-demand/geojson - Export water demand heatmap
router.get(
  '/water-demand/geojson',
  [
    query('zone').optional().isString().trim(),
    query('method').optional().isIn(['RID-MS', 'ROS', 'AWD']),
    query('date').optional().isISO8601(),
    query('resolution').optional().isIn(['high', 'medium', 'low']),
  ],
  asyncHandler(controller.exportWaterDemandHeatmap)
);

// POST /api/v1/export/custom - Custom GeoJSON export
router.post(
  '/custom',
  [
    body('type').isIn(['parcels', 'zones', 'water-demand']),
    body('filters').optional().isObject(),
    body('attributes').optional().isArray(),
    body('attributes.*').isString(),
    body('format').optional().isIn(['geojson', 'csv', 'kml']),
    body('simplify').optional().isBoolean(),
    body('precision').optional().isInt({ min: 0, max: 10 }),
  ],
  asyncHandler(controller.customExport)
);

export const exportRoutes = router;