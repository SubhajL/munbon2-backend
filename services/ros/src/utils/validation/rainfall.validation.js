"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.rainfallValidation = void 0;
const joi_1 = __importDefault(require("joi"));
exports.rainfallValidation = {
    getWeeklyRainfall: {
        params: joi_1.default.object({
            areaId: joi_1.default.string().required(),
        }),
        query: joi_1.default.object({
            weekStartDate: joi_1.default.date().iso().optional(),
        }),
    },
    addRainfall: {
        body: joi_1.default.object({
            areaId: joi_1.default.string().required(),
            date: joi_1.default.date().required(),
            rainfallMm: joi_1.default.number().min(0).required(),
            effectiveRainfallMm: joi_1.default.number().min(0).optional(),
            source: joi_1.default.string().valid('manual', 'weather_api', 'sensor').required(),
        }),
    },
    importRainfall: {
        body: joi_1.default.object({
            rainfallData: joi_1.default.array().items(joi_1.default.object({
                areaId: joi_1.default.string().required(),
                date: joi_1.default.date().required(),
                rainfallMm: joi_1.default.number().min(0).required(),
                effectiveRainfallMm: joi_1.default.number().min(0).optional(),
                source: joi_1.default.string().valid('manual', 'weather_api', 'sensor').required(),
            })).min(1).required(),
        }),
    },
    getRainfallHistory: {
        params: joi_1.default.object({
            areaId: joi_1.default.string().required(),
        }),
        query: joi_1.default.object({
            startDate: joi_1.default.date().iso().required(),
            endDate: joi_1.default.date().iso().min(joi_1.default.ref('startDate')).required(),
        }),
    },
    updateRainfall: {
        params: joi_1.default.object({
            areaId: joi_1.default.string().required(),
            date: joi_1.default.date().required(),
        }),
        body: joi_1.default.object({
            rainfallMm: joi_1.default.number().min(0).optional(),
            effectiveRainfallMm: joi_1.default.number().min(0).optional(),
            source: joi_1.default.string().valid('manual', 'weather_api', 'sensor').optional(),
        }).min(1),
    },
    deleteRainfall: {
        params: joi_1.default.object({
            areaId: joi_1.default.string().required(),
            date: joi_1.default.date().required(),
        }),
    },
    getRainfallStatistics: {
        params: joi_1.default.object({
            areaId: joi_1.default.string().required(),
        }),
        query: joi_1.default.object({
            year: joi_1.default.number().integer().min(2000).max(2100).optional(),
            month: joi_1.default.number().integer().min(1).max(12).optional(),
        }),
    },
};
//# sourceMappingURL=rainfall.validation.js.map