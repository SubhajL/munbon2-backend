import { Router } from 'express';

const router = Router();

// TODO: Implement crop routes
router.get('/', (req, res) => {
  res.status(501).json({ message: 'Crop management endpoints not yet implemented' });
});

export default router;