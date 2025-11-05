/**
 * Raw database row from moisture_readings table
 */
export interface MoistureReadingRow {
  time: Date | string;
  sensor_id: string;
  moisture_surface_pct: string | number;
  moisture_deep_pct: string | number;
  avg_moisture_surface?: string | number;
  min_moisture_surface?: string | number;
  max_moisture_surface?: string | number;
  avg_moisture_deep?: string | number;
  min_moisture_deep?: string | number;
  max_moisture_deep?: string | number;
  sample_count?: string | number;
  temp_surface_c?: string | number | null;
  temp_deep_c?: string | number | null;
  ambient_temp_c?: string | number | null;
  ambient_humidity_pct?: string | number | null;
  voltage?: string | number | null;
  quality_score?: string | number;
}

/**
 * Single data point in a sensor's chart data
 */
export interface SensorDataPoint {
  time: string; // Local timezone ISO string
  avgMoistureSurface: number | null;
  minMoistureSurface: number | null;
  maxMoistureSurface: number | null;
  avgMoistureDeep: number | null;
  minMoistureDeep: number | null;
  maxMoistureDeep: number | null;
  sampleCount: number;
}

/**
 * Chart data for a single sensor
 */
export interface SensorChartData {
  sensorId: string;
  plotId?: string | null;
  thresholds?: {
    lower: number | null;
    upper: number | null;
  };
  dataPoints: SensorDataPoint[];
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
export interface MoistureChartResponse {
  aggregation: {
    interval: string;
    method: string;
  };
  period: '24h' | '3d' | '7d' | '14d';
  timeRange: {
    start: string; // UTC
    end: string; // UTC
  };
  localTimeZone: string;
  sensors: Record<string, SensorChartData>;
  summary: {
    totalSensors: number;
    totalDataPoints: number;
  };
}
