import { Request, Response, NextFunction } from 'express';
declare class TileController {
    getTile(req: Request, res: Response, next: NextFunction): Promise<void>;
    getTileMetadata(req: Request, res: Response, next: NextFunction): Promise<void>;
    getAvailableLayers(req: Request, res: Response, next: NextFunction): Promise<void>;
    getStyle(req: Request, res: Response, next: NextFunction): Promise<void>;
    clearTileCache(req: Request, res: Response, next: NextFunction): Promise<void>;
    preGenerateTiles(req: Request, res: Response, next: NextFunction): Promise<void>;
    getGenerationStatus(req: Request, res: Response, next: NextFunction): Promise<void>;
    updateLayerConfig(req: Request, res: Response, next: NextFunction): Promise<void>;
    private getLayerDescription;
    private getLayerFields;
    private getStyleLayers;
}
export declare const tileController: TileController;
export {};
//# sourceMappingURL=tile.controller.d.ts.map