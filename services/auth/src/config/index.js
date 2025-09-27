"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.config = void 0;
const dotenv_1 = __importDefault(require("dotenv"));
const joi_1 = __importDefault(require("joi"));
dotenv_1.default.config();
const envSchema = joi_1.default.object({
    NODE_ENV: joi_1.default.string().valid('development', 'test', 'production').default('development'),
    PORT: joi_1.default.number().default(3001),
    HOST: joi_1.default.string().default('0.0.0.0'),
    DATABASE_URL: joi_1.default.string().required(),
    DATABASE_SSL: joi_1.default.boolean().default(false),
    REDIS_URL: joi_1.default.string().required(),
    REDIS_PASSWORD: joi_1.default.string().allow('').optional(),
    JWT_SECRET: joi_1.default.string().required(),
    JWT_ACCESS_TOKEN_EXPIRES_IN: joi_1.default.string().default('15m'),
    JWT_REFRESH_TOKEN_EXPIRES_IN: joi_1.default.string().default('7d'),
    JWT_ISSUER: joi_1.default.string().default('munbon-auth'),
    JWT_AUDIENCE: joi_1.default.string().default('munbon-api'),
    SESSION_SECRET: joi_1.default.string().required(),
    SESSION_MAX_AGE: joi_1.default.number().default(86400000),
    OAUTH_CALLBACK_URL: joi_1.default.string().required(),
    THAI_DIGITAL_ID_CLIENT_ID: joi_1.default.string().required(),
    THAI_DIGITAL_ID_CLIENT_SECRET: joi_1.default.string().required(),
    THAI_DIGITAL_ID_AUTH_URL: joi_1.default.string().required(),
    THAI_DIGITAL_ID_TOKEN_URL: joi_1.default.string().required(),
    THAI_DIGITAL_ID_USERINFO_URL: joi_1.default.string().required(),
    TOTP_ISSUER: joi_1.default.string().default('Munbon Irrigation System'),
    TOTP_WINDOW: joi_1.default.number().default(1),
    SMTP_HOST: joi_1.default.string().required(),
    SMTP_PORT: joi_1.default.number().default(587),
    SMTP_SECURE: joi_1.default.boolean().default(false),
    SMTP_USER: joi_1.default.string().required(),
    SMTP_PASS: joi_1.default.string().required(),
    EMAIL_FROM: joi_1.default.string().required(),
    BCRYPT_ROUNDS: joi_1.default.number().default(12),
    PASSWORD_MIN_LENGTH: joi_1.default.number().default(8),
    PASSWORD_REQUIRE_UPPERCASE: joi_1.default.boolean().default(true),
    PASSWORD_REQUIRE_LOWERCASE: joi_1.default.boolean().default(true),
    PASSWORD_REQUIRE_NUMBER: joi_1.default.boolean().default(true),
    PASSWORD_REQUIRE_SPECIAL: joi_1.default.boolean().default(true),
    MAX_LOGIN_ATTEMPTS: joi_1.default.number().default(5),
    LOCKOUT_DURATION: joi_1.default.number().default(15),
    CORS_ORIGIN: joi_1.default.string().default('http://localhost:3000'),
    CORS_CREDENTIALS: joi_1.default.boolean().default(true),
    RATE_LIMIT_WINDOW_MS: joi_1.default.number().default(900000),
    RATE_LIMIT_MAX_REQUESTS: joi_1.default.number().default(100),
    LOG_LEVEL: joi_1.default.string().valid('error', 'warn', 'info', 'debug').default('info'),
    LOG_FORMAT: joi_1.default.string().valid('json', 'simple').default('json'),
}).unknown(true);
const { error, value: envVars } = envSchema.validate(process.env);
if (error) {
    throw new Error(`Config validation error: ${error.message}`);
}
exports.config = {
    env: envVars.NODE_ENV,
    port: envVars.PORT,
    host: envVars.HOST,
    database: {
        url: envVars.DATABASE_URL,
        ssl: envVars.DATABASE_SSL,
    },
    redis: {
        url: envVars.REDIS_URL,
        password: envVars.REDIS_PASSWORD,
    },
    jwt: {
        secret: envVars.JWT_SECRET,
        accessTokenExpiresIn: envVars.JWT_ACCESS_TOKEN_EXPIRES_IN,
        refreshTokenExpiresIn: envVars.JWT_REFRESH_TOKEN_EXPIRES_IN,
        issuer: envVars.JWT_ISSUER,
        audience: envVars.JWT_AUDIENCE,
    },
    session: {
        secret: envVars.SESSION_SECRET,
        maxAge: envVars.SESSION_MAX_AGE,
    },
    oauth: {
        callbackUrl: envVars.OAUTH_CALLBACK_URL,
    },
    thaiDigitalId: {
        clientId: envVars.THAI_DIGITAL_ID_CLIENT_ID,
        clientSecret: envVars.THAI_DIGITAL_ID_CLIENT_SECRET,
        authUrl: envVars.THAI_DIGITAL_ID_AUTH_URL,
        tokenUrl: envVars.THAI_DIGITAL_ID_TOKEN_URL,
        userinfoUrl: envVars.THAI_DIGITAL_ID_USERINFO_URL,
    },
    totp: {
        issuer: envVars.TOTP_ISSUER,
        window: envVars.TOTP_WINDOW,
    },
    email: {
        host: envVars.SMTP_HOST,
        port: envVars.SMTP_PORT,
        secure: envVars.SMTP_SECURE,
        user: envVars.SMTP_USER,
        pass: envVars.SMTP_PASS,
        from: envVars.EMAIL_FROM,
    },
    security: {
        bcryptRounds: envVars.BCRYPT_ROUNDS,
        password: {
            minLength: envVars.PASSWORD_MIN_LENGTH,
            requireUppercase: envVars.PASSWORD_REQUIRE_UPPERCASE,
            requireLowercase: envVars.PASSWORD_REQUIRE_LOWERCASE,
            requireNumber: envVars.PASSWORD_REQUIRE_NUMBER,
            requireSpecial: envVars.PASSWORD_REQUIRE_SPECIAL,
        },
        maxLoginAttempts: envVars.MAX_LOGIN_ATTEMPTS,
        lockoutDuration: envVars.LOCKOUT_DURATION,
    },
    cors: {
        origin: envVars.CORS_ORIGIN.split(','),
        credentials: envVars.CORS_CREDENTIALS,
    },
    rateLimit: {
        windowMs: envVars.RATE_LIMIT_WINDOW_MS,
        max: envVars.RATE_LIMIT_MAX_REQUESTS,
    },
    logging: {
        level: envVars.LOG_LEVEL,
        format: envVars.LOG_FORMAT,
    },
};
//# sourceMappingURL=index.js.map