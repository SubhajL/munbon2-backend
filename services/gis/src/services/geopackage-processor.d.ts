import { Parcel } from '../models/parcel.entity';
import { Zone } from '../models/zone.entity';
interface ProcessingResult {
    parcels: Partial<Parcel>[];
    zones: Partial<Zone>[];
    metadata: {
        totalFeatures: number;
        processedFeatures: number;
        failedFeatures: number;
        sourceSRS?: string;
        tableName: string;
    };
}
export declare class GeoPackageProcessor {
    private parcelRepository;
    private zoneRepository;
    processGeoPackageFile(filePath: string, uploadId: string): Promise<ProcessingResult[]>;
    private processFeatureTable;
    private processFeature;
    private transformGeometry;
    private getProjectionString;
    private calculateAreaHectares;
    private calculateAreaRai;
    private isZoneFeature;
    saveProcessingResults(results: ProcessingResult[]): Promise<{
        totalParcels: number;
        totalZones: number;
        errors: string[];
    }>;
}
export {};
//# sourceMappingURL=geopackage-processor.d.ts.map