"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const rainfall_controller_1 = require("@controllers/rainfall.controller");
const validate_request_1 = require("@middleware/validate-request");
const rainfall_validation_1 = require("@utils/validation/rainfall.validation");
const router = (0, express_1.Router)();
// Get weekly effective rainfall
router.get('/weekly/:areaId', (0, validate_request_1.validateRequest)(rainfall_validation_1.rainfallValidation.getWeeklyRainfall), rainfall_controller_1.rainfallController.getWeeklyEffectiveRainfall);
// Add rainfall data
router.post('/', (0, validate_request_1.validateRequest)(rainfall_validation_1.rainfallValidation.addRainfall), rainfall_controller_1.rainfallController.addRainfallData);
// Bulk import rainfall data
router.post('/import', (0, validate_request_1.validateRequest)(rainfall_validation_1.rainfallValidation.importRainfall), rainfall_controller_1.rainfallController.importRainfallData);
// Get rainfall history
router.get('/history/:areaId', (0, validate_request_1.validateRequest)(rainfall_validation_1.rainfallValidation.getRainfallHistory), rainfall_controller_1.rainfallController.getRainfallHistory);
// Update rainfall data
router.put('/:areaId/:date', (0, validate_request_1.validateRequest)(rainfall_validation_1.rainfallValidation.updateRainfall), rainfall_controller_1.rainfallController.updateRainfallData);
// Delete rainfall data
router.delete('/:areaId/:date', (0, validate_request_1.validateRequest)(rainfall_validation_1.rainfallValidation.deleteRainfall), rainfall_controller_1.rainfallController.deleteRainfallData);
// Get rainfall statistics
router.get('/statistics/:areaId', (0, validate_request_1.validateRequest)(rainfall_validation_1.rainfallValidation.getRainfallStatistics), rainfall_controller_1.rainfallController.getRainfallStatistics);
exports.default = router;
//# sourceMappingURL=rainfall.routes.js.map