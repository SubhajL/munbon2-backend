"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.reportService = exports.ReportService = void 0;
const pdfkit_1 = __importDefault(require("pdfkit"));
const promises_1 = __importDefault(require("fs/promises"));
const path_1 = __importDefault(require("path"));
const logger_1 = require("../utils/logger");
const errorHandler_1 = require("../middleware/errorHandler");
const excelService_1 = require("./excelService");
const reportModel_1 = require("../models/reportModel");
class ReportService {
    reportDir;
    constructor() {
        this.reportDir = process.env.REPORT_TEMP_DIR || './temp/reports';
        this.ensureReportDirectory();
    }
    /**
     * Ensure report directory exists
     */
    async ensureReportDirectory() {
        try {
            await promises_1.default.mkdir(this.reportDir, { recursive: true });
        }
        catch (error) {
            logger_1.logger.error('Error creating report directory:', error);
        }
    }
    /**
     * Generate PDF report
     */
    async generatePDFReport(calculation, options = {}) {
        return new Promise((resolve, reject) => {
            try {
                const doc = new pdfkit_1.default({
                    size: 'A4',
                    margins: { top: 50, bottom: 50, left: 50, right: 50 }
                });
                const chunks = [];
                doc.on('data', chunk => chunks.push(chunk));
                doc.on('end', () => resolve(Buffer.concat(chunks)));
                doc.on('error', reject);
                // Title page
                doc.fontSize(24).text('Water Demand Calculation Report', { align: 'center' });
                doc.fontSize(16).text('Munbon Irrigation Project', { align: 'center' });
                doc.moveDown();
                doc.fontSize(12).text(`Generated: ${new Date().toLocaleDateString()}`, { align: 'center' });
                doc.moveDown(2);
                // Executive Summary
                doc.fontSize(18).text('Executive Summary', { underline: true });
                doc.moveDown();
                doc.fontSize(12);
                doc.text(`Crop Type: ${calculation.cropType}`);
                doc.text(`Calculation Period: ${calculation.calculationPeriod}`);
                doc.text(`Total Area: ${calculation.cropDetails.totalAreaRai.toLocaleString()} rai`);
                doc.text(`Total Water Demand: ${(calculation.totalWaterDemand_m3 / 1e6).toFixed(2)} million m³`);
                doc.moveDown(2);
                // Water Requirements Section
                doc.addPage();
                doc.fontSize(18).text('Water Requirements', { underline: true });
                doc.moveDown();
                // Agricultural demand
                doc.fontSize(14).text('Agricultural Demand');
                doc.fontSize(12);
                doc.text(`ETc: ${calculation.waterRequirement.etc.toFixed(2)} mm`);
                doc.text(`Percolation: ${calculation.waterRequirement.percolation.toFixed(2)} mm`);
                doc.text(`Total Requirement: ${calculation.waterRequirement.total_mm.toFixed(2)} mm`);
                doc.text(`Volume: ${(calculation.waterRequirement.total_m3 / 1000).toFixed(0)} thousand m³`);
                doc.moveDown();
                // Effective rainfall
                doc.fontSize(14).text('Effective Rainfall');
                doc.fontSize(12);
                doc.text(`Amount: ${calculation.effectiveRainfall.amount_mm.toFixed(2)} mm`);
                doc.text(`Volume: ${(calculation.effectiveRainfall.amount_m3 / 1000).toFixed(0)} thousand m³`);
                doc.moveDown();
                // Net irrigation
                doc.fontSize(14).text('Net Irrigation Requirement');
                doc.fontSize(12);
                doc.text(`Amount: ${calculation.netIrrigation.amount_mm.toFixed(2)} mm`);
                doc.text(`Volume: ${(calculation.netIrrigation.amount_m3 / 1000).toFixed(0)} thousand m³`);
                doc.moveDown();
                // Non-agricultural demand
                doc.fontSize(14).text('Non-Agricultural Demand');
                doc.fontSize(12);
                doc.text(`Total: ${(calculation.nonAgriculturalDemand_m3 / 1000).toFixed(0)} thousand m³`);
                doc.moveDown(2);
                // Crop Details
                if (calculation.cropDetails.activeGrowthStages.length > 0) {
                    doc.addPage();
                    doc.fontSize(18).text('Active Plantings', { underline: true });
                    doc.moveDown();
                    // Table header
                    doc.fontSize(10);
                    const tableTop = doc.y;
                    doc.text('Planting ID', 50, tableTop);
                    doc.text('Week', 200, tableTop);
                    doc.text('Kc', 250, tableTop);
                    doc.text('Area (rai)', 300, tableTop);
                    doc.text('Stage', 380, tableTop);
                    doc.moveDown();
                    // Table rows
                    calculation.cropDetails.activeGrowthStages.forEach((stage) => {
                        const y = doc.y;
                        doc.text(stage.plantingId.substring(0, 10), 50, y);
                        doc.text(stage.growthWeek.toString(), 200, y);
                        doc.text(stage.kc.toFixed(2), 250, y);
                        doc.text(stage.areaRai.toLocaleString(), 300, y);
                        doc.text(stage.growthStage, 380, y);
                        doc.moveDown();
                    });
                }
                // Include charts if requested
                if (options.includeCharts) {
                    // This would require canvas/chart generation
                    // Placeholder for chart implementation
                }
                // Parameters used
                doc.addPage();
                doc.fontSize(18).text('Calculation Parameters', { underline: true });
                doc.moveDown();
                doc.fontSize(12);
                doc.text(`Weighted Kc: ${calculation.cropDetails.weightedKc.toFixed(3)}`);
                doc.text(`ET0: ${calculation.cropDetails.et0.toFixed(2)} mm`);
                doc.text(`Calculation Method: ${calculation.calculationMethod}`);
                doc.text(`Calculation Date: ${new Date(calculation.calculationDate).toLocaleDateString()}`);
                doc.end();
            }
            catch (error) {
                logger_1.logger.error('Error generating PDF report:', error);
                reject(error);
            }
        });
    }
    /**
     * Generate Excel report
     */
    async generateExcelReport(calculation, options = {}) {
        try {
            const reportData = {
                weeklyResults: [this.formatCalculationForExcel(calculation)],
                monthlySummary: [{
                        month: new Date(calculation.calculationDate).getMonth() + 1,
                        year: new Date(calculation.calculationDate).getFullYear(),
                        totalDemand_m3: calculation.totalWaterDemand_m3,
                        agriculturalDemand_m3: calculation.netIrrigation.amount_m3,
                        nonAgriculturalDemand_m3: calculation.nonAgriculturalDemand_m3
                    }],
                annualSummary: [{
                        category: 'Agricultural',
                        annual_m3: calculation.netIrrigation.amount_m3,
                        million_m3: calculation.netIrrigation.amount_m3 / 1e6
                    }, {
                        category: 'Non-Agricultural',
                        annual_m3: calculation.nonAgriculturalDemand_m3,
                        million_m3: calculation.nonAgriculturalDemand_m3 / 1e6
                    }, {
                        category: 'Total',
                        annual_m3: calculation.totalWaterDemand_m3,
                        million_m3: calculation.totalWaterDemand_m3 / 1e6
                    }],
                parameters: {
                    cropType: calculation.cropType,
                    totalArea_rai: calculation.cropDetails.totalAreaRai,
                    weightedKc: calculation.cropDetails.weightedKc,
                    et0: calculation.cropDetails.et0,
                    calculationDate: calculation.calculationDate,
                    calculationPeriod: calculation.calculationPeriod
                }
            };
            return await excelService_1.excelService.generateExcelReport(reportData);
        }
        catch (error) {
            logger_1.logger.error('Error generating Excel report:', error);
            throw new errorHandler_1.AppError('Failed to generate Excel report', 500);
        }
    }
    /**
     * Generate CSV report
     */
    async generateCSVReport(calculation, options = {}) {
        try {
            const csvData = [this.formatCalculationForExcel(calculation)];
            return await excelService_1.excelService.generateCSVReport(csvData);
        }
        catch (error) {
            logger_1.logger.error('Error generating CSV report:', error);
            throw new errorHandler_1.AppError('Failed to generate CSV report', 500);
        }
    }
    /**
     * Format calculation for Excel/CSV export
     */
    formatCalculationForExcel(calculation) {
        return {
            date: calculation.calculationDate,
            cropType: calculation.cropType,
            totalArea_rai: calculation.cropDetails.totalAreaRai,
            weightedKc: calculation.cropDetails.weightedKc,
            et0_mm: calculation.cropDetails.et0,
            etc_mm: calculation.waterRequirement.etc,
            percolation_mm: calculation.waterRequirement.percolation,
            totalRequirement_mm: calculation.waterRequirement.total_mm,
            totalRequirement_m3: calculation.waterRequirement.total_m3,
            effectiveRainfall_mm: calculation.effectiveRainfall.amount_mm,
            effectiveRainfall_m3: calculation.effectiveRainfall.amount_m3,
            netIrrigation_mm: calculation.netIrrigation.amount_mm,
            netIrrigation_m3: calculation.netIrrigation.amount_m3,
            nonAgriculturalDemand_m3: calculation.nonAgriculturalDemand_m3,
            totalDemand_m3: calculation.totalWaterDemand_m3
        };
    }
    /**
     * Save report to database and filesystem
     */
    async saveReport(reportData) {
        try {
            // Generate filename
            const filename = `report_${reportData.calculationId}_${Date.now()}.${reportData.format}`;
            const filePath = path_1.default.join(this.reportDir, filename);
            // Save to filesystem
            if (Buffer.isBuffer(reportData.data)) {
                await promises_1.default.writeFile(filePath, reportData.data);
            }
            else {
                await promises_1.default.writeFile(filePath, reportData.data, 'utf8');
            }
            // Save metadata to database
            const report = await reportModel_1.ReportModel.create({
                calculationId: reportData.calculationId,
                format: reportData.format,
                filename: filename,
                filePath: filePath,
                metadata: reportData.metadata,
                status: 'completed',
                generatedAt: new Date()
            });
            logger_1.logger.info(`Report saved: ${filename}`);
            return report;
        }
        catch (error) {
            logger_1.logger.error('Error saving report:', error);
            throw new errorHandler_1.AppError('Failed to save report', 500);
        }
    }
    /**
     * Get report status
     */
    async getReportStatus(reportId) {
        try {
            const report = await reportModel_1.ReportModel.findById(reportId);
            if (!report) {
                throw new errorHandler_1.AppError('Report not found', 404);
            }
            return {
                id: report._id,
                status: report.status,
                format: report.format,
                generatedAt: report.generatedAt,
                metadata: report.metadata
            };
        }
        catch (error) {
            logger_1.logger.error('Error getting report status:', error);
            throw error;
        }
    }
    /**
     * Get report file for download
     */
    async getReportFile(reportId) {
        try {
            const report = await reportModel_1.ReportModel.findById(reportId);
            if (!report) {
                throw new errorHandler_1.AppError('Report not found', 404);
            }
            // Check if file exists
            await promises_1.default.access(report.filePath);
            // Determine content type
            const contentType = this.getContentType(report.format);
            // Create read stream
            const stream = promises_1.default.createReadStream(report.filePath);
            return {
                stream,
                filename: report.filename,
                contentType
            };
        }
        catch (error) {
            logger_1.logger.error('Error getting report file:', error);
            throw new errorHandler_1.AppError('Failed to retrieve report file', 500);
        }
    }
    /**
     * Get content type for format
     */
    getContentType(format) {
        const types = {
            pdf: 'application/pdf',
            excel: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            csv: 'text/csv'
        };
        return types[format] || 'application/octet-stream';
    }
    /**
     * Clean old reports
     */
    async cleanOldReports(daysToKeep = 30) {
        try {
            const cutoffDate = new Date();
            cutoffDate.setDate(cutoffDate.getDate() - daysToKeep);
            // Find old reports
            const oldReports = await reportModel_1.ReportModel.find({
                generatedAt: { $lt: cutoffDate }
            });
            // Delete files and records
            for (const report of oldReports) {
                try {
                    await promises_1.default.unlink(report.filePath);
                }
                catch (error) {
                    logger_1.logger.warn(`Could not delete report file: ${report.filePath}`);
                }
            }
            // Delete from database
            await reportModel_1.ReportModel.deleteMany({
                generatedAt: { $lt: cutoffDate }
            });
            logger_1.logger.info(`Cleaned ${oldReports.length} old reports`);
        }
        catch (error) {
            logger_1.logger.error('Error cleaning old reports:', error);
        }
    }
}
exports.ReportService = ReportService;
exports.reportService = new ReportService();
//# sourceMappingURL=reportService.js.map