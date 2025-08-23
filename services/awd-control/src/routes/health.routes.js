"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.healthRouter = void 0;
const express_1 = require("express");
const database_1 = require("../config/database");
const redis_1 = require("../config/redis");
const logger_1 = require("../utils/logger");
exports.healthRouter = (0, express_1.Router)();
exports.healthRouter.get('/', async (_req, res) => {
    res.json({
        status: 'ok',
        service: 'awd-control-service',
        timestamp: new Date().toISOString(),
    });
});
exports.healthRouter.get('/ready', async (_req, res) => {
    const checks = {
        postgres: false,
        timescale: false,
        redis: false,
    };
    try {
        const pgPool = (0, database_1.getPostgresPool)();
        await pgPool.query('SELECT 1');
        checks.postgres = true;
    }
    catch (error) {
        logger_1.logger.error(error, 'PostgreSQL health check failed');
    }
    try {
        const tsPool = (0, database_1.getTimescalePool)();
        await tsPool.query('SELECT 1');
        checks.timescale = true;
    }
    catch (error) {
        logger_1.logger.error(error, 'TimescaleDB health check failed');
    }
    try {
        const redis = (0, redis_1.getRedisClient)();
        await redis.ping();
        checks.redis = true;
    }
    catch (error) {
        logger_1.logger.error(error, 'Redis health check failed');
    }
    const allHealthy = Object.values(checks).every(check => check === true);
    const status = allHealthy ? 200 : 503;
    res.status(status).json({
        ready: allHealthy,
        checks,
        timestamp: new Date().toISOString(),
    });
});
exports.healthRouter.get('/live', (_req, res) => {
    res.json({
        alive: true,
        uptime: process.uptime(),
        timestamp: new Date().toISOString(),
    });
});
//# sourceMappingURL=health.routes.js.map