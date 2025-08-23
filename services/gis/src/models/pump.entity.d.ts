import { Point } from 'geojson';
export declare enum PumpType {
    CENTRIFUGAL = "centrifugal",
    SUBMERSIBLE = "submersible",
    TURBINE = "turbine",
    AXIAL_FLOW = "axial_flow",
    MIXED_FLOW = "mixed_flow"
}
export declare enum PumpStatus {
    OPERATIONAL = "operational",
    STANDBY = "standby",
    MAINTENANCE = "maintenance",
    FAULTY = "faulty",
    DECOMMISSIONED = "decommissioned"
}
export declare class Pump {
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
    createdAt: Date;
    updatedAt: Date;
}
//# sourceMappingURL=pump.entity.d.ts.map