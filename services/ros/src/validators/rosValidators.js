"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.validatePagination = exports.validateDateRange = exports.validateDataImport = exports.validateReportGeneration = exports.validateBatchCalculation = exports.validateCalculation = void 0;
const joi_1 = __importDefault(require("joi"));
const errorHandler_1 = require("../middleware/errorHandler");
// Calculation request schema
const calculationSchema = joi_1.default.object({
    cropType: joi_1.default.string().required().min(1).max(100),
    plantings: joi_1.default.array().items(joi_1.default.object({
        plantingDate: joi_1.default.date().iso().required(),
        areaRai: joi_1.default.number().positive().required(),
        growthDays: joi_1.default.number().integer().min(0).optional()
    })).min(1).required(),
    calculationDate: joi_1.default.date().iso().required(),
    calculationPeriod: joi_1.default.string().valid('daily', 'weekly', 'monthly').required(),
    nonAgriculturalDemands: joi_1.default.object({
        domestic: joi_1.default.number().min(0).optional(),
        industrial: joi_1.default.number().min(0).optional(),
        ecosystem: joi_1.default.number().min(0).optional(),
        other: joi_1.default.number().min(0).optional()
    }).optional()
});
// Batch calculation schema
const batchCalculationSchema = joi_1.default.object({
    scenarios: joi_1.default.array().items(calculationSchema).min(1).max(100).required()
});
// Report generation schema
const reportGenerationSchema = joi_1.default.object({
    calculationId: joi_1.default.string().required(),
    format: joi_1.default.string().valid('pdf', 'csv', 'excel').required(),
    includeCharts: joi_1.default.boolean().optional(),
    includeHistorical: joi_1.default.boolean().optional(),
    dateRange: joi_1.default.object({
        start: joi_1.default.date().iso().required(),
        end: joi_1.default.date().iso().greater(joi_1.default.ref('start')).required()
    }).optional(),
    language: joi_1.default.string().valid('en', 'th').optional()
});
// Data import schema
const dataImportSchema = joi_1.default.object({
    dataType: joi_1.default.string().valid('kc', 'et0', 'rainfall').required(),
    year: joi_1.default.number().integer().min(2000).max(2100).optional(),
    location: joi_1.default.string().optional()
});
/**
 * Validate calculation request
 */
const validateCalculation = (req, res, next) => {
    const { error } = calculationSchema.validate(req.body, { abortEarly: false });
    if (error) {
        const errors = error.details.map(detail => ({
            field: detail.path.join('.'),
            message: detail.message
        }));
        return next(new errorHandler_1.AppError(`Validation error: ${errors.map(e => e.message).join(', ')}`, 400));
    }
    next();
};
exports.validateCalculation = validateCalculation;
/**
 * Validate batch calculation request
 */
const validateBatchCalculation = (req, res, next) => {
    const { error } = batchCalculationSchema.validate(req.body, { abortEarly: false });
    if (error) {
        const errors = error.details.map(detail => ({
            field: detail.path.join('.'),
            message: detail.message
        }));
        return next(new errorHandler_1.AppError(`Validation error: ${errors.map(e => e.message).join(', ')}`, 400));
    }
    next();
};
exports.validateBatchCalculation = validateBatchCalculation;
/**
 * Validate report generation request
 */
const validateReportGeneration = (req, res, next) => {
    const { error } = reportGenerationSchema.validate(req.body, { abortEarly: false });
    if (error) {
        const errors = error.details.map(detail => ({
            field: detail.path.join('.'),
            message: detail.message
        }));
        return next(new errorHandler_1.AppError(`Validation error: ${errors.map(e => e.message).join(', ')}`, 400));
    }
    next();
};
exports.validateReportGeneration = validateReportGeneration;
/**
 * Validate data import request
 */
const validateDataImport = (req, res, next) => {
    if (!req.file) {
        return next(new errorHandler_1.AppError('File is required for data import', 400));
    }
    const allowedMimeTypes = [
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/csv'
    ];
    if (!allowedMimeTypes.includes(req.file.mimetype)) {
        return next(new errorHandler_1.AppError('Invalid file type. Only Excel and CSV files are allowed', 400));
    }
    const { error } = dataImportSchema.validate(req.body, { abortEarly: false });
    if (error) {
        const errors = error.details.map(detail => ({
            field: detail.path.join('.'),
            message: detail.message
        }));
        return next(new errorHandler_1.AppError(`Validation error: ${errors.map(e => e.message).join(', ')}`, 400));
    }
    next();
};
exports.validateDataImport = validateDataImport;
/**
 * Validate date range
 */
const validateDateRange = (req, res, next) => {
    const { startDate, endDate } = req.query;
    if (startDate && endDate) {
        const start = new Date(startDate);
        const end = new Date(endDate);
        if (isNaN(start.getTime()) || isNaN(end.getTime())) {
            return next(new errorHandler_1.AppError('Invalid date format', 400));
        }
        if (start > end) {
            return next(new errorHandler_1.AppError('Start date must be before end date', 400));
        }
        // Maximum range of 1 year
        const maxRange = 365 * 24 * 60 * 60 * 1000; // 1 year in milliseconds
        if (end.getTime() - start.getTime() > maxRange) {
            return next(new errorHandler_1.AppError('Date range cannot exceed 1 year', 400));
        }
    }
    next();
};
exports.validateDateRange = validateDateRange;
/**
 * Validate pagination parameters
 */
const validatePagination = (req, res, next) => {
    const { page = 1, limit = 10 } = req.query;
    const pageNum = parseInt(page);
    const limitNum = parseInt(limit);
    if (isNaN(pageNum) || pageNum < 1) {
        return next(new errorHandler_1.AppError('Page must be a positive integer', 400));
    }
    if (isNaN(limitNum) || limitNum < 1 || limitNum > 100) {
        return next(new errorHandler_1.AppError('Limit must be between 1 and 100', 400));
    }
    // Attach to request for use in controllers
    req.query.page = pageNum.toString();
    req.query.limit = limitNum.toString();
    next();
};
exports.validatePagination = validatePagination;
//# sourceMappingURL=rosValidators.js.map