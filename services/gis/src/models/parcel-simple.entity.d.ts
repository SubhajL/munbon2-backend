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
export declare class ParcelSimple {
    id: string;
    parcelCode: string;
    uploadId: string;
    zoneId: string;
    geometry: any;
    centroid?: any;
    area: number;
    perimeter?: number;
    status: ParcelStatus;
    landUseType: LandUseType;
    ownerId?: string;
    ownerName?: string;
    cropType?: string;
    attributes?: Record<string, any>;
    properties?: Record<string, any>;
    createdAt: Date;
    updatedAt: Date;
}
//# sourceMappingURL=parcel-simple.entity.d.ts.map