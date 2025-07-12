import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import rateLimit from 'express-rate-limit';
import { config } from '@config/index';
import { logger } from '@utils/logger';
import { testConnection } from '@config/database';
import { errorHandler } from '@middleware/error-handler';
import { requestLogger } from '@middleware/request-logger';

// Import routers
import etoRouter from '@routes/eto.routes';
import kcRouter from '@routes/kc.routes';
import cropRouter from '@routes/crop.routes';
import demandRouter from '@routes/demand.routes';
import scheduleRouter from '@routes/schedule.routes';
import calendarRouter from '@routes/calendar.routes';
import areaRouter from '@routes/area.routes';
import rainfallRouter from '@routes/rainfall.routes';
import waterLevelRouter from '@routes/water-level.routes';

const app = express();

// Basic middleware
app.use(helmet());
app.use(cors());
app.use(compression());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Request logging
app.use(requestLogger);

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  message: 'Too many requests from this IP, please try again later.',
});
app.use('/api/', limiter);

// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'ok',
    service: config.service.name,
    timestamp: new Date().toISOString(),
  });
});

// API routes
app.use('/api/v1/ros/eto', etoRouter);
app.use('/api/v1/ros/kc', kcRouter);
app.use('/api/v1/ros/crops', cropRouter);
app.use('/api/v1/ros/demand', demandRouter);
app.use('/api/v1/ros/schedule', scheduleRouter);
app.use('/api/v1/ros/calendar', calendarRouter);
app.use('/api/v1/ros/areas', areaRouter);
app.use('/api/v1/ros/rainfall', rainfallRouter);
app.use('/api/v1/ros/water-level', waterLevelRouter);

// Error handling
app.use(errorHandler);

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
    const dbConnected = await testConnection();
    if (!dbConnected) {
      throw new Error('Failed to connect to database');
    }

    // Start server
    app.listen(config.service.port, () => {
      logger.info(`${config.service.name} listening on port ${config.service.port}`);
      logger.info(`Environment: ${config.service.env}`);
    });
  } catch (error) {
    logger.error('Failed to start server:', error);
    process.exit(1);
  }
}

// Handle graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('SIGTERM received, shutting down gracefully');
  process.exit(0);
});

process.on('SIGINT', async () => {
  logger.info('SIGINT received, shutting down gracefully');
  process.exit(0);
});

// Start the server
startServer();