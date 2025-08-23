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
    PORT: joi_1.default.number().default(3003),
    HOST: joi_1.default.string().default('0.0.0.0'),
    DATABASE_URL: joi_1.default.string().required(),
    DATABASE_SSL: joi_1.default.boolean().default(false),
    GIS_SCHEMA: joi_1.default.string().default('gis'),
    REDIS_URL: joi_1.default.string().required(),
    REDIS_PASSWORD: joi_1.default.string().allow('').optional(),
    CACHE_TTL: joi_1.default.number().default(3600),
    UPLOAD_DIR: joi_1.default.string().default('/tmp/gis-uploads'),
    MAX_FILE_SIZE: joi_1.default.number().default(104857600),
    TILE_CACHE_ENABLED: joi_1.default.boolean().default(true),
    TILE_CACHE_DIR: joi_1.default.string().default('/tmp/gis-tiles'),
    MAX_ZOOM_LEVEL: joi_1.default.number().default(18),
    MIN_ZOOM_LEVEL: joi_1.default.number().default(1),
    TILE_SIZE: joi_1.default.number().default(256),
    DEFAULT_SRID: joi_1.default.number().default(4326),
    THAILAND_SRID: joi_1.default.number().default(32647),
    API_PREFIX: joi_1.default.string().default('/api/v1'),
    CORS_ORIGIN: joi_1.default.string().default('http://localhost:3000'),
    CORS_CREDENTIALS: joi_1.default.boolean().default(true),
    RATE_LIMIT_WINDOW_MS: joi_1.default.number().default(900000),
    RATE_LIMIT_MAX_REQUESTS: joi_1.default.number().default(1000),
    LOG_LEVEL: joi_1.default.string().valid('error', 'warn', 'info', 'debug').default('info'),
    LOG_FORMAT: joi_1.default.string().valid('json', 'simple').default('json'),
    GEOSERVER_URL: joi_1.default.string().optional(),
    GEOSERVER_USER: joi_1.default.string().optional(),
    GEOSERVER_PASSWORD: joi_1.default.string().optional(),
    GEOSERVER_WORKSPACE: joi_1.default.string().default('munbon'),
    MAPBOX_ACCESS_TOKEN: joi_1.default.string().optional(),
    GISTDA_API_KEY: joi_1.default.string().optional(),
    GISTDA_BASE_URL: joi_1.default.string().default('https://api.gistda.or.th'),
    DB_POOL_SIZE: joi_1.default.number().default(20),
    DB_POOL_IDLE_TIMEOUT: joi_1.default.number().default(30000),
    ENABLE_QUERY_LOGGING: joi_1.default.boolean().default(false),
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
        gisSchema: envVars.GIS_SCHEMA,
        poolSize: envVars.DB_POOL_SIZE,
        poolIdleTimeout: envVars.DB_POOL_IDLE_TIMEOUT,
        enableQueryLogging: envVars.ENABLE_QUERY_LOGGING,
    },
    redis: {
        url: envVars.REDIS_URL,
        password: envVars.REDIS_PASSWORD,
        cacheTTL: envVars.CACHE_TTL,
    },
    storage: {
        uploadDir: envVars.UPLOAD_DIR,
        maxFileSize: envVars.MAX_FILE_SIZE,
    },
    tiles: {
        cacheEnabled: envVars.TILE_CACHE_ENABLED,
        cacheDir: envVars.TILE_CACHE_DIR,
        maxZoom: envVars.MAX_ZOOM_LEVEL,
        minZoom: envVars.MIN_ZOOM_LEVEL,
        tileSize: envVars.TILE_SIZE,
        bounds: [-180, -85.05112878, 180, 85.05112878],
        attribution: 'Munbon Irrigation Project © 2024',
    },
    spatial: {
        defaultSRID: envVars.DEFAULT_SRID,
        thailandSRID: envVars.THAILAND_SRID,
    },
    api: {
        prefix: envVars.API_PREFIX,
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
    external: {
        geoserver: {
            url: envVars.GEOSERVER_URL,
            user: envVars.GEOSERVER_USER,
            password: envVars.GEOSERVER_PASSWORD,
            workspace: envVars.GEOSERVER_WORKSPACE,
        },
        mapbox: {
            accessToken: envVars.MAPBOX_ACCESS_TOKEN,
        },
        gistda: {
            apiKey: envVars.GISTDA_API_KEY,
            baseUrl: envVars.GISTDA_BASE_URL,
        },
        uploadToken: envVars.EXTERNAL_UPLOAD_TOKEN,
    },
    jwt: {
        secret: envVars.JWT_SECRET || 'munbon-gis-jwt-secret',
        expiresIn: envVars.JWT_EXPIRES_IN || '24h',
    },
};
//# sourceMappingURL=index.js.map