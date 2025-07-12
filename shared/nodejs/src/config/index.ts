import dotenv from 'dotenv';
import joi from 'joi';

// Load environment variables
dotenv.config();

// Base configuration schema
const baseConfigSchema = joi.object({
  NODE_ENV: joi.string().valid('development', 'test', 'production').default('development'),
  PORT: joi.number().default(3000),
  LOG_LEVEL: joi.string().valid('error', 'warn', 'info', 'debug').default('info'),
  SERVICE_NAME: joi.string().required(),
  
  // Database
  DATABASE_URL: joi.string().uri().optional(),
  
  // Redis
  REDIS_URL: joi.string().uri().optional(),
  
  // Message Queue
  RABBITMQ_URL: joi.string().uri().optional(),
  KAFKA_BROKERS: joi.string().optional(),
  
  // Authentication
  JWT_SECRET: joi.string().when('NODE_ENV', {
    is: 'production',
    then: joi.required(),
    otherwise: joi.optional().default('dev-secret')
  }),
  JWT_EXPIRY: joi.string().default('24h'),
  
  // Monitoring
  PROMETHEUS_PORT: joi.number().default(9090),
  JAEGER_ENDPOINT: joi.string().uri().optional(),
  
  // Feature flags
  ENABLE_METRICS: joi.boolean().default(true),
  ENABLE_TRACING: joi.boolean().default(false),
  ENABLE_RATE_LIMITING: joi.boolean().default(true),
  
  // Rate limiting
  RATE_LIMIT_WINDOW_MS: joi.number().default(15 * 60 * 1000), // 15 minutes
  RATE_LIMIT_MAX_REQUESTS: joi.number().default(100)
}).unknown();

// Configuration factory
export const createConfig = <T extends Record<string, unknown>>(
  schema?: joi.Schema<T>
): T & ReturnType<typeof getBaseConfig> => {
  const finalSchema = schema 
    ? baseConfigSchema.concat(schema) 
    : baseConfigSchema;
    
  const { error, value } = finalSchema.validate(process.env, {
    abortEarly: false,
    stripUnknown: true
  });

  if (error) {
    throw new Error(`Configuration validation error: ${error.message}`);
  }

  return value as T & ReturnType<typeof getBaseConfig>;
};

// Get base configuration
export const getBaseConfig = () => {
  const { error, value } = baseConfigSchema.validate(process.env, {
    abortEarly: false,
    stripUnknown: true
  });

  if (error) {
    throw new Error(`Configuration validation error: ${error.message}`);
  }

  return value;
};

// Export config type
export type BaseConfig = ReturnType<typeof getBaseConfig>;