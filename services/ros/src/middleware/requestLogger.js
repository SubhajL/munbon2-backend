"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.requestLogger = void 0;
const logger_1 = require("../utils/logger");
const requestLogger = (req, res, next) => {
    const start = Date.now();
    // Log request
    logger_1.logger.info({
        type: 'request',
        method: req.method,
        path: req.path,
        query: req.query,
        ip: req.ip,
        userAgent: req.get('user-agent'),
    });
    // Log response
    res.on('finish', () => {
        const duration = Date.now() - start;
        logger_1.logger.info({
            type: 'response',
            method: req.method,
            path: req.path,
            statusCode: res.statusCode,
            duration: `${duration}ms`,
            contentLength: res.get('content-length'),
        });
    });
    next();
};
exports.requestLogger = requestLogger;
//# sourceMappingURL=requestLogger.js.map