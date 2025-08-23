import { Request, Response, NextFunction } from 'express';
declare class PlotPlantingDateController {
    /**
     * Update planting date for a single plot
     */
    updatePlotPlantingDate(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Batch update planting dates
     */
    batchUpdatePlantingDates(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get plots by planting date range
     */
    getPlotsByPlantingDateRange(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get upcoming planting schedules
     */
    getUpcomingPlantingSchedules(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Update crop status
     */
    updateCropStatus(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get plots ready for harvest
     */
    getPlotsReadyForHarvest(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get planting date statistics by zone
     */
    getPlantingDateStatsByZone(req: Request, res: Response, next: NextFunction): Promise<void>;
}
export declare const plotPlantingDateController: PlotPlantingDateController;
export {};
//# sourceMappingURL=plot-planting-date.controller.d.ts.map