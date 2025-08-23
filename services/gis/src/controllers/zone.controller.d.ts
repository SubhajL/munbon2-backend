import { Request, Response, NextFunction } from 'express';
declare class ZoneController {
    getAllZones(req: Request, res: Response, next: NextFunction): Promise<void>;
    getZoneById(req: Request, res: Response, next: NextFunction): Promise<void>;
    queryZones(req: Request, res: Response, next: NextFunction): Promise<void>;
    getZoneStatistics(req: Request, res: Response, next: NextFunction): Promise<void>;
    getParcelsInZone(req: Request, res: Response, next: NextFunction): Promise<void>;
    getWaterDistribution(req: Request, res: Response, next: NextFunction): Promise<void>;
    createZone(req: Request, res: Response, next: NextFunction): Promise<void>;
    updateZone(req: Request, res: Response, next: NextFunction): Promise<void>;
    updateZoneGeometry(req: Request, res: Response, next: NextFunction): Promise<void>;
    deleteZone(req: Request, res: Response, next: NextFunction): Promise<void>;
    bulkImportZones(req: Request, res: Response, next: NextFunction): Promise<void>;
    bulkUpdateZones(req: Request, res: Response, next: NextFunction): Promise<void>;
}
export declare const zoneController: ZoneController;
export {};
//# sourceMappingURL=zone.controller.d.ts.map