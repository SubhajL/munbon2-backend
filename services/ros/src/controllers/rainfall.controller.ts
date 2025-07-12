import { Request, Response, NextFunction } from 'express';
import { rainfallService } from '@services/rainfall.service';
import { logger } from '@utils/logger';

class RainfallController {
  /**
   * Get weekly effective rainfall
   */
  async getWeeklyEffectiveRainfall(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaId } = req.params;
      const { weekStartDate } = req.query;
      
      const effectiveRainfall = await rainfallService.getWeeklyEffectiveRainfall(
        areaId,
        weekStartDate ? new Date(weekStartDate as string) : new Date()
      );

      res.status(200).json({
        success: true,
        data: {
          areaId,
          weekStartDate: weekStartDate || new Date().toISOString().split('T')[0],
          effectiveRainfallMm: effectiveRainfall,
        },
      });
    } catch (error) {
      logger.error('Error getting weekly effective rainfall', error);
      next(error);
    }
  }

  /**
   * Add rainfall data
   */
  async addRainfallData(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const rainfallData = req.body;
      const result = await rainfallService.addRainfallData(rainfallData);

      res.status(201).json({
        success: true,
        data: result,
      });
    } catch (error) {
      logger.error('Error adding rainfall data', error);
      next(error);
    }
  }

  /**
   * Import bulk rainfall data
   */
  async importRainfallData(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { rainfallData } = req.body;
      const result = await rainfallService.importRainfallData(rainfallData);

      res.status(200).json({
        success: true,
        data: result,
      });
    } catch (error) {
      logger.error('Error importing rainfall data', error);
      next(error);
    }
  }

  /**
   * Get rainfall history
   */
  async getRainfallHistory(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaId } = req.params;
      const { startDate, endDate } = req.query;

      const history = await rainfallService.getRainfallHistory(
        areaId,
        new Date(startDate as string),
        new Date(endDate as string)
      );

      res.status(200).json({
        success: true,
        data: history,
        count: history.length,
      });
    } catch (error) {
      logger.error('Error getting rainfall history', error);
      next(error);
    }
  }

  /**
   * Update rainfall data
   */
  async updateRainfallData(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaId, date } = req.params;
      const updates = req.body;

      const result = await rainfallService.updateRainfallData(
        areaId,
        new Date(date),
        updates
      );

      if (!result) {
        res.status(404).json({
          success: false,
          message: `Rainfall data not found for area ${areaId} on ${date}`,
        });
        return;
      }

      res.status(200).json({
        success: true,
        data: result,
      });
    } catch (error) {
      logger.error('Error updating rainfall data', error);
      next(error);
    }
  }

  /**
   * Delete rainfall data
   */
  async deleteRainfallData(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaId, date } = req.params;

      const deleted = await rainfallService.deleteRainfallData(
        areaId,
        new Date(date)
      );

      if (!deleted) {
        res.status(404).json({
          success: false,
          message: `Rainfall data not found for area ${areaId} on ${date}`,
        });
        return;
      }

      res.status(200).json({
        success: true,
        message: `Rainfall data deleted successfully`,
      });
    } catch (error) {
      logger.error('Error deleting rainfall data', error);
      next(error);
    }
  }

  /**
   * Get rainfall statistics
   */
  async getRainfallStatistics(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaId } = req.params;
      const { year, month } = req.query;

      const stats = await rainfallService.getRainfallStatistics(
        areaId,
        year ? parseInt(year as string) : undefined,
        month ? parseInt(month as string) : undefined
      );

      res.status(200).json({
        success: true,
        data: stats,
      });
    } catch (error) {
      logger.error('Error getting rainfall statistics', error);
      next(error);
    }
  }
}

export const rainfallController = new RainfallController();