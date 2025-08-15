import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import 'express-async-errors';
import sensorMappingRoutes from './api/sensor-mapping.routes';
import dashboardRoutes from './api/dashboard.routes';
import { testConnections } from './config/database';

const app = express();
const PORT = process.env.PORT || 3018;

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Health check
app.get('/health', (req, res) => {
  res.json({ 
    status: 'healthy', 
    service: 'sensor-location-mapping',
    timestamp: new Date().toISOString() 
  });
});

// Routes
app.use('/api/v1', sensorMappingRoutes);
app.use('/api/v1/dashboard', dashboardRoutes);

// Error handling middleware
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  console.error('Error:', err);
  res.status(err.status || 500).json({
    error: err.message || 'Internal server error',
    ...(process.env.NODE_ENV === 'development' && { stack: err.stack })
  });
});

// Start server
async function start() {
  try {
    // Test database connections
    await testConnections();
    
    app.listen(PORT, () => {
      console.log(`🚀 Sensor Location Mapping Service running on port ${PORT}`);
      console.log(`📍 Health check: http://localhost:${PORT}/health`);
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

start();