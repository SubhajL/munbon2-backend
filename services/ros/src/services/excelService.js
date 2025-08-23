"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.excelService = exports.ExcelService = void 0;
const XLSX = __importStar(require("xlsx"));
const errorHandler_1 = require("../middleware/errorHandler");
const logger_1 = require("../utils/logger");
class ExcelService {
    /**
     * Parse Kc data from Excel file
     */
    async parseKcData(buffer) {
        try {
            const workbook = XLSX.read(buffer, { type: 'buffer' });
            const kcSheet = workbook.Sheets['Kc'];
            if (!kcSheet) {
                throw new errorHandler_1.AppError('Kc sheet not found in Excel file', 400);
            }
            const data = XLSX.utils.sheet_to_json(kcSheet, { header: 1 });
            const results = [];
            // Find crop names row (typically row 3, index 2)
            const cropRow = 2;
            const crops = [];
            // Get crop names from columns B onwards
            for (let col = 1; col < data[cropRow].length; col++) {
                if (data[cropRow][col]) {
                    crops.push(data[cropRow][col]);
                }
            }
            // Parse Kc values for each crop
            for (let cropIndex = 0; cropIndex < crops.length; cropIndex++) {
                const cropType = crops[cropIndex];
                const colIndex = cropIndex + 1; // Starting from column B
                // Parse growth weeks (rows 4 onwards)
                for (let row = 3; row < data.length; row++) {
                    const week = row - 2; // Week number
                    const kcValue = parseFloat(data[row][colIndex]);
                    if (!isNaN(kcValue)) {
                        results.push({
                            cropType,
                            growthWeek: week,
                            kcValue,
                            growthStage: this.determineGrowthStage(week)
                        });
                    }
                }
            }
            logger_1.logger.info(`Parsed ${results.length} Kc values for ${crops.length} crops`);
            return results;
        }
        catch (error) {
            logger_1.logger.error('Error parsing Kc data:', error);
            throw new errorHandler_1.AppError('Failed to parse Kc data from Excel', 400);
        }
    }
    /**
     * Parse ET0 data from Excel file
     */
    async parseET0Data(buffer) {
        try {
            const workbook = XLSX.read(buffer, { type: 'buffer' });
            const et0Sheet = workbook.Sheets['ETo'] || workbook.Sheets['ET0'];
            if (!et0Sheet) {
                throw new errorHandler_1.AppError('ETo sheet not found in Excel file', 400);
            }
            const data = XLSX.utils.sheet_to_json(et0Sheet, { header: 1 });
            const results = [];
            const currentYear = new Date().getFullYear();
            // ET0 data typically has months in columns starting from column D (index 3)
            // Parse monthly values
            for (let month = 1; month <= 12; month++) {
                const colIndex = month + 2; // Columns D-O for Jan-Dec
                let monthlySum = 0;
                let count = 0;
                // Average values from multiple rows
                for (let row = 3; row < Math.min(88, data.length); row++) {
                    const value = parseFloat(data[row][colIndex]);
                    if (!isNaN(value) && value > 0) {
                        monthlySum += value;
                        count++;
                    }
                }
                if (count > 0) {
                    results.push({
                        location: 'Munbon',
                        year: currentYear,
                        month: month,
                        et0Value: monthlySum / count,
                        source: 'Excel import'
                    });
                }
            }
            logger_1.logger.info(`Parsed ET0 data for ${results.length} months`);
            return results;
        }
        catch (error) {
            logger_1.logger.error('Error parsing ET0 data:', error);
            throw new errorHandler_1.AppError('Failed to parse ET0 data from Excel', 400);
        }
    }
    /**
     * Parse rainfall data from Excel file
     */
    async parseRainfallData(buffer) {
        try {
            const workbook = XLSX.read(buffer, { type: 'buffer' });
            const rainSheet = workbook.Sheets['ฝนใช้การข้าว'] ||
                workbook.Sheets['rainforpaddy'] ||
                workbook.Sheets['Rainfall'];
            if (!rainSheet) {
                throw new errorHandler_1.AppError('Rainfall sheet not found in Excel file', 400);
            }
            const data = XLSX.utils.sheet_to_json(rainSheet, { header: 1 });
            const results = [];
            const currentYear = new Date().getFullYear();
            // Parse rainfall data (expecting month in first column, values in subsequent columns)
            for (let row = 1; row < data.length; row++) {
                const month = parseInt(data[row][0]);
                if (month >= 1 && month <= 12) {
                    const totalRainfall = parseFloat(data[row][1]) || 0;
                    const effectiveRainfall = parseFloat(data[row][3]) || 0;
                    const rainyDays = parseInt(data[row][2]) || undefined;
                    results.push({
                        location: 'Munbon',
                        year: currentYear,
                        month: month,
                        totalRainfall: totalRainfall,
                        effectiveRainfall: effectiveRainfall,
                        numberOfRainyDays: rainyDays
                    });
                }
            }
            logger_1.logger.info(`Parsed rainfall data for ${results.length} months`);
            return results;
        }
        catch (error) {
            logger_1.logger.error('Error parsing rainfall data:', error);
            throw new errorHandler_1.AppError('Failed to parse rainfall data from Excel', 400);
        }
    }
    /**
     * Parse complete ROS Excel file
     */
    async parseROSExcelFile(buffer) {
        try {
            const workbook = XLSX.read(buffer, { type: 'buffer' });
            // Get fill_data sheet for parameters
            const fillDataSheet = workbook.Sheets['fill_data'];
            if (!fillDataSheet) {
                throw new errorHandler_1.AppError('fill_data sheet not found', 400);
            }
            // Extract crop type (D5)
            const cropType = this.getCellValue(fillDataSheet, 'D5') || 'ข้าว กข.(นาดำ)';
            // Extract non-agricultural demands
            const nonAgriculturalDemands = {
                domestic: this.getNumericCellValue(fillDataSheet, 'C64'),
                industrial: this.getNumericCellValue(fillDataSheet, 'D64'),
                ecosystem: this.getNumericCellValue(fillDataSheet, 'E64'),
                other: this.getNumericCellValue(fillDataSheet, 'F64')
            };
            // Extract planting schedule from paddy_rain sheet
            const paddySheet = workbook.Sheets['paddy_rain'];
            const plantingSchedule = this.extractPlantingSchedule(paddySheet);
            // Extract other parameters
            const parameters = {
                cropDuration: this.getNumericCellValue(fillDataSheet, 'E9') || 17,
                percolationRate: this.getNumericCellValue(fillDataSheet, 'E10') || 2,
                startDate: this.getCellValue(fillDataSheet, 'D7') || new Date()
            };
            return {
                cropType,
                plantingSchedule,
                nonAgriculturalDemands,
                parameters
            };
        }
        catch (error) {
            logger_1.logger.error('Error parsing ROS Excel file:', error);
            throw error;
        }
    }
    /**
     * Extract planting schedule from paddy sheet
     */
    extractPlantingSchedule(sheet) {
        if (!sheet)
            return [];
        const data = XLSX.utils.sheet_to_json(sheet, { header: 1 });
        const schedule = [];
        const baseDate = new Date(2024, 10, 1); // November 1, 2024
        // Parse F3:G23 range
        for (let row = 2; row < 23 && row < data.length; row++) {
            const weekNumber = parseInt(data[row][5]); // Column F
            const areaRai = parseFloat(data[row][6]); // Column G
            if (!isNaN(weekNumber) && !isNaN(areaRai) && areaRai > 0) {
                const plantingDate = new Date(baseDate);
                plantingDate.setDate(plantingDate.getDate() + (weekNumber - 1) * 7);
                schedule.push({
                    plantingDate,
                    areaRai
                });
            }
        }
        return schedule;
    }
    /**
     * Generate Excel report
     */
    async generateExcelReport(data) {
        try {
            const workbook = XLSX.utils.book_new();
            // Weekly results sheet
            const weeklySheet = XLSX.utils.json_to_sheet(data.weeklyResults);
            XLSX.utils.book_append_sheet(workbook, weeklySheet, 'Weekly_Results');
            // Monthly summary sheet
            const monthlySheet = XLSX.utils.json_to_sheet(data.monthlySummary);
            XLSX.utils.book_append_sheet(workbook, monthlySheet, 'Monthly_Summary');
            // Annual summary sheet
            const annualSheet = XLSX.utils.json_to_sheet(data.annualSummary);
            XLSX.utils.book_append_sheet(workbook, annualSheet, 'Annual_Summary');
            // Parameters sheet
            const paramsSheet = XLSX.utils.json_to_sheet([data.parameters]);
            XLSX.utils.book_append_sheet(workbook, paramsSheet, 'Parameters');
            // Generate buffer
            const buffer = XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' });
            return buffer;
        }
        catch (error) {
            logger_1.logger.error('Error generating Excel report:', error);
            throw new errorHandler_1.AppError('Failed to generate Excel report', 500);
        }
    }
    /**
     * Get cell value helper
     */
    getCellValue(sheet, address) {
        const cell = sheet[address];
        return cell ? cell.v : undefined;
    }
    /**
     * Get numeric cell value helper
     */
    getNumericCellValue(sheet, address) {
        const value = this.getCellValue(sheet, address);
        const num = parseFloat(value);
        return isNaN(num) ? undefined : num;
    }
    /**
     * Determine growth stage based on week
     */
    determineGrowthStage(week) {
        if (week <= 3)
            return 'initial';
        if (week <= 7)
            return 'development';
        if (week <= 13)
            return 'mid-season';
        if (week <= 16)
            return 'late-season';
        return 'harvest';
    }
    /**
     * Generate CSV report
     */
    async generateCSVReport(data) {
        try {
            const worksheet = XLSX.utils.json_to_sheet(data);
            const csv = XLSX.utils.sheet_to_csv(worksheet);
            return csv;
        }
        catch (error) {
            logger_1.logger.error('Error generating CSV report:', error);
            throw new errorHandler_1.AppError('Failed to generate CSV report', 500);
        }
    }
}
exports.ExcelService = ExcelService;
exports.excelService = new ExcelService();
//# sourceMappingURL=excelService.js.map