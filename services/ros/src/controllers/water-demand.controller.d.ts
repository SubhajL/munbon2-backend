import { Request, Response, NextFunction } from 'express';
declare class WaterDemandController {
    /**
     * Calculate water demand for a specific crop week
     */
    calculateWaterDemand(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Calculate water demand for entire crop season
     */
    calculateSeasonalWaterDemand(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get water demand for a particular area for a crop week
     */
    getWaterDemandByCropWeek(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get water demand for entire crop season by week
     */
    getSeasonalWaterDemandByWeek(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get water demand summary for an area
     */
    getWaterDemandSummary(req: Request, res: Response, next: NextFunction): Promise<void>;
}
export declare const waterDemandController: WaterDemandController;
export {};
//# sourceMappingURL=water-demand.controller.d.ts.map