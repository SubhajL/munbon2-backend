"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const cors_1 = __importDefault(require("cors"));
const helmet_1 = __importDefault(require("helmet"));
const express_rate_limit_1 = require("express-rate-limit");
const swagger_ui_express_1 = __importDefault(require("swagger-ui-express"));
const config_1 = require("./config");
const logger_1 = require("./utils/logger");
const error_handler_1 = require("./middleware/error-handler");
const rid_ms_routes_1 = require("./routes/rid-ms.routes");
const shapefile_routes_1 = require("./routes/shapefile.routes");
const water_demand_routes_1 = require("./routes/water-demand.routes");
const health_routes_1 = require("./routes/health.routes");
const parcels_routes_1 = require("./routes/parcels.routes");
const zones_routes_1 = require("./routes/zones.routes");
const export_routes_1 = require("./routes/export.routes");
const database_service_1 = require("./services/database.service");
const kafka_service_1 = require("./services/kafka.service");
const job_scheduler_1 = require("./jobs/job-scheduler");
const swagger_1 = require("./config/swagger");
const app = (0, express_1.default)();
app.use((0, helmet_1.default)());
app.use((0, cors_1.default)());
app.use(express_1.default.json({ limit: '10mb' }));
app.use(express_1.default.urlencoded({ extended: true, limit: '10mb' }));
const limiter = (0, express_rate_limit_1.rateLimit)({
    windowMs: config_1.config.api.rateLimitWindow * 60 * 1000,
    max: config_1.config.api.rateLimitMaxRequests,
    message: 'Too many requests from this IP, please try again later.'
});
app.use(`${config_1.config.api.prefix}/`, limiter);
app.use('/api-docs', swagger_ui_express_1.default.serve, swagger_ui_express_1.default.setup(swagger_1.swaggerSpec));
app.use(`${config_1.config.api.prefix}/health`, health_routes_1.healthRoutes);
app.use(`${config_1.config.api.prefix}/rid-ms`, rid_ms_routes_1.ridMsRoutes);
app.use(`${config_1.config.api.prefix}/shapefiles`, shapefile_routes_1.shapeFileRoutes);
app.use(`${config_1.config.api.prefix}/water-demand`, water_demand_routes_1.waterDemandRoutes);
app.use(`${config_1.config.api.prefix}/parcels`, parcels_routes_1.parcelsRoutes);
app.use(`${config_1.config.api.prefix}/zones`, zones_routes_1.zonesRoutes);
app.use(`${config_1.config.api.prefix}/export`, export_routes_1.exportRoutes);
app.use(error_handler_1.errorHandler);
async function startServer() {
    try {
        await (0, database_service_1.initializeDatabase)();
        logger_1.logger.info('Database initialized successfully');
        const kafkaService = kafka_service_1.KafkaService.getInstance();
        await kafkaService.connect();
        logger_1.logger.info('Kafka service connected');
        const jobScheduler = job_scheduler_1.JobScheduler.getInstance();
        await jobScheduler.start();
        logger_1.logger.info('Job scheduler started');
        const server = app.listen(config_1.config.port, () => {
            logger_1.logger.info(`RID-MS Service listening on port ${config_1.config.port}`);
            logger_1.logger.info(`API Documentation available at http://localhost:${config_1.config.port}/api-docs`);
        });
        process.on('SIGTERM', async () => {
            logger_1.logger.info('SIGTERM received, shutting down gracefully');
            server.close(() => {
                logger_1.logger.info('HTTP server closed');
            });
            await kafkaService.disconnect();
            await jobScheduler.stop();
            process.exit(0);
        });
    }
    catch (error) {
        logger_1.logger.error('Failed to start server:', error);
        process.exit(1);
    }
}
startServer();
//# sourceMappingURL=index.js.map