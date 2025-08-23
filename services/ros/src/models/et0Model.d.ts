import { Document } from 'mongoose';
export interface IET0 extends Document {
    location?: string;
    year: number;
    month: number;
    et0Value: number;
    temperature?: number;
    humidity?: number;
    windSpeed?: number;
    solarRadiation?: number;
    source?: string;
    method?: string;
    createdAt: Date;
    updatedAt: Date;
}
export declare const ET0Model: any;
//# sourceMappingURL=et0Model.d.ts.map