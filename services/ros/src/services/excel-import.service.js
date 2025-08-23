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
exports.excelImportService = exports.ExcelImportService = void 0;
const XLSX = __importStar(require("xlsx"));
const eto_data_service_1 = require("./eto-data.service");
const kc_data_service_1 = require("./kc-data.service");
const logger_1 = require("@utils/logger");
class ExcelImportService {
    /**
     * Import ETo data from Excel file
     */
    async importEToData(filePath) {
        try {
            // Read Excel file
            const workbook = XLSX.readFile(filePath);
            const sheetName = 'ETo'; // Assuming sheet name is 'ETo'
            const worksheet = workbook.Sheets[sheetName];
            if (!worksheet) {
                return { success: false, message: `Sheet '${sheetName}' not found in Excel file` };
            }
            // Convert to JSON
            const data = XLSX.utils.sheet_to_json(worksheet);
            // Process and validate data
            const etoRecords = [];
            for (const row of data) {
                // Assuming Excel columns: Station, Province, Month, ETo
                const station = row['Station'] || row['สถานี'] || 'นครราชสีมา';
                const province = row['Province'] || row['จังหวัด'] || 'นครราชสีมา';
                // Process monthly columns (Jan-Dec or 1-12)
                for (let month = 1; month <= 12; month++) {
                    const monthKey = this.getMonthKey(row, month);
                    if (monthKey && row[monthKey] !== undefined) {
                        const etoValue = parseFloat(row[monthKey]);
                        if (!isNaN(etoValue)) {
                            etoRecords.push({
                                aosStation: station,
                                province: province,
                                month: month,
                                etoValue: etoValue,
                            });
                        }
                    }
                }
            }
            // Upload to database
            await eto_data_service_1.etoDataService.uploadEToData(etoRecords);
            return {
                success: true,
                message: `Successfully imported ${etoRecords.length} ETo records`,
                count: etoRecords.length,
            };
        }
        catch (error) {
            logger_1.logger.error('Failed to import ETo data', error);
            return {
                success: false,
                message: `Import failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
            };
        }
    }
    /**
     * Import Kc data from Excel file
     */
    async importKcData(filePath) {
        try {
            // Read Excel file
            const workbook = XLSX.readFile(filePath);
            const sheetName = 'Kc'; // Assuming sheet name is 'Kc'
            const worksheet = workbook.Sheets[sheetName];
            if (!worksheet) {
                return { success: false, message: `Sheet '${sheetName}' not found in Excel file` };
            }
            // Convert to JSON
            const data = XLSX.utils.sheet_to_json(worksheet);
            // Process and validate data
            const kcRecords = [];
            for (const row of data) {
                // Assuming Excel columns: Crop Type, Week 1, Week 2, ..., Week N
                const cropTypeRaw = row['Crop Type'] || row['ชนิดพืช'] || row['Crop'] || '';
                const cropType = this.normalizeCropType(cropTypeRaw);
                if (!cropType) {
                    continue; // Skip invalid crop types
                }
                // Process weekly columns
                for (let week = 1; week <= 52; week++) {
                    const weekKey = `Week ${week}` || `สัปดาห์ ${week}` || `W${week}` || week.toString();
                    if (row[weekKey] !== undefined) {
                        const kcValue = parseFloat(row[weekKey]);
                        if (!isNaN(kcValue)) {
                            kcRecords.push({
                                cropType: cropType,
                                cropWeek: week,
                                kcValue: kcValue,
                            });
                        }
                    }
                }
            }
            // Upload to database
            await kc_data_service_1.kcDataService.uploadKcData(kcRecords);
            return {
                success: true,
                message: `Successfully imported ${kcRecords.length} Kc records`,
                count: kcRecords.length,
            };
        }
        catch (error) {
            logger_1.logger.error('Failed to import Kc data', error);
            return {
                success: false,
                message: `Import failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
            };
        }
    }
    /**
     * Get month key from row data
     */
    getMonthKey(row, month) {
        // Try different month formats
        const monthNames = [
            ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
                'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'],
            ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
                'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'],
        ];
        // Check numeric month
        if (row[month.toString()]) {
            return month.toString();
        }
        // Check month names
        for (const names of monthNames) {
            if (row[names[month - 1]]) {
                return names[month - 1];
            }
        }
        return null;
    }
    /**
     * Normalize crop type string to valid CropType
     */
    normalizeCropType(cropTypeRaw) {
        const normalized = cropTypeRaw.toLowerCase().trim();
        // Map various names to standard crop types
        const cropMap = {
            'rice': 'rice',
            'ข้าว': 'rice',
            'ข้าวนาปี': 'rice',
            'ข้าวนาปรัง': 'rice',
            'corn': 'corn',
            'maize': 'corn',
            'ข้าวโพด': 'corn',
            'sugarcane': 'sugarcane',
            'sugar cane': 'sugarcane',
            'อ้อย': 'sugarcane',
        };
        return cropMap[normalized] || null;
    }
    /**
     * Validate Excel file structure for ETo data
     */
    validateEToExcel(filePath) {
        try {
            const workbook = XLSX.readFile(filePath);
            const errors = [];
            // Check for ETo sheet
            if (!workbook.Sheets['ETo']) {
                errors.push("Missing 'ETo' worksheet");
            }
            // Additional validation can be added here
            return {
                valid: errors.length === 0,
                errors,
            };
        }
        catch (error) {
            return {
                valid: false,
                errors: [`Failed to read Excel file: ${error instanceof Error ? error.message : 'Unknown error'}`],
            };
        }
    }
    /**
     * Validate Excel file structure for Kc data
     */
    validateKcExcel(filePath) {
        try {
            const workbook = XLSX.readFile(filePath);
            const errors = [];
            // Check for Kc sheet
            if (!workbook.Sheets['Kc']) {
                errors.push("Missing 'Kc' worksheet");
            }
            // Additional validation can be added here
            return {
                valid: errors.length === 0,
                errors,
            };
        }
        catch (error) {
            return {
                valid: false,
                errors: [`Failed to read Excel file: ${error instanceof Error ? error.message : 'Unknown error'}`],
            };
        }
    }
}
exports.ExcelImportService = ExcelImportService;
exports.excelImportService = new ExcelImportService();
//# sourceMappingURL=excel-import.service.js.map