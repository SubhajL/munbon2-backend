import { Router } from 'express';
import { parcelController } from '../controllers/parcel.controller';
import { authenticate } from '../middleware/auth';
import { authorize } from '../middleware/authorize';
import { validateRequest } from '../middleware/validate-request';
import {
  createParcelSchema,
  updateParcelSchema,
  queryParcelSchema,
  parcelIdSchema,
  transferOwnershipSchema,
} from '../validators/parcel.validator';

const router = Router();

// Apply authentication to all routes
router.use(authenticate);

// Public routes (authenticated users)
router.get('/', parcelController.getAllParcels);
router.get('/:id', validateRequest(parcelIdSchema), parcelController.getParcelById);
router.post('/query', validateRequest(queryParcelSchema), parcelController.queryParcels);
router.get('/:id/history', validateRequest(parcelIdSchema), parcelController.getParcelHistory);
router.get('/owner/:ownerId', parcelController.getParcelsByOwner);

// Farmer routes
router.get('/:id/crop-plan', 
  validateRequest(parcelIdSchema), 
  authorize(['FARMER', 'STAFF', 'ADMIN']), 
  parcelController.getCropPlan
);

router.put('/:id/crop-plan', 
  validateRequest(parcelIdSchema), 
  authorize(['FARMER', 'STAFF', 'ADMIN']), 
  parcelController.updateCropPlan
);

// Administrative routes
router.use(authorize(['STAFF', 'ADMIN', 'SYSTEM_ADMIN']));

router.post('/', validateRequest(createParcelSchema), parcelController.createParcel);
router.put('/:id', validateRequest(updateParcelSchema), parcelController.updateParcel);
router.put('/:id/geometry', validateRequest(parcelIdSchema), parcelController.updateParcelGeometry);

// Ownership transfer
router.post('/:id/transfer', 
  validateRequest(transferOwnershipSchema), 
  parcelController.transferOwnership
);

// Admin only routes
router.use(authorize(['ADMIN', 'SYSTEM_ADMIN']));

router.delete('/:id', validateRequest(parcelIdSchema), parcelController.deleteParcel);
router.post('/bulk/import', parcelController.bulkImportParcels);
router.put('/bulk/update', parcelController.bulkUpdateParcels);
router.post('/merge', parcelController.mergeParcels);
router.post('/:id/split', validateRequest(parcelIdSchema), parcelController.splitParcel);

export { router as parcelRoutes };