import { Request, Response, NextFunction } from 'express';
import { plotPlantingDateService } from '@services/plot-planting-date.service';
import { logger } from '@utils/logger';
import { pool } from '@config/database';

class PlotPlantingDateController {
  /**
   * Update planting date for a single plot
   */
  async updatePlotPlantingDate(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { plotId } = req.params;
      const { plantingDate, cropType, season, status } = req.body;

      const result = await plotPlantingDateService.updatePlotPlantingDate({
        plotId,
        plantingDate: new Date(plantingDate),
        cropType,
        season,
        status
      });

      res.status(200).json({
        success: true,
        data: result,
        message: `Planting date updated for plot ${plotId}`
      });
    } catch (error) {
      logger.error('Error updating plot planting date', error);
      next(error);
    }
  }

  /**
   * Batch update planting dates
   */
  async batchUpdatePlantingDates(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { plotIds, plantingDate, cropType, season, status } = req.body;

      const updatedCount = await plotPlantingDateService.batchUpdatePlantingDates({
        plotIds,
        plantingDate: new Date(plantingDate),
        cropType,
        season,
        status
      });

      res.status(200).json({
        success: true,
        data: {
          updatedPlots: updatedCount,
          totalRequested: plotIds.length
        },
        message: `Updated planting dates for ${updatedCount} plots`
      });
    } catch (error) {
      logger.error('Error batch updating planting dates', error);
      next(error);
    }
  }

  /**
   * Get plots by planting date range
   */
  async getPlotsByPlantingDateRange(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { startDate, endDate, zoneId } = req.query;

      if (!startDate || !endDate) {
        res.status(400).json({
          success: false,
          error: 'startDate and endDate are required'
        });
        return;
      }

      const plots = await plotPlantingDateService.getPlotsByPlantingDateRange(
        new Date(startDate as string),
        new Date(endDate as string),
        zoneId as string
      );

      res.status(200).json({
        success: true,
        data: plots,
        count: plots.length
      });
    } catch (error) {
      logger.error('Error getting plots by planting date range', error);
      next(error);
    }
  }

  /**
   * Get upcoming planting schedules
   */
  async getUpcomingPlantingSchedules(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { daysAhead = 30 } = req.query;

      const schedules = await plotPlantingDateService.getUpcomingPlantingSchedules(
        parseInt(daysAhead as string)
      );

      res.status(200).json({
        success: true,
        data: schedules,
        count: schedules.length
      });
    } catch (error) {
      logger.error('Error getting upcoming planting schedules', error);
      next(error);
    }
  }

  /**
   * Update crop status
   */
  async updateCropStatus(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { plotId } = req.params;
      const { status } = req.body;

      await plotPlantingDateService.updateCropStatus(plotId, status);

      res.status(200).json({
        success: true,
        message: `Crop status updated to ${status} for plot ${plotId}`
      });
    } catch (error) {
      logger.error('Error updating crop status', error);
      next(error);
    }
  }

  /**
   * Get plots ready for harvest
   */
  async getPlotsReadyForHarvest(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { daysWindow = 7 } = req.query;

      const plots = await plotPlantingDateService.getPlotsReadyForHarvest(
        parseInt(daysWindow as string)
      );

      res.status(200).json({
        success: true,
        data: plots,
        count: plots.length,
        message: `Found ${plots.length} plots ready for harvest within ${daysWindow} days`
      });
    } catch (error) {
      logger.error('Error getting plots ready for harvest', error);
      next(error);
    }
  }

  /**
   * Get planting date statistics by zone
   */
  async getPlantingDateStatsByZone(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const query = `
        SELECT 
          parent_zone_id as zone,
          COUNT(*) as total_plots,
          COUNT(current_planting_date) as planted_plots,
          MIN(current_planting_date) as earliest_planting,
          MAX(current_planting_date) as latest_planting,
          COUNT(DISTINCT current_crop_type) as crop_types,
          SUM(CASE WHEN current_crop_status = 'active' THEN 1 ELSE 0 END) as active_crops,
          SUM(area_rai) as total_area_rai
        FROM ros.plots
        GROUP BY parent_zone_id
        ORDER BY parent_zone_id
      `;

      const result = await pool.query(query);

      res.status(200).json({
        success: true,
        data: result.rows,
        summary: {
          totalZones: result.rows.length,
          totalPlots: result.rows.reduce((sum, row) => sum + parseInt(row.total_plots), 0),
          totalPlanted: result.rows.reduce((sum, row) => sum + parseInt(row.planted_plots), 0)
        }
      });
    } catch (error) {
      logger.error('Error getting planting date stats', error);
      next(error);
    }
  }
}

export const plotPlantingDateController = new PlotPlantingDateController();