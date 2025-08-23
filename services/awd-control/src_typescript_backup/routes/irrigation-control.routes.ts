import { Router, Request, Response } from 'express';
import { body, param, query, validationResult } from 'express-validator';
import { awdControlServiceV2 } from '../services/awd-control-v2.service';
import { irrigationControllerService } from '../services/irrigation-controller.service';
import { irrigationLearningService } from '../services/irrigation-learning.service';
import { logger } from '../utils/logger';

const router = Router();

/**
 * Start irrigation with water level-based control
 */
router.post('/fields/:fieldId/irrigation/start',
  [
    param('fieldId').isUUID().withMessage('Invalid field ID'),
    body('targetLevelCm').isFloat({ min: 1, max: 20 }).withMessage('Target level must be between 1-20cm'),
    body('toleranceCm').optional().isFloat({ min: 0.1, max: 2 }).withMessage('Tolerance must be between 0.1-2cm'),
    body('maxDurationHours').optional().isFloat({ min: 1, max: 48 }).withMessage('Max duration must be between 1-48 hours'),
    body('emergencyStopLevel').optional().isFloat({ min: 10, max: 25 }).withMessage('Emergency stop level must be between 10-25cm')
  ],
  async (req: Request, res: Response) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { fieldId } = req.params;

      // Make control decision
      const decision = await awdControlServiceV2.makeControlDecision(fieldId);
      
      if (decision.action !== 'start_irrigation') {
        return res.status(409).json({
          success: false,
          reason: decision.reason,
          decision
        });
      }

      // Execute irrigation with custom parameters if provided
      const customDecision = {
        ...decision,
        targetWaterLevel: req.body.targetLevelCm || decision.targetWaterLevel,
        maxDuration: (req.body.maxDurationHours || 24) * 60,
        emergencyStopLevel: req.body.emergencyStopLevel || 15
      };

      const result = await awdControlServiceV2.executeIrrigation(fieldId, customDecision);

      res.json({
        success: true,
        scheduleId: result.scheduleId,
        status: result.status,
        method: result.method,
        prediction: decision.metadata?.prediction,
        recommendation: decision.metadata?.recommendation
      });

    } catch (error) {
      logger.error({ error, fieldId: req.params.fieldId }, 'Failed to start irrigation');
      res.status(500).json({ error: 'Failed to start irrigation' });
    }
  }
);

/**
 * Get irrigation status with real-time monitoring data
 */
router.get('/fields/:fieldId/irrigation/status',
  [
    param('fieldId').isUUID().withMessage('Invalid field ID'),
    query('includeHistory').optional().isBoolean().withMessage('includeHistory must be boolean')
  ],
  async (req: Request, res: Response) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { fieldId } = req.params;
      const status = await awdControlServiceV2.getIrrigationStatus(fieldId);

      if (req.query.includeHistory === 'true' && !status.active) {
        // Get recent irrigation history
        const history = await irrigationLearningService.analyzeFieldPatterns(fieldId);
        return res.json({
          ...status,
          history
        });
      }

      res.json(status);

    } catch (error) {
      logger.error({ error, fieldId: req.params.fieldId }, 'Failed to get irrigation status');
      res.status(500).json({ error: 'Failed to get irrigation status' });
    }
  }
);

/**
 * Stop active irrigation
 */
router.post('/fields/:fieldId/irrigation/stop',
  [
    param('fieldId').isUUID().withMessage('Invalid field ID'),
    body('reason').isString().notEmpty().withMessage('Reason is required')
  ],
  async (req: Request, res: Response) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { fieldId } = req.params;
      const { reason } = req.body;

      const result = await awdControlServiceV2.stopIrrigation(fieldId, reason);

      res.json(result);

    } catch (error) {
      logger.error({ error, fieldId: req.params.fieldId }, 'Failed to stop irrigation');
      res.status(500).json({ error: 'Failed to stop irrigation' });
    }
  }
);

/**
 * Get irrigation recommendation based on AI/ML
 */
router.get('/fields/:fieldId/irrigation/recommendation',
  [
    param('fieldId').isUUID().withMessage('Invalid field ID'),
    query('targetLevel').optional().isFloat({ min: 1, max: 20 }).withMessage('Invalid target level')
  ],
  async (req: Request, res: Response) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { fieldId } = req.params;
      const targetLevel = req.query.targetLevel ? parseFloat(req.query.targetLevel as string) : 10;

      const recommendation = await irrigationControllerService.getIrrigationRecommendation(
        fieldId,
        targetLevel
      );

      res.json(recommendation);

    } catch (error) {
      logger.error({ error, fieldId: req.params.fieldId }, 'Failed to get recommendation');
      res.status(500).json({ error: 'Failed to get recommendation' });
    }
  }
);

