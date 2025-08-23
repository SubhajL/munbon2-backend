import { Request, Response, NextFunction } from 'express';
declare class KcDataController {
    /**
     * Get Kc value for specific crop and week
     */
    getKcValue(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get all Kc values for a crop type
     */
    getAllKcValues(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get crop summary
     */
    getCropSummary(req: Request, res: Response, next: NextFunction): Promise<void>;
}
export declare const kcDataController: KcDataController;
export {};
//# sourceMappingURL=kc-data.controller.d.ts.map