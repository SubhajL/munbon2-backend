import { Router } from 'express';
import { body, param, query, validationResult } from 'express-validator';
import { RidMsController } from '../controllers/rid-ms.controller';
import { authMiddleware } from '../middleware/auth.middleware';

const router = Router();
const controller = new RidMsController();

// Validation middleware
const validateRequest = (req: any, res: any, next: any) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(400).json({ errors: errors.array() });
  }
  next();
};

// Routes

/**
 * Get all shape files
 * GET /api/v1/rid-ms/shapefiles
 */
router.get(
  '/shapefiles',
  authMiddleware,
  [
    query('status')
      .optional()
      .isIn(['pending', 'processing', 'processed', 'failed']),
    query('limit').optional().isInt({ min: 1, max: 100 }).toInt(),
    query('lastKey').optional().isString(),
  ],
  validateRequest,
  controller.getShapeFiles.bind(controller)
);

/**
 * Get shape file by ID
 * GET /api/v1/rid-ms/shapefiles/:id
 */
router.get(
  '/shapefiles/:id',
  authMiddleware,
  [
    param('id').isString().withMessage('Invalid shape file ID'),
  ],
  validateRequest,
  controller.getShapeFileById.bind(controller)
);

/**
 * Get parcels by shape file ID
 * GET /api/v1/rid-ms/shapefiles/:shapeFileId/parcels
 */
router.get(
  '/shapefiles/:shapeFileId/parcels',
  authMiddleware,
  [
    param('shapeFileId').isString(),
    query('limit').optional().isInt({ min: 1, max: 1000 }).toInt(),
    query('lastKey').optional().isString(),
  ],
  validateRequest,
  controller.getParcelsByShapeFile.bind(controller)
);

/**
 * Get parcels by zone
 * GET /api/v1/rid-ms/zones/:zone/parcels
 */
router.get(
  '/zones/:zone/parcels',
  authMiddleware,
  [
    param('zone').isString(),
    query('waterDemandMethod')
      .optional()
      .isIn(['RID-MS', 'ROS', 'AWD']),
    query('limit').optional().isInt({ min: 1, max: 1000 }).toInt(),
    query('lastKey').optional().isString(),
  ],
  validateRequest,
  controller.getParcelsByZone.bind(controller)
);

/**
 * Get water demand for a parcel
 * GET /api/v1/rid-ms/parcels/:parcelId/water-demand
 */
router.get(
  '/parcels/:parcelId/water-demand',
  authMiddleware,
  [
    param('parcelId').isString(),
  ],
  validateRequest,
  controller.getParcelWaterDemand.bind(controller)
);

/**
 * Get water demand summary by zone
 * GET /api/v1/rid-ms/zones/:zone/water-demand-summary
 */
router.get(
  '/zones/:zone/water-demand-summary',
  authMiddleware,
  [
    param('zone').isString(),
  ],
  validateRequest,
  controller.getWaterDemandSummaryByZone.bind(controller)
);

/**
 * Get GeoJSON for visualization
 * GET /api/v1/rid-ms/shapefiles/:shapeFileId/geojson
 */
router.get(
  '/shapefiles/:shapeFileId/geojson',
  authMiddleware,
  [
    param('shapeFileId').isString(),
    query('includeWaterDemand').optional().isBoolean().toBoolean(),
  ],
  validateRequest,
  controller.getGeoJSON.bind(controller)
);

/**
 * Get presigned upload URL
 * POST /api/v1/rid-ms/upload-url
 */
router.post(
  '/upload-url',
  authMiddleware,
  [
    body('fileName').isString().withMessage('fileName is required'),
    body('waterDemandMethod')
      .optional()
      .isIn(['RID-MS', 'ROS', 'AWD']),
    body('processingInterval')
      .optional()
      .isIn(['daily', 'weekly', 'bi-weekly']),
  ],
  validateRequest,
  controller.getUploadUrl.bind(controller)
);

/**
 * Update water demand method for parcels
 * PUT /api/v1/rid-ms/parcels/water-demand-method
 */
router.put(
  '/parcels/water-demand-method',
  authMiddleware,
  [
    body('parcelIds')
      .isArray({ min: 1 })
      .withMessage('parcelIds must be a non-empty array'),
    body('parcelIds.*').isString(),
    body('method')
      .isIn(['RID-MS', 'ROS', 'AWD'])
      .withMessage('Method must be RID-MS, ROS, or AWD'),
  ],
  validateRequest,
  controller.updateWaterDemandMethod.bind(controller)
);

export const ridMsRoutes = router;