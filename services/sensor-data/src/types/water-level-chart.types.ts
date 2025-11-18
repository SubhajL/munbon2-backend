/**
 * Raw database row from water_level_readings table
 */
export interface WaterLevelReadingRow {
  time: Date | string;
  sensor_id: string;
  avg_level?: string | number;
  min_level?: string | number;
  max_level?: string | number;
  avg_quality?: string | number;
  sample_count?: string | number;
  source?: 'raw' | 'smoothed'; // Added to distinguish data origin
}

/**
 * Single data point in a sensor's chart data
 */
export interface WaterLevelDataPoint {
  time: string;
  avgLevel: number | null;
  minLevel: number | null;
  maxLevel: number | null;
  avgQuality: number | null;
  sampleCount: number;
}

/**
 * Chart data for a single sensor
 */
export interface WaterLevelSensorData {
  sensorId: string;
  plotId?: string | null;
  thresholds?: {
    lower: number | null;
    upper: number | null;
  };
  dataPoints: WaterLevelDataPoint[];
  smoothedDataPoints?: WaterLevelDataPoint[]; // Added for smoothed data overlay
  stats: {
    totalSamples: number;
    timeRange: {
      start: string;
      end: string;
    };
  };
}

/**
 * Complete formatted chart response with all sensors
 */
export interface WaterLevelChartResponse {
  aggregation: {
    interval: string;
    method: string;
  };
  period: '24h' | '3d' | '7d' | '14d';
  timeRange: {
    start: string;
    end: string;
  };
  localTimeZone: string;
  sensors: Record<string, WaterLevelSensorData>;
  summary: {
    totalSensors: number;
    totalDataPoints: number;
  };
}
