"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.waterLevelValidation = void 0;
const joi_1 = __importDefault(require("joi"));
exports.waterLevelValidation = {
    getCurrentLevel: {
        params: joi_1.default.object({
            areaId: joi_1.default.string().required(),
        }),
    },
    addWaterLevel: {
        body: joi_1.default.object({
            areaId: joi_1.default.string().required(),
            measurementDate: joi_1.default.date().required(),
            measurementTime: joi_1.default.string().pattern(/^([01]\d|2[0-3]):([0-5]\d)$/).optional(), // HH:MM format
            waterLevelM: joi_1.default.number().required(),
            referenceLevel: joi_1.default.string().valid('MSL', 'local_datum', 'relative').optional(),
            source: joi_1.default.string().valid('manual', 'sensor', 'scada').required(),
            sensorId: joi_1.default.string().optional(),
        }),
    },
    importWaterLevels: {
        body: joi_1.default.object({
            waterLevels: joi_1.default.array().items(joi_1.default.object({
                areaId: joi_1.default.string().required(),
                measurementDate: joi_1.default.date().required(),
                measurementTime: joi_1.default.string().pattern(/^([01]\d|2[0-3]):([0-5]\d)$/).optional(),
                waterLevelM: joi_1.default.number().required(),
                referenceLevel: joi_1.default.string().valid('MSL', 'local_datum', 'relative').optional(),
                source: joi_1.default.string().valid('manual', 'sensor', 'scada').required(),
                sensorId: joi_1.default.string().optional(),
            })).min(1).required(),
        }),
    },
    getWaterLevelHistory: {
        params: joi_1.default.object({
            areaId: joi_1.default.string().required(),
        }),
        query: joi_1.default.object({
            startDate: joi_1.default.date().iso().required(),
            endDate: joi_1.default.date().iso().min(joi_1.default.ref('startDate')).required(),
            source: joi_1.default.string().valid('manual', 'sensor', 'scada').optional(),
        }),
    },
    updateWaterLevel: {
        params: joi_1.default.object({
            id: joi_1.default.number().integer().positive().required(),
        }),
        body: joi_1.default.object({
            waterLevelM: joi_1.default.number().optional(),
            referenceLevel: joi_1.default.string().valid('MSL', 'local_datum', 'relative').optional(),
            source: joi_1.default.string().valid('manual', 'sensor', 'scada').optional(),
            sensorId: joi_1.default.string().optional(),
        }).min(1),
    },
    deleteWaterLevel: {
        params: joi_1.default.object({
            id: joi_1.default.number().integer().positive().required(),
        }),
    },
    getWaterLevelStatistics: {
        params: joi_1.default.object({
            areaId: joi_1.default.string().required(),
        }),
        query: joi_1.default.object({
            period: joi_1.default.string().valid('daily', 'weekly', 'monthly', 'yearly').default('monthly'),
            year: joi_1.default.number().integer().min(2000).max(2100).optional(),
            month: joi_1.default.number().integer().min(1).max(12).optional(),
        }),
    },
    getWaterLevelTrends: {
        params: joi_1.default.object({
            areaId: joi_1.default.string().required(),
        }),
        query: joi_1.default.object({
            days: joi_1.default.number().integer().min(7).max(365).default(30),
        }),
    },
};
//# sourceMappingURL=water-level.validation.js.map