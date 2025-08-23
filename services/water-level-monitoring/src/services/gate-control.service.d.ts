import { TimescaleService } from './timescale.service';
import { GateControlRecommendation, WaterLevelReading } from '../models/water-level.model';
export declare class GateControlService {
    private timescaleService;
    constructor(timescaleService: TimescaleService);
    generateRecommendation(gateId: string, sensorId: string, currentReading: WaterLevelReading): Promise<GateControlRecommendation | null>;
    private sendToScada;
    getGateStatus(gateId: string): Promise<any>;
}
//# sourceMappingURL=gate-control.service.d.ts.map