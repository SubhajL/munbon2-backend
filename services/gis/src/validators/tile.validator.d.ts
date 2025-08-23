import { z } from 'zod';
export declare const tileRequestSchema: z.ZodObject<{
    params: z.ZodObject<{
        layer: z.ZodEnum<["zones", "parcels", "canals", "gates", "pumps"]>;
        z: z.ZodPipeline<z.ZodEffects<z.ZodString, number, string>, z.ZodNumber>;
        x: z.ZodPipeline<z.ZodEffects<z.ZodString, number, string>, z.ZodNumber>;
        y: z.ZodPipeline<z.ZodEffects<z.ZodString, number, string>, z.ZodNumber>;
    }, "strip", z.ZodTypeAny, {
        z: number;
        x: number;
        y: number;
        layer: "gates" | "parcels" | "canals" | "zones" | "pumps";
    }, {
        z: string;
        x: string;
        y: string;
        layer: "gates" | "parcels" | "canals" | "zones" | "pumps";
    }>;
}, "strip", z.ZodTypeAny, {
    params: {
        z: number;
        x: number;
        y: number;
        layer: "gates" | "parcels" | "canals" | "zones" | "pumps";
    };
}, {
    params: {
        z: string;
        x: string;
        y: string;
        layer: "gates" | "parcels" | "canals" | "zones" | "pumps";
    };
}>;
//# sourceMappingURL=tile.validator.d.ts.map