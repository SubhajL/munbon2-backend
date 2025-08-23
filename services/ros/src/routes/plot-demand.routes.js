"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const plot_water_demand_controller_1 = require("@controllers/plot-water-demand.controller");
const validate_request_1 = require("@middleware/validate-request");
const express_validator_1 = require("express-validator");
const router = (0, express_1.Router)();
// Validation rules
const calculatePlotDemandValidation = [
    (0, express_validator_1.param)('plotId').notEmpty().withMessage('Plot ID is required'),
    (0, express_validator_1.body)('cropType').isIn(['rice', 'corn', 'sugarcane']).withMessage('Invalid crop type'),
    (0, express_validator_1.body)('plantingDate').isISO8601().withMessage('Invalid planting date format'),
    (0, express_validator_1.body)('includeRainfall').optional().isBoolean(),
    (0, express_validator_1.body)('includeLandPreparation').optional().isBoolean(),
];
const calculateBatchDemandValidation = [
    (0, express_validator_1.body)('plotIds').isArray({ min: 1 }).withMessage('plotIds must be a non-empty array'),
    (0, express_validator_1.body)('plotIds.*').isString().notEmpty().withMessage('Each plot ID must be a non-empty string'),
    (0, express_validator_1.body)('cropType').isIn(['rice', 'corn', 'sugarcane']).withMessage('Invalid crop type'),
    (0, express_validator_1.body)('plantingDate').isISO8601().withMessage('Invalid planting date format'),
    (0, express_validator_1.body)('includeRainfall').optional().isBoolean(),
    (0, express_validator_1.body)('includeLandPreparation').optional().isBoolean(),
];
const getPlotsByAreaValidation = [
    (0, express_validator_1.param)('areaType').isIn(['zone', 'section']).withMessage('areaType must be zone or section'),
    (0, express_validator_1.param)('areaId').notEmpty().withMessage('Area ID is required'),
];
const getHistoricalDemandValidation = [
    (0, express_validator_1.param)('plotId').notEmpty().withMessage('Plot ID is required'),
    (0, express_validator_1.query)('startYear').optional().isInt({ min: 2000, max: 2100 }),
    (0, express_validator_1.query)('endYear').optional().isInt({ min: 2000, max: 2100 }),
];
const getCurrentWeekValidation = [
    (0, express_validator_1.query)('week').optional().isInt({ min: 1, max: 53 }),
    (0, express_validator_1.query)('year').optional().isInt({ min: 2000, max: 2100 }),
];
// Routes
// Single plot calculation
router.post('/plot/:plotId/calculate', calculatePlotDemandValidation, validate_request_1.validateRequest, plot_water_demand_controller_1.plotWaterDemandController.calculatePlotDemand);
// Batch calculation for multiple plots
router.post('/plots/batch-calculate', calculateBatchDemandValidation, validate_request_1.validateRequest, plot_water_demand_controller_1.plotWaterDemandController.calculateBatchPlotDemand);
// Get plots by area (zone or section)
router.get('/plots/by-area/:areaType/:areaId', getPlotsByAreaValidation, validate_request_1.validateRequest, plot_water_demand_controller_1.plotWaterDemandController.getPlotsByArea);
// Get plot information
router.get('/plot/:plotId', (0, express_validator_1.param)('plotId').notEmpty(), validate_request_1.validateRequest, plot_water_demand_controller_1.plotWaterDemandController.getPlotInfo);
// Get historical demand for a plot
router.get('/plot/:plotId/history', getHistoricalDemandValidation, validate_request_1.validateRequest, plot_water_demand_controller_1.plotWaterDemandController.getPlotHistoricalDemand);
// Get current week demand for all active plots
router.get('/plots/current-week', getCurrentWeekValidation, validate_request_1.validateRequest, plot_water_demand_controller_1.plotWaterDemandController.getCurrentWeekDemand);
// Calculate aggregate demand for all plots in a zone
router.post('/zone/:zoneId/calculate', [
    (0, express_validator_1.param)('zoneId').notEmpty().withMessage('Zone ID is required'),
    ...calculatePlotDemandValidation.slice(1), // Skip plotId validation
], validate_request_1.validateRequest, plot_water_demand_controller_1.plotWaterDemandController.calculateZoneDemand);
exports.default = router;
//# sourceMappingURL=plot-demand.routes.js.map