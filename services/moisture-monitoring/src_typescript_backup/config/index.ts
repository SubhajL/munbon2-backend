import dotenv from 'dotenv';
import Joi from 'joi';

dotenv.config();

const envSchema = Joi.object({
  NODE_ENV: Joi.string().valid('development', 'production', 'test').default('development'),
  PORT: Joi.number().default(3005),
  HOST: Joi.string().default('0.0.0.0'),
  LOG_LEVEL: Joi.string().valid('trace', 'debug', 'info', 'warn', 'error', 'fatal').default('info'),
  
  // TimescaleDB
  TIMESCALE_HOST: Joi.string().required(),
  TIMESCALE_PORT: Joi.number().default(5433),
  TIMESCALE_DATABASE: Joi.string().required(),
  TIMESCALE_USER: Joi.string().required(),
  TIMESCALE_PASSWORD: Joi.string().required(),
  TIMESCALE_SSL: Joi.boolean().default(false),
  
  // Redis
  REDIS_HOST: Joi.string().default('localhost'),
  REDIS_PORT: Joi.number().default(6379),
  REDIS_PASSWORD: Joi.string().allow('').default(''),
  REDIS_DB: Joi.number().default(2),
  
  // MQTT
  MQTT_BROKER_URL: Joi.string().required(),
  MQTT_CLIENT_ID: Joi.string().default('moisture-monitoring-service'),
  MQTT_USERNAME: Joi.string().allow('').default(''),
  MQTT_PASSWORD: Joi.string().allow('').default(''),
  MQTT_RECONNECT_PERIOD: Joi.number().default(5000),
  
  // WebSocket
  WEBSOCKET_PATH: Joi.string().default('/moisture/socket.io'),
  WEBSOCKET_CORS_ORIGIN: Joi.string().default('*'),
  
  // Alerts
  ALERT_LOW_MOISTURE_THRESHOLD: Joi.number().default(20),
  ALERT_CRITICAL_LOW_MOISTURE_THRESHOLD: Joi.number().default(10),
  ALERT_HIGH_MOISTURE_THRESHOLD: Joi.number().default(90),
  ALERT_FLOOD_DETECTION_ENABLED: Joi.boolean().default(true),
  ALERT_COOLDOWN_MINUTES: Joi.number().default(30),
  
  // Analytics
  ANALYTICS_RETENTION_DAYS: Joi.number().default(90),
  ANALYTICS_AGGREGATION_INTERVALS: Joi.string().default('5m,15m,1h,1d'),
  ANALYTICS_CACHE_TTL_SECONDS: Joi.number().default(300),
  
  // Service Discovery
  NOTIFICATION_SERVICE_URL: Joi.string().optional(),
  ALERT_SERVICE_URL: Joi.string().optional(),
  
  // Rate Limiting
  RATE_LIMIT_WINDOW_MS: Joi.number().default(60000),
  RATE_LIMIT_MAX_REQUESTS: Joi.number().default(100),
  
  // Monitoring
  HEALTH_CHECK_INTERVAL_MS: Joi.number().default(30000),
  METRICS_ENABLED: Joi.boolean().default(true),
  METRICS_PORT: Joi.number().default(9092),
}).unknown();

const { error, value: envVars } = envSchema.validate(process.env);

if (error) {
  throw new Error(`Config validation error: ${error.message}`);
}

export const config = {
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
    lowMoistureThreshold: envVars.ALERT_LOW_MOISTURE_THRESHOLD,
    criticalLowMoistureThreshold: envVars.ALERT_CRITICAL_LOW_MOISTURE_THRESHOLD,
    highMoistureThreshold: envVars.ALERT_HIGH_MOISTURE_THRESHOLD,
    floodDetectionEnabled: envVars.ALERT_FLOOD_DETECTION_ENABLED,
    cooldownMinutes: envVars.ALERT_COOLDOWN_MINUTES,
  },
  
  analytics: {
    retentionDays: envVars.ANALYTICS_RETENTION_DAYS,
    aggregationIntervals: envVars.ANALYTICS_AGGREGATION_INTERVALS.split(','),
    cacheTTLSeconds: envVars.ANALYTICS_CACHE_TTL_SECONDS,
  },
  
  services: {
    notificationUrl: envVars.NOTIFICATION_SERVICE_URL,
    alertUrl: envVars.ALERT_SERVICE_URL,
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