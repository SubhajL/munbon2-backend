import { Router } from 'express';
import { userController } from '../controllers/user.controller';
import { authenticate } from '../middleware/authenticate';
import { authorize } from '../middleware/authorize';
import { validateRequest } from '../middleware/validate-request';
import { updateProfileSchema } from '../validators/auth.validator';
import { PERMISSIONS } from '../models/permission.entity';

const router = Router();

// All routes require authentication
router.use(authenticate);

// User profile routes
router.get('/profile', userController.getProfile);
router.put('/profile', validateRequest(updateProfileSchema), userController.updateProfile);
router.delete('/profile', userController.deleteAccount);

// Admin routes
router.get('/', authorize(PERMISSIONS.USERS_READ), userController.getUsers);
router.get('/:id', authorize(PERMISSIONS.USERS_READ), userController.getUser);
router.put('/:id', authorize(PERMISSIONS.USERS_WRITE), userController.updateUser);
router.delete('/:id', authorize(PERMISSIONS.USERS_DELETE), userController.deleteUser);
router.post('/:id/lock', authorize(PERMISSIONS.USERS_WRITE), userController.lockUser);
router.post('/:id/unlock', authorize(PERMISSIONS.USERS_WRITE), userController.unlockUser);
router.get('/:id/audit-logs', authorize(PERMISSIONS.USERS_READ), userController.getUserAuditLogs);

// Role management
router.post('/:id/roles', authorize(PERMISSIONS.USERS_MANAGE_ROLES), userController.assignRole);
router.delete('/:id/roles/:roleId', authorize(PERMISSIONS.USERS_MANAGE_ROLES), userController.revokeRole);

export { router as userRoutes };