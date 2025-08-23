"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.cropWeekController = void 0;
const crop_week_calculator_1 = require("@utils/crop-week-calculator");
const logger_1 = require("@utils/logger");
class CropWeekController {
    /**
     * Calculate current crop week from planting date
     */
    async calculateCurrentCropWeek(req, res, next) {
        try {
            const { plantingDate, currentDate } = req.body;
            const cropWeek = (0, crop_week_calculator_1.calculateCropWeek)(new Date(plantingDate), currentDate ? new Date(currentDate) : new Date());
            if (cropWeek === null) {
                res.status(400).json({
                    success: false,
                    message: 'Current date is before planting date'
                });
                return;
            }
            const calendarInfo = (0, crop_week_calculator_1.getCalendarWeekFromCropWeek)(new Date(plantingDate), cropWeek);
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
        }
        catch (error) {
            logger_1.logger.error('Error calculating crop week', error);
            next(error);
        }
    }
    /**
     * Get crop week info for multiple plots
     */
    async getCropWeeksForPlots(req, res, next) {
        try {
            const { plots } = req.body; // Array of {plotId, plantingDate}
            const results = plots.map((plot) => {
                const info = (0, crop_week_calculator_1.getCurrentCropWeekInfo)(new Date(plot.plantingDate));
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
        }
        catch (error) {
            logger_1.logger.error('Error getting crop weeks for plots', error);
            next(error);
        }
    }
    /**
     * Calculate planting date from current crop week
     */
    async calculatePlantingDate(req, res, next) {
        try {
            const { cropWeek, currentDate } = req.body;
            const plantingDate = (0, crop_week_calculator_1.calculatePlantingDateFromCropWeek)(cropWeek, currentDate ? new Date(currentDate) : new Date());
            res.status(200).json({
                success: true,
                data: {
                    cropWeek,
                    currentDate: currentDate || new Date().toISOString(),
                    estimatedPlantingDate: plantingDate.toISOString()
                }
            });
        }
        catch (error) {
            logger_1.logger.error('Error calculating planting date', error);
            next(error);
        }
    }
}
exports.cropWeekController = new CropWeekController();
//# sourceMappingURL=crop-week.controller.js.map