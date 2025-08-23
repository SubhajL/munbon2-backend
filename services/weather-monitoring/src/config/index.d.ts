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
    postgres: {
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
        highTempThreshold: any;
        lowTempThreshold: any;
        highWindSpeedThreshold: any;
        heavyRainThreshold: any;
        frostWarningTemp: any;
        cooldownMinutes: any;
    };
    analytics: {
        retentionDays: any;
        aggregationIntervals: any;
        cacheTTLSeconds: any;
    };
    forecasting: {
        shortTermDays: any;
        longTermDays: any;
        updateIntervalMinutes: any;
        confidenceThreshold: any;
    };
    irrigation: {
        etCalculationMethod: any;
        soilMoistureWeight: any;
        forecastWeight: any;
        recommendationHorizonDays: any;
    };
    services: {
        notificationUrl: any;
        alertUrl: any;
        aiModelUrl: any;
        cropManagementUrl: any;
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