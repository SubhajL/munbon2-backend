import express from 'express';
import http from 'http';
import cors from 'cors';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import pinoHttp from 'pino-http';
import { config } from './config';
import { logger } from './utils/logger';
import { TimescaleService } from './services/timescale.service';
import { CacheService } from './services/cache.service';
import { AlertService } from './services/alert.service';
import { MqttService } from './services/mqtt.service';
import { WebSocketService } from './services/websocket.service';
import { DataProcessor } from './workers/data-processor';
import { createMoistureRoutes } from './routes/moisture.routes';
import { createHealthRoutes } from './routes/health.routes';
import { errorHandler, notFoundHandler } from './middleware/error.middleware';

async function startServer() {
  // Initialize services
  const timescaleService = new TimescaleService();
  const cacheService = new CacheService();
  const alertService = new AlertService(cacheService);
  const mqttService = new MqttService();
  
  // Create Express app
  const app = express();
  const server = http.createServer(app);
  
  // Initialize WebSocket service
  const websocketService = new WebSocketService(server);
  
  // Initialize data processor
  const dataProcessor = new DataProcessor(
    cacheService,
    alertService,
    mqttService,
    websocketService
  );
  
  // Middleware
  app.use(helmet());
  app.use(cors());
  app.use(express.json({ limit: '10mb' }));
  app.use(express.urlencoded({ extended: true }));
  
  // Request logging
  app.use(pinoHttp({
    logger,
    autoLogging: {
      ignore: (req) => req.url === '/health',
    },
  }));
  
  // Rate limiting
  const limiter = rateLimit({
    windowMs: config.rateLimit.windowMs,
    max: config.rateLimit.maxRequests,
    message: 'Too many requests from this IP, please try again later.',
  });
  app.use('/api/', limiter);
  
  // Routes
  app.use('/api/v1/moisture', createMoistureRoutes(timescaleService, cacheService, alertService));
  app.use('/', createHealthRoutes(timescaleService, cacheService, mqttService, websocketService));
  
  // Error handling
  app.use(notFoundHandler);
  app.use(errorHandler);
  
  // Start data processor
  await dataProcessor.start();
  
  // Start server
  server.listen(config.port, config.host, () => {
    logger.info({
      service: 'moisture-monitoring',
      port: config.port,
      host: config.host,
      env: config.env,
    }, 'Moisture monitoring service started');
  });
  
  // Graceful shutdown
  process.on('SIGTERM', async () => {
    logger.info('SIGTERM received, shutting down gracefully');
    
    server.close(() => {
      logger.info('HTTP server closed');
    });
    
    await timescaleService.close();
    await cacheService.close();
    mqttService.close();
    websocketService.close();
    
    process.exit(0);
  });
}

// Start the server
startServer().catch((error) => {
  logger.fatal({ error }, 'Failed to start server');
  process.exit(1);
});