import { Request, Response, NextFunction } from 'express';
import { waterDemandService } from '@services/water-demand.service';
import { WaterDemandInput } from '@types/index';
import { logger } from '@utils/logger';

class WaterDemandController {
  /**
   * Calculate water demand for a specific crop week
   */
  async calculateWaterDemand(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const input: WaterDemandInput = req.body;
      const result = await waterDemandService.calculateWaterDemand(input);

      res.status(200).json({
        success: true,
        data: result,
      });
    } catch (error) {
      logger.error('Error calculating water demand', error);
      next(error);
    }
  }

  /**
   * Calculate water demand for entire crop season
   */
  async calculateSeasonalWaterDemand(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const {
        areaId,
        areaType,
        areaRai,
        cropType,
        plantingDate,
        includeRainfall = false,
      } = req.body;

      const result = await waterDemandService.calculateSeasonalWaterDemand(
        areaId,
        areaType,
        areaRai,
        cropType,
        new Date(plantingDate),
        includeRainfall
      );

      res.status(200).json({
        success: true,
        data: result,
      });
    } catch (error) {
      logger.error('Error calculating seasonal water demand', error);
      next(error);
    }
  }

  /**
   * Get water demand for a particular area for a crop week
   */
  async getWaterDemandByCropWeek(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaId } = req.params;
      const { cropWeek } = req.query;

      // Implementation would query saved calculations
      res.status(200).json({
        success: true,
        message: 'Endpoint for getting water demand by crop week',
        areaId,
        cropWeek,
      });
    } catch (error) {
      logger.error('Error getting water demand by crop week', error);
      next(error);
    }
  }

  /**
   * Get water demand for entire crop season by week
   */
  async getSeasonalWaterDemandByWeek(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaId } = req.params;
      const { startDate, endDate } = req.query;

      const result = await waterDemandService.getHistoricalWaterDemand(
        areaId,
        new Date(startDate as string),
        new Date(endDate as string)
      );

      res.status(200).json({
        success: true,
        data: result,
        count: result.length,
      });
    } catch (error) {
      logger.error('Error getting seasonal water demand by week', error);
      next(error);
    }
  }

  /**
   * Get water demand summary for an area
   */
  async getWaterDemandSummary(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaType } = req.params;
      const { areaId, startDate, endDate } = req.query;

      // Implementation would aggregate water demand by area type
      res.status(200).json({
        success: true,
        message: 'Endpoint for water demand summary',
        areaType,
        areaId,
        period: { startDate, endDate },
      });
    } catch (error) {
      logger.error('Error getting water demand summary', error);
      next(error);
    }
  }
}

export const waterDemandController = new WaterDemandController();