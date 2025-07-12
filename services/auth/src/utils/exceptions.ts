export class AppError extends Error {
  constructor(
    public statusCode: number,
    public message: string,
    public code?: string,
    public details?: any
  ) {
    super(message);
    this.name = this.constructor.name;
    Error.captureStackTrace(this, this.constructor);
  }
}

export class BadRequestException extends AppError {
  constructor(message: string, code?: string, details?: any) {
    super(400, message, code, details);
  }
}

export class UnauthorizedException extends AppError {
  constructor(message: string = 'Unauthorized', code?: string, details?: any) {
    super(401, message, code, details);
  }
}

export class ForbiddenException extends AppError {
  constructor(message: string = 'Forbidden', code?: string, details?: any) {
    super(403, message, code, details);
  }
}

export class NotFoundException extends AppError {
  constructor(message: string = 'Not found', code?: string, details?: any) {
    super(404, message, code, details);
  }
}

export class ConflictException extends AppError {
  constructor(message: string, code?: string, details?: any) {
    super(409, message, code, details);
  }
}

export class ValidationException extends AppError {
  constructor(message: string, details?: any) {
    super(422, message, 'VALIDATION_ERROR', details);
  }
}

export class TooManyRequestsException extends AppError {
  constructor(message: string = 'Too many requests', retryAfter?: number) {
    super(429, message, 'RATE_LIMIT_EXCEEDED', { retryAfter });
  }
}

export class InternalServerException extends AppError {
  constructor(message: string = 'Internal server error', code?: string, details?: any) {
    super(500, message, code, details);
  }
}