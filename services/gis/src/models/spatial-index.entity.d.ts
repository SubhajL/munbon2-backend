import { Polygon } from 'geojson';
export declare class SpatialIndex {
    id: string;
    entityType: string;
    entityId: string;
    bounds: Polygon;
    tileX: number;
    tileY: number;
    zoom: number;
    minZoom: number;
    maxZoom: number;
    createdAt: Date;
}
//# sourceMappingURL=spatial-index.entity.d.ts.map