"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.healthRoutes = void 0;
const express_1 = require("express");
const database_1 = require("../config/database");
const redis_1 = require("redis");
const config_1 = require("../config");
const router = (0, express_1.Router)();
exports.healthRoutes = router;
router.get('/', async (req, res) => {
    const health = {
        status: 'healthy',
        timestamp: new Date().toISOString(),
        service: 'auth-service',
        version: '1.0.0',
        uptime: process.uptime(),
        environment: config_1.config.env,
        checks: {
            database: 'unknown',
            redis: 'unknown',
        },
    };
    try {
        await database_1.AppDataSource.query('SELECT 1');
        health.checks.database = 'healthy';
    }
    catch (error) {
        health.checks.database = 'unhealthy';
        health.status = 'degraded';
    }
    try {
        const redisClient = (0, redis_1.createClient)({ url: config_1.config.redis.url });
        await redisClient.connect();
        await redisClient.ping();
        await redisClient.quit();
        health.checks.redis = 'healthy';
    }
    catch (error) {
        health.checks.redis = 'unhealthy';
        health.status = 'degraded';
    }
    const statusCode = health.status === 'healthy' ? 200 : 503;
    res.status(statusCode).json(health);
});
router.get('/live', (req, res) => {
    res.status(200).json({ status: 'alive' });
});
router.get('/ready', async (req, res) => {
    try {
        await database_1.AppDataSource.query('SELECT 1');
        res.status(200).json({ status: 'ready' });
    }
    catch (error) {
        res.status(503).json({ status: 'not ready' });
    }
});
//# sourceMappingURL=health.routes.js.map