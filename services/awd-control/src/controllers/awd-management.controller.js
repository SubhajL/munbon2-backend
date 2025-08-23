"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.awdManagementController = void 0;
const express_validator_1 = require("express-validator");
const errorHandler_1 = require("../middleware/errorHandler");
const awd_control_service_1 = require("../services/awd-control.service");
const logger_1 = require("../utils/logger");
exports.awdManagementController = {
    initializeField: [
        (0, express_validator_1.body)('fieldId').isUUID(),
        (0, express_validator_1.body)('plantingMethod').isIn(['transplanted', 'direct-seeded']).optional(),
        (0, express_validator_1.body)('startDate').isISO8601(),
        async (req, res, next) => {
            try {
                const errors = (0, express_validator_1.validationResult)(req);
                if (!errors.isEmpty()) {
                    throw new errorHandler_1.AppError(400, 'Validation error', true, errors.array());
                }
                const { fieldId, plantingMethod, startDate } = req.body;
                const method = plantingMethod ||
                    await awd_control_service_1.awdControlService.getPlantingMethodFromGIS(fieldId);
                const config = await awd_control_service_1.awdControlService.initializeFieldControl(fieldId, method, new Date(startDate));
                res.json({
                    success: true,
                    data: config,
                    message: 'AWD control initialized successfully'
                });
            }
            catch (error) {
                next(error);
            }
        }
    ],
    getControlDecision: [
        (0, express_validator_1.param)('fieldId').isUUID(),
        async (req, res, next) => {
            try {
                const errors = (0, express_validator_1.validationResult)(req);
                if (!errors.isEmpty()) {
                    throw new errorHandler_1.AppError(400, 'Validation error', true, errors.array());
                }
                const { fieldId } = req.params;
                const decision = await awd_control_service_1.awdControlService.makeControlDecision(fieldId);
                res.json({
                    success: true,
                    data: decision,
                    timestamp: new Date().toISOString()
                });
            }
            catch (error) {
                next(error);
            }
        }
    ],
    updateSectionStartDates: [
        (0, express_validator_1.body)('sectionId').isString(),
        (0, express_validator_1.body)('startDate').isISO8601(),
        (0, express_validator_1.body)('fieldIds').isArray().optional(),
        async (req, res, next) => {
            try {
                const errors = (0, express_validator_1.validationResult)(req);
                if (!errors.isEmpty()) {
                    throw new errorHandler_1.AppError(400, 'Validation error', true, errors.array());
                }
                const { sectionId, startDate, fieldIds } = req.body;
                const startDateObj = new Date(startDate);
                const fields = fieldIds || await getFieldsInSection(sectionId);
                const results = await Promise.allSettled(fields.map((fieldId) => awd_control_service_1.awdControlService.initializeFieldControl(fieldId, 'direct-seeded', startDateObj)));
                const successful = results.filter(r => r.status === 'fulfilled').length;
                const failed = results.filter(r => r.status === 'rejected').length;
                res.json({
                    success: true,
                    data: {
                        sectionId,
                        startDate,
                        fieldsUpdated: successful,
                        fieldsFailed: failed,
                        totalFields: fields.length
                    },
                    message: `Updated ${successful} fields in section ${sectionId}`
                });
            }
            catch (error) {
                next(error);
            }
        }
    ],
    getSchedule: [
        (0, express_validator_1.param)('plantingMethod').isIn(['transplanted', 'direct-seeded']),
        async (req, res, next) => {
            try {
                const errors = (0, express_validator_1.validationResult)(req);
                if (!errors.isEmpty()) {
                    throw new errorHandler_1.AppError(400, 'Validation error', true, errors.array());
                }
                const { plantingMethod } = req.params;
                const schedule = plantingMethod === 'transplanted'
                    ? require('../types/awd-control.types').TRANSPLANTED_SCHEDULE
                    : require('../types/awd-control.types').DIRECT_SEEDED_SCHEDULE;
                res.json({
                    success: true,
                    data: schedule
                });
            }
            catch (error) {
                next(error);
            }
        }
    ]
};
async function getFieldsInSection(sectionId) {
    logger_1.logger.warn({ sectionId }, 'getFieldsInSection not implemented');
    return [];
}
//# sourceMappingURL=awd-management.controller.js.map