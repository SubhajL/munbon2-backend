"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.plotPlantingDateController = void 0;
const plot_planting_date_service_1 = require("@services/plot-planting-date.service");
const logger_1 = require("@utils/logger");
const database_1 = require("@config/database");
class PlotPlantingDateController {
    /**
     * Update planting date for a single plot
     */
    async updatePlotPlantingDate(req, res, next) {
        try {
            const { plotId } = req.params;
            const { plantingDate, cropType, season, status } = req.body;
            const result = await plot_planting_date_service_1.plotPlantingDateService.updatePlotPlantingDate({
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
        }
        catch (error) {
            logger_1.logger.error('Error updating plot planting date', error);
            next(error);
        }
    }
    /**
     * Batch update planting dates
     */
    async batchUpdatePlantingDates(req, res, next) {
        try {
            const { plotIds, plantingDate, cropType, season, status } = req.body;
            const updatedCount = await plot_planting_date_service_1.plotPlantingDateService.batchUpdatePlantingDates({
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
        }
        catch (error) {
            logger_1.logger.error('Error batch updating planting dates', error);
            next(error);
        }
    }
    /**
     * Get plots by planting date range
     */
    async getPlotsByPlantingDateRange(req, res, next) {
        try {
            const { startDate, endDate, zoneId } = req.query;
            if (!startDate || !endDate) {
                res.status(400).json({
                    success: false,
                    error: 'startDate and endDate are required'
                });
                return;
            }
            const plots = await plot_planting_date_service_1.plotPlantingDateService.getPlotsByPlantingDateRange(new Date(startDate), new Date(endDate), zoneId);
            res.status(200).json({
                success: true,
                data: plots,
                count: plots.length
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting plots by planting date range', error);
            next(error);
        }
    }
    /**
     * Get upcoming planting schedules
     */
    async getUpcomingPlantingSchedules(req, res, next) {
        try {
            const { daysAhead = 30 } = req.query;
            const schedules = await plot_planting_date_service_1.plotPlantingDateService.getUpcomingPlantingSchedules(parseInt(daysAhead));
            res.status(200).json({
                success: true,
                data: schedules,
                count: schedules.length
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting upcoming planting schedules', error);
            next(error);
        }
    }
    /**
     * Update crop status
     */
    async updateCropStatus(req, res, next) {
        try {
            const { plotId } = req.params;
            const { status } = req.body;
            await plot_planting_date_service_1.plotPlantingDateService.updateCropStatus(plotId, status);
            res.status(200).json({
                success: true,
                message: `Crop status updated to ${status} for plot ${plotId}`
            });
        }
        catch (error) {
            logger_1.logger.error('Error updating crop status', error);
            next(error);
        }
    }
    /**
     * Get plots ready for harvest
     */
    async getPlotsReadyForHarvest(req, res, next) {
        try {
            const { daysWindow = 7 } = req.query;
            const plots = await plot_planting_date_service_1.plotPlantingDateService.getPlotsReadyForHarvest(parseInt(daysWindow));
            res.status(200).json({
                success: true,
                data: plots,
                count: plots.length,
                message: `Found ${plots.length} plots ready for harvest within ${daysWindow} days`
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting plots ready for harvest', error);
            next(error);
        }
    }
    /**
     * Get planting date statistics by zone
     */
    async getPlantingDateStatsByZone(req, res, next) {
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
            const result = await database_1.pool.query(query);
            res.status(200).json({
                success: true,
                data: result.rows,
                summary: {
                    totalZones: result.rows.length,
                    totalPlots: result.rows.reduce((sum, row) => sum + parseInt(row.total_plots), 0),
                    totalPlanted: result.rows.reduce((sum, row) => sum + parseInt(row.planted_plots), 0)
                }
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting planting date stats', error);
            next(error);
        }
    }
}
exports.plotPlantingDateController = new PlotPlantingDateController();
//# sourceMappingURL=plot-planting-date.controller.js.map