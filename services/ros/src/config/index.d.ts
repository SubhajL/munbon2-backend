export declare const config: {
    service: {
        name: string;
        port: number;
        env: string;
    };
    database: {
        host: string;
        port: number;
        name: string;
        user: string;
        password: string;
    };
    calculation: {
        defaultAltitude: number;
        defaultLatitude: number;
        defaultLongitude: number;
        psychrometricConstant: number;
    };
    irrigation: {
        surfaceEfficiency: number;
        sprinklerEfficiency: number;
        dripEfficiency: number;
        defaultEfficiency: number;
    };
    soil: {
        defaultType: string;
        fieldCapacity: number;
        wiltingPoint: number;
        totalAvailableWater: number;
    };
    mad: {
        vegetables: number;
        grainCrops: number;
        rice: number;
        default: number;
    };
    externalServices: {
        weather: string;
        gis: string;
        moisture: string;
    };
    redis: {
        host: string;
        port: number;
        db: number;
        ttl: {
            eto: number;
            kc: number;
        };
    };
};
//# sourceMappingURL=index.d.ts.map