import { Request, Response, NextFunction } from 'express';
import { etoDataService } from '@services/eto-data.service';
import { logger } from '@utils/logger';

class EToDataController {
  /**
   * Get monthly ETo value for a specific month
   */
  async getMonthlyETo(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { month, station, province } = req.query;

      if (!month) {
        res.status(400).json({
          success: false,
          message: 'Month parameter is required',
        });
        return;
      }

      const monthNum = parseInt(month as string);
      if (monthNum < 1 || monthNum > 12) {
        res.status(400).json({
          success: false,
          message: 'Month must be between 1 and 12',
        });
        return;
      }

      const etoValue = await etoDataService.getMonthlyETo(
        station as string || 'นครราชสีมา',
        province as string || 'นครราชสีมา',
        monthNum
      );

      res.status(200).json({
        success: true,
        data: {
          month: monthNum,
          station: station || 'นครราชสีมา',
          province: province || 'นครราชสีมา',
          etoValue,
          unit: 'mm/month',
        },
      });
    } catch (error) {
      logger.error('Error getting monthly ETo', error);
      next(error);
    }
  }

  /**
   * Get all monthly ETo values for a station
   */
  async getAllMonthlyETo(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { station, province } = req.query;

      const etoData = await etoDataService.getAllMonthlyETo(
        station as string || 'นครราชสีมา',
        province as string || 'นครราชสีมา'
      );

      res.status(200).json({
        success: true,
        data: {
          station: station || 'นครราชสีมา',
          province: province || 'นครราชสีมา',
          monthlyValues: etoData,
          unit: 'mm/month',
        },
      });
    } catch (error) {
      logger.error('Error getting all monthly ETo', error);
      next(error);
    }
  }
}

export const etoDataController = new EToDataController();