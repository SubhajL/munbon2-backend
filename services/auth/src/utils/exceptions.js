"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.InternalServerException = exports.TooManyRequestsException = exports.ValidationException = exports.ConflictException = exports.NotFoundException = exports.ForbiddenException = exports.UnauthorizedException = exports.BadRequestException = exports.AppError = void 0;
class AppError extends Error {
    statusCode;
    message;
    code;
    details;
    constructor(statusCode, message, code, details) {
        super(message);
        this.statusCode = statusCode;
        this.message = message;
        this.code = code;
        this.details = details;
        this.name = this.constructor.name;
        Error.captureStackTrace(this, this.constructor);
    }
}
exports.AppError = AppError;
class BadRequestException extends AppError {
    constructor(message, code, details) {
        super(400, message, code, details);
    }
}
exports.BadRequestException = BadRequestException;
class UnauthorizedException extends AppError {
    constructor(message = 'Unauthorized', code, details) {
        super(401, message, code, details);
    }
}
exports.UnauthorizedException = UnauthorizedException;
class ForbiddenException extends AppError {
    constructor(message = 'Forbidden', code, details) {
        super(403, message, code, details);
    }
}
exports.ForbiddenException = ForbiddenException;
class NotFoundException extends AppError {
    constructor(message = 'Not found', code, details) {
        super(404, message, code, details);
    }
}
exports.NotFoundException = NotFoundException;
class ConflictException extends AppError {
    constructor(message, code, details) {
        super(409, message, code, details);
    }
}
exports.ConflictException = ConflictException;
class ValidationException extends AppError {
    constructor(message, details) {
        super(422, message, 'VALIDATION_ERROR', details);
    }
}
exports.ValidationException = ValidationException;
class TooManyRequestsException extends AppError {
    constructor(message = 'Too many requests', retryAfter) {
        super(429, message, 'RATE_LIMIT_EXCEEDED', { retryAfter });
    }
}
exports.TooManyRequestsException = TooManyRequestsException;
class InternalServerException extends AppError {
    constructor(message = 'Internal server error', code, details) {
        super(500, message, code, details);
    }
}
exports.InternalServerException = InternalServerException;
//# sourceMappingURL=exceptions.js.map