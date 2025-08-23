"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.logger = void 0;
const winston_1 = __importDefault(require("winston"));
const config_1 = require("../config");
const logFormat = winston_1.default.format.combine(winston_1.default.format.timestamp(), winston_1.default.format.errors({ stack: true }), winston_1.default.format.json());
const simpleFormat = winston_1.default.format.combine(winston_1.default.format.timestamp(), winston_1.default.format.colorize(), winston_1.default.format.simple());
exports.logger = winston_1.default.createLogger({
    level: config_1.config.logging.level,
    format: config_1.config.logging.format === 'json' ? logFormat : simpleFormat,
    defaultMeta: { service: 'gis-service' },
    transports: [
        new winston_1.default.transports.Console({
            handleExceptions: true,
        }),
    ],
    exitOnError: false,
});
//# sourceMappingURL=logger.js.map