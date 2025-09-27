require('dotenv').config();
const express = require('express');
const { ApolloServer } = require('@apollo/server');
const { expressMiddleware } = require('@apollo/server/express4');
const { ApolloServerPluginDrainHttpServer } = require('@apollo/server/plugin/drainHttpServer');
const { makeExecutableSchema } = require('@graphql-tools/schema');
const { WebSocketServer } = require('ws');
const { useServer } = require('graphql-ws/lib/use/ws');
const http = require('http');
const cors = require('cors');
const winston = require('winston');

const typeDefs = require('./graphql/schema');
const resolvers = require('./graphql/resolvers');
const { initializeScadaConnection, closeConnections } = require('./config/database');
const waterControlRoutes = require('./routes/water-control.routes');
const redisConfig = require('./config/redis');
const DemandEventSubscriber = require('./services/demand-event-subscriber');
const WaterControlOrchestratorService = require('./services/water-control-orchestrator.service');

// Configure logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console({
      format: winston.format.simple()
    }),
    new winston.transports.File({ filename: 'error.log', level: 'error' }),
    new winston.transports.File({ filename: 'combined.log' })
  ]
});

async function startServer() {
  // Create Express app
  const app = express();
  const httpServer = http.createServer(app);

  // Create GraphQL schema
  const schema = makeExecutableSchema({ typeDefs, resolvers });

  // Create WebSocket server for subscriptions
  const wsServer = new WebSocketServer({
    server: httpServer,
    path: process.env.SUBSCRIPTION_PATH || '/graphql/ws',
  });

  // Set up WebSocket server
  const serverCleanup = useServer(
    {
      schema,
      onConnect: async (ctx) => {
        logger.info('Client connected to WebSocket');
        // Add authentication here if needed
        return true;
      },
      onDisconnect: async (ctx) => {
        logger.info('Client disconnected from WebSocket');
      },
    },
    wsServer
  );

  // Create Apollo Server
  const server = new ApolloServer({
    schema,
    plugins: [
      ApolloServerPluginDrainHttpServer({ httpServer }),
      {
        async serverWillStart() {
          return {
            async drainServer() {
              await serverCleanup.dispose();
            },
          };
        },
      },
    ],
    formatError: (err) => {
      logger.error('GraphQL Error:', err);
      return err;
    },
  });

  // Start Apollo Server
  await server.start();

  // Apply middleware
  app.use(cors());
  app.use(express.json());

  // Health check endpoint
  app.get('/health', (req, res) => {
    res.json({
      status: 'healthy',
      service: process.env.SERVICE_NAME,
      timestamp: new Date().toISOString()
    });
  });

  // REST API routes
  app.use('/api/v1/water-control', waterControlRoutes);

  // GraphQL endpoint
  app.use(
    process.env.GRAPHQL_PATH || '/graphql',
    expressMiddleware(server, {
      context: async ({ req }) => {
        // Add authentication context here
        return {
          user: req.headers.authorization ? { /* decoded token */ } : null
        };
      },
    })
  );

  // Initialize database connection
  try {
    await initializeScadaConnection();
    logger.info('SCADA database connection initialized');
  } catch (error) {
    logger.error('Failed to initialize SCADA database:', error);
    // Continue running even if SCADA is not available
  }

  // Initialize Redis connection
  let demandEventSubscriber = null;
  try {
    await redisConfig.createRedisSubscriber();
    logger.info('Redis connection initialized');
    
    // Initialize demand event subscriber
    const orchestratorService = new WaterControlOrchestratorService();
    demandEventSubscriber = new DemandEventSubscriber(
      orchestratorService,
      orchestratorService.demandService
    );
    
    await demandEventSubscriber.subscribeToEvents();
    logger.info('Demand event subscriber initialized');
    
  } catch (error) {
    logger.error('Failed to initialize Redis/Event subscriber:', error);
    logger.warn('Running without Redis event coordination - using pull-based approach only');
  }

  // Start server
  const PORT = process.env.PORT || 4003;
  httpServer.listen(PORT, () => {
    logger.info(`🚀 Water Control BFF Service running at http://localhost:${PORT}`);
    logger.info(`📊 GraphQL endpoint: http://localhost:${PORT}${process.env.GRAPHQL_PATH || '/graphql'}`);
    logger.info(`🔌 WebSocket endpoint: ws://localhost:${PORT}${process.env.SUBSCRIPTION_PATH || '/graphql/ws'}`);
    logger.info(`🔧 REST API endpoint: http://localhost:${PORT}/api/v1/water-control`);
  });

  // Graceful shutdown
  process.on('SIGTERM', async () => {
    logger.info('SIGTERM signal received: closing HTTP server');
    
    httpServer.close(async () => {
      logger.info('HTTP server closed');
      
      // Clean up event subscriber
      if (demandEventSubscriber) {
        await demandEventSubscriber.unsubscribe();
        logger.info('Event subscriber closed');
      }
      
      // Clean up Redis connection
      await redisConfig.disconnect();
      logger.info('Redis connection closed');
      
      await closeConnections();
      await server.stop();
      process.exit(0);
    });
  });
}

// Start the server
startServer().catch((error) => {
  logger.error('Failed to start server:', error);
  process.exit(1);
});