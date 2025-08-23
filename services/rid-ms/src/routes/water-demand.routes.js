"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.waterDemandRoutes = void 0;
const express_1 = require("express");
const express_validator_1 = require("express-validator");
const water_demand_controller_1 = require("../controllers/water-demand.controller");
const auth_middleware_1 = require("../middleware/auth.middleware");
const async_handler_1 = require("../middleware/async-handler");
const router = (0, express_1.Router)();
const controller = new water_demand_controller_1.WaterDemandController();
const validateRequest = (req, res, next) => {
    const errors = (0, express_validator_1.validationResult)(req);
    if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
    }
    next();
};
router.post('/calculate', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.body)('parcels')
        .isArray({ min: 1 })
        .withMessage('Parcels must be a non-empty array'),
    (0, express_validator_1.body)('parcels.*')
        .isString()
        .withMessage('Each parcel ID must be a string'),
    (0, express_validator_1.body)('method')
        .isIn(['RID-MS', 'ROS', 'AWD'])
        .withMessage('Method must be RID-MS, ROS, or AWD'),
    (0, express_validator_1.body)('parameters').optional().isObject(),
    (0, express_validator_1.body)('parameters.cropType').optional().isString(),
    (0, express_validator_1.body)('parameters.plantingDate').optional().isISO8601(),
    (0, express_validator_1.body)('parameters.irrigationEfficiency')
        .optional()
        .isFloat({ min: 0.1, max: 1.0 })
        .withMessage('Irrigation efficiency must be between 0.1 and 1.0'),
], validateRequest, controller.calculateWaterDemand.bind(controller));
router.get('/parcels/:parcelId', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.param)('parcelId').isString().withMessage('Invalid parcel ID'),
    (0, express_validator_1.query)('date').optional().isISO8601(),
], validateRequest, controller.getParcelWaterDemand.bind(controller));
router.get('/history/:parcelId', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.param)('parcelId').isString().withMessage('Invalid parcel ID'),
    (0, express_validator_1.query)('startDate').notEmpty().isISO8601(),
    (0, express_validator_1.query)('endDate').notEmpty().isISO8601(),
], validateRequest, (0, async_handler_1.asyncHandler)(controller.getWaterDemandHistory.bind(controller)));
router.put('/parcels/method', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.body)('parcels')
        .isArray({ min: 1 })
        .withMessage('Parcels must be a non-empty array'),
    (0, express_validator_1.body)('parcels.*')
        .isString()
        .withMessage('Each parcel ID must be a string'),
    (0, express_validator_1.body)('method')
        .isIn(['RID-MS', 'ROS', 'AWD'])
        .withMessage('Method must be RID-MS, ROS, or AWD'),
], validateRequest, controller.updateWaterDemandMethod.bind(controller));
router.get('/zones/:zone/statistics', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.param)('zone').isString().withMessage('Invalid zone'),
], validateRequest, controller.getZoneWaterDemandStatistics.bind(controller));
router.get('/summary', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.query)('groupBy')
        .optional()
        .isIn(['zone', 'method', 'cropType'])
        .withMessage('Group by must be zone, method, or cropType'),
    (0, express_validator_1.query)('startDate').optional().isISO8601(),
    (0, express_validator_1.query)('endDate').optional().isISO8601(),
], validateRequest, controller.getWaterDemandSummary.bind(controller));
router.get('/export', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.query)('format')
        .isIn(['csv', 'json', 'excel'])
        .withMessage('Format must be csv, json, or excel'),
    (0, express_validator_1.query)('zone').optional().isString(),
    (0, express_validator_1.query)('method')
        .optional()
        .isIn(['RID-MS', 'ROS', 'AWD']),
    (0, express_validator_1.query)('startDate').optional().isISO8601(),
    (0, express_validator_1.query)('endDate').optional().isISO8601(),
], validateRequest, controller.exportWaterDemandData.bind(controller));
router.get('/forecast', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.query)('zone').optional().isString(),
    (0, express_validator_1.query)('days')
        .optional()
        .isInt({ min: 1, max: 30 })
        .toInt()
        .withMessage('Days must be between 1 and 30'),
], validateRequest, controller.getWaterDemandForecast.bind(controller));
router.post('/update-all', auth_middleware_1.authMiddleware, controller.triggerWaterDemandUpdate.bind(controller));
exports.waterDemandRoutes = router;
//# sourceMappingURL=water-demand.routes.js.map