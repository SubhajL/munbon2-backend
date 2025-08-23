"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.fieldsRouter = void 0;
const express_1 = require("express");
const express_validator_1 = require("express-validator");
const errorHandler_1 = require("../middleware/errorHandler");
const logger_1 = require("../utils/logger");
exports.fieldsRouter = (0, express_1.Router)();
const validateRequest = (req, _res, next) => {
    const errors = (0, express_validator_1.validationResult)(req);
    if (!errors.isEmpty()) {
        throw new errorHandler_1.AppError(400, 'Validation error', true, errors.array());
    }
    next();
};
exports.fieldsRouter.get('/', [
    (0, express_validator_1.query)('zone_id').optional().isInt().toInt(),
    (0, express_validator_1.query)('limit').optional().isInt({ min: 1, max: 100 }).toInt(),
    (0, express_validator_1.query)('offset').optional().isInt({ min: 0 }).toInt(),
], validateRequest, async (req, res, next) => {
    try {
        res.json({
            success: true,
            data: {
                fields: [],
                total: 0,
                limit: req.query.limit || 20,
                offset: req.query.offset || 0,
            },
        });
    }
    catch (error) {
        next(error);
    }
});
exports.fieldsRouter.get('/:fieldId/status', [(0, express_validator_1.param)('fieldId').isUUID()], validateRequest, async (req, res, next) => {
    try {
        const { fieldId } = req.params;
        res.json({
            success: true,
            data: {
                fieldId,
                status: 'unknown',
                currentWaterLevel: null,
                lastIrrigation: null,
                nextIrrigation: null,
            },
        });
    }
    catch (error) {
        next(error);
    }
});
exports.fieldsRouter.get('/:fieldId/sensors', [(0, express_validator_1.param)('fieldId').isUUID()], validateRequest, async (req, res, next) => {
    try {
        const { fieldId } = req.params;
        res.json({
            success: true,
            data: {
                fieldId,
                sensors: [],
            },
        });
    }
    catch (error) {
        next(error);
    }
});
exports.fieldsRouter.get('/:fieldId/history', [
    (0, express_validator_1.param)('fieldId').isUUID(),
    (0, express_validator_1.query)('days').optional().isInt({ min: 1, max: 90 }).toInt(),
], validateRequest, async (req, res, next) => {
    try {
        const { fieldId } = req.params;
        const days = req.query.days || 7;
        res.json({
            success: true,
            data: {
                fieldId,
                days,
                cycles: [],
            },
        });
    }
    catch (error) {
        next(error);
    }
});
exports.fieldsRouter.post('/:fieldId/control', [
    (0, express_validator_1.param)('fieldId').isUUID(),
    (0, express_validator_1.body)('action').isIn(['start_irrigation', 'stop_irrigation', 'pause', 'resume']),
    (0, express_validator_1.body)('duration').optional().isInt({ min: 1, max: 480 }),
    (0, express_validator_1.body)('reason').optional().isString().trim(),
], validateRequest, async (req, res, next) => {
    try {
        const { fieldId } = req.params;
        const { action, duration, reason } = req.body;
        logger_1.logger.info({
            fieldId,
            action,
            duration,
            reason,
        }, 'Manual control override requested');
        res.json({
            success: true,
            data: {
                fieldId,
                action,
                status: 'accepted',
                message: 'Control command queued',
            },
        });
    }
    catch (error) {
        next(error);
    }
});
exports.fieldsRouter.put('/:fieldId/config', [
    (0, express_validator_1.param)('fieldId').isUUID(),
    (0, express_validator_1.body)('dryingDepth').optional().isInt({ min: 5, max: 30 }),
    (0, express_validator_1.body)('safeAwdDepth').optional().isInt({ min: 5, max: 20 }),
    (0, express_validator_1.body)('emergencyThreshold').optional().isInt({ min: 15, max: 40 }),
    (0, express_validator_1.body)('growthStage').optional().isIn(['vegetative', 'reproductive', 'maturation']),
    (0, express_validator_1.body)('priority').optional().isInt({ min: 1, max: 10 }),
], validateRequest, async (req, res, next) => {
    try {
        const { fieldId } = req.params;
        const config = req.body;
        logger_1.logger.info({
            fieldId,
            config,
        }, 'AWD configuration update requested');
        res.json({
            success: true,
            data: {
                fieldId,
                config,
                message: 'Configuration updated successfully',
            },
        });
    }
    catch (error) {
        next(error);
    }
});
//# sourceMappingURL=fields.routes.js.map