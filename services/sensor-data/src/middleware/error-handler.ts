import { Request, Response, NextFunction } from 'express';
import { Logger } from 'pino';

export interface AppError extends Error {
  statusCode?: number;
  isOperational?: boolean;
}

export function errorHandler(
  err: AppError,
  req: Request,
  res: Response,
  _next: NextFunction
): void {
  const statusCode = err.statusCode || 500;
  const message = err.message || 'Internal Server Error';
  
  // Log error
  const logger: Logger = (req as any).logger || console;
  logger.error({
    error: {
      message: err.message,
      stack: err.stack,
      statusCode
    },
    request: {
      method: req.method,
      url: req.url,
      params: req.params,
      query: req.query,
      body: req.body
    }
  }, 'Request error');

  // Send error response
  res.status(statusCode).json({
    error: {
      message,
      statusCode,
      timestamp: new Date().toISOString()
    }
  });
}