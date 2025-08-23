import { Request, Response } from 'express';
export declare class ZonesController {
    private db;
    constructor();
    listZones(req: Request, res: Response): Promise<Response<any, Record<string, any>> | undefined>;
    getZoneParcels(req: Request, res: Response): Promise<void>;
    getZoneSummary(req: Request, res: Response): Promise<Response<any, Record<string, any>> | undefined>;
    getZoneGeoJSON(req: Request, res: Response): Promise<void>;
    getZoneChanges(req: Request, res: Response): Promise<void>;
}
//# sourceMappingURL=zones.controller.d.ts.map