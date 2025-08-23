import { Router } from 'express';
import multer from 'multer';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';
import { body, param, query, validationResult } from 'express-validator';
import { ShapeFileController } from '../controllers/shapefile.controller';
import { config } from '../config';
import { authMiddleware } from '../middleware/auth.middleware';

const router = Router();
const controller = new ShapeFileController();

// Configure multer for file uploads
const storage = multer.diskStorage({
  destination: async (req, file, cb) => {
    cb(null, config.fileProcessing.uploadDir);
  },
  filename: (req, file, cb) => {
    const uniqueName = `${uuidv4()}${path.extname(file.originalname)}`;
    cb(null, uniqueName);
  },
});

const upload = multer({
  storage,
  limits: {
    fileSize: config.fileProcessing.maxFileSize,
  },
  fileFilter: (req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    if (config.fileProcessing.allowedFileTypes.includes(ext)) {
      cb(null, true);
    } else {
      cb(new Error(`File type ${ext} is not allowed`));
    }
  },
});

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
 * Upload and process shape file
 * POST /api/v1/shapefiles/upload
 */
router.post(
  '/upload',
  authMiddleware,
  upload.single('shapefile'),
  [
    body('description').optional().isString().trim(),
    body('waterDemandMethod')
      .optional()
      .isIn(['RID-MS', 'ROS', 'AWD'])
      .withMessage('Water demand method must be RID-MS, ROS, or AWD'),
    body('processingInterval')
      .optional()
      .isIn(['daily', 'weekly', 'bi-weekly'])
      .withMessage('Processing interval must be daily, weekly, or bi-weekly'),
  ],
  validateRequest,
  controller.uploadShapeFile.bind(controller)
);

/**
 * Get shape file metadata
 * GET /api/v1/shapefiles/:id
 */
router.get(
  '/:id',
  authMiddleware,
  [
    param('id').isUUID().withMessage('Invalid shape file ID'),
  ],
  validateRequest,
  controller.getShapeFileMetadata.bind(controller)
);

/**
 * List all shape files
 * GET /api/v1/shapefiles
 */
router.get(
  '/',
  authMiddleware,
  [
    query('status')
      .optional()
      .isIn(['pending', 'processing', 'processed', 'failed'])
      .withMessage('Invalid status'),
    query('page').optional().isInt({ min: 1 }).toInt(),
    query('limit').optional().isInt({ min: 1, max: 100 }).toInt(),
    query('sortBy')
      .optional()
      .isIn(['uploadDate', 'processedDate', 'fileSize', 'featureCount'])
      .withMessage('Invalid sort field'),
    query('sortOrder')
      .optional()
      .isIn(['asc', 'desc'])
      .withMessage('Sort order must be asc or desc'),
  ],
  validateRequest,
  controller.listShapeFiles.bind(controller)
);

/**
 * Get parcels from shape file
 * GET /api/v1/shapefiles/:id/parcels
 */
router.get(
  '/:id/parcels',
  authMiddleware,
  [
    param('id').isUUID().withMessage('Invalid shape file ID'),
    query('zone').optional().isString(),
    query('cropType').optional().isString(),
    query('waterDemandMethod')
      .optional()
      .isIn(['RID-MS', 'ROS', 'AWD']),
    query('page').optional().isInt({ min: 1 }).toInt(),
    query('limit').optional().isInt({ min: 1, max: 1000 }).toInt(),
  ],
  validateRequest,
  controller.getShapeFileParcels.bind(controller)
);

/**
 * Export shape file as GeoJSON
 * GET /api/v1/shapefiles/:id/export/geojson
 */
router.get(
  '/:id/export/geojson',
  authMiddleware,
  [
    param('id').isUUID().withMessage('Invalid shape file ID'),
    query('includeWaterDemand')
      .optional()
      .isBoolean()
      .toBoolean(),
  ],
  validateRequest,
  controller.exportAsGeoJSON.bind(controller)
);

/**
 * Get shape file statistics
 * GET /api/v1/shapefiles/:id/statistics
 */
router.get(
  '/:id/statistics',
  authMiddleware,
  [
    param('id').isUUID().withMessage('Invalid shape file ID'),
  ],
  validateRequest,
  controller.getShapeFileStatistics.bind(controller)
);

/**
 * Delete shape file
 * DELETE /api/v1/shapefiles/:id
 */
router.delete(
  '/:id',
  authMiddleware,
  [
    param('id').isUUID().withMessage('Invalid shape file ID'),
  ],
  validateRequest,
  controller.deleteShapeFile.bind(controller)
);

/**
 * Reprocess shape file
 * POST /api/v1/shapefiles/:id/reprocess
 */
router.post(
  '/:id/reprocess',
  authMiddleware,
  [
    param('id').isUUID().withMessage('Invalid shape file ID'),
  ],
  validateRequest,
  controller.reprocessShapeFile.bind(controller)
);

export const shapeFileRoutes = router;