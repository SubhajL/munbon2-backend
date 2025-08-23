import Joi from 'joi';

export const waterLevelValidation = {
  getCurrentLevel: {
    params: Joi.object({
      areaId: Joi.string().required(),
    }),
  },

  addWaterLevel: {
    body: Joi.object({
      areaId: Joi.string().required(),
      measurementDate: Joi.date().required(),
      measurementTime: Joi.string().pattern(/^([01]\d|2[0-3]):([0-5]\d)$/).optional(), // HH:MM format
      waterLevelM: Joi.number().required(),
      referenceLevel: Joi.string().valid('MSL', 'local_datum', 'relative').optional(),
      source: Joi.string().valid('manual', 'sensor', 'scada').required(),
      sensorId: Joi.string().optional(),
    }),
  },

  importWaterLevels: {
    body: Joi.object({
      waterLevels: Joi.array().items(
        Joi.object({
          areaId: Joi.string().required(),
          measurementDate: Joi.date().required(),
          measurementTime: Joi.string().pattern(/^([01]\d|2[0-3]):([0-5]\d)$/).optional(),
          waterLevelM: Joi.number().required(),
          referenceLevel: Joi.string().valid('MSL', 'local_datum', 'relative').optional(),
          source: Joi.string().valid('manual', 'sensor', 'scada').required(),
          sensorId: Joi.string().optional(),
        })
      ).min(1).required(),
    }),
  },

  getWaterLevelHistory: {
    params: Joi.object({
      areaId: Joi.string().required(),
    }),
    query: Joi.object({
      startDate: Joi.date().iso().required(),
      endDate: Joi.date().iso().min(Joi.ref('startDate')).required(),
      source: Joi.string().valid('manual', 'sensor', 'scada').optional(),
    }),
  },

  updateWaterLevel: {
    params: Joi.object({
      id: Joi.number().integer().positive().required(),
    }),
    body: Joi.object({
      waterLevelM: Joi.number().optional(),
      referenceLevel: Joi.string().valid('MSL', 'local_datum', 'relative').optional(),
      source: Joi.string().valid('manual', 'sensor', 'scada').optional(),
      sensorId: Joi.string().optional(),
    }).min(1),
  },

  deleteWaterLevel: {
    params: Joi.object({
      id: Joi.number().integer().positive().required(),
    }),
  },

  getWaterLevelStatistics: {
    params: Joi.object({
      areaId: Joi.string().required(),
    }),
    query: Joi.object({
      period: Joi.string().valid('daily', 'weekly', 'monthly', 'yearly').default('monthly'),
      year: Joi.number().integer().min(2000).max(2100).optional(),
      month: Joi.number().integer().min(1).max(12).optional(),
    }),
  },

  getWaterLevelTrends: {
    params: Joi.object({
      areaId: Joi.string().required(),
    }),
    query: Joi.object({
      days: Joi.number().integer().min(7).max(365).default(30),
    }),
  },
};