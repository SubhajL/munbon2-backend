const express = require('express');
const router = express.Router();
const logger = require('../utils/logger');

module.exports = (controller) => {
  // Health check
  router.get('/health', (req, res) => {
    res.json({
      status: 'healthy',
      service: 'smartfarm-water-control',
      timestamp: new Date().toISOString()
    });
  });

  // Get status of all plots
  router.get('/plots', async (req, res) => {
    try {
      const statuses = await Promise.all(
        controller.config.plots.map((plot) =>
          controller.getPlotStatus(plot.plotId)
        )
      );

      res.json({
        success: true,
        data: statuses
      });
    } catch (error) {
      logger.error({ error }, 'Failed to get plot statuses');
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  });

  // Get status of specific plot
  router.get('/plots/:plotId', async (req, res) => {
    try {
      const { plotId } = req.params;
      const status = await controller.getPlotStatus(plotId);

      res.json({
        success: true,
        data: status
      });
    } catch (error) {
      logger.error(
        { error, plotId: req.params.plotId },
        'Failed to get plot status'
      );
      res.status(error.message.includes('not found') ? 404 : 500).json({
        success: false,
        error: error.message
      });
    }
  });

  // Trigger control loop manually
  router.post('/control/run', async (req, res) => {
    try {
      await controller.runControlLoop();

      res.json({
        success: true,
        message: 'Control loop executed successfully'
      });
    } catch (error) {
      logger.error({ error }, 'Failed to run control loop');
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  });

  // Trigger planning loop manually
  router.post('/planning/run', async (req, res) => {
    try {
      await controller.runPlanningLoop();

      res.json({
        success: true,
        message: 'Planning loop executed successfully'
      });
    } catch (error) {
      logger.error({ error }, 'Failed to run planning loop');
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  });

  // Get water balance for a plot
  router.get('/plots/:plotId/balance', async (req, res) => {
    try {
      const { plotId } = req.params;
      const { date } = req.query;

      const targetDate = date ? new Date(date) : new Date();
      const balance = await controller.waterBalance.calculateDailyBalance(
        plotId,
        targetDate
      );

      res.json({
        success: true,
        data: balance
      });
    } catch (error) {
      logger.error(
        { error, plotId: req.params.plotId },
        'Failed to get water balance'
      );
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  });

  // Get water usage metrics
  router.get('/metrics/usage', async (req, res) => {
    try {
      const { startDate, endDate } = req.query;

      if (!startDate || !endDate) {
        return res.status(400).json({
          success: false,
          error: 'startDate and endDate are required'
        });
      }

      const metrics = await controller.waterBalance.aggregateUsageMetrics(
        new Date(startDate),
        new Date(endDate)
      );

      res.json({
        success: true,
        data: metrics
      });
    } catch (error) {
      logger.error({ error }, 'Failed to get usage metrics');
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  });

  // Manual valve control
  router.post('/plots/:plotId/valve', async (req, res) => {
    try {
      const { plotId } = req.params;
      const { action, reason = 'Manual control' } = req.body;

      if (!['ON', 'OFF'].includes(action)) {
        return res.status(400).json({
          success: false,
          error: 'Invalid action. Must be ON or OFF'
        });
      }

      const level = action === 'ON' ? 1 : 0;
      await controller.valveCommand.sendValveCommand(
        plotId,
        level,
        new Date(),
        reason
      );

      // Track manual irrigation
      if (action === 'ON') {
        const plotConfig = controller.config.plots.find(
          (p) => p.plotId === plotId
        );
        controller.waterBalance.startIrrigation(
          plotId,
          plotConfig.valveName,
          'MANUAL',
          0
        );
      } else {
        await controller.waterBalance.stopIrrigation(plotId);
      }

      res.json({
        success: true,
        message: `Valve ${action} command sent for plot ${plotId}`
      });
    } catch (error) {
      logger.error(
        { error, plotId: req.params.plotId },
        'Failed to control valve'
      );
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  });

  // Update daily progress manually
  router.post('/progress/update', async (req, res) => {
    try {
      await controller.updateDailyProgress();

      res.json({
        success: true,
        message: 'Daily progress updated successfully'
      });
    } catch (error) {
      logger.error({ error }, 'Failed to update daily progress');
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  });

  return router;
};
