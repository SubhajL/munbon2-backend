import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import dotenv from 'dotenv';
import { logger } from './utils/logger';
import { errorHandler } from './middleware/errorHandler';
import { healthRouter } from './routes/health.routes';
import { awdRouter } from './routes/awd.routes';
import { connectDatabases } from './config/database';
import { initializeKafka } from './config/kafka';
import { initializeRedis } from './config/redis';
import { startMetricsCollection } from './utils/metrics';

// Load environment variables
dotenv.config();

const app = express();
const PORT = process.env.PORT || 3010;

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Request logging
app.use((req, _, next) => {
  logger.info({
    method: req.method,
    url: req.url,
    ip: req.ip,
    userAgent: req.get('user-agent'),
  }, 'Incoming request');
  next();
});

// Routes
app.use('/health', healthRouter);
app.use('/api/v1/awd', awdRouter);

// Error handling
app.use(errorHandler);

// Graceful shutdown
let server: any;

const gracefulShutdown = async (signal: string) => {
  logger.info(`${signal} received, starting graceful shutdown`);
  
  if (server) {
    server.close(() => {
      logger.info('HTTP server closed');
    });
  }

  // Close database connections, Kafka consumers, etc.
  process.exit(0);
};

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));

// Start server
const startServer = async () => {
  try {
    // Initialize connections
    await connectDatabases();
    await initializeKafka();
    await initializeRedis();
    
    // Start metrics collection
    if (process.env.METRICS_ENABLED === 'true') {
      startMetricsCollection();
    }

    server = app.listen(PORT, () => {
      logger.info(`AWD Control Service running on port ${PORT}`);
      logger.info(`Environment: ${process.env.NODE_ENV}`);
    });
  } catch (error) {
    logger.error(error, 'Failed to start server');
    process.exit(1);
  }
};

startServer();