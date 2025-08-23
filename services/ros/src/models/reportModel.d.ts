import { Document } from 'mongoose';
export interface IReport extends Document {
    calculationId: string;
    format: 'pdf' | 'excel' | 'csv';
    filename: string;
    filePath: string;
    status: 'pending' | 'generating' | 'completed' | 'failed';
    metadata: {
        generatedBy?: string;
        options?: any;
        error?: string;
    };
    generatedAt: Date;
    expiresAt?: Date;
    createdAt: Date;
    updatedAt: Date;
}
export declare const ReportModel: any;
//# sourceMappingURL=reportModel.d.ts.map