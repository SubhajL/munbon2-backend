import { Request, Response, NextFunction } from 'express';
declare class WaterLevelController {
    /**
     * Get current water level
     */
    getCurrentWaterLevel(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Add water level measurement
     */
    addWaterLevelMeasurement(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Import bulk water level data
     */
    importWaterLevelData(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get water level history
     */
    getWaterLevelHistory(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Update water level
     */
    updateWaterLevel(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Delete water level
     */
    deleteWaterLevel(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get water level statistics
     */
    getWaterLevelStatistics(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get water level trends
     */
    getWaterLevelTrends(req: Request, res: Response, next: NextFunction): Promise<void>;
}
export declare const waterLevelController: WaterLevelController;
export {};
//# sourceMappingURL=water-level.controller.d.ts.map