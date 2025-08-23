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
    NODE_ENV: joi_1.default.string().valid('development', 'production', 'test').default('development'),
    PORT: joi_1.default.number().default(3008),
    HOST: joi_1.default.string().default('0.0.0.0'),
    LOG_LEVEL: joi_1.default.string().valid('trace', 'debug', 'info', 'warn', 'error', 'fatal').default('info'),
    // TimescaleDB
    TIMESCALE_HOST: joi_1.default.string().required(),
    TIMESCALE_PORT: joi_1.default.number().default(5433),
    TIMESCALE_DATABASE: joi_1.default.string().required(),
    TIMESCALE_USER: joi_1.default.string().required(),
    TIMESCALE_PASSWORD: joi_1.default.string().required(),
    TIMESCALE_SSL: joi_1.default.boolean().default(false),
    // Redis
    REDIS_HOST: joi_1.default.string().default('localhost'),
    REDIS_PORT: joi_1.default.number().default(6379),
    REDIS_PASSWORD: joi_1.default.string().allow('').default(''),
    REDIS_DB: joi_1.default.number().default(3),
    // MQTT
    MQTT_BROKER_URL: joi_1.default.string().required(),
    MQTT_CLIENT_ID: joi_1.default.string().default('water-level-monitoring-service'),
    MQTT_USERNAME: joi_1.default.string().allow('').default(''),
    MQTT_PASSWORD: joi_1.default.string().allow('').default(''),
    MQTT_RECONNECT_PERIOD: joi_1.default.number().default(5000),
    // WebSocket
    WEBSOCKET_PATH: joi_1.default.string().default('/water-level/socket.io'),
    WEBSOCKET_CORS_ORIGIN: joi_1.default.string().default('*'),
    // Alerts
    ALERT_LOW_WATER_THRESHOLD: joi_1.default.number().default(5),
    ALERT_CRITICAL_LOW_WATER_THRESHOLD: joi_1.default.number().default(2),
    ALERT_HIGH_WATER_THRESHOLD: joi_1.default.number().default(25),
    ALERT_CRITICAL_HIGH_WATER_THRESHOLD: joi_1.default.number().default(28),
    ALERT_RAPID_CHANGE_THRESHOLD: joi_1.default.number().default(5),
    ALERT_COOLDOWN_MINUTES: joi_1.default.number().default(30),
    // Analytics
    ANALYTICS_RETENTION_DAYS: joi_1.default.number().default(90),
    ANALYTICS_AGGREGATION_INTERVALS: joi_1.default.string().default('5m,15m,1h,1d'),
    ANALYTICS_CACHE_TTL_SECONDS: joi_1.default.number().default(300),
    // Gate Control
    GATE_CONTROL_ENABLED: joi_1.default.boolean().default(false),
    GATE_CONTROL_SERVICE_URL: joi_1.default.string().optional(),
    GATE_CONTROL_MIN_LEVEL: joi_1.default.number().default(10),
    GATE_CONTROL_MAX_LEVEL: joi_1.default.number().default(20),
    // Service Discovery
    NOTIFICATION_SERVICE_URL: joi_1.default.string().optional(),
    ALERT_SERVICE_URL: joi_1.default.string().optional(),
    SCADA_SERVICE_URL: joi_1.default.string().optional(),
    // Rate Limiting
    RATE_LIMIT_WINDOW_MS: joi_1.default.number().default(60000),
    RATE_LIMIT_MAX_REQUESTS: joi_1.default.number().default(100),
    // Monitoring
    HEALTH_CHECK_INTERVAL_MS: joi_1.default.number().default(30000),
    METRICS_ENABLED: joi_1.default.boolean().default(true),
    METRICS_PORT: joi_1.default.number().default(9094),
}).unknown();
const { error, value: envVars } = envSchema.validate(process.env);
if (error) {
    throw new Error(`Config validation error: ${error.message}`);
}
exports.config = {
    env: envVars.NODE_ENV,
    port: envVars.PORT,
    host: envVars.HOST,
    logLevel: envVars.LOG_LEVEL,
    timescale: {
        host: envVars.TIMESCALE_HOST,
        port: envVars.TIMESCALE_PORT,
        database: envVars.TIMESCALE_DATABASE,
        user: envVars.TIMESCALE_USER,
        password: envVars.TIMESCALE_PASSWORD,
        ssl: envVars.TIMESCALE_SSL,
    },
    redis: {
        host: envVars.REDIS_HOST,
        port: envVars.REDIS_PORT,
        password: envVars.REDIS_PASSWORD,
        db: envVars.REDIS_DB,
    },
    mqtt: {
        brokerUrl: envVars.MQTT_BROKER_URL,
        clientId: envVars.MQTT_CLIENT_ID,
        username: envVars.MQTT_USERNAME,
        password: envVars.MQTT_PASSWORD,
        reconnectPeriod: envVars.MQTT_RECONNECT_PERIOD,
    },
    websocket: {
        path: envVars.WEBSOCKET_PATH,
        corsOrigin: envVars.WEBSOCKET_CORS_ORIGIN,
    },
    alerts: {
        lowWaterThreshold: envVars.ALERT_LOW_WATER_THRESHOLD,
        criticalLowWaterThreshold: envVars.ALERT_CRITICAL_LOW_WATER_THRESHOLD,
        highWaterThreshold: envVars.ALERT_HIGH_WATER_THRESHOLD,
        criticalHighWaterThreshold: envVars.ALERT_CRITICAL_HIGH_WATER_THRESHOLD,
        rapidChangeThreshold: envVars.ALERT_RAPID_CHANGE_THRESHOLD,
        cooldownMinutes: envVars.ALERT_COOLDOWN_MINUTES,
    },
    analytics: {
        retentionDays: envVars.ANALYTICS_RETENTION_DAYS,
        aggregationIntervals: envVars.ANALYTICS_AGGREGATION_INTERVALS.split(','),
        cacheTTLSeconds: envVars.ANALYTICS_CACHE_TTL_SECONDS,
    },
    gateControl: {
        enabled: envVars.GATE_CONTROL_ENABLED,
        serviceUrl: envVars.GATE_CONTROL_SERVICE_URL,
        minLevel: envVars.GATE_CONTROL_MIN_LEVEL,
        maxLevel: envVars.GATE_CONTROL_MAX_LEVEL,
    },
    services: {
        notificationUrl: envVars.NOTIFICATION_SERVICE_URL,
        alertUrl: envVars.ALERT_SERVICE_URL,
        scadaUrl: envVars.SCADA_SERVICE_URL,
    },
    rateLimit: {
        windowMs: envVars.RATE_LIMIT_WINDOW_MS,
        maxRequests: envVars.RATE_LIMIT_MAX_REQUESTS,
    },
    monitoring: {
        healthCheckIntervalMs: envVars.HEALTH_CHECK_INTERVAL_MS,
        metricsEnabled: envVars.METRICS_ENABLED,
        metricsPort: envVars.METRICS_PORT,
    },
};
//# sourceMappingURL=index.js.map