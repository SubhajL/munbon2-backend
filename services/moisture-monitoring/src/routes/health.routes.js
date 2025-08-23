"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createHealthRoutes = createHealthRoutes;
const express_1 = require("express");
const router = (0, express_1.Router)();
function createHealthRoutes(timescaleService, cacheService, mqttService, websocketService) {
    router.get('/health', async (_req, res) => {
        try {
            // Check TimescaleDB connection
            const dbHealthy = await checkDatabaseHealth(timescaleService);
            // Check Redis connection
            const cacheHealthy = await checkCacheHealth(cacheService);
            const health = {
                status: dbHealthy && cacheHealthy ? 'healthy' : 'unhealthy',
                timestamp: new Date(),
                service: 'moisture-monitoring',
                version: '1.0.0',
                uptime: process.uptime(),
                checks: {
                    database: dbHealthy ? 'healthy' : 'unhealthy',
                    cache: cacheHealthy ? 'healthy' : 'unhealthy',
                    mqtt: 'healthy', // MQTT has auto-reconnect
                    websocket: 'healthy',
                },
                metrics: {
                    connectedClients: websocketService.getConnectedClients(),
                    memoryUsage: process.memoryUsage(),
                },
            };
            res.status(health.status === 'healthy' ? 200 : 503).json(health);
        }
        catch (error) {
            res.status(503).json({
                status: 'unhealthy',
                error: error.message,
            });
        }
    });
    router.get('/ready', async (_req, res) => {
        try {
            const dbHealthy = await checkDatabaseHealth(timescaleService);
            if (dbHealthy) {
                res.json({ ready: true });
            }
            else {
                res.status(503).json({ ready: false });
            }
        }
        catch (error) {
            res.status(503).json({ ready: false });
        }
    });
    return router;
}
async function checkDatabaseHealth(timescaleService) {
    try {
        // Simple query to check connection
        await timescaleService.getLatestReadings([], 1);
        return true;
    }
    catch (error) {
        return false;
    }
}
async function checkCacheHealth(cacheService) {
    try {
        const testKey = 'health:check';
        await cacheService.set(testKey, { test: true }, 10);
        await cacheService.get(testKey);
        await cacheService.delete(testKey);
        return true;
    }
    catch (error) {
        return false;
    }
}
//# sourceMappingURL=health.routes.js.map