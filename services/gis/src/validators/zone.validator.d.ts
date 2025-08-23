import { z } from 'zod';
export declare const createZoneSchema: z.ZodObject<{
    body: z.ZodObject<{
        code: z.ZodString;
        name: z.ZodString;
        type: z.ZodEnum<["irrigation", "drainage", "mixed"]>;
        geometry: z.ZodObject<{
            type: z.ZodLiteral<"Polygon">;
            coordinates: z.ZodArray<z.ZodArray<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>, "many">, "many">;
        }, "strip", z.ZodTypeAny, {
            type: "Polygon";
            coordinates: [number, number][][];
        }, {
            type: "Polygon";
            coordinates: [number, number][][];
        }>;
        waterAllocation: z.ZodOptional<z.ZodNumber>;
        description: z.ZodOptional<z.ZodString>;
        metadata: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    }, "strip", z.ZodTypeAny, {
        code: string;
        name: string;
        geometry: {
            type: "Polygon";
            coordinates: [number, number][][];
        };
        type: "mixed" | "drainage" | "irrigation";
        waterAllocation?: number | undefined;
        metadata?: Record<string, any> | undefined;
        description?: string | undefined;
    }, {
        code: string;
        name: string;
        geometry: {
            type: "Polygon";
            coordinates: [number, number][][];
        };
        type: "mixed" | "drainage" | "irrigation";
        waterAllocation?: number | undefined;
        metadata?: Record<string, any> | undefined;
        description?: string | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    body: {
        code: string;
        name: string;
        geometry: {
            type: "Polygon";
            coordinates: [number, number][][];
        };
        type: "mixed" | "drainage" | "irrigation";
        waterAllocation?: number | undefined;
        metadata?: Record<string, any> | undefined;
        description?: string | undefined;
    };
}, {
    body: {
        code: string;
        name: string;
        geometry: {
            type: "Polygon";
            coordinates: [number, number][][];
        };
        type: "mixed" | "drainage" | "irrigation";
        waterAllocation?: number | undefined;
        metadata?: Record<string, any> | undefined;
        description?: string | undefined;
    };
}>;
export declare const updateZoneSchema: z.ZodObject<{
    params: z.ZodObject<{
        id: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        id: string;
    }, {
        id: string;
    }>;
    body: z.ZodObject<{
        code: z.ZodOptional<z.ZodString>;
        name: z.ZodOptional<z.ZodString>;
        type: z.ZodOptional<z.ZodEnum<["irrigation", "drainage", "mixed"]>>;
        waterAllocation: z.ZodOptional<z.ZodNumber>;
        status: z.ZodOptional<z.ZodEnum<["active", "inactive", "maintenance"]>>;
        description: z.ZodOptional<z.ZodString>;
        metadata: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    }, "strip", z.ZodTypeAny, {
        code?: string | undefined;
        name?: string | undefined;
        type?: "mixed" | "drainage" | "irrigation" | undefined;
        waterAllocation?: number | undefined;
        status?: "active" | "inactive" | "maintenance" | undefined;
        metadata?: Record<string, any> | undefined;
        description?: string | undefined;
    }, {
        code?: string | undefined;
        name?: string | undefined;
        type?: "mixed" | "drainage" | "irrigation" | undefined;
        waterAllocation?: number | undefined;
        status?: "active" | "inactive" | "maintenance" | undefined;
        metadata?: Record<string, any> | undefined;
        description?: string | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    params: {
        id: string;
    };
    body: {
        code?: string | undefined;
        name?: string | undefined;
        type?: "mixed" | "drainage" | "irrigation" | undefined;
        waterAllocation?: number | undefined;
        status?: "active" | "inactive" | "maintenance" | undefined;
        metadata?: Record<string, any> | undefined;
        description?: string | undefined;
    };
}, {
    params: {
        id: string;
    };
    body: {
        code?: string | undefined;
        name?: string | undefined;
        type?: "mixed" | "drainage" | "irrigation" | undefined;
        waterAllocation?: number | undefined;
        status?: "active" | "inactive" | "maintenance" | undefined;
        metadata?: Record<string, any> | undefined;
        description?: string | undefined;
    };
}>;
export declare const queryZoneSchema: z.ZodObject<{
    body: z.ZodObject<{
        type: z.ZodOptional<z.ZodEnum<["irrigation", "drainage", "mixed"]>>;
        status: z.ZodOptional<z.ZodEnum<["active", "inactive", "maintenance"]>>;
        minArea: z.ZodOptional<z.ZodNumber>;
        maxArea: z.ZodOptional<z.ZodNumber>;
        bounds: z.ZodOptional<z.ZodTuple<[z.ZodNumber, z.ZodNumber, z.ZodNumber, z.ZodNumber], null>>;
        nearPoint: z.ZodOptional<z.ZodObject<{
            lng: z.ZodNumber;
            lat: z.ZodNumber;
            distance: z.ZodNumber;
        }, "strip", z.ZodTypeAny, {
            distance: number;
            lng: number;
            lat: number;
        }, {
            distance: number;
            lng: number;
            lat: number;
        }>>;
    }, "strip", z.ZodTypeAny, {
        type?: "mixed" | "drainage" | "irrigation" | undefined;
        bounds?: [number, number, number, number] | undefined;
        status?: "active" | "inactive" | "maintenance" | undefined;
        minArea?: number | undefined;
        maxArea?: number | undefined;
        nearPoint?: {
            distance: number;
            lng: number;
            lat: number;
        } | undefined;
    }, {
        type?: "mixed" | "drainage" | "irrigation" | undefined;
        bounds?: [number, number, number, number] | undefined;
        status?: "active" | "inactive" | "maintenance" | undefined;
        minArea?: number | undefined;
        maxArea?: number | undefined;
        nearPoint?: {
            distance: number;
            lng: number;
            lat: number;
        } | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    body: {
        type?: "mixed" | "drainage" | "irrigation" | undefined;
        bounds?: [number, number, number, number] | undefined;
        status?: "active" | "inactive" | "maintenance" | undefined;
        minArea?: number | undefined;
        maxArea?: number | undefined;
        nearPoint?: {
            distance: number;
            lng: number;
            lat: number;
        } | undefined;
    };
}, {
    body: {
        type?: "mixed" | "drainage" | "irrigation" | undefined;
        bounds?: [number, number, number, number] | undefined;
        status?: "active" | "inactive" | "maintenance" | undefined;
        minArea?: number | undefined;
        maxArea?: number | undefined;
        nearPoint?: {
            distance: number;
            lng: number;
            lat: number;
        } | undefined;
    };
}>;
export declare const zoneIdSchema: z.ZodObject<{
    params: z.ZodObject<{
        id: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        id: string;
    }, {
        id: string;
    }>;
}, "strip", z.ZodTypeAny, {
    params: {
        id: string;
    };
}, {
    params: {
        id: string;
    };
}>;
//# sourceMappingURL=zone.validator.d.ts.map