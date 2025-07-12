import dotenv from 'dotenv';
import Joi from 'joi';

dotenv.config();

const envSchema = Joi.object({
  NODE_ENV: Joi.string().valid('development', 'production', 'test').default('development'),
  PORT: Joi.number().default(3006),
  HOST: Joi.string().default('0.0.0.0'),
  LOG_LEVEL: Joi.string().valid('trace', 'debug', 'info', 'warn', 'error', 'fatal').default('info'),
  
  // TimescaleDB
  TIMESCALE_HOST: Joi.string().required(),
  TIMESCALE_PORT: Joi.number().default(5433),
  TIMESCALE_DATABASE: Joi.string().required(),
  TIMESCALE_USER: Joi.string().required(),
  TIMESCALE_PASSWORD: Joi.string().required(),
  TIMESCALE_SSL: Joi.boolean().default(false),
  
  // PostgreSQL
  POSTGRES_HOST: Joi.string().required(),
  POSTGRES_PORT: Joi.number().default(5432),
  POSTGRES_DATABASE: Joi.string().required(),
  POSTGRES_USER: Joi.string().required(),
  POSTGRES_PASSWORD: Joi.string().required(),
  POSTGRES_SSL: Joi.boolean().default(false),
  
  // Redis
  REDIS_HOST: Joi.string().default('localhost'),
  REDIS_PORT: Joi.number().default(6379),
  REDIS_PASSWORD: Joi.string().allow('').default(''),
  REDIS_DB: Joi.number().default(4),
  
  // MQTT
  MQTT_BROKER_URL: Joi.string().required(),
  MQTT_CLIENT_ID: Joi.string().default('weather-monitoring-service'),
  MQTT_USERNAME: Joi.string().allow('').default(''),
  MQTT_PASSWORD: Joi.string().allow('').default(''),
  MQTT_RECONNECT_PERIOD: Joi.number().default(5000),
  
  // WebSocket
  WEBSOCKET_PATH: Joi.string().default('/weather/socket.io'),
  WEBSOCKET_CORS_ORIGIN: Joi.string().default('*'),
  
  // Alerts
  ALERT_HIGH_TEMP_THRESHOLD: Joi.number().default(40),
  ALERT_LOW_TEMP_THRESHOLD: Joi.number().default(10),
  ALERT_HIGH_WIND_SPEED_THRESHOLD: Joi.number().default(60),
  ALERT_HEAVY_RAIN_THRESHOLD: Joi.number().default(50),
  ALERT_FROST_WARNING_TEMP: Joi.number().default(5),
  ALERT_COOLDOWN_MINUTES: Joi.number().default(60),
  
  // Analytics
  ANALYTICS_RETENTION_DAYS: Joi.number().default(365),
  ANALYTICS_AGGREGATION_INTERVALS: Joi.string().default('15m,1h,6h,1d,7d'),
  ANALYTICS_CACHE_TTL_SECONDS: Joi.number().default(900),
  
  // Forecasting
  FORECAST_SHORT_TERM_DAYS: Joi.number().default(7),
  FORECAST_LONG_TERM_DAYS: Joi.number().default(30),
  FORECAST_UPDATE_INTERVAL_MINUTES: Joi.number().default(60),
  FORECAST_CONFIDENCE_THRESHOLD: Joi.number().default(0.7),
  
  // Irrigation
  IRRIGATION_ET_CALCULATION_METHOD: Joi.string().default('penman-monteith'),
  IRRIGATION_SOIL_MOISTURE_WEIGHT: Joi.number().default(0.4),
  IRRIGATION_FORECAST_WEIGHT: Joi.number().default(0.6),
  IRRIGATION_RECOMMENDATION_HORIZON_DAYS: Joi.number().default(3),
  
  // Service Discovery
  NOTIFICATION_SERVICE_URL: Joi.string().optional(),
  ALERT_SERVICE_URL: Joi.string().optional(),
  AI_MODEL_SERVICE_URL: Joi.string().optional(),
  CROP_MANAGEMENT_SERVICE_URL: Joi.string().optional(),
  
  // Rate Limiting
  RATE_LIMIT_WINDOW_MS: Joi.number().default(60000),
  RATE_LIMIT_MAX_REQUESTS: Joi.number().default(100),
  
  // Monitoring
  HEALTH_CHECK_INTERVAL_MS: Joi.number().default(30000),
  METRICS_ENABLED: Joi.boolean().default(true),
  METRICS_PORT: Joi.number().default(9095),
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
  
  postgres: {
    host: envVars.POSTGRES_HOST,
    port: envVars.POSTGRES_PORT,
    database: envVars.POSTGRES_DATABASE,
    user: envVars.POSTGRES_USER,
    password: envVars.POSTGRES_PASSWORD,
    ssl: envVars.POSTGRES_SSL,
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
    highTempThreshold: envVars.ALERT_HIGH_TEMP_THRESHOLD,
    lowTempThreshold: envVars.ALERT_LOW_TEMP_THRESHOLD,
    highWindSpeedThreshold: envVars.ALERT_HIGH_WIND_SPEED_THRESHOLD,
    heavyRainThreshold: envVars.ALERT_HEAVY_RAIN_THRESHOLD,
    frostWarningTemp: envVars.ALERT_FROST_WARNING_TEMP,
    cooldownMinutes: envVars.ALERT_COOLDOWN_MINUTES,
  },
  
  analytics: {
    retentionDays: envVars.ANALYTICS_RETENTION_DAYS,
    aggregationIntervals: envVars.ANALYTICS_AGGREGATION_INTERVALS.split(','),
    cacheTTLSeconds: envVars.ANALYTICS_CACHE_TTL_SECONDS,
  },
  
  forecasting: {
    shortTermDays: envVars.FORECAST_SHORT_TERM_DAYS,
    longTermDays: envVars.FORECAST_LONG_TERM_DAYS,
    updateIntervalMinutes: envVars.FORECAST_UPDATE_INTERVAL_MINUTES,
    confidenceThreshold: envVars.FORECAST_CONFIDENCE_THRESHOLD,
  },
  
  irrigation: {
    etCalculationMethod: envVars.IRRIGATION_ET_CALCULATION_METHOD,
    soilMoistureWeight: envVars.IRRIGATION_SOIL_MOISTURE_WEIGHT,
    forecastWeight: envVars.IRRIGATION_FORECAST_WEIGHT,
    recommendationHorizonDays: envVars.IRRIGATION_RECOMMENDATION_HORIZON_DAYS,
  },
  
  services: {
    notificationUrl: envVars.NOTIFICATION_SERVICE_URL,
    alertUrl: envVars.ALERT_SERVICE_URL,
    aiModelUrl: envVars.AI_MODEL_SERVICE_URL,
    cropManagementUrl: envVars.CROP_MANAGEMENT_SERVICE_URL,
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