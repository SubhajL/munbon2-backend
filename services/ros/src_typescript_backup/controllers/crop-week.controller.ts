import { Request, Response, NextFunction } from 'express';
import { 
  calculateCropWeek, 
  getCalendarWeekFromCropWeek,
  getCurrentCropWeekInfo,
  calculatePlantingDateFromCropWeek 
} from '@utils/crop-week-calculator';
import { logger } from '@utils/logger';

class CropWeekController {
  /**
   * Calculate current crop week from planting date
   */
  async calculateCurrentCropWeek(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { plantingDate, currentDate } = req.body;
      
      const cropWeek = calculateCropWeek(
        new Date(plantingDate),
        currentDate ? new Date(currentDate) : new Date()
      );

      if (cropWeek === null) {
        res.status(400).json({
          success: false,
          message: 'Current date is before planting date'
        });
        return;
      }

      const calendarInfo = getCalendarWeekFromCropWeek(new Date(plantingDate), cropWeek);

      res.status(200).json({
        success: true,
        data: {
          plantingDate,
          currentDate: currentDate || new Date().toISOString(),
          cropWeek,
          calendarWeek: calendarInfo.calendarWeek,
          calendarYear: calendarInfo.calendarYear
        }
      });
    } catch (error) {
      logger.error('Error calculating crop week', error);
      next(error);
    }
  }

  /**
   * Get crop week info for multiple plots
   */
  async getCropWeeksForPlots(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { plots } = req.body; // Array of {plotId, plantingDate}
      
      const results = plots.map((plot: any) => {
        const info = getCurrentCropWeekInfo(new Date(plot.plantingDate));
        return {
          plotId: plot.plotId,
          plantingDate: plot.plantingDate,
          ...info
        };
      });

      res.status(200).json({
        success: true,
        data: results
      });
    } catch (error) {
      logger.error('Error getting crop weeks for plots', error);
      next(error);
    }
  }

  /**
   * Calculate planting date from current crop week
   */
  async calculatePlantingDate(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { cropWeek, currentDate } = req.body;
      
      const plantingDate = calculatePlantingDateFromCropWeek(
        cropWeek,
        currentDate ? new Date(currentDate) : new Date()
      );

      res.status(200).json({
        success: true,
        data: {
          cropWeek,
          currentDate: currentDate || new Date().toISOString(),
          estimatedPlantingDate: plantingDate.toISOString()
        }
      });
    } catch (error) {
      logger.error('Error calculating planting date', error);
      next(error);
    }
  }
}

export const cropWeekController = new CropWeekController();