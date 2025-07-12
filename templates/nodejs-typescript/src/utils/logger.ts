import winston from 'winston';

const logLevel = process.env.LOG_LEVEL || 'info';
const logFormat = process.env.LOG_FORMAT || 'json';

const formats = {
  json: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json(),
  ),
  simple: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.simple(),
  ),
};

export const logger = winston.createLogger({
  level: logLevel,
  format: formats[logFormat as keyof typeof formats] || formats.json,
  defaultMeta: { service: process.env.SERVICE_NAME || '{{SERVICE_NAME}}' },
  transports: [
    new winston.transports.Console({
      stderrLevels: ['error'],
    }),
  ],
});

// Create a stream object with a 'write' function for Morgan
export const stream = {
  write: (message: string): void => {
    logger.info(message.trim());
  },
};