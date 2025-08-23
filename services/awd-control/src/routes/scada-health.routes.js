"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const scada_api_service_1 = require("../services/scada-api.service");
const router = (0, express_1.Router)();
router.get('/scada/health', async (req, res) => {
    try {
        const health = await scada_api_service_1.scadaApiService.getHealthStatus();
        res.json(health);
    }
    catch (error) {
        res.status(503).json({
            status: 'failed',
            message: 'Failed to get SCADA health status',
            error: error.message
        });
    }
});
router.get('/scada/health/detailed', async (req, res) => {
    try {
        const health = await scada_api_service_1.scadaApiService.getDetailedHealthStatus();
        res.json(health);
    }
    catch (error) {
        res.status(503).json({
            status: 'failed',
            message: 'Failed to get detailed SCADA health status',
            error: error.message
        });
    }
});
router.get('/scada/availability', async (req, res) => {
    try {
        const isAvailable = await scada_api_service_1.scadaApiService.isScadaAvailable();
        res.json({
            available: isAvailable,
            timestamp: new Date()
        });
    }
    catch (error) {
        res.status(503).json({
            available: false,
            error: error.message,
            timestamp: new Date()
        });
    }
});
exports.default = router;
//# sourceMappingURL=scada-health.routes.js.map