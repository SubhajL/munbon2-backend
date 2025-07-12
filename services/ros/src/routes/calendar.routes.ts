import { Router } from 'express';

const router = Router();

// TODO: Implement crop calendar routes
router.get('/', (req, res) => {
  res.status(501).json({ message: 'Crop calendar endpoints not yet implemented' });
});

export default router;