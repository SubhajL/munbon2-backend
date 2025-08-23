"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const water_level_controller_1 = require("@controllers/water-level.controller");
const validate_request_1 = require("@middleware/validate-request");
const water_level_validation_1 = require("@utils/validation/water-level.validation");
const router = (0, express_1.Router)();
// Get current water level
router.get('/current/:areaId', (0, validate_request_1.validateRequest)(water_level_validation_1.waterLevelValidation.getCurrentLevel), water_level_controller_1.waterLevelController.getCurrentWaterLevel);
// Add water level measurement
router.post('/', (0, validate_request_1.validateRequest)(water_level_validation_1.waterLevelValidation.addWaterLevel), water_level_controller_1.waterLevelController.addWaterLevelMeasurement);
// Bulk import water level data
router.post('/import', (0, validate_request_1.validateRequest)(water_level_validation_1.waterLevelValidation.importWaterLevels), water_level_controller_1.waterLevelController.importWaterLevelData);
// Get water level history
router.get('/history/:areaId', (0, validate_request_1.validateRequest)(water_level_validation_1.waterLevelValidation.getWaterLevelHistory), water_level_controller_1.waterLevelController.getWaterLevelHistory);
// Update water level data
router.put('/:id', (0, validate_request_1.validateRequest)(water_level_validation_1.waterLevelValidation.updateWaterLevel), water_level_controller_1.waterLevelController.updateWaterLevel);
// Delete water level data
router.delete('/:id', (0, validate_request_1.validateRequest)(water_level_validation_1.waterLevelValidation.deleteWaterLevel), water_level_controller_1.waterLevelController.deleteWaterLevel);
// Get water level statistics
router.get('/statistics/:areaId', (0, validate_request_1.validateRequest)(water_level_validation_1.waterLevelValidation.getWaterLevelStatistics), water_level_controller_1.waterLevelController.getWaterLevelStatistics);
// Get water level trends
router.get('/trends/:areaId', (0, validate_request_1.validateRequest)(water_level_validation_1.waterLevelValidation.getWaterLevelTrends), water_level_controller_1.waterLevelController.getWaterLevelTrends);
exports.default = router;
//# sourceMappingURL=water-level.routes.js.map