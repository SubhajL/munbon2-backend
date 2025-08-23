"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createWeatherRoutes = createWeatherRoutes;
const express_1 = require("express");
const express_validator_1 = require("express-validator");
const logger_1 = require("../utils/logger");
function createWeatherRoutes(databaseService, cacheService, alertService, analyticsService, irrigationService) {
    const router = (0, express_1.Router)();
    // Validation middleware
    const handleValidationErrors = (req, res, next) => {
        const errors = (0, express_validator_1.validationResult)(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }
        next();
    };
    // GET /current - Get current weather
    router.get('/current', [
        (0, express_validator_1.query)('lat').optional().isFloat({ min: -90, max: 90 }),
        (0, express_validator_1.query)('lng').optional().isFloat({ min: -180, max: 180 }),
        (0, express_validator_1.query)('stationIds').optional().isString(),
    ], handleValidationErrors, async (req, res) => {
        try {
            const { lat, lng, stationIds } = req.query;
            const location = lat && lng ? {
                lat: parseFloat(lat),
                lng: parseFloat(lng),
            } : undefined;
            const stationIdArray = stationIds
                ? stationIds.split(',').map(id => id.trim())
                : undefined;
            const readings = await databaseService.getCurrentWeather(location, stationIdArray);
            res.json({
                success: true,
                data: readings,
                count: readings.length,
                timestamp: new Date(),
            });
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get current weather');
            res.status(500).json({
                success: false,
                error: 'Failed to get current weather',
            });
        }
    });
    // GET /historical - Get historical weather data
    router.get('/historical', [
        (0, express_validator_1.query)('startTime').isISO8601(),
        (0, express_validator_1.query)('endTime').isISO8601(),
        (0, express_validator_1.query)('lat').optional().isFloat({ min: -90, max: 90 }),
        (0, express_validator_1.query)('lng').optional().isFloat({ min: -180, max: 180 }),
        (0, express_validator_1.query)('stationIds').optional().isString(),
    ], handleValidationErrors, async (req, res) => {
        try {
            const { startTime, endTime, lat, lng, stationIds } = req.query;
            const location = lat && lng ? {
                lat: parseFloat(lat),
                lng: parseFloat(lng),
            } : undefined;
            const stationIdArray = stationIds
                ? stationIds.split(',').map(id => id.trim())
                : undefined;
            const readings = await databaseService.getHistoricalWeather(new Date(startTime), new Date(endTime), location, stationIdArray);
            res.json({
                success: true,
                data: readings,
                count: readings.length,
                startTime,
                endTime,
            });
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get historical weather');
            res.status(500).json({
                success: false,
                error: 'Failed to get historical weather',
            });
        }
    });
    // GET /aggregated - Get aggregated weather data
    router.get('/aggregated', [
        (0, express_validator_1.query)('startTime').isISO8601(),
        (0, express_validator_1.query)('endTime').isISO8601(),
        (0, express_validator_1.query)('interval').isIn(['1 hour', '6 hours', '1 day', '1 week', '1 month']),
        (0, express_validator_1.query)('lat').optional().isFloat({ min: -90, max: 90 }),
        (0, express_validator_1.query)('lng').optional().isFloat({ min: -180, max: 180 }),
        (0, express_validator_1.query)('stationId').optional().isString(),
    ], handleValidationErrors, async (req, res) => {
        try {
            const { startTime, endTime, interval, lat, lng, stationId } = req.query;
            const location = lat && lng ? {
                lat: parseFloat(lat),
                lng: parseFloat(lng),
            } : undefined;
            const aggregated = await databaseService.getAggregatedWeather(new Date(startTime), new Date(endTime), interval, location, stationId);
            res.json({
                success: true,
                data: aggregated,
                count: aggregated.length,
                interval,
            });
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get aggregated weather');
            res.status(500).json({
                success: false,
                error: 'Failed to get aggregated weather',
            });
        }
    });
    // GET /stations - Get weather stations
    router.get('/stations', [
        (0, express_validator_1.query)('active').optional().isBoolean(),
    ], handleValidationErrors, async (req, res) => {
        try {
            const { active } = req.query;
            const stations = await databaseService.getWeatherStations(active !== undefined ? active === 'true' : undefined);
            res.json({
                success: true,
                data: stations,
                count: stations.length,
            });
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get weather stations');
            res.status(500).json({
                success: false,
                error: 'Failed to get weather stations',
            });
        }
    });
    // GET /forecast - Get weather forecast
    router.get('/forecast', [
        (0, express_validator_1.query)('lat').isFloat({ min: -90, max: 90 }),
        (0, express_validator_1.query)('lng').isFloat({ min: -180, max: 180 }),
        (0, express_validator_1.query)('days').optional().isInt({ min: 1, max: 14 }),
    ], handleValidationErrors, async (req, res) => {
        try {
            const { lat, lng, days } = req.query;
            const location = {
                lat: parseFloat(lat),
                lng: parseFloat(lng),
            };
            const forecasts = await databaseService.getWeatherForecasts(location, days ? parseInt(days) : 7);
            res.json({
                success: true,
                data: forecasts,
                count: forecasts.length,
                location,
            });
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get weather forecast');
            res.status(500).json({
                success: false,
                error: 'Failed to get weather forecast',
            });
        }
    });
    // GET /analytics - Get weather analytics
    router.get('/analytics', [
        (0, express_validator_1.query)('lat').isFloat({ min: -90, max: 90 }),
        (0, express_validator_1.query)('lng').isFloat({ min: -180, max: 180 }),
        (0, express_validator_1.query)('period').optional().isIn(['1d', '7d', '30d', '90d', '1y']),
    ], handleValidationErrors, async (req, res) => {
        try {
            const { lat, lng, period } = req.query;
            const location = {
                lat: parseFloat(lat),
                lng: parseFloat(lng),
            };
            const analytics = await analyticsService.getWeatherAnalytics(location, period || '7d');
            res.json({
                success: true,
                data: analytics,
            });
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get weather analytics');
            res.status(500).json({
                success: false,
                error: 'Failed to get weather analytics',
            });
        }
    });
    // GET /analytics/trends - Get weather trends
    router.get('/analytics/trends', [
        (0, express_validator_1.query)('lat').isFloat({ min: -90, max: 90 }),
        (0, express_validator_1.query)('lng').isFloat({ min: -180, max: 180 }),
        (0, express_validator_1.query)('metric').isIn(['temperature', 'rainfall', 'humidity', 'pressure']),
        (0, express_validator_1.query)('period').optional().isIn(['7d', '30d', '90d', '1y']),
    ], handleValidationErrors, async (req, res) => {
        try {
            const { lat, lng, metric, period } = req.query;
            const location = {
                lat: parseFloat(lat),
                lng: parseFloat(lng),
            };
            const trends = await analyticsService.getWeatherTrends(location, metric, period || '30d');
            res.json({
                success: true,
                data: trends,
            });
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get weather trends');
            res.status(500).json({
                success: false,
                error: 'Failed to get weather trends',
            });
        }
    });
    // GET /analytics/anomalies - Detect weather anomalies
    router.get('/analytics/anomalies', [
        (0, express_validator_1.query)('lat').isFloat({ min: -90, max: 90 }),
        (0, express_validator_1.query)('lng').isFloat({ min: -180, max: 180 }),
        (0, express_validator_1.query)('threshold').optional().isFloat({ min: 1, max: 5 }),
    ], handleValidationErrors, async (req, res) => {
        try {
            const { lat, lng, threshold } = req.query;
            const location = {
                lat: parseFloat(lat),
                lng: parseFloat(lng),
            };
            const anomalies = await analyticsService.detectAnomalies(location, threshold ? parseFloat(threshold) : 2.5);
            res.json({
                success: true,
                data: anomalies,
            });
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to detect anomalies');
            res.status(500).json({
                success: false,
                error: 'Failed to detect anomalies',
            });
        }
    });
    // GET /analytics/comparison - Compare weather between locations
    router.post('/analytics/comparison', [
        (0, express_validator_1.body)('locations').isArray({ min: 2, max: 10 }),
        (0, express_validator_1.body)('locations.*.lat').isFloat({ min: -90, max: 90 }),
        (0, express_validator_1.body)('locations.*.lng').isFloat({ min: -180, max: 180 }),
        (0, express_validator_1.body)('period').optional().isIn(['7d', '30d', '90d', '1y']),
    ], handleValidationErrors, async (req, res) => {
        try {
            const { locations, period } = req.body;
            const comparison = await analyticsService.getComparativeAnalytics(locations, period || '30d');
            res.json({
                success: true,
                data: comparison,
            });
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to compare weather');
            res.status(500).json({
                success: false,
                error: 'Failed to compare weather',
            });
        }
    });
    // GET /evapotranspiration - Calculate evapotranspiration
    router.get('/evapotranspiration', [
        (0, express_validator_1.query)('lat').isFloat({ min: -90, max: 90 }),
        (0, express_validator_1.query)('lng').isFloat({ min: -180, max: 180 }),
        (0, express_validator_1.query)('date').optional().isISO8601(),
        (0, express_validator_1.query)('cropCoefficient').optional().isFloat({ min: 0.1, max: 2.0 }),
    ], handleValidationErrors, async (req, res) => {
        try {
            const { lat, lng, date, cropCoefficient } = req.query;
            const location = {
                lat: parseFloat(lat),
                lng: parseFloat(lng),
            };
            const et = await analyticsService.calculateEvapotranspiration(location, date ? new Date(date) : new Date(), cropCoefficient ? parseFloat(cropCoefficient) : 1.0);
            res.json({
                success: true,
                data: et,
            });
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to calculate evapotranspiration');
            res.status(500).json({
                success: false,
                error: 'Failed to calculate evapotranspiration',
            });
        }
    });
    // GET /irrigation/recommendation - Get irrigation recommendation
    router.get('/irrigation/recommendation', [
        (0, express_validator_1.query)('lat').isFloat({ min: -90, max: 90 }),
        (0, express_validator_1.query)('lng').isFloat({ min: -180, max: 180 }),
        (0, express_validator_1.query)('cropType').optional().isString(),
        (0, express_validator_1.query)('growthStage').optional().isString(),
        (0, express_validator_1.query)('soilMoisture').optional().isFloat({ min: 0, max: 100 }),
    ], handleValidationErrors, async (req, res) => {
        try {
            const { lat, lng, cropType, growthStage, soilMoisture } = req.query;
            const location = {
                lat: parseFloat(lat),
                lng: parseFloat(lng),
            };
            const recommendation = await irrigationService.getIrrigationRecommendation(location, cropType || 'rice', growthStage || 'vegetative', soilMoisture ? parseFloat(soilMoisture) : undefined);
            res.json({
                success: true,
                data: recommendation,
            });
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get irrigation recommendation');
            res.status(500).json({
                success: false,
                error: 'Failed to get irrigation recommendation',
            });
        }
    });
    // GET /irrigation/schedule - Get irrigation schedule
    router.get('/irrigation/schedule', [
        (0, express_validator_1.query)('lat').isFloat({ min: -90, max: 90 }),
        (0, express_validator_1.query)('lng').isFloat({ min: -180, max: 180 }),
        (0, express_validator_1.query)('cropType').isString(),
        (0, express_validator_1.query)('growthStage').isString(),
        (0, express_validator_1.query)('fieldSize').isFloat({ min: 0.1, max: 10000 }),
        (0, express_validator_1.query)('system').optional().isIn(['drip', 'sprinkler', 'flood']),
    ], handleValidationErrors, async (req, res) => {
        try {
            const { lat, lng, cropType, growthStage, fieldSize, system } = req.query;
            const location = {
                lat: parseFloat(lat),
                lng: parseFloat(lng),
            };
            const schedule = await irrigationService.getIrrigationSchedule(location, cropType, growthStage, parseFloat(fieldSize), system || 'flood');
            res.json({
                success: true,
                data: schedule,
            });
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get irrigation schedule');
            res.status(500).json({
                success: false,
                error: 'Failed to get irrigation schedule',
            });
        }
    });
    // GET /irrigation/water-balance - Get water balance analysis
    router.get('/irrigation/water-balance', [
        (0, express_validator_1.query)('lat').isFloat({ min: -90, max: 90 }),
        (0, express_validator_1.query)('lng').isFloat({ min: -180, max: 180 }),
        (0, express_validator_1.query)('cropType').isString(),
        (0, express_validator_1.query)('growthStage').isString(),
        (0, express_validator_1.query)('period').optional().isIn(['7d', '30d', '90d']),
    ], handleValidationErrors, async (req, res) => {
        try {
            const { lat, lng, cropType, growthStage, period } = req.query;
            const location = {
                lat: parseFloat(lat),
                lng: parseFloat(lng),
            };
            const waterBalance = await irrigationService.getWaterBalanceAnalysis(location, cropType, growthStage, period || '30d');
            res.json({
                success: true,
                data: waterBalance,
            });
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get water balance');
            res.status(500).json({
                success: false,
                error: 'Failed to get water balance',
            });
        }
    });
    // GET /alerts - Get active weather alerts
    router.get('/alerts', [
        (0, express_validator_1.query)('lat').optional().isFloat({ min: -90, max: 90 }),
        (0, express_validator_1.query)('lng').optional().isFloat({ min: -180, max: 180 }),
        (0, express_validator_1.query)('radius').optional().isFloat({ min: 1, max: 500 }),
    ], handleValidationErrors, async (req, res) => {
        try {
            const { lat, lng, radius } = req.query;
            const location = lat && lng ? {
                lat: parseFloat(lat),
                lng: parseFloat(lng),
            } : undefined;
            const alerts = await alertService.getActiveAlerts(location, radius ? parseFloat(radius) : undefined);
            res.json({
                success: true,
                data: alerts,
                count: alerts.length,
            });
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get alerts');
            res.status(500).json({
                success: false,
                error: 'Failed to get alerts',
            });
        }
    });
    // PUT /alerts/:id/acknowledge - Acknowledge an alert
    router.put('/alerts/:id/acknowledge', [
        (0, express_validator_1.param)('id').isUUID(),
        (0, express_validator_1.body)('acknowledgedBy').isString(),
    ], handleValidationErrors, async (req, res) => {
        try {
            const { id } = req.params;
            const { acknowledgedBy } = req.body;
            await alertService.acknowledgeAlert(id, acknowledgedBy);
            res.json({
                success: true,
                message: 'Alert acknowledged',
            });
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to acknowledge alert');
            res.status(500).json({
                success: false,
                error: 'Failed to acknowledge alert',
            });
        }
    });
    return router;
}
//# sourceMappingURL=weather.routes.js.map