"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const mongoose_1 = __importDefault(require("mongoose"));
const redis_1 = require("../config/redis");
const router = (0, express_1.Router)();
router.get('/', async (req, res) => {
    const healthStatus = {
        status: 'healthy',
        service: 'ros-service',
        timestamp: new Date().toISOString(),
        uptime: process.uptime(),
        environment: process.env.NODE_ENV,
        version: process.env.npm_package_version || '1.0.0'
    };
    res.json(healthStatus);
});
router.get('/ready', async (req, res) => {
    try {
        // Check MongoDB connection
        if (mongoose_1.default.connection.readyState !== 1) {
            throw new Error('MongoDB not connected');
        }
        // Check Redis connection
        const redis = (0, redis_1.getRedisClient)();
        await redis.ping();
        res.json({
            status: 'ready',
            service: 'ros-service',
            timestamp: new Date().toISOString(),
            dependencies: {
                mongodb: 'connected',
                redis: 'connected'
            }
        });
    }
    catch (error) {
        res.status(503).json({
            status: 'not ready',
            service: 'ros-service',
            timestamp: new Date().toISOString(),
            error: error instanceof Error ? error.message : 'Unknown error'
        });
    }
});
router.get('/live', (req, res) => {
    res.json({
        status: 'alive',
        service: 'ros-service',
        timestamp: new Date().toISOString()
    });
});
exports.default = router;
//# sourceMappingURL=health.routes.js.map