import { Request, Response, NextFunction } from 'express';
import { kcDataService } from '@services/kc-data.service';
import { CropType } from '@types/index';
import { logger } from '@utils/logger';

class KcDataController {
  /**
   * Get Kc value for specific crop and week
   */
  async getKcValue(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { cropType, week } = req.params;
      const cropWeek = parseInt(week);

      if (isNaN(cropWeek) || cropWeek < 1) {
        res.status(400).json({
          success: false,
          message: 'Invalid week number',
        });
        return;
      }

      const kcValue = await kcDataService.getKcValue(cropType as CropType, cropWeek);

      res.status(200).json({
        success: true,
        data: {
          cropType,
          cropWeek,
          kcValue,
        },
      });
    } catch (error) {
      logger.error('Error getting Kc value', error);
      next(error);
    }
  }

  /**
   * Get all Kc values for a crop type
   */
  async getAllKcValues(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { cropType } = req.params;

      const kcData = await kcDataService.getAllKcValues(cropType as CropType);
      const totalWeeks = await kcDataService.getTotalCropWeeks(cropType as CropType);

      res.status(200).json({
        success: true,
        data: {
          cropType,
          totalWeeks,
          weeklyValues: kcData,
        },
      });
    } catch (error) {
      logger.error('Error getting all Kc values', error);
      next(error);
    }
  }

  /**
   * Get crop summary
   */
  async getCropSummary(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const summary = await kcDataService.getCropSummary();

      res.status(200).json({
        success: true,
        data: summary,
      });
    } catch (error) {
      logger.error('Error getting crop summary', error);
      next(error);
    }
  }
}

export const kcDataController = new KcDataController();