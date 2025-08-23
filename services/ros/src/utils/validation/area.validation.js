"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.areaValidation = void 0;
const joi_1 = __importDefault(require("joi"));
const areaTypes = ['project', 'zone', 'section', 'FTO'];
exports.areaValidation = {
    createArea: {
        body: joi_1.default.object({
            areaId: joi_1.default.string().required(),
            areaType: joi_1.default.string().valid(...areaTypes).required(),
            areaName: joi_1.default.string().optional(),
            totalAreaRai: joi_1.default.number().positive().required(),
            parentAreaId: joi_1.default.string().optional(),
            aosStation: joi_1.default.string().optional(),
            province: joi_1.default.string().optional(),
        }),
    },
    getAreaById: {
        params: joi_1.default.object({
            areaId: joi_1.default.string().required(),
        }),
    },
    updateArea: {
        params: joi_1.default.object({
            areaId: joi_1.default.string().required(),
        }),
        body: joi_1.default.object({
            areaName: joi_1.default.string().optional(),
            totalAreaRai: joi_1.default.number().positive().optional(),
            parentAreaId: joi_1.default.string().optional(),
            aosStation: joi_1.default.string().optional(),
            province: joi_1.default.string().optional(),
        }).min(1),
    },
    deleteArea: {
        params: joi_1.default.object({
            areaId: joi_1.default.string().required(),
        }),
    },
    getAreasByType: {
        params: joi_1.default.object({
            areaType: joi_1.default.string().valid(...areaTypes).required(),
        }),
    },
    getChildAreas: {
        params: joi_1.default.object({
            areaId: joi_1.default.string().required(),
        }),
    },
    getAreaHierarchy: {
        params: joi_1.default.object({
            projectId: joi_1.default.string().required(),
        }),
    },
    calculateTotalArea: {
        params: joi_1.default.object({
            areaId: joi_1.default.string().required(),
        }),
    },
    importAreas: {
        body: joi_1.default.object({
            areas: joi_1.default.array().items(joi_1.default.object({
                areaId: joi_1.default.string().required(),
                areaType: joi_1.default.string().valid(...areaTypes).required(),
                areaName: joi_1.default.string().optional(),
                totalAreaRai: joi_1.default.number().positive().required(),
                parentAreaId: joi_1.default.string().optional(),
                aosStation: joi_1.default.string().optional(),
                province: joi_1.default.string().optional(),
            })).min(1).required(),
        }),
    },
};
//# sourceMappingURL=area.validation.js.map