import dotenv from 'dotenv';
import Joi from 'joi';

// Load environment variables
dotenv.config();

// Validation schema for environment variables
const envSchema = Joi.object({
  NODE_ENV: Joi.string().valid('development', 'test', 'production').default('development'),
  PORT: Joi.number().default(3003),
  HOST: Joi.string().default('0.0.0.0'),
  
  // Database
  DATABASE_URL: Joi.string().required(),
  DATABASE_SSL: Joi.boolean().default(false),
  GIS_SCHEMA: Joi.string().default('gis'),
  
  // Redis
  REDIS_URL: Joi.string().required(),
  REDIS_PASSWORD: Joi.string().allow('').optional(),
  CACHE_TTL: Joi.number().default(3600),
  
  // File Storage
  UPLOAD_DIR: Joi.string().default('/tmp/gis-uploads'),
  MAX_FILE_SIZE: Joi.number().default(104857600), // 100MB
  
  // Vector Tiles
  TILE_CACHE_ENABLED: Joi.boolean().default(true),
  TILE_CACHE_DIR: Joi.string().default('/tmp/gis-tiles'),
  MAX_ZOOM_LEVEL: Joi.number().default(18),
  MIN_ZOOM_LEVEL: Joi.number().default(1),
  TILE_SIZE: Joi.number().default(256),
  
  // Spatial Reference Systems
  DEFAULT_SRID: Joi.number().default(4326), // WGS84
  THAILAND_SRID: Joi.number().default(32647), // WGS84 / UTM zone 47N
  
  // API
  API_PREFIX: Joi.string().default('/api/v1'),
  CORS_ORIGIN: Joi.string().default('http://localhost:3000'),
  CORS_CREDENTIALS: Joi.boolean().default(true),
  
  // Rate Limiting
  RATE_LIMIT_WINDOW_MS: Joi.number().default(900000),
  RATE_LIMIT_MAX_REQUESTS: Joi.number().default(1000),
  
  // Logging
  LOG_LEVEL: Joi.string().valid('error', 'warn', 'info', 'debug').default('info'),
  LOG_FORMAT: Joi.string().valid('json', 'simple').default('json'),
  
  // External Services
  GEOSERVER_URL: Joi.string().optional(),
  GEOSERVER_USER: Joi.string().optional(),
  GEOSERVER_PASSWORD: Joi.string().optional(),
  GEOSERVER_WORKSPACE: Joi.string().default('munbon'),
  
  MAPBOX_ACCESS_TOKEN: Joi.string().optional(),
  
  GISTDA_API_KEY: Joi.string().optional(),
  GISTDA_BASE_URL: Joi.string().default('https://api.gistda.or.th'),
  
  // Performance
  DB_POOL_SIZE: Joi.number().default(20),
  DB_POOL_IDLE_TIMEOUT: Joi.number().default(30000),
  ENABLE_QUERY_LOGGING: Joi.boolean().default(false),
}).unknown(true);

// Validate environment variables
const { error, value: envVars } = envSchema.validate(process.env);
if (error) {
  throw new Error(`Config validation error: ${error.message}`);
}

// Export configuration
export const config = {
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
    bounds: [-180, -85.05112878, 180, 85.05112878], // Web Mercator bounds
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