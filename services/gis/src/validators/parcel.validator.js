"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.transferOwnershipSchema = exports.parcelIdSchema = exports.queryParcelSchema = exports.updateParcelSchema = exports.createParcelSchema = void 0;
const zod_1 = require("zod");
const polygonSchema = zod_1.z.object({
    type: zod_1.z.literal('Polygon'),
    coordinates: zod_1.z.array(zod_1.z.array(zod_1.z.tuple([zod_1.z.number(), zod_1.z.number()]))).min(1),
});
exports.createParcelSchema = zod_1.z.object({
    body: zod_1.z.object({
        parcelCode: zod_1.z.string().min(1).max(100),
        area: zod_1.z.number().positive(),
        geometry: polygonSchema,
        zoneId: zod_1.z.string().uuid(),
        landUseType: zod_1.z.string().min(1).max(100),
        soilType: zod_1.z.string().optional(),
        ownerName: zod_1.z.string().min(1).max(200),
        ownerContact: zod_1.z.string().optional(),
        irrigationStatus: zod_1.z.enum(['irrigated', 'non-irrigated', 'partial']),
        waterRights: zod_1.z.number().min(0).optional(),
        metadata: zod_1.z.record(zod_1.z.any()).optional(),
    }),
});
exports.updateParcelSchema = zod_1.z.object({
    params: zod_1.z.object({
        id: zod_1.z.string().uuid(),
    }),
    body: zod_1.z.object({
        parcelCode: zod_1.z.string().min(1).max(100).optional(),
        area: zod_1.z.number().positive().optional(),
        landUseType: zod_1.z.string().min(1).max(100).optional(),
        soilType: zod_1.z.string().optional(),
        ownerName: zod_1.z.string().min(1).max(200).optional(),
        ownerContact: zod_1.z.string().optional(),
        irrigationStatus: zod_1.z.enum(['irrigated', 'non-irrigated', 'partial']).optional(),
        waterRights: zod_1.z.number().min(0).optional(),
        metadata: zod_1.z.record(zod_1.z.any()).optional(),
    }),
});
exports.queryParcelSchema = zod_1.z.object({
    body: zod_1.z.object({
        zoneId: zod_1.z.string().uuid().optional(),
        landUseType: zod_1.z.string().optional(),
        irrigationStatus: zod_1.z.enum(['irrigated', 'non-irrigated', 'partial']).optional(),
        ownerName: zod_1.z.string().optional(),
        minArea: zod_1.z.number().positive().optional(),
        maxArea: zod_1.z.number().positive().optional(),
        bounds: zod_1.z.tuple([
            zod_1.z.number(),
            zod_1.z.number(),
            zod_1.z.number(),
            zod_1.z.number(),
        ]).optional(),
    }),
});
exports.parcelIdSchema = zod_1.z.object({
    params: zod_1.z.object({
        id: zod_1.z.string().uuid(),
    }),
});
exports.transferOwnershipSchema = zod_1.z.object({
    params: zod_1.z.object({
        id: zod_1.z.string().uuid(),
    }),
    body: zod_1.z.object({
        newOwnerId: zod_1.z.string().uuid(),
        transferDate: zod_1.z.string().datetime(),
        notes: zod_1.z.string().optional(),
    }),
});
//# sourceMappingURL=parcel.validator.js.map