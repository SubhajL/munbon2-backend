import { Request, Response, NextFunction } from 'express';
import { logger } from '../utils/logger';

export interface AppError extends Error {
  statusCode?: number;
  isOperational?: boolean;
}

export const errorHandler = (
  err: AppError,
  req: Request,
  res: Response,
  _next: NextFunction,
): void => {
  const statusCode = err.statusCode || 500;
  const message = err.message || 'Internal Server Error';
  const isOperational = err.isOperational || false;

  logger.error({
    error: {
      message: err.message,
      stack: err.stack,
      statusCode,
      isOperational,
    },
    request: {
      method: req.method,
      url: req.url,
      ip: req.ip,
      headers: req.headers,
    },
  });

  res.status(statusCode).json({
    error: {
      message: isOperational ? message : 'Internal Server Error',
      ...(process.env.NODE_ENV === 'development' && { stack: err.stack }),
    },
  });
};