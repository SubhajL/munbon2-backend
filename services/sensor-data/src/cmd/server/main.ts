import * as dotenv from 'dotenv';
import path from 'path';
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import { createServer } from 'http';
import { Server } from 'socket.io';
import pino from 'pino';
import swaggerUi from 'swagger-ui-express';
import { MqttBroker } from '../../services/mqtt-broker';
import { SensorDataService } from '../../services/sensor-data.service';
import { TimescaleRepository } from '../../repository/timescale.repository';
import { setupRoutes } from '../../routes';
import { errorHandler } from '../../middleware/error-handler';
import { swaggerSpec } from '../../config/swagger';
import { SmartFarmRepository } from '../../repository/smartfarm.repository';

// Load env from default location (cwd) and then from the service directory to
// ensure PM2 runs from repo root still picks up services/sensor-data/.env
dotenv.config();
const serviceEnvPath = path.resolve(__dirname, '../../..', '.env');
dotenv.config({ path: serviceEnvPath, override: true });

const logger = pino({
  transport: {
    target: 'pino-pretty',
    options: {
      colorize: true
    }
  }
});

async function main() {
  try {
    // Initialize Express app
    const app = express();
    const server = createServer(app);
    const io = new Server(server, {
      cors: {
        origin: process.env.CORS_ORIGIN?.split(',') || '*',
        methods: ['GET', 'POST']
      }
    });

    // Middleware
    app.use(cors({
      origin: '*',
      methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
      allowedHeaders: ['Content-Type', 'Authorization', 'X-API-Key', 'X-Admin-Token']
    }));
    app.use(helmet({
      contentSecurityPolicy: {
        directives: {
          defaultSrc: ["'self'"],
          styleSrc: ["'self'", "'unsafe-inline'"],
          scriptSrc: ["'self'", "'unsafe-inline'"],
          imgSrc: ["'self'", "data:", "https:"],
        },
      },
    }));
    app.use(express.json());
    app.use(express.urlencoded({ extended: true }));

    // API Documentation
    app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(swaggerSpec, {
      customCss: '.swagger-ui .topbar { display: none }',
      customSiteTitle: 'Munbon Sensor Data API Documentation'
    }));

    // Health check
    app.get('/health', (_req, res) => {
      res.json({
        status: 'healthy',
        service: 'sensor-data',
        timestamp: new Date().toISOString()
      });
    });

    // Initialize repositories
    const timescaleRepo = new TimescaleRepository({
      host: process.env.TIMESCALE_HOST || 'localhost',
      port: parseInt(process.env.TIMESCALE_PORT || '5432'),
      database: process.env.TIMESCALE_DB || 'munbon_timescale',
      user: process.env.TIMESCALE_USER || 'postgres',
      password: process.env.TIMESCALE_PASSWORD || ''
    });

    // Log connection target (safe: no password)
    logger.info({
      host: process.env.TIMESCALE_HOST,
      port: process.env.TIMESCALE_PORT,
      database: process.env.TIMESCALE_DB,
      user: process.env.TIMESCALE_USER,
      ssl: process.env.TIMESCALE_SSL || 'false'
    }, 'Connecting to TimescaleDB');

    // Optional schema logging for visibility
    if (process.env.TIMESCALE_SCHEMA) {
      logger.info(`Using Timescale schema: ${process.env.TIMESCALE_SCHEMA}`);
    }

    await timescaleRepo.initialize();
    logger.info('TimescaleDB initialized');

    // Initialize MQTT broker
    const mqttBroker = new MqttBroker({
      port: parseInt(process.env.MQTT_PORT || '1883'),
      wsPort: parseInt(process.env.MQTT_WS_PORT || '8083'),
      logger
    });

    await mqttBroker.start();
    logger.info('MQTT broker started');

    // Initialize sensor data service
    const sensorDataService = new SensorDataService({
      repository: timescaleRepo,
      mqttBroker,
      io,
      logger
    });

    // Optional SmartFarm repository for plot/threshold enrichment
    const smartFarmRepo = new SmartFarmRepository();

    // Setup routes
    setupRoutes(app, {
      sensorDataService,
      timescaleRepo,
      logger,
      smartFarmRepository: smartFarmRepo,
    });

    // Error handler
    app.use(errorHandler);

    // Socket.IO connection handling
    io.on('connection', (socket) => {
      logger.info(`Client connected: ${socket.id}`);

      socket.on('subscribe', (topics: string[]) => {
        topics.forEach(topic => {
          socket.join(topic);
          logger.info(`Client ${socket.id} subscribed to ${topic}`);
        });
      });

      socket.on('unsubscribe', (topics: string[]) => {
        topics.forEach(topic => {
          socket.leave(topic);
          logger.info(`Client ${socket.id} unsubscribed from ${topic}`);
        });
      });

      socket.on('disconnect', () => {
        logger.info(`Client disconnected: ${socket.id}`);
      });
    });

    // Start server
    const PORT = process.env.PORT || 3001;
    server.listen(PORT, () => {
      logger.info(`🚀 Sensor Data Service running on port ${PORT}`);
      logger.info(`📡 MQTT broker on port ${process.env.MQTT_PORT || 1883}`);
      logger.info(`🌐 WebSocket on port ${process.env.MQTT_WS_PORT || 8083}`);
    });

    // Graceful shutdown
    process.on('SIGTERM', async () => {
      logger.info('SIGTERM received, shutting down gracefully...');
      
      server.close(() => {
        logger.info('HTTP server closed');
      });

      await mqttBroker.stop();
      await timescaleRepo.close();
      
      process.exit(0);
    });

  } catch (error) {
    logger.error({ error }, 'Failed to start service');
    process.exit(1);
  }
}

main().catch(error => {
  logger.error({ error }, 'Unhandled error');
  process.exit(1);
});
