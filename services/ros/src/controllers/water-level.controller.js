"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.waterLevelController = void 0;
const water_level_service_1 = require("@services/water-level.service");
const logger_1 = require("@utils/logger");
class WaterLevelController {
    /**
     * Get current water level
     */
    async getCurrentWaterLevel(req, res, next) {
        try {
            const { areaId } = req.params;
            const currentLevel = await water_level_service_1.waterLevelService.getCurrentWaterLevel(areaId);
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
        }
        catch (error) {
            logger_1.logger.error('Error getting current water level', error);
            next(error);
        }
    }
    /**
     * Add water level measurement
     */
    async addWaterLevelMeasurement(req, res, next) {
        try {
            const measurement = req.body;
            const result = await water_level_service_1.waterLevelService.addWaterLevelMeasurement(measurement);
            res.status(201).json({
                success: true,
                data: result,
            });
        }
        catch (error) {
            logger_1.logger.error('Error adding water level measurement', error);
            next(error);
        }
    }
    /**
     * Import bulk water level data
     */
    async importWaterLevelData(req, res, next) {
        try {
            const { waterLevels } = req.body;
            const result = await water_level_service_1.waterLevelService.importWaterLevelData(waterLevels);
            res.status(200).json({
                success: true,
                data: result,
            });
        }
        catch (error) {
            logger_1.logger.error('Error importing water level data', error);
            next(error);
        }
    }
    /**
     * Get water level history
     */
    async getWaterLevelHistory(req, res, next) {
        try {
            const { areaId } = req.params;
            const { startDate, endDate, source } = req.query;
            const history = await water_level_service_1.waterLevelService.getWaterLevelHistory(areaId, new Date(startDate), new Date(endDate), source);
            res.status(200).json({
                success: true,
                data: history,
                count: history.length,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting water level history', error);
            next(error);
        }
    }
    /**
     * Update water level
     */
    async updateWaterLevel(req, res, next) {
        try {
            const { id } = req.params;
            const updates = req.body;
            const result = await water_level_service_1.waterLevelService.updateWaterLevel(parseInt(id), updates);
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
        }
        catch (error) {
            logger_1.logger.error('Error updating water level', error);
            next(error);
        }
    }
    /**
     * Delete water level
     */
    async deleteWaterLevel(req, res, next) {
        try {
            const { id } = req.params;
            const deleted = await water_level_service_1.waterLevelService.deleteWaterLevel(parseInt(id));
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
        }
        catch (error) {
            logger_1.logger.error('Error deleting water level', error);
            next(error);
        }
    }
    /**
     * Get water level statistics
     */
    async getWaterLevelStatistics(req, res, next) {
        try {
            const { areaId } = req.params;
            const { period, year, month } = req.query;
            const stats = await water_level_service_1.waterLevelService.getWaterLevelStatistics(areaId, period || 'monthly', year ? parseInt(year) : undefined, month ? parseInt(month) : undefined);
            res.status(200).json({
                success: true,
                data: stats,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting water level statistics', error);
            next(error);
        }
    }
    /**
     * Get water level trends
     */
    async getWaterLevelTrends(req, res, next) {
        try {
            const { areaId } = req.params;
            const { days } = req.query;
            const trends = await water_level_service_1.waterLevelService.getWaterLevelTrends(areaId, days ? parseInt(days) : 30);
            res.status(200).json({
                success: true,
                data: trends,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting water level trends', error);
            next(error);
        }
    }
}
exports.waterLevelController = new WaterLevelController();
//# sourceMappingURL=water-level.controller.js.map