import mongoose, { Schema, Document } from 'mongoose';
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

const CalculationSchema = new Schema<ICalculation>({
  cropType: {
    type: String,
    required: true,
    index: true
  },
  plantings: [{
    plantingDate: {
      type: Date,
      required: true
    },
    areaRai: {
      type: Number,
      required: true
    },
    growthDays: Number
  }],
  calculationDate: {
    type: Date,
    required: true,
    index: true
  },
  calculationPeriod: {
    type: String,
    enum: ['daily', 'weekly', 'monthly'],
    required: true
  },
  results: {
    type: Schema.Types.Mixed,
    required: true
  },
  metadata: {
    calculatedBy: String,
    sourceFile: String,
    parameters: Schema.Types.Mixed,
    processingTime: Number,
    version: String
  },
  tags: [String]
}, {
  timestamps: true
});

// Indexes for efficient queries
CalculationSchema.index({ cropType: 1, calculationDate: -1 });
CalculationSchema.index({ 'metadata.calculatedBy': 1, createdAt: -1 });
CalculationSchema.index({ tags: 1 });

// Virtual for total area
CalculationSchema.virtual('totalArea').get(function() {
  return this.plantings.reduce((sum, p) => sum + p.areaRai, 0);
});

export const CalculationModel = mongoose.model<ICalculation>('Calculation', CalculationSchema);