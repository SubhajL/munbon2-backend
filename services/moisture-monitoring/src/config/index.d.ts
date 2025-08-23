export declare const config: {
    env: any;
    port: any;
    host: any;
    logLevel: any;
    timescale: {
        host: any;
        port: any;
        database: any;
        user: any;
        password: any;
        ssl: any;
    };
    redis: {
        host: any;
        port: any;
        password: any;
        db: any;
    };
    mqtt: {
        brokerUrl: any;
        clientId: any;
        username: any;
        password: any;
        reconnectPeriod: any;
    };
    websocket: {
        path: any;
        corsOrigin: any;
    };
    alerts: {
        lowMoistureThreshold: any;
        criticalLowMoistureThreshold: any;
        highMoistureThreshold: any;
        floodDetectionEnabled: any;
        cooldownMinutes: any;
    };
    analytics: {
        retentionDays: any;
        aggregationIntervals: any;
        cacheTTLSeconds: any;
    };
    services: {
        notificationUrl: any;
        alertUrl: any;
    };
    rateLimit: {
        windowMs: any;
        maxRequests: any;
    };
    monitoring: {
        healthCheckIntervalMs: any;
        metricsEnabled: any;
        metricsPort: any;
    };
};
//# sourceMappingURL=index.d.ts.map