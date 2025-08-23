import { Parcel } from '../models/parcel.entity';
import { Polygon } from 'geojson';
interface ParcelQuery {
    page: number;
    limit: number;
    includeGeometry?: boolean;
    filters?: {
        zoneId?: string;
        landUseType?: string;
        irrigationStatus?: string;
    };
}
interface CropPlan {
    parcelId: string;
    season: string;
    year: number;
    cropType: string;
    plantingDate: Date;
    expectedHarvestDate: Date;
    estimatedYield: number;
    waterRequirement: number;
    status: string;
}
declare class ParcelService {
    private parcelRepository;
    private zoneRepository;
    constructor();
    getAllParcels(query: ParcelQuery): Promise<any>;
    getParcelById(id: string): Promise<Parcel | null>;
    queryParcels(query: any): Promise<Parcel[]>;
    getParcelHistory(parcelId: string, dateRange: any): Promise<any>;
    getParcelsByOwner(ownerId: string, options: any): Promise<any>;
    getCropPlan(parcelId: string, options: any): Promise<CropPlan | null>;
    updateCropPlan(parcelId: string, planData: any): Promise<CropPlan>;
    createParcel(data: any): Promise<Parcel>;
    updateParcel(id: string, data: any): Promise<Parcel>;
    updateParcelGeometry(id: string, geometry: Polygon): Promise<Parcel>;
    transferOwnership(id: string, transferData: any): Promise<any>;
    deleteParcel(id: string): Promise<void>;
    bulkImportParcels(data: any, options: any): Promise<any>;
    bulkUpdateParcels(parcels: any[]): Promise<any>;
    mergeParcels(parcelIds: string[], newParcelData: any): Promise<Parcel>;
    splitParcel(id: string, splitData: any): Promise<Parcel[]>;
    private updateZoneStatistics;
}
export declare const parcelService: ParcelService;
export {};
//# sourceMappingURL=parcel.service.d.ts.map