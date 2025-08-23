import { Document } from 'mongoose';
import { ROSCalculationOutput } from '../types';
export interface ICalculation extends Document {
    cropType: string;
    plantings: Array<{
        plantingDate: Date;
        areaRai: number;
        growthDays?: number;
    }>;
    calculationDate: Date;
    calculationPeriod: 'daily' | 'weekly' | 'monthly';
    results: ROSCalculationOutput;
    metadata: {
        calculatedBy?: string;
        sourceFile?: string;
        parameters?: any;
        processingTime?: number;
        version?: string;
    };
    tags?: string[];
    createdAt: Date;
    updatedAt: Date;
}
export declare const CalculationModel: any;
//# sourceMappingURL=calculationModel.d.ts.map