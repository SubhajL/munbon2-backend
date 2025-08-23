import { Router } from 'express';
import { tileController } from '../controllers/tile.controller';
import { authenticate } from '../middleware/auth';
import { authorize } from '../middleware/authorize';
import { validateRequest } from '../middleware/validate-request';
import { tileRequestSchema } from '../validators/tile.validator';
import { cacheMiddleware } from '../middleware/cache';

const router = Router();

// Public tile access (with caching)
router.get(
  '/:layer/:z/:x/:y.pbf',
  cacheMiddleware({ ttl: 3600 }), // 1 hour cache
  validateRequest(tileRequestSchema),
  tileController.getTile
);

// Tile metadata
router.get('/metadata/:layer', tileController.getTileMetadata);

// Available layers
router.get('/layers', tileController.getAvailableLayers);

// Style JSON for MapboxGL
router.get('/style/:style', tileController.getStyle);

// Admin routes - require authentication
router.use(authenticate);
router.use(authorize(['ADMIN', 'SYSTEM_ADMIN']));

// Clear tile cache
router.delete('/cache/:layer?', tileController.clearTileCache);

// Pre-generate tiles
router.post('/pregenerate', tileController.preGenerateTiles);

// Get tile generation status
router.get('/generation/status/:jobId', tileController.getGenerationStatus);

// Update tile configuration
router.put('/config/:layer', tileController.updateLayerConfig);

export { router as tileRoutes };