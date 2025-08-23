export declare const config: {
    env: string;
    port: number;
    serviceName: string;
    database: {
        host: string;
        port: number;
        database: string;
        user: string;
        password: string;
        maxConnections: number;
        idleTimeoutMillis: number;
    };
    redis: {
        host: string;
        port: number;
        password: string;
    };
    kafka: {
        brokers: string[];
        clientId: string;
        groupId: string;
        topics: {
            shapeFileProcessed: string;
            waterDemandUpdated: string;
            processingError: string;
        };
    };
    fileProcessing: {
        uploadDir: string;
        processedDir: string;
        archiveDir: string;
        maxFileSize: number;
        allowedFileTypes: string[];
        retentionDays: number;
        batchSize: number;
    };
    waterDemand: {
        defaultMethod: string;
        updateInterval: string;
        coordinateSystem: string;
    };
    api: {
        prefix: string;
        rateLimitWindow: number;
        rateLimitMaxRequests: number;
    };
    logging: {
        level: string;
        file: string;
    };
    jobs: {
        shapeFileCheckCron: string;
        cleanupCron: string;
    };
    integrations: {
        gisService: {
            url: string;
            apiKey: string;
        };
        waterDemandService: {
            url: string;
            apiKey: string;
        };
    };
};
//# sourceMappingURL=index.d.ts.map