import { Request, Response, NextFunction } from 'express';
import { body, param, validationResult } from 'express-validator';
import { AppError } from '../middleware/errorHandler';
import { awdControlService } from '../services/awd-control.service';
import { logger } from '../utils/logger';

export const awdManagementController = {
  /**
   * Initialize AWD control for a field
   */
  initializeField: [
    body('fieldId').isUUID(),
    body('plantingMethod').isIn(['transplanted', 'direct-seeded']).optional(),
    body('startDate').isISO8601(),
    async (req: Request, res: Response, next: NextFunction) => {
      try {
        const errors = validationResult(req);
        if (!errors.isEmpty()) {
          throw new AppError(400, 'Validation error', true, errors.array());
        }

        const { fieldId, plantingMethod, startDate } = req.body;
        
        // Get planting method from GIS if not provided
        const method = plantingMethod || 
          await awdControlService.getPlantingMethodFromGIS(fieldId);
        
        const config = await awdControlService.initializeFieldControl(
          fieldId,
          method,
          new Date(startDate)
        );

        res.json({
          success: true,
          data: config,
          message: 'AWD control initialized successfully'
        });
      } catch (error) {
        next(error);
      }
    }
  ],

  /**
   * Get control decision for a field
   */
  getControlDecision: [
    param('fieldId').isUUID(),
    async (req: Request, res: Response, next: NextFunction) => {
      try {
        const errors = validationResult(req);
        if (!errors.isEmpty()) {
          throw new AppError(400, 'Validation error', true, errors.array());
        }

        const { fieldId } = req.params;
        const decision = await awdControlService.makeControlDecision(fieldId);

        res.json({
          success: true,
          data: decision,
          timestamp: new Date().toISOString()
        });
      } catch (error) {
        next(error);
      }
    }
  ],

  /**
   * Update section start dates
   */
  updateSectionStartDates: [
    body('sectionId').isString(),
    body('startDate').isISO8601(),
    body('fieldIds').isArray().optional(),
    async (req: Request, res: Response, next: NextFunction) => {
      try {
        const errors = validationResult(req);
        if (!errors.isEmpty()) {
          throw new AppError(400, 'Validation error', true, errors.array());
        }

        const { sectionId, startDate, fieldIds } = req.body;
        const startDateObj = new Date(startDate);
        
        // Get all fields in section if fieldIds not provided
        const fields = fieldIds || await getFieldsInSection(sectionId);
        
        const results = await Promise.allSettled(
          fields.map((fieldId: string) => 
            awdControlService.initializeFieldControl(
              fieldId,
              'direct-seeded', // Will be overridden by GIS data
              startDateObj
            )
          )
        );

        const successful = results.filter(r => r.status === 'fulfilled').length;
        const failed = results.filter(r => r.status === 'rejected').length;

        res.json({
          success: true,
          data: {
            sectionId,
            startDate,
            fieldsUpdated: successful,
            fieldsFailed: failed,
            totalFields: fields.length
          },
          message: `Updated ${successful} fields in section ${sectionId}`
        });
      } catch (error) {
        next(error);
      }
    }
  ],

  /**
   * Get AWD schedule for a planting method
   */
  getSchedule: [
    param('plantingMethod').isIn(['transplanted', 'direct-seeded']),
    async (req: Request, res: Response, next: NextFunction) => {
      try {
        const errors = validationResult(req);
        if (!errors.isEmpty()) {
          throw new AppError(400, 'Validation error', true, errors.array());
        }

        const { plantingMethod } = req.params;
        const schedule = plantingMethod === 'transplanted' 
          ? require('../types/awd-control.types').TRANSPLANTED_SCHEDULE
          : require('../types/awd-control.types').DIRECT_SEEDED_SCHEDULE;

        res.json({
          success: true,
          data: schedule
        });
      } catch (error) {
        next(error);
      }
    }
  ]
};

// Helper function to get fields in a section
async function getFieldsInSection(sectionId: string): Promise<string[]> {
  // This would query the GIS data or field management service
  // For now, return empty array
  logger.warn({ sectionId }, 'getFieldsInSection not implemented');
  return [];
}