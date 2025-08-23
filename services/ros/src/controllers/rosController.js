"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.rosController = void 0;
const calculationService_1 = require("../services/calculationService");
const kcService_1 = require("../services/kcService");
const et0Service_1 = require("../services/et0Service");
const rainfallService_1 = require("../services/rainfallService");
const excelService_1 = require("../services/excelService");
const reportService_1 = require("../services/reportService");
const queueService_1 = require("../services/queueService");
const errorHandler_1 = require("../middleware/errorHandler");
class ROSController {
    /**
     * Calculate water demand
     */
    async calculateWaterDemand(req, res, next) {
        try {
            const input = {
                ...req.body,
                calculationDate: new Date(req.body.calculationDate),
                plantings: req.body.plantings.map((p) => ({
                    ...p,
                    plantingDate: new Date(p.plantingDate)
                }))
            };
            const result = await calculationService_1.calculationService.calculateWaterDemand(input);
            res.json({
                success: true,
                data: result,
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Batch calculate for multiple scenarios
     */
    async batchCalculate(req, res, next) {
        try {
            const { scenarios } = req.body;
            if (!Array.isArray(scenarios) || scenarios.length === 0) {
                throw new errorHandler_1.AppError('Scenarios array is required', 400);
            }
            // Queue the batch job
            const job = await queueService_1.queueService.addCalculationJob({
                type: 'batch-calculation',
                scenarios: scenarios
            });
            res.json({
                success: true,
                data: {
                    jobId: job.id,
                    status: 'queued',
                    scenarioCount: scenarios.length
                },
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Import Kc data from Excel
     */
    async importKcData(req, res, next) {
        try {
            if (!req.file) {
                throw new errorHandler_1.AppError('Excel file is required', 400);
            }
            const data = await excelService_1.excelService.parseKcData(req.file.buffer);
            await kcService_1.kcService.importKcData(data);
            res.json({
                success: true,
                data: {
                    recordsImported: data.length,
                    crops: [...new Set(data.map(d => d.cropType))]
                },
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Import ET0 data from Excel
     */
    async importET0Data(req, res, next) {
        try {
            if (!req.file) {
                throw new errorHandler_1.AppError('Excel file is required', 400);
            }
            const data = await excelService_1.excelService.parseET0Data(req.file.buffer);
            await et0Service_1.et0Service.importET0Data(data);
            res.json({
                success: true,
                data: {
                    recordsImported: data.length
                },
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Import rainfall data from Excel
     */
    async importRainfallData(req, res, next) {
        try {
            if (!req.file) {
                throw new errorHandler_1.AppError('Excel file is required', 400);
            }
            const data = await excelService_1.excelService.parseRainfallData(req.file.buffer);
            await rainfallService_1.rainfallService.importRainfallData(data);
            res.json({
                success: true,
                data: {
                    recordsImported: data.length
                },
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Get Kc curve for a crop
     */
    async getKcCurve(req, res, next) {
        try {
            const { cropType } = req.params;
            const curve = await kcService_1.kcService.getKcCurve(cropType);
            res.json({
                success: true,
                data: {
                    cropType,
                    curve
                },
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Get annual ET0 pattern
     */
    async getAnnualET0(req, res, next) {
        try {
            const year = req.query.year ? parseInt(req.query.year) : undefined;
            const pattern = await et0Service_1.et0Service.getAnnualET0Pattern(year);
            res.json({
                success: true,
                data: {
                    year: year || new Date().getFullYear(),
                    pattern
                },
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Get annual rainfall pattern
     */
    async getAnnualRainfall(req, res, next) {
        try {
            const year = req.query.year ? parseInt(req.query.year) : undefined;
            const pattern = await rainfallService_1.rainfallService.getAnnualRainfallPattern(year);
            res.json({
                success: true,
                data: {
                    year: year || new Date().getFullYear(),
                    pattern
                },
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Generate report
     */
    async generateReport(req, res, next) {
        try {
            const reportRequest = req.body;
            const job = await queueService_1.queueService.addReportJob(reportRequest);
            res.json({
                success: true,
                data: {
                    reportId: job.id,
                    status: 'queued'
                },
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Get report status
     */
    async getReport(req, res, next) {
        try {
            const { reportId } = req.params;
            const report = await reportService_1.reportService.getReportStatus(reportId);
            res.json({
                success: true,
                data: report,
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Download report
     */
    async downloadReport(req, res, next) {
        try {
            const { reportId } = req.params;
            const { stream, filename, contentType } = await reportService_1.reportService.getReportFile(reportId);
            res.setHeader('Content-Type', contentType);
            res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
            stream.pipe(res);
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Upload Excel file for processing
     */
    async uploadExcelFile(req, res, next) {
        try {
            if (!req.file) {
                throw new errorHandler_1.AppError('Excel file is required', 400);
            }
            const job = await queueService_1.queueService.addExcelProcessingJob({
                filename: req.file.originalname,
                buffer: req.file.buffer,
                userId: req.userId || 'anonymous'
            });
            res.json({
                success: true,
                data: {
                    jobId: job.id,
                    status: 'queued',
                    filename: req.file.originalname
                },
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Get processing status
     */
    async getProcessingStatus(req, res, next) {
        try {
            const { jobId } = req.params;
            const job = await queueService_1.queueService.getJobStatus(jobId);
            if (!job) {
                throw new errorHandler_1.AppError('Job not found', 404);
            }
            res.json({
                success: true,
                data: {
                    jobId: job.id,
                    status: await job.getState(),
                    progress: job.progress(),
                    result: job.returnvalue,
                    error: job.failedReason
                },
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Get calculation history
     */
    async getCalculationHistory(req, res, next) {
        try {
            const { page = 1, limit = 10, startDate, endDate } = req.query;
            const history = await calculationService_1.calculationService.getCalculationHistory({
                page: parseInt(page),
                limit: parseInt(limit),
                startDate: startDate ? new Date(startDate) : undefined,
                endDate: endDate ? new Date(endDate) : undefined
            });
            res.json({
                success: true,
                data: history,
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Get calculation details
     */
    async getCalculationDetails(req, res, next) {
        try {
            const { calculationId } = req.params;
            const details = await calculationService_1.calculationService.getCalculationById(calculationId);
            if (!details) {
                throw new errorHandler_1.AppError('Calculation not found', 404);
            }
            res.json({
                success: true,
                data: details,
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Get demand pattern visualization data
     */
    async getDemandPattern(req, res, next) {
        try {
            const { cropType, year, period = 'monthly' } = req.query;
            const pattern = await calculationService_1.calculationService.getDemandPattern({
                cropType: cropType,
                year: year ? parseInt(year) : new Date().getFullYear(),
                period: period
            });
            res.json({
                success: true,
                data: pattern,
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Get seasonal analysis
     */
    async getSeasonalAnalysis(req, res, next) {
        try {
            const { year } = req.query;
            const analysis = await calculationService_1.calculationService.getSeasonalAnalysis(year ? parseInt(year) : new Date().getFullYear());
            res.json({
                success: true,
                data: analysis,
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Get available crops
     */
    async getAvailableCrops(req, res, next) {
        try {
            const crops = await kcService_1.kcService.getAvailableCrops();
            res.json({
                success: true,
                data: crops,
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
    /**
     * Get crop information
     */
    async getCropInfo(req, res, next) {
        try {
            const { cropType } = req.params;
            const info = await kcService_1.kcService.getCropInfo(cropType);
            res.json({
                success: true,
                data: info,
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            next(error);
        }
    }
}
exports.rosController = new ROSController();
//# sourceMappingURL=rosController.js.map