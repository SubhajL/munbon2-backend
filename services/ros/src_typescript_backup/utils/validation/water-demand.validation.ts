import Joi from 'joi';

const cropTypes = ['rice', 'corn', 'sugarcane'];
const areaTypes = ['project', 'zone', 'section', 'FTO'];

export const waterDemandValidation = {
  calculateWaterDemand: {
    body: Joi.object({
      areaId: Joi.string().required(),
      cropType: Joi.string().valid(...cropTypes).required(),
      areaType: Joi.string().valid(...areaTypes).required(),
      areaRai: Joi.number().positive().required(),
      cropWeek: Joi.number().integer().min(1).required(),
      calendarWeek: Joi.number().integer().min(1).max(53).required(),
      calendarYear: Joi.number().integer().min(2024).max(2050).required(),
      effectiveRainfall: Joi.number().min(0).optional(),
      waterLevel: Joi.number().min(0).optional(),
    }),
  },

  calculateSeasonalWaterDemand: {
    body: Joi.object({
      areaId: Joi.string().required(),
      areaType: Joi.string().valid(...areaTypes).required(),
      areaRai: Joi.number().positive().required(),
      cropType: Joi.string().valid(...cropTypes).required(),
      plantingDate: Joi.date().required(),
      includeRainfall: Joi.boolean().optional(),
    }),
  },

  getWaterDemandByCropWeek: {
    params: Joi.object({
      areaId: Joi.string().required(),
    }),
    query: Joi.object({
      cropWeek: Joi.number().integer().min(1).required(),
    }),
  },

  getSeasonalWaterDemandByWeek: {
    params: Joi.object({
      areaId: Joi.string().required(),
    }),
    query: Joi.object({
      startDate: Joi.date().required(),
      endDate: Joi.date().min(Joi.ref('startDate')).required(),
    }),
  },

  getWaterDemandSummary: {
    params: Joi.object({
      areaType: Joi.string().valid(...areaTypes).required(),
    }),
    query: Joi.object({
      areaId: Joi.string().optional(),
      startDate: Joi.date().required(),
      endDate: Joi.date().min(Joi.ref('startDate')).required(),
    }),
  },
};