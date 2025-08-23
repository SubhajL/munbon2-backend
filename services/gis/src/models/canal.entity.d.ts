import { LineString } from 'geojson';
import { Zone } from './zone.entity';
import { Gate } from './gate.entity';
export declare enum CanalType {
    MAIN = "main",
    LATERAL = "lateral",
    SUB_LATERAL = "sub_lateral",
    FIELD = "field",
    DRAINAGE = "drainage"
}
export declare enum CanalStatus {
    OPERATIONAL = "operational",
    MAINTENANCE = "maintenance",
    DAMAGED = "damaged",
    ABANDONED = "abandoned"
}
export declare enum CanalCondition {
    EXCELLENT = "excellent",
    GOOD = "good",
    FAIR = "fair",
    POOR = "poor",
    CRITICAL = "critical"
}
export declare class Canal {
    id: string;
    canalCode: string;
    canalName: string;
    canalType?: string;
    lengthMeters: number;
    widthMeters?: number;
    depthMeters?: number;
    capacityCms?: number;
    geometry: LineString;
    upstreamNodeId?: string;
    downstreamNodeId?: string;
    zone?: Zone;
    gates: Gate[];
    createdAt: Date;
    updatedAt: Date;
    get geoJSON(): any;
}
//# sourceMappingURL=canal.entity.d.ts.map