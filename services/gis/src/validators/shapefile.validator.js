"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.shapeFileUploadValidator = void 0;
const joi_1 = __importDefault(require("joi"));
exports.shapeFileUploadValidator = joi_1.default.object({
    waterDemandMethod: joi_1.default.string()
        .valid('RID-MS', 'ROS', 'AWD')
        .default('RID-MS')
        .description('Water demand calculation method'),
    processingInterval: joi_1.default.string()
        .valid('daily', 'weekly', 'bi-weekly')
        .default('weekly')
        .description('Processing interval for water demand calculations'),
    zone: joi_1.default.string()
        .pattern(/^Zone\d+$/)
        .description('Zone identifier (e.g., Zone1, Zone2)'),
    description: joi_1.default.string()
        .max(500)
        .description('Description of the shape file upload'),
    metadata: joi_1.default.object()
        .description('Additional metadata for the upload'),
}).options({ stripUnknown: true });
//# sourceMappingURL=shapefile.validator.js.map