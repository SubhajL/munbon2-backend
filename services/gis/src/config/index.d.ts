export declare const config: {
    env: any;
    port: any;
    host: any;
    database: {
        url: any;
        ssl: any;
        gisSchema: any;
        poolSize: any;
        poolIdleTimeout: any;
        enableQueryLogging: any;
    };
    redis: {
        url: any;
        password: any;
        cacheTTL: any;
    };
    storage: {
        uploadDir: any;
        maxFileSize: any;
    };
    tiles: {
        cacheEnabled: any;
        cacheDir: any;
        maxZoom: any;
        minZoom: any;
        tileSize: any;
        bounds: number[];
        attribution: string;
    };
    spatial: {
        defaultSRID: any;
        thailandSRID: any;
    };
    api: {
        prefix: any;
    };
    cors: {
        origin: any;
        credentials: any;
    };
    rateLimit: {
        windowMs: any;
        max: any;
    };
    logging: {
        level: any;
        format: any;
    };
    external: {
        geoserver: {
            url: any;
            user: any;
            password: any;
            workspace: any;
        };
        mapbox: {
            accessToken: any;
        };
        gistda: {
            apiKey: any;
            baseUrl: any;
        };
        uploadToken: any;
    };
    jwt: {
        secret: any;
        expiresIn: any;
    };
};
//# sourceMappingURL=index.d.ts.map