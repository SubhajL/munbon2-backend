"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.logger = void 0;
const pino_1 = __importDefault(require("pino"));
const logLevel = process.env.LOG_LEVEL || 'info';
const isProduction = process.env.NODE_ENV === 'production';
exports.logger = (0, pino_1.default)({
    level: logLevel,
    transport: isProduction
        ? undefined
        : {
            target: 'pino-pretty',
            options: {
                colorize: true,
                translateTime: 'yyyy-mm-dd HH:MM:ss',
                ignore: 'pid,hostname',
            },
        },
    base: {
        service: 'awd-control-service',
    },
    timestamp: pino_1.default.stdTimeFunctions.isoTime,
    formatters: {
        level: (label) => {
            return { level: label.toUpperCase() };
        },
    },
    serializers: {
        error: pino_1.default.stdSerializers.err,
        req: (req) => ({
            id: req.id,
            method: req.method,
            url: req.url,
            query: req.query,
            params: req.params,
        }),
        res: (res) => ({
            statusCode: res.statusCode,
        }),
    },
});
//# sourceMappingURL=logger.js.map