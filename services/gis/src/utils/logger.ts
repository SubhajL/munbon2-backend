import winston from 'winston';
import { config } from '../config';

const logFormat = winston.format.combine(
  winston.format.timestamp(),
  winston.format.errors({ stack: true }),
  winston.format.json()
);

const simpleFormat = winston.format.combine(
  winston.format.timestamp(),
  winston.format.colorize(),
  winston.format.simple()
);

export const logger = winston.createLogger({
  level: config.logging.level,
  format: config.logging.format === 'json' ? logFormat : simpleFormat,
  defaultMeta: { service: 'gis-service' },
  transports: [
    new winston.transports.Console({
      handleExceptions: true,
    }),
  ],
  exitOnError: false,
});