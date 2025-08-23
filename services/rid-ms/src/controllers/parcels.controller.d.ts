import { Request, Response } from 'express';
export declare class ParcelsController {
    private db;
    constructor();
    listParcels(req: Request, res: Response): Promise<Response<any, Record<string, any>> | undefined>;
    searchParcels(req: Request, res: Response): Promise<Response<any, Record<string, any>> | undefined>;
    getParcelById(req: Request, res: Response): Promise<Response<any, Record<string, any>> | undefined>;
    getParcelHistory(req: Request, res: Response): Promise<void>;
    getParcelsAtDate(req: Request, res: Response): Promise<void>;
    updateParcel(req: Request, res: Response): Promise<Response<any, Record<string, any>> | undefined>;
}
//# sourceMappingURL=parcels.controller.d.ts.map