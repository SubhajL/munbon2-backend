"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.waterDemandValidation = void 0;
const joi_1 = __importDefault(require("joi"));
const cropTypes = ['rice', 'corn', 'sugarcane'];
const areaTypes = ['project', 'zone', 'section', 'FTO'];
exports.waterDemandValidation = {
    calculateWaterDemand: {
        body: joi_1.default.object({
            areaId: joi_1.default.string().required(),
            cropType: joi_1.default.string().valid(...cropTypes).required(),
            areaType: joi_1.default.string().valid(...areaTypes).required(),
            areaRai: joi_1.default.number().positive().required(),
            cropWeek: joi_1.default.number().integer().min(1).required(),
            calendarWeek: joi_1.default.number().integer().min(1).max(53).required(),
            calendarYear: joi_1.default.number().integer().min(2024).max(2050).required(),
            effectiveRainfall: joi_1.default.number().min(0).optional(),
            waterLevel: joi_1.default.number().min(0).optional(),
        }),
    },
    calculateSeasonalWaterDemand: {
        body: joi_1.default.object({
            areaId: joi_1.default.string().required(),
            areaType: joi_1.default.string().valid(...areaTypes).required(),
            areaRai: joi_1.default.number().positive().required(),
            cropType: joi_1.default.string().valid(...cropTypes).required(),
            plantingDate: joi_1.default.date().required(),
            includeRainfall: joi_1.default.boolean().optional(),
        }),
    },
    getWaterDemandByCropWeek: {
        params: joi_1.default.object({
            areaId: joi_1.default.string().required(),
        }),
        query: joi_1.default.object({
            cropWeek: joi_1.default.number().integer().min(1).required(),
        }),
    },
    getSeasonalWaterDemandByWeek: {
        params: joi_1.default.object({
            areaId: joi_1.default.string().required(),
        }),
        query: joi_1.default.object({
            startDate: joi_1.default.date().required(),
            endDate: joi_1.default.date().min(joi_1.default.ref('startDate')).required(),
        }),
    },
    getWaterDemandSummary: {
        params: joi_1.default.object({
            areaType: joi_1.default.string().valid(...areaTypes).required(),
        }),
        query: joi_1.default.object({
            areaId: joi_1.default.string().optional(),
            startDate: joi_1.default.date().required(),
            endDate: joi_1.default.date().min(joi_1.default.ref('startDate')).required(),
        }),
    },
};
//# sourceMappingURL=water-demand.validation.js.map