import { Point } from 'geojson';
import { Canal } from './canal.entity';
export declare enum GateType {
    MAIN = "main",
    CHECK = "check",
    FARM = "farm",
    REGULATOR = "regulator",
    SPILLWAY = "spillway",
    INTAKE = "intake"
}
export declare enum GateStatus {
    OPERATIONAL = "operational",
    MAINTENANCE = "maintenance",
    FAULTY = "faulty",
    CLOSED = "closed"
}
export declare enum GateControlType {
    MANUAL = "manual",
    ELECTRIC = "electric",
    HYDRAULIC = "hydraulic",
    PNEUMATIC = "pneumatic",
    SCADA = "scada"
}
export declare class Gate {
    id: string;
    structureCode: string;
    structureName: string;
    structureType: string;
    canalId?: string;
    location: Point;
    elevationMsl?: number;
    maxDischargeCms?: number;
    scadaTag?: string;
    operationalStatus?: string;
    canal?: Canal;
    createdAt: Date;
    updatedAt: Date;
    get geoJSON(): any;
}
//# sourceMappingURL=gate.entity.d.ts.map