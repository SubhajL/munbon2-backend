"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.waterDemandController = void 0;
const water_demand_service_1 = require("@services/water-demand.service");
const logger_1 = require("@utils/logger");
class WaterDemandController {
    /**
     * Calculate water demand for a specific crop week
     */
    async calculateWaterDemand(req, res, next) {
        try {
            const input = req.body;
            const result = await water_demand_service_1.waterDemandService.calculateWaterDemand(input);
            res.status(200).json({
                success: true,
                data: result,
            });
        }
        catch (error) {
            logger_1.logger.error('Error calculating water demand', error);
            next(error);
        }
    }
    /**
     * Calculate water demand for entire crop season
     */
    async calculateSeasonalWaterDemand(req, res, next) {
        try {
            const { areaId, areaType, areaRai, cropType, plantingDate, includeRainfall = false, } = req.body;
            const result = await water_demand_service_1.waterDemandService.calculateSeasonalWaterDemand(areaId, areaType, areaRai, cropType, new Date(plantingDate), includeRainfall);
            res.status(200).json({
                success: true,
                data: result,
            });
        }
        catch (error) {
            logger_1.logger.error('Error calculating seasonal water demand', error);
            next(error);
        }
    }
    /**
     * Get water demand for a particular area for a crop week
     */
    async getWaterDemandByCropWeek(req, res, next) {
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
        }
        catch (error) {
            logger_1.logger.error('Error getting water demand by crop week', error);
            next(error);
        }
    }
    /**
     * Get water demand for entire crop season by week
     */
    async getSeasonalWaterDemandByWeek(req, res, next) {
        try {
            const { areaId } = req.params;
            const { startDate, endDate } = req.query;
            const result = await water_demand_service_1.waterDemandService.getHistoricalWaterDemand(areaId, new Date(startDate), new Date(endDate));
            res.status(200).json({
                success: true,
                data: result,
                count: result.length,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting seasonal water demand by week', error);
            next(error);
        }
    }
    /**
     * Get water demand summary for an area
     */
    async getWaterDemandSummary(req, res, next) {
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
        }
        catch (error) {
            logger_1.logger.error('Error getting water demand summary', error);
            next(error);
        }
    }
}
exports.waterDemandController = new WaterDemandController();
//# sourceMappingURL=water-demand.controller.js.map