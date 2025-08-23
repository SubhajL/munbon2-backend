interface TileRequest {
    z: number;
    x: number;
    y: number;
    layer: string;
}
declare class TileService {
    private tileCache;
    private tileIndices;
    getTile(request: TileRequest): Promise<Buffer>;
    private getFeaturesForTile;
    private buildTileQuery;
    private buildPointQuery;
    private generateVectorTile;
    private tileToBounds;
    private getSimplificationTolerance;
    private getAreaThreshold;
    private shouldRegenerateTileIndex;
    private extractProperties;
    clearTileCache(layer?: string): Promise<void>;
    preGenerateTiles(layer: string, minZoom: number, maxZoom: number, bounds?: number[]): Promise<void>;
}
export declare const tileService: TileService;
export {};
//# sourceMappingURL=tile.service.d.ts.map