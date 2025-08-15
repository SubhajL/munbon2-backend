import { Router } from 'express';
import { scadaApiService } from '../services/scada-api.service';

const router = Router();

/**
 * GET /api/v1/awd/scada/health
 * Get SCADA health status through AWD service
 */
router.get('/scada/health', async (req, res) => {
  try {
    const health = await scadaApiService.getHealthStatus();
    res.json(health);
  } catch (error: any) {
    res.status(503).json({
      status: 'failed',
      message: 'Failed to get SCADA health status',
      error: error.message
    });
  }
});

/**
 * GET /api/v1/awd/scada/health/detailed
 * Get detailed SCADA health status
 */
router.get('/scada/health/detailed', async (req, res) => {
  try {
    const health = await scadaApiService.getDetailedHealthStatus();
    res.json(health);
  } catch (error: any) {
    res.status(503).json({
      status: 'failed',
      message: 'Failed to get detailed SCADA health status',
      error: error.message
    });
  }
});

/**
 * GET /api/v1/awd/scada/availability
 * Quick check if SCADA is available
 */
router.get('/scada/availability', async (req, res) => {
  try {
    const isAvailable = await scadaApiService.isScadaAvailable();
    res.json({
      available: isAvailable,
      timestamp: new Date()
    });
  } catch (error: any) {
    res.status(503).json({
      available: false,
      error: error.message,
      timestamp: new Date()
    });
  }
});

export default router;