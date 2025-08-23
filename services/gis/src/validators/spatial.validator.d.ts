import { z } from 'zod';
export declare const spatialQuerySchema: z.ZodObject<{
    body: z.ZodObject<{
        tableName: z.ZodString;
        bounds: z.ZodOptional<z.ZodTuple<[z.ZodNumber, z.ZodNumber, z.ZodNumber, z.ZodNumber], null>>;
        center: z.ZodOptional<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>>;
        distance: z.ZodOptional<z.ZodNumber>;
        unit: z.ZodOptional<z.ZodEnum<["meters", "kilometers", "miles", "feet"]>>;
        geometry: z.ZodOptional<z.ZodUnion<[z.ZodObject<{
            type: z.ZodLiteral<"Point">;
            coordinates: z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>;
        }, "strip", z.ZodTypeAny, {
            type: "Point";
            coordinates: [number, number];
        }, {
            type: "Point";
            coordinates: [number, number];
        }>, z.ZodObject<{
            type: z.ZodLiteral<"LineString">;
            coordinates: z.ZodArray<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>, "many">;
        }, "strip", z.ZodTypeAny, {
            type: "LineString";
            coordinates: [number, number][];
        }, {
            type: "LineString";
            coordinates: [number, number][];
        }>, z.ZodObject<{
            type: z.ZodLiteral<"Polygon">;
            coordinates: z.ZodArray<z.ZodArray<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>, "many">, "many">;
        }, "strip", z.ZodTypeAny, {
            type: "Polygon";
            coordinates: [number, number][][];
        }, {
            type: "Polygon";
            coordinates: [number, number][][];
        }>]>>;
        properties: z.ZodOptional<z.ZodArray<z.ZodString, "many">>;
    }, "strip", z.ZodTypeAny, {
        tableName: string;
        geometry?: {
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        } | undefined;
        properties?: string[] | undefined;
        bounds?: [number, number, number, number] | undefined;
        distance?: number | undefined;
        unit?: "meters" | "kilometers" | "miles" | "feet" | undefined;
        center?: [number, number] | undefined;
    }, {
        tableName: string;
        geometry?: {
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        } | undefined;
        properties?: string[] | undefined;
        bounds?: [number, number, number, number] | undefined;
        distance?: number | undefined;
        unit?: "meters" | "kilometers" | "miles" | "feet" | undefined;
        center?: [number, number] | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    body: {
        tableName: string;
        geometry?: {
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        } | undefined;
        properties?: string[] | undefined;
        bounds?: [number, number, number, number] | undefined;
        distance?: number | undefined;
        unit?: "meters" | "kilometers" | "miles" | "feet" | undefined;
        center?: [number, number] | undefined;
    };
}, {
    body: {
        tableName: string;
        geometry?: {
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        } | undefined;
        properties?: string[] | undefined;
        bounds?: [number, number, number, number] | undefined;
        distance?: number | undefined;
        unit?: "meters" | "kilometers" | "miles" | "feet" | undefined;
        center?: [number, number] | undefined;
    };
}>;
export declare const bufferSchema: z.ZodObject<{
    body: z.ZodObject<{
        geometry: z.ZodUnion<[z.ZodObject<{
            type: z.ZodLiteral<"Point">;
            coordinates: z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>;
        }, "strip", z.ZodTypeAny, {
            type: "Point";
            coordinates: [number, number];
        }, {
            type: "Point";
            coordinates: [number, number];
        }>, z.ZodObject<{
            type: z.ZodLiteral<"LineString">;
            coordinates: z.ZodArray<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>, "many">;
        }, "strip", z.ZodTypeAny, {
            type: "LineString";
            coordinates: [number, number][];
        }, {
            type: "LineString";
            coordinates: [number, number][];
        }>, z.ZodObject<{
            type: z.ZodLiteral<"Polygon">;
            coordinates: z.ZodArray<z.ZodArray<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>, "many">, "many">;
        }, "strip", z.ZodTypeAny, {
            type: "Polygon";
            coordinates: [number, number][][];
        }, {
            type: "Polygon";
            coordinates: [number, number][][];
        }>]>;
        distance: z.ZodNumber;
        unit: z.ZodOptional<z.ZodEnum<["meters", "kilometers", "miles", "feet"]>>;
        options: z.ZodOptional<z.ZodObject<{
            steps: z.ZodOptional<z.ZodNumber>;
            units: z.ZodOptional<z.ZodString>;
        }, "strip", z.ZodTypeAny, {
            steps?: number | undefined;
            units?: string | undefined;
        }, {
            steps?: number | undefined;
            units?: string | undefined;
        }>>;
    }, "strip", z.ZodTypeAny, {
        geometry: {
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        };
        distance: number;
        unit?: "meters" | "kilometers" | "miles" | "feet" | undefined;
        options?: {
            steps?: number | undefined;
            units?: string | undefined;
        } | undefined;
    }, {
        geometry: {
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        };
        distance: number;
        unit?: "meters" | "kilometers" | "miles" | "feet" | undefined;
        options?: {
            steps?: number | undefined;
            units?: string | undefined;
        } | undefined;
    }>;
}, "strip", z.ZodTypeAny, {
    body: {
        geometry: {
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        };
        distance: number;
        unit?: "meters" | "kilometers" | "miles" | "feet" | undefined;
        options?: {
            steps?: number | undefined;
            units?: string | undefined;
        } | undefined;
    };
}, {
    body: {
        geometry: {
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        };
        distance: number;
        unit?: "meters" | "kilometers" | "miles" | "feet" | undefined;
        options?: {
            steps?: number | undefined;
            units?: string | undefined;
        } | undefined;
    };
}>;
export declare const unionSchema: z.ZodObject<{
    body: z.ZodObject<{
        geometries: z.ZodArray<z.ZodUnion<[z.ZodObject<{
            type: z.ZodLiteral<"Point">;
            coordinates: z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>;
        }, "strip", z.ZodTypeAny, {
            type: "Point";
            coordinates: [number, number];
        }, {
            type: "Point";
            coordinates: [number, number];
        }>, z.ZodObject<{
            type: z.ZodLiteral<"LineString">;
            coordinates: z.ZodArray<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>, "many">;
        }, "strip", z.ZodTypeAny, {
            type: "LineString";
            coordinates: [number, number][];
        }, {
            type: "LineString";
            coordinates: [number, number][];
        }>, z.ZodObject<{
            type: z.ZodLiteral<"Polygon">;
            coordinates: z.ZodArray<z.ZodArray<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>, "many">, "many">;
        }, "strip", z.ZodTypeAny, {
            type: "Polygon";
            coordinates: [number, number][][];
        }, {
            type: "Polygon";
            coordinates: [number, number][][];
        }>]>, "many">;
    }, "strip", z.ZodTypeAny, {
        geometries: ({
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        })[];
    }, {
        geometries: ({
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        })[];
    }>;
}, "strip", z.ZodTypeAny, {
    body: {
        geometries: ({
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        })[];
    };
}, {
    body: {
        geometries: ({
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        })[];
    };
}>;
export declare const intersectionSchema: z.ZodObject<{
    body: z.ZodObject<{
        geometry1: z.ZodUnion<[z.ZodObject<{
            type: z.ZodLiteral<"Point">;
            coordinates: z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>;
        }, "strip", z.ZodTypeAny, {
            type: "Point";
            coordinates: [number, number];
        }, {
            type: "Point";
            coordinates: [number, number];
        }>, z.ZodObject<{
            type: z.ZodLiteral<"LineString">;
            coordinates: z.ZodArray<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>, "many">;
        }, "strip", z.ZodTypeAny, {
            type: "LineString";
            coordinates: [number, number][];
        }, {
            type: "LineString";
            coordinates: [number, number][];
        }>, z.ZodObject<{
            type: z.ZodLiteral<"Polygon">;
            coordinates: z.ZodArray<z.ZodArray<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>, "many">, "many">;
        }, "strip", z.ZodTypeAny, {
            type: "Polygon";
            coordinates: [number, number][][];
        }, {
            type: "Polygon";
            coordinates: [number, number][][];
        }>]>;
        geometry2: z.ZodUnion<[z.ZodObject<{
            type: z.ZodLiteral<"Point">;
            coordinates: z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>;
        }, "strip", z.ZodTypeAny, {
            type: "Point";
            coordinates: [number, number];
        }, {
            type: "Point";
            coordinates: [number, number];
        }>, z.ZodObject<{
            type: z.ZodLiteral<"LineString">;
            coordinates: z.ZodArray<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>, "many">;
        }, "strip", z.ZodTypeAny, {
            type: "LineString";
            coordinates: [number, number][];
        }, {
            type: "LineString";
            coordinates: [number, number][];
        }>, z.ZodObject<{
            type: z.ZodLiteral<"Polygon">;
            coordinates: z.ZodArray<z.ZodArray<z.ZodTuple<[z.ZodNumber, z.ZodNumber], null>, "many">, "many">;
        }, "strip", z.ZodTypeAny, {
            type: "Polygon";
            coordinates: [number, number][][];
        }, {
            type: "Polygon";
            coordinates: [number, number][][];
        }>]>;
    }, "strip", z.ZodTypeAny, {
        geometry1: {
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        };
        geometry2: {
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        };
    }, {
        geometry1: {
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        };
        geometry2: {
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        };
    }>;
}, "strip", z.ZodTypeAny, {
    body: {
        geometry1: {
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        };
        geometry2: {
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        };
    };
}, {
    body: {
        geometry1: {
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        };
        geometry2: {
            type: "Point";
            coordinates: [number, number];
        } | {
            type: "LineString";
            coordinates: [number, number][];
        } | {
            type: "Polygon";
            coordinates: [number, number][][];
        };
    };
}>;
//# sourceMappingURL=spatial.validator.d.ts.map