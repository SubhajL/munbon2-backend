import { WaterDemandRequest, WaterDemandResponse } from '../types';
export declare class WaterDemandCalculatorService {
    private static instance;
    private databaseService;
    private kafkaService;
    private readonly cropCoefficients;
    private readonly irrigationEfficiencies;
    private readonly monthlyET0;
    private constructor();
    static getInstance(): WaterDemandCalculatorService;
    calculateWaterDemand(request: WaterDemandRequest): Promise<WaterDemandResponse>;
    private calculateParcelWaterDemand;
    private getCropCoefficient;
    calculateZoneWaterDemand(zone: string): Promise<any>;
    updateAllWaterDemands(): Promise<void>;
}
//# sourceMappingURL=water-demand-calculator.service.d.ts.map