import Redis from 'ioredis';
export declare const initializeRedis: () => Promise<void>;
export declare const getRedisClient: () => Redis;
export declare const getRedisSubscriber: () => Redis;
export declare const RedisKeys: {
    fieldState: (fieldId: string) => string;
    fieldConfig: (fieldId: string) => string;
    fieldSensors: (fieldId: string) => string;
    sensorReading: (sensorId: string) => string;
    sensorStatus: (sensorId: string) => string;
    irrigationQueue: string;
    irrigationActive: string;
    fieldIrrigationHistory: (fieldId: string) => string;
    controlLock: (fieldId: string) => string;
    emergencyOverride: string;
    dailyWaterUsage: (date: string) => string;
    fieldMetrics: (fieldId: string) => string;
    systemHealth: string;
    activeAlerts: string;
};
export declare const closeRedis: () => Promise<void>;
//# sourceMappingURL=redis.d.ts.map