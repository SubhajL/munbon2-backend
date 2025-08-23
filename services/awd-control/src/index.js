"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const cors_1 = __importDefault(require("cors"));
const helmet_1 = __importDefault(require("helmet"));
const dotenv_1 = __importDefault(require("dotenv"));
const logger_1 = require("./utils/logger");
const errorHandler_1 = require("./middleware/errorHandler");
const health_routes_1 = require("./routes/health.routes");
const awd_routes_1 = require("./routes/awd.routes");
const scada_health_routes_1 = __importDefault(require("./routes/scada-health.routes"));
const database_1 = require("./config/database");
const kafka_1 = require("./config/kafka");
const redis_1 = require("./config/redis");
const metrics_1 = require("./utils/metrics");
const scada_gate_control_service_1 = require("./services/scada-gate-control.service");
dotenv_1.default.config();
const app = (0, express_1.default)();
const PORT = process.env.PORT || 3010;
app.use((0, helmet_1.default)());
app.use((0, cors_1.default)());
app.use(express_1.default.json());
app.use(express_1.default.urlencoded({ extended: true }));
app.use((req, _, next) => {
    logger_1.logger.info({
        method: req.method,
        url: req.url,
        ip: req.ip,
        userAgent: req.get('user-agent'),
    }, 'Incoming request');
    next();
});
app.use('/health', health_routes_1.healthRouter);
app.use('/api/v1/awd', awd_routes_1.awdRouter);
app.use('/api/v1/awd', scada_health_routes_1.default);
const scada_routes_1 = __importDefault(require("./routes/scada.routes"));
const irrigation_routes_1 = require("./routes/irrigation.routes");
app.use('/api/scada', scada_routes_1.default);
app.use('/api/irrigation', irrigation_routes_1.irrigationRouter);
app.use(errorHandler_1.errorHandler);
let server;
const gracefulShutdown = async (signal) => {
    logger_1.logger.info(`${signal} received, starting graceful shutdown`);
    if (server) {
        server.close(() => {
            logger_1.logger.info('HTTP server closed');
        });
    }
    process.exit(0);
};
process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));
const startServer = async () => {
    try {
        await (0, database_1.connectDatabases)();
        await (0, kafka_1.initializeKafka)();
        await (0, redis_1.initializeRedis)();
        if (process.env.METRICS_ENABLED === 'true') {
            (0, metrics_1.startMetricsCollection)();
        }
        scada_gate_control_service_1.scadaGateControlService.startMonitoring();
        logger_1.logger.info('SCADA gate control monitoring initialized');
        server = app.listen(PORT, () => {
            logger_1.logger.info(`AWD Control Service running on port ${PORT}`);
            logger_1.logger.info(`Environment: ${process.env.NODE_ENV}`);
            logger_1.logger.info('Water level-based irrigation control ready (NO PUMPS)');
        });
    }
    catch (error) {
        logger_1.logger.error(error, 'Failed to start server');
        process.exit(1);
    }
};
startServer();
//# sourceMappingURL=index.js.map