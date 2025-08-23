import { Polygon, Point } from 'geojson';
export declare enum WaterSourceType {
    RESERVOIR = "reservoir",
    RIVER = "river",
    POND = "pond",
    WELL = "well",
    SPRING = "spring",
    DAM = "dam"
}
export declare class WaterSource {
    id: string;
    code: string;
    name: string;
    nameTh?: string;
    type: WaterSourceType;
    geometry: Polygon | Point;
    area?: number;
    maxCapacity?: number;
    currentVolume?: number;
    waterLevel?: number;
    qualityIndex?: number;
    properties?: Record<string, any>;
    createdAt: Date;
    updatedAt: Date;
}
//# sourceMappingURL=water-source.entity.d.ts.map