import { Polygon } from 'geojson';
import { Parcel } from './parcel.entity';
import { Canal } from './canal.entity';
import { IrrigationBlock } from './irrigation-block.entity';
export declare enum ZoneType {
    IRRIGATION = "irrigation",
    ADMINISTRATIVE = "administrative",
    WATERSHED = "watershed",
    CULTIVATION = "cultivation"
}
export declare enum ZoneStatus {
    ACTIVE = "active",
    INACTIVE = "inactive",
    MAINTENANCE = "maintenance"
}
export declare class Zone {
    id: string;
    zoneCode: string;
    zoneName: string;
    zoneType?: string;
    areaHectares: number;
    boundary: Polygon;
    parcels: Parcel[];
    canals: Canal[];
    irrigationBlocks: IrrigationBlock[];
    createdAt: Date;
    updatedAt: Date;
    get geoJSON(): any;
}
//# sourceMappingURL=zone.entity.d.ts.map