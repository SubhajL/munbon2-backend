"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const rosController_1 = require("../controllers/rosController");
const rosValidators_1 = require("../validators/rosValidators");
const uploadMiddleware_1 = require("../middleware/uploadMiddleware");
const rateLimiter_1 = require("../middleware/rateLimiter");
const router = (0, express_1.Router)();
// Water demand calculation endpoints
router.post('/calculate', rateLimiter_1.calculationRateLimiter, rosValidators_1.validateCalculation, rosController_1.rosController.calculateWaterDemand);
router.post('/calculate/batch', rateLimiter_1.calculationRateLimiter, rosController_1.rosController.batchCalculate);
// Data management endpoints
router.post('/data/kc/import', rateLimiter_1.uploadRateLimiter, uploadMiddleware_1.uploadMiddleware.single('file'), rosController_1.rosController.importKcData);
router.post('/data/et0/import', rateLimiter_1.uploadRateLimiter, uploadMiddleware_1.uploadMiddleware.single('file'), rosController_1.rosController.importET0Data);
router.post('/data/rainfall/import', rateLimiter_1.uploadRateLimiter, uploadMiddleware_1.uploadMiddleware.single('file'), rosController_1.rosController.importRainfallData);
// Lookup data endpoints
router.get('/data/kc/:cropType', rosController_1.rosController.getKcCurve);
router.get('/data/et0/annual', rosController_1.rosController.getAnnualET0);
router.get('/data/rainfall/annual', rosController_1.rosController.getAnnualRainfall);
// Report generation endpoints
router.post('/report/generate', rosController_1.rosController.generateReport);
router.get('/report/:reportId', rosController_1.rosController.getReport);
router.get('/report/:reportId/download', rosController_1.rosController.downloadReport);
// Excel processing endpoints
router.post('/excel/upload', rateLimiter_1.uploadRateLimiter, uploadMiddleware_1.uploadMiddleware.single('file'), rosController_1.rosController.uploadExcelFile);
router.get('/excel/status/:jobId', rosController_1.rosController.getProcessingStatus);
// Historical data endpoints
router.get('/history/calculations', rosController_1.rosController.getCalculationHistory);
router.get('/history/calculations/:calculationId', rosController_1.rosController.getCalculationDetails);
// Visualization endpoints
router.get('/visualization/demand-pattern', rosController_1.rosController.getDemandPattern);
router.get('/visualization/seasonal-analysis', rosController_1.rosController.getSeasonalAnalysis);
// Crop information endpoints
router.get('/crops', rosController_1.rosController.getAvailableCrops);
router.get('/crops/:cropType/info', rosController_1.rosController.getCropInfo);
exports.default = router;
//# sourceMappingURL=ros.routes.js.map