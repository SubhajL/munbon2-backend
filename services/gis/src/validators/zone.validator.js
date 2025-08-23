"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.zoneIdSchema = exports.queryZoneSchema = exports.updateZoneSchema = exports.createZoneSchema = void 0;
const zod_1 = require("zod");
const polygonSchema = zod_1.z.object({
    type: zod_1.z.literal('Polygon'),
    coordinates: zod_1.z.array(zod_1.z.array(zod_1.z.tuple([zod_1.z.number(), zod_1.z.number()]))).min(1),
});
exports.createZoneSchema = zod_1.z.object({
    body: zod_1.z.object({
        code: zod_1.z.string().min(1).max(50),
        name: zod_1.z.string().min(1).max(200),
        type: zod_1.z.enum(['irrigation', 'drainage', 'mixed']),
        geometry: polygonSchema,
        waterAllocation: zod_1.z.number().min(0).optional(),
        description: zod_1.z.string().optional(),
        metadata: zod_1.z.record(zod_1.z.any()).optional(),
    }),
});
exports.updateZoneSchema = zod_1.z.object({
    params: zod_1.z.object({
        id: zod_1.z.string().uuid(),
    }),
    body: zod_1.z.object({
        code: zod_1.z.string().min(1).max(50).optional(),
        name: zod_1.z.string().min(1).max(200).optional(),
        type: zod_1.z.enum(['irrigation', 'drainage', 'mixed']).optional(),
        waterAllocation: zod_1.z.number().min(0).optional(),
        status: zod_1.z.enum(['active', 'inactive', 'maintenance']).optional(),
        description: zod_1.z.string().optional(),
        metadata: zod_1.z.record(zod_1.z.any()).optional(),
    }),
});
exports.queryZoneSchema = zod_1.z.object({
    body: zod_1.z.object({
        type: zod_1.z.enum(['irrigation', 'drainage', 'mixed']).optional(),
        status: zod_1.z.enum(['active', 'inactive', 'maintenance']).optional(),
        minArea: zod_1.z.number().min(0).optional(),
        maxArea: zod_1.z.number().min(0).optional(),
        bounds: zod_1.z.tuple([
            zod_1.z.number(),
            zod_1.z.number(),
            zod_1.z.number(),
            zod_1.z.number(),
        ]).optional(),
        nearPoint: zod_1.z.object({
            lng: zod_1.z.number().min(-180).max(180),
            lat: zod_1.z.number().min(-90).max(90),
            distance: zod_1.z.number().min(0),
        }).optional(),
    }),
});
exports.zoneIdSchema = zod_1.z.object({
    params: zod_1.z.object({
        id: zod_1.z.string().uuid(),
    }),
});
//# sourceMappingURL=zone.validator.js.map