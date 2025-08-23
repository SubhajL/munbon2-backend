export class ApiError extends Error {
  public statusCode: number;
  public code?: string;
  public details?: any;

  constructor(statusCode: number, message: string, details?: any, code?: string) {
    super(message);
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
    this.name = 'ApiError';
    Error.captureStackTrace(this, this.constructor);
  }
}