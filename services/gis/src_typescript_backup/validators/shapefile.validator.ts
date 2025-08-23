import Joi from 'joi';

export const shapeFileUploadValidator = Joi.object({
  waterDemandMethod: Joi.string()
    .valid('RID-MS', 'ROS', 'AWD')
    .default('RID-MS')
    .description('Water demand calculation method'),
  
  processingInterval: Joi.string()
    .valid('daily', 'weekly', 'bi-weekly')
    .default('weekly')
    .description('Processing interval for water demand calculations'),
  
  zone: Joi.string()
    .pattern(/^Zone\d+$/)
    .description('Zone identifier (e.g., Zone1, Zone2)'),
  
  description: Joi.string()
    .max(500)
    .description('Description of the shape file upload'),
  
  metadata: Joi.object()
    .description('Additional metadata for the upload'),
}).options({ stripUnknown: true });