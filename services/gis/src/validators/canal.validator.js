"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.flowUpdateSchema = exports.canalIdSchema = exports.queryCanalSchema = exports.updateCanalSchema = exports.createCanalSchema = void 0;
const zod_1 = require("zod");
const lineStringSchema = zod_1.z.object({
    type: zod_1.z.literal('LineString'),
    coordinates: zod_1.z.array(zod_1.z.tuple([zod_1.z.number(), zod_1.z.number()])).min(2),
});
exports.createCanalSchema = zod_1.z.object({
    body: zod_1.z.object({
        code: zod_1.z.string().min(1).max(50),
        name: zod_1.z.string().min(1).max(200),
        type: zod_1.z.enum(['main', 'secondary', 'tertiary', 'field']),
        level: zod_1.z.number().int().min(1).max(4),
        geometry: lineStringSchema,
        length: zod_1.z.number().positive().optional(),
        width: zod_1.z.number().positive().optional(),
        depth: zod_1.z.number().positive().optional(),
        capacity: zod_1.z.number().positive(),
        material: zod_1.z.string().optional(),
        constructionYear: zod_1.z.number().int().optional(),
        metadata: zod_1.z.record(zod_1.z.any()).optional(),
    }),
});
exports.updateCanalSchema = zod_1.z.object({
    params: zod_1.z.object({
        id: zod_1.z.string().uuid(),
    }),
    body: zod_1.z.object({
        code: zod_1.z.string().min(1).max(50).optional(),
        name: zod_1.z.string().min(1).max(200).optional(),
        type: zod_1.z.enum(['main', 'secondary', 'tertiary', 'field']).optional(),
        status: zod_1.z.enum(['operational', 'maintenance', 'closed', 'damaged']).optional(),
        capacity: zod_1.z.number().positive().optional(),
        currentFlow: zod_1.z.number().min(0).optional(),
        metadata: zod_1.z.record(zod_1.z.any()).optional(),
    }),
});
exports.queryCanalSchema = zod_1.z.object({
    body: zod_1.z.object({
        type: zod_1.z.enum(['main', 'secondary', 'tertiary', 'field']).optional(),
        level: zod_1.z.number().int().min(1).max(4).optional(),
        status: zod_1.z.enum(['operational', 'maintenance', 'closed', 'damaged']).optional(),
        minCapacity: zod_1.z.number().positive().optional(),
        maxCapacity: zod_1.z.number().positive().optional(),
        bounds: zod_1.z.tuple([
            zod_1.z.number(),
            zod_1.z.number(),
            zod_1.z.number(),
            zod_1.z.number(),
        ]).optional(),
        nearPoint: zod_1.z.object({
            lng: zod_1.z.number().min(-180).max(180),
            lat: zod_1.z.number().min(-90).max(90),
            distance: zod_1.z.number().positive(),
        }).optional(),
    }),
});
exports.canalIdSchema = zod_1.z.object({
    params: zod_1.z.object({
        id: zod_1.z.string().uuid(),
    }),
});
exports.flowUpdateSchema = zod_1.z.object({
    params: zod_1.z.object({
        id: zod_1.z.string().uuid(),
    }),
    body: zod_1.z.object({
        flowRate: zod_1.z.number().min(0),
        measuredAt: zod_1.z.string().datetime(),
        sensorId: zod_1.z.string().optional(),
    }),
});
//# sourceMappingURL=canal.validator.js.map