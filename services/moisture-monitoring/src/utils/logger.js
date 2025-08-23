"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.logger = void 0;
const pino_1 = __importDefault(require("pino"));
const config_1 = require("../config");
exports.logger = (0, pino_1.default)({
    level: config_1.config.logLevel,
    transport: config_1.config.env === 'development' ? {
        target: 'pino-pretty',
        options: {
            colorize: true,
            ignore: 'pid,hostname',
            translateTime: 'SYS:standard',
        },
    } : undefined,
    serializers: {
        req: pino_1.default.stdSerializers.req,
        res: pino_1.default.stdSerializers.res,
        err: pino_1.default.stdSerializers.err,
    },
    base: {
        service: 'moisture-monitoring',
        env: config_1.config.env,
    },
});
//# sourceMappingURL=logger.js.map