import pino from 'pino';

export const logger = pino({
  name: 'scada-gate-control',
  level: process.env.LOG_LEVEL || 'info',
});
