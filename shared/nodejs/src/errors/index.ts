// Base error class for all custom errors
export class BaseError extends Error {
  public readonly statusCode: number;
  public readonly isOperational: boolean;
  public readonly timestamp: Date;

  constructor(
    message: string,
    statusCode: number = 500,
    isOperational: boolean = true
  ) {
    super(message);
    this.statusCode = statusCode;
    this.isOperational = isOperational;
    this.timestamp = new Date();

    Object.setPrototypeOf(this, BaseError.prototype);
    Error.captureStackTrace(this, this.constructor);
  }
}

// Specific error classes
export class ValidationError extends BaseError {
  constructor(message: string, public readonly errors?: Record<string, string>) {
    super(message, 400);
    Object.setPrototypeOf(this, ValidationError.prototype);
  }
}

export class NotFoundError extends BaseError {
  constructor(resource: string, identifier?: string) {
    const message = identifier 
      ? `${resource} with identifier ${identifier} not found`
      : `${resource} not found`;
    super(message, 404);
    Object.setPrototypeOf(this, NotFoundError.prototype);
  }
}

export class UnauthorizedError extends BaseError {
  constructor(message: string = 'Unauthorized') {
    super(message, 401);
    Object.setPrototypeOf(this, UnauthorizedError.prototype);
  }
}

export class ForbiddenError extends BaseError {
  constructor(message: string = 'Forbidden') {
    super(message, 403);
    Object.setPrototypeOf(this, ForbiddenError.prototype);
  }
}

export class ConflictError extends BaseError {
  constructor(message: string) {
    super(message, 409);
    Object.setPrototypeOf(this, ConflictError.prototype);
  }
}

export class RateLimitError extends BaseError {
  constructor(message: string = 'Too many requests') {
    super(message, 429);
    Object.setPrototypeOf(this, RateLimitError.prototype);
  }
}

export class ServiceUnavailableError extends BaseError {
  constructor(service: string) {
    super(`Service ${service} is temporarily unavailable`, 503);
    Object.setPrototypeOf(this, ServiceUnavailableError.prototype);
  }
}

// Error handler utility
export const isOperationalError = (error: Error): boolean => {
  if (error instanceof BaseError) {
    return error.isOperational;
  }
  return false;
};