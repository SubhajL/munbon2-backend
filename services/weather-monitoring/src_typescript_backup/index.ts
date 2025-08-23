import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import http from 'http';
import { config } from './config';
import { logger } from './utils/logger';
import { createWeatherRoutes } from './routes/weather.routes';
import { DatabaseService } from './services/database.service';
import { CacheService } from './services/cache.service';
import { AlertService } from './services/alert.service';
import { MqttService } from './services/mqtt.service';
import { WebSocketService } from './services/websocket.service';
import { AnalyticsService } from './services/analytics.service';
import { IrrigationService } from './services/irrigation.service';
import { DataProcessor } from './workers/data-processor';

// Initialize Express app
const app = express();
const server = http.createServer(app);

// Initialize services
const databaseService = new DatabaseService();
const cacheService = new CacheService();
const alertService = new AlertService(cacheService);
const mqttService = new MqttService();
const websocketService = new WebSocketService(server);
const analyticsService = new AnalyticsService(databaseService, cacheService);
const irrigationService = new IrrigationService(databaseService, analyticsService, cacheService);

// Initialize data processor
const dataProcessor = new DataProcessor(
  cacheService,
  databaseService,
  alertService,
  mqttService,
  websocketService
);

// Middleware
app.use(helmet());
app.use(compression());
app.use(cors({
  origin: config.cors.origin.split(','),
  credentials: true,
}));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Request logging
app.use((req, res, next) => {
  logger.info({
    method: req.method,
    url: req.url,
    headers: req.headers,
  }, 'Incoming request');
  next();
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'weather-monitoring',
    version: process.env.npm_package_version || '1.0.0',
    timestamp: new Date(),
    connections: {
      mqtt: mqttService.isConnected(),
      websocket: websocketService.getConnectionCount(),
    },
  });
});

// API routes
app.use('/api/v1/weather', createWeatherRoutes(
  databaseService,
  cacheService,
  alertService,
  analyticsService,
  irrigationService
));

// WebSocket status endpoint
app.get('/api/v1/ws/status', (req, res) => {
  res.json({
    connections: websocketService.getConnectionCount(),
    subscriptions: websocketService.getSubscriptionCount(),
    details: websocketService.getDetailedStats(),
  });
});

// Error handling middleware
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  logger.error({
    err,
    req: {
      method: req.method,
      url: req.url,
      headers: req.headers,
      body: req.body,
    },
  }, 'Request error');

  res.status(err.status || 500).json({
    success: false,
    error: err.message || 'Internal server error',
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    success: false,
    error: 'Not found',
  });
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('SIGTERM received, shutting down gracefully');
  
  // Stop accepting new connections
  server.close(() => {
    logger.info('HTTP server closed');
  });

  // Stop data processor
  dataProcessor.stop();

  // Disconnect services
  await Promise.all([
    mqttService.disconnect(),
    cacheService.close(),
    databaseService.close(),
  ]);

  process.exit(0);
});

// Start server
async function start() {
  try {
    // Connect to MQTT
    await mqttService.connect();
    logger.info('Connected to MQTT broker');

    // Start data processor
    dataProcessor.start();
    logger.info('Data processor started');

    // Setup MQTT event handlers
    mqttService.on('refresh', async (payload) => {
      logger.info({ payload }, 'Refresh command received');
      await cacheService.invalidateWeatherCache(payload.location);
    });

    mqttService.on('invalidate-cache', async (payload) => {
      logger.info({ payload }, 'Cache invalidation command received');
      await cacheService.invalidateWeatherCache(payload.location);
      await cacheService.invalidateForecastCache(payload.location);
    });

    mqttService.on('request-current', async (payload) => {
      try {
        const weather = await databaseService.getCurrentWeather(payload.location);
        await mqttService.publishWeatherData(weather[0]);
      } catch (error) {
        logger.error({ error, payload }, 'Failed to handle current weather request');
      }
    });

    mqttService.on('request-forecast', async (payload) => {
      try {
        const forecast = await databaseService.getWeatherForecasts(payload.location, payload.days || 7);
        await mqttService.publishForecast(payload.location, forecast);
      } catch (error) {
        logger.error({ error, payload }, 'Failed to handle forecast request');
      }
    });

    mqttService.on('request-analytics', async (payload) => {
      try {
        const analytics = await analyticsService.getWeatherAnalytics(payload.location, payload.period);
        await mqttService.publishAnalytics(payload.location, analytics);
      } catch (error) {
        logger.error({ error, payload }, 'Failed to handle analytics request');
      }
    });

    mqttService.on('request-irrigation', async (payload) => {
      try {
        const recommendation = await irrigationService.getIrrigationRecommendation(
          payload.location,
          payload.cropType,
          payload.growthStage,
          payload.soilMoisture
        );
        await mqttService.publishIrrigationRecommendation(recommendation);
      } catch (error) {
        logger.error({ error, payload }, 'Failed to handle irrigation request');
      }
    });

    // Start HTTP server
    server.listen(config.port, () => {
      logger.info({
        port: config.port,
        env: config.env,
      }, 'Weather Monitoring Service started');
    });
  } catch (error) {
    logger.fatal({ error }, 'Failed to start server');
    process.exit(1);
  }
}

// Start the application
start();