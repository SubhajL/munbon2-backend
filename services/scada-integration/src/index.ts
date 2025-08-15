import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import 'express-async-errors';
import { testScadaConnection, closeConnections } from './config/database';
import { healthMonitorService } from './services/health-monitor.service';
import { gateCommandService } from './services/gate-command.service';
import healthRoutes from './routes/health.routes';
import commandRoutes from './routes/command.routes';

const app = express();
const PORT = process.env.PORT || 3015;

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Request logging middleware
app.use((req, res, next) => {
  console.log(`${new Date().toISOString()} ${req.method} ${req.path}`);
  next();
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ 
    status: 'healthy', 
    service: 'scada-integration',
    version: '1.0.0',
    timestamp: new Date().toISOString() 
  });
});

// API routes
app.use('/api/v1/scada', healthRoutes);
app.use('/api/v1/scada', commandRoutes);

// 404 handler
app.use((req, res) => {
  res.status(404).json({ 
    message: 'Route not found',
    path: req.path 
  });
});

// Error handling middleware
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  console.error('Error:', err);
  res.status(err.status || 500).json({
    message: err.message || 'Internal server error',
    ...(process.env.NODE_ENV === 'development' && { stack: err.stack })
  });
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, shutting down gracefully...');
  healthMonitorService.stopMonitoring();
  gateCommandService.stopMonitoring();
  await closeConnections();
  process.exit(0);
});

process.on('SIGINT', async () => {
  console.log('SIGINT received, shutting down gracefully...');
  healthMonitorService.stopMonitoring();
  gateCommandService.stopMonitoring();
  await closeConnections();
  process.exit(0);
});

// Start server
async function start() {
  try {
    // Test database connection
    const dbConnected = await testScadaConnection();
    if (!dbConnected) {
      throw new Error('Failed to connect to SCADA database');
    }

    // Start monitoring services
    healthMonitorService.startMonitoring();
    gateCommandService.startMonitoring();

    app.listen(PORT, () => {
      console.log(`🚀 SCADA Integration Service running on port ${PORT}`);
      console.log(`📡 Health check: http://localhost:${PORT}/health`);
      console.log(`📊 SCADA health: http://localhost:${PORT}/api/v1/scada/health`);
      console.log(`🎛️  Gate commands: http://localhost:${PORT}/api/v1/scada/command/send`);
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

start();