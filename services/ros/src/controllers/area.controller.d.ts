import { Request, Response, NextFunction } from 'express';
declare class AreaController {
    /**
     * Create a new area
     */
    createArea(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get area by ID
     */
    getAreaById(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get areas by type
     */
    getAreasByType(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get child areas
     */
    getChildAreas(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Update area
     */
    updateArea(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Delete area
     */
    deleteArea(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get area hierarchy
     */
    getAreaHierarchy(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Calculate total area
     */
    calculateTotalArea(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Import areas
     */
    importAreas(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Get area statistics
     */
    getAreaStatistics(req: Request, res: Response, next: NextFunction): Promise<void>;
}
export declare const areaController: AreaController;
export {};
//# sourceMappingURL=area.controller.d.ts.map