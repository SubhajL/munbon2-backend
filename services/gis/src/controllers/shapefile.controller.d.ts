import { Request, Response, NextFunction } from 'express';
export declare class ShapeFileController {
    private shapeFileService;
    constructor();
    uploadShapeFile: (req: Request, res: Response, next: NextFunction) => Promise<void>;
    externalUpload: (req: Request, res: Response, next: NextFunction) => Promise<void>;
    listUploads: (req: Request, res: Response, next: NextFunction) => Promise<void>;
    getUploadStatus: (req: Request, res: Response, next: NextFunction) => Promise<void>;
    getUploadParcels: (req: Request, res: Response, next: NextFunction) => Promise<void>;
    deleteUpload: (req: Request, res: Response, next: NextFunction) => Promise<void>;
}
//# sourceMappingURL=shapefile.controller.d.ts.map