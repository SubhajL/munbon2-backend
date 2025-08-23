"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.errorHandler = exports.AppError = void 0;
const logger_1 = require("../utils/logger");
class AppError extends Error {
    statusCode;
    message;
    isOperational;
    details;
    constructor(statusCode, message, isOperational = true, details) {
        super(message);
        this.statusCode = statusCode;
        this.message = message;
        this.isOperational = isOperational;
        this.details = details;
        Object.setPrototypeOf(this, AppError.prototype);
    }
}
exports.AppError = AppError;
const errorHandler = (err, req, res, _next) => {
    if (err instanceof AppError) {
        logger_1.logger.error({
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
    }
    else {
        logger_1.logger.error({
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
exports.errorHandler = errorHandler;
//# sourceMappingURL=errorHandler.js.map