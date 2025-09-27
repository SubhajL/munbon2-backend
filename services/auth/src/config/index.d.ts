export declare const config: {
    env: any;
    port: any;
    host: any;
    database: {
        url: any;
        ssl: any;
    };
    redis: {
        url: any;
        password: any;
    };
    jwt: {
        secret: any;
        accessTokenExpiresIn: any;
        refreshTokenExpiresIn: any;
        issuer: any;
        audience: any;
    };
    session: {
        secret: any;
        maxAge: any;
    };
    oauth: {
        callbackUrl: any;
    };
    thaiDigitalId: {
        clientId: any;
        clientSecret: any;
        authUrl: any;
        tokenUrl: any;
        userinfoUrl: any;
    };
    totp: {
        issuer: any;
        window: any;
    };
    email: {
        host: any;
        port: any;
        secure: any;
        user: any;
        pass: any;
        from: any;
    };
    security: {
        bcryptRounds: any;
        password: {
            minLength: any;
            requireUppercase: any;
            requireLowercase: any;
            requireNumber: any;
            requireSpecial: any;
        };
        maxLoginAttempts: any;
        lockoutDuration: any;
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
};
//# sourceMappingURL=index.d.ts.map