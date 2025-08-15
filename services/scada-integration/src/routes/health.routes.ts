import { Router, Request, Response } from 'express';
import { healthMonitorService } from '../services/health-monitor.service';

const router = Router();

/**
 * GET /api/v1/scada/health
 * Get overall SCADA health status
 */
router.get('/health', async (req: Request, res: Response) => {
  try {
    const report = await healthMonitorService.getHealthStatus();
    
    // Set appropriate HTTP status based on health
    let httpStatus = 200;
    if (report.status === 'failed') {
      httpStatus = 503; // Service Unavailable
    } else if (report.status === 'critical') {
      httpStatus = 500; // Internal Server Error
    }
    
    res.status(httpStatus).json(report);
  } catch (error: any) {
    console.error('Error getting health status:', error);
    res.status(500).json({
      status: 'failed',
      message: 'Failed to get health status',
      error: error.message
    });
  }
});

/**
 * GET /api/v1/scada/health/detailed
 * Get detailed SCADA health status with individual site information
 */
router.get('/health/detailed', async (req: Request, res: Response) => {
  try {
    const report = await healthMonitorService.getDetailedHealthStatus();
    res.json(report);
  } catch (error: any) {
    console.error('Error getting detailed health status:', error);
    res.status(500).json({
      status: 'failed',
      message: 'Failed to get detailed health status',
      error: error.message
    });
  }
});

/**
 * GET /api/v1/scada/sites/status
 * Get all site statuses
 */
router.get('/sites/status', async (req: Request, res: Response) => {
  try {
    const report = await healthMonitorService.getDetailedHealthStatus();
    res.json({
      sites: report.details || [],
      timestamp: new Date()
    });
  } catch (error: any) {
    console.error('Error getting site statuses:', error);
    res.status(500).json({
      message: 'Failed to get site statuses',
      error: error.message
    });
  }
});

/**
 * GET /api/v1/scada/sites/:stationCode/status
 * Get specific site status
 */
router.get('/sites/:stationCode/status', async (req: Request, res: Response) => {
  try {
    const { stationCode } = req.params;
    const siteStatus = await healthMonitorService.getSiteStatus(stationCode);
    
    if (!siteStatus) {
      return res.status(404).json({
        message: `Site ${stationCode} not found`
      });
    }
    
    res.json(siteStatus);
  } catch (error: any) {
    console.error('Error getting site status:', error);
    res.status(500).json({
      message: 'Failed to get site status',
      error: error.message
    });
  }
});

export default router;