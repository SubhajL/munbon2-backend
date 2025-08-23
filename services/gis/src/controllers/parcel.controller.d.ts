import { Request, Response, NextFunction } from 'express';
declare class ParcelController {
    getAllParcels(req: Request, res: Response, next: NextFunction): Promise<void>;
    getParcelById(req: Request, res: Response, next: NextFunction): Promise<void>;
    queryParcels(req: Request, res: Response, next: NextFunction): Promise<void>;
    getParcelHistory(req: Request, res: Response, next: NextFunction): Promise<void>;
    getParcelsByOwner(req: Request, res: Response, next: NextFunction): Promise<void>;
    getCropPlan(req: Request, res: Response, next: NextFunction): Promise<void>;
    updateCropPlan(req: Request, res: Response, next: NextFunction): Promise<void>;
    createParcel(req: Request, res: Response, next: NextFunction): Promise<void>;
    updateParcel(req: Request, res: Response, next: NextFunction): Promise<void>;
    updateParcelGeometry(req: Request, res: Response, next: NextFunction): Promise<void>;
    transferOwnership(req: Request, res: Response, next: NextFunction): Promise<void>;
    deleteParcel(req: Request, res: Response, next: NextFunction): Promise<void>;
    bulkImportParcels(req: Request, res: Response, next: NextFunction): Promise<void>;
    bulkUpdateParcels(req: Request, res: Response, next: NextFunction): Promise<void>;
    mergeParcels(req: Request, res: Response, next: NextFunction): Promise<void>;
    splitParcel(req: Request, res: Response, next: NextFunction): Promise<void>;
}
export declare const parcelController: ParcelController;
export {};
//# sourceMappingURL=parcel.controller.d.ts.map