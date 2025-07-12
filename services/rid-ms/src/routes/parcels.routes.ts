import { Router } from 'express';
import { query, param, body, validationResult } from 'express-validator';
import { ParcelsController } from '../controllers/parcels.controller';
import { asyncHandler } from '../middleware/async-handler';

const router = Router();
const controller = new ParcelsController();

// GET /api/v1/parcels - List parcels with filters
router.get(
  '/',
  [
    query('zone').optional().isString().trim(),
    query('cropType').optional().isString().trim(),
    query('ownerName').optional().isString().trim(),
    query('waterDemandMethod').optional().isIn(['RID-MS', 'ROS', 'AWD']),
    query('limit').optional().isInt({ min: 1, max: 1000 }).toInt(),
    query('offset').optional().isInt({ min: 0 }).toInt(),
    query('sortBy').optional().isIn(['parcelId', 'zone', 'areaRai', 'createdAt']),
    query('sortOrder').optional().isIn(['asc', 'desc']),
  ],
  asyncHandler(controller.listParcels)
);

// GET /api/v1/parcels/search - Search parcels
router.get(
  '/search',
  [
    query('q').notEmpty().isString().trim(),
    query('searchFields').optional().isString(), // comma-separated fields
    query('limit').optional().isInt({ min: 1, max: 100 }).toInt(),
  ],
  asyncHandler(controller.searchParcels)
);

// GET /api/v1/parcels/at-date - Get parcels valid at specific date
router.get(
  '/at-date',
  [
    query('date').notEmpty().isISO8601(),
    query('zone').optional().isString().trim(),
    query('limit').optional().isInt({ min: 1, max: 1000 }).toInt(),
    query('offset').optional().isInt({ min: 0 }).toInt(),
  ],
  asyncHandler(controller.getParcelsAtDate)
);

// GET /api/v1/parcels/:id - Get single parcel
router.get(
  '/:id',
  [
    param('id').isUUID(),
  ],
  asyncHandler(controller.getParcelById)
);

// GET /api/v1/parcels/history/:id - Get parcel version history
router.get(
  '/history/:parcelId',
  [
    param('parcelId').notEmpty().isString(),
  ],
  asyncHandler(controller.getParcelHistory)
);

// PUT /api/v1/parcels/:id - Update parcel attributes
router.put(
  '/:id',
  [
    param('id').isUUID(),
    body('cropType').optional().isString().trim(),
    body('waterDemandMethod').optional().isIn(['RID-MS', 'ROS', 'AWD']),
    body('ownerName').optional().isString().trim(),
    body('plantingDate').optional().isISO8601(),
    body('harvestDate').optional().isISO8601(),
  ],
  asyncHandler(controller.updateParcel)
);

export const parcelsRoutes = router;