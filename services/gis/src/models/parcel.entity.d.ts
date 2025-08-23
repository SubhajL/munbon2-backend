import { Geometry } from 'geojson';
import { Zone } from './zone.entity';
export declare enum ParcelStatus {
    ACTIVE = "active",
    INACTIVE = "inactive",
    ABANDONED = "abandoned",
    CONVERTING = "converting"
}
export declare enum LandUseType {
    RICE = "rice",
    VEGETABLE = "vegetable",
    FRUIT = "fruit",
    AQUACULTURE = "aquaculture",
    LIVESTOCK = "livestock",
    MIXED = "mixed",
    FALLOW = "fallow",
    OTHER = "other"
}
export declare enum IrrigationMethod {
    FLOODING = "flooding",
    FURROW = "furrow",
    SPRINKLER = "sprinkler",
    DRIP = "drip",
    CENTER_PIVOT = "center_pivot",
    MANUAL = "manual"
}
export declare class Parcel {
    id: string;
    plotCode: string;
    farmerId: string;
    zoneId: string;
    areaHectares: number;
    areaRai: number;
    boundary: Geometry;
    currentCropType?: string;
    plantingDate?: Date;
    expectedHarvestDate?: Date;
    soilType?: string;
    properties?: {
        uploadId?: string;
        ridAttributes?: {
            parcelAreaRai?: number;
            dataDateProcess?: Date;
            startInt?: Date;
            wpet?: number;
            age?: number;
            wprod?: number;
            plantId?: string;
            yieldAtMcKgpr?: number;
            seasonIrrM3PerRai?: number;
            autoNote?: string;
        };
        waterLevel?: number;
        cropHeight?: number;
        lastUpdated?: Date;
        geometry?: any;
        cropType?: string;
        ownerName?: string;
        ownerId?: string;
        subZone?: string;
        landUseType?: string;
    };
    zone: Zone;
    createdAt: Date;
    updatedAt: Date;
    get geoJSON(): any;
}
//# sourceMappingURL=parcel.entity.d.ts.map