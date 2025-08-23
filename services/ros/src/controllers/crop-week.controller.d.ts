import { Request, Response, NextFunction } from 'express';
declare class CropWeekController {
    /**
     * Calculate current crop week from planting date
     */
    calculateCurrentCropWeek(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get crop week info for multiple plots
     */
    getCropWeeksForPlots(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Calculate planting date from current crop week
     */
    calculatePlantingDate(req: Request, res: Response, next: NextFunction): Promise<void>;
}
export declare const cropWeekController: CropWeekController;
export {};
//# sourceMappingURL=crop-week.controller.d.ts.map