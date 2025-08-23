import { Request, Response } from 'express';
export declare class ExportController {
    private db;
    constructor();
    exportParcelsGeoJSON(req: Request, res: Response): Promise<void>;
    exportZonesGeoJSON(req: Request, res: Response): Promise<void>;
    exportWaterDemandHeatmap(req: Request, res: Response): Promise<void>;
    customExport(req: Request, res: Response): Promise<Response<any, Record<string, any>> | undefined>;
    private getHeatmapColor;
    private interpolateColor;
    private isValidAttribute;
}
//# sourceMappingURL=export.controller.d.ts.map