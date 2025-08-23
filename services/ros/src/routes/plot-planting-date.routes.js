"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const plot_planting_date_controller_1 = require("@controllers/plot-planting-date.controller");
const validate_request_1 = require("@middleware/validate-request");
const express_validator_1 = require("express-validator");
const router = (0, express_1.Router)();
// Validation rules
const updatePlantingDateValidation = [
    (0, express_validator_1.param)('plotId').notEmpty().withMessage('Plot ID is required'),
    (0, express_validator_1.body)('plantingDate').isISO8601().withMessage('Invalid planting date format'),
    (0, express_validator_1.body)('cropType').isIn(['rice', 'corn', 'sugarcane']).withMessage('Invalid crop type'),
    (0, express_validator_1.body)('season').optional().isIn(['wet', 'dry']).withMessage('Invalid season'),
    (0, express_validator_1.body)('status').optional().isIn(['planned', 'active']).withMessage('Invalid status'),
];
const batchUpdateValidation = [
    (0, express_validator_1.body)('plotIds').isArray({ min: 1 }).withMessage('plotIds must be a non-empty array'),
    (0, express_validator_1.body)('plotIds.*').isString().notEmpty().withMessage('Each plot ID must be a non-empty string'),
    (0, express_validator_1.body)('plantingDate').isISO8601().withMessage('Invalid planting date format'),
    (0, express_validator_1.body)('cropType').isIn(['rice', 'corn', 'sugarcane']).withMessage('Invalid crop type'),
    (0, express_validator_1.body)('season').optional().isIn(['wet', 'dry']).withMessage('Invalid season'),
    (0, express_validator_1.body)('status').optional().isIn(['planned', 'active']).withMessage('Invalid status'),
];
const dateRangeValidation = [
    (0, express_validator_1.query)('startDate').isISO8601().withMessage('Invalid start date format'),
    (0, express_validator_1.query)('endDate').isISO8601().withMessage('Invalid end date format'),
    (0, express_validator_1.query)('zoneId').optional().isString(),
];
const updateStatusValidation = [
    (0, express_validator_1.param)('plotId').notEmpty().withMessage('Plot ID is required'),
    (0, express_validator_1.body)('status').isIn(['active', 'harvested', 'fallow', 'planned']).withMessage('Invalid status'),
];
// Routes
// Update planting date for single plot
router.put('/plot/:plotId/planting-date', updatePlantingDateValidation, validate_request_1.validateRequest, plot_planting_date_controller_1.plotPlantingDateController.updatePlotPlantingDate);
// Batch update planting dates
router.post('/plots/batch-update-planting-dates', batchUpdateValidation, validate_request_1.validateRequest, plot_planting_date_controller_1.plotPlantingDateController.batchUpdatePlantingDates);
// Get plots by planting date range
router.get('/plots/by-planting-date', dateRangeValidation, validate_request_1.validateRequest, plot_planting_date_controller_1.plotPlantingDateController.getPlotsByPlantingDateRange);
// Get upcoming planting schedules
router.get('/plots/upcoming-plantings', (0, express_validator_1.query)('daysAhead').optional().isInt({ min: 1, max: 365 }), validate_request_1.validateRequest, plot_planting_date_controller_1.plotPlantingDateController.getUpcomingPlantingSchedules);
// Update crop status
router.put('/plot/:plotId/crop-status', updateStatusValidation, validate_request_1.validateRequest, plot_planting_date_controller_1.plotPlantingDateController.updateCropStatus);
// Get plots ready for harvest
router.get('/plots/ready-for-harvest', (0, express_validator_1.query)('daysWindow').optional().isInt({ min: 1, max: 30 }), validate_request_1.validateRequest, plot_planting_date_controller_1.plotPlantingDateController.getPlotsReadyForHarvest);
// Get planting date statistics by zone
router.get('/plots/planting-stats-by-zone', plot_planting_date_controller_1.plotPlantingDateController.getPlantingDateStatsByZone);
exports.default = router;
//# sourceMappingURL=plot-planting-date.routes.js.map