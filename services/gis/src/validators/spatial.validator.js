"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.intersectionSchema = exports.unionSchema = exports.bufferSchema = exports.spatialQuerySchema = void 0;
const zod_1 = require("zod");
const pointSchema = zod_1.z.object({
    type: zod_1.z.literal('Point'),
    coordinates: zod_1.z.tuple([zod_1.z.number(), zod_1.z.number()]),
});
const lineStringSchema = zod_1.z.object({
    type: zod_1.z.literal('LineString'),
    coordinates: zod_1.z.array(zod_1.z.tuple([zod_1.z.number(), zod_1.z.number()])).min(2),
});
const polygonSchema = zod_1.z.object({
    type: zod_1.z.literal('Polygon'),
    coordinates: zod_1.z.array(zod_1.z.array(zod_1.z.tuple([zod_1.z.number(), zod_1.z.number()]))).min(1),
});
const geometrySchema = zod_1.z.union([pointSchema, lineStringSchema, polygonSchema]);
exports.spatialQuerySchema = zod_1.z.object({
    body: zod_1.z.object({
        tableName: zod_1.z.string().min(1),
        bounds: zod_1.z.tuple([
            zod_1.z.number(),
            zod_1.z.number(),
            zod_1.z.number(),
            zod_1.z.number(),
        ]).optional(),
        center: zod_1.z.tuple([zod_1.z.number(), zod_1.z.number()]).optional(),
        distance: zod_1.z.number().positive().optional(),
        unit: zod_1.z.enum(['meters', 'kilometers', 'miles', 'feet']).optional(),
        geometry: geometrySchema.optional(),
        properties: zod_1.z.array(zod_1.z.string()).optional(),
    }),
});
exports.bufferSchema = zod_1.z.object({
    body: zod_1.z.object({
        geometry: geometrySchema,
        distance: zod_1.z.number().positive(),
        unit: zod_1.z.enum(['meters', 'kilometers', 'miles', 'feet']).optional(),
        options: zod_1.z.object({
            steps: zod_1.z.number().int().positive().optional(),
            units: zod_1.z.string().optional(),
        }).optional(),
    }),
});
exports.unionSchema = zod_1.z.object({
    body: zod_1.z.object({
        geometries: zod_1.z.array(geometrySchema).min(2),
    }),
});
exports.intersectionSchema = zod_1.z.object({
    body: zod_1.z.object({
        geometry1: geometrySchema,
        geometry2: geometrySchema,
    }),
});
//# sourceMappingURL=spatial.validator.js.map