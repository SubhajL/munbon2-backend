"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.calculationRateLimiter = exports.uploadRateLimiter = exports.rateLimiter = void 0;
const express_rate_limit_1 = __importDefault(require("express-rate-limit"));
exports.rateLimiter = (0, express_rate_limit_1.default)({
    windowMs: parseInt(process.env.API_RATE_WINDOW || '15') * 60 * 1000, // minutes to milliseconds
    max: parseInt(process.env.API_RATE_LIMIT || '100'),
    message: 'Too many requests from this IP, please try again later.',
    standardHeaders: true,
    legacyHeaders: false,
    handler: (req, res) => {
        res.status(429).json({
            success: false,
            error: {
                message: 'Too many requests, please try again later.',
                retryAfter: req.rateLimit?.resetTime,
            },
        });
    },
});
// Create specific rate limiters for different endpoints
exports.uploadRateLimiter = (0, express_rate_limit_1.default)({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 10, // limit each IP to 10 uploads per windowMs
    message: 'Too many file uploads, please try again later.',
});
exports.calculationRateLimiter = (0, express_rate_limit_1.default)({
    windowMs: 5 * 60 * 1000, // 5 minutes
    max: 20, // limit each IP to 20 calculations per windowMs
    message: 'Too many calculation requests, please try again later.',
});
//# sourceMappingURL=rateLimiter.js.map