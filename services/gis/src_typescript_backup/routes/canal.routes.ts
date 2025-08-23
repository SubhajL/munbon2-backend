import { Router } from 'express';
import { canalController } from '../controllers/canal.controller';
import { authenticate } from '../middleware/auth';
import { authorize } from '../middleware/authorize';
import { validateRequest } from '../middleware/validate-request';
import {
  createCanalSchema,
  updateCanalSchema,
  queryCanalSchema,
  canalIdSchema,
  flowUpdateSchema,
} from '../validators/canal.validator';

const router = Router();

// Apply authentication to all routes
router.use(authenticate);

// Public routes (authenticated users)
router.get('/', canalController.getAllCanals);
router.get('/:id', validateRequest(canalIdSchema), canalController.getCanalById);
router.post('/query', validateRequest(queryCanalSchema), canalController.queryCanals);
router.get('/:id/flow-history', validateRequest(canalIdSchema), canalController.getFlowHistory);
router.get('/:id/connected-gates', validateRequest(canalIdSchema), canalController.getConnectedGates);
router.get('/network/topology', canalController.getNetworkTopology);

// Staff routes
router.use(authorize(['STAFF', 'OPERATOR', 'ADMIN', 'SYSTEM_ADMIN']));

router.put('/:id/status', validateRequest(canalIdSchema), canalController.updateCanalStatus);
router.post('/:id/flow', validateRequest(flowUpdateSchema), canalController.updateFlowRate);
router.get('/:id/maintenance-history', validateRequest(canalIdSchema), canalController.getMaintenanceHistory);

// Administrative routes
router.use(authorize(['ADMIN', 'SYSTEM_ADMIN']));

router.post('/', validateRequest(createCanalSchema), canalController.createCanal);
router.put('/:id', validateRequest(updateCanalSchema), canalController.updateCanal);
router.put('/:id/geometry', validateRequest(canalIdSchema), canalController.updateCanalGeometry);
router.delete('/:id', validateRequest(canalIdSchema), canalController.deleteCanal);

// Network analysis routes
router.post('/network/analyze', canalController.analyzeNetwork);
router.post('/network/optimize-flow', canalController.optimizeFlow);
router.get('/network/bottlenecks', canalController.identifyBottlenecks);

// Bulk operations
router.post('/bulk/import', canalController.bulkImportCanals);
router.put('/bulk/update', canalController.bulkUpdateCanals);

export { router as canalRoutes };