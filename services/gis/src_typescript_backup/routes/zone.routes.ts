import { Router } from 'express';
import { zoneController } from '../controllers/zone.controller';
import { authenticate } from '../middleware/auth';
import { authorize } from '../middleware/authorize';
import { validateRequest } from '../middleware/validate-request';
import {
  createZoneSchema,
  updateZoneSchema,
  queryZoneSchema,
  zoneIdSchema,
} from '../validators/zone.validator';

const router = Router();

// Apply authentication to all routes
router.use(authenticate);

// Get all zones
router.get('/', zoneController.getAllZones);

// Get zone by ID
router.get('/:id', validateRequest(zoneIdSchema), zoneController.getZoneById);

// Get zones by query
router.post('/query', validateRequest(queryZoneSchema), zoneController.queryZones);

// Get zone statistics
router.get('/:id/statistics', validateRequest(zoneIdSchema), zoneController.getZoneStatistics);

// Get parcels in zone
router.get('/:id/parcels', validateRequest(zoneIdSchema), zoneController.getParcelsInZone);

// Get water distribution for zone
router.get('/:id/water-distribution', validateRequest(zoneIdSchema), zoneController.getWaterDistribution);

// Protected routes - require admin role
router.use(authorize(['ADMIN', 'SYSTEM_ADMIN']));

// Create new zone
router.post('/', validateRequest(createZoneSchema), zoneController.createZone);

// Update zone
router.put('/:id', validateRequest(updateZoneSchema), zoneController.updateZone);

// Update zone geometry
router.put('/:id/geometry', validateRequest(zoneIdSchema), zoneController.updateZoneGeometry);

// Delete zone
router.delete('/:id', validateRequest(zoneIdSchema), zoneController.deleteZone);

// Bulk operations
router.post('/bulk/import', zoneController.bulkImportZones);
router.post('/bulk/update', zoneController.bulkUpdateZones);

export { router as zoneRoutes };