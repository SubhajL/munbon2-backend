export declare class AppError extends Error {
    statusCode: number;
    message: string;
    code?: string | undefined;
    details?: any | undefined;
    constructor(statusCode: number, message: string, code?: string | undefined, details?: any | undefined);
}
export declare class BadRequestException extends AppError {
    constructor(message: string, code?: string, details?: any);
}
export declare class UnauthorizedException extends AppError {
    constructor(message?: string, code?: string, details?: any);
}
export declare class ForbiddenException extends AppError {
    constructor(message?: string, code?: string, details?: any);
}
export declare class NotFoundException extends AppError {
    constructor(message?: string, code?: string, details?: any);
}
export declare class ConflictException extends AppError {
    constructor(message: string, code?: string, details?: any);
}
export declare class ValidationException extends AppError {
    constructor(message: string, details?: any);
}
export declare class TooManyRequestsException extends AppError {
    constructor(message?: string, retryAfter?: number);
}
export declare class InternalServerException extends AppError {
    constructor(message?: string, code?: string, details?: any);
}
//# sourceMappingURL=exceptions.d.ts.map