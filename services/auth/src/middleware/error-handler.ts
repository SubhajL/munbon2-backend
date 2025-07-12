import { Request, Response, NextFunction } from 'express';
import { ValidationError } from 'joi';
import { QueryFailedError } from 'typeorm';
import { JsonWebTokenError, TokenExpiredError } from 'jsonwebtoken';
import { AppError } from '../utils/exceptions';
import { logger } from '../utils/logger';

export const errorHandler = (
  err: Error,
  req: Request,
  res: Response,
  next: NextFunction
) => {
  let statusCode = 500;
  let message = 'Internal server error';
  let code = 'INTERNAL_ERROR';
  let details = undefined;

  // Log error
  logger.error({
    error: err.message,
    stack: err.stack,
    method: req.method,
    url: req.url,
    ip: req.ip,
    userId: req.user?.id,
  });

  // Handle known error types
  if (err instanceof AppError) {
    statusCode = err.statusCode;
    message = err.message;
    code = err.code || code;
    details = err.details;
  } else if (err instanceof ValidationError) {
    statusCode = 422;
    message = 'Validation error';
    code = 'VALIDATION_ERROR';
    details = err.details.map(detail => ({
      field: detail.path.join('.'),
      message: detail.message,
    }));
  } else if (err instanceof QueryFailedError) {
    statusCode = 400;
    message = 'Database operation failed';
    code = 'DATABASE_ERROR';
    
    // Handle specific database errors
    const dbError = err as any;
    if (dbError.code === '23505') {
      message = 'Duplicate entry';
      code = 'DUPLICATE_ENTRY';
    }
  } else if (err instanceof TokenExpiredError) {
    statusCode = 401;
    message = 'Token expired';
    code = 'TOKEN_EXPIRED';
  } else if (err instanceof JsonWebTokenError) {
    statusCode = 401;
    message = 'Invalid token';
    code = 'INVALID_TOKEN';
  }

  // Send error response
  res.status(statusCode).json({
    success: false,
    error: {
      code,
      message,
      details,
      ...(process.env.NODE_ENV === 'development' && {
        stack: err.stack,
      }),
    },
    timestamp: new Date().toISOString(),
    path: req.path,
  });
};