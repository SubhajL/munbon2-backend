"use strict";
// Register module aliases first
require('module-alias/register');

var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const cors_1 = __importDefault(require("cors"));
const helmet_1 = __importDefault(require("helmet"));
const compression_1 = __importDefault(require("compression"));
const express_rate_limit_1 = __importDefault(require("express-rate-limit"));
const index_1 = require("@config/index");
const logger_1 = require("@utils/logger");
const database_1 = require("@config/database");
const error_handler_1 = require("@middleware/error-handler");
const request_logger_1 = require("@middleware/request-logger");
// Import routers
const eto_routes_1 = __importDefault(require("@routes/eto.routes"));
const kc_routes_1 = __importDefault(require("@routes/kc.routes"));
const crop_routes_1 = __importDefault(require("@routes/crop.routes"));
const demand_routes_1 = __importDefault(require("@routes/demand.routes"));
const schedule_routes_1 = __importDefault(require("@routes/schedule.routes"));
const calendar_routes_1 = __importDefault(require("@routes/calendar.routes"));
const area_routes_1 = __importDefault(require("@routes/area.routes"));
const rainfall_routes_1 = __importDefault(require("@routes/rainfall.routes"));
const water_level_routes_1 = __importDefault(require("@routes/water-level.routes"));
const plot_demand_routes_1 = __importDefault(require("@routes/plot-demand.routes"));
const plot_planting_date_routes_1 = __importDefault(require("@routes/plot-planting-date.routes"));
const app = (0, express_1.default)();
// Basic middleware
app.use((0, helmet_1.default)());
app.use((0, cors_1.default)());
app.use((0, compression_1.default)());
app.use(express_1.default.json());
app.use(express_1.default.urlencoded({ extended: true }));
// Request logging
app.use(request_logger_1.requestLogger);
// Rate limiting
const limiter = (0, express_rate_limit_1.default)({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 100, // limit each IP to 100 requests per windowMs
    message: 'Too many requests from this IP, please try again later.',
});
app.use('/api/', limiter);
// Health check endpoint
app.get('/health', (req, res) => {
    res.status(200).json({
        status: 'ok',
        service: index_1.config.service.name,
        timestamp: new Date().toISOString(),
    });
});
// API routes
app.use('/api/v1/ros/eto', eto_routes_1.default);
app.use('/api/v1/ros/kc', kc_routes_1.default);
app.use('/api/v1/ros/crops', crop_routes_1.default);
app.use('/api/v1/ros/demand', demand_routes_1.default);
app.use('/api/v1/ros/schedule', schedule_routes_1.default);
app.use('/api/v1/ros/calendar', calendar_routes_1.default);
app.use('/api/v1/ros/areas', area_routes_1.default);
app.use('/api/v1/ros/rainfall', rainfall_routes_1.default);
app.use('/api/v1/ros/water-level', water_level_routes_1.default);
app.use('/api/v1/ros/plot-demand', plot_demand_routes_1.default);
app.use('/api/v1/ros/plot-planting', plot_planting_date_routes_1.default);
// Error handling
app.use(error_handler_1.errorHandler);
// 404 handler
app.use((req, res) => {
    res.status(404).json({
        error: 'Not Found',
        message: `Route ${req.originalUrl} not found`,
    });
});
async function startServer() {
    try {
        // Test database connection
        const dbConnected = await (0, database_1.testConnection)();
        if (!dbConnected) {
            throw new Error('Failed to connect to database');
        }
        // Start server
        app.listen(index_1.config.service.port, () => {
            logger_1.logger.info(`${index_1.config.service.name} listening on port ${index_1.config.service.port}`);
            logger_1.logger.info(`Environment: ${index_1.config.service.env}`);
        });
    }
    catch (error) {
        logger_1.logger.error('Failed to start server:', error);
        process.exit(1);
    }
}
// Handle graceful shutdown
process.on('SIGTERM', async () => {
    logger_1.logger.info('SIGTERM received, shutting down gracefully');
    process.exit(0);
});
process.on('SIGINT', async () => {
    logger_1.logger.info('SIGINT received, shutting down gracefully');
    process.exit(0);
});
// Start the server
startServer();
//# sourceMappingURL=index.js.map