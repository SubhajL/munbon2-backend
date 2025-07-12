import { Router } from 'express';
import { authenticate } from '../middleware/authenticate';
import { authorize } from '../middleware/authorize';
import { PERMISSIONS } from '../models/permission.entity';

const router = Router();

// All admin routes require authentication and admin permissions
router.use(authenticate);
router.use(authorize(PERMISSIONS.SYSTEM_ADMIN));

// Role management
router.get('/roles', (req, res) => {
  res.json({ message: 'List roles' });
});

// Permission management
router.get('/permissions', (req, res) => {
  res.json({ message: 'List permissions' });
});

// System configuration
router.get('/config', (req, res) => {
  res.json({ message: 'Get system config' });
});

// Security audit logs
router.get('/audit-logs', (req, res) => {
  res.json({ message: 'Get audit logs' });
});

export { router as adminRoutes };