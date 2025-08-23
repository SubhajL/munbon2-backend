import { Router } from 'express';
import { spatialController } from '../controllers/spatial.controller';
import { validateRequest } from '../middleware/validate-request';
import { 
  spatialQuerySchema,
  bufferSchema,
  unionSchema,
  intersectionSchema
} from '../validators/spatial.validator';

const router = Router();

// Spatial queries
router.post('/query/bounds', validateRequest(spatialQuerySchema), spatialController.queryByBounds);
router.post('/query/distance', validateRequest(spatialQuerySchema), spatialController.queryByDistance);
router.post('/query/intersect', validateRequest(spatialQuerySchema), spatialController.queryByIntersection);

// Spatial operations
router.post('/buffer', validateRequest(bufferSchema), spatialController.buffer);
router.post('/union', validateRequest(unionSchema), spatialController.union);
router.post('/intersection', validateRequest(intersectionSchema), spatialController.intersection);
router.post('/simplify', spatialController.simplify);
router.post('/transform', spatialController.transform);

// Spatial analysis
router.post('/area', spatialController.calculateArea);
router.post('/length', spatialController.calculateLength);
router.post('/distance', spatialController.calculateDistance);
router.get('/elevation/:lng/:lat', spatialController.getElevation);

export { router as spatialRoutes };