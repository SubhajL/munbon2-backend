import { Request, Response, NextFunction } from 'express';
declare class EToDataController {
    /**
     * Get monthly ETo value for a specific month
     */
    getMonthlyETo(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get all monthly ETo values for a station
     */
    getAllMonthlyETo(req: Request, res: Response, next: NextFunction): Promise<void>;
}
export declare const etoDataController: EToDataController;
export {};
//# sourceMappingURL=eto-data.controller.d.ts.map