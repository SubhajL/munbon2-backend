"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.effectiveRainfallService = exports.EffectiveRainfallService = void 0;
const database_1 = require("@config/database");
const logger_1 = require("@utils/logger");
const dayjs_1 = __importDefault(require("dayjs"));
const weekOfYear_1 = __importDefault(require("dayjs/plugin/weekOfYear"));
dayjs_1.default.extend(weekOfYear_1.default);
class EffectiveRainfallService {
    /**
     * Get effective rainfall based on Excel data for specific crop type and time period
     * This uses pre-calculated effective rainfall values from the Thai Excel sheet
     */
    async getEffectiveRainfall(cropType, calendarWeek, calendarYear, aosStation = 'นครราชสีมา', province = 'นครราชสีมา') {
        try {
            // Determine crop category for effective rainfall lookup
            const cropCategory = this.getCropCategory(cropType);
            // Get the month for this calendar week
            const weekDate = (0, dayjs_1.default)().year(calendarYear).week(calendarWeek);
            const month = weekDate.month() + 1; // dayjs months are 0-indexed
            // Check if week spans two months
            const weekStart = weekDate.startOf('week');
            const weekEnd = weekDate.endOf('week');
            const spansMonths = weekStart.month() !== weekEnd.month();
            let monthlyEffectiveRainfall;
            if (spansMonths) {
                // If week spans months, use next month's effective rainfall (following Excel logic)
                const nextMonth = weekEnd.month() + 1;
                monthlyEffectiveRainfall = await this.getMonthlyEffectiveRainfall(aosStation, province, nextMonth, cropCategory);
            }
            else {
                // Use current month's effective rainfall
                monthlyEffectiveRainfall = await this.getMonthlyEffectiveRainfall(aosStation, province, month, cropCategory);
            }
            // Calculate weekly effective rainfall (daily × 7)
            // Get days in month
            const daysInMonth = this.getDaysInMonth(month, calendarYear);
            const dailyEffectiveRainfall = monthlyEffectiveRainfall / daysInMonth;
            const weeklyEffectiveRainfall = dailyEffectiveRainfall * 7;
            return {
                monthlyEffectiveRainfall,
                weeklyEffectiveRainfall,
                cropType: cropCategory,
                month,
                year: calendarYear,
                week: calendarWeek
            };
        }
        catch (error) {
            logger_1.logger.error('Failed to get effective rainfall', error);
            throw error;
        }
    }
    /**
     * Get monthly effective rainfall from database
     */
    async getMonthlyEffectiveRainfall(aosStation, province, month, cropType) {
        try {
            const query = `
        SELECT effective_rainfall_mm 
        FROM ros.effective_rainfall_monthly 
        WHERE aos_station = $1 
          AND province = $2
          AND month = $3
          AND crop_type = $4
      `;
            const result = await database_1.pool.query(query, [aosStation, province, month, cropType]);
            if (result.rows.length === 0) {
                // Fall back to hardcoded values if not in database
                return this.getDefaultEffectiveRainfall(month, cropType);
            }
            return parseFloat(result.rows[0].effective_rainfall_mm);
        }
        catch (error) {
            logger_1.logger.error('Failed to get monthly effective rainfall from database', error);
            // Fall back to hardcoded values
            return this.getDefaultEffectiveRainfall(month, cropType);
        }
    }
    /**
     * Determine crop category for effective rainfall lookup
     */
    getCropCategory(cropType) {
        const riceTypes = ['rice', 'rice_wet', 'rice_dry', 'ข้าว', 'นาปี', 'นาปรัง'];
        const normalizedCrop = cropType.toLowerCase();
        if (riceTypes.some(rice => normalizedCrop.includes(rice))) {
            return 'rice';
        }
        // All other crops (corn, sugarcane, etc.) are field crops
        return 'field_crop';
    }
    /**
     * Get default effective rainfall values (fallback)
     * Based on Excel data: ฝนใช้การรายวัน sheet
     */
    getDefaultEffectiveRainfall(month, cropType) {
        const effectiveRainfallData = {
            rice: {
                1: 4.6, // January
                2: 20.5, // February
                3: 41.6, // March
                4: 65.8, // April
                5: 152.1, // May
                6: 104.5, // June
                7: 122.5, // July
                8: 128.0, // August
                9: 233.2, // September
                10: 152.1, // October
                11: 31.0, // November
                12: 3.6 // December
            },
            field_crop: {
                1: 4.6, // January
                2: 16.5, // February
                3: 31.3, // March
                4: 42.3, // April
                5: 67.6, // May
                6: 46.5, // June
                7: 74.5, // July
                8: 89.3, // August
                9: 142.6, // September
                10: 81.8, // October
                11: 21.4, // November
                12: 3.6 // December
            }
        };
        return effectiveRainfallData[cropType][month] || 0;
    }
    /**
     * Get number of days in a month
     */
    getDaysInMonth(month, year) {
        // Check for leap year for February
        const isLeapYear = (year % 4 === 0 && year % 100 !== 0) || (year % 400 === 0);
        switch (month) {
            case 2: // February
                return isLeapYear ? 29 : 28;
            case 4: // April
            case 6: // June
            case 9: // September
            case 11: // November
                return 30;
            default:
                return 31;
        }
    }
    /**
     * Get effective rainfall for a date range
     */
    async getEffectiveRainfallForPeriod(cropType, startDate, endDate, aosStation = 'นครราชสีมา', province = 'นครราชสีมา') {
        try {
            const weeklyBreakdown = [];
            let totalEffectiveRainfall = 0;
            const start = (0, dayjs_1.default)(startDate);
            const end = (0, dayjs_1.default)(endDate);
            // Iterate through each week in the period
            let current = start.startOf('week');
            while (current.isBefore(end) || current.isSame(end, 'week')) {
                const week = current.week();
                const year = current.year();
                const weeklyData = await this.getEffectiveRainfall(cropType, week, year, aosStation, province);
                weeklyBreakdown.push(weeklyData);
                totalEffectiveRainfall += weeklyData.weeklyEffectiveRainfall;
                current = current.add(1, 'week');
            }
            return {
                totalEffectiveRainfall,
                weeklyBreakdown
            };
        }
        catch (error) {
            logger_1.logger.error('Failed to get effective rainfall for period', error);
            throw error;
        }
    }
}
exports.EffectiveRainfallService = EffectiveRainfallService;
exports.effectiveRainfallService = new EffectiveRainfallService();
//# sourceMappingURL=effective-rainfall.service.js.map