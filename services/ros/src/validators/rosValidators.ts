import { Request, Response, NextFunction } from 'express';
import Joi from 'joi';
import { AppError } from '../middleware/errorHandler';

// Calculation request schema
const calculationSchema = Joi.object({
  cropType: Joi.string().required().min(1).max(100),
  plantings: Joi.array().items(
    Joi.object({
      plantingDate: Joi.date().iso().required(),
      areaRai: Joi.number().positive().required(),
      growthDays: Joi.number().integer().min(0).optional()
    })
  ).min(1).required(),
  calculationDate: Joi.date().iso().required(),
  calculationPeriod: Joi.string().valid('daily', 'weekly', 'monthly').required(),
  nonAgriculturalDemands: Joi.object({
    domestic: Joi.number().min(0).optional(),
    industrial: Joi.number().min(0).optional(),
    ecosystem: Joi.number().min(0).optional(),
    other: Joi.number().min(0).optional()
  }).optional()
});

// Batch calculation schema
const batchCalculationSchema = Joi.object({
  scenarios: Joi.array().items(calculationSchema).min(1).max(100).required()
});

// Report generation schema
const reportGenerationSchema = Joi.object({
  calculationId: Joi.string().required(),
  format: Joi.string().valid('pdf', 'csv', 'excel').required(),
  includeCharts: Joi.boolean().optional(),
  includeHistorical: Joi.boolean().optional(),
  dateRange: Joi.object({
    start: Joi.date().iso().required(),
    end: Joi.date().iso().greater(Joi.ref('start')).required()
  }).optional(),
  language: Joi.string().valid('en', 'th').optional()
});

// Data import schema
const dataImportSchema = Joi.object({
  dataType: Joi.string().valid('kc', 'et0', 'rainfall').required(),
  year: Joi.number().integer().min(2000).max(2100).optional(),
  location: Joi.string().optional()
});

/**
 * Validate calculation request
 */
export const validateCalculation = (req: Request, res: Response, next: NextFunction) => {
  const { error } = calculationSchema.validate(req.body, { abortEarly: false });
  
  if (error) {
    const errors = error.details.map(detail => ({
      field: detail.path.join('.'),
      message: detail.message
    }));
    
    return next(new AppError(`Validation error: ${errors.map(e => e.message).join(', ')}`, 400));
  }
  
  next();
};

/**
 * Validate batch calculation request
 */
export const validateBatchCalculation = (req: Request, res: Response, next: NextFunction) => {
  const { error } = batchCalculationSchema.validate(req.body, { abortEarly: false });
  
  if (error) {
    const errors = error.details.map(detail => ({
      field: detail.path.join('.'),
      message: detail.message
    }));
    
    return next(new AppError(`Validation error: ${errors.map(e => e.message).join(', ')}`, 400));
  }
  
  next();
};

/**
 * Validate report generation request
 */
export const validateReportGeneration = (req: Request, res: Response, next: NextFunction) => {
  const { error } = reportGenerationSchema.validate(req.body, { abortEarly: false });
  
  if (error) {
    const errors = error.details.map(detail => ({
      field: detail.path.join('.'),
      message: detail.message
    }));
    
    return next(new AppError(`Validation error: ${errors.map(e => e.message).join(', ')}`, 400));
  }
  
  next();
};

/**
 * Validate data import request
 */
export const validateDataImport = (req: Request, res: Response, next: NextFunction) => {
  if (!req.file) {
    return next(new AppError('File is required for data import', 400));
  }

  const allowedMimeTypes = [
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/csv'
  ];

  if (!allowedMimeTypes.includes(req.file.mimetype)) {
    return next(new AppError('Invalid file type. Only Excel and CSV files are allowed', 400));
  }

  const { error } = dataImportSchema.validate(req.body, { abortEarly: false });
  
  if (error) {
    const errors = error.details.map(detail => ({
      field: detail.path.join('.'),
      message: detail.message
    }));
    
    return next(new AppError(`Validation error: ${errors.map(e => e.message).join(', ')}`, 400));
  }
  
  next();
};

/**
 * Validate date range
 */
export const validateDateRange = (req: Request, res: Response, next: NextFunction) => {
  const { startDate, endDate } = req.query;

  if (startDate && endDate) {
    const start = new Date(startDate as string);
    const end = new Date(endDate as string);

    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
      return next(new AppError('Invalid date format', 400));
    }

    if (start > end) {
      return next(new AppError('Start date must be before end date', 400));
    }

    // Maximum range of 1 year
    const maxRange = 365 * 24 * 60 * 60 * 1000; // 1 year in milliseconds
    if (end.getTime() - start.getTime() > maxRange) {
      return next(new AppError('Date range cannot exceed 1 year', 400));
    }
  }

  next();
};

/**
 * Validate pagination parameters
 */
export const validatePagination = (req: Request, res: Response, next: NextFunction) => {
  const { page = 1, limit = 10 } = req.query;

  const pageNum = parseInt(page as string);
  const limitNum = parseInt(limit as string);

  if (isNaN(pageNum) || pageNum < 1) {
    return next(new AppError('Page must be a positive integer', 400));
  }

  if (isNaN(limitNum) || limitNum < 1 || limitNum > 100) {
    return next(new AppError('Limit must be between 1 and 100', 400));
  }

  // Attach to request for use in controllers
  req.query.page = pageNum.toString();
  req.query.limit = limitNum.toString();

  next();
};