import { z } from 'zod';
export declare const createParcelSchema: z.ZodObject<{
    body: z.ZodObject<{
        parcelCode: z.ZodString;
        area: z.ZodNumber;
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
        zoneId: z.ZodString;
        landUseType: z.ZodString;
        soilType: z.ZodOptional<z.ZodString>;
        ownerName: z.ZodString;
        ownerContact: z.ZodOptional<z.ZodString>;
        irrigationStatus: z.ZodEnum<["irrigated", "non-irrigated", "partial"]>;
        waterRights: z.ZodOptional<z.ZodNumber>;
        metadata: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    }, "strip", z.ZodTypeAny, {
        zoneId: string;
        geometry: {
            type: "Polygon";
            coordinates: [number, number][][];
        };
        area: number;
        parcelCode: string;
        landUseType: string;
        ownerName: string;
        irrigationStatus: "irrigated" | "non-irrigated" | "partial";
        soilType?: string | undefined;
        metadata?: Record<string, any> | undefined;
        ownerContact?: string | undefined;
        waterRights?: number | undefined;
    }, {
        zoneId: string;
        geometry: {
            type: "Polygon";
            coordinates: [number, number][][];
        };
        area: number;
        parcelCode: string;
        landUseType: string;
        ownerName: string;
        irrigationStatus: "irrigated" | "non-irrigated" | "partial";
        soilType?: string | undefined;
        metadata?: Record<string, any> | undefined;
        ownerContact?: string | undefined;
        waterRights?: number | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    body: {
        zoneId: string;
        geometry: {
            type: "Polygon";
            coordinates: [number, number][][];
        };
        area: number;
        parcelCode: string;
        landUseType: string;
        ownerName: string;
        irrigationStatus: "irrigated" | "non-irrigated" | "partial";
        soilType?: string | undefined;
        metadata?: Record<string, any> | undefined;
        ownerContact?: string | undefined;
        waterRights?: number | undefined;
    };
}, {
    body: {
        zoneId: string;
        geometry: {
            type: "Polygon";
            coordinates: [number, number][][];
        };
        area: number;
        parcelCode: string;
        landUseType: string;
        ownerName: string;
        irrigationStatus: "irrigated" | "non-irrigated" | "partial";
        soilType?: string | undefined;
        metadata?: Record<string, any> | undefined;
        ownerContact?: string | undefined;
        waterRights?: number | undefined;
    };
}>;
export declare const updateParcelSchema: z.ZodObject<{
    params: z.ZodObject<{
        id: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        id: string;
    }, {
        id: string;
    }>;
    body: z.ZodObject<{
        parcelCode: z.ZodOptional<z.ZodString>;
        area: z.ZodOptional<z.ZodNumber>;
        landUseType: z.ZodOptional<z.ZodString>;
        soilType: z.ZodOptional<z.ZodString>;
        ownerName: z.ZodOptional<z.ZodString>;
        ownerContact: z.ZodOptional<z.ZodString>;
        irrigationStatus: z.ZodOptional<z.ZodEnum<["irrigated", "non-irrigated", "partial"]>>;
        waterRights: z.ZodOptional<z.ZodNumber>;
        metadata: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    }, "strip", z.ZodTypeAny, {
        area?: number | undefined;
        soilType?: string | undefined;
        metadata?: Record<string, any> | undefined;
        parcelCode?: string | undefined;
        landUseType?: string | undefined;
        ownerName?: string | undefined;
        irrigationStatus?: "irrigated" | "non-irrigated" | "partial" | undefined;
        ownerContact?: string | undefined;
        waterRights?: number | undefined;
    }, {
        area?: number | undefined;
        soilType?: string | undefined;
        metadata?: Record<string, any> | undefined;
        parcelCode?: string | undefined;
        landUseType?: string | undefined;
        ownerName?: string | undefined;
        irrigationStatus?: "irrigated" | "non-irrigated" | "partial" | undefined;
        ownerContact?: string | undefined;
        waterRights?: number | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    params: {
        id: string;
    };
    body: {
        area?: number | undefined;
        soilType?: string | undefined;
        metadata?: Record<string, any> | undefined;
        parcelCode?: string | undefined;
        landUseType?: string | undefined;
        ownerName?: string | undefined;
        irrigationStatus?: "irrigated" | "non-irrigated" | "partial" | undefined;
        ownerContact?: string | undefined;
        waterRights?: number | undefined;
    };
}, {
    params: {
        id: string;
    };
    body: {
        area?: number | undefined;
        soilType?: string | undefined;
        metadata?: Record<string, any> | undefined;
        parcelCode?: string | undefined;
        landUseType?: string | undefined;
        ownerName?: string | undefined;
        irrigationStatus?: "irrigated" | "non-irrigated" | "partial" | undefined;
        ownerContact?: string | undefined;
        waterRights?: number | undefined;
    };
}>;
export declare const queryParcelSchema: z.ZodObject<{
    body: z.ZodObject<{
        zoneId: z.ZodOptional<z.ZodString>;
        landUseType: z.ZodOptional<z.ZodString>;
        irrigationStatus: z.ZodOptional<z.ZodEnum<["irrigated", "non-irrigated", "partial"]>>;
        ownerName: z.ZodOptional<z.ZodString>;
        minArea: z.ZodOptional<z.ZodNumber>;
        maxArea: z.ZodOptional<z.ZodNumber>;
        bounds: z.ZodOptional<z.ZodTuple<[z.ZodNumber, z.ZodNumber, z.ZodNumber, z.ZodNumber], null>>;
    }, "strip", z.ZodTypeAny, {
        zoneId?: string | undefined;
        bounds?: [number, number, number, number] | undefined;
        landUseType?: string | undefined;
        ownerName?: string | undefined;
        minArea?: number | undefined;
        maxArea?: number | undefined;
        irrigationStatus?: "irrigated" | "non-irrigated" | "partial" | undefined;
    }, {
        zoneId?: string | undefined;
        bounds?: [number, number, number, number] | undefined;
        landUseType?: string | undefined;
        ownerName?: string | undefined;
        minArea?: number | undefined;
        maxArea?: number | undefined;
        irrigationStatus?: "irrigated" | "non-irrigated" | "partial" | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    body: {
        zoneId?: string | undefined;
        bounds?: [number, number, number, number] | undefined;
        landUseType?: string | undefined;
        ownerName?: string | undefined;
        minArea?: number | undefined;
        maxArea?: number | undefined;
        irrigationStatus?: "irrigated" | "non-irrigated" | "partial" | undefined;
    };
}, {
    body: {
        zoneId?: string | undefined;
        bounds?: [number, number, number, number] | undefined;
        landUseType?: string | undefined;
        ownerName?: string | undefined;
        minArea?: number | undefined;
        maxArea?: number | undefined;
        irrigationStatus?: "irrigated" | "non-irrigated" | "partial" | undefined;
    };
}>;
export declare const parcelIdSchema: z.ZodObject<{
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
export declare const transferOwnershipSchema: z.ZodObject<{
    params: z.ZodObject<{
        id: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        id: string;
    }, {
        id: string;
    }>;
    body: z.ZodObject<{
        newOwnerId: z.ZodString;
        transferDate: z.ZodString;
        notes: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        newOwnerId: string;
        transferDate: string;
        notes?: string | undefined;
    }, {
        newOwnerId: string;
        transferDate: string;
        notes?: string | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    params: {
        id: string;
    };
    body: {
        newOwnerId: string;
        transferDate: string;
        notes?: string | undefined;
    };
}, {
    params: {
        id: string;
    };
    body: {
        newOwnerId: string;
        transferDate: string;
        notes?: string | undefined;
    };
}>;
//# sourceMappingURL=parcel.validator.d.ts.map