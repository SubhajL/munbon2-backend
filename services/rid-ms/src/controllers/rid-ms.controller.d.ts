import { Request, Response } from 'express';
export declare class RidMsController {
    getShapeFiles(req: Request, res: Response): Promise<void>;
    getShapeFileById(req: Request, res: Response): Promise<Response<any, Record<string, any>> | undefined>;
    getParcelsByShapeFile(req: Request, res: Response): Promise<void>;
    getParcelsByZone(req: Request, res: Response): Promise<void>;
    getParcelWaterDemand(req: Request, res: Response): Promise<Response<any, Record<string, any>> | undefined>;
    getWaterDemandSummaryByZone(req: Request, res: Response): Promise<Response<any, Record<string, any>> | undefined>;
    getGeoJSON(req: Request, res: Response): Promise<void>;
    getUploadUrl(req: Request, res: Response): Promise<Response<any, Record<string, any>> | undefined>;
    updateWaterDemandMethod(req: Request, res: Response): Promise<Response<any, Record<string, any>> | undefined>;
}
//# sourceMappingURL=rid-ms.controller.d.ts.map