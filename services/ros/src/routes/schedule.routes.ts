import { Router } from 'express';

const router = Router();

// TODO: Implement irrigation schedule routes
router.get('/', (req, res) => {
  res.status(501).json({ message: 'Irrigation schedule endpoints not yet implemented' });
});

export default router;