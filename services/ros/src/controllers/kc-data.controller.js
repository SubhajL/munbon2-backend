"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.kcDataController = void 0;
const kc_data_service_1 = require("@services/kc-data.service");
const logger_1 = require("@utils/logger");
class KcDataController {
    /**
     * Get Kc value for specific crop and week
     */
    async getKcValue(req, res, next) {
        try {
            const { cropType, week } = req.params;
            const cropWeek = parseInt(week);
            if (isNaN(cropWeek) || cropWeek < 1) {
                res.status(400).json({
                    success: false,
                    message: 'Invalid week number',
                });
                return;
            }
            const kcValue = await kc_data_service_1.kcDataService.getKcValue(cropType, cropWeek);
            res.status(200).json({
                success: true,
                data: {
                    cropType,
                    cropWeek,
                    kcValue,
                },
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting Kc value', error);
            next(error);
        }
    }
    /**
     * Get all Kc values for a crop type
     */
    async getAllKcValues(req, res, next) {
        try {
            const { cropType } = req.params;
            const kcData = await kc_data_service_1.kcDataService.getAllKcValues(cropType);
            const totalWeeks = await kc_data_service_1.kcDataService.getTotalCropWeeks(cropType);
            res.status(200).json({
                success: true,
                data: {
                    cropType,
                    totalWeeks,
                    weeklyValues: kcData,
                },
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting all Kc values', error);
            next(error);
        }
    }
    /**
     * Get crop summary
     */
    async getCropSummary(req, res, next) {
        try {
            const summary = await kc_data_service_1.kcDataService.getCropSummary();
            res.status(200).json({
                success: true,
                data: summary,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting crop summary', error);
            next(error);
        }
    }
}
exports.kcDataController = new KcDataController();
//# sourceMappingURL=kc-data.controller.js.map