/**
 * Get irrigation performance analytics
 */
router.get('/fields/:fieldId/irrigation/analytics',
  [
    param('fieldId').isUUID().withMessage('Invalid field ID'),
    query('days').optional().isInt({ min: 1, max: 365 }).withMessage('Days must be between 1-365')
  ],
  async (req: Request, res: Response) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { fieldId } = req.params;
      const days = req.query.days ? parseInt(req.query.days as string) : 30;

      // Get performance patterns
      const patterns = await irrigationLearningService.analyzeFieldPatterns(fieldId);

      // Get optimal parameters based on learning
      const optimalParams = await irrigationLearningService.getOptimalParameters(fieldId);

      res.json({
        fieldId,
        period: `Last ${days} days`,
        patterns,
        optimalParameters: optimalParams,
        insights: generateInsights(patterns, optimalParams)
      });

    } catch (error) {
      logger.error({ error, fieldId: req.params.fieldId }, 'Failed to get analytics');
      res.status(500).json({ error: 'Failed to get analytics' });
    }
  }
);

/**
 * Predict irrigation performance
 */
router.post('/fields/:fieldId/irrigation/predict',
  [
    param('fieldId').isUUID().withMessage('Invalid field ID'),
    body('initialLevel').isFloat({ min: 0, max: 20 }).withMessage('Invalid initial level'),
    body('targetLevel').isFloat({ min: 1, max: 20 }).withMessage('Invalid target level'),
    body('temperature').optional().isFloat({ min: 0, max: 50 }).withMessage('Invalid temperature'),
    body('humidity').optional().isFloat({ min: 0, max: 100 }).withMessage('Invalid humidity')
  ],
  async (req: Request, res: Response) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { fieldId } = req.params;
      
      const prediction = await irrigationLearningService.predictIrrigationPerformance(
        fieldId,
        {
          initialLevel: req.body.initialLevel,
          targetLevel: req.body.targetLevel,
          soilType: req.body.soilType || 'loam',
          temperature: req.body.temperature || 28,
          humidity: req.body.humidity || 70,
          lastIrrigationDays: req.body.lastIrrigationDays || 7,
          concurrentIrrigations: req.body.concurrentIrrigations || 0,
          season: req.body.season || getCurrentSeason()
        }
      );

      res.json(prediction);

    } catch (error) {
      logger.error({ error, fieldId: req.params.fieldId }, 'Failed to predict performance');
      res.status(500).json({ error: 'Failed to predict performance' });
    }
  }
);

/**
 * Get active irrigations across all fields
 */
router.get('/irrigation/active',
  [
    query('limit').optional().isInt({ min: 1, max: 100 }).withMessage('Limit must be between 1-100'),
    query('offset').optional().isInt({ min: 0 }).withMessage('Invalid offset')
  ],
  async (req: Request, res: Response) => {
    try {
      const limit = req.query.limit ? parseInt(req.query.limit as string) : 20;
      const offset = req.query.offset ? parseInt(req.query.offset as string) : 0;

      // This would be implemented in the service
      // For now, returning a placeholder
      res.json({
        active: [],
        total: 0,
        limit,
        offset
      });

    } catch (error) {
      logger.error({ error }, 'Failed to get active irrigations');
      res.status(500).json({ error: 'Failed to get active irrigations' });
    }
  }
);

/**
 * Helper function to generate insights
 */
function generateInsights(patterns: any[], optimalParams: any): string[] {
  const insights: string[] = [];

  // Analyze patterns for insights
  patterns.forEach(pattern => {
    if (pattern.pattern === 'high_flow_variability' && pattern.impact === 'negative') {
      insights.push('High flow rate variability detected - consider maintenance');
    }
    if (pattern.pattern === 'improving_efficiency' && pattern.impact === 'positive') {
      insights.push('Irrigation efficiency has improved recently');
    }
    if (pattern.pattern === 'frequent_anomalies' && pattern.frequency > 10) {
      insights.push('Frequent anomalies detected - system review recommended');
    }
  });

  // Add parameter insights
  if (optimalParams.sensorCheckInterval < 300) {
    insights.push('Fast sensor check interval recommended due to quick irrigation times');
  }
  if (optimalParams.toleranceCm < 1.0) {
    insights.push('Tight tolerance recommended due to past anomalies');
  }

  return insights;
}

/**
 * Get current season helper
 */
function getCurrentSeason(): string {
  const month = new Date().getMonth();
  if (month >= 10 || month <= 1) return 'dry';
  if (month >= 5 && month <= 9) return 'wet';
  return 'normal';
}

export default router;