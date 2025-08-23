"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.sensorsRouter = void 0;
const express_1 = require("express");
const express_validator_1 = require("express-validator");
const errorHandler_1 = require("../middleware/errorHandler");
const sensor_management_service_1 = require("../services/sensor-management.service");
const sensor_repository_1 = require("../repositories/sensor.repository");
exports.sensorsRouter = (0, express_1.Router)();
const validateRequest = (req, _res, next) => {
    const errors = (0, express_validator_1.validationResult)(req);
    if (!errors.isEmpty()) {
        throw new errorHandler_1.AppError(400, 'Validation error', true, errors.array());
    }
    next();
};
exports.sensorsRouter.get('/:sensorId/status', [(0, express_validator_1.param)('sensorId').isString().notEmpty()], validateRequest, async (req, res, next) => {
    try {
        const { sensorId } = req.params;
        const status = await sensor_repository_1.sensorRepository.getSensorStatus(sensorId);
        if (!status) {
            throw new errorHandler_1.AppError(404, 'Sensor not found');
        }
        res.json({
            success: true,
            data: status,
        });
    }
    catch (error) {
        next(error);
    }
});
exports.sensorsRouter.get('/field/:fieldId', [(0, express_validator_1.param)('fieldId').isUUID()], validateRequest, async (req, res, next) => {
    try {
        const { fieldId } = req.params;
        const sensorConfig = await sensor_repository_1.sensorRepository.getFieldSensorConfig(fieldId);
        const health = await sensor_management_service_1.sensorManagementService.getFieldSensorHealth(fieldId);
        res.json({
            success: true,
            data: {
                fieldId,
                sensorConfig,
                health,
            },
        });
    }
    catch (error) {
        next(error);
    }
});
exports.sensorsRouter.get('/field/:fieldId/readings', [(0, express_validator_1.param)('fieldId').isUUID()], validateRequest, async (req, res, next) => {
    try {
        const { fieldId } = req.params;
        const [waterLevel, moisture] = await Promise.all([
            sensor_management_service_1.sensorManagementService.getCurrentWaterLevel(fieldId),
            sensor_management_service_1.sensorManagementService.getCurrentMoistureLevel(fieldId)
        ]);
        res.json({
            success: true,
            data: {
                fieldId,
                waterLevel,
                moisture,
                timestamp: new Date().toISOString(),
            },
        });
    }
    catch (error) {
        next(error);
    }
});
exports.sensorsRouter.get('/field/:fieldId/history', [
    (0, express_validator_1.param)('fieldId').isUUID(),
    (0, express_validator_1.query)('type').isIn(['water_level', 'moisture']).optional(),
    (0, express_validator_1.query)('startDate').isISO8601().optional(),
    (0, express_validator_1.query)('endDate').isISO8601().optional(),
    (0, express_validator_1.query)('hours').isInt({ min: 1, max: 168 }).optional().toInt(),
], validateRequest, async (req, res, next) => {
    try {
        const { fieldId } = req.params;
        const { type, startDate, endDate, hours } = req.query;
        let start;
        let end;
        if (startDate && endDate) {
            start = new Date(startDate);
            end = new Date(endDate);
        }
        else {
            end = new Date();
            const hoursBack = typeof hours === 'number' ? hours : 24;
            start = new Date(end.getTime() - hoursBack * 60 * 60 * 1000);
        }
        const results = {};
        if (!type || type === 'water_level') {
            results.waterLevel = await sensor_repository_1.sensorRepository.getWaterLevelHistory(fieldId, start, end);
        }
        if (!type || type === 'moisture') {
            results.moisture = await sensor_repository_1.sensorRepository.getMoistureHistory(fieldId, start, end);
        }
        res.json({
            success: true,
            data: {
                fieldId,
                startDate: start.toISOString(),
                endDate: end.toISOString(),
                ...results,
            },
        });
    }
    catch (error) {
        next(error);
    }
});
exports.sensorsRouter.get('/field/:fieldId/irrigation-check', [(0, express_validator_1.param)('fieldId').isUUID()], validateRequest, async (req, res, next) => {
    try {
        const { fieldId } = req.params;
        const check = await sensor_management_service_1.sensorManagementService.checkIrrigationNeed(fieldId);
        res.json({
            success: true,
            data: {
                fieldId,
                ...check,
                timestamp: new Date().toISOString(),
            },
        });
    }
    catch (error) {
        next(error);
    }
});
//# sourceMappingURL=sensors.routes.js.map