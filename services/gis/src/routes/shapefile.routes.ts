import { Router } from 'express';
import multer from 'multer';
import { ShapeFileController } from '../controllers/shapefile.controller';
import { authenticate } from '../middleware/auth';
import { authorize } from '../middleware/authorize';
import { validateRequest } from '../middleware/validate-request';
import { shapeFileUploadValidator } from '../validators/shapefile-zod.validator';

const router = Router();
const controller = new ShapeFileController();

// Configure multer for file uploads
const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 100 * 1024 * 1024, // 100MB max file size
  },
  fileFilter: (req, file, cb) => {
    // Accept .zip files (shapefiles) and .gpkg files (GeoPackage)
    const filename = file.originalname.toLowerCase();
    if (file.mimetype === 'application/zip' || filename.endsWith('.zip') ||
        file.mimetype === 'application/geopackage+sqlite3' || filename.endsWith('.gpkg')) {
      cb(null, true);
    } else {
      cb(new Error('Only .zip (shapefile) and .gpkg (GeoPackage) files are allowed'));
    }
  },
});

// Routes
router.post(
  '/upload',
  authenticate,
  authorize(['admin', 'operator']),
  upload.single('file'),
  validateRequest(shapeFileUploadValidator),
  controller.uploadShapeFile
);

router.get(
  '/uploads',
  authenticate,
  controller.listUploads
);

router.get(
  '/uploads/:uploadId',
  authenticate,
  controller.getUploadStatus
);

router.get(
  '/uploads/:uploadId/parcels',
  authenticate,
  controller.getUploadParcels
);

router.delete(
  '/uploads/:uploadId',
  authenticate,
  authorize(['admin']),
  controller.deleteUpload
);

// Public endpoint for external systems (RID)
router.post(
  '/external/upload',
  upload.single('file'),
  controller.externalUpload
);

export { router as shapeFileRoutes };