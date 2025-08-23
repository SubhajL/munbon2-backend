import { ShapeFileMetadata, ParcelData } from '../types';
export declare class DatabaseService {
    private static instance;
    private pool;
    private constructor();
    static getInstance(): DatabaseService;
    initialize(): Promise<void>;
    saveShapeFileMetadata(metadata: ShapeFileMetadata): Promise<void>;
    updateShapeFileMetadata(metadata: Partial<ShapeFileMetadata> & {
        id: string;
    }): Promise<void>;
    saveParcels(parcels: ParcelData[]): Promise<void>;
    getParcelsByIds(parcelIds: string[]): Promise<ParcelData[]>;
    getParcelsByZone(zone: string): Promise<ParcelData[]>;
    getAllParcels(): Promise<ParcelData[]>;
    updateParcel(parcel: ParcelData): Promise<void>;
    private saveWaterDemandHistory;
    private mapRowToParcel;
    close(): Promise<void>;
}
//# sourceMappingURL=database.service.d.ts.map