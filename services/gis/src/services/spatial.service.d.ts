import * as turf from '@turf/turf';
import { Feature, FeatureCollection, Geometry } from 'geojson';
interface SpatialQueryOptions {
    geometry?: Geometry;
    distance?: number;
    unit?: turf.Units;
    properties?: string[];
    limit?: number;
    offset?: number;
}
interface BufferOptions {
    distance: number;
    unit?: turf.Units;
    steps?: number;
}
declare class SpatialService {
    findWithinBounds(tableName: string, bounds: [number, number, number, number], options?: SpatialQueryOptions): Promise<FeatureCollection>;
    findWithinDistance(tableName: string, center: [number, number], distance: number, unit?: turf.Units, options?: SpatialQueryOptions): Promise<FeatureCollection>;
    findIntersecting(tableName: string, geometry: Geometry, options?: SpatialQueryOptions): Promise<FeatureCollection>;
    calculateArea(geometry: Geometry, unit?: string): Promise<number>;
    calculateLength(geometry: Geometry, unit?: string): Promise<number>;
    buffer(geometry: Geometry, options: BufferOptions): Promise<Feature>;
    union(geometries: Geometry[]): Promise<Feature>;
    intersection(geometry1: Geometry, geometry2: Geometry): Promise<Feature | null>;
    simplify(geometry: Geometry, tolerance?: number, highQuality?: boolean): Promise<Feature>;
    transform(geometry: Geometry, fromSRID: number, toSRID: number): Promise<Feature>;
    routeOptimization(start: [number, number], end: [number, number], waypoints?: Array<[number, number]>): Promise<Feature>;
    getElevation(lng: number, lat: number): Promise<number>;
    private extractProperties;
}
export declare const spatialService: SpatialService;
export {};
//# sourceMappingURL=spatial.service.d.ts.map