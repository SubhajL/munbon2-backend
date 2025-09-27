"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.errorHandler = void 0;
const joi_1 = require("joi");
const typeorm_1 = require("typeorm");
const jsonwebtoken_1 = require("jsonwebtoken");
const exceptions_1 = require("../utils/exceptions");
const logger_1 = require("../utils/logger");
const errorHandler = (err, req, res, next) => {
    let statusCode = 500;
    let message = 'Internal server error';
    let code = 'INTERNAL_ERROR';
    let details = undefined;
    logger_1.logger.error({
        error: err.message,
        stack: err.stack,
        method: req.method,
        url: req.url,
        ip: req.ip,
        userId: req.user?.id,
    });
    if (err instanceof exceptions_1.AppError) {
        statusCode = err.statusCode;
        message = err.message;
        code = err.code || code;
        details = err.details;
    }
    else if (err instanceof joi_1.ValidationError) {
        statusCode = 422;
        message = 'Validation error';
        code = 'VALIDATION_ERROR';
        details = err.details.map(detail => ({
            field: detail.path.join('.'),
            message: detail.message,
        }));
    }
    else if (err instanceof typeorm_1.QueryFailedError) {
        statusCode = 400;
        message = 'Database operation failed';
        code = 'DATABASE_ERROR';
        const dbError = err;
        if (dbError.code === '23505') {
            message = 'Duplicate entry';
            code = 'DUPLICATE_ENTRY';
        }
    }
    else if (err instanceof jsonwebtoken_1.TokenExpiredError) {
        statusCode = 401;
        message = 'Token expired';
        code = 'TOKEN_EXPIRED';
    }
    else if (err instanceof jsonwebtoken_1.JsonWebTokenError) {
        statusCode = 401;
        message = 'Invalid token';
        code = 'INVALID_TOKEN';
    }
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
exports.errorHandler = errorHandler;
//# sourceMappingURL=error-handler.js.map