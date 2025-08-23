import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import dotenv from 'dotenv';
import { logger } from './utils/logger';
import { errorHandler } from './middleware/errorHandler';
import { healthRouter } from './routes/health.routes';
import { awdRouter } from './routes/awd.routes';
import scadaHealthRouter from './routes/scada-health.routes';
import { connectDatabases } from './config/database';
import { initializeKafka } from './config/kafka';
import { initializeRedis } from './config/redis';
import { startMetricsCollection } from './utils/metrics';
import { scadaGateControlService } from './services/scada-gate-control.service';

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
app.use('/api/v1/awd', scadaHealthRouter);

// Import and use new routes
import scadaRouter from './routes/scada.routes';
import { irrigationRouter } from './routes/irrigation.routes';

app.use('/api/scada', scadaRouter);
app.use('/api/irrigation', irrigationRouter);

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

    // Start SCADA gate monitoring
    scadaGateControlService.startMonitoring();
    logger.info('SCADA gate control monitoring initialized');

    server = app.listen(PORT, () => {
      logger.info(`AWD Control Service running on port ${PORT}`);
      logger.info(`Environment: ${process.env.NODE_ENV}`);
      logger.info('Water level-based irrigation control ready (NO PUMPS)');
    });
  } catch (error) {
    logger.error(error, 'Failed to start server');
    process.exit(1);
  }
};

startServer();