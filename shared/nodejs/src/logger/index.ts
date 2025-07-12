import winston from 'winston';

const { combine, timestamp, errors, json, printf } = winston.format;

// Custom format for console output
const consoleFormat = printf(({ level, message, timestamp, service, ...metadata }) => {
  let msg = `${timestamp} [${service}] ${level}: ${message}`;
  if (Object.keys(metadata).length > 0) {
    msg += ` ${JSON.stringify(metadata)}`;
  }
  return msg;
});

// Create logger factory
export const createLogger = (serviceName: string): winston.Logger => {
  const logger = winston.createLogger({
    level: process.env.LOG_LEVEL || 'info',
    format: combine(
      timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
      errors({ stack: true }),
      json()
    ),
    defaultMeta: { service: serviceName },
    transports: []
  });

  // Console transport for development
  if (process.env.NODE_ENV !== 'production') {
    logger.add(new winston.transports.Console({
      format: combine(
        winston.format.colorize(),
        timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
        consoleFormat
      )
    }));
  } else {
    // JSON format for production (structured logging)
    logger.add(new winston.transports.Console({
      format: combine(
        timestamp(),
        json()
      )
    }));
  }

  return logger;
};

// Default logger instance
export const logger = createLogger('munbon-shared');