import { Router } from 'express';
import { areaController } from '@controllers/area.controller';
import { validateRequest } from '@middleware/validate-request';
import { areaValidation } from '@utils/validation/area.validation';

const router = Router();

// Get area statistics
router.get('/statistics', areaController.getAreaStatistics);

// Create new area
router.post(
  '/',
  validateRequest(areaValidation.createArea),
  areaController.createArea
);

// Import multiple areas
router.post(
  '/import',
  validateRequest(areaValidation.importAreas),
  areaController.importAreas
);

// Get area by ID
router.get(
  '/:areaId',
  validateRequest(areaValidation.getAreaById),
  areaController.getAreaById
);

// Update area
router.put(
  '/:areaId',
  validateRequest(areaValidation.updateArea),
  areaController.updateArea
);

// Delete area
router.delete(
  '/:areaId',
  validateRequest(areaValidation.deleteArea),
  areaController.deleteArea
);

// Get areas by type
router.get(
  '/type/:areaType',
  validateRequest(areaValidation.getAreasByType),
  areaController.getAreasByType
);

// Get child areas
router.get(
  '/:areaId/children',
  validateRequest(areaValidation.getChildAreas),
  areaController.getChildAreas
);

// Get area hierarchy
router.get(
  '/hierarchy/:projectId',
  validateRequest(areaValidation.getAreaHierarchy),
  areaController.getAreaHierarchy
);

// Calculate total area
router.get(
  '/:areaId/total-area',
  validateRequest(areaValidation.calculateTotalArea),
  areaController.calculateTotalArea
);

export default router;