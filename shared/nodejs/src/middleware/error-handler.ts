import { Request, Response, NextFunction } from 'express';
import { BaseError, isOperationalError } from '../errors';
import { createLogger } from '../logger';

const logger = createLogger('error-handler');

export interface ErrorResponse {
  error: {
    message: string;
    statusCode: number;
    timestamp: Date;
    path: string;
    method: string;
    requestId?: string;
    errors?: Record<string, string>;
  };
}

export const errorHandler = (
  err: Error,
  req: Request,
  res: Response,
  _next: NextFunction
): void => {
  // Log the error
  logger.error('Error caught in error handler', {
    error: err.message,
    stack: err.stack,
    url: req.url,
    method: req.method,
    ip: req.ip,
    requestId: req.headers['x-request-id']
  });

  // Default error response
  let statusCode = 500;
  let message = 'Internal Server Error';
  let errors: Record<string, string> | undefined;

  // Handle known errors
  if (err instanceof BaseError) {
    statusCode = err.statusCode;
    message = err.message;
    if ('errors' in err) {
      errors = (err as any).errors;
    }
  }

  // Send error response
  const errorResponse: ErrorResponse = {
    error: {
      message,
      statusCode,
      timestamp: new Date(),
      path: req.path,
      method: req.method,
      requestId: req.headers['x-request-id'] as string,
      errors
    }
  };

  res.status(statusCode).json(errorResponse);

  // For non-operational errors, we might want to crash the process
  if (!isOperationalError(err)) {
    logger.error('Non-operational error detected, exiting process', {
      error: err.message,
      stack: err.stack
    });
    process.exit(1);
  }
};