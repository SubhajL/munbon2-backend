"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const http_1 = __importDefault(require("http"));
const cors_1 = __importDefault(require("cors"));
const helmet_1 = __importDefault(require("helmet"));
const express_rate_limit_1 = __importDefault(require("express-rate-limit"));
const pino_http_1 = __importDefault(require("pino-http"));
const config_1 = require("./config");
const logger_1 = require("./utils/logger");
const timescale_service_1 = require("./services/timescale.service");
const cache_service_1 = require("./services/cache.service");
const alert_service_1 = require("./services/alert.service");
const mqtt_service_1 = require("./services/mqtt.service");
const websocket_service_1 = require("./services/websocket.service");
const gate_control_service_1 = require("./services/gate-control.service");
const data_processor_1 = require("./workers/data-processor");
const water_level_routes_1 = require("./routes/water-level.routes");
const health_routes_1 = require("./routes/health.routes");
const error_middleware_1 = require("./middleware/error.middleware");
async function startServer() {
    // Initialize services
    const timescaleService = new timescale_service_1.TimescaleService();
    const cacheService = new cache_service_1.CacheService();
    const alertService = new alert_service_1.AlertService(cacheService, timescaleService);
    const mqttService = new mqtt_service_1.MqttService();
    const gateControlService = new gate_control_service_1.GateControlService(timescaleService);
    // Create Express app
    const app = (0, express_1.default)();
    const server = http_1.default.createServer(app);
    // Initialize WebSocket service
    const websocketService = new websocket_service_1.WebSocketService(server);
    // Initialize data processor
    const dataProcessor = new data_processor_1.DataProcessor(cacheService, alertService, mqttService, websocketService, gateControlService);
    // Middleware
    app.use((0, helmet_1.default)());
    app.use((0, cors_1.default)());
    app.use(express_1.default.json({ limit: '10mb' }));
    app.use(express_1.default.urlencoded({ extended: true }));
    // Request logging
    app.use((0, pino_http_1.default)({
        logger: logger_1.logger,
        autoLogging: {
            ignore: (req) => req.url === '/health',
        },
    }));
    // Rate limiting
    const limiter = (0, express_rate_limit_1.default)({
        windowMs: config_1.config.rateLimit.windowMs,
        max: config_1.config.rateLimit.maxRequests,
        message: 'Too many requests from this IP, please try again later.',
    });
    app.use('/api/', limiter);
    // Routes
    app.use('/api/v1/water-levels', (0, water_level_routes_1.createWaterLevelRoutes)(timescaleService, cacheService, alertService, gateControlService));
    app.use('/', (0, health_routes_1.createHealthRoutes)(timescaleService, cacheService, mqttService, websocketService));
    // Error handling
    app.use(error_middleware_1.notFoundHandler);
    app.use(error_middleware_1.errorHandler);
    // Start data processor
    await dataProcessor.start();
    // Start server
    server.listen(config_1.config.port, config_1.config.host, () => {
        logger_1.logger.info({
            service: 'water-level-monitoring',
            port: config_1.config.port,
            host: config_1.config.host,
            env: config_1.config.env,
        }, 'Water level monitoring service started');
    });
    // Graceful shutdown
    process.on('SIGTERM', async () => {
        logger_1.logger.info('SIGTERM received, shutting down gracefully');
        server.close(() => {
            logger_1.logger.info('HTTP server closed');
        });
        await timescaleService.close();
        await cacheService.close();
        mqttService.close();
        websocketService.close();
        process.exit(0);
    });
}
// Start the server
startServer().catch((error) => {
    logger_1.logger.fatal({ error }, 'Failed to start server');
    process.exit(1);
});
//# sourceMappingURL=index.js.map