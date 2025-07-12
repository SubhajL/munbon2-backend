import express from 'express';
import { config } from 'dotenv';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import { errorHandler } from './middleware/error.middleware';
import moistureRoutes from './routes/moisture.routes';
import healthRoutes from './routes/health.routes';
import { displayTunnelInfo, tunnelConfig } from './config/tunnel.config';

// Load environment variables
config();

const app = express();
const PORT = process.env.PORT || 3005;

// Middleware
app.use(helmet());
app.use(cors());
app.use(morgan('combined'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Routes
app.use('/api/v1/moisture', moistureRoutes);
app.use('/health', healthRoutes);

// Telemetry endpoint for moisture sensors (legacy support)
app.post('/api/v1/:token/telemetry', (req, res) => {
  // Forward to sensor-data service for processing
  // This is a placeholder - actual implementation would forward to sensor-data service
  console.log(`Received telemetry from token: ${req.params.token}`, req.body);
  res.json({ status: 'received', timestamp: new Date() });
});

// Error handling
app.use(errorHandler);

// Start server
app.listen(PORT, () => {
  console.log(`Moisture monitoring service running on port ${PORT}`);
  
  // Display tunnel configuration if enabled
  if (process.env.TUNNEL_ENABLED === 'true') {
    displayTunnelInfo();
  }
});