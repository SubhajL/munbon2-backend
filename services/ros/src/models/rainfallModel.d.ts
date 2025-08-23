import { Document } from 'mongoose';
export interface IRainfall extends Document {
    location?: string;
    year: number;
    month: number;
    totalRainfall: number;
    effectiveRainfall: number;
    numberOfRainyDays?: number;
    maxDailyRainfall?: number;
    probabilityOfRain?: number;
    source?: string;
    createdAt: Date;
    updatedAt: Date;
}
export declare const RainfallModel: any;
//# sourceMappingURL=rainfallModel.d.ts.map