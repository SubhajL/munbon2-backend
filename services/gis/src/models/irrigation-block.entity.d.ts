import { Polygon } from 'geojson';
import { Zone } from './zone.entity';
export declare class IrrigationBlock {
    id: string;
    code: string;
    name: string;
    geometry: Polygon;
    area: number;
    zoneId: string;
    zone: Zone;
    waterAllocation?: number;
    irrigationSchedule?: Array<{
        dayOfWeek: number;
        startTime: string;
        endTime: string;
        allocation: number;
    }>;
    properties?: Record<string, any>;
    createdAt: Date;
    updatedAt: Date;
}
//# sourceMappingURL=irrigation-block.entity.d.ts.map