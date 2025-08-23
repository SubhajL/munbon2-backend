"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
require("express-async-errors");
const express_1 = __importDefault(require("express"));
const helmet_1 = __importDefault(require("helmet"));
const cors_1 = __importDefault(require("cors"));
const config_1 = require("./config");
const logger_1 = require("./utils/logger");
const error_handler_1 = require("./middleware/error-handler");
const request_logger_1 = require("./middleware/request-logger");
const database_1 = require("./config/database");
const cache_1 = require("./config/cache");
const spatial_routes_1 = require("./routes/spatial.routes");
const zone_routes_1 = require("./routes/zone.routes");
const parcel_routes_1 = require("./routes/parcel.routes");
const canal_routes_1 = require("./routes/canal.routes");
const tile_routes_1 = require("./routes/tile.routes");
const shapefile_routes_1 = require("./routes/shapefile.routes");
const rid_plan_routes_1 = __importDefault(require("./routes/rid-plan.routes"));
const ros_demands_v2_1 = __importDefault(require("./routes/ros-demands-v2"));
async function startServer() {
    try {
        await (0, database_1.connectDatabase)();
        logger_1.logger.info('Database connected successfully');
        await (0, cache_1.initializeCache)();
        logger_1.logger.info('Cache initialized successfully');
        const app = (0, express_1.default)();
        app.use((0, helmet_1.default)({
            contentSecurityPolicy: {
                directives: {
                    defaultSrc: ["'self'"],
                    styleSrc: ["'self'", "'unsafe-inline'"],
                    scriptSrc: ["'self'"],
                    imgSrc: ["'self'", "data:", "https:", "blob:"],
                    connectSrc: ["'self'", "https://*.mapbox.com", "https://*.gistda.or.th"],
                },
            },
        }));
        app.use((0, cors_1.default)({
            origin: config_1.config.cors.origin,
            credentials: config_1.config.cors.credentials,
            methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
            allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With'],
        }));
        app.use(express_1.default.json({ limit: '50mb' }));
        app.use(express_1.default.urlencoded({ extended: true, limit: '50mb' }));
        app.use(request_logger_1.requestLogger);
        const apiPrefix = config_1.config.api.prefix;
        app.use(`${apiPrefix}/spatial`, spatial_routes_1.spatialRoutes);
        app.use(`${apiPrefix}/zones`, zone_routes_1.zoneRoutes);
        app.use(`${apiPrefix}/parcels`, parcel_routes_1.parcelRoutes);
        app.use(`${apiPrefix}/canals`, canal_routes_1.canalRoutes);
        app.use(`${apiPrefix}/tiles`, tile_routes_1.tileRoutes);
        app.use(`${apiPrefix}/shapefiles`, shapefile_routes_1.shapeFileRoutes);
        app.use(`${apiPrefix}/rid-plan`, rid_plan_routes_1.default);
        app.use(`${apiPrefix}/ros-demands`, ros_demands_v2_1.default);
        app.get('/health', (req, res) => {
            res.json({
                status: 'healthy',
                service: 'gis-service',
                timestamp: new Date().toISOString(),
            });
        });
        app.get('/', (req, res) => {
            res.json({
                service: 'Munbon GIS Service',
                version: '1.0.0',
                status: 'running',
                endpoints: {
                    spatial: `${apiPrefix}/spatial`,
                    zones: `${apiPrefix}/zones`,
                    parcels: `${apiPrefix}/parcels`,
                    canals: `${apiPrefix}/canals`,
                    tiles: `${apiPrefix}/tiles`,
                    ridPlan: `${apiPrefix}/rid-plan`,
                    rosDemands: `${apiPrefix}/ros-demands`,
                    health: '/health',
                },
            });
        });
        app.use((req, res) => {
            res.status(404).json({
                error: 'Not Found',
                message: `Route ${req.method} ${req.path} not found`,
            });
        });
        app.use(error_handler_1.errorHandler);
        const server = app.listen(config_1.config.port, config_1.config.host, () => {
            logger_1.logger.info(`GIS service listening on ${config_1.config.host}:${config_1.config.port}`);
            logger_1.logger.info(`Environment: ${config_1.config.env}`);
        });
        const gracefulShutdown = async (signal) => {
            logger_1.logger.info(`${signal} received, starting graceful shutdown`);
            server.close(() => {
                logger_1.logger.info('HTTP server closed');
            });
            try {
                logger_1.logger.info('Closing database connections...');
                process.exit(0);
            }
            catch (error) {
                logger_1.logger.error('Error during shutdown:', error);
                process.exit(1);
            }
        };
        process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
        process.on('SIGINT', () => gracefulShutdown('SIGINT'));
    }
    catch (error) {
        logger_1.logger.error('Failed to start server:', error);
        process.exit(1);
    }
}
startServer();
//# sourceMappingURL=index.js.map