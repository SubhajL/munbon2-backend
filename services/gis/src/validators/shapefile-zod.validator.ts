import { z } from 'zod';

export const shapeFileUploadValidator = z.object({
  body: z.object({
    waterDemandMethod: z.enum(['RID-MS', 'ROS', 'AWD'])
      .default('RID-MS')
      .describe('Water demand calculation method'),
    
    processingInterval: z.enum(['daily', 'weekly', 'bi-weekly'])
      .default('weekly')
      .describe('Processing interval for water demand calculations'),
    
    zone: z.string()
      .regex(/^Zone\d+$/)
      .optional()
      .describe('Zone identifier (e.g., Zone1, Zone2)'),
    
    description: z.string()
      .max(500)
      .optional()
      .describe('Description of the shape file upload'),
    
    metadata: z.record(z.any())
      .optional()
      .describe('Additional metadata for the upload'),
  }),
  query: z.object({}).optional(),
  params: z.object({}).optional(),
});