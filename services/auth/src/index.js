"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
require("express-async-errors");
const express_1 = __importDefault(require("express"));
const helmet_1 = __importDefault(require("helmet"));
const cors_1 = __importDefault(require("cors"));
const express_session_1 = __importDefault(require("express-session"));
const connect_redis_1 = __importDefault(require("connect-redis"));
const passport_1 = __importDefault(require("passport"));
const redis_1 = require("redis");
const config_1 = require("./config");
const logger_1 = require("./utils/logger");
const error_handler_1 = require("./middleware/error-handler");
const request_logger_1 = require("./middleware/request-logger");
const rate_limiter_1 = require("./middleware/rate-limiter");
const passport_2 = require("./config/passport");
const database_1 = require("./config/database");
const auth_routes_1 = require("./routes/auth.routes");
const user_routes_1 = require("./routes/user.routes");
const oauth_routes_1 = require("./routes/oauth.routes");
const admin_routes_1 = require("./routes/admin.routes");
const health_routes_1 = require("./routes/health.routes");
async function startServer() {
    try {
        await (0, database_1.connectDatabase)();
        logger_1.logger.info('Database connected successfully');
        const redisClient = (0, redis_1.createClient)({
            url: config_1.config.redis.url,
            password: config_1.config.redis.password || undefined,
        });
        redisClient.on('error', (err) => logger_1.logger.error('Redis Client Error:', err));
        await redisClient.connect();
        logger_1.logger.info('Redis connected successfully');
        const app = (0, express_1.default)();
        app.use((0, helmet_1.default)({
            contentSecurityPolicy: {
                directives: {
                    defaultSrc: ["'self'"],
                    styleSrc: ["'self'", "'unsafe-inline'"],
                    scriptSrc: ["'self'"],
                    imgSrc: ["'self'", "data:", "https:"],
                },
            },
        }));
        app.use((0, cors_1.default)({
            origin: config_1.config.cors.origin,
            credentials: config_1.config.cors.credentials,
            methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
            allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With'],
        }));
        app.use(express_1.default.json({ limit: '10mb' }));
        app.use(express_1.default.urlencoded({ extended: true, limit: '10mb' }));
        app.use((0, express_session_1.default)({
            store: new connect_redis_1.default({ client: redisClient }),
            secret: config_1.config.session.secret,
            resave: false,
            saveUninitialized: false,
            cookie: {
                secure: config_1.config.env === 'production',
                httpOnly: true,
                maxAge: config_1.config.session.maxAge,
                sameSite: 'lax',
            },
        }));
        app.use(passport_1.default.initialize());
        app.use(passport_1.default.session());
        (0, passport_2.setupPassport)();
        app.use(request_logger_1.requestLogger);
        app.use('/api/v1/auth/login', rate_limiter_1.rateLimiter);
        app.use('/api/v1/auth/register', rate_limiter_1.rateLimiter);
        app.use('/api/v1/auth', auth_routes_1.authRoutes);
        app.use('/api/v1/users', user_routes_1.userRoutes);
        app.use('/api/v1/oauth', oauth_routes_1.oauthRoutes);
        app.use('/api/v1/admin', admin_routes_1.adminRoutes);
        app.use('/health', health_routes_1.healthRoutes);
        app.get('/', (req, res) => {
            res.json({
                service: 'Munbon Authentication Service',
                version: '1.0.0',
                status: 'running',
                endpoints: {
                    auth: '/api/v1/auth',
                    users: '/api/v1/users',
                    oauth: '/api/v1/oauth',
                    admin: '/api/v1/admin',
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
            logger_1.logger.info(`Auth service listening on ${config_1.config.host}:${config_1.config.port}`);
            logger_1.logger.info(`Environment: ${config_1.config.env}`);
        });
        const gracefulShutdown = async (signal) => {
            logger_1.logger.info(`${signal} received, starting graceful shutdown`);
            server.close(() => {
                logger_1.logger.info('HTTP server closed');
            });
            try {
                await redisClient.quit();
                logger_1.logger.info('Redis connection closed');
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