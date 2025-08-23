"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.etoDataController = void 0;
const eto_data_service_1 = require("@services/eto-data.service");
const logger_1 = require("@utils/logger");
class EToDataController {
    /**
     * Get monthly ETo value for a specific month
     */
    async getMonthlyETo(req, res, next) {
        try {
            const { month, station, province } = req.query;
            if (!month) {
                res.status(400).json({
                    success: false,
                    message: 'Month parameter is required',
                });
                return;
            }
            const monthNum = parseInt(month);
            if (monthNum < 1 || monthNum > 12) {
                res.status(400).json({
                    success: false,
                    message: 'Month must be between 1 and 12',
                });
                return;
            }
            const etoValue = await eto_data_service_1.etoDataService.getMonthlyETo(station || 'นครราชสีมา', province || 'นครราชสีมา', monthNum);
            res.status(200).json({
                success: true,
                data: {
                    month: monthNum,
                    station: station || 'นครราชสีมา',
                    province: province || 'นครราชสีมา',
                    etoValue,
                    unit: 'mm/month',
                },
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting monthly ETo', error);
            next(error);
        }
    }
    /**
     * Get all monthly ETo values for a station
     */
    async getAllMonthlyETo(req, res, next) {
        try {
            const { station, province } = req.query;
            const etoData = await eto_data_service_1.etoDataService.getAllMonthlyETo(station || 'นครราชสีมา', province || 'นครราชสีมา');
            res.status(200).json({
                success: true,
                data: {
                    station: station || 'นครราชสีมา',
                    province: province || 'นครราชสีมา',
                    monthlyValues: etoData,
                    unit: 'mm/month',
                },
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting all monthly ETo', error);
            next(error);
        }
    }
}
exports.etoDataController = new EToDataController();
//# sourceMappingURL=eto-data.controller.js.map