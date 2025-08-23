"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.shapeFileUploadValidator = void 0;
const zod_1 = require("zod");
exports.shapeFileUploadValidator = zod_1.z.object({
    body: zod_1.z.object({
        waterDemandMethod: zod_1.z.enum(['RID-MS', 'ROS', 'AWD'])
            .default('RID-MS')
            .describe('Water demand calculation method'),
        processingInterval: zod_1.z.enum(['daily', 'weekly', 'bi-weekly'])
            .default('weekly')
            .describe('Processing interval for water demand calculations'),
        zone: zod_1.z.string()
            .regex(/^Zone\d+$/)
            .optional()
            .describe('Zone identifier (e.g., Zone1, Zone2)'),
        description: zod_1.z.string()
            .max(500)
            .optional()
            .describe('Description of the shape file upload'),
        metadata: zod_1.z.record(zod_1.z.any())
            .optional()
            .describe('Additional metadata for the upload'),
    }),
    query: zod_1.z.object({}).optional(),
    params: zod_1.z.object({}).optional(),
});
//# sourceMappingURL=shapefile-zod.validator.js.map