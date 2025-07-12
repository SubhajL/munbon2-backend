import { Request, Response, NextFunction } from 'express';
import { createLogger } from '../logger';

const logger = createLogger('request-logger');

export interface RequestLoggerOptions {
  skipPaths?: string[];
  logBody?: boolean;
  logHeaders?: boolean;
}

export const requestLogger = (options: RequestLoggerOptions = {}) => {
  const { 
    skipPaths = ['/health', '/ready', '/metrics'],
    logBody = false,
    logHeaders = false
  } = options;

  return (req: Request, res: Response, next: NextFunction): void => {
    // Skip logging for certain paths
    if (skipPaths.includes(req.path)) {
      return next();
    }

    const startTime = Date.now();
    const requestId = req.headers['x-request-id'] as string;

    // Log request
    const requestLog: Record<string, any> = {
      method: req.method,
      url: req.url,
      ip: req.ip,
      userAgent: req.headers['user-agent'],
      requestId
    };

    if (logBody && req.body && Object.keys(req.body).length > 0) {
      requestLog.body = req.body;
    }

    if (logHeaders) {
      requestLog.headers = req.headers;
    }

    logger.info('Incoming request', requestLog);

    // Capture response
    const originalSend = res.send;
    res.send = function(data: any): Response {
      res.send = originalSend;
      
      const duration = Date.now() - startTime;
      
      logger.info('Request completed', {
        method: req.method,
        url: req.url,
        statusCode: res.statusCode,
        duration: `${duration}ms`,
        requestId
      });
      
      return res.send(data);
    };

    next();
  };
};