import 'express-async-errors';
import express from 'express';
import helmet from 'helmet';
import cors from 'cors';
import session from 'express-session';
import RedisStore from 'connect-redis';
import passport from 'passport';
import { createClient } from 'redis';
import { config } from './config';
import { logger } from './utils/logger';
import { errorHandler } from './middleware/error-handler';
import { requestLogger } from './middleware/request-logger';
import { rateLimiter } from './middleware/rate-limiter';
import { setupPassport } from './config/passport';
import { connectDatabase } from './config/database';
import { authRoutes } from './routes/auth.routes';
import { userRoutes } from './routes/user.routes';
import { oauthRoutes } from './routes/oauth.routes';
import { adminRoutes } from './routes/admin.routes';
import { healthRoutes } from './routes/health.routes';

async function startServer() {
  try {
    // Connect to database
    await connectDatabase();
    logger.info('Database connected successfully');

    // Initialize Redis client
    const redisClient = createClient({
      url: config.redis.url,
      password: config.redis.password || undefined,
    });

    redisClient.on('error', (err) => logger.error('Redis Client Error:', err));
    await redisClient.connect();
    logger.info('Redis connected successfully');

    // Create Express app
    const app = express();

    // Security middleware
    app.use(helmet({
      contentSecurityPolicy: {
        directives: {
          defaultSrc: ["'self'"],
          styleSrc: ["'self'", "'unsafe-inline'"],
          scriptSrc: ["'self'"],
          imgSrc: ["'self'", "data:", "https:"],
        },
      },
    }));

    // CORS configuration
    app.use(cors({
      origin: config.cors.origin,
      credentials: config.cors.credentials,
      methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
      allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With'],
    }));

    // Body parsing middleware
    app.use(express.json({ limit: '10mb' }));
    app.use(express.urlencoded({ extended: true, limit: '10mb' }));

    // Session configuration
    app.use(session({
      store: new RedisStore({ client: redisClient }),
      secret: config.session.secret,
      resave: false,
      saveUninitialized: false,
      cookie: {
        secure: config.env === 'production',
        httpOnly: true,
        maxAge: config.session.maxAge,
        sameSite: 'lax',
      },
    }));

    // Passport initialization
    app.use(passport.initialize());
    app.use(passport.session());
    setupPassport();

    // Request logging
    app.use(requestLogger);

    // Rate limiting
    app.use('/api/v1/auth/login', rateLimiter);
    app.use('/api/v1/auth/register', rateLimiter);

    // Routes
    app.use('/api/v1/auth', authRoutes);
    app.use('/api/v1/users', userRoutes);
    app.use('/api/v1/oauth', oauthRoutes);
    app.use('/api/v1/admin', adminRoutes);
    app.use('/health', healthRoutes);

    // Root endpoint
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

    // 404 handler
    app.use((req, res) => {
      res.status(404).json({
        error: 'Not Found',
        message: `Route ${req.method} ${req.path} not found`,
      });
    });

    // Error handling middleware (must be last)
    app.use(errorHandler);

    // Start server
    const server = app.listen(config.port, config.host, () => {
      logger.info(`Auth service listening on ${config.host}:${config.port}`);
      logger.info(`Environment: ${config.env}`);
    });

    // Graceful shutdown
    const gracefulShutdown = async (signal: string) => {
      logger.info(`${signal} received, starting graceful shutdown`);
      
      server.close(() => {
        logger.info('HTTP server closed');
      });

      try {
        await redisClient.quit();
        logger.info('Redis connection closed');
        
        process.exit(0);
      } catch (error) {
        logger.error('Error during shutdown:', error);
        process.exit(1);
      }
    };

    process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
    process.on('SIGINT', () => gracefulShutdown('SIGINT'));

  } catch (error) {
    logger.error('Failed to start server:', error);
    process.exit(1);
  }
}

// Start the server
startServer();