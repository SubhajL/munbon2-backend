import { z } from 'zod';
export declare const shapeFileUploadValidator: z.ZodObject<{
    body: z.ZodObject<{
        waterDemandMethod: z.ZodDefault<z.ZodEnum<["RID-MS", "ROS", "AWD"]>>;
        processingInterval: z.ZodDefault<z.ZodEnum<["daily", "weekly", "bi-weekly"]>>;
        zone: z.ZodOptional<z.ZodString>;
        description: z.ZodOptional<z.ZodString>;
        metadata: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodAny>>;
    }, "strip", z.ZodTypeAny, {
        waterDemandMethod: "RID-MS" | "ROS" | "AWD";
        processingInterval: "daily" | "weekly" | "bi-weekly";
        zone?: string | undefined;
        metadata?: Record<string, any> | undefined;
        description?: string | undefined;
    }, {
        zone?: string | undefined;
        metadata?: Record<string, any> | undefined;
        description?: string | undefined;
        waterDemandMethod?: "RID-MS" | "ROS" | "AWD" | undefined;
        processingInterval?: "daily" | "weekly" | "bi-weekly" | undefined;
    }>;
    query: z.ZodOptional<z.ZodObject<{}, "strip", z.ZodTypeAny, {}, {}>>;
    params: z.ZodOptional<z.ZodObject<{}, "strip", z.ZodTypeAny, {}, {}>>;
}, "strip", z.ZodTypeAny, {
    body: {
        waterDemandMethod: "RID-MS" | "ROS" | "AWD";
        processingInterval: "daily" | "weekly" | "bi-weekly";
        zone?: string | undefined;
        metadata?: Record<string, any> | undefined;
        description?: string | undefined;
    };
    query?: {} | undefined;
    params?: {} | undefined;
}, {
    body: {
        zone?: string | undefined;
        metadata?: Record<string, any> | undefined;
        description?: string | undefined;
        waterDemandMethod?: "RID-MS" | "ROS" | "AWD" | undefined;
        processingInterval?: "daily" | "weekly" | "bi-weekly" | undefined;
    };
    query?: {} | undefined;
    params?: {} | undefined;
}>;
//# sourceMappingURL=shapefile-zod.validator.d.ts.map