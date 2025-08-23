import { Router } from 'express';
import { fieldsRouter } from './fields.routes';
import { sensorsRouter } from './sensors.routes';
import { irrigationRouter } from './irrigation.routes';
import { analyticsRouter } from './analytics.routes';
import { schedulesRouter } from './schedules.routes';
import { awdManagementRouter } from './awd-management.routes';
import irrigationControlRouter from './irrigation-control.routes';
import monitoringDashboardRouter from './monitoring-dashboard.routes';

export const awdRouter = Router();

// Mount sub-routers
awdRouter.use('/fields', fieldsRouter);
awdRouter.use('/sensors', sensorsRouter);
awdRouter.use('/irrigation', irrigationRouter);
awdRouter.use('/analytics', analyticsRouter);
awdRouter.use('/schedules', schedulesRouter);
awdRouter.use('/management', awdManagementRouter);

// New water level-based control routes
awdRouter.use('/control', irrigationControlRouter);
awdRouter.use('/monitoring', monitoringDashboardRouter);

// AWD system-wide endpoints
awdRouter.get('/status', async (_req, res) => {
  // System-wide AWD status
  res.json({
    status: 'operational',
    activeFields: 0,
    totalWaterSaved: 0,
    timestamp: new Date().toISOString(),
  });
});

awdRouter.get('/recommendations', async (_req, res) => {
  // AWD recommendations based on current conditions
  res.json({
    recommendations: [],
    timestamp: new Date().toISOString(),
  });
});