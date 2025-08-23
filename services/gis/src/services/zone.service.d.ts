import { Zone } from '../models/zone.entity';
import { Polygon } from 'geojson';
interface ZoneQuery {
    page: number;
    limit: number;
    includeGeometry?: boolean;
}
interface ZoneStatistics {
    totalArea: number;
    totalParcels: number;
    irrigatedArea: number;
    nonIrrigatedArea: number;
    cropTypes: Record<string, number>;
    waterUsage: {
        current: number;
        allocated: number;
        percentage: number;
    };
}
declare class ZoneService {
    private zoneRepository;
    private parcelRepository;
    constructor();
    getAllZones(query: ZoneQuery): Promise<any>;
    getZoneById(id: string): Promise<Zone | null>;
    queryZones(query: any): Promise<Zone[]>;
    getZoneStatistics(zoneId: string): Promise<ZoneStatistics>;
    getParcelsInZone(zoneId: string, options: {
        page: number;
        limit: number;
    }): Promise<any>;
    getWaterDistribution(zoneId: string, dateRange: any): Promise<any>;
    createZone(data: any): Promise<Zone>;
    updateZone(id: string, data: any): Promise<Zone>;
    updateZoneGeometry(id: string, geometry: Polygon): Promise<Zone>;
    deleteZone(id: string): Promise<void>;
    bulkImportZones(data: any, format: string): Promise<any>;
    bulkUpdateZones(zones: any[]): Promise<any>;
}
export declare const zoneService: ZoneService;
export {};
//# sourceMappingURL=zone.service.d.ts.map