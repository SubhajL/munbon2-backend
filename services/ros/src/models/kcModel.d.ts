import { Document } from 'mongoose';
export interface IKc extends Document {
    cropType: string;
    growthWeek: number;
    kcValue: number;
    growthStage?: string;
    description?: string;
    source?: string;
    createdAt: Date;
    updatedAt: Date;
}
export declare const KcModel: any;
//# sourceMappingURL=kcModel.d.ts.map