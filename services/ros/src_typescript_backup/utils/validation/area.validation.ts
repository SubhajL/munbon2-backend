import Joi from 'joi';

const areaTypes = ['project', 'zone', 'section', 'FTO'];

export const areaValidation = {
  createArea: {
    body: Joi.object({
      areaId: Joi.string().required(),
      areaType: Joi.string().valid(...areaTypes).required(),
      areaName: Joi.string().optional(),
      totalAreaRai: Joi.number().positive().required(),
      parentAreaId: Joi.string().optional(),
      aosStation: Joi.string().optional(),
      province: Joi.string().optional(),
    }),
  },

  getAreaById: {
    params: Joi.object({
      areaId: Joi.string().required(),
    }),
  },

  updateArea: {
    params: Joi.object({
      areaId: Joi.string().required(),
    }),
    body: Joi.object({
      areaName: Joi.string().optional(),
      totalAreaRai: Joi.number().positive().optional(),
      parentAreaId: Joi.string().optional(),
      aosStation: Joi.string().optional(),
      province: Joi.string().optional(),
    }).min(1),
  },

  deleteArea: {
    params: Joi.object({
      areaId: Joi.string().required(),
    }),
  },

  getAreasByType: {
    params: Joi.object({
      areaType: Joi.string().valid(...areaTypes).required(),
    }),
  },

  getChildAreas: {
    params: Joi.object({
      areaId: Joi.string().required(),
    }),
  },

  getAreaHierarchy: {
    params: Joi.object({
      projectId: Joi.string().required(),
    }),
  },

  calculateTotalArea: {
    params: Joi.object({
      areaId: Joi.string().required(),
    }),
  },

  importAreas: {
    body: Joi.object({
      areas: Joi.array().items(
        Joi.object({
          areaId: Joi.string().required(),
          areaType: Joi.string().valid(...areaTypes).required(),
          areaName: Joi.string().optional(),
          totalAreaRai: Joi.number().positive().required(),
          parentAreaId: Joi.string().optional(),
          aosStation: Joi.string().optional(),
          province: Joi.string().optional(),
        })
      ).min(1).required(),
    }),
  },
};