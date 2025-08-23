"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const cors_1 = __importDefault(require("cors"));
const helmet_1 = __importDefault(require("helmet"));
const compression_1 = __importDefault(require("compression"));
const http_1 = __importDefault(require("http"));
const config_1 = require("./config");
const logger_1 = require("./utils/logger");
const weather_routes_1 = require("./routes/weather.routes");
const database_service_1 = require("./services/database.service");
const cache_service_1 = require("./services/cache.service");
const alert_service_1 = require("./services/alert.service");
const mqtt_service_1 = require("./services/mqtt.service");
const websocket_service_1 = require("./services/websocket.service");
const analytics_service_1 = require("./services/analytics.service");
const irrigation_service_1 = require("./services/irrigation.service");
const data_processor_1 = require("./workers/data-processor");
// Initialize Express app
const app = (0, express_1.default)();
const server = http_1.default.createServer(app);
// Initialize services
const databaseService = new database_service_1.DatabaseService();
const cacheService = new cache_service_1.CacheService();
const alertService = new alert_service_1.AlertService(cacheService);
const mqttService = new mqtt_service_1.MqttService();
const websocketService = new websocket_service_1.WebSocketService(server);
const analyticsService = new analytics_service_1.AnalyticsService(databaseService, cacheService);
const irrigationService = new irrigation_service_1.IrrigationService(databaseService, analyticsService, cacheService);
// Initialize data processor
const dataProcessor = new data_processor_1.DataProcessor(cacheService, databaseService, alertService, mqttService, websocketService);
// Middleware
app.use((0, helmet_1.default)());
app.use((0, compression_1.default)());
app.use((0, cors_1.default)({
    origin: config_1.config.cors.origin.split(','),
    credentials: true,
}));
app.use(express_1.default.json());
app.use(express_1.default.urlencoded({ extended: true }));
// Request logging
app.use((req, res, next) => {
    logger_1.logger.info({
        method: req.method,
        url: req.url,
        headers: req.headers,
    }, 'Incoming request');
    next();
});
// Health check endpoint
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        service: 'weather-monitoring',
        version: process.env.npm_package_version || '1.0.0',
        timestamp: new Date(),
        connections: {
            mqtt: mqttService.isConnected(),
            websocket: websocketService.getConnectionCount(),
        },
    });
});
// API routes
app.use('/api/v1/weather', (0, weather_routes_1.createWeatherRoutes)(databaseService, cacheService, alertService, analyticsService, irrigationService));
// WebSocket status endpoint
app.get('/api/v1/ws/status', (req, res) => {
    res.json({
        connections: websocketService.getConnectionCount(),
        subscriptions: websocketService.getSubscriptionCount(),
        details: websocketService.getDetailedStats(),
    });
});
// Error handling middleware
app.use((err, req, res, next) => {
    logger_1.logger.error({
        err,
        req: {
            method: req.method,
            url: req.url,
            headers: req.headers,
            body: req.body,
        },
    }, 'Request error');
    res.status(err.status || 500).json({
        success: false,
        error: err.message || 'Internal server error',
    });
});
// 404 handler
app.use((req, res) => {
    res.status(404).json({
        success: false,
        error: 'Not found',
    });
});
// Graceful shutdown
process.on('SIGTERM', async () => {
    logger_1.logger.info('SIGTERM received, shutting down gracefully');
    // Stop accepting new connections
    server.close(() => {
        logger_1.logger.info('HTTP server closed');
    });
    // Stop data processor
    dataProcessor.stop();
    // Disconnect services
    await Promise.all([
        mqttService.disconnect(),
        cacheService.close(),
        databaseService.close(),
    ]);
    process.exit(0);
});
// Start server
async function start() {
    try {
        // Connect to MQTT
        await mqttService.connect();
        logger_1.logger.info('Connected to MQTT broker');
        // Start data processor
        dataProcessor.start();
        logger_1.logger.info('Data processor started');
        // Setup MQTT event handlers
        mqttService.on('refresh', async (payload) => {
            logger_1.logger.info({ payload }, 'Refresh command received');
            await cacheService.invalidateWeatherCache(payload.location);
        });
        mqttService.on('invalidate-cache', async (payload) => {
            logger_1.logger.info({ payload }, 'Cache invalidation command received');
            await cacheService.invalidateWeatherCache(payload.location);
            await cacheService.invalidateForecastCache(payload.location);
        });
        mqttService.on('request-current', async (payload) => {
            try {
                const weather = await databaseService.getCurrentWeather(payload.location);
                await mqttService.publishWeatherData(weather[0]);
            }
            catch (error) {
                logger_1.logger.error({ error, payload }, 'Failed to handle current weather request');
            }
        });
        mqttService.on('request-forecast', async (payload) => {
            try {
                const forecast = await databaseService.getWeatherForecasts(payload.location, payload.days || 7);
                await mqttService.publishForecast(payload.location, forecast);
            }
            catch (error) {
                logger_1.logger.error({ error, payload }, 'Failed to handle forecast request');
            }
        });
        mqttService.on('request-analytics', async (payload) => {
            try {
                const analytics = await analyticsService.getWeatherAnalytics(payload.location, payload.period);
                await mqttService.publishAnalytics(payload.location, analytics);
            }
            catch (error) {
                logger_1.logger.error({ error, payload }, 'Failed to handle analytics request');
            }
        });
        mqttService.on('request-irrigation', async (payload) => {
            try {
                const recommendation = await irrigationService.getIrrigationRecommendation(payload.location, payload.cropType, payload.growthStage, payload.soilMoisture);
                await mqttService.publishIrrigationRecommendation(recommendation);
            }
            catch (error) {
                logger_1.logger.error({ error, payload }, 'Failed to handle irrigation request');
            }
        });
        // Start HTTP server
        server.listen(config_1.config.port, () => {
            logger_1.logger.info({
                port: config_1.config.port,
                env: config_1.config.env,
            }, 'Weather Monitoring Service started');
        });
    }
    catch (error) {
        logger_1.logger.fatal({ error }, 'Failed to start server');
        process.exit(1);
    }
}
// Start the application
start();
//# sourceMappingURL=index.js.map