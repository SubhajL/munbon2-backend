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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.dataUploadController = void 0;
const excel_import_service_1 = require("@services/excel-import.service");
const logger_1 = require("@utils/logger");
const promises_1 = __importDefault(require("fs/promises"));
class DataUploadController {
    /**
     * Upload and import ETo data from Excel
     */
    async uploadEToData(req, res, next) {
        try {
            if (!req.file) {
                res.status(400).json({
                    success: false,
                    message: 'No file uploaded',
                });
                return;
            }
            // Validate file
            const validation = excel_import_service_1.excelImportService.validateEToExcel(req.file.path);
            if (!validation.valid) {
                // Clean up uploaded file
                await promises_1.default.unlink(req.file.path);
                res.status(400).json({
                    success: false,
                    message: 'Invalid Excel file',
                    errors: validation.errors,
                });
                return;
            }
            // Import data
            const result = await excel_import_service_1.excelImportService.importEToData(req.file.path);
            // Clean up uploaded file
            await promises_1.default.unlink(req.file.path);
            if (result.success) {
                res.status(200).json(result);
            }
            else {
                res.status(400).json(result);
            }
        }
        catch (error) {
            logger_1.logger.error('Error uploading ETo data', error);
            // Clean up file if exists
            if (req.file) {
                await promises_1.default.unlink(req.file.path).catch(() => { });
            }
            next(error);
        }
    }
    /**
     * Upload and import Kc data from Excel
     */
    async uploadKcData(req, res, next) {
        try {
            if (!req.file) {
                res.status(400).json({
                    success: false,
                    message: 'No file uploaded',
                });
                return;
            }
            // Validate file
            const validation = excel_import_service_1.excelImportService.validateKcExcel(req.file.path);
            if (!validation.valid) {
                // Clean up uploaded file
                await promises_1.default.unlink(req.file.path);
                res.status(400).json({
                    success: false,
                    message: 'Invalid Excel file',
                    errors: validation.errors,
                });
                return;
            }
            // Import data
            const result = await excel_import_service_1.excelImportService.importKcData(req.file.path);
            // Clean up uploaded file
            await promises_1.default.unlink(req.file.path);
            if (result.success) {
                res.status(200).json(result);
            }
            else {
                res.status(400).json(result);
            }
        }
        catch (error) {
            logger_1.logger.error('Error uploading Kc data', error);
            // Clean up file if exists
            if (req.file) {
                await promises_1.default.unlink(req.file.path).catch(() => { });
            }
            next(error);
        }
    }
    /**
     * Download ETo template Excel file
     */
    async downloadEToTemplate(req, res, next) {
        try {
            // Create template Excel file
            const XLSX = await Promise.resolve().then(() => __importStar(require('xlsx')));
            const workbook = XLSX.utils.book_new();
            // Create ETo sheet with headers
            const headers = ['Station', 'Province', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            const sampleData = [
                headers,
                ['นครราชสีมา', 'นครราชสีมา', 108.5, 122.4, 151.9, 156.0, 148.8, 132.0,
                    130.2, 127.1, 114.0, 108.5, 102.0, 99.2],
            ];
            const ws = XLSX.utils.aoa_to_sheet(sampleData);
            XLSX.utils.book_append_sheet(workbook, ws, 'ETo');
            // Write to buffer
            const buffer = XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' });
            res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
            res.setHeader('Content-Disposition', 'attachment; filename=eto-template.xlsx');
            res.send(buffer);
        }
        catch (error) {
            logger_1.logger.error('Error creating ETo template', error);
            next(error);
        }
    }
    /**
     * Download Kc template Excel file
     */
    async downloadKcTemplate(req, res, next) {
        try {
            // Create template Excel file
            const XLSX = await Promise.resolve().then(() => __importStar(require('xlsx')));
            const workbook = XLSX.utils.book_new();
            // Create Kc sheet with headers
            const headers = ['Crop Type'];
            for (let i = 1; i <= 16; i++) {
                headers.push(`Week ${i}`);
            }
            const sampleData = [
                headers,
                ['rice', 1.05, 1.05, 1.05, 1.05, 1.10, 1.15, 1.20, 1.20,
                    1.20, 1.20, 1.20, 1.15, 1.10, 1.00, 0.95, 0.90],
                ['corn', 0.30, 0.30, 0.40, 0.50, 0.60, 0.75, 0.90, 1.05,
                    1.20, 1.20, 1.20, 1.10, 1.00, 0.85, 0.70, 0.60],
            ];
            const ws = XLSX.utils.aoa_to_sheet(sampleData);
            XLSX.utils.book_append_sheet(workbook, ws, 'Kc');
            // Write to buffer
            const buffer = XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' });
            res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
            res.setHeader('Content-Disposition', 'attachment; filename=kc-template.xlsx');
            res.send(buffer);
        }
        catch (error) {
            logger_1.logger.error('Error creating Kc template', error);
            next(error);
        }
    }
}
exports.dataUploadController = new DataUploadController();
//# sourceMappingURL=data-upload.controller.js.map