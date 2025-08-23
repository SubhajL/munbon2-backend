"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.tileRequestSchema = void 0;
const zod_1 = require("zod");
exports.tileRequestSchema = zod_1.z.object({
    params: zod_1.z.object({
        layer: zod_1.z.enum(['zones', 'parcels', 'canals', 'gates', 'pumps']),
        z: zod_1.z.string().transform(val => parseInt(val, 10)).pipe(zod_1.z.number().int().min(0).max(20)),
        x: zod_1.z.string().transform(val => parseInt(val, 10)).pipe(zod_1.z.number().int().min(0)),
        y: zod_1.z.string().transform(val => parseInt(val, 10)).pipe(zod_1.z.number().int().min(0)),
    }),
});
//# sourceMappingURL=tile.validator.js.map