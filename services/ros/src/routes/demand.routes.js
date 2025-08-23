"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const water_demand_controller_1 = require("@controllers/water-demand.controller");
const crop_week_controller_1 = require("@controllers/crop-week.controller");
const validate_request_1 = require("@middleware/validate-request");
const water_demand_validation_1 = require("@utils/validation/water-demand.validation");
const router = (0, express_1.Router)();
// Calculate water demand for a specific crop week
router.post('/calculate', (0, validate_request_1.validateRequest)(water_demand_validation_1.waterDemandValidation.calculateWaterDemand), water_demand_controller_1.waterDemandController.calculateWaterDemand);
// Calculate water demand for entire crop season
router.post('/seasonal', (0, validate_request_1.validateRequest)(water_demand_validation_1.waterDemandValidation.calculateSeasonalWaterDemand), water_demand_controller_1.waterDemandController.calculateSeasonalWaterDemand);
// Get water demand for a particular area for a crop week
router.get('/area/:areaId/week', (0, validate_request_1.validateRequest)(water_demand_validation_1.waterDemandValidation.getWaterDemandByCropWeek), water_demand_controller_1.waterDemandController.getWaterDemandByCropWeek);
// Get water demand for entire crop season by week
router.get('/area/:areaId/seasonal', (0, validate_request_1.validateRequest)(water_demand_validation_1.waterDemandValidation.getSeasonalWaterDemandByWeek), water_demand_controller_1.waterDemandController.getSeasonalWaterDemandByWeek);
// Get water demand summary for an area type
router.get('/summary/:areaType', (0, validate_request_1.validateRequest)(water_demand_validation_1.waterDemandValidation.getWaterDemandSummary), water_demand_controller_1.waterDemandController.getWaterDemandSummary);
// Crop week calculation endpoints
router.post('/crop-week/current', crop_week_controller_1.cropWeekController.calculateCurrentCropWeek);
router.post('/crop-week/plots', crop_week_controller_1.cropWeekController.getCropWeeksForPlots);
router.post('/crop-week/planting-date', crop_week_controller_1.cropWeekController.calculatePlantingDate);
exports.default = router;
//# sourceMappingURL=demand.routes.js.map