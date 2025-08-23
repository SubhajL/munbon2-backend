"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.plotWaterDemandController = void 0;
const plot_water_demand_service_1 = require("@services/plot-water-demand.service");
const logger_1 = require("@utils/logger");
class PlotWaterDemandController {
    /**
     * Calculate water demand for a single plot
     */
    async calculatePlotDemand(req, res, next) {
        try {
            const { plotId } = req.params;
            const { cropType, plantingDate, includeRainfall = true, includeLandPreparation = true } = req.body;
            const result = await plot_water_demand_service_1.plotWaterDemandService.calculatePlotWaterDemand({
                plotId,
                cropType,
                plantingDate: new Date(plantingDate),
                includeRainfall,
                includeLandPreparation,
            });
            res.status(200).json({
                success: true,
                data: result,
            });
        }
        catch (error) {
            logger_1.logger.error('Error calculating plot water demand', error);
            next(error);
        }
    }
    /**
     * Calculate water demand for multiple plots (batch)
     */
    async calculateBatchPlotDemand(req, res, next) {
        try {
            const { plotIds, cropType, plantingDate, includeRainfall = true, includeLandPreparation = true } = req.body;
            if (!Array.isArray(plotIds) || plotIds.length === 0) {
                res.status(400).json({
                    success: false,
                    error: 'plotIds must be a non-empty array',
                });
                return;
            }
            const results = await plot_water_demand_service_1.plotWaterDemandService.calculateBatchPlotWaterDemand({
                plotIds,
                cropType,
                plantingDate: new Date(plantingDate),
                includeRainfall,
                includeLandPreparation,
            });
            // Convert Map to object for JSON response
            const data = {};
            results.forEach((value, key) => {
                data[key] = value;
            });
            res.status(200).json({
                success: true,
                data,
                summary: {
                    totalPlots: plotIds.length,
                    successfulCalculations: results.size,
                    failedCalculations: plotIds.length - results.size,
                },
            });
        }
        catch (error) {
            logger_1.logger.error('Error calculating batch plot water demand', error);
            next(error);
        }
    }
    /**
     * Get plots by zone or section
     */
    async getPlotsByArea(req, res, next) {
        try {
            const { areaType, areaId } = req.params;
            if (areaType !== 'zone' && areaType !== 'section') {
                res.status(400).json({
                    success: false,
                    error: 'areaType must be either "zone" or "section"',
                });
                return;
            }
            const plots = await plot_water_demand_service_1.plotWaterDemandService.getPlotsByArea(areaType, areaId);
            res.status(200).json({
                success: true,
                data: plots,
                count: plots.length,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting plots by area', error);
            next(error);
        }
    }
    /**
     * Get plot information
     */
    async getPlotInfo(req, res, next) {
        try {
            const { plotId } = req.params;
            const plotInfo = await plot_water_demand_service_1.plotWaterDemandService.getPlotInfo(plotId);
            if (!plotInfo) {
                res.status(404).json({
                    success: false,
                    error: `Plot ${plotId} not found`,
                });
                return;
            }
            res.status(200).json({
                success: true,
                data: plotInfo,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting plot info', error);
            next(error);
        }
    }
    /**
     * Get historical water demand for a plot
     */
    async getPlotHistoricalDemand(req, res, next) {
        try {
            const { plotId } = req.params;
            const { startYear, endYear } = req.query;
            const history = await plot_water_demand_service_1.plotWaterDemandService.getPlotHistoricalDemand(plotId, startYear ? parseInt(startYear) : undefined, endYear ? parseInt(endYear) : undefined);
            res.status(200).json({
                success: true,
                data: history,
                count: history.length,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting plot historical demand', error);
            next(error);
        }
    }
    /**
     * Get current week water demand for all active plots
     */
    async getCurrentWeekDemand(req, res, next) {
        try {
            const { week, year } = req.query;
            const currentWeek = week ? parseInt(week) : new Date().getWeek();
            const currentYear = year ? parseInt(year) : new Date().getFullYear();
            const demands = await plot_water_demand_service_1.plotWaterDemandService.getCurrentWeekDemandForActivePlots(currentWeek, currentYear);
            // Calculate summary statistics
            const summary = {
                totalPlots: demands.length,
                totalWaterDemandM3: demands.reduce((sum, d) => sum + parseFloat(d.crop_water_demand_m3 || 0), 0),
                totalNetWaterDemandM3: demands.reduce((sum, d) => sum + parseFloat(d.net_water_demand_m3 || 0), 0),
                byZone: {},
            };
            // Group by zone
            demands.forEach(d => {
                const zone = d.parent_zone_id || 'Unknown';
                if (!summary.byZone[zone]) {
                    summary.byZone[zone] = 0;
                }
                summary.byZone[zone] += parseFloat(d.net_water_demand_m3 || 0);
            });
            res.status(200).json({
                success: true,
                data: demands,
                summary,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting current week demand', error);
            next(error);
        }
    }
    /**
     * Calculate water demand by zone (aggregate all plots in zone)
     */
    async calculateZoneDemand(req, res, next) {
        try {
            const { zoneId } = req.params;
            const { cropType, plantingDate, includeRainfall = true, includeLandPreparation = true } = req.body;
            // Get all plots in the zone
            const plots = await plot_water_demand_service_1.plotWaterDemandService.getPlotsByArea('zone', zoneId);
            if (plots.length === 0) {
                res.status(404).json({
                    success: false,
                    error: `No plots found in zone ${zoneId}`,
                });
                return;
            }
            // Calculate for all plots
            const plotIds = plots.map(p => p.plotId);
            const results = await plot_water_demand_service_1.plotWaterDemandService.calculateBatchPlotWaterDemand({
                plotIds,
                cropType,
                plantingDate: new Date(plantingDate),
                includeRainfall,
                includeLandPreparation,
            });
            // Aggregate results
            let totalAreaRai = 0;
            let totalWaterDemandM3 = 0;
            let totalNetWaterDemandM3 = 0;
            let totalLandPreparationM3 = 0;
            results.forEach((result, plotId) => {
                totalAreaRai += result.areaRai;
                totalWaterDemandM3 += result.totalWaterDemandM3;
                totalNetWaterDemandM3 += result.totalNetWaterDemandM3 || 0;
                totalLandPreparationM3 += result.landPreparationM3 || 0;
            });
            res.status(200).json({
                success: true,
                data: {
                    zoneId,
                    totalPlots: plots.length,
                    totalAreaRai,
                    cropType,
                    plantingDate,
                    totalWaterDemandM3,
                    totalNetWaterDemandM3,
                    totalLandPreparationM3,
                    averagePerPlot: {
                        waterDemandM3: totalWaterDemandM3 / plots.length,
                        netWaterDemandM3: totalNetWaterDemandM3 / plots.length,
                    },
                    plotDetails: Object.fromEntries(results),
                },
            });
        }
        catch (error) {
            logger_1.logger.error('Error calculating zone demand', error);
            next(error);
        }
    }
}
exports.plotWaterDemandController = new PlotWaterDemandController();
//# sourceMappingURL=plot-water-demand.controller.js.map