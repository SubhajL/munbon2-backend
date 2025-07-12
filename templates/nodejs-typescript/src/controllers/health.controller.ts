import { Request, Response } from 'express';

interface HealthStatus {
  status: 'healthy' | 'unhealthy';
  service: string;
  timestamp: string;
  uptime: number;
  checks?: Record<string, boolean>;
}

export const healthCheck = async (_req: Request, res: Response): Promise<void> => {
  const healthStatus: HealthStatus = {
    status: 'healthy',
    service: process.env.SERVICE_NAME || '{{SERVICE_NAME}}',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
  };

  res.status(200).json(healthStatus);
};

export const readinessCheck = async (_req: Request, res: Response): Promise<void> => {
  // Add readiness checks here (e.g., database connectivity, external service availability)
  const checks = {
    database: true, // Replace with actual database check
    externalService: true, // Replace with actual service check
  };

  const isReady = Object.values(checks).every((check) => check === true);

  const readinessStatus: HealthStatus = {
    status: isReady ? 'healthy' : 'unhealthy',
    service: process.env.SERVICE_NAME || '{{SERVICE_NAME}}',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    checks,
  };

  res.status(isReady ? 200 : 503).json(readinessStatus);
};