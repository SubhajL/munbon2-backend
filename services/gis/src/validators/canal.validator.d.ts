import { z } from 'zod';
export declare const createCanalSchema: z.ZodObject<{
    body: z.ZodObject<{
        code: z.ZodString;
        name: z.ZodString;
        type: z.ZodEnum<["main", "secondary", "tertiary", "field"]>;
        level: z.ZodNumber;
        geometry: z.ZodObject<{
            type: z.ZodLiteral<"LineString">;
            coordinates: z.ZodArray<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>, "many">;
        }, "strip", z.ZodTypeAny, {
            type: "LineString";
            coordinates: [number, number][];
        }, {
            type: "LineString";
            coordinates: [number, number][];
        }>;
        length: z.ZodOptional<z.ZodNumber>;
        width: z.ZodOptional<z.ZodNumber>;
        depth: z.ZodOptional<z.ZodNumber>;
        capacity: z.ZodNumber;
        material: z.ZodOptional<z.ZodString>;
        constructionYear: z.ZodOptional<z.ZodNumber>;
        metadata: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    }, "strip", z.ZodTypeAny, {
        level: number;
        code: string;
        name: string;
        geometry: {
            type: "LineString";
            coordinates: [number, number][];
        };
        type: "main" | "field" | "secondary" | "tertiary";
        capacity: number;
        length?: number | undefined;
        metadata?: Record<string, any> | undefined;
        depth?: number | undefined;
        width?: number | undefined;
        material?: string | undefined;
        constructionYear?: number | undefined;
    }, {
        level: number;
        code: string;
        name: string;
        geometry: {
            type: "LineString";
            coordinates: [number, number][];
        };
        type: "main" | "field" | "secondary" | "tertiary";
        capacity: number;
        length?: number | undefined;
        metadata?: Record<string, any> | undefined;
        depth?: number | undefined;
        width?: number | undefined;
        material?: string | undefined;
        constructionYear?: number | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    body: {
        level: number;
        code: string;
        name: string;
        geometry: {
            type: "LineString";
            coordinates: [number, number][];
        };
        type: "main" | "field" | "secondary" | "tertiary";
        capacity: number;
        length?: number | undefined;
        metadata?: Record<string, any> | undefined;
        depth?: number | undefined;
        width?: number | undefined;
        material?: string | undefined;
        constructionYear?: number | undefined;
    };
}, {
    body: {
        level: number;
        code: string;
        name: string;
        geometry: {
            type: "LineString";
            coordinates: [number, number][];
        };
        type: "main" | "field" | "secondary" | "tertiary";
        capacity: number;
        length?: number | undefined;
        metadata?: Record<string, any> | undefined;
        depth?: number | undefined;
        width?: number | undefined;
        material?: string | undefined;
        constructionYear?: number | undefined;
    };
}>;
export declare const updateCanalSchema: z.ZodObject<{
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
        type: z.ZodOptional<z.ZodEnum<["main", "secondary", "tertiary", "field"]>>;
        status: z.ZodOptional<z.ZodEnum<["operational", "maintenance", "closed", "damaged"]>>;
        capacity: z.ZodOptional<z.ZodNumber>;
        currentFlow: z.ZodOptional<z.ZodNumber>;
        metadata: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    }, "strip", z.ZodTypeAny, {
        code?: string | undefined;
        name?: string | undefined;
        type?: "main" | "field" | "secondary" | "tertiary" | undefined;
        status?: "operational" | "maintenance" | "closed" | "damaged" | undefined;
        metadata?: Record<string, any> | undefined;
        capacity?: number | undefined;
        currentFlow?: number | undefined;
    }, {
        code?: string | undefined;
        name?: string | undefined;
        type?: "main" | "field" | "secondary" | "tertiary" | undefined;
        status?: "operational" | "maintenance" | "closed" | "damaged" | undefined;
        metadata?: Record<string, any> | undefined;
        capacity?: number | undefined;
        currentFlow?: number | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    params: {
        id: string;
    };
    body: {
        code?: string | undefined;
        name?: string | undefined;
        type?: "main" | "field" | "secondary" | "tertiary" | undefined;
        status?: "operational" | "maintenance" | "closed" | "damaged" | undefined;
        metadata?: Record<string, any> | undefined;
        capacity?: number | undefined;
        currentFlow?: number | undefined;
    };
}, {
    params: {
        id: string;
    };
    body: {
        code?: string | undefined;
        name?: string | undefined;
        type?: "main" | "field" | "secondary" | "tertiary" | undefined;
        status?: "operational" | "maintenance" | "closed" | "damaged" | undefined;
        metadata?: Record<string, any> | undefined;
        capacity?: number | undefined;
        currentFlow?: number | undefined;
    };
}>;
export declare const queryCanalSchema: z.ZodObject<{
    body: z.ZodObject<{
        type: z.ZodOptional<z.ZodEnum<["main", "secondary", "tertiary", "field"]>>;
        level: z.ZodOptional<z.ZodNumber>;
        status: z.ZodOptional<z.ZodEnum<["operational", "maintenance", "closed", "damaged"]>>;
        minCapacity: z.ZodOptional<z.ZodNumber>;
        maxCapacity: z.ZodOptional<z.ZodNumber>;
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
        level?: number | undefined;
        type?: "main" | "field" | "secondary" | "tertiary" | undefined;
        maxCapacity?: number | undefined;
        bounds?: [number, number, number, number] | undefined;
        status?: "operational" | "maintenance" | "closed" | "damaged" | undefined;
        nearPoint?: {
            distance: number;
            lng: number;
            lat: number;
        } | undefined;
        minCapacity?: number | undefined;
    }, {
        level?: number | undefined;
        type?: "main" | "field" | "secondary" | "tertiary" | undefined;
        maxCapacity?: number | undefined;
        bounds?: [number, number, number, number] | undefined;
        status?: "operational" | "maintenance" | "closed" | "damaged" | undefined;
        nearPoint?: {
            distance: number;
            lng: number;
            lat: number;
        } | undefined;
        minCapacity?: number | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    body: {
        level?: number | undefined;
        type?: "main" | "field" | "secondary" | "tertiary" | undefined;
        maxCapacity?: number | undefined;
        bounds?: [number, number, number, number] | undefined;
        status?: "operational" | "maintenance" | "closed" | "damaged" | undefined;
        nearPoint?: {
            distance: number;
            lng: number;
            lat: number;
        } | undefined;
        minCapacity?: number | undefined;
    };
}, {
    body: {
        level?: number | undefined;
        type?: "main" | "field" | "secondary" | "tertiary" | undefined;
        maxCapacity?: number | undefined;
        bounds?: [number, number, number, number] | undefined;
        status?: "operational" | "maintenance" | "closed" | "damaged" | undefined;
        nearPoint?: {
            distance: number;
            lng: number;
            lat: number;
        } | undefined;
        minCapacity?: number | undefined;
    };
}>;
export declare const canalIdSchema: z.ZodObject<{
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
export declare const flowUpdateSchema: z.ZodObject<{
    params: z.ZodObject<{
        id: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        id: string;
    }, {
        id: string;
    }>;
    body: z.ZodObject<{
        flowRate: z.ZodNumber;
        measuredAt: z.ZodString;
        sensorId: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        flowRate: number;
        measuredAt: string;
        sensorId?: string | undefined;
    }, {
        flowRate: number;
        measuredAt: string;
        sensorId?: string | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    params: {
        id: string;
    };
    body: {
        flowRate: number;
        measuredAt: string;
        sensorId?: string | undefined;
    };
}, {
    params: {
        id: string;
    };
    body: {
        flowRate: number;
        measuredAt: string;
        sensorId?: string | undefined;
    };
}>;
//# sourceMappingURL=canal.validator.d.ts.map