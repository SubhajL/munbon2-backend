import { Request, Response, NextFunction } from 'express';
import { logger } from '../utils/logger';

export class AppError extends Error {
  constructor(
    public statusCode: number,
    public message: string,
    public isOperational = true,
    public details?: any
  ) {
    super(message);
    Object.setPrototypeOf(this, AppError.prototype);
  }
}

export const errorHandler = (
  err: Error | AppError,
  req: Request,
  res: Response,
  _next: NextFunction
): void => {
  if (err instanceof AppError) {
    logger.error({
      error: err,
      statusCode: err.statusCode,
      message: err.message,
      details: err.details,
      url: req.url,
      method: req.method,
    }, 'Application error');

    res.status(err.statusCode).json({
      success: false,
      error: {
        message: err.message,
        ...(process.env.NODE_ENV !== 'production' && { details: err.details }),
      },
    });
  } else {
    logger.error({
      error: err,
      url: req.url,
      method: req.method,
      stack: err.stack,
    }, 'Unexpected error');

    res.status(500).json({
      success: false,
      error: {
        message: 'Internal server error',
        ...(process.env.NODE_ENV !== 'production' && { 
          details: err.message,
          stack: err.stack 
        }),
      },
    });
  }
};