"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.errorHandler = exports.AppError = void 0;
const logger_1 = require("../utils/logger");
class AppError extends Error {
    statusCode;
    isOperational;
    constructor(message, statusCode) {
        super(message);
        this.statusCode = statusCode;
        this.isOperational = true;
        Error.captureStackTrace(this, this.constructor);
    }
}
exports.AppError = AppError;
const errorHandler = (err, req, res, next) => {
    let statusCode = 500;
    let message = 'Internal Server Error';
    let isOperational = false;
    if (err instanceof AppError) {
        statusCode = err.statusCode;
        message = err.message;
        isOperational = err.isOperational;
    }
    logger_1.logger.error({
        error: err.message,
        stack: err.stack,
        path: req.path,
        method: req.method,
        ip: req.ip,
        isOperational,
    });
    res.status(statusCode).json({
        success: false,
        error: {
            message: process.env.NODE_ENV === 'production' && !isOperational
                ? 'Something went wrong'
                : message,
            ...(process.env.NODE_ENV !== 'production' && { stack: err.stack }),
        },
        timestamp: new Date().toISOString(),
    });
};
exports.errorHandler = errorHandler;
//# sourceMappingURL=errorHandler.js.map