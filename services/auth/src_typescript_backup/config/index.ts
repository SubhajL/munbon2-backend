import dotenv from 'dotenv';
import Joi from 'joi';

// Load environment variables
dotenv.config();

// Validation schema for environment variables
const envSchema = Joi.object({
  NODE_ENV: Joi.string().valid('development', 'test', 'production').default('development'),
  PORT: Joi.number().default(3001),
  HOST: Joi.string().default('0.0.0.0'),
  
  // Database
  DATABASE_URL: Joi.string().required(),
  DATABASE_SSL: Joi.boolean().default(false),
  
  // Redis
  REDIS_URL: Joi.string().required(),
  REDIS_PASSWORD: Joi.string().allow('').optional(),
  
  // JWT
  JWT_SECRET: Joi.string().required(),
  JWT_ACCESS_TOKEN_EXPIRES_IN: Joi.string().default('15m'),
  JWT_REFRESH_TOKEN_EXPIRES_IN: Joi.string().default('7d'),
  JWT_ISSUER: Joi.string().default('munbon-auth'),
  JWT_AUDIENCE: Joi.string().default('munbon-api'),
  
  // Session
  SESSION_SECRET: Joi.string().required(),
  SESSION_MAX_AGE: Joi.number().default(86400000), // 24 hours
  
  // OAuth
  OAUTH_CALLBACK_URL: Joi.string().required(),
  
  // Thai Digital ID
  THAI_DIGITAL_ID_CLIENT_ID: Joi.string().required(),
  THAI_DIGITAL_ID_CLIENT_SECRET: Joi.string().required(),
  THAI_DIGITAL_ID_AUTH_URL: Joi.string().required(),
  THAI_DIGITAL_ID_TOKEN_URL: Joi.string().required(),
  THAI_DIGITAL_ID_USERINFO_URL: Joi.string().required(),
  
  // TOTP
  TOTP_ISSUER: Joi.string().default('Munbon Irrigation System'),
  TOTP_WINDOW: Joi.number().default(1),
  
  // Email
  SMTP_HOST: Joi.string().required(),
  SMTP_PORT: Joi.number().default(587),
  SMTP_SECURE: Joi.boolean().default(false),
  SMTP_USER: Joi.string().required(),
  SMTP_PASS: Joi.string().required(),
  EMAIL_FROM: Joi.string().required(),
  
  // Security
  BCRYPT_ROUNDS: Joi.number().default(12),
  PASSWORD_MIN_LENGTH: Joi.number().default(8),
  PASSWORD_REQUIRE_UPPERCASE: Joi.boolean().default(true),
  PASSWORD_REQUIRE_LOWERCASE: Joi.boolean().default(true),
  PASSWORD_REQUIRE_NUMBER: Joi.boolean().default(true),
  PASSWORD_REQUIRE_SPECIAL: Joi.boolean().default(true),
  MAX_LOGIN_ATTEMPTS: Joi.number().default(5),
  LOCKOUT_DURATION: Joi.number().default(15), // minutes
  
  // CORS
  CORS_ORIGIN: Joi.string().default('http://localhost:3000'),
  CORS_CREDENTIALS: Joi.boolean().default(true),
  
  // Rate Limiting
  RATE_LIMIT_WINDOW_MS: Joi.number().default(900000), // 15 minutes
  RATE_LIMIT_MAX_REQUESTS: Joi.number().default(100),
  
  // Logging
  LOG_LEVEL: Joi.string().valid('error', 'warn', 'info', 'debug').default('info'),
  LOG_FORMAT: Joi.string().valid('json', 'simple').default('json'),
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