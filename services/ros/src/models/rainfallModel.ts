import mongoose, { Schema, Document } from 'mongoose';

export interface IRainfall extends Document {
  location?: string;
  year: number;
  month: number;
  totalRainfall: number; // mm/month
  effectiveRainfall: number; // mm/month
  numberOfRainyDays?: number;
  maxDailyRainfall?: number;
  probabilityOfRain?: number;
  source?: string;
  createdAt: Date;
  updatedAt: Date;
}

const RainfallSchema = new Schema<IRainfall>({
  location: {
    type: String,
    default: 'Munbon'
  },
  year: {
    type: Number,
    required: true
  },
  month: {
    type: Number,
    required: true,
    min: 1,
    max: 12
  },
  totalRainfall: {
    type: Number,
    required: true,
    min: 0
  },
  effectiveRainfall: {
    type: Number,
    required: true,
    min: 0
  },
  numberOfRainyDays: {
    type: Number,
    min: 0,
    max: 31
  },
  maxDailyRainfall: Number,
  probabilityOfRain: {
    type: Number,
    min: 0,
    max: 100
  },
  source: {
    type: String,
    default: 'Excel lookup table'
  }
}, {
  timestamps: true
});

// Compound index for efficient lookups
RainfallSchema.index({ year: 1, month: 1, location: 1 }, { unique: true });

export const RainfallModel = mongoose.model<IRainfall>('Rainfall', RainfallSchema);