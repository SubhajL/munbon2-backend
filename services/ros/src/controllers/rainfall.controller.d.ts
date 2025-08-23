import { Request, Response, NextFunction } from 'express';
declare class RainfallController {
    /**
     * Get weekly effective rainfall
     */
    getWeeklyEffectiveRainfall(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Add rainfall data
     */
    addRainfallData(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Import bulk rainfall data
     */
    importRainfallData(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get rainfall history
     */
    getRainfallHistory(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Update rainfall data
     */
    updateRainfallData(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Delete rainfall data
     */
    deleteRainfallData(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get rainfall statistics
     */
    getRainfallStatistics(req: Request, res: Response, next: NextFunction): Promise<void>;
}
export declare const rainfallController: RainfallController;
export {};
//# sourceMappingURL=rainfall.controller.d.ts.map