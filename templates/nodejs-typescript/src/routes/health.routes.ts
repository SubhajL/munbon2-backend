import { Router } from 'express';
import { healthCheck, readinessCheck } from '../controllers/health.controller';

export const healthRouter = Router();

/**
 * @swagger
 * /health:
 *   get:
 *     summary: Health check endpoint
 *     tags: [Health]
 *     responses:
 *       200:
 *         description: Service is healthy
 *       503:
 *         description: Service is unhealthy
 */
healthRouter.get('/', healthCheck);

/**
 * @swagger
 * /health/ready:
 *   get:
 *     summary: Readiness check endpoint
 *     tags: [Health]
 *     responses:
 *       200:
 *         description: Service is ready
 *       503:
 *         description: Service is not ready
 */
healthRouter.get('/ready', readinessCheck);