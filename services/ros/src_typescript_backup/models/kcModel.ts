import mongoose, { Schema, Document } from 'mongoose';

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

const KcSchema = new Schema<IKc>({
  cropType: {
    type: String,
    required: true,
    index: true
  },
  growthWeek: {
    type: Number,
    required: true,
    min: 1
  },
  kcValue: {
    type: Number,
    required: true,
    min: 0,
    max: 2
  },
  growthStage: {
    type: String,
    enum: ['initial', 'development', 'mid-season', 'late-season', 'harvest']
  },
  description: String,
  source: {
    type: String,
    default: 'Excel lookup table'
  }
}, {
  timestamps: true
});

// Compound index for efficient lookups
KcSchema.index({ cropType: 1, growthWeek: 1 }, { unique: true });

export const KcModel = mongoose.model<IKc>('Kc', KcSchema);