const express = require('express');
const router = express.Router();
const waterControlService = require('../services/water-control-data.service');
const { validateRequest } = require('../middleware/validate');
const Joi = require('joi');

// Validation schemas
const weeklyScheduleSchema = Joi.object({
  zone_id: Joi.string().pattern(/^\d{2}-\d{2}$/).required(),
  week_start: Joi.date().iso(),
  week_end: Joi.date().iso()
});

const progressUpdateSchema = Joi.object({
  progress_id: Joi.number().integer().required(),
  actual_start_datetime: Joi.date().iso(),
  actual_end_datetime: Joi.date().iso(),
  actual_flow_m3s: Joi.number(),
  actual_volume_m3: Joi.number(),
  execution_status: Joi.string().valid('pending', 'executing', 'completed', 'failed', 'cancelled'),
  execution_notes: Joi.string()
});

// GET /api/v1/water-control/zones/:zoneId/weekly-schedule
router.get('/zones/:zoneId/weekly-schedule', 
  validateRequest({ params: Joi.object({ zoneId: Joi.string().pattern(/^\d{2}-\d{2}$/).required() }) }),
  async (req, res, next) => {
    try {
      const { zoneId } = req.params;
      const { week_start, week_end } = req.query;

      const schedule = await waterControlService.getWeeklySchedule(zoneId, {
        weekStart: week_start,
        weekEnd: week_end
      });

      res.json({
        success: true,
        data: schedule
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/v1/water-control/zones/:zoneId/current-week
router.get('/zones/:zoneId/current-week', 
  validateRequest({ params: Joi.object({ zoneId: Joi.string().pattern(/^\d{2}-\d{2}$/).required() }) }),
  async (req, res, next) => {
    try {
      const { zoneId } = req.params;
      
      const currentWeek = await waterControlService.getCurrentWeekSchedule(zoneId);

      res.json({
        success: true,
        data: currentWeek
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/v1/water-control/gates/:gateId/schedule
router.get('/gates/:gateId/schedule',
  validateRequest({ params: Joi.object({ gateId: Joi.string().required() }) }),
  async (req, res, next) => {
    try {
      const { gateId } = req.params;
      const { week_start, week_end, status } = req.query;

      const gateSchedule = await waterControlService.getGateSchedule(gateId, {
        weekStart: week_start,
        weekEnd: week_end,
        status
      });

      res.json({
        success: true,
        data: gateSchedule
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/v1/water-control/sections/:sectionId/schedule
router.get('/sections/:sectionId/schedule',
  validateRequest({ params: Joi.object({ sectionId: Joi.string().pattern(/^\d{2}-\d{2}-\d{2}-\d{2}$/).required() }) }),
  async (req, res, next) => {
    try {
      const { sectionId } = req.params;
      const { week_start, include_gate_details } = req.query;

      const sectionSchedule = await waterControlService.getSectionSchedule(sectionId, {
        weekStart: week_start,
        includeGateDetails: include_gate_details === 'true'
      });

      res.json({
        success: true,
        data: sectionSchedule
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/v1/water-control/job-orders/manual-gates
router.get('/job-orders/manual-gates',
  async (req, res, next) => {
    try {
      const { zone_id, status, date_from, date_to } = req.query;

      const jobOrders = await waterControlService.getManualGateJobOrders({
        zoneId: zone_id,
        status,
        dateFrom: date_from,
        dateTo: date_to
      });

      res.json({
        success: true,
        data: jobOrders
      });
    } catch (error) {
      next(error);
    }
  }
);

// PUT /api/v1/water-control/progress/:progressId
router.put('/progress/:progressId',
  validateRequest({ 
    params: Joi.object({ progressId: Joi.number().integer().required() }),
    body: progressUpdateSchema
  }),
  async (req, res, next) => {
    try {
      const { progressId } = req.params;
      const updateData = req.body;

      const updated = await waterControlService.updateProgress(progressId, updateData);

      res.json({
        success: true,
        data: updated
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/v1/water-control/monitoring/weekly/:weeklyControlId
router.get('/monitoring/weekly/:weeklyControlId',
  validateRequest({ params: Joi.object({ weeklyControlId: Joi.number().integer().required() }) }),
  async (req, res, next) => {
    try {
      const { weeklyControlId } = req.params;
      const { date } = req.query;

      const monitoring = await waterControlService.getWeeklyMonitoring(weeklyControlId, date);

      res.json({
        success: true,
        data: monitoring
      });
    } catch (error) {
      next(error);
    }
  }
);

// POST /api/v1/water-control/recommendations
router.post('/recommendations',
  validateRequest({
    body: Joi.object({
      weekly_control_id: Joi.number().integer().required(),
      progress_id: Joi.number().integer(),
      recommendation_type: Joi.string().required(),
      severity: Joi.string().valid('low', 'medium', 'high', 'critical').required(),
      current_value: Joi.number(),
      recommended_value: Joi.number(),
      reason: Joi.string().required()
    })
  }),
  async (req, res, next) => {
    try {
      const recommendation = await waterControlService.createRecommendation(req.body);

      res.json({
        success: true,
        data: recommendation
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/v1/water-control/status/overview
router.get('/status/overview',
  async (req, res, next) => {
    try {
      const { zone_id } = req.query;

      const overview = await waterControlService.getStatusOverview(zone_id);

      res.json({
        success: true,
        data: overview
      });
    } catch (error) {
      next(error);
    }
  }
);

module.exports = router;