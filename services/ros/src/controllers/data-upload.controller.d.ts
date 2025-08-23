import { Request, Response, NextFunction } from 'express';
declare class DataUploadController {
    /**
     * Upload and import ETo data from Excel
     */
    uploadEToData(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Upload and import Kc data from Excel
     */
    uploadKcData(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Download ETo template Excel file
     */
    downloadEToTemplate(req: Request, res: Response, next: NextFunction): Promise<void>;
    /**
     * Download Kc template Excel file
     */
    downloadKcTemplate(req: Request, res: Response, next: NextFunction): Promise<void>;
}
export declare const dataUploadController: DataUploadController;
export {};
//# sourceMappingURL=data-upload.controller.d.ts.map