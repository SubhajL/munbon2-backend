"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.errorHandler = void 0;
const api_error_1 = require("../utils/api-error");
const logger_1 = require("../utils/logger");
const errorHandler = (err, req, res, next) => {
    if (err instanceof api_error_1.ApiError) {
        res.status(err.statusCode).json({
            success: false,
            error: {
                message: err.message,
                code: err.code,
                details: err.details,
            },
        });
        return;
    }
    logger_1.logger.error('Unhandled error:', {
        error: err.message,
        stack: err.stack,
        url: req.originalUrl,
        method: req.method,
        ip: req.ip,
    });
    const isDevelopment = process.env.NODE_ENV === 'development';
    res.status(500).json({
        success: false,
        error: {
            message: isDevelopment ? err.message : 'Internal server error',
            stack: isDevelopment ? err.stack : undefined,
        },
    });
};
exports.errorHandler = errorHandler;
//# sourceMappingURL=error-handler.js.map