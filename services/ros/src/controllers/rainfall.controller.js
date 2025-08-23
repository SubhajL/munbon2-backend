"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.rainfallController = void 0;
const rainfall_service_1 = require("@services/rainfall.service");
const logger_1 = require("@utils/logger");
class RainfallController {
    /**
     * Get weekly effective rainfall
     */
    async getWeeklyEffectiveRainfall(req, res, next) {
        try {
            const { areaId } = req.params;
            const { weekStartDate } = req.query;
            const effectiveRainfall = await rainfall_service_1.rainfallService.getWeeklyEffectiveRainfall(areaId, weekStartDate ? new Date(weekStartDate) : new Date());
            res.status(200).json({
                success: true,
                data: {
                    areaId,
                    weekStartDate: weekStartDate || new Date().toISOString().split('T')[0],
                    effectiveRainfallMm: effectiveRainfall,
                },
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting weekly effective rainfall', error);
            next(error);
        }
    }
    /**
     * Add rainfall data
     */
    async addRainfallData(req, res, next) {
        try {
            const rainfallData = req.body;
            const result = await rainfall_service_1.rainfallService.addRainfallData(rainfallData);
            res.status(201).json({
                success: true,
                data: result,
            });
        }
        catch (error) {
            logger_1.logger.error('Error adding rainfall data', error);
            next(error);
        }
    }
    /**
     * Import bulk rainfall data
     */
    async importRainfallData(req, res, next) {
        try {
            const { rainfallData } = req.body;
            const result = await rainfall_service_1.rainfallService.importRainfallData(rainfallData);
            res.status(200).json({
                success: true,
                data: result,
            });
        }
        catch (error) {
            logger_1.logger.error('Error importing rainfall data', error);
            next(error);
        }
    }
    /**
     * Get rainfall history
     */
    async getRainfallHistory(req, res, next) {
        try {
            const { areaId } = req.params;
            const { startDate, endDate } = req.query;
            const history = await rainfall_service_1.rainfallService.getRainfallHistory(areaId, new Date(startDate), new Date(endDate));
            res.status(200).json({
                success: true,
                data: history,
                count: history.length,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting rainfall history', error);
            next(error);
        }
    }
    /**
     * Update rainfall data
     */
    async updateRainfallData(req, res, next) {
        try {
            const { areaId, date } = req.params;
            const updates = req.body;
            const result = await rainfall_service_1.rainfallService.updateRainfallData(areaId, new Date(date), updates);
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
        }
        catch (error) {
            logger_1.logger.error('Error updating rainfall data', error);
            next(error);
        }
    }
    /**
     * Delete rainfall data
     */
    async deleteRainfallData(req, res, next) {
        try {
            const { areaId, date } = req.params;
            const deleted = await rainfall_service_1.rainfallService.deleteRainfallData(areaId, new Date(date));
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
        }
        catch (error) {
            logger_1.logger.error('Error deleting rainfall data', error);
            next(error);
        }
    }
    /**
     * Get rainfall statistics
     */
    async getRainfallStatistics(req, res, next) {
        try {
            const { areaId } = req.params;
            const { year, month } = req.query;
            const stats = await rainfall_service_1.rainfallService.getRainfallStatistics(areaId, year ? parseInt(year) : undefined, month ? parseInt(month) : undefined);
            res.status(200).json({
                success: true,
                data: stats,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting rainfall statistics', error);
            next(error);
        }
    }
}
exports.rainfallController = new RainfallController();
//# sourceMappingURL=rainfall.controller.js.map