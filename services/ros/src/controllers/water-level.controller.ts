import { Request, Response, NextFunction } from 'express';
import { waterLevelService } from '@services/water-level.service';
import { logger } from '@utils/logger';

class WaterLevelController {
  /**
   * Get current water level
   */
  async getCurrentWaterLevel(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaId } = req.params;
      
      const currentLevel = await waterLevelService.getCurrentWaterLevel(areaId);

      if (!currentLevel) {
        res.status(404).json({
          success: false,
          message: `No water level data found for area ${areaId}`,
        });
        return;
      }

      res.status(200).json({
        success: true,
        data: currentLevel,
      });
    } catch (error) {
      logger.error('Error getting current water level', error);
      next(error);
    }
  }

  /**
   * Add water level measurement
   */
  async addWaterLevelMeasurement(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const measurement = req.body;
      const result = await waterLevelService.addWaterLevelMeasurement(measurement);

      res.status(201).json({
        success: true,
        data: result,
      });
    } catch (error) {
      logger.error('Error adding water level measurement', error);
      next(error);
    }
  }

  /**
   * Import bulk water level data
   */
  async importWaterLevelData(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { waterLevels } = req.body;
      const result = await waterLevelService.importWaterLevelData(waterLevels);

      res.status(200).json({
        success: true,
        data: result,
      });
    } catch (error) {
      logger.error('Error importing water level data', error);
      next(error);
    }
  }

  /**
   * Get water level history
   */
  async getWaterLevelHistory(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaId } = req.params;
      const { startDate, endDate, source } = req.query;

      const history = await waterLevelService.getWaterLevelHistory(
        areaId,
        new Date(startDate as string),
        new Date(endDate as string),
        source as string
      );

      res.status(200).json({
        success: true,
        data: history,
        count: history.length,
      });
    } catch (error) {
      logger.error('Error getting water level history', error);
      next(error);
    }
  }

  /**
   * Update water level
   */
  async updateWaterLevel(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const updates = req.body;

      const result = await waterLevelService.updateWaterLevel(
        parseInt(id),
        updates
      );

      if (!result) {
        res.status(404).json({
          success: false,
          message: `Water level record ${id} not found`,
        });
        return;
      }

      res.status(200).json({
        success: true,
        data: result,
      });
    } catch (error) {
      logger.error('Error updating water level', error);
      next(error);
    }
  }

  /**
   * Delete water level
   */
  async deleteWaterLevel(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;

      const deleted = await waterLevelService.deleteWaterLevel(parseInt(id));

      if (!deleted) {
        res.status(404).json({
          success: false,
          message: `Water level record ${id} not found`,
        });
        return;
      }

      res.status(200).json({
        success: true,
        message: `Water level record deleted successfully`,
      });
    } catch (error) {
      logger.error('Error deleting water level', error);
      next(error);
    }
  }

  /**
   * Get water level statistics
   */
  async getWaterLevelStatistics(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaId } = req.params;
      const { period, year, month } = req.query;

      const stats = await waterLevelService.getWaterLevelStatistics(
        areaId,
        period as string || 'monthly',
        year ? parseInt(year as string) : undefined,
        month ? parseInt(month as string) : undefined
      );

      res.status(200).json({
        success: true,
        data: stats,
      });
    } catch (error) {
      logger.error('Error getting water level statistics', error);
      next(error);
    }
  }

  /**
   * Get water level trends
   */
  async getWaterLevelTrends(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaId } = req.params;
      const { days } = req.query;

      const trends = await waterLevelService.getWaterLevelTrends(
        areaId,
        days ? parseInt(days as string) : 30
      );

      res.status(200).json({
        success: true,
        data: trends,
      });
    } catch (error) {
      logger.error('Error getting water level trends', error);
      next(error);
    }
  }
}

export const waterLevelController = new WaterLevelController();