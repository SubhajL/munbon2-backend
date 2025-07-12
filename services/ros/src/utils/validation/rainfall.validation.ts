import Joi from 'joi';

export const rainfallValidation = {
  getWeeklyRainfall: {
    params: Joi.object({
      areaId: Joi.string().required(),
    }),
    query: Joi.object({
      weekStartDate: Joi.date().iso().optional(),
    }),
  },

  addRainfall: {
    body: Joi.object({
      areaId: Joi.string().required(),
      date: Joi.date().required(),
      rainfallMm: Joi.number().min(0).required(),
      effectiveRainfallMm: Joi.number().min(0).optional(),
      source: Joi.string().valid('manual', 'weather_api', 'sensor').required(),
    }),
  },

  importRainfall: {
    body: Joi.object({
      rainfallData: Joi.array().items(
        Joi.object({
          areaId: Joi.string().required(),
          date: Joi.date().required(),
          rainfallMm: Joi.number().min(0).required(),
          effectiveRainfallMm: Joi.number().min(0).optional(),
          source: Joi.string().valid('manual', 'weather_api', 'sensor').required(),
        })
      ).min(1).required(),
    }),
  },

  getRainfallHistory: {
    params: Joi.object({
      areaId: Joi.string().required(),
    }),
    query: Joi.object({
      startDate: Joi.date().iso().required(),
      endDate: Joi.date().iso().min(Joi.ref('startDate')).required(),
    }),
  },

  updateRainfall: {
    params: Joi.object({
      areaId: Joi.string().required(),
      date: Joi.date().required(),
    }),
    body: Joi.object({
      rainfallMm: Joi.number().min(0).optional(),
      effectiveRainfallMm: Joi.number().min(0).optional(),
      source: Joi.string().valid('manual', 'weather_api', 'sensor').optional(),
    }).min(1),
  },

  deleteRainfall: {
    params: Joi.object({
      areaId: Joi.string().required(),
      date: Joi.date().required(),
    }),
  },

  getRainfallStatistics: {
    params: Joi.object({
      areaId: Joi.string().required(),
    }),
    query: Joi.object({
      year: Joi.number().integer().min(2000).max(2100).optional(),
      month: Joi.number().integer().min(1).max(12).optional(),
    }),
  },
};