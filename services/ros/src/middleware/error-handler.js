"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.errorHandler = errorHandler;
const logger_1 = require("@utils/logger");
function errorHandler(err, req, res, next) {
    logger_1.logger.error('Error occurred:', {
        error: err.message,
        stack: err.stack,
        url: req.url,
        method: req.method,
        body: req.body,
    });
    res.status(500).json({
        error: 'Internal Server Error',
        message: process.env.NODE_ENV === 'development' ? err.message : 'An error occurred',
    });
}
//# sourceMappingURL=error-handler.js.map