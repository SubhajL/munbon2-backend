import 'express-async-errors';
import express from 'express';
import helmet from 'helmet';
import cors from 'cors';
import { config } from './config';
import { logger } from './utils/logger';
import { errorHandler } from './middleware/error-handler';
import { requestLogger } from './middleware/request-logger';
import { connectDatabase } from './config/database';
import { initializeCache } from './config/cache';
import { spatialRoutes } from './routes/spatial.routes';
import { zoneRoutes } from './routes/zone.routes';
import { parcelRoutes } from './routes/parcel.routes';
import { canalRoutes } from './routes/canal.routes';
import { tileRoutes } from './routes/tile.routes';
import { shapeFileRoutes } from './routes/shapefile.routes';
import ridPlanRoutes from './routes/rid-plan.routes';
import rosDemandRoutes from './routes/ros-demands-v2';

async function startServer() {
  try {
    // Connect to database
    await connectDatabase();
    logger.info('Database connected successfully');

    // Initialize cache
    await initializeCache();
    logger.info('Cache initialized successfully');

    // Create Express app
    const app = express();

    // Security middleware
    app.use(helmet({
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

    // CORS configuration
    app.use(cors({
      origin: config.cors.origin,
      credentials: config.cors.credentials,
      methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
      allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With'],
    }));

    // Body parsing middleware
    app.use(express.json({ limit: '50mb' }));
    app.use(express.urlencoded({ extended: true, limit: '50mb' }));

    // Request logging
    app.use(requestLogger);

    // API Routes
    const apiPrefix = config.api.prefix;
    app.use(`${apiPrefix}/spatial`, spatialRoutes);
    app.use(`${apiPrefix}/zones`, zoneRoutes);
    app.use(`${apiPrefix}/parcels`, parcelRoutes);
    app.use(`${apiPrefix}/canals`, canalRoutes);
    app.use(`${apiPrefix}/tiles`, tileRoutes);
    app.use(`${apiPrefix}/shapefiles`, shapeFileRoutes);
    app.use(`${apiPrefix}/rid-plan`, ridPlanRoutes);
    app.use(`${apiPrefix}/ros-demands`, rosDemandRoutes);
    
    // Health check endpoint
    app.get('/health', (req, res) => {
      res.json({
        status: 'healthy',
        service: 'gis-service',
        timestamp: new Date().toISOString(),
      });
    });

    // Root endpoint
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
      logger.info(`GIS service listening on ${config.host}:${config.port}`);
      logger.info(`Environment: ${config.env}`);
    });

    // Graceful shutdown
    const gracefulShutdown = async (signal: string) => {
      logger.info(`${signal} received, starting graceful shutdown`);
      
      server.close(() => {
        logger.info('HTTP server closed');
      });

      try {
        // Close database connections
        logger.info('Closing database connections...');
        
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