"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.requestLogger = void 0;
const logger_1 = require("../utils/logger");
const requestLogger = (req, res, next) => {
    const start = Date.now();
    logger_1.logger.info(`${req.method} ${req.originalUrl}`, {
        method: req.method,
        url: req.originalUrl,
        ip: req.ip,
        userAgent: req.get('user-agent'),
    });
    res.on('finish', () => {
        const duration = Date.now() - start;
        logger_1.logger.info(`${req.method} ${req.originalUrl} ${res.statusCode} ${duration}ms`, {
            method: req.method,
            url: req.originalUrl,
            statusCode: res.statusCode,
            duration,
        });
    });
    next();
};
exports.requestLogger = requestLogger;
//# sourceMappingURL=request-logger.js.map