import mongoose, { Schema, Document } from 'mongoose';

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

const ReportSchema = new Schema<IReport>({
  calculationId: {
    type: String,
    required: true,
    index: true
  },
  format: {
    type: String,
    enum: ['pdf', 'excel', 'csv'],
    required: true
  },
  filename: {
    type: String,
    required: true
  },
  filePath: {
    type: String,
    required: true
  },
  status: {
    type: String,
    enum: ['pending', 'generating', 'completed', 'failed'],
    default: 'pending'
  },
  metadata: {
    generatedBy: String,
    options: Schema.Types.Mixed,
    error: String
  },
  generatedAt: {
    type: Date,
    default: Date.now
  },
  expiresAt: Date
}, {
  timestamps: true
});

// Index for cleanup queries
ReportSchema.index({ generatedAt: 1 });
ReportSchema.index({ status: 1, generatedAt: 1 });

export const ReportModel = mongoose.model<IReport>('Report', ReportSchema);