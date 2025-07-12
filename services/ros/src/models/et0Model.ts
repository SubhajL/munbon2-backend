import mongoose, { Schema, Document } from 'mongoose';

export interface IET0 extends Document {
  location?: string;
  year: number;
  month: number;
  et0Value: number; // mm/month
  temperature?: number; // Average temperature
  humidity?: number; // Average relative humidity
  windSpeed?: number; // Average wind speed
  solarRadiation?: number; // Average solar radiation
  source?: string;
  method?: string;
  createdAt: Date;
  updatedAt: Date;
}

const ET0Schema = new Schema<IET0>({
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
  et0Value: {
    type: Number,
    required: true,
    min: 0
  },
  temperature: Number,
  humidity: Number,
  windSpeed: Number,
  solarRadiation: Number,
  source: {
    type: String,
    default: 'Excel lookup table'
  },
  method: {
    type: String,
    enum: ['lookup', 'penman-monteith', 'hargreaves', 'blaney-criddle'],
    default: 'lookup'
  }
}, {
  timestamps: true
});

// Compound index for efficient lookups
ET0Schema.index({ year: 1, month: 1, location: 1 }, { unique: true });

export const ET0Model = mongoose.model<IET0>('ET0', ET0Schema);