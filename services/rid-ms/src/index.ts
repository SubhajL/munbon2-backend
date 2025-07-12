import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import { rateLimit } from 'express-rate-limit';
import swaggerUi from 'swagger-ui-express';
import { config } from './config';
import { logger } from './utils/logger';
import { errorHandler } from './middleware/error-handler';
import { ridMsRoutes } from './routes/rid-ms.routes';
import { shapeFileRoutes } from './routes/shapefile.routes';
import { waterDemandRoutes } from './routes/water-demand.routes';
import { healthRoutes } from './routes/health.routes';
import { parcelsRoutes } from './routes/parcels.routes';
import { zonesRoutes } from './routes/zones.routes';
import { exportRoutes } from './routes/export.routes';
import { initializeDatabase } from './services/database.service';
import { KafkaService } from './services/kafka.service';
import { JobScheduler } from './jobs/job-scheduler';
import { swaggerSpec } from './config/swagger';

const app = express();

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Rate limiting
const limiter = rateLimit({
  windowMs: config.api.rateLimitWindow * 60 * 1000,
  max: config.api.rateLimitMaxRequests,
  message: 'Too many requests from this IP, please try again later.'
});
app.use(`${config.api.prefix}/`, limiter);

// API Documentation
app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(swaggerSpec));

// Routes
app.use(`${config.api.prefix}/health`, healthRoutes);
app.use(`${config.api.prefix}/rid-ms`, ridMsRoutes);
app.use(`${config.api.prefix}/shapefiles`, shapeFileRoutes);
app.use(`${config.api.prefix}/water-demand`, waterDemandRoutes);
app.use(`${config.api.prefix}/parcels`, parcelsRoutes);
app.use(`${config.api.prefix}/zones`, zonesRoutes);
app.use(`${config.api.prefix}/export`, exportRoutes);

// Error handling
app.use(errorHandler);

// Initialize services
async function startServer() {
  try {
    // Initialize database
    await initializeDatabase();
    logger.info('Database initialized successfully');

    // Initialize Kafka
    const kafkaService = KafkaService.getInstance();
    await kafkaService.connect();
    logger.info('Kafka service connected');

    // Initialize job scheduler
    const jobScheduler = JobScheduler.getInstance();
    await jobScheduler.start();
    logger.info('Job scheduler started');

    // Start server
    const server = app.listen(config.port, () => {
      logger.info(`RID-MS Service listening on port ${config.port}`);
      logger.info(`API Documentation available at http://localhost:${config.port}/api-docs`);
    });

    // Graceful shutdown
    process.on('SIGTERM', async () => {
      logger.info('SIGTERM received, shutting down gracefully');
      server.close(() => {
        logger.info('HTTP server closed');
      });
      
      await kafkaService.disconnect();
      await jobScheduler.stop();
      process.exit(0);
    });

  } catch (error) {
    logger.error('Failed to start server:', error);
    process.exit(1);
  }
}

startServer();