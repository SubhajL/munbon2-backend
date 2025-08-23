export interface RIDShapefileProperties {
    PARCEL_SEQ: string;
    sub_member: number;
    parcel_area_rai: number;
    data_date_process: string;
    start_int: string;
    wpet: number;
    age: number;
    wprod: number;
    plant_id: string;
    yield_at_mc_kgpr: number;
    season_irr_m3_per_rai: number;
    auto_note: string;
}
export declare const ZONE_PLANTING_DATES: {
    1: string;
    2: string;
    3: string;
    4: string;
    5: string;
    6: string;
};
export interface RIDShapefileFeature {
    type: 'Feature';
    geometry: {
        type: 'Polygon' | 'MultiPolygon';
        coordinates: number[][][] | number[][][][];
    };
    properties: RIDShapefileProperties;
}
export interface RIDShapefileCollection {
    type: 'FeatureCollection';
    features: RIDShapefileFeature[];
    crs?: {
        type: 'name';
        properties: {
            name: 'EPSG:32648';
        };
    };
}
//# sourceMappingURL=rid-shapefile.types.d.ts.map