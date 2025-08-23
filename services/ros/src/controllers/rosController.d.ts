import { Request, Response, NextFunction } from 'express';
declare class ROSController {
    /**
     * Calculate water demand
     */
    calculateWaterDemand(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Batch calculate for multiple scenarios
     */
    batchCalculate(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Import Kc data from Excel
     */
    importKcData(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Import ET0 data from Excel
     */
    importET0Data(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Import rainfall data from Excel
     */
    importRainfallData(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get Kc curve for a crop
     */
    getKcCurve(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get annual ET0 pattern
     */
    getAnnualET0(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get annual rainfall pattern
     */
    getAnnualRainfall(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Generate report
     */
    generateReport(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get report status
     */
    getReport(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Download report
     */
    downloadReport(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Upload Excel file for processing
     */
    uploadExcelFile(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get processing status
     */
    getProcessingStatus(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get calculation history
     */
    getCalculationHistory(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get calculation details
     */
    getCalculationDetails(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get demand pattern visualization data
     */
    getDemandPattern(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get seasonal analysis
     */
    getSeasonalAnalysis(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get available crops
     */
    getAvailableCrops(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get crop information
     */
    getCropInfo(req: Request, res: Response, next: NextFunction): Promise<void>;
}
export declare const rosController: ROSController;
export {};
//# sourceMappingURL=rosController.d.ts.map