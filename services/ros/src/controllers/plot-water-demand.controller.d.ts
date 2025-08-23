import { Request, Response, NextFunction } from 'express';
declare class PlotWaterDemandController {
    /**
     * Calculate water demand for a single plot
     */
    calculatePlotDemand(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Calculate water demand for multiple plots (batch)
     */
    calculateBatchPlotDemand(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get plots by zone or section
     */
    getPlotsByArea(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get plot information
     */
    getPlotInfo(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get historical water demand for a plot
     */
    getPlotHistoricalDemand(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get current week water demand for all active plots
     */
    getCurrentWeekDemand(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Calculate water demand by zone (aggregate all plots in zone)
     */
    calculateZoneDemand(req: Request, res: Response, next: NextFunction): Promise<void>;
}
export declare const plotWaterDemandController: PlotWaterDemandController;
export {};
//# sourceMappingURL=plot-water-demand.controller.d.ts.map