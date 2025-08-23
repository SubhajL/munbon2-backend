import { Request, Response, NextFunction } from 'express';
/**
 * Validate calculation request
 */
export declare const validateCalculation: (req: Request, res: Response, next: NextFunction) => void;
/**
 * Validate batch calculation request
 */
export declare const validateBatchCalculation: (req: Request, res: Response, next: NextFunction) => void;
/**
 * Validate report generation request
 */
export declare const validateReportGeneration: (req: Request, res: Response, next: NextFunction) => void;
/**
 * Validate data import request
 */
export declare const validateDataImport: (req: Request, res: Response, next: NextFunction) => void;
/**
 * Validate date range
 */
export declare const validateDateRange: (req: Request, res: Response, next: NextFunction) => void;
/**
 * Validate pagination parameters
 */
export declare const validatePagination: (req: Request, res: Response, next: NextFunction) => void;
//# sourceMappingURL=rosValidators.d.ts.map