import { Router } from 'express';
import { rosController } from '../controllers/rosController';
import { validateCalculation } from '../validators/rosValidators';
import { uploadMiddleware } from '../middleware/uploadMiddleware';
import { uploadRateLimiter, calculationRateLimiter } from '../middleware/rateLimiter';

const router = Router();

// Water demand calculation endpoints
router.post(
  '/calculate',
  calculationRateLimiter,
  validateCalculation,
  rosController.calculateWaterDemand
);

router.post(
  '/calculate/batch',
  calculationRateLimiter,
  rosController.batchCalculate
);

// Data management endpoints
router.post(
  '/data/kc/import',
  uploadRateLimiter,
  uploadMiddleware.single('file'),
  rosController.importKcData
);

router.post(
  '/data/et0/import',
  uploadRateLimiter,
  uploadMiddleware.single('file'),
  rosController.importET0Data
);

router.post(
  '/data/rainfall/import',
  uploadRateLimiter,
  uploadMiddleware.single('file'),
  rosController.importRainfallData
);

// Lookup data endpoints
router.get('/data/kc/:cropType', rosController.getKcCurve);
router.get('/data/et0/annual', rosController.getAnnualET0);
router.get('/data/rainfall/annual', rosController.getAnnualRainfall);

// Report generation endpoints
router.post('/report/generate', rosController.generateReport);
router.get('/report/:reportId', rosController.getReport);
router.get('/report/:reportId/download', rosController.downloadReport);

// Excel processing endpoints
router.post(
  '/excel/upload',
  uploadRateLimiter,
  uploadMiddleware.single('file'),
  rosController.uploadExcelFile
);

router.get('/excel/status/:jobId', rosController.getProcessingStatus);

// Historical data endpoints
router.get('/history/calculations', rosController.getCalculationHistory);
router.get('/history/calculations/:calculationId', rosController.getCalculationDetails);

// Visualization endpoints
router.get('/visualization/demand-pattern', rosController.getDemandPattern);
router.get('/visualization/seasonal-analysis', rosController.getSeasonalAnalysis);

// Crop information endpoints
router.get('/crops', rosController.getAvailableCrops);
router.get('/crops/:cropType/info', rosController.getCropInfo);

export default router;