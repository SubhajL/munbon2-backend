"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.errorHandler = errorHandler;
exports.notFoundHandler = notFoundHandler;
const logger_1 = require("../utils/logger");
function errorHandler(err, _req, res, _next) {
    logger_1.logger.error({ err }, 'Unhandled error');
    const statusCode = err.statusCode || 500;
    const message = err.message || 'Internal server error';
    res.status(statusCode).json({
        success: false,
        error: {
            message,
            ...(process.env.NODE_ENV === 'development' && { stack: err.stack }),
        },
    });
}
function notFoundHandler(_req, res) {
    res.status(404).json({
        success: false,
        error: {
            message: 'Resource not found',
        },
    });
}
//# sourceMappingURL=error.middleware.js.map